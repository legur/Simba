# MotionLab → Wix member inbox → GitHub Actions → Montage

**Status (2026-11-11):** browser build deployed on existing Headless site; Wix collection API smoke TEST insert/read/delete passed; GitHub PR #133 draft until merge. Backend polling intentionally **disabled** until allowlist and GH secret are tested. Nothing authorizes MP4, A2E, TTS, paid actions or publication.

## Ownership and storage

- **Studio = MotionLab**, one editor. The browser authenticates a Wix *site member* using OAuth 2.0 PKCE (public `clientId` only). It writes a **create-only** item to the existing private CMS collection `SimbaMotionLabInboxV1`.
- **Wix site**: `795efbc2-50c4-435e-939e-537cb2df75c7`; login callback is `https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com/storyboard.html`. Dedicated public OAuth app ID: `2771b8ab-4ba7-4438-a6f1-5a37a7bc665a`, no client secret in browser. Previous Headless OAuth app untouched.
- **CMS permissions**: `insert=SITE_MEMBER`, `read=SITE_MEMBER_AUTHOR`, `update/remove=ADMIN`. Public/visitor writes are *denied*. GitHub validates authoritative Wix-owned `_owner` against allowlisted member ID.
- **GitHub Actions** owns all server secrets and polls `PENDING` records (max 100 per run; cron twice hourly; manual workflow dispatch available). It validates `projectId/sessionId/deliveryId/sourceFingerprint`, canonical SHA-256 JSON, no-paid guards and forbidden private fields. For each item, stores immutable data under `motionlab-inbox/<delivery-id>`, path `inbox/selection.json` (one branch per approval). An identical retry returns the old receipt. Only after the GitHub content write succeeds does Wix get state `SAVED_IN_GITHUB_PENDING_MONTAGE`.
- **Montage** must independently verify original project stage fingerprint, actual private source media, approved audio lock, true word alignment and renderer capabilities. The inbox record says **untrusted pending source verification** and never means `SPEC_READY`, `APPLIED` or `VIDEO_QA_PASS`.
- **Cleanup**: The temporary branch must not be removed on page close. Branch deletion is permitted only after verified Montage/Dispatcher `APPLIED` and durable canonical receipt/archive. CMS record retention should likewise follow verified consumption; no automatic cleanup is wired yet.

## Provisioned live Wix resources

- CMS collection `SimbaMotionLabInboxV1` with fields: `projectId`, `sessionId`, `deliveryId`, `selectionSha256`, `sourceFingerprint`, `ownerSessionReceipt`, `selection` (OBJECT), `state`, `githubReceipt`, `errorCode`, `updatedUtc`.
- OAuth app callback `/storyboard.html`; browser access tokens held only in same-tab `sessionStorage` (expired tokens require login again), never in Git. No Wix admin token or GitHub PAT in frontend.
- Browser `motionlab_wix_inbox.js` handles sign-in, create-only receipt, read-only status recovery. Editor `storyboard.js` protects existing direct host bridge, and allows verified stage **draft selection** in a separate Wix member mode if host bridge is absent. Real browser MP4 bytes are not uploaded. Unsupported visual edits are attached only as `visual_draft` with a production blocker. Login after importing an MP4 or changing visual geometry is blocked to avoid silently losing unpersisted browser media/layout.

## Server activation gate

In the GitHub repository settings, ensure:

1. Existing Actions secret `MOTIONLAB_WIX_API_KEY` is an API key for this site with Wix **Read Data Items** and **Write Data Items** scope (the separate Wix Headless CLI 403 `VELO.APP_PROJECT_READ` does not prove CMS authorization).
2. Actions secret `MOTIONLAB_WIX_OWNER_ID` is the actual Wix *member ID* of the authorized editor user. Do not substitute an unverified account ID. The member ID may be read from Wix Members only **after real login** confirms it matches the CMS `_owner`.
3. Repository variable `MOTIONLAB_INBOX_ENABLED=true` is set only after successful dry-run and tested member insert/status recovery. When missing, scheduled polling jobs skip.
4. Merge PR #133 to `main` only after CI and review; GitHub scheduled workflows run only from default branch. No automatic pipeline trigger comes from a push made by `GITHUB_TOKEN`; Montage consumer must read the branch explicitly or be dispatched from the poller in a separate implementation.

To test manually use **Actions → MotionLab Wix inbox to GitHub → Run workflow** with `dry_run=true` first. A real E2E test requires a real site-member sign-in, a real approved source fingerprint (not guessed), persisted `PENDING`, successful poller/branch write, Wix status `SAVED_IN_GITHUB_PENDING_MONTAGE` and subsequent trusted Montage receipt. It **must not** start render/TTS/A2E.

## User-visible status contract

| UI text | What it proves |
| --- | --- |
| Wix login required | no member access; no submission |
| Saved in Wix | Wix create-only `dataItem.id` confirmed; not yet delivered |
| In GitHub / awaiting Montage | Wix row PATCH indicates the GitHub receipt was saved |
| Montage applied | **not implemented in inbox v1**; only trusted Dispatcher/Montage canonical CAS may claim it |
| Network/permission/error | no false ACK or production authorization |

The previously reported offline 10-scene test is still **not an authentic production source** merely because it has JSON or frames. Montage v1 8-scene render limit and real audio word alignment remain separate blockers. No material has been invented or rendered.
