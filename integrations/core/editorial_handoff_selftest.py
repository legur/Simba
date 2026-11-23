"""Deterministic, free contract smoke test for Simba CORE editorial handoffs.

NO LLMs ARE CALLED. Fixed fixture outputs exercise only the real production
state machine: Simba -> Critic -> Simba repair -> Critic -> Simba finalize ->
Humanizer -> Critic. A passing result is NEVER editorial approval or evidence
of autonomous ChatGPT agents, provider calls, fact-checking or publication.
"""
import json

from editorial_live_runner import Blocked, CoreRun, sha


BRIEF = (
    "Исключительно синтетический редакционный тест: одна короткая публикация "
    "о вымышленном музее в несуществующем городе. Не указывать настоящие "
    "даты, цены, бронирования, контакты, источники или клиентские данные."
)
DRAFT = "Музей открылся. Приходи завтра."
REPAIRED = (
    "ТЕСТОВЫЙ МАРШРУТ. В вымышленном городе есть вымышленный музей. "
    "Это технический пример, а не туристическое предложение."
)
HUMANIZED = (
    "ТЕСТОВЫЙ МАРШРУТ. В воображаемом городе находится вымышленный музей. "
    "Это технический пример, не предложение к бронированию."
)


def _critic(decision, score, issues):
    return json.dumps({
        "decision": decision, "score": score,
        "blocking_issues": issues,
        "rationale": "Фиксированный тестовый результат, не независимый Critic.",
    }, ensure_ascii=False)


class OfflineFixture:
    # Spoofed to ensure only the actual transport TYPE may be labeled live.
    kind = "LIVE_OPENAI_RESPONSES"

    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = []

    def create(self, role, instructions, user_input, schema=None):
        if not self.turns:
            raise RuntimeError("OFFLINE_FIXTURE_EXHAUSTED")
        expected_role, output = self.turns.pop(0)
        if role != expected_role:
            raise RuntimeError("ROLE_HANDOFF_MISMATCH")
        if bool(schema) != (role == "Critic"):
            raise RuntimeError("CRITIC_SCHEMA_HANDOFF_MISMATCH")
        self.calls.append({
            "role": role, "user_input": user_input,
            "rule_context_loaded": bool(instructions and "=====" in instructions),
            "has_critic_schema": bool(schema),
        })
        idx = len(self.calls)
        return {
            "text": output,
            "response_id": "OFFLINE_RESPONSE_" + str(idx),
            "request_id": "OFFLINE_REQUEST_" + str(idx),
            "model": "OFFLINE_FIXTURE_NEVER_PROVIDER",
            "at": "2000-01-01T00:00:00+00:00",
        }


def _assert(condition, code):
    if not condition:
        raise RuntimeError("OFFLINE_SELFTEST_" + code)


