"""Offline regression: public project manifests cannot leak private Drive URLs/IDs."""
import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from catalog import project_issues, project_progress

PROJECTS = [
    "campaigns/bavaria-new-year-2027/project.json",
    "campaigns/prague-new-year-2027/project.json",
]
EDITOR = "campaigns/vietnam-cambodia-2027/storyboard_option_2_SCENE_EDITOR.json"


class PublicMediaPrivacyTests(unittest.TestCase):
    def test_escrow_marker_preserves_state_without_embedded_urls(self):
        for rel in PROJECTS:
            p = ROOT / rel
            raw = p.read_text(encoding="utf-8")
            data = json.loads(raw)
            self.assertNotRegex(raw, r"https?://(?:drive|docs)\.google\.com/")
            self.assertEqual(data["private_media_redaction"]["status"],
                             "OWNER_PRIVATE_LOOKUP_REQUIRED")
            private = [x for x in data["assets"]
                       if x.get("storage") == "owner_private_drive"]
            self.assertTrue(private)
            self.assertTrue(all(x.get("url") == "" and
                                x.get("private_locator_status") == "OWNER_ONLY_LOOKUP_REQUIRED"
                                and x.get("private_locator_key") == "PRIVATE_MEDIA_ESCROW_20261117"
                                for x in private))
            self.assertFalse([e for e in project_issues(ROOT, p, data)
                              if "Invalid owner-private asset locator" in e])
            progress = project_progress(ROOT, p, data)
            self.assertEqual(set(progress["checks"]["private_asset_lookup_required"]),
                             {x["id"] for x in private})
            self.assertEqual(progress["checks"]["external_media_and_actual_publication"],
                             "NOT_VERIFIED_BY_CATALOG")

    def test_scene_editor_is_non_linkable_until_authorized_private_restore(self):
        editor = json.loads((ROOT / EDITOR).read_text(encoding="utf-8"))
        self.assertEqual(editor["private_media_redaction"]["status"],
                         "OWNER_PRIVATE_LOOKUP_REQUIRED")
        for i, sc in enumerate(editor["scenes"]):
            for name, a in sc["visual_alternatives"].items():
                self.assertFalse(a.get("url"), (i, name))
                self.assertFalse(a.get("drive_id"), (i, name))
            self.assertFalse(sc.get("selected_media_drive_url"), i)
            self.assertFalse(sc.get("selected_media_drive_file_id"), i)

    def test_rejects_attempt_to_reinsert_private_asset_link(self):
        p = ROOT / PROJECTS[0]
        data = json.loads(p.read_text(encoding="utf-8"))
        private = next(x for x in data["assets"] if x.get("storage") == "owner_private_drive")
        private["url"] = "https://drive.google.com/file/d/untrusted/view"
        issues = project_issues(ROOT, p, data)
        self.assertTrue(any(x.startswith("Invalid owner-private asset locator") for x in issues))

    def test_vietnam_cambodia_joins_registry_without_inventing_final_approval(self):
        p = ROOT / "campaigns/vietnam-cambodia-2027/project.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(data["id"], "vietnam-cambodia-2027")
        self.assertEqual(data["approvals"]["editorial"], "pending")
        self.assertEqual(data["approvals"]["publication"], "pending")
        self.assertIsNone(data["approved_asset_id"])
        self.assertIsNone(data["working_asset_id"])
        self.assertIn("Монтажер", data["next_action"])
        self.assertFalse(project_issues(ROOT, p, data))
        self.assertEqual(project_progress(ROOT, p, data)["state"], "IN_PROGRESS")
        self.assertEqual(project_progress(ROOT, p, data)["next_action"], data["next_action"])

    def test_vietnam_archived_a2e_clips_are_not_regenerated_or_marked_not_started(self):
        editor = json.loads((ROOT / EDITOR).read_text(encoding="utf-8"))
        registry = json.loads((ROOT / "campaigns/vietnam-cambodia-2027/project.json").read_text(encoding="utf-8"))
        self.assertEqual(editor["a2e_completed_mp4_count"], 10)
        self.assertEqual(len(editor["scenes"]), 10)
        self.assertNotIn("CLIPS_NOT_GENERATED", editor["media_status"])
        for i, scene in enumerate(editor["scenes"], 1):
            self.assertNotIn("NOT_STARTED", scene["media_status"], f"scene {i} was already generated")
            self.assertIn("FULL_DECODE_VERIFIED_NOT_FINAL", scene["media_status"])
            self.assertEqual(scene["scene_approval"], "IMAGE_SELECTED_OWNER")
        qa = editor["technical_media_qa_latest"]
        self.assertEqual(qa["verified_selected_stills"], 10)
        self.assertEqual(qa["verified_archived_a2e_mp4s"], 10)
        self.assertEqual(qa["video_full_decode_pass"], 10)
        self.assertEqual(qa["private_acl_checked_reference_ids"], 52)
        self.assertFalse(qa["paid_regeneration_authorized"])
        self.assertFalse(editor["studio_tts_produced"])
        self.assertFalse(editor["studio_music_selected"])
        self.assertFalse(editor["studio_final_master_ready"])
        self.assertEqual(registry["approvals"]["editorial"], "pending")
        self.assertEqual(registry["approvals"]["publication"], "pending")
        self.assertFalse(registry["technical_media_qa_latest"]["paid_regeneration_authorized"])
        self.assertIn("ПОВТОРНО ИСПОЛЬЗОВАТЬ", registry["next_action"])
        self.assertNotIn("Не подтверждена возможность открыть текущие 10", " ".join(registry["missing"]))
        self.assertNotRegex(json.dumps(editor, ensure_ascii=False), r"https?://(?:drive|docs)\.google\.com/")
        self.assertNotRegex(json.dumps(registry, ensure_ascii=False), r"https?://(?:drive|docs)\.google\.com/")

    def test_restoration_source_must_not_be_fake(self):
        data = json.loads((ROOT / PROJECTS[1]).read_text(encoding="utf-8"))
        self.assertNotIn("APPROVED_BY_BOT", json.dumps(data))
        self.assertTrue(data["private_media_redaction"]["escrow_key"])


if __name__ == "__main__":
    unittest.main()
