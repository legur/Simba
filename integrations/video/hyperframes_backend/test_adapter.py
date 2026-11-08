import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


from hyperframes_backend import render
from hyperframes_backend.adapter import _probe_video


class HyperFramesAdapterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # The CLI below intentionally produces a byte stub, not an encoded MP4.
        # Isolate its adapter-contract tests from the host's installed ffprobe.
        # The real probe is tested separately against its subprocess boundary.
        probe_patch = patch("hyperframes_backend.adapter._probe_video")
        self.probe = probe_patch.start()
        self.addCleanup(probe_patch.stop)
        self.root = Path(self.temp.name)
        self.job = self.root / "job"
        (self.job / "assets").mkdir(parents=True)
        (self.job / "assets" / "photo.jpg").write_bytes(b"not-decoded-by-the-cli-stub")
        self.output = self.job / "out" / "video.mp4"
        self.plan = {
            "size": [1080, 1920],
            "dur": 1.25,
            "crossfade": 0.2,
            "motion": "anime",
            "scenes": [{"t0": 0.0, "t1": 1.0, "image": "assets/photo.jpg"}],
            "offer": None,
            "lines": [],
            "music": {"style": "calm"},
            "plucks": [],
            "clipAudio": [],
            "end": {"t0": 1.0, "bg": "assets/photo.jpg", "brand": "Simba"},
        }

    def _fake_cli(self, *, create_output=True, exit_code=0):
        cli = self.root / "fake-hyperframes.mjs"
        cli.write_text(
            """
import fs from 'fs';
import path from 'path';
const args = process.argv.slice(2);
const project = args[args.indexOf('render') + 1];
const out = args[args.indexOf('--output') + 1];
const composition = args[args.indexOf('--composition') + 1];
const html = fs.readFileSync(path.join(project, composition), 'utf8');
const timeline = fs.readFileSync(path.join(project, '.simba-hyperframes', 'timeline.json'), 'utf8');
fs.writeFileSync(path.join(project, 'hyperframes-invocation.json'), JSON.stringify({
  args,
  html,
  timeline,
  env: {
    gemini: process.env.GEMINI_API_KEY ?? null,
    gdrive: process.env.GDRIVE_TOKEN ?? null,
    ffmpeg: process.env.HYPERFRAMES_FFMPEG_PATH ?? null,
    browser: process.env.HYPERFRAMES_BROWSER_PATH ?? null,
    telemetry: process.env.HYPERFRAMES_NO_TELEMETRY ?? null,
    doNotTrack: process.env.DO_NOT_TRACK ?? null,
  },
}));
if (__CREATE_OUTPUT__) {
  fs.mkdirSync(path.dirname(out), {recursive: true});
  fs.writeFileSync(out, Buffer.alloc(128, 7));
}
process.exit(__EXIT_CODE__);
""".replace("__CREATE_OUTPUT__", "true" if create_output else "false")
            .replace("__EXIT_CODE__", str(exit_code)).strip(),
            encoding="utf-8",
        )
        return cli, {"HYPERFRAMES_CLI": str(cli)}

    def test_render_builds_self_contained_composition_and_invokes_cli(self):
        cli, env = self._fake_cli()
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(render(self.job, self.plan, 24, self.output))

        invocation = json.loads((self.job / "hyperframes-invocation.json").read_text(encoding="utf-8"))
        args = invocation["args"]
        self.assertEqual(args[:2], ["render", str(self.job.resolve())])
        self.assertIn(str(cli), os.environ.get("HYPERFRAMES_CLI", str(cli)))
        self.assertEqual(args[args.index("--fps") + 1], "24")
        self.assertEqual(args[args.index("--workers") + 1], "1")
        self.assertIn("--no-best-effort", args)
        self.assertIn("--strict", args)
        self.assertEqual(args[args.index("--composition") + 1], ".simba-hyperframes/index.html")
        self.assertIn('window.__timelines["simba-main"]', invocation["html"])
        self.assertNotIn("data-no-timeline", invocation["html"])
        self.assertIn('data-duration="1.25"', invocation["html"])
        self.assertNotIn("<audio", invocation["html"])
        generated_plan = json.loads(invocation["timeline"])
        self.assertEqual(generated_plan["scenes"][0]["image"], "/assets/photo.jpg")
        self.assertEqual(generated_plan["end"]["bg"], "/assets/photo.jpg")
        self.assertEqual(self.output.stat().st_size, 128)
        self.probe.assert_called_once()
        self.assertEqual(self.probe.call_args.args[1:3], (1.25, 24))
        runtime_film = (self.job / ".simba-hyperframes" / "runtime" / "template" / "film.js").read_text(encoding="utf-8")
        self.assertIn("/.simba-hyperframes/timeline.json", runtime_film)

    def test_render_waits_for_extracted_frame_scenes_before_capture(self):
        frames = self.job / "frames" / "clip"
        frames.mkdir(parents=True)
        (frames / "00001.jpg").write_bytes(b"frame")
        plan = json.loads(json.dumps(self.plan))
        plan["scenes"][0] = {
            "t0": 0.0,
            "t1": 1.0,
            "frames": "frames/clip/",
            "fps": 24,
            "count": 1,
        }
        _, env = self._fake_cli()
        with patch.dict(os.environ, env, clear=False):
            render(self.job, plan, 24, self.output)
        invocation = json.loads((self.job / "hyperframes-invocation.json").read_text(encoding="utf-8"))
        generated_plan = json.loads(invocation["timeline"])
        self.assertEqual(generated_plan["scenes"][0]["frames"], "/frames/clip/")
        self.assertIn("window.__simbaPendingFrame", invocation["html"])
        self.assertIn("__hfWaitForSeekCompletion", invocation["html"])
        self.assertIn('Object.defineProperty(window, "__hfWaitForSeekCompletion"', invocation["html"])
        self.assertIn("await window.prepare(time)", invocation["html"])
        self.assertIn("seek(time)", invocation["html"])

    def test_render_rejects_asset_outside_job(self):
        plan = json.loads(json.dumps(self.plan))
        plan["scenes"][0]["image"] = "../outside.jpg"
        with self.assertRaisesRegex(RuntimeError, "outside the job"):
            render(self.job, plan, 24, self.output)

    def test_render_fails_when_cli_reports_success_without_output(self):
        _, env = self._fake_cli(create_output=False)
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(RuntimeError, "did not create"):
                render(self.job, self.plan, 24, self.output)

    def test_render_preserves_existing_output_when_cli_fails(self):
        self.output.parent.mkdir(parents=True)
        self.output.write_bytes(b"previous-good-video")
        _, env = self._fake_cli(create_output=False, exit_code=7)
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(RuntimeError, "exit code 7"):
                render(self.job, self.plan, 24, self.output)
        self.assertEqual(self.output.read_bytes(), b"previous-good-video")
        leftovers = list(self.output.parent.glob(f".{self.output.name}.hyperframes-*.mp4"))
        self.assertEqual(leftovers, [])

    def test_render_atomically_replaces_existing_output_after_success(self):
        self.output.parent.mkdir(parents=True)
        self.output.write_bytes(b"previous-good-video")
        _, env = self._fake_cli()
        with patch.dict(os.environ, env, clear=False):
            render(self.job, self.plan, 24, self.output)
        self.assertEqual(self.output.read_bytes(), bytes([7]) * 128)

    def test_render_preserves_existing_output_when_ffprobe_rejects_temporary_video(self):
        self.output.parent.mkdir(parents=True)
        self.output.write_bytes(b"previous-good-video")
        _, env = self._fake_cli()
        with patch.dict(os.environ, env, clear=False), patch(
            "hyperframes_backend.adapter._probe_video",
            side_effect=RuntimeError("ffprobe found no video stream"),
        ):
            with self.assertRaisesRegex(RuntimeError, "no video stream"):
                render(self.job, self.plan, 24, self.output)
        self.assertEqual(self.output.read_bytes(), b"previous-good-video")

    def test_render_does_not_forward_secrets_but_keeps_local_tool_paths(self):
        _, env = self._fake_cli()
        env.update({
            "GEMINI_API_KEY": "must-not-leak",
            "GDRIVE_TOKEN": "must-not-leak",
            "HYPERFRAMES_FFMPEG_PATH": "C:/local/ffmpeg.exe",
            "HYPERFRAMES_BROWSER_PATH": "C:/local/chrome.exe",
        })
        with patch.dict(os.environ, env, clear=False):
            render(self.job, self.plan, 24, self.output)
        invocation = json.loads((self.job / "hyperframes-invocation.json").read_text(encoding="utf-8"))
        self.assertIsNone(invocation["env"]["gemini"])
        self.assertIsNone(invocation["env"]["gdrive"])
        self.assertEqual(invocation["env"]["ffmpeg"], "C:/local/ffmpeg.exe")
        self.assertEqual(invocation["env"]["browser"], "C:/local/chrome.exe")
        self.assertEqual(invocation["env"]["telemetry"], "1")
        self.assertEqual(invocation["env"]["doNotTrack"], "1")

    def test_render_passes_explicit_ffmpeg_to_hyperframes(self):
        ffmpeg = self.root / "tools" / "ffmpeg.exe"
        ffmpeg.parent.mkdir()
        ffmpeg.write_bytes(b"tool-placeholder")
        _, env = self._fake_cli()
        with patch.dict(os.environ, env, clear=False):
            render(self.job, self.plan, 24, self.output, ffmpeg=ffmpeg)
        invocation = json.loads((self.job / "hyperframes-invocation.json").read_text(encoding="utf-8"))
        self.assertEqual(invocation["env"]["ffmpeg"], str(ffmpeg.resolve()))