def run_offline_handoff_selftest():
    """Exercise both a successful *fake* revision chain and hard blockers."""
    pass_verdict = _critic("PASS", 9.0, [])
    revise = _critic("REVISE", 6.5, ["Не сказано, что событие вымышленное"])
    turns = [
        ("Simba", DRAFT),
        ("Critic", revise),
        ("Simba", REPAIRED),
        ("Critic", pass_verdict),
        ("Simba", REPAIRED),
        ("Humanizer", HUMANIZED),
        ("Critic", pass_verdict),
    ]
    fixture = OfflineFixture(turns)
    runner = CoreRun(fixture, max_calls=9)
    final = runner.execute(BRIEF)
    report = runner.report(final["state"], {"text_sha256": final["text_sha256"]})
    expected_steps = [
        "draft", "independent_critic", "repair", "independent_critic",
        "finalize", "humanizer", "independent_critic",
    ]
    actual_steps = [entry["step"] for entry in runner.receipts]
    _assert(actual_steps == expected_steps, "WRONG_STEP_ORDER")
    _assert(not fixture.turns and len(fixture.calls) == 7, "CALL_COUNT_WRONG")
    _assert(all(c["rule_context_loaded"] for c in fixture.calls), "ROLE_RULES_ABSENT")

    revision_by_step = [
        None, DRAFT, DRAFT, REPAIRED, REPAIRED, REPAIRED, HUMANIZED
    ]
    for receipt, upstream in zip(runner.receipts, revision_by_step):
        _assert(receipt["source_text_sha256"] ==
                (sha(upstream) if upstream is not None else None), "REVISION_HASH_MISMATCH")
        _assert(receipt["transport"] == "UNTRUSTED_TEST_TRANSPORT",
                "FAKE_TRANSPORT_ESCALATED")
    for idx, exact in ((1, DRAFT), (3, REPAIRED), (6, HUMANIZED)):
        call = fixture.calls[idx]
        _assert(call["role"] == "Critic" and call["has_critic_schema"], "CRITIC_NOT_INDEPENDENT_STEP")
        _assert(sha(exact) in call["user_input"] and exact in call["user_input"],
                "CRITIC_NOT_EXACT_REVISION")
    _assert(final["text"] == HUMANIZED and final["text_sha256"] == sha(HUMANIZED),
            "FINAL_NOT_EXACT")
    _assert(final["state"] == "DECLARED_TEST_ONLY", "LIVE_STATE_SPOOFED")
    _assert(report["mode"] == "UNTRUSTED_TEST_TRANSPORT", "PROVIDER_SPOOFED")
    _assert(report["ready_for_production"] is False and
            report["publication_authorized"] is False and
            report["leo_approval_verified"] is False, "AUTHORITY_ESCALATION")

    bad_humanizer = OfflineFixture([
        ("Simba", DRAFT),
        ("Critic", pass_verdict),
        ("Simba", DRAFT),
        ("Humanizer", HUMANIZED),
        ("Critic", _critic("REVISE", 7.0, ["Добавлен неподтвержденный факт"])),
    ])
    try:
        CoreRun(bad_humanizer, max_calls=9).execute(BRIEF)
    except Blocked as exc:
        _assert(str(exc) == "HUMANIZER_CHANGE_REQUIRES_SIMBA_REPAIR",
                "HUMANIZER_REVISE_WRONG_BLOCKER")
    else:
        raise RuntimeError("OFFLINE_SELFTEST_UNREVIEWED_HUMANIZER_PASSED")

    no_change = OfflineFixture([
        ("Simba", DRAFT),
        ("Critic", revise),
        ("Simba", DRAFT),
    ])
    try:
        CoreRun(no_change, max_calls=9).execute(BRIEF)
    except Blocked as exc:
        _assert(str(exc) == "SIMBA_REPAIR_NO_TEXT_CHANGE",
                "UNMODIFIED_REPAIR_WRONG_BLOCKER")
    else:
        raise RuntimeError("OFFLINE_SELFTEST_NO_CHANGE_REPAIR_PASSED")

    return {
        "status": "OFFLINE_HANDOFF_CONTRACT_OK_NOT_AGENT_EXECUTION",
        "scenario": "SYNTHETIC_EDITORIAL_FIXTURE_ONLY",
        "roles_in_order": [call["role"] for call in fixture.calls],
        "steps": actual_steps,
        "receipts_checked": len(runner.receipts),
        "final_sha256": final["text_sha256"],
        "revision_binding_verified": True,
        "critic_after_humanizer_verified": True,
        "humanizer_revise_blocks_verified": True,
        "unchanged_simba_repair_blocks_verified": True,
        "tests_real_role_orchestration": False,
        "live_calls_made": False,
        "provider_receipts_authentic": False,
        "source_resolution_verified": False,
        "dynamic_fact_check_verified": False,
        "tia_execution_verified": False,
        "leo_approval_verified": False,
        "publication_authorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_offline_handoff_selftest(), ensure_ascii=False))
