"""Real, non-generative repository readback for an EXISTING Simba post.

This loads actual KB files from the checked-out repository and audits the
existing archive's *declared* provenance. No agent, API or paid task is run.
No critic PASS, Leo approval, delivery or publication is invented.
"""
import argparse
import json
import re
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "SIMBA KNOWLEDGE BASE"
LIB = KB / "03_CONTENT_LIBRARY"
VIETNAM_CASE = LIB / "2026-11-17__SIMBA__VIETNAM-SEASONS-GUIDE__APPROVED.md"

REQUIRED_CORE_FILES = (
    "AGENTS.md",
    "ROUTER_v10.1.md",
    "META-Governance-v8.1.md",
    "Симба (Писатель)/Simba-v5.0.md",
    "Critic/Critic-5.7.md",
    "Симба (Писатель)/Humanizer-v1.4.md",
    "SIMBA KNOWLEDGE BASE/00_CORE/KNOWLEDGE_MAP.md",
    "SIMBA KNOWLEDGE BASE/00_CORE/KB_RUNTIME_PROTOCOL.md",
    "SIMBA KNOWLEDGE BASE/01_BRAND/STYLE_LEO.md",
    "SIMBA KNOWLEDGE BASE/01_BRAND/ANTI_STYLE.md",
    "SIMBA KNOWLEDGE BASE/01_BRAND/BRAND_RULES.md",
    "SIMBA KNOWLEDGE BASE/02_AUDIENCE/SEGMENTS.md",
    "SIMBA KNOWLEDGE BASE/02_AUDIENCE/OBJECTIONS_AND_LANGUAGE.md",
    "SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/_INDEX.md",
    "SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/_PATTERN_TRACKER.md",
    "SIMBA KNOWLEDGE BASE/04_BUSINESS/COMPANY_AND_PRODUCTS.md",
    "SIMBA KNOWLEDGE BASE/05_OPERATIONAL_RULES/FACTS_FRESHNESS_PRICING.md",
    "SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/CONTENT_PIPELINE.md",
    "SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/INTRIGAN.md",
    "SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/COPYWRITER_TEST.md",
    "SIMBA KNOWLEDGE BASE/07_LEARNINGS/PATTERN_WATCH.md",
)


def fingerprint(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def audit_existing_archive(path: Path = VIETNAM_CASE) -> dict:
    """Audit only verified repository file facts, NEVER infer role execution."""
    paths = [ROOT / name for name in REQUIRED_CORE_FILES]
    missing = [name for name, item in zip(REQUIRED_CORE_FILES, paths)
               if not item.is_file() or item.stat().st_size == 0]
    if missing:
        return {"outcome": "BLOCKED_KB_UNAVAILABLE", "missing_kb": missing}
    if not path.is_file():
        return {"outcome": "SOURCE_BLOCKED", "missing_archive": str(path)}
    raw = path.read_text(encoding="utf-8-sig")
    header, sep, body = raw.partition("\n---\n")
    if not sep:
        return {"outcome": "SOURCE_BLOCKED", "reason": "NO_ARCHIVE_BODY_DELIMITER"}

    index = (LIB / "_INDEX.md").read_text(encoding="utf-8-sig")
    declared_approved = bool(re.search(r"\bSTATUS:\s*APPROVED_TEXT\b", header))
    mention = path.name in index
    # Existing natural-language approval metadata is not an authenticated
    # event or proof of an independently executed agent quality review.
    approval_reported = "APPROVAL_EVIDENCE:" in header
    critic_receipt_recorded = "INTERNAL_CRITIC_PASS" in header
    humanizer_receipt_recorded = "HUMANIZER_PASS" in header
    pdf_promised = bool(re.search(r"\b(?:PDF|ПДФ)\b", body))
    pdf_unverified = ("PDF attachment availability/delivery NOT independently verified"
                      in header)
    explicitly_unpublished = bool(re.search(r"\bPUBLISHED:\s*NO\b", header))

    blockers = ["EXECUTOR_NOT_INVOKED_IN_THIS_READ_ONLY_RUN",
                "INTERNAL_CRITIC_NOT_INVOKED_IN_THIS_READ_ONLY_RUN",
                "HUMANIZER_NOT_INVOKED_IN_THIS_READ_ONLY_RUN",
                "LEO_APPROVAL_NOT_AUTHENTICATED_BY_THIS_RUN"]
    if pdf_promised and pdf_unverified:
        blockers.append("BLOCKED_FULFILLMENT_NOT_VERIFIED")
    blockers.append("PUBLICATION_AUTHORIZATION_NOT_VERIFIED")

    return {
        "mode": "EXISTING_ARCHIVE_READ_ONLY_PREFLIGHT",
        "outcome": "BLOCKED_LIVE_EXECUTOR_NOT_RUN",
        "source": str(path.relative_to(ROOT)),
        "source_sha256": fingerprint(path),
        "actual_kb_docs_read": len(paths),
        "kb_content_sha256": {str(item.relative_to(ROOT)): fingerprint(item)
                              for item in paths},
        "indexed": mention,
        "archived_approval_status": "DECLARED_APPROVED_TEXT" if declared_approved
                                    else "NO_APPROVED_TEXT_RECORD",
        "leo_approval_note_recorded": approval_reported,
        "leo_approval_independently_verified": False,
        "critic_receipt_recorded_in_archive_header": critic_receipt_recorded,
        "humanizer_receipt_recorded_in_archive_header": humanizer_receipt_recorded,
        "role_execution_observed_this_run": False,
        "pdf_fulfillment_verified": False if pdf_unverified else None,
        "archive_explicitly_unpublished": explicitly_unpublished,
        "publication_confirmation_observed": False,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", type=Path, default=VIETNAM_CASE,
                        help="existing approved archive in checkout; read only")
    args = parser.parse_args()
    report = audit_existing_archive(args.post.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # This read-only diagnostic succeeds when it faithfully reports a blocker.
    # CI must not equate exit code 0 with actual author/pass/publication.
    return 1 if report["outcome"] in {"BLOCKED_KB_UNAVAILABLE", "SOURCE_BLOCKED"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
