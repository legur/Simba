"""Deterministic negative-path smoke tests, including existing exact source files.

Synthetic declared traces are NOT real model-tool invocation evidence.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from editorial_trace import digest_text, validate_trace, validate_variant_set

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "SIMBA KNOWLEDGE BASE" / "03_CONTENT_LIBRARY"


def base(author="Simba", input_kind="SOURCE_ONLY", text="Достоверный тестовый текст."):
    start = (["SOURCE_RESOLVED", "ROUTER_TASK_CLASSIFIED"]
             if input_kind == "SOURCE_ONLY" else ["ROUTER_TASK_CLASSIFIED"])
    common = ["EXECUTOR_RULES_LOADED", "FACTS_VERIFIED",
              "INTRIGAN_SKIPPED", "TIA_CHECKED", "AUTHOR_DRAFTED", "AUTHOR_QA_PASS"]
    final = (["INTERNAL_CRITIC_PASS", "SIMBA_FINALIZE"] if author == "Simba"
             else ["AUTHOR_FINALIZE"])
    text_hash = digest_text(text)
    return {"id": "v1", "author": author, "input_kind": input_kind,
            "text": text, "events": start + common + final +
            ["HUMANIZER_PASS", "TEXT_READY_FOR_LEO", "LEO_APPROVED", "ARCHIVED_APPROVED"],
            "approval_sha256": text_hash, "archive_sha256": text_hash,
            "approval_evidence": "synthetic fixture only - NOT an actual Leo approval",
            "publication_requested": False}


class EditorialSmokeTests(unittest.TestCase):
    def test_source_only_simba_complete_is_approved_not_published(self):
        self.assertEqual(validate_trace(base()).state, "DECLARED_APPROVED_TEXT_UNVERIFIED")

    def test_missing_source_resolution_fails_closed(self):
        t = base(); t["events"].remove("SOURCE_RESOLVED")
        self.assertIn("SOURCE_ONLY_RESOLUTION_MISSING", validate_trace(t).blockers)

    def test_missing_rules_fails_closed(self):
        t = base(); t["events"].remove("EXECUTOR_RULES_LOADED")
        self.assertEqual(validate_trace(t).state, "BLOCKED_EDITORIAL")

    def test_missing_critic_cannot_be_replaced_by_external_critic(self):
        t = base(); t["events"].remove("INTERNAL_CRITIC_PASS")
        t["events"].insert(t["events"].index("SIMBA_FINALIZE"), "EXTERNAL_CRITIC_PASS")
        self.assertIn("SIMBA_INTERNAL_CRITIC_OR_FINALIZE_MISSING", validate_trace(t).blockers)

    def test_critic_revise_must_return_to_simba_and_qa(self):
        t = base(); e = t["events"]; e.insert(e.index("INTERNAL_CRITIC_PASS"), "INTERNAL_CRITIC_REVISE")
        self.assertIn("CRITIC_REVISE_WITHOUT_AUTHOR_REPAIR", validate_trace(t).blockers)

    def test_critic_revise_with_real_second_qa_can_pass(self):
        t = base(); e = t["events"]
        e[e.index("INTERNAL_CRITIC_PASS"):e.index("INTERNAL_CRITIC_PASS")] = [
            "INTERNAL_CRITIC_REVISE", "SIMBA_REPAIR", "AUTHOR_QA_PASS"]
        self.assertEqual(validate_trace(t).state, "DECLARED_APPROVED_TEXT_UNVERIFIED")

    def test_critic_no_progress_is_terminal(self):
        t = base(); t["events"].insert(8, "BLOCKED_CRITIC_NO_PROGRESS")
        self.assertEqual(validate_trace(t).state, "BLOCKED_EDITORIAL")

    def test_missing_humanizer_never_ready(self):
        t = base(); t["events"].remove("HUMANIZER_PASS")
        self.assertIn("HUMANIZER_OR_READY_MISSING", validate_trace(t).blockers)

    def test_explicit_leo_approval_digest_must_match_exact_text(self):
        t = base(); t["text"] = "Добавлена новая фраза."
        self.assertIn("APPROVAL_TEXT_HASH_OR_EVIDENCE_MISSING", validate_trace(t).blockers)

    def test_later_text_change_invalidates_old_approval(self):
        t = base(); t["events"].insert(-1, "TEXT_CHANGED")
        self.assertEqual(validate_trace(t).state, "BLOCKED_EDITORIAL")

    def test_approved_text_without_archive_readback_is_not_a_stable_archival_record(self):
        t = base(); t["events"].remove("ARCHIVED_APPROVED")
        self.assertEqual(validate_trace(t).state, "BLOCKED_ARCHIVE")

    def test_no_publish_without_separate_publication_permission(self):
        t = base(); t["publication_requested"] = True
        self.assertIn("PUBLICATION_AUTHORIZATION_MISSING", validate_trace(t).blockers)

    def test_no_publish_without_leo_approval_even_if_editorial_ready(self):
        t = base(); t["events"].remove("LEO_APPROVED")
        t["publication_requested"] = True
        self.assertEqual(validate_trace(t).state, "BLOCKED_PUBLICATION")

    def test_approved_real_vietnam_offer_is_blocked_for_unverified_pdf(self):
        archive = (ARCHIVE / "2026-11-17__SIMBA__VIETNAM-SEASONS-GUIDE__APPROVED.md").read_text(encoding="utf-8-sig")
        self.assertIn("STATUS: APPROVED_TEXT", archive)
        self.assertIn("PDF attachment availability/delivery NOT independently verified", archive)
        self.assertIn("Пришлю вам PDF", archive)
        t = base(text=archive)
        t.update(publication_requested=True, fulfillment_required=True,
                 fulfillment_verified=False,
                 publication_authorization_sha256=digest_text(archive),
                 publication_authorization_evidence="synthetic permission fixture only")
        self.assertIn("BLOCKED_FULFILLMENT_NOT_VERIFIED", validate_trace(t).blockers)

    def test_news_direct_does_not_require_simba_critic_but_needs_humanizer(self):
        t = base(author="News", input_kind="DIRECT_NEWS")
        self.assertNotIn("INTERNAL_CRITIC_PASS", t["events"])
        self.assertEqual(validate_trace(t).state, "DECLARED_APPROVED_TEXT_UNVERIFIED")
        t["events"].remove("HUMANIZER_PASS")
        self.assertEqual(validate_trace(t).state, "BLOCKED_EDITORIAL")

    def test_dynamic_event_cannot_publish_without_freshness_check(self):
        archive = (ARCHIVE / "2026-11-16__NEWS__AYALON-INSTITUTE-HANUKKAH-FAMILY-QUEST__APPROVED.md").read_text(encoding="utf-8-sig")
        self.assertIn("HUMANIZER_PASS зафиксирован", archive)
        self.assertIn("перепроверять перед публикацией", archive)
        t = base(author="News", input_kind="DIRECT_NEWS", text=archive)
        t.update(publication_requested=True, dynamic_facts=True, freshness_verified=False,
                 publication_authorization_sha256=digest_text(archive),
                 publication_authorization_evidence="synthetic permission fixture only")
        self.assertIn("DYNAMIC_FACTS_RECHECK_MISSING", validate_trace(t).blockers)

    def test_publication_permission_is_not_publication_confirmation(self):
        t = base(); t.update(publication_requested=True,
                             publication_authorization_sha256=digest_text(t["text"]),
                             publication_authorization_evidence="synthetic permission fixture only")
        self.assertEqual(validate_trace(t).state, "BLOCKED_PUBLICATION")
        t["events"].append("PUBLICATION_AUTHORIZED")
        self.assertEqual(validate_trace(t).state, "DECLARED_PUBLICATION_AUTHORIZED_UNVERIFIED")
        t["events"].append("PUBLISHED_CONFIRMED")
        self.assertEqual(validate_trace(t).state, "DECLARED_PUBLISHED_UNVERIFIED")

    def test_fourth_variant_needs_own_pass_and_unique_id(self):
        variants = [base(text=f"Вариант {i}.") for i in range(4)]
        for i, v in enumerate(variants): v["id"] = f"v{i+1}"
        self.assertEqual(validate_variant_set(variants, 4).state, "DECLARED_VARIANTS_READY_FOR_LEO")
        variants[3]["events"].remove("INTERNAL_CRITIC_PASS")
        self.assertEqual(validate_variant_set(variants, 4).state, "BLOCKED_EDITORIAL")
        self.assertEqual(validate_variant_set(variants[:3], 4).state, "BLOCKED_EDITORIAL")

    def test_fabricated_approval_evidence_and_fake_published_event_are_never_real_status(self):
        t = base()
        t["publication_requested"] = True
        t["publication_authorization_sha256"] = digest_text(t["text"])
        t["publication_authorization_evidence"] = "I declare publication to have been approved"
        t["events"].extend(["PUBLICATION_AUTHORIZED", "PUBLISHED_CONFIRMED"])
        verdict = validate_trace(t)
        self.assertEqual(verdict.state, "DECLARED_PUBLISHED_UNVERIFIED")
        self.assertNotEqual(verdict.state, "PUBLISHED")

    def test_fabricated_approval_never_authorizes_a_real_post(self):
        t = base()
        t["approval_evidence"] = "synthetic Leo quote with no independent proof"
        self.assertEqual(validate_trace(t).state, "DECLARED_APPROVED_TEXT_UNVERIFIED")
        self.assertNotEqual(validate_trace(t).state, "APPROVED_TEXT")

    def test_live_workflow_is_not_claimed_by_smoke_validation(self):
        s = (ROOT / "integrations/core/editorial_trace.py").read_text(encoding="utf-8-sig")
        self.assertIn("does NOT call agents", s)
        self.assertIn("assertions until backed by independent source evidence", s)


if __name__ == "__main__":
    unittest.main()
