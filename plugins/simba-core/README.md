# Simba CORE · ChatGPT-first редакционная работа

## Основной режим с 18.11.2026: все выполняется внутри чата

**Прямое решение Leo:** обычные текстовые задания Simba CORE выполняются в самом ChatGPT: чтение правил `legur/Simba@main` через доступные подключенные инструменты → авторский проход → QA/правки → результат и выбор в том же чате. Локальный MCP, Windows PowerShell, Python и отдельный платный OpenAI API **не требуются**. Правила и границы: `SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/CHATGPT_NATIVE_EDITORIAL.md`; onboarding `skills/simba-editorial/SKILL.md`.

**Два типа свидетельств:**
- `CHAT_NATIVE_SINGLE_MODEL`: реальное написание текста в ChatGPT с последовательной самопроверкой, но не с независимыми агентами; результат — `CHAT_DRAFT_SELF_REVIEWED_INDEPENDENCE_UNVERIFIED`.
- `CHAT_NATIVE_VERIFIED_ROLE_TOOLS`: только когда текущая ChatGPT-сессия предоставляет реальные отдельные инструменты ролей и их outputs проверены. В противном случае независимое исполнение остается `BLOCKED_INDEPENDENT_EXECUTOR_UNAVAILABLE`. Не выдавать `OFFLINE_HANDOFF_CONTRACT_OK_NOT_AGENT_EXECUTION` за работу моделей.

Прежняя локальная MCP-ветка ниже сохраняется **только как опциональная legacy-диагностика/отдельный opt-in API pilot**, не как штатная инструкция по использованию Simba. Ее `simba_core_run_private_pilot` остается закрытой без отдельного утвержденного бюджета. Ни один режим не дает автоматического APPROVED/PUBLISHED и не затрагивает Киностудию.

---

## Legacy: локальный MCP-пилот (не требуется для работы в чате)



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

## Windows — unattended local preparation (no API spend)

A Windows PowerShell helper is provided at `plugins/simba-core/setup_simba_core_windows.ps1`. Running it **on the Windows PC**, rather than in a remote ChatGPT session, can:

- Clone the public `legur/Simba` main branch into a dedicated `%LOCALAPPDATA%\\SimbaCore\\Repo` location if absent (requires Git + Python 3.9+); it does **not** overwrite an existing repo.
- Create a dedicated new `%LOCALAPPDATA%\\SimbaCore\\Private` directory (no confidential files downloaded), remove inherited ACLs **only on that new folder**, and verify that only the current user, SYSTEM or Administrators can access it.
- Persist non-secret, per-user `SIMBA_CORE_REPO_ROOT`, `SIMBA_CORE_PRIVATE_DIR`, `SIMBA_CORE_WINDOWS_PRIVATE_ACL_VERIFIED=1` when the ACL check passes.
- Run a **read-only** MCP JSON-RPC preflight and print the actual status and blockers. It does not set a billing flag or API key; no model, publishing or Studio calls.

In PowerShell, after saving the reviewed script locally:

    .\\setup_simba_core_windows.ps1

For an already existing checkout:

    .\\setup_simba_core_windows.ps1 -RepoRoot "C:\\Your\\Simba\\Repo"

The helper does not press buttons or install the private plugin in the ChatGPT Desktop interface. The user must open the plugin card and select Install/Connect if available, then start a new Desktop chat to load the configured local MCP tool. If the app version, workspace, or plan does not support local executor installation, the state remains **BLOCKED**; do not simulate the missing capability.

The GitHub CI executes only **Python/static checks** of this PowerShell file, not Windows PowerShell on the user's machine. The only decisive Windows connection check is its local MCP preflight plus availability of the connected tool in a Desktop chat.

## Windows — recover without ANY Git checkout or PowerShell script

The user's actual Windows PowerShell 5.1 logs showed that **all three approaches failed** with the same Windows-invalid Archivarius paths:

1. `git clone` downloaded the objects but failed working-tree checkout.
2. `git sparse-checkout set` followed by `git checkout main` still touched the invalid index.
3. `git archive HEAD -- <safe paths>` unexpectedly also attempted unpack of that invalid tree and failed.

No further Git actions should be attempted against this damaged working tree.

### Supported recovery method

Use **Python 3.9+** (already observed Python 3.12 on the user's machine) with the standalone `plugins/simba-core/recover_windows.py` helper:

    Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/legur/Simba/main/plugins/simba-core/recover_windows.py" -OutFile "$env:USERPROFILE\Downloads\simba_core_recover.py"
    python "$env:USERPROFILE\Downloads\simba_core_recover.py"

This Python tool downloads GitHub's **commit-pinned source ZIP** over HTTPS (`https://codeload.github.com/legur/Simba/zip/<SHA>`). It validates the ZIP's selected CORE contents **without consulting the corrupted local Git index**, then extracts only `integrations/core/`, `plugins/simba-core/`, `SIMBA KNOWLEDGE BASE/`, `Симба (Писатель)/`, `Critic/` and three root rule files. All `Archivarius` files — including Windows-invalid paths — are ignored. It does not alter Windows PowerShell execution policy, Git metadata, credentials, provider accounts or publication settings.

Success means **only** `CORE_FILES_READY_LOCAL_MCP_NOT_CONNECTED`, not a connected ChatGPT Desktop plugin. Never claim Windows E2E success based solely on Linux CI. A subsequent independent, no-charge local MCP/ACL preflight is still required before any explicit budget-approved API pilot.

The PowerShell setup file now uses the same Python source-ZIP recovery method internally, but **does not need to be run** on Windows devices that prohibit unsigned PowerShell scripts.

## One synthetic text: offline editorial handoff smoke test

After the canonical MCP server is updated to include the new `simba_core_handoff_selftest` tool, it can exercise the **real local handoff state machine** with predetermined fixture strings and structured Critic verdicts. No API key, billing enablement, private output directory, web connection, personal data or owner approval is required for the test.

The fixture follows a synthetic, explicitly fictional museum example through these steps:

    Simba draft -> Critic REVISE -> Simba repair -> Critic PASS
    -> Simba finalize unchanged -> Humanizer changes text -> Critic PASS

It also confirms that a Critic REVISE after Humanizer blocks, that an unchanged Simba repair blocks, and that a fake transport claiming to be live cannot escalate `DECLARED_TEST_ONLY` to a live or production-ready state.

From the local repo, in PowerShell without running an unsigned script:

    $repo = "$env:LOCALAPPDATA\\SimbaCore\\Repo"
    python "$repo\\integrations\\core\\editorial_handoff_selftest.py"

From a connected ChatGPT Desktop session, use the **read-only** tool `simba_core_handoff_selftest` with empty arguments. The expected status is `OFFLINE_HANDOFF_CONTRACT_OK_NOT_AGENT_EXECUTION`, and `live_calls_made`, `publication_authorized`, `leo_approval_verified` all remain `false`.

**Limitations:** a passing synthetic smoke test is not execution of actual Simba/Critic/Humanizer model roles, not authenticated provider receipts, not verified facts, TIA, owner approval or publication. This tool is a protocol/state-machine test only. No other existing approved text is modified.

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
