# Simba CORE · ChatGPT Desktop MCP bridge

**Scope:** Bon Tours editorial CORE only. No Studio, video, Rafael, social publication, client data, or automatic Leo approvals.

## What is real and what is not

- The plugin ships a **local stdio MCP server** for ChatGPT Desktop. This allows ChatGPT to *request* an editorial test using the separately implemented Simba/Critic/Humanizer API executor. It does **not** create native ChatGPT subagents.
- Tool `simba_core_preflight` is read-only and never spends API credits.
- Tool `simba_core_run_private_pilot` is billable: requires a clearly approved budget, two explicit tool flags and a **separately enabled local operator gate**. Each distinct role is a distinct Responses API request; receipts contain provider IDs and exact text hashes.
- Tool `simba_core_audit_pilot_receipts` checks the stored revision chain, but offline JSON consistency is NOT proof of provider identity. Tool `simba_core_read_pilot_text` reads the local pilot, not an approved post.
- No tool can mark text as approved, send content to a platform, close audit issue #220 or alter the archived APPROVED texts.

## Desktop setup (not performed by installing the archive)

The **current ChatGPT Desktop application** needs to support local MCP servers on this user's machine. A private plugin created in ChatGPT is not automatically installed, connected, or authorized to read your local files.

1. Install Python and check out `legur/Simba` locally. The path must be absolute, and checkout must include `plugins/simba-core/server/simba_core_mcp.py` and `integrations/core/editorial_live_runner.py`. Use an up-to-date `main`.
2. In the desktop local MCP environment, configure `SIMBA_CORE_REPO_ROOT` as that checkout's absolute path, and `SIMBA_CORE_PRIVATE_DIR` as an **existing private directory outside the repository**.
3. On Unix, restrict the private directory to its owner (e.g. mode `0700`); on Windows, restrict its permissions using the folder Security settings, then explicitly set `SIMBA_CORE_WINDOWS_PRIVATE_ACL_VERIFIED=1`. This marker asserts an operator has checked the ACL; it is not the ACL check itself.
4. Install the private `Simba CORE — Редколлегия` plugin and connect its local stdio MCP server. The plugin's `mcp.json` uses `python` on PATH with `${PLUGIN_ROOT}/server/simba_core_mcp.py`. If the desktop surface does not support bundled stdio MCP, add an equivalent local server manually under Settings → MCP servers and restart.
5. Run `simba_core_preflight`. Until setup is complete it correctly returns blockers. A visible plugin card alone is **not** proof of a working server.

**Billable use is disabled by default.** Only for a separately approved budget/configured model: configure `OPENAI_API_KEY` in the user's own protected local environment, set `SIMBA_CORE_ALLOW_BILLABLE=1`, and explicitly authorize both `execute_live` and `permit_billable_api_calls` in a tool call. `max_calls` limits calls, **not money**. There are no automatic network retries on ambiguous outcomes.

The ChatGPT conversation should never ask for the secret API key as a chat message or place it in GitHub. Windows shell/environment specifics vary by desktop configuration; the user sets them locally.

## Reproducible no-charge verification

From a checkout, offline regression tests:

    python -m unittest integrations.core.test_simba_core_mcp -v

Or simulate a stdio MCP handshake:

    python plugins/simba-core/server/simba_core_mcp.py

Supply newline-delimited JSON-RPC `initialize`, `tools/list` or `tools/call` (preflight) messages over stdin. No network or authorization is required for these reads.

## Status and limitations

- Installed/registered plugin: configuration object exists, **not** proof of local execution.
- MCP preflight: local files and gate state, not production quality.
- A paid pilot, if later run, is `LIVE_EDITORIAL_PILOT_UNVERIFIED`, *not* `TEXT_READY_FOR_LEO`.
- Offline receipt readback is `DECLARED_RECEIPTS_CONSISTENT_AUTHENTICITY_UNVERIFIED`.
- Source resolution, TIA, dynamic facts, independent provider validation, exact ChatGPT-runtime attribution and Leo publication authorization remain separate unresolved dependencies in [Issue #220](https://github.com/legur/Simba/issues/220).
