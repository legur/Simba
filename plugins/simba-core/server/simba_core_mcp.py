"""Minimal stdlib MCP stdio bridge for Simba CORE editorial private pilot.

Desktop-only. No API credentials, calls, or publication by default.
It runs the repository's existing audited opt-in executor, never impersonates
ChatGPT sub-agents, and never converts a pilot into a production approval.
"""
import json
import os
from pathlib import Path
import re
import sys
import uuid

PROTOCOL = "2025-06-18"
VERSION = "0.1.0"
MAX_INPUT_BYTES = 200_000
MAX_BRIEF = 7000
SAFE_RUN_ID = re.compile(r"^[0-9a-fA-F-]{36}$")

TOOLS = [
    {
        "name": "simba_core_preflight",
        "description": "Read-only check of Simba CORE repository and local pilot configuration. Never calls model APIs.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"title": "Simba CORE preflight", "readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "simba_core_run_private_pilot",
        "description": (
            "Runs independent, billable API requests for one private test text, "
            "only with explicit invocation flags AND locally configured "
            "SIMBA_CORE_ALLOW_BILLABLE=1 and OPENAI_API_KEY. "
            "DO NOT invoke before user explicitly authorizes API spending. "
            "Returns only LIVE_EDITORIAL_PILOT_UNVERIFIED or a block; "
            "never approves text, publishes, or claims ChatGPT agent execution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "brief": {"type": "string", "minLength": 1, "maxLength": MAX_BRIEF},
                "model": {"type": "string"},
                "execute_live": {"type": "boolean"},
                "permit_billable_api_calls": {"type": "boolean"},
                "max_calls": {"type": "integer", "minimum": 4, "maximum": 12},
                "max_output_tokens": {"type": "integer", "minimum": 500, "maximum": 2400},
            },
            "required": ["brief", "model", "execute_live", "permit_billable_api_calls"],
            "additionalProperties": False,
        },
        "annotations": {"title": "Simba private paid pilot", "readOnlyHint": False,
                        "openWorldHint": True, "destructiveHint": False},
    },
    {
        "name": "simba_core_audit_pilot_receipts",
        "description": (
            "Offline SHA-256 and sequence consistency audit for a private "
            "pilot by run_id, never verifies provider authenticity or owner approval."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "string"}},
            "required": ["run_id"],
            "additionalProperties": False,
        },
        "annotations": {"title": "Audit pilot receipt integrity",
                        "readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "simba_core_read_pilot_text",
        "description": "Read final text from a private local pilot by run_id. No publication or approval.",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "string"}},
            "required": ["run_id"],
            "additionalProperties": False,
        },
        "annotations": {"title": "Read private pilot draft",
                        "readOnlyHint": True, "openWorldHint": False},
    },
]


class BridgeBlocked(Exception):
    pass


def repo_root():
    value = os.environ.get("SIMBA_CORE_REPO_ROOT", "")
    if not value or not Path(value).is_absolute():
        raise BridgeBlocked("SIMBA_CORE_REPO_ROOT_NOT_CONFIGURED")
    root = Path(value).expanduser().resolve()
    required = root / "integrations/core/editorial_live_runner.py"
    if not required.is_file():
        raise BridgeBlocked("SIMBA_CORE_REPO_INVALID")
    return root


def private_dir():
    value = os.environ.get("SIMBA_CORE_PRIVATE_DIR", "")
    if not value or not Path(value).is_absolute():
        raise BridgeBlocked("SIMBA_CORE_PRIVATE_DIR_NOT_CONFIGURED")
    dest = Path(value).expanduser().resolve()
    root = repo_root()
    if dest == root or root in dest.parents:
        raise BridgeBlocked("PRIVATE_DIR_WITHIN_PUBLIC_REPOSITORY")
    if not dest.is_dir():
        raise BridgeBlocked("PRIVATE_DIR_MUST_EXIST")
    if os.name == "nt":
        if os.environ.get("SIMBA_CORE_WINDOWS_PRIVATE_ACL_VERIFIED") != "1":
            raise BridgeBlocked("WINDOWS_PRIVATE_ACL_NOT_CONFIRMED")
    elif dest.stat().st_mode & 0o077:
        raise BridgeBlocked("PRIVATE_DIR_PERMISSIONS_UNSAFE")
    return dest


