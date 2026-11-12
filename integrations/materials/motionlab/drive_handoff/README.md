# MotionLab -> Google Drive -> Montage

Status: the deployed receiver passed the synthetic round-trip and duplicate-submit test (PR #141). This is not a real project render or Montage acceptance. Opening private original clips from a project link is a separate change and requires redeploying the same Apps Script deployment with the updated Code.gs, updating the two existing Wix JS files, and a real-project readback test before announcing it live.

## Open a private project in an ordinary browser

The existing ticket issuer optionally validates `preview_assets`: exact asset ID, private A2E archive Drive file ID, SHA-256, byte size, and `video/mp4`. Every scene must name one of these exact sources. Limits: 24 unique originals, 20 MiB each, 120 MiB total. The ticket binds the **original launch bytes SHA-256**, project, request and source fingerprint; write-only legacy tickets grant no project-read access.

The project link is the existing `storyboard.html` URL with fragment `#project=TICKET_ID.TICKET_TOKEN`. Supply this link privately to the owner only; never commit it or put it in an Issue. The fragment is removed immediately into same-tab sessionStorage (not localStorage or HTTP query/referrer). A refresh can restore it until the server-side three-hour expiry. A new browser needs its own private link. The capability grants only this project's listed previews and its existing one-use selection submission; it is not a Drive OAuth token.

`load_project` / `load_asset` POST operations reuse the existing Apps Script deployment and exact-origin, nonce-bound response channel. They never list arbitrary Drive contents, take a caller-supplied Drive file ID, create a receipt, or trigger Montage. The source must be private and inside Launches; original clips must be private and inside the existing A2E_Auto_Archive folder. Server and browser verify original SHA-256 before previews are attached. There is no public file sharing. Editor controls are inert while loading; source changes and unsupported/expired replies show a failure instead of a successful project-open status. Same-source reload retains already restored draft scene settings but does not invent user approval.

To prepare a project, store its real verified source launch and preview manifest in private Launches, issue the existing ticket once, then read the authorized launch through the owner Drive connection to deliver the private fragment link. The issuer logs only private file IDs and expiry. Do not create another ticket after an ambiguous issuer result until checking existing Tickets/Launches. A project-open success is not a selection ACK, APPLIED, render authorization, verified audio timing, or publication.

## Private owner-only Drive folders

- Parent MotionLab_Handoff: 18Nv8mJ-pAafpGIkxNaDBnlVdBZ51cJ_2
- Launches: 10IdAl9pS-YSqLEYFbfTIKNEoho7bWGWA
- Tickets: 1lHQS4Pfl3OhDoxeWEL768C-XkBIcCxjs
- Inbox: 1gYNUU3HUeWnu2jEcs1gEf4cu9LJEEPoD
- Applied: 1Ya87Y6FUUmstpSs8jG0mKvEVLRqTvwxH

All are inside the existing Simba Media Archive, owned by the same account as the existing GitHub Drive OAuth integration. Never share these folders publicly.

## Operational flow

1. Dispatcher saves a real approved MotionLab storyboard launch/v1 with exactly three proposed options and its canonical source fingerprint in the private Launches folder.
2. GitHub Action MotionLab - issue one-use private Google Drive launch ticket takes that file ID. It reuses existing GDRIVE_OAUTH_CLIENT_ID, GDRIVE_OAUTH_CLIENT_SECRET and GDRIVE_OAUTH_REFRESH_TOKEN GitHub Secrets. It writes a private ticket containing only a SHA-256 of a random capability; a separate private launch includes the actual capability and ticket ID, never logged or added to Git.
3. MotionLab imports this authorized private launch. Upon user approval and when the receiver is deployed, the editor sends exact selections to the Google Apps Script web app using an HTTPS form in an invisible iframe. No Wix/Google login or permanent OAuth token is needed in the browser.
4. Apps Script Code.gs validates the one-use ticket inside the owner-only Drive folder, project/request/fingerprint, 3 options, hash, scene limit and no-paid/no-render guards; writes one private Inbox receipt. Duplicate submissions of identical content recover the same receipt. Because Google HtmlService nests response frames, the response script forwards a receipt to ancestors with the exact Wix target origin. MotionLab validates the Google response origin, an unpredictable one-time nonce, the exact selection SHA-256 and the receipt status before saying saved in Google Drive. Browser source-window equality alone is not sufficient for nested Apps Script frames.
5. GitHub Action MotionLab - private Drive inbox to Montage polls the Inbox after explicit enabling, independently verifies source/ticket/hash/guards and creates a private Montage Issue containing ONLY metadata and a private file link. It records the issue ID in private Drive appProperties. It never starts render/TTS/A2E/publishing.
6. Montage verifies original approved media, approved voice/music, forced word alignment and technical QA before declaring APPLIED. No deletions on browser close; no user selection is invented or re-generated.

## One-time Apps Script owner deployment REQUIRED

Existing Drive OAuth tokens do not have script.projects or script.deployments scopes, so GitHub Secrets cannot programmatically publish Apps Script using their current permissions.

- Open https://script.google.com/home/projects/create in the SAME Google account that owns Simba Media Archive.
- Copy the reviewed Code.gs from this GitHub directory into a new script project and save it.
- Deploy > New deployment > Web app. Execute as Me; access Anyone; grant Drive permission to the script owner. Do NOT execute as the anonymous visitor.
- Supply the resulting https://script.google.com/macros/s/DEPLOYMENT_ID/exec URL to the Studio editor config motionlab_drive_config.js. This URL is not a secret; do not supply a token or client secret.
- Update the Wix static site with the allowlisted files and perform one real trusted source test. After verifying a receipt, configure the server-only Actions dispatch token in Apps Script as described in Active-only GitHub dispatch below. No GitHub cron or repository variable is needed.

Important: The earlier Wix CMS and member-login polling architecture is retired and must remain disabled. This replacement does not bypass Montage's existing audio and scene renderer gates.

Official docs:
https://developers.google.com/apps-script/guides/web
https://developers.google.com/apps-script/api/reference/rest/v1/projects/create
https://developers.google.com/apps-script/api/reference/rest/v1/projects.deployments/create

## Automatic free Montage stage — 12 November 2026

Implementation: auto_render.py and render_profiles/alaska-voyager-2027.json. The existing motionlab-drive-inbox.yml workflow is now dispatched immediately on each verified owner-private receipt, with a temporary 10-minute Apps Script retry trigger while ACTIVE. It verifies the consumed one-use ticket, project fingerprint, source media and exact owner-approved selection, then renders with open-source FFmpeg. Unconfigured/unsupported projects remain untouched; no guesswork or paid calls.

The narrowly authorized Alaska pilot pins the real Studio receipt a55b5a41-529e-468f-84e6-09b16c3fccff and selection SHA-256 9580ce34d60afd47c213270a5b9142a9d81ed93caaff179956d98720e4e2a2e3. It uses 10 Studio scenes, nine crossfades of 900ms, seven SHA-verified original A2E MP4s, and approved original audio bitstream copied without re-synthesis. Existing on-screen price/date/contact cues are source-pinned in the profile. Unknown effects or visual coordinates fail closed.

Trust checks: private receipt and consumed ticket; SHA-256 of original private launch and full A2E bytes; exact approved scene order and asset IDs; original approved reference MP4 and AAC ADTS hashes; private Drive destination ACL; full ffmpeg decode, dimensions/length and exact audio byte stream. Render is idempotently archived with private video+QA and a separate Drive receipt in Applied only after upload and readback checks.

Status after technical success is RENDERED_PENDING_OWNER_REVIEW, NOT published or canonically APPLIED; a human separately approves the exact output. The manually approved Alaska reference is not overwritten. Word-level subtitle timing in the Alaska profile is estimated (not forced-aligned), so the QA explicitly retains a listening-review caveat.

No A2E, TTS, paid video service, stock asset generation, public Drive sharing or automatic publication is invoked. GitHub Actions runs only on authenticated Studio dispatch or explicit owner manual invocation; GitHub minutes may count against the account quota, but there is no idle cron.

## Owner-only render result back to Studio (Apps Script deployment gate)

After the automatic FFmpeg workflow has uploaded an MP4 and QA to private Drive, the Code.gs web app now supports read-only operation render_status. It verifies a consumed source-pinned ticket, immutable selection receipt, private Applied render record, original video location/sharing and QA SHA-256 before returning only the private Google Drive view URLs and technical status to the exact Wix Studio origin. Studio displays a link and status without publishing or exposing video bytes. Normal source media reading and new selection submissions still expire after 3 hours; consumed-ticket render-status reading has a separate maximum 24-hour grace after expiry. Invalid/unconsumed tokens receive no extra access.

This result-status change itself requires no new OAuth scope or paid API. The subsequent active-only workflow dispatch additionally requires a narrowly scoped owner Actions token in Google Apps Script Script Properties. It DOES require the user to copy the newest Code.gs to their existing Google Apps Script project and select Deploy > Manage deployments > Edit > New version > Deploy, preserving the same /exec URL. Current Google Drive OAuth keys cannot publish a new Apps Script deployment. Until that owner action, the updated Wix frontend shows render-status unavailable, rather than fabricating a result. The private links need the Google account with owner access to view the MP4.

If the preview ticket expired before the result was ready, Studio can still query the bounded read-only status and show the owner-only video link when opened from the same original private project link. It does not reopen the private source preview or enable a new write.

## Active-only GitHub dispatch (replaces idle polling, 12 November 2026)

The two-hour GitHub Actions schedule is removed. The new workflow is invoked on demand by the existing owner-executed Google Apps Script only AFTER an authenticated Studio selection is validated and durably saved in private Drive. The browser never receives a GitHub credential. In the web app:

- `Code.gs` maintains the private owner Script Properties key `MOTIONLAB_QUEUE_ACTIVE_V1` (receipt IDs, private Drive receipt file IDs, fingerprints, attempts; **no bearer tickets or GitHub keys**).
- One immediate GitHub workflow_dispatch requests only `motionlab-drive-inbox.yml` on the `main` branch with exact receipt_file_id, using the repo-owner fine-grained token held **only** in Script Properties.
- A single temporary owner-installed Apps Script clock trigger runs `motionlabQueueTick` every 10 minutes only while any job is active. It checks for a verified private render receipt, retries dispatch if needed, and deletes itself when the queue is empty. It never changes Drive sharing or performs paid rendering.
- Idempotent GitHub checks prevent duplicate renders. Incomplete work stops after ten attempts or two hours, whichever happens first; the flag is removed and `MOTIONLAB_QUEUE_LAST_RESULTS_V1` records a safe owner-only needs-review status. It never loops indefinitely.
- No GitHub cron runs while the queue is empty. A Google Apps Script trigger is **not** a precise timer; 10-minute wake-ups may be delayed slightly.

**One-time owner action still required (not automatically installed):**
1. In the GitHub account owning the private `legur/Simba` repository, create a **fine-grained Personal Access Token** restricted to `legur/Simba`, **Actions: Read and write** only, with an expiry. Do not grant repository Contents write or any other permissions, and **do not paste the token in ChatGPT, the Wix page, GitHub source, or an issue**.
2. In the owner Google Apps Script project, open Project Settings → Script properties and save name `MOTIONLAB_GITHUB_ACTIONS_TOKEN` with that secret value. Script properties are server-side. Review access and rotate the token before its expiry.
3. Replace existing `Code.gs` with the current reviewed repository source, save, then **Deploy → Manage deployments → Edit → New version → Deploy** (same public /exec URL). On the editor toolbar, run `motionlabActivateQueue` once to authorize Google Apps Script to create its own temporary time trigger and issue the GitHub HTTPS request. If no pending jobs it returns `QUEUE_EMPTY_READY`; this is normal. If approval is not granted or the token is missing, Studio correctly reports Drive saved but GitHub not started.
4. Approve a **fresh** Studio selection and verify Drive Inbox has its receipt, workflow_dispatch appears in private GitHub Actions with matching receipt_file_id, Applied has the signed render result, the temporary clock trigger disappears, and Studio shows the private result link (the previous tested Alaska selection is already completed and cannot be used to prove a new dispatch).

No new cloud service, public Drive sharing, paid A2E/TTS, or publication. Note that private GitHub Actions runner minutes can count against account quotas; dispatch occurs only on active project submissions and bounded retries. This mechanism works while the user is away, only after the owner has completed the explicit one-time Apps Script credential and permission setup.

GitHub workflow dispatch API requirements: https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event
Google temporary time triggers: https://developers.google.com/apps-script/reference/script/clock-trigger-builder#everyMinutes(Integer)