class ProbeVideoTest(unittest.TestCase):
    def probe(self, metadata, returncode=0):
        result = SimpleNamespace(returncode=returncode, stdout=json.dumps(metadata), stderr="invalid MP4" if returncode else "")
        with patch("hyperframes_backend.adapter.shutil.which", return_value="/tools/ffprobe"), patch(
            "hyperframes_backend.adapter.subprocess.run", return_value=result
        ) as run:
            _probe_video(Path("temporary.mp4"), 1.25, 24)
        return run.call_args.args[0]

    def test_probe_accepts_video_with_expected_duration(self):
        command = self.probe({"streams": [{"codec_type": "video"}], "format": {"duration": "1.25"}})
        self.assertEqual(command[0], "/tools/ffprobe")
        self.assertEqual(command[-1], "temporary.mp4")

    def test_probe_rejects_invalid_mp4(self):
        with self.assertRaisesRegex(RuntimeError, "ffprobe rejected"):
            self.probe({}, returncode=1)

    def test_probe_rejects_output_without_video(self):
        with self.assertRaisesRegex(RuntimeError, "no video stream"):
            self.probe({"streams": [], "format": {"duration": "1.25"}})

    def test_probe_rejects_wrong_duration(self):
        with self.assertRaisesRegex(RuntimeError, "duration mismatch"):
            self.probe({"streams": [{"codec_type": "video"}], "format": {"duration": "12.5"}})


if __name__ == "__main__":
    unittest.main()

