"""Offline tests ONLY: fake outputs must never create a live-ready receipt."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editorial_live_runner as live


class FakeClient:
    kind = "SIMULATED_OFFLINE"
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, role, instructions, user_input, schema=None):
        self.calls.append((role, user_input, instructions, schema))
        if not self.replies:
            raise AssertionError("Unexpected model call")
        return {
            "text": self.replies.pop(0),
            "response_id": "FAKE_DO_NOT_TRUST",
            "request_id": "FAKE_DO_NOT_TRUST",
            "model": "offline-fixture",
            "at": "2000-01-01T00:00:00+00:00",
        }


def verdict(decision="PASS", score=8.5, issues=None):
    return json.dumps({
        "decision": decision,
        "score": score,
        "blocking_issues": issues if issues is not None else [],
        "rationale": "Offline test only",
    })


class CoreLiveRunnerTests(unittest.TestCase):
    def test_real_KB_profiles_are_read(self):
        for role in ("Simba", "Critic", "Humanizer"):
            self.assertIn("=====", live.rule_context(role))
            self.assertTrue(live.rule_context(role))

    def test_mandatory_core_preflight_is_loaded_for_each_role(self):
        for role in ("Simba", "Critic", "Humanizer"):
            rules = live.rule_context(role)
            self.assertIn("KB_RUNTIME_PROTOCOL.md", rules)
            self.assertIn("KNOWLEDGE_MAP.md", rules)
            self.assertIn("CONTENT_PIPELINE.md", rules)
            self.assertIn("PATTERN_WATCH.md", rules)

    def test_spoofed_client_kind_cannot_claim_live(self):
        class SpoofedFake(FakeClient):
            kind = "LIVE_OPENAI_RESPONSES"
        fake = SpoofedFake(["Черновик.", verdict(), "Черновик.", "Черновик."])
        run = live.CoreRun(fake)
        result = run.execute("Только синтетический тест.")
        self.assertEqual(result["state"], "DECLARED_TEST_ONLY")
        report = run.report(result["state"])
        self.assertEqual(report["mode"], "UNTRUSTED_TEST_TRANSPORT")
        self.assertTrue(all(r["transport"] == "UNTRUSTED_TEST_TRANSPORT"
                            for r in report["receipts"]))
        self.assertFalse(report["ready_for_production"])
        self.assertFalse(report["source_resolution_verified"])
        self.assertFalse(report["dynamic_fact_check_verified"])

    def test_no_change_during_repair_blocks_without_extra_calls(self):
        fake = FakeClient(["Тот же текст.", verdict("REVISE", 6.0, ["Слабый хук"]),
                           "Тот же текст."])
        runner = live.CoreRun(fake)
        with self.assertRaisesRegex(live.Blocked, "SIMBA_REPAIR_NO_TEXT_CHANGE"):
            runner.execute("Одна тестовая редакция.")
        self.assertEqual(len(runner.receipts), 3)

    def test_mock_sequence_never_returns_live_ready(self):
        client = FakeClient(["Исходный текст.", verdict(), "Исходный текст.", "Исходный текст."])
        runner = live.CoreRun(client)
        result = runner.execute("Подготовь короткий безопасный тестовый пост.")
        self.assertEqual(result["state"], "DECLARED_TEST_ONLY")
        self.assertEqual([r["role"] for r in runner.receipts],
                         ["Simba", "Critic", "Simba", "Humanizer"])
        self.assertEqual(runner.receipts[1]["source_text_sha256"],
                         runner.receipts[0]["output_sha256"])
        self.assertEqual(runner.receipts[2]["source_text_sha256"],
                         runner.receipts[0]["output_sha256"])
        self.assertEqual(runner.receipts[3]["source_text_sha256"],
                         runner.receipts[2]["output_sha256"])
        report = runner.report(result["state"])
        self.assertFalse(report["publication_authorized"])
        self.assertFalse(report["leo_approval_verified"])
        self.assertEqual(report["mode"], "SIMULATED_OFFLINE")

    def test_independent_critic_rechecks_changed_finalize(self):
        fake = FakeClient([
            "Первый вариант.", verdict(), "Отредактированный вариант.", verdict(),
            "Отредактированный вариант.",
        ])
        run = live.CoreRun(fake)
        result = run.execute("Составь один пост.")
        self.assertEqual(result["state"], "DECLARED_TEST_ONLY")
        self.assertEqual([r["role"] for r in run.receipts],
                         ["Simba", "Critic", "Simba", "Critic", "Humanizer"])
        self.assertEqual(run.receipts[3]["source_text_sha256"],
                         run.receipts[2]["output_sha256"])

    def test_independent_critic_rechecks_humanizer_changes(self):
        fake = FakeClient([
            "Первый вариант.", verdict(), "Первый вариант.",
            "Второй вариант.", verdict(),
        ])
        run = live.CoreRun(fake)
        self.assertEqual(run.execute("Составь один пост.")["state"], "DECLARED_TEST_ONLY")
        self.assertEqual(run.receipts[-1]["source_text_sha256"],
                         run.receipts[-2]["output_sha256"])

    def test_humanizer_failed_recheck_blocks(self):
        fake = FakeClient([
            "Первый вариант.", verdict(), "Первый вариант.",
            "Испорченный вариант.", verdict("REVISE", 6.0, ["Смысл изменен"]),
        ])
        run = live.CoreRun(fake)
        with self.assertRaisesRegex(live.Blocked, "HUMANIZER_CHANGE_REQUIRES_SIMBA_REPAIR"):
            run.execute("Составь один пост.")
        self.assertEqual(len(run.receipts), 5)

    def test_critic_revise_really_returns_to_simba(self):
        fake = FakeClient([
            "Черновик.", verdict("REVISE", 6.5, ["Слабый хук"]),
            "Исправленный черновик.", verdict(), "Исправленный черновик.",
            "Исправленный черновик.",
        ])
        run = live.CoreRun(fake)
        result = run.execute("Один пост.")
        self.assertEqual(result["state"], "DECLARED_TEST_ONLY")
        self.assertEqual([x["step"] for x in run.receipts],
                         ["draft", "independent_critic", "repair",
                          "independent_critic", "finalize", "humanizer"])

    def test_finite_no_progress_blocks_after_three_repairs(self):
        issue = verdict("REVISE", 7.0, ["Нет понятной выгоды"])
        fake = FakeClient([
            "T1", issue, "T2", issue, "T3", issue, "T4", issue,
        ])
        run = live.CoreRun(fake, max_calls=12)
        with self.assertRaisesRegex(live.Blocked, "BLOCKED_CRITIC_NO_PROGRESS"):
            run.execute("Составь один пост.")
        self.assertEqual(len(run.receipts), 8)

    def test_bad_critic_pass_is_blocked(self):
        with self.assertRaisesRegex(live.Blocked, "CRITIC_UNSAFE_PASS"):
            live.checked_critic(verdict("PASS", 7.9))
        with self.assertRaisesRegex(live.Blocked, "CRITIC_UNSAFE_PASS"):
            live.checked_critic(verdict("PASS", 9.0, ["Факт не подтвержден"]))
        with self.assertRaisesRegex(live.Blocked, "CRITIC_REVISE_WITHOUT_ISSUES"):
            live.checked_critic(verdict("REVISE", 7.5))

    def test_missing_rule_causes_hard_block_before_calls(self):
        with patch.object(live, "ROOT", Path("/obviously-absent/simba")):
            with self.assertRaisesRegex(live.Blocked, "BLOCKED_KB_UNAVAILABLE"):
                live.CoreRun(FakeClient([]))

    def test_api_non_completed_and_refusal_are_blocked(self):
        with self.assertRaisesRegex(live.Blocked, "API_RESPONSE_NOT_COMPLETED"):
            live.response_output({"status": "incomplete"})
        with self.assertRaisesRegex(live.Blocked, "API_MODEL_REFUSAL"):
            live.response_output({"status": "completed", "output": [
                {"type": "message", "content": [{"type": "refusal"}]}]})

    def test_missing_key_never_makes_a_call(self):
        with self.assertRaisesRegex(live.Blocked, "OPENAI_KEY_OR_MODEL_MISSING"):
            live.OpenAIResponsesClient("gpt-6", None)

    def test_private_output_rejects_repo_path(self):
        with self.assertRaisesRegex(live.Blocked, "OUTPUT_MUST_BE_OUTSIDE_PUBLIC_REPOSITORY"):
            live._write_private(live.ROOT / "integrations" / "core", {"run_id": "fake"})

    def test_cli_without_billable_opt_in_never_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief = Path(tmp) / "brief.txt"
            brief.write_text("Техническая проверка одного поста.", encoding="utf-8")
            output = Path(tmp) / "out"
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                code = live.main(["--brief-file", str(brief),
                                  "--output-dir", str(output)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(capture.getvalue())["status"],
                             "BLOCKED_LIVE_EXECUTOR_NOT_RUN")
            self.assertFalse(output.exists())

    def test_billing_flags_alone_cannot_override_missing_model_or_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief = Path(tmp) / "brief.txt"
            brief.write_text("Техническая проверка.", encoding="utf-8")
            with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
                with contextlib.redirect_stderr(io.StringIO()) as stream:
                    code = live.main(["--brief-file", str(brief), "--output-dir", tmp,
                                      "--model", "gpt-6", "--execute-live",
                                      "--permit-billable-api-calls"])
            self.assertEqual(code, 1)
            self.assertIn("BLOCKED_RUNTIME_INTEGRATION", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