def load_core():
    root = repo_root()
    core = str(root / "integrations/core")
    if core not in sys.path:
        sys.path.insert(0, core)
    import editorial_live_runner as live
    import editorial_receipts_audit as audit
    # Ensure no stale, unrelated core modules already imported in process.
    if Path(live.__file__).resolve() != Path(core, "editorial_live_runner.py").resolve():
        raise BridgeBlocked("SIMBA_MODULE_PATH_MISMATCH")
    return live, audit


def preflight():
    report = {
        "status": "BLOCKED_LIVE_EXECUTOR_NOT_RUN",
        "surface": "CHATGPT_DESKTOP_LOCAL_MCP_NOT_CLOUD",
        "live_calls_made": False,
        "publication_authorized": False,
    }
    blockers = []
    try:
        live, _ = load_core()
        for role in live.ROLE_FILES:
            live.rule_context(role)
    except Exception as exc:
        blockers.append("CORE_RULES_UNAVAILABLE:" + type(exc).__name__)
    try:
        private_dir()
    except BridgeBlocked as exc:
        blockers.append(str(exc))
    if not os.getenv("OPENAI_API_KEY"):
        blockers.append("OPENAI_API_KEY_NOT_CONFIGURED")
    if os.getenv("SIMBA_CORE_ALLOW_BILLABLE") != "1":
        blockers.append("BILLABLE_OPERATOR_GATE_DISABLED")
    report["preflight_blockers"] = blockers
    report["local_pilot_configured"] = not blockers
    return report


def run_private_pilot(args):
    # Check three independent operator gates before even importing runtime.
    if args.get("execute_live") is not True:
        raise BridgeBlocked("EXPLICIT_LIVE_FLAG_REQUIRED")
    if args.get("permit_billable_api_calls") is not True:
        raise BridgeBlocked("EXPLICIT_BILLABLE_FLAG_REQUIRED")
    if os.getenv("SIMBA_CORE_ALLOW_BILLABLE") != "1":
        raise BridgeBlocked("LOCAL_BILLABLE_GATE_DISABLED")
    if not os.getenv("OPENAI_API_KEY"):
        raise BridgeBlocked("OPENAI_API_KEY_NOT_CONFIGURED")

    brief = args.get("brief")
    model = args.get("model")
    max_calls = args.get("max_calls", 8)
    output_tokens = args.get("max_output_tokens", 1600)
    if not isinstance(brief, str) or not brief.strip() or len(brief) > MAX_BRIEF:
        raise BridgeBlocked("INVALID_BRIEF")
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", model):
        raise BridgeBlocked("INVALID_MODEL")
    if type(max_calls) is not int or not 4 <= max_calls <= 12:
        raise BridgeBlocked("INVALID_MAX_CALLS")
    if type(output_tokens) is not int or not 500 <= output_tokens <= 2400:
        raise BridgeBlocked("INVALID_MAX_OUTPUT_TOKENS")

    destination = private_dir()
    live, _ = load_core()
    client = live.OpenAIResponsesClient(model, os.environ.get("OPENAI_API_KEY"), output_tokens)
    run = live.CoreRun(client, max_calls=max_calls)
    result = None
    try:
        result = run.execute(brief)
        report = run.report(result["state"], {"text_sha256": result["text_sha256"]})
    except live.Blocked as exc:
        report = run.report("BLOCKED_EDITORIAL", str(exc))
    # Logs contain metadata only. The draft stays in the user's private path.
    report_path = live._write_private(destination, report, result["text"] if result else None)
    return {
        "status": report["status"], "run_id": run.run_id,
        "calls": len(run.receipts),
        "report_saved_private": bool(report_path),
        "leo_approval_verified": False,
        "publication_authorized": False,
        "note": "API pilot, not ChatGPT autonomous subagent execution or production readiness",
    }


