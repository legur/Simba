"""Offline verification of declared Simba editorial gate traces.

This does NOT call agents, re-run their creative judgement, authenticate Leo's
approval, confirm external facts, prove a file exists, or publish anything.
Trace events are assertions until backed by independent source evidence.
"""
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

AUTHORS = frozenset({"Simba", "News", "Info", "Travel", "Leo"})


@dataclass(frozen=True)
class Verdict:
    state: str
    blockers: tuple[str, ...] = ()


def digest_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _index_after(events: list[str], name: str, after: int) -> int:
    try:
        return events.index(name, after + 1)
    except ValueError:
        return -1


def validate_trace(trace: Mapping[str, Any]) -> Verdict:
    """Conservative state for a single exact-text candidate's declared trace.

    Missing, unordered, or stale gates block advancement. This is a declared
    trace consistency check, NOT external verification of the execution.
    """
    author = trace.get("author")
    if author not in AUTHORS:
        return Verdict("BLOCKED_EDITORIAL", ("UNKNOWN_AUTHOR",))
    exact_text = trace.get("text")
    if not isinstance(exact_text, str) or not exact_text.strip():
        return Verdict("BLOCKED_EDITORIAL", ("EMPTY_EXACT_TEXT",))
    events = trace.get("events", [])
    if not isinstance(events, list) or not all(isinstance(v, str) for v in events):
        return Verdict("BLOCKED_EDITORIAL", ("INVALID_EVENT_TRACE",))
    if "BLOCKED_CRITIC_NO_PROGRESS" in events:
        return Verdict("BLOCKED_EDITORIAL", ("BLOCKED_CRITIC_NO_PROGRESS",))
    if "BLOCKED_FACTS" in events or "BLOCKED_KB_UNAVAILABLE" in events:
        return Verdict("BLOCKED_EDITORIAL", ("SOURCE_OR_FACTS_BLOCKED",))

    # Text changes revoke all prior author/Critic/Humanizer/approval evidence.
    change = max((i for i, v in enumerate(events) if v == "TEXT_CHANGED"), default=-1)
    if trace.get("input_kind") == "SOURCE_ONLY":
        source = _index_after(events, "SOURCE_RESOLVED", -1)
        route = _index_after(events, "ROUTER_TASK_CLASSIFIED", source)
        if source < 0 or route < 0 or source >= route:
            return Verdict("BLOCKED_EDITORIAL", ("SOURCE_ONLY_RESOLUTION_MISSING",))

    previous = change
    for group in (
        ("EXECUTOR_RULES_LOADED",),
        ("FACTS_VERIFIED",),
        ("INTRIGAN_CHECKED", "INTRIGAN_SKIPPED"),
        ("TIA_CHECKED", "TIA_UNAVAILABLE_REPORTED"),
        ("AUTHOR_DRAFTED",),
        ("AUTHOR_QA_PASS",),
    ):
        candidates = [(events.index(event, previous + 1), event)
                      for event in group if event in events[previous + 1:]]
        if not candidates:
            return Verdict("BLOCKED_EDITORIAL", ("AUTHOR_PREFLIGHT_OR_QA_MISSING",))
        previous = min(candidates)[0]

    if author == "Simba":
        # REVISE is not permission to turn into PASS without Simba repair.
        for i, event in enumerate(events):
            if event == "INTERNAL_CRITIC_REVISE" and i > previous:
                repaired = _index_after(events, "SIMBA_REPAIR", i)
                rechecked = _index_after(events, "AUTHOR_QA_PASS", repaired)
                if repaired < 0 or rechecked < 0 or not (i < repaired < rechecked):
                    return Verdict("BLOCKED_EDITORIAL", ("CRITIC_REVISE_WITHOUT_AUTHOR_REPAIR",))
                previous = rechecked
        critic = _index_after(events, "INTERNAL_CRITIC_PASS", previous)
        final = _index_after(events, "SIMBA_FINALIZE", critic)
        if critic < 0 or final < 0 or critic >= final:
            return Verdict("BLOCKED_EDITORIAL", ("SIMBA_INTERNAL_CRITIC_OR_FINALIZE_MISSING",))
        previous = final
    else:
        final = _index_after(events, "AUTHOR_FINALIZE", previous)
        if final < 0:
            return Verdict("BLOCKED_EDITORIAL", ("AUTHOR_FINALIZE_MISSING",))
        previous = final

    humanizer = _index_after(events, "HUMANIZER_PASS", previous)
    ready = _index_after(events, "TEXT_READY_FOR_LEO", humanizer)
    if humanizer < 0 or ready < 0 or humanizer >= ready:
        return Verdict("BLOCKED_EDITORIAL", ("HUMANIZER_OR_READY_MISSING",))

    expected = digest_text(exact_text)
    approved = _index_after(events, "LEO_APPROVED", ready)
    if approved < 0:
        if trace.get("publication_requested"):
            return Verdict("BLOCKED_PUBLICATION", ("LEO_TEXT_APPROVAL_MISSING",))
        return Verdict("TEXT_READY_FOR_LEO")
    if trace.get("approval_sha256") != expected or not trace.get("approval_evidence"):
        return Verdict("BLOCKED_EDITORIAL", ("APPROVAL_TEXT_HASH_OR_EVIDENCE_MISSING",))

    archived = _index_after(events, "ARCHIVED_APPROVED", approved)
    if archived < 0 or trace.get("archive_sha256") != expected:
        return Verdict("BLOCKED_ARCHIVE", ("APPROVED_ARCHIVE_READBACK_MISSING",))
    if not trace.get("publication_requested", False):
        return Verdict("APPROVED_TEXT")

    blockers = []
    if trace.get("publication_authorization_sha256") != expected or not trace.get("publication_authorization_evidence"):
        blockers.append("PUBLICATION_AUTHORIZATION_MISSING")
    if trace.get("fulfillment_required") and not trace.get("fulfillment_verified"):
        blockers.append("BLOCKED_FULFILLMENT_NOT_VERIFIED")
    if trace.get("dynamic_facts") and not trace.get("freshness_verified"):
        blockers.append("DYNAMIC_FACTS_RECHECK_MISSING")
    if blockers:
        return Verdict("BLOCKED_PUBLICATION", tuple(blockers))
    authorized = _index_after(events, "PUBLICATION_AUTHORIZED", archived)
    if authorized < 0:
        return Verdict("BLOCKED_PUBLICATION", ("PUBLICATION_AUTHORIZED_EVENT_MISSING",))
    confirmed = _index_after(events, "PUBLISHED_CONFIRMED", authorized)
    if confirmed < 0:
        return Verdict("PUBLICATION_AUTHORIZED_NOT_CONFIRMED")
    return Verdict("PUBLISHED")


def validate_variant_set(variants: list[Mapping[str, Any]], expected_count: int) -> Verdict:
    """A passed candidate does not lend a pass to another candidate."""
    if expected_count < 1 or len(variants) != expected_count:
        return Verdict("BLOCKED_EDITORIAL", ("VARIANT_COUNT_MISMATCH",))
    if len({v.get("id") for v in variants}) != len(variants):
        return Verdict("BLOCKED_EDITORIAL", ("DUPLICATE_VARIANT_IDS",))
    outcomes = [validate_trace(v) for v in variants]
    bad = [(v.get("id"), result.state, result.blockers)
           for v, result in zip(variants, outcomes)
           if result.state not in {"TEXT_READY_FOR_LEO", "APPROVED_TEXT"}]
    if bad:
        return Verdict("BLOCKED_EDITORIAL",
                       tuple(f"{name}: {state}: {blockers}" for name, state, blockers in bad))
    return Verdict("VARIANTS_READY_FOR_LEO")
