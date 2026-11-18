"""Live, opt-in Simba CORE editor chain. Never publishes or grants Leo approval.

Unlike editorial_trace.py, this module can execute separate real model requests.
Its receipts are call-time provider metadata, not cryptographic attestations:
a later party must independently verify them before treating them as authority.
Offline/fake transports can never produce a production-ready state.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
API_URL = "https://api.openai.com/v1/responses"
MAX_BODY_BYTES = 2_000_000
ROLE_FILES = {
    "Simba": (
        "Симба (Писатель)/Simba-v5.0.md",
        "SIMBA KNOWLEDGE BASE/01_BRAND/STYLE_LEO.md",
        "SIMBA KNOWLEDGE BASE/01_BRAND/ANTI_STYLE.md",
        "SIMBA KNOWLEDGE BASE/05_OPERATIONAL_RULES/FACTS_FRESHNESS_PRICING.md",
        "SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/INTRIGAN.md",
    ),
    "Critic": (
        "Critic/Critic-5.7.md",
        "SIMBA KNOWLEDGE BASE/01_BRAND/STYLE_LEO.md",
        "SIMBA KNOWLEDGE BASE/02_AUDIENCE/SEGMENTS.md",
    ),
    "Humanizer": (
        "Симба (Писатель)/Humanizer-v1.4.md",
        "SIMBA KNOWLEDGE BASE/01_BRAND/STYLE_LEO.md",
        "SIMBA KNOWLEDGE BASE/01_BRAND/ANTI_STYLE.md",
    ),
}
CRITIC_SCHEMA = {
    "type": "json_schema",
    "name": "simba_core_critic_verdict",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["PASS", "REVISE"]},
            "score": {"type": "number"},
            "blocking_issues": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
        },
        "required": ["decision", "score", "blocking_issues", "rationale"],
        "additionalProperties": False,
    },
}


class Blocked(RuntimeError):
    """Fail closed without claiming an executed editorial gate."""


def sha(text):
    return sha256(text.encode("utf-8")).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def rule_context(role):
    if role not in ROLE_FILES:
        raise Blocked("UNKNOWN_ROLE")
    parts = []
    for rel in ROLE_FILES[role]:
        path = ROOT / rel
        if not path.is_file():
            raise Blocked("BLOCKED_KB_UNAVAILABLE:" + rel)
        data = path.read_text(encoding="utf-8-sig")
        if not data.strip():
            raise Blocked("EMPTY_KB:" + rel)
        parts.append("===== " + rel + " =====\n" + data)
    return "\n\n".join(parts)


def response_output(response):
    if response.get("status") != "completed":
        raise Blocked("API_RESPONSE_NOT_COMPLETED")
    texts = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") == "refusal":
                raise Blocked("API_MODEL_REFUSAL")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    result = "\n".join(texts).strip()
    if not result:
        raise Blocked("API_EMPTY_OUTPUT")
    return result


class OpenAIResponsesClient:
    """Fixed-origin HTTPS, non-streaming real Responses API transport."""

    kind = "LIVE_OPENAI_RESPONSES"

    def __init__(self, model, key, output_tokens=2400):
        if not key or not model or not re.fullmatch(r"[a-zA-Z0-9_.-]+", model):
            raise Blocked("OPENAI_KEY_OR_MODEL_MISSING")
        if not 500 <= output_tokens <= 5000:
            raise Blocked("OUTPUT_TOKEN_LIMIT_OUT_OF_RANGE")
        self.model = model
        self._key = key
        self.output_tokens = output_tokens

    def create(self, role, instructions, user_input, schema=None):
        payload = {
            "model": self.model,
            "store": False,
            "max_output_tokens": self.output_tokens,
            "input": [
                {"role": "developer", "content": instructions},
                {"role": "user", "content": user_input},
            ],
        }
        if schema is not None:
            payload["text"] = {"format": schema}
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self._key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            # Explicitly disallow redirects, avoiding forwarding credentials.
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=75) as response:
                raw = response.read(MAX_BODY_BYTES + 1)
                provider_request_id = response.headers.get("x-request-id")
        except urllib.error.HTTPError as exc:
            raise Blocked("OPENAI_HTTP_" + str(exc.code) + "_NO_AUTO_RETRY") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise Blocked("OPENAI_NETWORK_OUTCOME_UNKNOWN_NO_AUTO_RETRY") from None
        if len(raw) > MAX_BODY_BYTES:
            raise Blocked("API_RESPONSE_TOO_LARGE")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise Blocked("API_RESPONSE_INVALID_JSON") from None
        response_id = data.get("id")
        if not isinstance(response_id, str) or not response_id or not provider_request_id:
            raise Blocked("API_PROVIDER_RECEIPT_MISSING")
        return {
            "text": response_output(data),
            "response_id": response_id,
            "request_id": provider_request_id,
            "model": data.get("model"),
            "at": utc_now(),
        }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def checked_critic(payload):
    try:
        result = json.loads(payload)
    except ValueError:
        raise Blocked("CRITIC_NOT_STRUCTURED_JSON") from None
    if not isinstance(result, dict) or set(result) != {"decision", "score", "blocking_issues", "rationale"}:
        raise Blocked("CRITIC_SCHEMA_INVALID")
    score = result["score"]
    issues = result["blocking_issues"]
    if (result["decision"] not in ("PASS", "REVISE") or
            type(score) not in (int, float) or not 0 <= score <= 10 or
            not isinstance(issues, list) or
            any(not isinstance(item, str) or not item.strip() for item in issues)):
        raise Blocked("CRITIC_VERDICT_INVALID")
    if result["decision"] == "PASS" and (score < 8.0 or issues):
        raise Blocked("CRITIC_UNSAFE_PASS")
    if result["decision"] == "REVISE" and not issues:
        raise Blocked("CRITIC_REVISE_WITHOUT_ISSUES")
    return result


class CoreRun:
    """Run-time only provenance. Does not accept caller-supplied event receipts."""

    def __init__(self, client, max_calls=12):
        if not 4 <= max_calls <= 20:
            raise Blocked("MAX_CALLS_OUT_OF_RANGE")
        self.client = client
        self.max_calls = max_calls
        self.run_id = str(uuid4())
        self.receipts = []
        self.rules = {name: rule_context(name) for name in ROLE_FILES}

    def call(self, role, step, text, exact_input_text=None, schema=None):
        if len(self.receipts) >= self.max_calls:
            raise Blocked("MAX_API_CALLS_EXCEEDED")
        instructions = self.rules[role] + (
            "\n\nMANDATORY PILOT RULES: Use only the supplied facts; never invent "
            "rates, approvals, sources or events. This is a one-variant, text-only "
            "private editorial pilot; do NOT publish, request a visual or claim "
            "real-world actions. For Simba/Humanizer, return ONLY the full exact "
            "candidate text without explanation. For Critic, evaluate the exact "
            "candidate against the live Critic rules, return structured JSON; "
            "PASS only when every hard gate passes and score >= 8."
        )
        outcome = self.client.create(role, instructions, text, schema=schema)
        result = outcome["text"]
        receipt = {
            "sequence": len(self.receipts) + 1,
            "role": role,
            "step": step,
            "source_text_sha256": sha(exact_input_text) if exact_input_text is not None else None,
            "request_input_sha256": sha(text),
            "rules_sha256": sha(instructions),
            "output_sha256": sha(result),
            "provider_response_id": outcome["response_id"],
            "provider_request_id": outcome["request_id"],
            "model": outcome["model"],
            "timestamp": outcome["at"],
            "transport": self.client.kind,
        }
        self.receipts.append(receipt)
        return result

    def critic(self, candidate, brief):
        inquiry = (
            "Проверь ТОЛЬКО эту точную редакцию текста. Тема/цель:\n"
            + brief + "\nSHA-256: " + sha(candidate)
            + "\n\n=== ТЕКСТ ДЛЯ ПРОВЕРКИ ===\n" + candidate
        )
        result = self.call("Critic", "independent_critic", inquiry, candidate, CRITIC_SCHEMA)
        return checked_critic(result)

    def execute(self, brief):
        if not isinstance(brief, str) or not brief.strip() or len(brief) > 7000:
            raise Blocked("INVALID_BRIEF")
        candidate = self.call(
            "Simba", "draft", "Составь одну редакцию для проверки.\n" + brief
        )
        last_issues = None
        no_progress = 0
        finalized = False
        for _ in range(self.max_calls):
            verdict = self.critic(candidate, brief)
            if verdict["decision"] == "PASS":
                if not finalized:
                    newer = self.call(
                        "Simba", "finalize", "Заверши авторскую редакцию. "
                        "Верни исходный текст без изменений, если правка не нужна.\n\n" + candidate,
                        candidate,
                    )
                    finalized = True
                    if newer != candidate:
                        candidate = newer  # a changed finalization needs a NEW Critic receipt
                        continue
                break
            issues = tuple(sorted(issue.strip().casefold() for issue in verdict["blocking_issues"]))
            if issues == last_issues:
                no_progress += 1
            else:
                no_progress = 0
            if no_progress >= 3:
                raise Blocked("BLOCKED_CRITIC_NO_PROGRESS")
            last_issues = issues
            candidate = self.call(
                "Simba", "repair", "Исправь ТОЛЬКО замечания независимого Critic.\n"
                + "\n".join(verdict["blocking_issues"])
                + "\n\n=== ТЕКСТ ===\n" + candidate,
                candidate,
            )
            finalized = False
        else:
            raise Blocked("CRITIC_LOOP_BUDGET_EXHAUSTED")

        humanized = self.call(
            "Humanizer", "humanizer", "Сделай только минимальную языковую правку, "
            "не добавляя новых фактов. Сохрани смысл и CTA.\n\n" + candidate,
            candidate,
        )
        if humanized != candidate:
            after = self.critic(humanized, brief)
            if after["decision"] != "PASS":
                raise Blocked("HUMANIZER_CHANGE_REQUIRES_SIMBA_REPAIR")
        state = ("TEXT_READY_FOR_LEO" if self.client.kind == "LIVE_OPENAI_RESPONSES"
                 else "DECLARED_TEST_ONLY")
        return {"state": state, "text": humanized, "text_sha256": sha(humanized)}

    def report(self, status, detail=None):
        return {
            "run_id": self.run_id, "status": status,
            "detail": detail, "mode": self.client.kind,
            "authenticity_note": "Live provider identifiers are not cryptographic attestations; independently verify before downstream authorization.",
            "publication_authorized": False,
            "leo_approval_verified": False,
            "invocation_count": len(self.receipts),
            "receipts": self.receipts,
        }


def _write_private(output_dir, report, text=None):
    dest = Path(output_dir).expanduser().resolve()
    if dest == ROOT or ROOT in dest.parents:
        raise Blocked("OUTPUT_MUST_BE_OUTSIDE_PUBLIC_REPOSITORY")
    dest.mkdir(mode=0o700, parents=True, exist_ok=True)
    report_file = dest / ("simba-core-" + report["run_id"] + ".json")
    with report_file.open("x", encoding="utf-8") as handle:
        os.chmod(report_file, 0o600)
        json.dump(report, handle, ensure_ascii=False, indent=2)
    if text is not None:
        txt = dest / ("simba-core-" + report["run_id"] + ".txt")
        with txt.open("x", encoding="utf-8") as handle:
            os.chmod(txt, 0o600)
            handle.write(text)
    return str(report_file)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief-file", type=Path, required=True)
    parser.add_argument("--output-dir", required=True, help="PRIVATE directory outside the public repository")
    parser.add_argument("--model", help="Explicit billable Responses model identifier")
    parser.add_argument("--max-calls", type=int, default=12)
    parser.add_argument("--max-output-tokens", type=int, default=2400)
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--permit-billable-api-calls", action="store_true")
    args = parser.parse_args(argv)
    try:
        brief = args.brief_file.read_text(encoding="utf-8-sig")
        if not brief.strip() or len(brief) > 7000:
            raise Blocked("INVALID_BRIEF")
        if not args.execute_live or not args.permit_billable_api_calls:
            for role in ROLE_FILES:
                rule_context(role)
            print(json.dumps({
                "status": "BLOCKED_LIVE_EXECUTOR_NOT_RUN",
                "reason": "Explicit --execute-live AND --permit-billable-api-calls required",
                "publication_authorized": False,
            }, ensure_ascii=False))
            return 0
        client = OpenAIResponsesClient(
            args.model, os.environ.get("OPENAI_API_KEY"), args.max_output_tokens
        )
        run = CoreRun(client, args.max_calls)
        result = None
        try:
            result = run.execute(brief)
            report = run.report(result["state"], {"text_sha256": result["text_sha256"]})
        except Blocked as exc:
            report = run.report("BLOCKED_EDITORIAL", str(exc))
        saved = _write_private(args.output_dir, report, result["text"] if result else None)
        print(json.dumps({"status": report["status"], "report_path": saved, "calls": len(run.receipts)}, ensure_ascii=False))
        return 0 if result and result["state"] == "TEXT_READY_FOR_LEO" else 1
    except (Blocked, OSError, UnicodeError) as exc:
        print(json.dumps({"status": "BLOCKED_RUNTIME_INTEGRATION", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
