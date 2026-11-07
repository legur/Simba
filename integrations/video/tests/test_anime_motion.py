import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))
from make_video import Stop, load_spec, timeline


class AnimeMotionIntegrationTests(unittest.TestCase):
    def _load(self, motion=None):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            (job / "scene.jpg").write_bytes(b"fixture")
            spec = {
                "packageId": "motion-test",
                "sourcePost": "not-read-by-load-spec",
                "size": "1080x1920",
                "scenes": [{"image": "scene.jpg", "title": "Prague", "lines": []}],
            }
            if motion is not None:
                spec["motion"] = motion
            (job / "video-spec.json").write_text(json.dumps(spec), encoding="utf-8")
            with patch("music_input.validate_music", return_value=None):
                loaded = load_spec(job)
            return loaded

    def test_default_motion_is_anime_and_reaches_timeline(self):
        spec = self._load()
        self.assertEqual(spec["motion"], "anime")
        self.assertEqual(timeline(spec)["motion"], "anime")

    def test_editor_can_explicitly_select_classic(self):
        spec = self._load("classic")
        self.assertEqual(spec["motion"], "classic")
        self.assertEqual(timeline(spec)["motion"], "classic")

    def test_invalid_motion_fails_before_rendering(self):
        with self.assertRaisesRegex(Stop, r"motion must be one of \['anime', 'classic'\]"):
            self._load("spring")

    def test_animejs_is_pinned_and_template_uses_paused_seek(self):
        package = json.loads((VIDEO / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["dependencies"]["animejs"], "4.2.2")

        film = (VIDEO / "template" / "film.js").read_text(encoding="utf-8")
        self.assertIn("/node_modules/animejs/", film)
        self.assertRegex(film, r"autoplay\s*:\s*false")
        self.assertRegex(film, r"\.seek\(")
        self.assertIn("MOTION === 'classic'", film)
        self.assertIn("y + (1 - eo(p)) * h * 1.1", film)

    def test_render_contract_and_final_text_geometry_remain_stable(self):
        film = (VIDEO / "template" / "film.js").read_text(encoding="utf-8")
        self.assertIn("window.prepare = async t =>", film)
        self.assertIn("window.render = t =>", film)
        self.assertIn("window.TEXTS = t =>", film)
        self.assertIn("texts.push({ id: id ?? txt, text: txt, x0, y0:", film)

        # The motion layer must be derived from p and seekable, not clock-driven.
        self.assertIsNone(re.search(r"Date\.now|performance\.now|Math\.random", film))


if __name__ == "__main__":
    unittest.main()
