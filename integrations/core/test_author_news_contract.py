"""Offline consistency checks for non-Simba author and News routing.

These tests inspect rules. They do not claim that live GPT agents were executed.
"""
import unittest
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PATHS = {
    "agents": "AGENTS.md",
    "router": "ROUTER_v10.1.md",
    "meta": "META-Governance-v8.1.md",
    "runtime": "SIMBA KNOWLEDGE BASE/00_CORE/KB_RUNTIME_PROTOCOL.md",
    "pipeline": "SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/CONTENT_PIPELINE.md",
    "roles": "SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/AGENT_ROLES.md",
    "info": "Симба (Писатель)/Info-v1.2.md",
    "travel": "Симба (Писатель)/Travel-v1.3.md",
    "leo": "Симба (Писатель)/Leo-v1.3.md",
    "news": "Симба (Писатель)/News-v1.2.md",
}
TEXT = {name: (ROOT / path).read_text(encoding="utf-8-sig")
        for name, path in PATHS.items()}


class AuthorAndNewsContractTests(unittest.TestCase):
    def test_single_news_and_digest_are_different_routes(self):
        for name in ("agents", "router", "runtime", "pipeline", "roles", "news"):
            with self.subTest(source=name):
                self.assertIn("NEWS_SINGLE_EVENT", TEXT[name])
                self.assertIn("NEWS_DIGEST", TEXT[name])

    def test_news_uses_verified_existing_sources_and_blocks_when_missing(self):
        for name in ("router", "runtime", "pipeline", "roles", "news"):
            with self.subTest(source=name):
                self.assertIn("BLOCKED_NEWS_SOURCE_UNVERIFIED", TEXT[name])
        self.assertIn("USER_DIRECT_NEWS_TASK", TEXT["pipeline"])
        self.assertIn("SOURCE_RESOLUTION", TEXT["news"])
        self.assertNotIn("требуй от пользователя:\n1. **Источник каждой новости**", TEXT["news"])
        self.assertNotIn("Без этого дайджест не создавать. Это не предложение", TEXT["news"])
        self.assertNotIn("даты не старше месяца", TEXT["news"])
        self.assertIn("Дата", TEXT["news"])
        self.assertIn("источник", TEXT["news"].lower())

    def test_all_non_simba_authors_are_fail_closed_at_author_and_humanizer_gates(self):
        for name in ("info", "travel", "leo", "news"):
            with self.subTest(author=name):
                t = TEXT[name]
                self.assertIn("HUMANIZER_PASS", t)
                self.assertIn("BLOCKED_", t)
                self.assertNotIn("Если после второй не удовлетворяет — выводи лучшую версию", t)
                self.assertIn("AUTHOR", t)
                self.assertNotIn("INTERNAL_CRITIC_PASS", t)
        self.assertIn("BLOCKED_AUTHOR_PROVENANCE", TEXT["leo"])
        self.assertIn("BLOCKED_AUTHOR_PROVENANCE", TEXT["travel"])
        self.assertIn("не придумывай", TEXT["travel"].lower())
        self.assertIn("не подтверждены", TEXT["leo"])

    def test_explicit_ready_flow_and_humanizer_control_remain(self):
        t = TEXT["pipeline"]
        self.assertIn("NEWS_AUTHOR_QA_PASS", t)
        self.assertIn("NEWS_FINALIZE\n  → HUMANIZER_EXECUTED\n  → HUMANIZER_PASS", t)
        self.assertIn("NEWS_TEXT_READY", t)
        self.assertIn("Internal Critic автоматически не добавляется", TEXT["runtime"])

    def test_meta_versions_match_current_author_modules(self):
        meta = TEXT["meta"]
        expected = {
            "Router": "20.3",
            "Info": "1.3",
            "Travel": "1.4",
            "Leo": "1.4",
            "News": "1.3",
            "Content Pipeline": "11.2",
        }
        for label, version in expected.items():
            with self.subTest(component=label):
                matches = [x for x in meta.splitlines() if x.startswith(f"| {label} |")]
                self.assertEqual(len(matches), 1)
                self.assertIn(version, matches[0])

        # KB Runtime evolves independently from News. Compare META against
        # the current runtime header instead of pinning a stale 9.x constant.
        current = re.search(r"^Редакция: runtime (\d+\.\d+)", TEXT["runtime"], re.M)
        self.assertIsNotNone(current)
        kb = [row for row in meta.splitlines()
              if row.startswith("| SIMBA Knowledge Base |")]
        self.assertEqual(len(kb), 1)
        self.assertIn("runtime " + current.group(1), kb[0].split("|")[3])


if __name__ == "__main__":
    unittest.main()
