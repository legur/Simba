"""Contract tests: no simulated approvals, no provider calls, no project writes."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import catalog
import handoff


class StageHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "campaigns/example").mkdir(parents=True)
        (self.root / "source.md").write_text("# Approved offer\n", encoding="utf-8")
        self.path = self.root / "campaigns/example/project.json"
        kinds = ("script", "storyboard", "animation_prompt", "animated_clip", "narration",
                 "music", "edit_plan", "review_video", "qa_report")
        self.project = {
            "schema_version": 1, "id": "example", "title": "Example", "aliases": ["Example"],
            "updated_at": "2026-11-10", "stage": "CREATION", "next_action": "Prepare reel",
            "sources": [{"path": "source.md", "sha256": catalog.digest(self.root / "source.md")}],
            "references": [],
            "assets": [{
                "id": kind, "title": kind, "kind": kind,
                "state": "available", "evidence": "Recorded source and reviewed by agent",
                "url": "https://drive.google.com/file/d/example-" + kind + "/view",
                **({"task_id": "task-12345"} if kind == "animated_clip" else {}),
            } for kind in kinds],
            "working_asset_id": None, "approved_asset_id": None,
            "approvals": {"editorial": "pending", "publication": "pending"},
            "missing": [],
        }
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.project, ensure_ascii=False), encoding="utf-8")

    def receipt(self, stage, record, expected):
        result, issues = handoff._validate_stage(self.project, stage, record, expected)
        self.assertEqual(issues, [])
        return result["receipt"]

    def complete_stage(self, stage, expected):
        kind = next(x[3] for x in handoff.STAGES if x[0] == stage)
        record = {
            "state": "completed" if stage in handoff.EXECUTION_STAGES else "approved",
            "input_fingerprint": expected, "assets": [kind],
            "approval_evidence": "Exact user decision recorded in stage session",
        }
        if stage in handoff.OPTIONS_STAGES:
            record.update(selected_option=2, options_presented=3,
                          options_evidence="All 3 variants in the stage session")
        if stage == "a2e_prompts":
            record.update(quoted_credits=25, max_credits=30, quote_evidence="Quote checked")
        if stage == "a2e_clips":
            record["task_evidence"] = "Task ID and completion report checked"
        if stage == "voice_music":
            record["assets"] = ["music", "narration"]
            record.update(text_option=1, music_option=3,
                          texts_presented=3, music_presented=3,
                          voice_profile="simba_warmbaritone",
                          music_license_evidence="Specific commercial-use license checked")
        if stage == "qa":
            record.update(qa_pass=True, qa_evidence="Observed QA PASS report")
        self.project.setdefault("stage_handoffs", {})[stage] = record
        return self.receipt(stage, record, expected)

    def test_first_stage_requires_explicit_script_selection(self):
        self.project["stage_handoffs"] = {}
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual((result["state"], result["recipient"]),
                         ("NEEDS_FIRST_STAGE", "SCENARIST"))
        self.assertFalse(result["paid_execution_authorized_by_handoff"])

    def test_selected_script_reaches_rafael_with_correct_fingerprint(self):
        expected = handoff.source_fingerprint(self.project)
        receipt = self.complete_stage("script", expected)
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual((result["state"], result["recipient"], result["packet"]["next_stage"]),
                         ("READY_FOR_HANDOFF", "RAFAEL", "storyboard"))
        self.assertEqual(result["packet"]["expected_input_fingerprint"], receipt)
        self.assertEqual(result["packet"]["lineage"][0]["decision"]["selected_option"], 2)

    def test_changing_source_prevents_handoff(self):
        expected = handoff.source_fingerprint(self.project)
        self.complete_stage("script", expected)
        (self.root / "source.md").write_text("Changed\n", encoding="utf-8")
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("STALE_SOURCE", " ".join(result["missing"]))

    def test_changing_upstream_choice_invalidates_following_stage(self):
        expected = handoff.source_fingerprint(self.project)
        expected = self.complete_stage("script", expected)
        self.complete_stage("storyboard", expected)
        self.project["stage_handoffs"]["script"]["selected_option"] = 3
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("input_fingerprint", " ".join(result["missing"]))

    def test_rejects_selection_without_three_options(self):
        expected = handoff.source_fingerprint(self.project)
        self.complete_stage("script", expected)
        self.project["stage_handoffs"]["script"]["options_presented"] = 2
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("three options", " ".join(result["missing"]))

    def test_rejects_forged_missing_approval_evidence(self):
        expected = handoff.source_fingerprint(self.project)
        self.complete_stage("script", expected)
        self.project["stage_handoffs"]["script"]["approval_evidence"] = ""
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("approval_evidence", " ".join(result["missing"]))

    def test_a2e_budget_over_limit_stops_handoff(self):
        expected = handoff.source_fingerprint(self.project)
        for stage in ("script", "storyboard", "a2e_prompts"):
            expected = self.complete_stage(stage, expected)
        self.project["stage_handoffs"]["a2e_prompts"]["quoted_credits"] = 100
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("quote/max_credits", " ".join(result["missing"]))

    def test_a2e_prompt_choice_passes_limit_but_never_runs(self):
        expected = handoff.source_fingerprint(self.project)
        for stage in ("script", "storyboard", "a2e_prompts"):
            expected = self.complete_stage(stage, expected)
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual((result["state"], result["recipient"]),
                         ("READY_FOR_HANDOFF", "A2E_RUNNER"))
        self.assertFalse(result["auto_dispatched"])
        self.assertFalse(result["paid_execution_authorized_by_handoff"])
        self.assertEqual(result["packet"]["decision"]["max_credits"], 30)

    def test_clip_missing_task_id_is_blocked(self):
        expected = handoff.source_fingerprint(self.project)
        for stage in ("script", "storyboard", "a2e_prompts", "a2e_clips"):
            expected = self.complete_stage(stage, expected)
        for asset in self.project["assets"]:
            if asset["id"] == "animated_clip":
                del asset["task_id"]
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("task_id", " ".join(result["missing"]))

    def test_voice_switch_without_approval_rejected(self):
        expected = handoff.source_fingerprint(self.project)
        for stage in ("script", "storyboard", "a2e_prompts", "a2e_clips", "voice_music"):
            expected = self.complete_stage(stage, expected)
        self.project["stage_handoffs"]["voice_music"]["voice_profile"] = "other_voice"
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("voice profile", " ".join(result["missing"]))

    def test_music_without_license_rejected(self):
        expected = handoff.source_fingerprint(self.project)
        for stage in ("script", "storyboard", "a2e_prompts", "a2e_clips", "voice_music"):
            expected = self.complete_stage(stage, expected)
        self.project["stage_handoffs"]["voice_music"]["music_license_evidence"] = ""
        self.assertIn("licensed music evidence",
                      " ".join(handoff.make_handoff(self.root, self.path, self.project)["missing"]))

    def test_full_lineage_preserves_selected_acts_and_files(self):
        expected = handoff.source_fingerprint(self.project)
        for stage in handoff.STAGE_NAMES:
            expected = self.complete_stage(stage, expected)
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "NEEDS_LEO_REVIEW")
        packet = result["packet"]
        self.assertEqual(len(packet["lineage"]), len(handoff.STAGE_NAMES))
        self.assertEqual(packet["assets"][0]["kind"], "script")
        self.assertEqual(packet["assets"][-1]["kind"], "qa_report")
        self.assertFalse(result["auto_dispatched"])
        self.assertFalse(result["external_media_verified"])

    def test_approved_final_does_not_publish(self):
        expected = handoff.source_fingerprint(self.project)
        for stage in handoff.STAGE_NAMES:
            expected = self.complete_stage(stage, expected)
        self.project["approved_asset_id"] = "review_video"
        self.project["approvals"].update(editorial="approved",
                                          editorial_evidence="Explicit approval of review_video")
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "APPROVED_UNPUBLISHED")
        self.assertFalse(result["auto_dispatched"])

    def test_legacy_review_requires_existing_working_video_and_qa(self):
        self.project["stage"] = "VIDEO_REVIEW"
        self.project["working_asset_id"] = "review_video"
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "NEEDS_LEO_REVIEW")
        self.assertEqual(result["packet"]["qa_status"], "RECORDED_NOT_REVERIFIED")
        self.project["working_asset_id"] = None
        self.assertEqual(handoff.make_handoff(self.root, self.path, self.project)["state"],
                         "BLOCKED")

    def test_cli_handoff_is_read_only(self):
        self.project["stage_handoffs"] = {}
        self.save()
        before = self.path.read_bytes()
        with redirect_stdout(StringIO()) as captured:
            status = handoff.main(["--root", str(self.root), "--json", "Example"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(captured.getvalue())["state"], "NEEDS_FIRST_STAGE")
        self.assertEqual(before, self.path.read_bytes())

    def test_all_report_only_has_non_failing_exit_for_known_blockers(self):
        self.save()
        with redirect_stdout(StringIO()) as captured:
            rc = handoff.main(["--root", str(self.root), "--json", "--report-only", "all"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(captured.getvalue())[0]["state"], "BLOCKED")


    def test_out_of_order_stages_are_blocked(self):
        self.project["stage_handoffs"] = {
            "qa": {"state": "completed", "qa_pass": True, "qa_evidence": "unrelated"}
        }
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "STAGE_ORDER_GAP")

    def test_qa_without_pass_is_blocked(self):
        expected = handoff.source_fingerprint(self.project)
        for stage in handoff.STAGE_NAMES:
            expected = self.complete_stage(stage, expected)
        self.project["stage_handoffs"]["qa"]["qa_pass"] = False
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("qa: pass", " ".join(result["missing"]))


    def test_legacy_explicit_final_approval_does_not_request_review_again(self):
        self.project["stage"] = "EDITORIAL_APPROVED__PUBLICATION_PENDING"
        self.project["working_asset_id"] = "review_video"
        self.project["approved_asset_id"] = "review_video"
        self.project["approvals"].update(
            editorial="approved",
            editorial_evidence="User accepted exact MP4 SHA-256"
        )
        self.project["missing"] = ["separate publication instruction"]
        result = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(result["state"], "APPROVED_UNPUBLISHED")
        self.assertEqual(result["packet"]["approved_asset_id"], "review_video")
        self.assertEqual(result["packet"]["next_stage"], "publication_decision")
        self.assertFalse(result["auto_dispatched"])
        self.assertFalse(result["external_media_verified"])

if __name__ == "__main__":
    unittest.main()
