# Runtime consistency validation — 18.10.2026

Scope: Leo requested fixes after the local project audit. Baseline main was `d17ecd7d1a50ac134ca9d3c3f9a82a1cd5c091a5`, independently matched against GitHub before delivery.

## Adapter execution

- Python 3.14.3, full offline unittest suite: **17/17 PASS**, independently rerun by the integrating agent.
- Three new regression cases were exercised before the fix: non-object package JSON escaped as AttributeError, and directory scan inputs reached the scanner mock. After narrow validation all three pass.
- AST parse: both Python files PASS.
- Windows sandbox blocks asyncio's local socketpair. The full suite ran with normal host permissions; external provider calls remained mocked. No publishing, remote drafts, package installation or paid calls were performed.
- `doctor`: xberg and ru-humanizer NOT_INSTALLED, scanner executable false, BulkPublish credentials false, publication supported false. These fixes do not constitute external deployment or OCR/provider verification.

## Runtime contract walkthroughs

These are checks of the prescribed document contracts, not evidence of generated posts or a live LLM workflow execution.

| Scenario | Required outcome checked |
|---|---|
| One current supplier offer source | Its own dated offer facts remain usable; no automatic second-source requirement |
| Unsupported material claim | Remove optional claim or return a missing/conflicting source blocker; no invented range or softened promise |
| Initial Simba result | Author draft → Internal Critic PASS → author finalize → Humanizer PASS → ready → Leo decision |
| Initial News/Info/Travel/Leo post | Author checks → Humanizer PASS → ready → Leo/policy decision; no added Internal Critic |
| Humanizer semantic change | Return to author; Simba repeats Internal Critic; all applicable post paths repeat Humanizer |
| Changed approved post | Preserve historical version; invalidate approval/policy and dependent readiness; require new checks/approval and affected visual QA/render |
| Hard blocker after two passes | BLOCKED_HUMANIZER; no ready/approval/visual handoff |
| External Critic verdict | Optional evidence/Session Log only; no internal PASS or publication authority |
| Formatter, client letter, JSON, visual | New post-finalization gate is not automatically applied |

Independent reviewer found no actionable conflict in Router/META and the integrated writer/critic/Humanizer/pipeline/trigger changes. Critic scoring criteria, weights, thresholds and C3 exception are unchanged.

## Structural checks

- UTF-8 decoding and balanced fenced blocks: 14 changed runtime documents PASS.
- 61 literal dependency references from AGENTS and KB runtime protocol resolved to existing canonical files.
- Version headers and META system map retain existing canonical paths.
- Whitespace validation uses `git -c core.whitespace=cr-at-eol diff --check` because existing tracked files include Windows CRLF.
- Preserved raw evidence has exact-path `-text -diff` attributes. The initial staged whitespace check flagged whitespace already present in the unchanged original exports; it was preserved, not rewritten. These three artifacts are verified by byte/blob equality instead of source-format lint.

## Archive read-back

- Outside `99_ТРЕБУЕТ_ПРОВЕРКИ`, the scan found 2472 distinct active AR IDs in readable cards with valid front matter and no collisions. This is an identity check, not full schema certification of every imported file.
- The preserved TIA-023 raw file exactly matches baseline Git bytes: 18013 bytes, SHA-256 `82a6ef58fb69915e4e307ede3fe16facab1c7f2a234ad25cd87e36a439704727`.
- Six modified manifest records and their optional runtime paths resolve locally. Source provenance is kept separately from normalized runtime identity/hash.
- A global local-filesystem path probe reported 21 inaccessible manifest paths (including Windows-invalid characters and very long paths). These are unchanged baseline entries; all 2872 original manifest paths exist in the baseline Git tree. This is a local checkout/access limitation, not evidence that this repair deleted those sources. All 2872 current manifest paths resolve in the staged Git index; hashes for all six changed records and their runtime artifacts match that index. All three staged raw evidence artifacts match original baseline bytes exactly.
- TIA-023's complete text is unavailable: the UTF-8 working record explicitly blocks runtime use, preserves only complete valid prefix lines and points to unchanged raw evidence. Existing derived patterns remain historical, unverified evidence.
- Independent archive review found one report-count ambiguity. It was corrected by separating the historical 2026-10-03 inventory from the current Git index (2892 archive paths), and by naming the current repair branch separately from the historical migration branch.

## KB-LINT

| Check | Result and basis |
|---|---|
| L01 SOURCE | PASS — direct user request after evidence-backed audit |
| L02 EVIDENCE | PASS — authorized consistency repair; no inferred content preference promoted |
| L03 PERSISTENT/DYNAMIC | PASS — no current price, availability or entry rule promoted into permanent knowledge |
| L04 TARGET | PASS — module rules, core/workflow and Decision Log updated in their existing layers |
| L05 DUPLICATE/CONFLICT | PASS — fact verification and text-finalization boundaries aligned; writer and independent reviewer passes separated |
| L06 SCOPE | PASS — post authors explicitly named; external Critic and publication authority unchanged |
| L07 REFERENCE SAFETY | PASS — quarantine paths and corrupt sources excluded irrespective of preserved original status |
| L08 VERSION | PASS — canonical rule paths retained; evidence records are historical provenance, not alternate working modules |
| L09 CONTENT LIBRARY | N/A — existing approved/published content was not edited or reclassified |

Limit: this is a bounded consistency repair. Full Archivarius RELEASE-STRICT/schema/sample certification, real supplier OCR and remote BulkPublish read-back remain separate checks.