def _get_private_run_files(run_id):
    if not isinstance(run_id, str) or not SAFE_RUN_ID.fullmatch(run_id):
        raise BridgeBlocked("INVALID_RUN_ID")
    try:
        uuid.UUID(run_id)
    except ValueError:
        raise BridgeBlocked("INVALID_RUN_ID") from None
    dest = private_dir()
    return (dest / ("simba-core-" + run_id + ".json"),
            dest / ("simba-core-" + run_id + ".txt"))


def audit_private(args):
    report_path, txt_path = _get_private_run_files(args.get("run_id"))
    if not report_path.is_file() or not txt_path.is_file():
        raise BridgeBlocked("PILOT_FILES_NOT_FOUND")
    if report_path.stat().st_size > 2_000_000 or txt_path.stat().st_size > 100_000:
        raise BridgeBlocked("PRIVATE_FILE_TOO_LARGE")
    _, audit = load_core()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    final = txt_path.read_text(encoding="utf-8")
    return audit.audit_receipts(data, final)


def read_private(args):
    _, txt_path = _get_private_run_files(args.get("run_id"))
    if not txt_path.is_file() or txt_path.stat().st_size > 100_000:
        raise BridgeBlocked("PILOT_TEXT_NOT_FOUND")
    return {"status": "PRIVATE_PILOT_DRAFT_UNAPPROVED",
            "text": txt_path.read_text(encoding="utf-8"), "publication_authorized": False}


def tool_call(name, args):
    if not isinstance(args, dict):
        raise BridgeBlocked("INVALID_TOOL_ARGUMENTS")
    if name == "simba_core_preflight":
        if args:
            raise BridgeBlocked("INVALID_TOOL_ARGUMENTS")
        return preflight()
    if name == "simba_core_run_private_pilot":
        return run_private_pilot(args)
    if name == "simba_core_audit_pilot_receipts":
        return audit_private(args)
    if name == "simba_core_read_pilot_text":
        return read_private(args)
    raise BridgeBlocked("UNKNOWN_TOOL")


def handle(message):
    method = message.get("method")
    request_id = message.get("id")
    if not isinstance(method, str):
        raise BridgeBlocked("INVALID_JSONRPC")
    if method == "notifications/initialized" or method.startswith("notifications/"):
        return None
    if request_id is None:
        return None
    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "simba-core-private-pilot", "version": VERSION},
            "instructions": (
                "Text editorial pilot only. Preflight first. NEVER invoke paid "
                "API without explicit user approval and local operator gate. "
                "Do not claim actual ChatGPT multi-agent execution, Leo approval "
                "or publication; even genuine API calls are unverified pilots."
            ),
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params") or {}
        try:
            info = tool_call(params.get("name"), params.get("arguments") or {})
            result = {
                "content": [{"type": "text", "text": json.dumps(info, ensure_ascii=False)}],
                "isError": False,
            }
        except (BridgeBlocked, ValueError, OSError, ImportError) as exc:
            result = {
                "content": [{"type": "text", "text": json.dumps(
                    {"status": "BLOCKED_RUNTIME_INTEGRATION",
                     "reason": str(exc) if isinstance(exc, BridgeBlocked) else type(exc).__name__,
                     "publication_authorized": False}, ensure_ascii=False)}],
                "isError": True,
            }
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32601, "message": "Method not found"}}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main():
    for raw in sys.stdin.buffer:
        if len(raw) > MAX_INPUT_BYTES:
            continue
        try:
            message = json.loads(raw)
            response = handle(message)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except (ValueError, TypeError, AttributeError) as exc:
            sys.stderr.write("Simba MCP rejected malformed input: " + type(exc).__name__ + "\n")


if __name__ == "__main__":
    main()
