## Коррекция источника Wix Studio — 02.11.2026

Канонический проект разработки сайта — legur/site-update-system, папка ReDesign/.
Текущий gateway подготовлен в draft PR https://github.com/legur/site-update-system/pull/84
Инструкция: ReDesign/docs/simba-a2e-wix-deployment.md.
Старый PR legur/travel#1 закрыт как устаревший; ветку legur/travel НЕ публиковать.
GitHub PR не равен Wix Studio deployment. Только после Studio read-back существующих
HTTP routes, additive merge и функциональных проверок можно делать публикацию.

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

The Wix Studio gateway source is now in `legur/site-update-system` (ReDesign/) draft PR #84. `legur/travel` is a historical Wix Git Integration snapshot and must not be used to publish.

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


## A2E API documentation alignment — 04.11.2026

The account's image-to-video API documentation was provided in the project chat
on 04.11.2026. For POST /v1/userImage2Video/start it documents:
- image_url, prompt, name, model_version, video_time, number_of_images;
- model_type=GENERAL and model_version=a2e-v2-flash in its dynamic
  "Current Parameters" example. These are **not documented mandatory
  settings for the original a2e model**. Do not silently change approved model
  or pricing based on the example alone.
- HTTP 400 means invalid parameters, but exact failing field is unknown.
- error envelope may include trace_id; save a strictly sanitized trace_id
  for technical support (not the raw response, request or token).
- asynchronous success requires later task-status read-back.

R2 presigned upload:
- Official A2E OpenAPI says the image upload's default bucket is 3days-apac.
- In the original test on 03.11 the A2E presign response supplied a
  7days-apac.downloadaivideo.com CDN URL; PUT succeeded but GET/HEAD
  returned Cloudflare HTTP 403. That proves the URL was inaccessible from
  the GitHub runner, **not** that all A2E customers or all A2E-origin fetchers
  are blocked.
- The direct-upload client now explicitly requests bucket=3days-apac,
  rather than sending the undocumented purpose=STAGING field.
- One successful presign was charged 1 credit; no video tasks were created.
- **No paid rerun has been made after this fix.** Before any further paid
  presign or generation, perform read-only status and transaction checks,
  and obtain approval for any new/changed total credit ceiling.

Primary references:
https://video.a2e.ai/dev/image-to-video-api
https://video.a2e.ai/dev/openapi-spec


## A2E CDN User-Agent fix — 05.11.2026

A2E support asked for an explicit, nonempty `User-Agent` header in outbound
read-only requests, suggesting `User-Agent: Genjutsu`. A GitHub Actions
read-only retest of both previously inaccessible A2E images used precisely
that header and succeeded: HEAD/GET returned HTTP 206 with `image/jpeg`,
including verified JPEG magic bytes on GET for both `3days-apac` and
`7days-apac`. The control Wix image also passed. Prior tests from GitHub
Actions without the explicit header had returned Cloudflare HTTP 403.
Reference: legur/Simba issue #8 (05.11.2026), workflow
`.github/workflows/simba-a2e-user-agent-genjutsu-check.yml`.

Production integration now sends `User-Agent: Genjutsu` on A2E CDN staged
image GET checks and completed MP4 downloads. These requests are read-only
and do not spend credits. This change does NOT prove the video generation
POST will succeed; further credit-bearing tests require independent
authorization and the existing no-retry rules.



## A2E support diagnosis — 05.11.2026

A2E support investigated rejected POST /v1/userImage2Video/start using
`trace_id=aa4531f0-27e8-4216-8ae1-e85dcc617c68`.

Confirmed server validation error:
`prompt and negative_prompt must required when lora is not set`.

**Required fix:** Every Simba a2e image-to-video request MUST include both a
nonempty `prompt` and nonempty `negative_prompt`; use
`negative_prompt="blurry, distorted, static"` by default.
`model_type` is optional (default `GENERAL`). These workflows never enable
`lora`, so they enforce both prompts locally before quoting or submitting.

**Important:** An A2E generation price quote may have
`exact: true` while `generationRequestValidated: false`; a quotation does
NOT prove the request is valid for the paid generation endpoint. Local
required-field preflight runs independently of the quote.

**Credit ledger correction:** A2E support identified the separate 30-credit
consumption at ~05:22 UTC (Nov 05) as a **completed, manual website** task:
- Task ID: `6aec12790dbde9022f6af0b2`
- Task name: `11-04-2026 23:05:12` (date-like name)
- Model: `a2e-v2-flash`; 5 seconds; audio on
- Completed ~05:23:38 UTC.
- This operation was **not** a Simba Prague generation.
- The failed 07:18 UTC API request produced no task and no additional charge.

The original reconciliation incorrectly filtered the task list for the
six named Prague scenes and would omit unrelated date-named or web UI tasks.
It now reports all recent image-to-video tasks and separates named Prague
tasks, explicitly warning when task pagination makes results incomplete.

Previous one-time paid-start journal markers still prohibit automatic
retries. Repeating the paid 30-credit video test requires a fresh, explicit
authorization, a new uniquely scoped no-retry workflow and preflight; do
not re-trigger old labels.


## Durable media archive after A2E completion — 05.11.2026

**Leo's operational correction:** A2E retains generated animated assets for about **3 days** from creation. Treat the expiry as a hard risk; the exact deletion schedule and access to a specific URL must be rechecked. Preserve finished MP4 **immediately when task.status == completed**, not at the end of editing; never rely on A2E CDN as a long-term library.

