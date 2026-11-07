"""Offline tests for the safe, manual OpenCut handoff."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opencut_handoff import HandoffError, build_handoff


class OpenCutHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = self.root / "job"
        self.job.mkdir()

    def write(self, relative: str, content: bytes = b"data") -> Path:
        path = self.job / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def make_job(self, *, scene_file: str = "media/scene.mp4") -> None:
        spec = {
            "packageId": "msc-ad",
            "sourcePost": "approved.md",
            "scenes": [{"clip": scene_file}, {"image": "media/still.jpg"}],
            "offer": {"bg": "media/still.jpg"},
            "end": {"poster": "media/poster.jpg", "bg": scene_file},
            "music": {"file": "music/licensed.mp3", "rights_confirmed": True},
        }
        timeline = {
            "lines": [{"id": "l01", "text": "Hello"}, {"id": "l02", "text": "Missing is optional"}],
            "clipAudio": [{"file": "voice/clip01.wav", "t0": 0}],
        }
        self.write("video-spec.json", json.dumps(spec).encode("utf-8"))
        self.write("timeline.json", json.dumps(timeline).encode("utf-8"))
        for relative in (
            "msc-ad.mp4", "msc-ad.srt", "cover.jpg", "qa-report.md",
            "media/scene.mp4", "media/still.jpg", "media/poster.jpg",
            "music/licensed.mp3", "voice/l01.wav", "voice/clip01.wav",
        ):
            self.write(relative, (relative + " content").encode())
        self.write("voice/.cache/private.attempt.json", b"must not be copied")
        self.write("out/frames/00001.jpg", b"derived frame must not be copied")

    def test_builds_explicit_editing_assets_and_truthful_manifest(self):
        self.make_job()
        before = {
            path.relative_to(self.job).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.job.rglob("*") if path.is_file()
        }

        output = build_handoff(self.job, self.root / "handoff")

        self.assertEqual(output, (self.root / "handoff").resolve())
        manifest = json.loads((output / "opencut-handoff.json").read_text(encoding="utf-8"))
        paths = [entry["path"] for entry in manifest["files"]]
        self.assertEqual(manifest["schema"], "simba-opencut-handoff/v1")
        self.assertEqual(manifest["project_import"], "manual")
        self.assertTrue(manifest["post_edit_qa_required"])
        self.assertEqual(manifest["post_edit_check"], "manual")
        for expected in (
            "video-spec.json", "timeline.json", "msc-ad.mp4", "msc-ad.srt",
            "cover.jpg", "qa-report.md", "media/scene.mp4", "media/still.jpg",
            "media/poster.jpg", "music/licensed.mp3", "voice/l01.wav",
            "voice/clip01.wav", "OPEN_IN_OPENCUT.md",
        ):
            self.assertIn(expected, paths)
            self.assertTrue((output / expected).is_file())
        self.assertNotIn("voice/l02.wav", paths)
        self.assertFalse((output / "voice/.cache").exists())
        self.assertFalse((output / "out").exists())
        self.assertTrue(all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in paths))
        self.assertTrue(all(set(entry) == {"path", "roles", "size", "sha256"} for entry in manifest["files"]))

        instructions = (output / "OPEN_IN_OPENCUT.md").read_text(encoding="utf-8")
        self.assertIn("ручного", instructions)
        self.assertIn("не файл проекта", instructions)
        self.assertIn("запечены и не редактируются по отдельности", instructions)
        self.assertIn("Отдельно вручную проверьте", instructions)
        self.assertIn("Автоматического возврата", instructions)
        after = {
            path.relative_to(self.job).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.job.rglob("*") if path.is_file()
        }
        self.assertEqual(before, after)

    def test_rejects_traversal_without_creating_output(self):
        self.make_job(scene_file="../secret.mp4")
        (self.root / "secret.mp4").write_bytes(b"secret")
        output = self.root / "handoff"

        with self.assertRaisesRegex(HandoffError, "inside the job folder"):
            build_handoff(self.job, output)

        self.assertFalse(output.exists())

    def test_rejects_referenced_symlink(self):
        self.make_job()
        target = self.root / "outside.mp4"
        target.write_bytes(b"outside")
        link = self.job / "media/scene.mp4"
        link.unlink()
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable for this Windows account")

        with self.assertRaisesRegex(HandoffError, "symlink"):
            build_handoff(self.job, self.root / "handoff")

    def test_existing_output_is_never_overwritten(self):
        self.make_job()
        output = self.root / "handoff"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")

        with self.assertRaisesRegex(HandoffError, "already exists"):
            build_handoff(self.job, output)

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        self.assertEqual([path.name for path in output.iterdir()], ["keep.txt"])

    def test_output_created_during_build_is_not_replaced_or_deleted(self):
        self.make_job()
        output = self.root / "handoff"
        real_mkdtemp = tempfile.mkdtemp

        def race(*args, **kwargs):
            stage = real_mkdtemp(*args, **kwargs)
            output.mkdir()
            (output / "foreign.txt").write_text("keep foreign data", encoding="utf-8")
            return stage

        with mock.patch("opencut_handoff.tempfile.mkdtemp", side_effect=race):
            with self.assertRaisesRegex(HandoffError, "appeared during build"):
                build_handoff(self.job, output)

        self.assertEqual((output / "foreign.txt").read_text(encoding="utf-8"), "keep foreign data")
        self.assertEqual([path.name for path in output.iterdir()], ["foreign.txt"])

    def test_rejects_reserved_and_case_insensitive_collisions(self):
        for first, second, message in (
            ("OPEN_IN_OPENCUT.md", "media/still.jpg", "reserved output path"),
            ("media/Scene.jpg", "media/scene.jpg", "portable path collision"),
        ):
            with self.subTest(first=first, second=second), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.job = root / "job"
                self.job.mkdir()
                self.make_job()
                spec_path = self.job / "video-spec.json"
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
                spec["scenes"] = [{"image": first}, {"image": second}]
                spec["offer"] = {}
                spec["end"] = {}
                spec_path.write_text(json.dumps(spec), encoding="utf-8")
                self.write(first, b"first")
                self.write(second, b"second")

                with self.assertRaisesRegex(HandoffError, message):
                    build_handoff(self.job, root / "handoff")
                self.assertFalse((root / "handoff").exists())

    def test_rejects_hidden_paths_and_wrong_extensions(self):
        for value, message in (
            (".cache/key.jpg", "hidden files or directories"),
            ("media/key.json", "safe extensions"),
        ):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.job = root / "job"
                self.job.mkdir()
                self.make_job()
                spec_path = self.job / "video-spec.json"
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
                spec["scenes"][0] = {"image": value}
                spec["end"]["bg"] = "media/still.jpg"
                spec_path.write_text(json.dumps(spec), encoding="utf-8")
                self.write(value, b"not an image")

                with self.assertRaisesRegex(HandoffError, message):
                    build_handoff(self.job, root / "handoff")
                self.assertFalse((root / "handoff").exists())

    def test_rejects_recursive_credential_fields_without_leaking_values(self):
        variants = (
            "api_key", "apiKey", "token", "password", "secret",
            "refresh_token", "refreshToken", "private_key", "privateKey",
            "accessToken", "client_secret",
            "GOOGLE_API_KEY", "GEMINI_API_KEY", "access_token",
            "service_account", "credentials", "authorization",
        )
        marker = "DO_NOT_LEAK_THIS_CREDENTIAL"
        for index, field in enumerate(variants):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.job = root / "job"
                self.job.mkdir()
                self.make_job()
                filename = "video-spec.json" if index % 2 == 0 else "timeline.json"
                path = self.job / filename
                value = json.loads(path.read_text(encoding="utf-8"))
                value["nested"] = [{"deeper": {field: marker}}]
                path.write_text(json.dumps(value), encoding="utf-8")

                with self.assertRaisesRegex(HandoffError, "credential field") as raised:
                    build_handoff(self.job, root / "handoff")
                self.assertIn(field, str(raised.exception))
                self.assertNotIn(marker, str(raised.exception))
                self.assertFalse((root / "handoff").exists())


if __name__ == "__main__":
    unittest.main()
