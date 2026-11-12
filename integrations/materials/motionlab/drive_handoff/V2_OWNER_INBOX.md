# Studio v2: private owner option selection transport

**Status:** additive source, not deployed until owner updates existing Google Apps Script. Live v1 remains independent.

## Backend stage

1. Trusted private v2 worker must complete approved source+WAV/music source locks, unattended dual-ASR QA (#169), original A2E MP4 SHA/ffprobe, and actual frame analysis (#170). Generate **one new** `bontours.motionlab.owner-launch/v2` JSON in private Drive **Launches**, containing exact `materials`, `proposals`, `preview_assets` (one exact asset per approved v2 scene with private Drive file ID, verified SHA, size, `video/mp4`). Do **not** invent a project, propose fake destinations or insert an owner's approval. The metadata is rejected if `audio_alignment_status != AUDIO_ALIGNMENT_VERIFIED_AUTO`.
2. The existing owner GitHub Actions Drive OAuth can run `issue_v2_ticket.py --owner-v2-launch-file-id <ID>` **after** the real owner-approved project is available; no new paid/provider credentials required. It checks the Python proposals contract, canonical SHA and each private preview file's exact folder/size. It writes an `ISSUED` v2 ticket with **only** token SHA to private Tickets, and a separate authorized private launch with bearer token into Launches. Never paste or log that token.
3. Deliver privately to owner only a URL `https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com/studio-v2.html#project_v2=TICKET_ID.TICKET_TOKEN` constructed by trusted owner tools from the private authorized launch, not in GitHub comments or public pages. Browser removes the fragment from its URL and keeps it only in same-tab sessionStorage, for a short-lived 3-hour authorization.
4. Current Apps Script project must contain **both** reviewed files `Code.gs` **and** `CodeV2.gs`, under the same existing deployment (Manage deployments → Edit → New version → Deploy, no URL change). The existing published v1 may continue normally without CodeV2 if this step is not yet done; the v2 UI reports an error rather than pretending to save.
5. Owner opens `studio-v2.html` and sees exactly three options. Private original clips arrive via `v2_asset`, SHA verified server- and browser-side; only source-compatible renderer-supported scene effects are offered. The user must choose one, check explicit approval, and submit. The browser checks hash + Google reply origin + unpredictable nonce and cannot receive a fabricated OK.
6. Apps Script **does NOT call the v1 queue** for `v2_submit`: it creates a private `motionlab-v2-TICKET_ID.json` Inbox receipt, idempotent for identical selection, with `status=V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS`, `canonical_applied=false`, `render_authorized=false`, `published=false`. There is NO auto-render and no automatic publication.
7. Future separate **owner-only canonical CAS worker** must fetch that owner-private Inbox receipt, corresponding original private launch and ticket, re-verify current canonical project/source, auto-analysis by decoding original MP4 bytes and current offline audio QA again, and run `build_candidate_v2(...)` with independent private SHA references before advancing to Montage planning. **Do not** treat a Drive receipt as APPLIED or a render approval.

## Critical boundaries

- This is **separate v2**, not v1 fields with a different schema. Old `Code.gs` v1 routes, receipts and GitHub dispatch stay identical.
- Apps Script verifies source and renderer whitelists for safe inbox storage, but it cannot prove video content semantics or independently execute ffprobe. The downstream trusted Python CAS worker must replay the video check; the source file is only an owner-private input, not self-authenticating analysis.
- No GitHub or OAuth tokens in the client. No public Drive file IDs, media links or URL parameters. A project capability is a temporary **secret** and must not be included in screenshots or public issues.
- Any mismatch, expired token, missing private media, unsupported effect or altered hash is **rejected**, without a v1 render or a second selection receipt.
- There is no automatic Word-by-Word owner audio check. Automatic technical QA is required before v2 proposals.
- The separate v2 Studio currently edits camera/title/transitions/global subtitle effects only. Source text and audio remain immutable; scene layout geometry is not yet editable in this standalone branch.
- A GitHub merge **does not deploy the owner Apps Script**. Current OAuth authorization lacks Apps Script deployment scopes; owner must do that explicit update. No real project v2 end-to-end test has been passed yet.

## CI

`motionlab-v2-secure-inbox.yml` runs the v1+v2 Apps Script code in a fake private Drive context and requires real locally generated MP4 fixture proposals for the Python private-ticket issuer. It verifies protected origin/nonce, scene effect guards, SHA, idempotence, no v1 queue dispatch, no paid operations and no automatic publish.
