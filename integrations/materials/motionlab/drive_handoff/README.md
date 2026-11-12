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
- Update the Wix static site with the allowlisted files and perform one real trusted source test. Only after a verified Inbox receipt and dry-run set GitHub repo variable MOTIONLAB_DRIVE_INBOX_ENABLED=true. Scheduled polling is OFF by default.

Important: The earlier Wix CMS and member-login polling architecture is retired and must remain disabled. This replacement does not bypass Montage's existing audio and scene renderer gates.

Official docs:
https://developers.google.com/apps-script/guides/web
https://developers.google.com/apps-script/api/reference/rest/v1/projects/create
https://developers.google.com/apps-script/api/reference/rest/v1/projects.deployments/create

## Automatic free Montage stage — 12 November 2026

Implementation: auto_render.py and render_profiles/alaska-voyager-2027.json. The existing motionlab-drive-inbox.yml scheduled job checks private Drive Inbox once an hour. It verifies the consumed one-use ticket, project fingerprint, source media and exact owner-approved selection, then renders with open-source FFmpeg. Unconfigured/unsupported projects remain untouched; no guesswork or paid calls.

The narrowly authorized Alaska pilot pins the real Studio receipt a55b5a41-529e-468f-84e6-09b16c3fccff and selection SHA-256 9580ce34d60afd47c213270a5b9142a9d81ed93caaff179956d98720e4e2a2e3. It uses 10 Studio scenes, nine crossfades of 900ms, seven SHA-verified original A2E MP4s, and approved original audio bitstream copied without re-synthesis. Existing on-screen price/date/contact cues are source-pinned in the profile. Unknown effects or visual coordinates fail closed.

Trust checks: private receipt and consumed ticket; SHA-256 of original private launch and full A2E bytes; exact approved scene order and asset IDs; original approved reference MP4 and AAC ADTS hashes; private Drive destination ACL; full ffmpeg decode, dimensions/length and exact audio byte stream. Render is idempotently archived with private video+QA and a separate Drive receipt in Applied only after upload and readback checks.

Status after technical success is RENDERED_PENDING_OWNER_REVIEW, NOT published or canonically APPLIED; a human separately approves the exact output. The manually approved Alaska reference is not overwritten. Word-level subtitle timing in the Alaska profile is estimated (not forced-aligned), so the QA explicitly retains a listening-review caveat.

No A2E, TTS, paid video service, stock asset generation, public Drive sharing or automatic publication is invoked. Hourly private GitHub Actions uses repository runner minutes, which can count against the account quota; it has a per-run timeout and only renders receipts with approved profiles.
