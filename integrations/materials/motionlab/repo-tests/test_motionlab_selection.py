"""Read-only contract tests for the Motion Lab selection receipt."""
import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("motionlab_selection", ROOT / "motionlab_selection.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

LAUNCH = json.loads((ROOT / "demo-launch.json").read_text(encoding="utf-8"))


def sample():
    rows = []
    for i, original in enumerate(LAUNCH["scenes"]):
        rows.append({
            "scene_id": original["scene_id"], "order": i + 1, "name": original["name"], "duration_seconds": original["duration_s"],
            "asset_id": original["asset_id"], "camera": {"id": "float", "intensity_percent": 35, "approximate_3d": False},
            "transition": None if i == 0 else {"id": "postcard", "duration_ms": 900},
            "title": {"effect_id": "light-sweep", "display_text": original["title_text"]},
            "subtitles": {"style_id": "luxury", "word_motion_id": "highlight-strip", "preview_text": original["subtitle_preview"], "timing_source": "NOT_PROVIDED_IN_STORYBOARD"},
        })
    return {
        "schema": "bontours.motionlab.storyboard.selection/v1", "request_id": LAUNCH["request_id"],
        "project_id": LAUNCH["project_id"], "stage": "edit_choice", "expected_input_fingerprint": LAUNCH["expected_input_fingerprint"],
        "decision": {"selected_option": 3, "options_presented": 3, "user_selected_at": "2026-11-10T16:44:00Z", "state": "USER_SELECTED_IN_CONNECTED_SESSION"},
        "format": "9:16", "scenes": rows,
        "guards": {"run_render": False, "run_tts": False, "run_a2e": False, "run_paid_operations": False, "auto_publish": False,
                   "preserve_approved_voice": True, "preserve_approved_music": True, "preserve_approved_narration": True},
        "next_stage": "MONTAGE_PLANNING_REVIEW",
    }


class ValidateContract(unittest.TestCase):
    def test_valid_receipt(self):
        result = mod.validate(LAUNCH, sample())
        self.assertTrue(result["accepted"])
        self.assertEqual(result["selected_option"], 3)
        self.assertFalse(result["auto_dispatched"])

    def test_stale_fingerprint_rejected(self):
        selection = sample()
        selection["expected_input_fingerprint"] = "b" * 64
        with self.assertRaisesRegex(mod.InvalidSelection, "stale"):
            mod.validate(LAUNCH, selection)

    def test_new_scenes_rejected(self):
        selection = sample()
        selection["scenes"].append(copy.deepcopy(selection["scenes"][-1]))
        with self.assertRaisesRegex(mod.InvalidSelection, "addition"):
            mod.validate(LAUNCH, selection)

    def test_deleted_scenes_rejected(self):
        selection = sample()
        selection["scenes"].pop()
        with self.assertRaisesRegex(mod.InvalidSelection, "addition"):
            mod.validate(LAUNCH, selection)

    def test_replacing_approved_asset_rejected(self):
        selection = sample()
        selection["scenes"][1]["asset_id"] = "unapproved-image"
        with self.assertRaisesRegex(mod.InvalidSelection, "source asset"):
            mod.validate(LAUNCH, selection)

    def test_paid_or_publish_actions_rejected(self):
        for key in mod.GUARDS:
            selection = sample()
            selection["guards"][key] = True
            with self.subTest(key=key), self.assertRaises(mod.InvalidSelection):
                mod.validate(LAUNCH, selection)

    def test_offline_draft_not_an_approval(self):
        selection = sample()
        selection["decision"]["state"] = "DRAFT_NOT_DELIVERED"
        with self.assertRaisesRegex(mod.InvalidSelection, "offline"):
            mod.validate(LAUNCH, selection)

    def test_three_options_required(self):
        launch = copy.deepcopy(LAUNCH)
        launch["options"].pop()
        with self.assertRaisesRegex(mod.InvalidSelection, "three choices"):
            mod.validate(launch, sample())

    def test_catalog_ids(self):
        self.assertEqual(len(mod.CAMERAS), 12)
        self.assertEqual(len(mod.TRANSITIONS), 31)  # 30 real effects plus the none sentinel
        self.assertEqual(len(mod.TITLE_FX), 16)  # 15 plus none
        self.assertEqual(len(mod.SUBTITLE_STYLES), 25)  # 24 plus none
        self.assertEqual(len(mod.WORD_MOTIONS), 5)


if __name__ == "__main__":
    unittest.main()