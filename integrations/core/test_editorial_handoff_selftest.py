"""No-charge tests for a single synthetic Simba CORE handoff fixture."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editorial_handoff_selftest as smoke
import editorial_live_runner as live


class OfflineHandoffSmokeTests(unittest.TestCase):
    def test_one_synthetic_text_routes_three_roles_and_rechecks_changed_humanizer(self):
        with patch.object(live.OpenAIResponsesClient, "create",
                          side_effect=AssertionError("UNAUTHORIZED_REAL_PROVIDER_CALL")):
            result = smoke.run_offline_handoff_selftest()
        self.assertEqual(result["status"],
                         "OFFLINE_HANDOFF_CONTRACT_OK_NOT_AGENT_EXECUTION")
        self.assertEqual(result["roles_in_order"],
                         ["Simba", "Critic", "Simba", "Critic",
                          "Simba", "Humanizer", "Critic"])
        self.assertEqual(result["steps"],
                         ["draft", "independent_critic", "repair",
                          "independent_critic", "finalize",
                          "humanizer", "independent_critic"])
        self.assertEqual(result["receipts_checked"], 7)
        self.assertEqual(result["final_sha256"], live.sha(smoke.HUMANIZED))
        self.assertTrue(result["revision_binding_verified"])
        self.assertTrue(result["humanizer_revise_blocks_verified"])
        self.assertTrue(result["unchanged_simba_repair_blocks_verified"])
        self.assertFalse(result["live_calls_made"])
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["leo_approval_verified"])
        self.assertFalse(result["provider_receipts_authentic"])
        self.assertFalse(result["tests_real_role_orchestration"])

    def test_fake_transport_cannot_escalate_even_with_spoofed_kind(self):
        self.assertEqual(smoke.OfflineFixture.kind, "LIVE_OPENAI_RESPONSES")
        fixture = smoke.OfflineFixture([
            ("Simba", smoke.DRAFT),
            ("Critic", smoke._critic("PASS", 9.0, [])),
            ("Simba", smoke.DRAFT),
            ("Humanizer", smoke.DRAFT),
        ])
        run = live.CoreRun(fixture, max_calls=9)
        outcome = run.execute(smoke.BRIEF)
        self.assertEqual(outcome["state"], "DECLARED_TEST_ONLY")
        report = run.report(outcome["state"])
        self.assertEqual(report["mode"], "UNTRUSTED_TEST_TRANSPORT")
        self.assertTrue(all(r["transport"] == "UNTRUSTED_TEST_TRANSPORT"
                            for r in report["receipts"]))

    def test_role_mismatch_is_hard_error_and_no_receipt_is_claimed(self):
        fixture = smoke.OfflineFixture([("Critic", smoke.DRAFT)])
        run = live.CoreRun(fixture)
        with self.assertRaisesRegex(RuntimeError, "ROLE_HANDOFF_MISMATCH"):
            run.execute(smoke.BRIEF)
        self.assertEqual(len(run.receipts), 0)

    def test_critic_schema_cannot_be_skipped_in_fixture(self):
        fixture = smoke.OfflineFixture([("Critic", "{}")])
        with self.assertRaisesRegex(RuntimeError, "CRITIC_SCHEMA_HANDOFF_MISMATCH"):
            fixture.create("Critic", "Rules", "Test", schema=None)


if __name__ == "__main__":
    unittest.main()
