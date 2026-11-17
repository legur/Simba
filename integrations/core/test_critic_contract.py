"""Offline static contract checks for Simba CORE writing workflow.

This is documentation/transition consistency testing, not evidence that
the live GPT orchestration actually executed these gates.
"""
import unittest
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = {
    "AGENTS": "AGENTS.md",
    "ROUTER": "ROUTER_v10.1.md",
    "META": "META-Governance-v8.1.md",
    "SIMBA": "Симба (Писатель)/Simba-v5.0.md",
    "MARKETER": "AI-Marketer-Simba-by-Bon-Tours-v5.0.md",
    "PIPELINE": "SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/CONTENT_PIPELINE.md",
    "CRITIC": "Critic/Critic-5.7.md",
    "HUMANIZER": "Симба (Писатель)/Humanizer-v1.4.md",
}
TEXTS = {key: (ROOT / path).read_text(encoding="utf-8-sig")
         for key, path in FILES.items()}


class CoreCriticContractTests(unittest.TestCase):
    def test_every_core_owner_handles_no_progress_explicitly(self):
        for name in ("AGENTS", "ROUTER", "META", "SIMBA", "MARKETER", "PIPELINE", "CRITIC"):
            with self.subTest(module=name):
                self.assertIn("BLOCKED_CRITIC_NO_PROGRESS", TEXTS[name])
                self.assertIn("INTERNAL_CRITIC_PASS", TEXTS[name])

    def test_failed_critic_cannot_approve_or_enter_humanizer(self):
        pipeline = TEXTS["PIPELINE"]
        self.assertIn("{INTERNAL_CRITIC_PASS | BLOCKED_CRITIC_NO_PROGRESS → STOP}", pipeline)
        self.assertIn("[ТОЛЬКО ПРИ INTERNAL_CRITIC_PASS] SIMBA_FINALIZE", pipeline)
        self.assertIn("НЕ переходить к HUMANIZER/APPROVED/PUBLISHED", pipeline)
        self.assertNotIn("Цикл повторяется без искусственного лимита попыток", TEXTS["SIMBA"])

    def test_critic_no_progress_is_three_consecutive_unproductive_revisions(self):
        critic = TEXTS["CRITIC"]
        self.assertIn("трех последовательных исправлений", critic)
        self.assertIn("Не ставить фиктивный PASS", critic)
        self.assertIn("если после", critic.lower())
        self.assertIn("если есть содержательный прогресс", TEXTS["SIMBA"].lower())

    def test_post_approval_humanizer_remains_required(self):
        for name in ("AGENTS", "ROUTER", "META", "SIMBA", "PIPELINE"):
            with self.subTest(module=name):
                self.assertIn("HUMANIZER_PASS", TEXTS[name])

    def test_meta_component_versions_match_updated_canonical_docs(self):
        meta = TEXTS["META"]
        # Compare the first, actual version in each module against META.
        # Never hardcode a stale version number: this must keep working when
        # a neighboring CORE module is correctly revised by a later audit.
        modules = [
            ("Router", "ROUTER", r"^Версия:\\s*(\\d+\\.\\d+)"),
            ("Simba", "SIMBA", r"^Версия\\s*(\\d+\\.\\d+)"),
            ("AI-Маркетолог", "MARKETER", r"^Версия\\s*(\\d+\\.\\d+)"),
            ("Content Pipeline", "PIPELINE", r"^Версия:\\s*(\\d+\\.\\d+)"),
            ("Critic", "CRITIC", r"^\\*\\*Версия:\\*\\*\\s*(\\d+\\.\\d+)"),
        ]
        for component, module, pattern in modules:
            with self.subTest(component=component):
                match = re.search(pattern, TEXTS[module], re.M)
                self.assertIsNotNone(match, f"Missing active version in {module}")
                rows = [row for row in meta.splitlines()
                        if row.startswith("| " + component + " |")]
                self.assertEqual(len(rows), 1)
                # Require the version cell to contain the current version,
                # not just a number that happens to occur in older prose.
                self.assertEqual(rows[0].split("|")[3].strip().split()[0],
                                 match.group(1))


if __name__ == "__main__":
    unittest.main()
