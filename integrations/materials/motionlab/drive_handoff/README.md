# MotionLab -> Google Drive -> Montage

Status: code prepared, deployment NOT complete. Public MotionLab receiver config URL is blank until verified Apps Script deployment. It must continue to show LOCAL_ONLY before that step.

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
4. Apps Script Code.gs validates the one-use ticket inside the owner-only Drive folder, project/request/fingerprint, 3 options, hash, scene limit and no-paid/no-render guards; writes one private Inbox receipt. Duplicate submissions of identical content recover the same receipt. Client checks iframe source/origin, nonce, SHA-256 and status before saying saved in Google Drive.
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
