"""Read-only checks against actual Simba source files, not synthetic role calls."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editorial_readonly_audit as audit

ROOT = Path(__file__).resolve().parents[2]


class ReadOnlyEditorialPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = audit.audit_existing_archive()

    def test_all_21_declared_core_dependencies_are_real_and_read(self):
        report = self.report
        self.assertEqual(report["actual_kb_docs_read"], len(audit.REQUIRED_CORE_FILES))
        self.assertEqual(report["actual_kb_docs_read"], 21)
        self.assertEqual(len(report["kb_content_sha256"]), 21)
        self.assertTrue(all(len(value) == 64
                            for value in report["kb_content_sha256"].values()))

    def test_real_approved_vietnam_archive_is_indexed_and_not_published(self):
        r = self.report
        self.assertTrue(r["indexed"])
        self.assertTrue(r["archive_explicitly_unpublished"])
        self.assertEqual(r["archived_approval_status"], "DECLARED_APPROVED_TEXT")
        self.assertTrue(r["leo_approval_note_recorded"])
        self.assertFalse(r["leo_approval_independently_verified"])
        self.assertEqual(r["source_sha256"], audit.fingerprint(audit.VIETNAM_CASE))

    def test_run_cannot_claim_unobserved_simba_critic_or_humanizer(self):
        r = self.report
        self.assertFalse(r["role_execution_observed_this_run"])
        self.assertFalse(r["critic_receipt_recorded_in_archive_header"])
        self.assertFalse(r["humanizer_receipt_recorded_in_archive_header"])
        self.assertEqual(r["outcome"], "BLOCKED_LIVE_EXECUTOR_NOT_RUN")
        self.assertIn("EXECUTOR_NOT_INVOKED_IN_THIS_READ_ONLY_RUN", r["blockers"])
        self.assertIn("INTERNAL_CRITIC_NOT_INVOKED_IN_THIS_READ_ONLY_RUN", r["blockers"])
        self.assertIn("HUMANIZER_NOT_INVOKED_IN_THIS_READ_ONLY_RUN", r["blockers"])

    def test_real_pdf_claim_must_not_be_treated_as_available(self):
        r = self.report
        self.assertFalse(r["pdf_fulfillment_verified"])
        self.assertIn("BLOCKED_FULFILLMENT_NOT_VERIFIED", r["blockers"])
        self.assertIn("PUBLICATION_AUTHORIZATION_NOT_VERIFIED", r["blockers"])
        self.assertFalse(r["publication_confirmation_observed"])

    def test_unavailable_kb_file_is_not_replaced_by_model_memory(self):
        prior = audit.REQUIRED_CORE_FILES
        try:
            audit.REQUIRED_CORE_FILES = ("MISSING-NONEXISTENT-RULE-FOR-TEST.md",)
            r = audit.audit_existing_archive()
            self.assertEqual(r["outcome"], "BLOCKED_KB_UNAVAILABLE")
        finally:
            audit.REQUIRED_CORE_FILES = prior

    def test_nonexistent_archive_is_not_presented_as_source(self):
        r = audit.audit_existing_archive(ROOT / "does_not_exist.md")
        self.assertEqual(r["outcome"], "SOURCE_BLOCKED")

    def test_does_not_claim_true_live_executor_or_independent_approval(self):
        source = (ROOT / "integrations/core/editorial_readonly_audit.py").read_text(encoding="utf-8")
        self.assertIn("No agent, API or paid task is run", source)
        self.assertIn('"leo_approval_independently_verified": False', source)
        self.assertIn('"role_execution_observed_this_run": False', source)


if __name__ == "__main__":
    unittest.main()
