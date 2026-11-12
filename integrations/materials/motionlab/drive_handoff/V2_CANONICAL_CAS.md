# Simba Studio v2: private owner receipt → canonical edit choice (CAS)

**Status as of 12 November 2026:** implementation & offline adversarial tests exist in PR #172; NOT deployed to owner GAS, no real v2 project has been applied. The original v1 FFmpeg workflow is independent and remains live.

## Exact protected transitions

1. Studio v2 sends one user-confirmed `selection/v2` using the existing private, short-lived Apps Script capability (PR #171). Apps Script stores exactly one private `drive-inbox/v2` receipt with `status=V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS`. This status is **not** an approval to render and cannot drive v1's queue.
2. Trusted owner-side Python `v2_receipt_preflight.inspect_receipt(svc, receipt_file_id)` verifies Drive **file ACL** (user-only), exact folder, exact filename `motionlab-v2-TICKET_ID.json`, mime/bytes, receipt UUID and no-render flags; then verifies the consumed owner ticket, owner-only secret hash (never needs token itself), original signed launch SHA, canonical material/proposal SHAs and explicit v2 selection SHA and timestamp. It runs the current official Python `validate_selection_v2()` too.
3. `replay_private_canonical(root, private_root, bundle)` recovers **current** canonical project and approved WAV/music (requiring automatic offline ASR QA), separately hashes and decodes real A2E MP4 frames, recomputes `proposals/v2` and regenerates the approved edit spec. If the stage or source has changed, it fails closed.
4. **Default is read-only.** With no `--apply`, the worker returns `V2_PRIVATE_SOURCE_REPLAY_PASSED_NO_WRITE` only if current original source replay succeeds. No Drive refs, GitHub commit, render, user checkbox or publication is written.
5. Explicit trusted owner-worker `--apply` first uploads four immutable source-bound JSONs to private **Applied** folder (materials, proposals, selection-v2, video-spec), re-reading each and checking SHA/size/ACL. It calls `build_candidate_v2()` using those exact private Drive IDs; this applies the existing project handoff rules but does not change project.json.
6. The narrow GitHub CAS reads **current `main`** `campaigns/PROJECT_ID/project.json`, checks the SHA-1 Git *blob* against the local canonical bytes that were independently replayed, and writes exactly that one project file via GitHub Contents API with the expected blob SHA. A concurrent edit returns a CAS conflict; never override/rebase automatically. No write if the existing `edit_choice` handoff is already recorded, the approved audio lock was modified or the candidate authorizes rendering or publishing.
7. Only **after** GitHub confirms the exact new blob and commit SHA does the worker write a private, immutable, idempotent Applied status `V2_EDIT_CHOICE_CANONICALLY_APPLIED_AWAITING_MONTAGE_PLAN` in a separate file. This is not an MP4 quality check, render authorization or public link.

## Owner-private runtime prerequisites

A legitimate canonical project at its actual `voice_music → edit_choice` handoff; its real private `approved-video-spec.json`, `verified-media.json`, original A2E MP4s, approved WAV/music and source text stored OUTSIDE GitHub; a trusted Python worker with `SIMBA_AUTO_QA_ASR_MODEL_DIR` pointing to a preinstalled private CTranslate2 model plus locally available WhisperX CTC; existing `GDRIVE_OAUTH_CLIENT_ID`, `GDRIVE_OAUTH_CLIENT_SECRET`, `GDRIVE_OAUTH_REFRESH_TOKEN`; and for the explicit CAS only, a narrowly scoped owner **GitHub contents-write** token supplied as `GITHUB_TOKEN` in that worker's secret environment. Do **not** put any of these in Wix static files, source code, the issue tracker or chat.

Trusted read-only invocation, when the owner has provisioned the private runtime:

```bash
python integrations/materials/motionlab/drive_handoff/v2_canonical_cas.py \
  --receipt-file-id PRIVATE_DRIVE_RECEIPT_ID \
  --private-root /OWNER-PRIVATE-PROJECT-JOB-ROOT
```

Only a deliberately authorized owner-run operation may append `--apply`. The command never asks a person to check word timing; the two independent local ASR methods handle the technical check, failing closed on disagreement.

**Deployment blockers:** the trusted v2 private worker has not yet been provisioned with real local model weights and WAV; the owner still needs to deploy additive `CodeV2.gs` plus the reviewed `Code.gs` into the SAME existing Apps Script deployment (new version) because the connected Drive OAuth lacks Apps Script deployment permissions. No new authenticated v2 owner project, ticket or approved selection is currently available for the actual pipeline. Never claim the above worked on the real Alaska profile or start a paid A2E/TTS/renderer.

**Failure/recovery:** if private evidence was staged before GitHub CAS conflict, it remains private but non-applied. If GitHub CAS succeeded but the separate Drive Applied ACK could not be saved, the command reports `V2_CAS_COMMITTED_ACK_PENDING_CHECK_GITHUB`. The owner operator must inspect the canonical GitHub edit_choice marker and the four pinned Drive source files before any recovery. **Do not blindly rerun --apply:** the canonical handoff now exists and source preflight intentionally refuses to replay it as an unapplied project. A separate safe recovery contract is required before auto-retry.

**Tests:** dedicated `studio-v2-canonical-cas.yml` performs only synthetic private Drive and mock GitHub API validation; no real customer WAV, A2E/ASR model, render, paid service, deploy or canonical commit is executed by CI.
