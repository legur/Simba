"""No-network contract tests for Motion Lab to Simba/HyperFrames transitions."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import make_video


class MotionLabTransitionsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.job = Path(temp.name)
        for image in ("s1.png", "s2.png"):
            (self.job / image).write_bytes(b"placeholder: no image decode at spec validation")
        self.spec = {
            "packageId": "motionlab-test",
            "sourcePost": "content/APPROVED.md",
            "renderer": "simba",
            "scenes": [{"image": "s1.png"}, {"image": "s2.png"}],
            "end": {"cta": "Test"}
        }

    def read(self):
        (self.job / "video-spec.json").write_text(
            json.dumps(self.spec, ensure_ascii=False), encoding="utf-8"
        )
        return make_video.load_spec(self.job)

    def test_all_thirty_ids_match_javascript_renderer(self):
        source = (ROOT / "template" / "transitions.js").read_text(encoding="utf-8")
        constants = source.split("export const TRANSITION_IDS =", 1)[1].split("]);", 1)[0]
        js_ids = set(re.findall(r"'([a-z]+)'", constants))
        self.assertEqual(make_video.TRANSITIONS, js_ids)
        self.assertEqual(len(js_ids), 30)

    def test_spec_transition_survives_timeline_for_both_engines(self):
        self.spec["scenes"][1]["transition"] = {"id": "portal", "duration_ms": 900}
        spec = self.read()
        self.assertEqual(spec["scenes"][1]["transition"]["id"], "portal")
        timeline = make_video.timeline(spec)
        self.assertIsNone(timeline["scenes"][0]["transition"])
        self.assertEqual(timeline["scenes"][1]["transition"], {"id": "portal", "duration_ms": 900})

    def test_old_video_spec_remains_backward_compatible(self):
        spec = self.read()
        self.assertNotIn("transition", spec["scenes"][1])
        self.assertIsNone(make_video.timeline(spec)["scenes"][1]["transition"])

    def test_invalid_transitions_are_rejected_before_render(self):
        invalid = [
            (0, {"id": "portal", "duration_ms": 900}),
            (1, {"id": "unknown", "duration_ms": 900}),
            (1, {"id": ["portal"], "duration_ms": 900}),
            (1, {"id": "portal", "duration_ms": 2500}),
            (1, {"id": "portal", "duration_ms": 399}),
            (1, {"id": "portal", "duration_ms": True}),
            (1, {"id": "portal", "duration_ms": "900"}),
        ]
        for scene_index, tr in invalid:
            with self.subTest(transition=tr, scene=scene_index):
                self.spec["scenes"] = [{"image": "s1.png"}, {"image": "s2.png"}]
                self.spec["scenes"][scene_index]["transition"] = tr
                with self.assertRaises(make_video.Stop):
                    self.read()


if __name__ == "__main__":
    unittest.main()
