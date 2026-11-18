"""Offline integrity audit of PRIVATE Simba editorial pilot receipts.

Checks structure, exact-text hashes and editorial ordering. Provider IDs and role
labels in a JSON file can be forged; this code NEVER authenticates OpenAI calls,
the human author, facts, approvals or publication.
"""
import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

HASH = re.compile(r"[a-f0-9]{64}\\Z")
STEPS = {
    "draft": "Simba",
    "repair": "Simba",
    "finalize": "Simba",
    "independent_critic": "Critic",
    "humanizer": "Humanizer",
}


class IntegrityBlocked(ValueError):
    pass


def digest(content):
    return sha256(content.encode("utf-8")).hexdigest()


def _valid_sha(value):
    return isinstance(value, str) and bool(HASH.fullmatch(value))


def _critic_check(verdict):
    if not isinstance(verdict, dict) or set(verdict) != {"decision", "score", "blocking_issues"}:
        raise IntegrityBlocked("CRITIC_VERDICT_MISSING")
    issues = verdict["blocking_issues"]
    score = verdict["score"]
    if (verdict["decision"] not in ("PASS", "REVISE") or
        type(score) not in (float, int) or not 0 <= score <= 10 or
        not isinstance(issues, list) or
        any(not isinstance(s, str) or not s.strip() for s in issues)):
        raise IntegrityBlocked("CRITIC_VERDICT_INVALID")
    if verdict["decision"] == "PASS" and (score < 8 or issues):
        raise IntegrityBlocked("CRITIC_INVALID_PASS")
    if verdict["decision"] == "REVISE" and not issues:
        raise IntegrityBlocked("CRITIC_REVISE_WITHOUT_ISSUES")
    return verdict["decision"]


def audit_receipts(report, final_text):
    """Return ONLY DECLARED consistency, never a trusted execution PASS."""
    if not isinstance(report, dict) or not isinstance(final_text, str):
        raise IntegrityBlocked("INPUT_FORMAT_INVALID")
    if report.get("status") != "LIVE_EDITORIAL_PILOT_UNVERIFIED":
        raise IntegrityBlocked("NO_LIVE_PILOT_STATUS")
    if report.get("mode") != "LIVE_OPENAI_RESPONSES":
        raise IntegrityBlocked("NOT_LIVE_MODE")
    if (report.get("publication_authorized") is not False or
        report.get("leo_approval_verified") is not False or
        report.get("ready_for_production") is not False):
        raise IntegrityBlocked("AUTHORITY_ESCALATION")
    if not _valid_sha(report.get("brief_sha256")):
        raise IntegrityBlocked("BRIEF_SHA_MISSING")
    detail = report.get("detail")
    if not isinstance(detail, dict) or detail.get("text_sha256") != digest(final_text):
        raise IntegrityBlocked("FINAL_TEXT_DIGEST_MISMATCH")
    receipts = report.get("receipts")
    if (not isinstance(receipts, list) or len(receipts) < 4 or
        report.get("invocation_count") != len(receipts)):
        raise IntegrityBlocked("MISSING_OR_INCOMPLETE_RECEIPTS")

    ids = set()
    state, candidate, recheck_origin = "draft", None, None
    for idx, entry in enumerate(receipts, 1):
        if not isinstance(entry, dict) or entry.get("sequence") != idx:
            raise IntegrityBlocked("RECEIPT_ORDER_INVALID")
        step = entry.get("step")
        if entry.get("role") != STEPS.get(step):
            raise IntegrityBlocked("ROLE_STEP_CONFLICT")
        if entry.get("transport") != "LIVE_OPENAI_RESPONSES":
            raise IntegrityBlocked("TRANSPORT_CLAIM_MISMATCH")
        for key in ("request_input_sha256", "rules_sha256", "output_sha256"):
            if not _valid_sha(entry.get(key)):
                raise IntegrityBlocked("INVALID_HASH:" + key)
        provider_id = entry.get("provider_response_id")
        request_id = entry.get("provider_request_id")
        if not isinstance(provider_id, str) or not provider_id.strip() or not isinstance(request_id, str) or not request_id.strip():
            raise IntegrityBlocked("MISSING_PROVIDER_IDS")
        if provider_id in ids or request_id in ids:
            raise IntegrityBlocked("DUPLICATE_PROVIDER_IDS")
        ids.update((provider_id, request_id))
        if not isinstance(entry.get("model"), str) or not entry["model"]:
            raise IntegrityBlocked("MODEL_NOT_RECORDED")
        try:
            dt = datetime.fromisoformat(entry["timestamp"])
            if dt.tzinfo is None:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise IntegrityBlocked("TIMESTAMP_INVALID") from None

        source = entry.get("source_text_sha256")
        if state == "draft":
            if step != "draft" or source is not None:
                raise IntegrityBlocked("DRAFT_START_INVALID")
            candidate = entry["output_sha256"]
            state = "critic"
            continue
        if state == "critic":
            if step != "independent_critic" or source != candidate:
                raise IntegrityBlocked("CRITIC_WRONG_REVISION")
            decision = _critic_check(entry.get("critic_verdict"))
            if recheck_origin == "humanizer":
                if decision != "PASS":
                    raise IntegrityBlocked("HUMANIZER_CHANGE_NOT_PASSED")
                state = "done"
            elif recheck_origin == "finalize":
                state = "humanizer" if decision == "PASS" else "repair"
                recheck_origin = None
            else:
                state = "finalize" if decision == "PASS" else "repair"
            continue
        if "critic_verdict" in entry:
            raise IntegrityBlocked("VERDICT_ON_NON_CRITIC")
        if source != candidate:
            raise IntegrityBlocked("HANDOFF_HASH_MISMATCH")
        if state == "repair":
            if step != "repair":
                raise IntegrityBlocked("EXPECTED_SIMBA_REPAIR")
            if entry["output_sha256"] == candidate:
                raise IntegrityBlocked("REPAIR_NOT_CHANGED")
            candidate = entry["output_sha256"]
            state = "critic"
            recheck_origin = None
        elif state == "finalize":
            if step != "finalize":
                raise IntegrityBlocked("EXPECTED_SIMBA_FINALIZE")
            changed = entry["output_sha256"] != candidate
            candidate = entry["output_sha256"]
            state = "critic" if changed else "humanizer"
            recheck_origin = "finalize" if changed else None
        elif state == "humanizer":
            if step != "humanizer":
                raise IntegrityBlocked("EXPECTED_HUMANIZER")
            changed = entry["output_sha256"] != candidate
            candidate = entry["output_sha256"]
            state = "critic" if changed else "done"
            recheck_origin = "humanizer" if changed else None
        else:
            raise IntegrityBlocked("EXTRA_CALL_AFTER_FINAL")
    if state != "done":
        raise IntegrityBlocked("EDITORIAL_SEQUENCE_INCOMPLETE")
    if candidate != digest(final_text):
        raise IntegrityBlocked("FINAL_HANDOFF_HASH_MISMATCH")
    return {
        "status": "DECLARED_RECEIPTS_CONSISTENT_AUTHENTICITY_UNVERIFIED",
        "receipts_checked": len(receipts),
        "text_sha256": candidate,
        "publication_authorized": False,
        "leo_approval_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8-sig"))
        final_text = args.text.read_text(encoding="utf-8")
        print(json.dumps(audit_receipts(report, final_text), ensure_ascii=False))
        return 0
    except (IntegrityBlocked, OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"status": "BLOCKED_RECEIPT_INTEGRITY",
                          "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
