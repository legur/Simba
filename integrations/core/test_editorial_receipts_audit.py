"""Negative and consistency tests: no claim of authentic provider execution."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from editorial_live_runner import CoreRun
from editorial_receipts_audit import IntegrityBlocked, audit_receipts


class OfflineFake:
    kind = "LIVE_OPENAI_RESPONSES"  # deliberate spoof to exercise fail-closed
    def __init__(self, replies):
        self.replies = list(replies)
        self.sequence = 0

    def create(self, role, instructions, user_input, schema=None):
        self.sequence += 1
        return {
            "text": self.replies.pop(0),
            "response_id": f"fake_res_{self.sequence}",
            "request_id": f"fake_req_{self.sequence}",
            "model": "fake-model",
            "at": "2026-11-18T07:00:00+00:00",
        }


def verdict(decision="PASS", score=9.0, issues=None):
    return json.dumps({
        "decision": decision, "score": score,
        "blocking_issues": issues if issues is not None else [],
        "rationale": "offline fixture",
    })


def make_fake_report(replies):
    runner = CoreRun(OfflineFake(replies), max_calls=12)
    result = runner.execute("Offline fake: no publication or claims.")
    # Even when client.kind spoofs LIVE, the actual runner remains fail-closed.
    assert result["state"] == "DECLARED_TEST_ONLY"
    report = runner.report(result["state"], {"text_sha256": result["text_sha256"]})
    # Deliberately forge JSON fields for the parser: integrity is not authenticity.
    report["status"] = "LIVE_EDITORIAL_PILOT_UNVERIFIED"
    report["mode"] = "LIVE_OPENAI_RESPONSES"
    for item in report["receipts"]:
        item["transport"] = "LIVE_OPENAI_RESPONSES"
    return report, result["text"]


class ReceiptIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.report, self.text = make_fake_report([
            "Тестовая публикация не разрешена.", verdict(),
            "Тестовая публикация не разрешена.",
            "Тестовая публикация не разрешена.",
        ])

    def assert_blocked(self, code, report=None, text=None):
        with self.assertRaisesRegex(IntegrityBlocked, code):
            audit_receipts(report if report is not None else self.report,
                           self.text if text is None else text)

    def test_forged_json_can_only_get_declared_integrity(self):
        result = audit_receipts(self.report, self.text)
        self.assertEqual(result["status"],
                         "DECLARED_RECEIPTS_CONSISTENT_AUTHENTICITY_UNVERIFIED")
        self.assertFalse(result["leo_approval_verified"])
        self.assertFalse(result["publication_authorized"])

    def test_original_fake_report_never_passes_live_filter(self):
        report = copy.deepcopy(self.report)
        report["status"] = "DECLARED_TEST_ONLY"
        self.assert_blocked("NO_LIVE_PILOT_STATUS", report)

    def test_changed_text_is_blocked(self):
        self.assert_blocked("FINAL_TEXT_DIGEST_MISMATCH", text="tampered text")

    def test_changed_source_digest_is_blocked(self):
        report = copy.deepcopy(self.report)
        report["receipts"][1]["source_text_sha256"] = "0" * 64
        self.assert_blocked("CRITIC_WRONG_REVISION", report)

    def test_duplicate_provider_ids_are_blocked(self):
        report = copy.deepcopy(self.report)
        report["receipts"][1]["provider_response_id"] = report["receipts"][0]["provider_response_id"]
        self.assert_blocked("DUPLICATE_PROVIDER_IDS", report)

    def test_inconsistent_sequence_is_blocked(self):
        report = copy.deepcopy(self.report)
        report["receipts"][1]["sequence"] = 9
        self.assert_blocked("RECEIPT_ORDER_INVALID", report)

    def test_self_granted_approval_is_blocked(self):
        report = copy.deepcopy(self.report)
        report["ready_for_production"] = True
        self.assert_blocked("AUTHORITY_ESCALATION", report)
        report["ready_for_production"] = False
        report["publication_authorized"] = True
        self.assert_blocked("AUTHORITY_ESCALATION", report)

    def test_critic_pass_below_threshold_is_blocked(self):
        report = copy.deepcopy(self.report)
        report["receipts"][1]["critic_verdict"]["score"] = 7.5
        self.assert_blocked("CRITIC_INVALID_PASS", report)

    def test_critic_revise_without_simba_repair_is_blocked(self):
        report = copy.deepcopy(self.report)
        report["receipts"][1]["critic_verdict"] = {
            "decision": "REVISE", "score": 6, "blocking_issues": ["Слабый хук"]}
        self.assert_blocked("EXPECTED_SIMBA_REPAIR", report)

    def test_unreviewed_humanizer_output_is_blocked(self):
        report = copy.deepcopy(self.report)
        report["receipts"][-1]["output_sha256"] = "1" * 64
        self.assert_blocked("EDITORIAL_SEQUENCE_INCOMPLETE", report)

    def test_missing_critic_verdict_is_blocked(self):
        report = copy.deepcopy(self.report)
        del report["receipts"][1]["critic_verdict"]
        self.assert_blocked("CRITIC_VERDICT_MISSING", report)

    def test_repair_sequence_can_be_consistent_but_not_authenticated(self):
        report, text = make_fake_report([
            "Плохой текст.", verdict("REVISE", 6, ["Неясно"]),
            "Исправленный текст.", verdict(),
            "Исправленный текст.", "Исправленный текст."])
        result = audit_receipts(report, text)
        self.assertEqual(result["receipts_checked"], 6)
        self.assertTrue(result["status"].startswith("DECLARED_"))

    def test_finalize_change_requires_second_critic(self):
        report, text = make_fake_report([
            "Ранняя редакция.", verdict(), "Поздняя редакция.", verdict(),
            "Поздняя редакция."])
        self.assertEqual(audit_receipts(report, text)["receipts_checked"], 5)
        report["receipts"].pop(3)
        report["invocation_count"] -= 1
        self.assert_blocked("RECEIPT_ORDER_INVALID|CRITIC_WRONG_REVISION|EXPECTED_HUMANIZER",
                            report, text)

    def test_humanizer_change_requires_second_critic(self):
        report, text = make_fake_report([
            "Ранняя редакция.", verdict(), "Ранняя редакция.",
            "Поздняя редакция.", verdict()])
        self.assertEqual(audit_receipts(report, text)["receipts_checked"], 5)
        report["receipts"].pop()
        report["invocation_count"] -= 1
        self.assert_blocked("EDITORIAL_SEQUENCE_INCOMPLETE", report, text)


if __name__ == "__main__":
    unittest.main()
