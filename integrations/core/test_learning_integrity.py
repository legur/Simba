"""Offline invariants for Simba's Knowledge Base and Feedback Learning.

Rules-only test: these checks cannot prove that a live LLM actually retrieved
the right observations or applied them to a newly written Facebook post.
"""
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "SIMBA KNOWLEDGE BASE"
LIB = KB / "03_CONTENT_LIBRARY"
LEARN = KB / "07_LEARNINGS"
CORE = KB / "00_CORE"


def read(path):
    return path.read_text(encoding="utf-8-sig")


class LearningIntegrityTests(unittest.TestCase):
    def test_every_canonical_approved_file_in_current_index_exactly_once(self):
        index = read(LIB / "_INDEX.md")
        actual = {p.name for p in LIB.glob("*__APPROVED.md")}
        self.assertTrue(actual)
        linked = re.findall(r"\]\(([^)]+__APPROVED\.md)\)", index)
        counts = Counter(linked)
        self.assertEqual(actual, set(counts), "Some approved files are invisible to future learning")
        self.assertTrue(all(v == 1 for v in counts.values()), "Duplicated APPROVED index entries")
        self.assertTrue(all((LIB / name).is_file() for name in counts))

    def test_all_date_rows_belong_to_one_chronological_index_table(self):
        lines = read(LIB / "_INDEX.md").splitlines()
        head = next(i for i, s in enumerate(lines) if s.startswith("| Date | Title | Status"))
        self.assertTrue(lines[head + 1].startswith("|---|"))
        row = re.compile(r"^\|\s*(20\d{2}-\d\d-\d\d)\s*\|")
        entries = [(i, row.match(s).group(1)) for i, s in enumerate(lines)
                   if row.match(s)]
        self.assertGreaterEqual(len(entries), 40)
        self.assertEqual([i for i, _ in entries],
                         list(range(head + 2, head + 2 + len(entries))),
                         "One or more rows escaped the main table")
        dates = [date for _, date in entries]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_index_does_not_claim_publication_of_five_recovered_files(self):
        lines = read(LIB / "_INDEX.md").splitlines()
        recovered = [
            "2026-09-09__EXPERT-VIRAL__SOUCHASTNIK__APPROVED.md",
            "2026-09-09__SELLING__CELEBRITY-DOUBLE-POINTS__APPROVED.md",
            "2026-09-09__SELLING__ISRAIR-LAST-MINUTE__APPROVED.md",
            "2026-09-30__NEWS__VOLENDAM-129-DAYS__APPROVED.md",
            "2026-10-04__SELLING__LAST-MINUTE-POLAND-GEORGIA-AZERBAIJAN__APPROVED.md",
        ]
        for filename in recovered:
            with self.subTest(filename=filename):
                matches = [row for row in lines if filename in row]
                self.assertEqual(len(matches), 1)
                self.assertIn("publication not independently confirmed", matches[0])
                status = matches[0].split("|")[3].strip()
                self.assertTrue(status.startswith("APPROVED_TEXT"))
                self.assertNotEqual(status, "PUBLISHED")

    def test_old_critic_and_old_source_only_chain_are_explicitly_superseded(self):
        corrections = read(LEARN / "CORRECTIONS_LOG.md")
        active = corrections.split("## Уже закреплённые корректировки")[1].split("## Запись 05.09.2026")[0]
        self.assertIn("INTERNAL_CRITIC_MODE", active)
        self.assertIn("EXTERNAL_REVIEW_MODE", active)
        self.assertNotIn("он не является участником production-пайплайна", active)
        self.assertIn("ИСТОРИЧЕСКОЕ ПРАВИЛО / SUPERSEDED 08.09.2026", corrections)
        self.assertIn("ИСТОРИЧЕСКАЯ ЦЕПОЧКА / SUPERSEDED 08.09.2026", corrections)
        self.assertIn("SOURCE_RESOLUTION", corrections)
        self.assertIn("HUMANIZER_PASS", corrections)

    def test_feedback_signal_counts_only_independent_case_evidence(self):
        watch = read(LEARN / "PATTERN_WATCH.md")
        self.assertIn("1 **независимый содержательный разбор", watch)
        self.assertIn("на разных материалах", watch)
        self.assertIn("не умножает evidence", watch)
        self.assertIn("Critic/ChatGPT/Claude", watch)
        self.assertIn("ACTIVE RULE CANDIDATE", watch)
        self.assertIn("не является активным системным правилом", watch)
        self.assertLess(watch.index("## 02.11.2026"), watch.index("## Changelog"))

    def test_historical_style_mining_is_not_current_corpus_statistic(self):
        old = read(LEARN / "STYLE_FEEDBACK_MINING.md")
        self.assertIn("ИСТОРИЧЕСКИЙ SNAPSHOT 05.09.2026", old)
        self.assertIn("40 физических файлов", old)
        self.assertIn("не автоматически 40 доказанных фактов публикации", old)
        self.assertGreaterEqual(len(list(LIB.glob("*__APPROVED.md"))), 15)
        tracker = read(LIB / "_PATTERN_TRACKER.md")
        self.assertIn("не hard gate", tracker)
        self.assertIn("не текущий размер", tracker.lower())
        self.assertNotIn("следующий пост должен менять минимум две оси", tracker)

    def test_learning_lint_and_runtime_enforce_versioned_promotion(self):
        lint = read(CORE / "KB_LINT.md")
        runtime = read(CORE / "KB_RUNTIME_PROTOCOL.md")
        maptext = read(CORE / "KNOWLEDGE_MAP.md")
        agents = read(ROOT / "AGENTS.md")
        self.assertIn("### L10 — LEARNING PROVENANCE / SUPERSESSION", lint)
        self.assertIn("### L11 — CONTENT LIBRARY INDEX INTEGRITY", lint)
        self.assertIn("SUPERSEDED", runtime)
        self.assertIn("SUPERSEDED", maptext)
        self.assertIn("SUPERSEDED", agents)
        self.assertIn("ACTIVE RULE CANDIDATE", runtime)
        self.assertIn("L10/L11", agents)
        self.assertIn("L10", runtime)
        self.assertIn("L11", runtime)

    def test_meta_versions_for_active_kb_are_not_stale(self):
        meta = read(ROOT / "META-Governance-v8.1.md")
        for label, current in (
            ("Feedback Learning / PATTERN_WATCH", "2.2"),
            ("SIMBA Knowledge Base", "Knowledge Map 2.1 / runtime 9.3"),
        ):
            rows = [line for line in meta.splitlines()
                    if line.startswith(f"| {label} |")]
            self.assertEqual(len(rows), 1)
            self.assertIn(current, rows[0])


if __name__ == "__main__":
    unittest.main()
