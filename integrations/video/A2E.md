# A2E video generator (Wix-backed bridge) — 02.11.2026

**Status: CODE_READY / REMOTE_DEPLOY_PENDING.** The A2E token remains in the Wix
"Давай Поедем" Secrets Manager as `A2E_Key`. The bridge authorization secret
is `Simba_Session_Key` on the same Wix site. Values are never committed or
printed. Both secret names were verified by a read-only Wix check.

## Architecture

```text
Simba / Scenarist / Rafael image (9:16)
    -> integrations/video/a2e_adapter.py
    -> Wix HTTPS /_functions/simbaA2e (token required)
    -> Wix Secrets A2E_Key -> api.a2e.ai
    -> returned task ID -> status -> video MP4 -> Montazher Klod scenes[].clip
```

This is a **renderer**, not a writer/strategist/publisher. Existing approval,
fact gate, Whisper, captions and video QA remain in force. No automatic paid
starts and no automatic Facebook publication.

## Deployment blocker / site safety

The Wix site is linked to GitHub `legur/travel` (wix.config.json, exact
siteId 489d3aa0-caf3-400e-bdc3-7c9510d86236). The backend gateway is in
feature branch `feature/simba-a2e-wix-gateway-20261102`.

IMPORTANT: that repository currently tracks no `src/backend/http-functions.js`,
but production may have existing HTTP functions outside this Git snapshot
(including tours/Simba bot). BEFORE merge or Wix publishing, reconcile the
**actual current Wix backend** and append only `post_simbaA2e` without
replacing any existing exports. Check site preview, Velo imports and site logs.
A Git commit is not proof of Wix publishing. Publish only with a separate site
release permission. Do not publish draft/test creatives.

## Local setup (Leo computer, not in GitHub or chat)

The bridge URL defaults to `https://www.letsgo-world.co.il/_functions/simbaA2e`.
Set `SIMBA_A2E_GATEWAY_TOKEN` securely on the local executor to the value of
the existing Wix `Simba_Session_Key`. This token MUST NOT be placed in
source, logs, screenshots, GitHub Actions secrets output or the chat.
Never set local `A2E_Key`; that credential stays on Wix.

Optional variable: `SIMBA_A2E_GATEWAY_URL` (test-site / production HTTPS URL).

```powershell
python integrations/video/a2e_adapter.py doctor
python integrations/video/a2e_adapter.py quote --image-file "C:\\myframes\\scene1.png" --prompt "Slow cinematic camera push, stable architecture, no text" --out "integrations/video/jobs/demo/scene1.quote.json"
```

`quote --image-file` securely requests a short-lived presigned URL, uploads
PNG/JPEG/WebP bytes straight to A2E without A2E/Wix authorization headers,
then calls the **free** A2E quote API. Images must be <=10 MB. Alternatively
use `--image-url https://.../image.jpg` for publicly available files.
The returned quote file has the exact request body and credits estimate.

## Paid start (explicit acceptance required)

Review the quoted `credits` and only then run this **charged** operation:

```powershell
python integrations/video/a2e_adapter.py start --quote-file "integrations/video/jobs/demo/scene1.quote.json" --max-credits 100 --send
```

`100` is only an EXAMPLE ceiling, not an observed current A2E price.
The Wix backend recomputes the quote immediately and refuses if unavailable
or if `coins > max-credits`. The client creates a hidden atomic start
journal and blocks duplicate requests on the same payload. A2E has **no
documented POST idempotency guarantee**: if the network fails after start,
do NOT delete the journal or resend; reconcile the A2E account/tasks first.

```powershell
python integrations/video/a2e_adapter.py status TASK_ID
python integrations/video/a2e_adapter.py download TASK_ID --output "integrations/video/jobs/demo/c1.mp4"
```

Only `completed` tasks download. Result URLs expire; download promptly.
Montazher uses `{"clip":"c1.mp4","lines":[{"text":"..."}]}` in
`video-spec.json`, then runs its existing QA. A2E result is NOT approved
until Leo reviews it.

## Capabilities and constraints

- Initial scope: Image-to-Video, model `a2e`, exactly 5 seconds, one output.
- Actions: `doctor` (free quote/token smoke), `presign` (upload),
  `quote` (no charges), `start` (charged + explicit limit), `status`.
- Authentication: Wix `Simba_Session_Key` on each call. Server-side Wix
  `A2E_Key` never goes to the client.
- Site endpoint rejects unknown actions and bad payloads, checks task IDs,
  and does not allow arbitrary proxy URLs.
- Automatic polling / repeated paid calls / publishing: NOT enabled.
- The A2E quote checks price but does not reserve credits or prove entitlements.
- Status must not be upgraded to REMOTE_VERIFIED until the production Wix
  backend is deployed and `doctor` succeeds. A 5-second paid smoke requires
  an approved actual source image and an accepted quote ceiling.

References:
- https://video.a2e.ai/dev
- https://video.a2e.ai/dev/image-to-video-api
- https://dev.wix.com/docs/develop-websites/articles/coding-with-velo/integrations/exposing-services/write-an-http-function
