"""Offline regression for Wix CMS -> GitHub inbox, no tokens or network."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from uuid import UUID

MODULE = Path(__file__).resolve().with_name("wix_github_inbox.py")
spec = importlib.util.spec_from_file_location("wix_github_inbox", MODULE)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def sample():
    sel = {
        "schema": "bontours.motionlab.storyboard.selection/v1",
        "request_id": "studio-123",
        "project_id": "bavaria",
        "stage": "edit_choice",
        "expected_input_fingerprint": "f" * 64,
        "decision": {"selected_option": 2, "options_presented": 3,
                     "state": "DRAFT_NOT_DELIVERED"},
        "guards": {"run_render": False, "run_tts": False, "run_a2e": False,
                   "run_paid_operations": False, "auto_publish": False,
                   "preserve_approved_voice": True,
                   "preserve_approved_music": True,
                   "preserve_approved_narration": True},
        "scenes": [{"scene_id": "scene-1", "camera": {"id": "float"}}],
    }
    return {"id": "wix-item-1", "data": {
        "_owner": "member-allowed", "state": "PENDING",
        "projectId": "bavaria", "sessionId": "studio-123",
        "deliveryId": "bb4aa134-7a22-4894-876a-f8f94f64be7c",
        "sourceFingerprint": "f" * 64,
        "selectionSha256": q.digest(sel), "selection": sel,
    }}


class InboxTests(unittest.TestCase):
    def test_valid_selection_preserved_but_not_approved(self):
        got = q.validate_item(sample(), "member-allowed")
        self.assertEqual(got["status"],
                         "STORED_IN_GITHUB_PENDING_MONTAGE_SOURCE_VERIFICATION")
        self.assertEqual(got["selection"]["decision"]["selected_option"], 2)
        self.assertFalse(got["render_authorized"])
        self.assertFalse(got["publication_authorized"])

    def test_non_owner_blocked(self):
        with self.assertRaisesRegex(q.QueueError, "WIX_MEMBER_NOT_ALLOWLISTED"):
            q.validate_item(sample(), "different-member")

    def test_hash_tamper_blocked(self):
        row = sample()
        row["data"]["selection"]["decision"]["selected_option"] = 1
        with self.assertRaisesRegex(q.QueueError, "SELECTION_HASH_OR_SIZE_MISMATCH"):
            q.validate_item(row, "member-allowed")

    def test_paid_action_blocked(self):
        row = sample()
        row["data"]["selection"]["guards"]["run_tts"] = True
        row["data"]["selectionSha256"] = q.digest(row["data"]["selection"])
        with self.assertRaisesRegex(q.QueueError, "PAID_OR_SOURCE_GUARD_VIOLATION"):
            q.validate_item(row, "member-allowed")

    def test_untrusted_media_url_rejected(self):
        row = sample()
        row["data"]["selection"]["privateUrl"] = "https://example.com/secret"
        row["data"]["selectionSha256"] = q.digest(row["data"]["selection"])
        with self.assertRaisesRegex(q.QueueError, "FORBIDDEN_SELECTION_FIELD"):
            q.validate_item(row, "member-allowed")

    def test_duplicate_delivery_id_format(self):
        row = sample()
        row["data"]["deliveryId"] = "../main"
        with self.assertRaisesRegex(q.QueueError, "INVALID_DELIVERY_ID"):
            q.validate_item(row, "member-allowed")

    def test_stale_revision_blocked(self):
        row = sample()
        row["data"]["sourceFingerprint"] = "a" * 64
        with self.assertRaisesRegex(q.QueueError, "SELECTION_SOURCE_MISMATCH"):
            q.validate_item(row, "member-allowed")

    def test_recovery_after_wix_ack_failure_does_not_rewrite(self):
        row = sample()
        class Fake:
            def __init__(self):
                self.items = [row]
                self.github = {}
                self.calls = 0
                self.fail_ack = True
            def wix_pending(self):
                return self.items
            def github_store(self, record):
                k = record["delivery_id"]
                raw = q.encoded(record)
                if k in self.github and self.github[k] != raw:
                    raise q.QueueError("DUPLICATE_DELIVERY_ID_DIFFERENT_PAYLOAD")
                self.github[k] = raw
                self.calls += 1
                return "c" * 40
            def wix_ack(self, item_id, commit):
                if self.fail_ack:
                    raise q.QueueError("WIX_API_HTTP_500")
                self.items = []
        api = Fake()
        first = q.run(api, "member-allowed")
        self.assertEqual(first["blocked"], 1)
        self.assertEqual(first["stored"], 0)
        api.fail_ack = False
        second = q.run(api, "member-allowed")
        self.assertEqual(second["stored"], 1)
        self.assertEqual(len(api.github), 1)
        self.assertEqual(second["paid_calls"], 0)


if __name__ == "__main__":
    unittest.main()