**Sequence (non-billable):**
1. Before any paid generation, search existing completed A2E task IDs, GitHub Actions artifacts, existing MP4s, and Google Drive. If the asset exists, reuse it instead of issuing a new billable start.
2. When A2E reports completed, download source/result with `User-Agent: Genjutsu`; validate MP4 magic/decoding, exact task ID, duration and SHA-256. Save to an immediate intermediate 30-day GitHub Actions artifact (not permanent storage).
3. Copy original Rafael JPG/PNG, generated MP4, source audio, final reel, metadata (A2E task ID, creation timestamp, prompt, model, SHA-256, origin, license evidence) to the connected **private Google Drive media archive**. Verify file IDs, sizes and folder listing after upload before marking `MEDIA_ARCHIVED_DRIVE_VERIFIED`.
4. Only after verification may a downstream assembly depend on the Drive copy as durable source. If archive fails, state `BACKUP_PENDING`, keep GitHub artifact, notify Leo; do **not** regenerate or repeat a paid POST.
5. A2E CDN may expire in ~72 h, and GitHub Actions artifacts also expire. Neither is a replacement for a persistent Drive archive. Google Drive storage is not Git's canonical text/KB source of truth.
6. **No autonomous background Drive upload is currently deployed** for GitHub Actions; while it is not configured, ChatGPT/Leo must explicitly archive completed assets with the connected Drive connector. Do not advertise continuous monitoring or automatic upload without a real running deployment.

**Project archived on 05.11.2026:** Six A2E Prague New Year 2027 5-second MP4s are preserved in GitHub Actions artifacts 13411260869 (scene 01) and 13412554383 (six-scene archive) and copied, without any new A2E generation, to:
- Google Drive account with project archive: `eskvlg@gmail.com`;
- `Simba Media Archive / Prague_New_Year_2027_A2E_2026-11-05`
- Project folder: https://drive.google.com/drive/folders/1UEY7O26bwHdVlQh2lg82c5WgGDEPlmUP
- `01_Rafael_Source_Images` — six original JPGs and source prompts ZIP
- `02_A2E_Animated_MP4` — ZIPs containing all six finished A2E MP4s
- `03_Final_Reels` — previous **static** test MP4 and separate **animated** 30.375s 6×5s A2E + Mixkit draft (no captions, not approved)
- `04_Audio_License_QA` — original Mixkit MP3 and music QA ZIP

**Archive read-back:** 7 source objects, 2 A2E video ZIP objects, 2 draft reels (static and animated), 2 audio/QA objects. The videos inside the archive were verified by ZIP entry listings, including scene_01.mp4 through scene_06.mp4. The Drive files have explicit IDs and verified parent folder; no billable A2E operation was made for this archival step.

**Animated Prague review draft:** https://drive.google.com/file/d/15OAazKjBeT4_ZhD9fKFX1_8bcpqUcWGc/view?usp=drivesdk (30.375 sec, 1080×1920, original six A2E MP4 scenes, Mixkit Tinsel and Mistletoe; no voice/captions, unpublished). Drive upload and metadata read-back verified on 05.11.2026. This does not upgrade the video to `VIDEO_READY_FOR_LEO` before standard QA and Leo approval.


## Prague A2E animated offer video — title layers & music QA — 05.11.2026

**New review version (not published):** [Prague_2027_A2E_Animated_Reel_Titles_Mixkit_REVIEW.mp4](https://drive.google.com/file/d/15zgVCXp_KBM02sGogYgzIRfK-xXZx5UD/view?usp=drivesdk).

- Source is the **six completed A2E motion clips**, already archived on Drive; do not substitute still photos for motion or regenerate any A2E scene. No new A2E credits were used.
- A 30.375-second, 1080×1920, 16-fps H.264/AAC film is assembled with six readable, fade-animated overlays: title, travel dates and duration, Opera Prague hotel and breakfast, Smartwings flight and luggage, atmosphere, price and WhatsApp CTA.
- Audio: previously archived licensed Mixkit **Tinsel and Mistletoe** (Ahjay Stelino), no artificial narrator; final track attenuated by 2 dB and remuxed.
- Measured technical QA: MP4 full decode OK; 486 video frames; zero black events; integrated loudness −14.1 LUFS, true peak −4.4 dBFS; SHA-256 `7ec84e9ce61b333894476544e995e410f562a374cddc8e9d2c45e52a33e37b37`; file size 29,430,993 bytes. Drive read-back confirmed parent folder and byte size.
- [QA report](https://drive.google.com/file/d/1uHDhS3-fA01VF2iVVWFCFaSKIrg_eLPq/view?usp=drivesdk), [reusable JSON manifest](https://drive.google.com/file/d/1sILGUKvWUkEVAhnYQJ8EBp2moGw1HxG_/view?usp=drivesdk) and [editable overlay/source ZIP](https://drive.google.com/file/d/1h6Z4VwLyl8XcfuYdCXAOszZQHCmz-D8v/view?usp=drivesdk) are archived and verified.
- **Status: `TECH_QA_PASS / LEO_EDITORIAL_REVIEW_REQUIRED / NOT_PUBLISHED`.** Price and availability of the 899 EUR Prague package must be rechecked before use, and Leo must approve the actual video. The external Google Drive upload here was an explicit one-time operation. No unattended auto-archive from GitHub Actions has been deployed.

