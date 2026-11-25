import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simba_voice
import simba_voice_issue as runner


class PrivateVoiceTest(unittest.TestCase):
    def setUp(self):
        self.parts = ["Первая часть.", "Вторая часть."]
        self.body = json.dumps({"kind": "simba_approved_voice", "parts": self.parts}).encode()
        self.digest = hashlib.sha256(self.body).hexdigest()
        self.event = {"repository": {"full_name": "legur/Simba"},
                      "sender": {"login": "legur"}, "inputs": {"request_sha256": self.digest}}
        self.env = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
                    "GITHUB_ACTOR": "legur", "GITHUB_TRIGGERING_ACTOR": "legur",
                    "GITHUB_REPOSITORY_OWNER": "legur", "GITHUB_REPOSITORY": "legur/Simba",
                    "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "a" * 40,
                    "GITHUB_WORKFLOW_SHA": "a" * 40, "GITHUB_WORKFLOW": "Simba approved voice private runner",
                    "GITHUB_WORKFLOW_REF": "legur/Simba/.github/workflows/simba-approved-voice-issue.yml@refs/heads/main"}

    def test_owner_dispatch_accepts_only_hash_input(self):
        with patch.dict(os.environ, self.env, clear=True):
            simba_voice._require_github_secrets_workflow()
        self.assertEqual(runner.request_digest(self.event, self.env), self.digest)
        for key in ("GITHUB_ACTOR", "GITHUB_TRIGGERING_ACTOR", "GITHUB_WORKFLOW_REF",
                    "GITHUB_SHA", "GITHUB_EVENT_NAME"):
            with self.subTest(key=key), patch.dict(os.environ, self.env | {key: "other"}, clear=True):
                with self.assertRaises(simba_voice.VoiceError):
                    simba_voice._require_github_secrets_workflow()
        issue = self.event | {"inputs": self.event["inputs"] | {"destination_folder_id": "private"}}
        with self.assertRaises(ValueError):
            runner.request_digest(issue, self.env)

    def test_requires_exact_bytes_and_limits(self):
        self.assertEqual(runner.parse_request(self.body, self.digest), self.parts)
        with self.assertRaises(ValueError):
            runner.parse_request(self.body + b" ", self.digest)
        for parts in ([], ["text"] * 2, ["x" * 451], self.parts + ["third"]):
            body = json.dumps({"kind": "simba_approved_voice", "parts": parts}).encode()
            with self.assertRaises(ValueError):
                runner.parse_request(body, hashlib.sha256(body).hexdigest())

    def test_drive_validation_precedes_read_and_synthesis(self):
        drive = Mock()
        item = {"name": f"simba-voice-request-{self.digest}.json", "mimeType": "application/json",
                "size": str(len(self.body)), "parents": ["folder_123456789"],
                "capabilities": {"canDownload": True},
                "permissions": [{"type": "user", "role": "reader"}]}
        with patch.object(runner.store, "_drive_list_all", return_value=[{"id": "file_123456789"}]), \
             patch.object(runner.store, "_get_drive_item", return_value=item):
            with self.assertRaises(runner.store.JobError):
                runner.read_private_request(drive, self.digest)
        drive.files.assert_not_called()

    def test_all_replay_checks_precede_paid_calls(self):
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(runner.store, "require_secret_environment"), \
             patch.object(runner.store, "oauth_drive_client"), \
             patch.object(runner, "read_private_request", return_value=("folder", self.parts)), \
             patch.object(runner.store, "_drive_matches", return_value=[]), \
             patch.object(runner.store, "ensure_no_global_marker", side_effect=[None, runner.store.ReplayBlocked("previous")]), \
             patch.object(runner.store, "create_attempt_marker") as marker, \
             patch.object(simba_voice, "synthesize_lines") as call:
            with self.assertRaises(runner.store.ReplayBlocked):
                runner.run(self.event, Path("."))
            marker.assert_not_called()
            call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
