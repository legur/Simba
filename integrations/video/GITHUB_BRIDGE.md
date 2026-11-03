# Simba A2E: ChatGPT -> GitHub Actions -> A2E (no Wix)

## Purpose

The connected ChatGPT GitHub app can open an issue. A GitHub Actions workflow
then contacts the official A2E developer API directly using A2E_API_KEY from
Actions repository secrets. No API key ever appears in the issue or chat.
This workflow is FREE QUOTE ONLY and cannot create paid tasks.

## One-time setup

1. Review and merge this PR into default branch main.
2. In repository legur/Simba, Settings > Secrets and variables > Actions,
   add secret A2E_API_KEY with the API token from A2E Account > API Token.
   A2E API tokens start with sk_. No Wix secret needed for direct mode.
3. Make sure GitHub Actions runs and issue comment permissions are available.
4. Create an issue authored by legur containing raw JSON:
   {
     "kind": "simba_a2e_quote",
     "scenes": [
       {
         "name": "Prague Charles Bridge",
         "image_url": "https://static.wixstatic.com/media/ACTUAL_IMAGE_ID.jpg",
         "prompt": "Slow cinematic camera push, snowfall, no text"
       }
     ]
   }
5. Add the label a2e-quote to the issue. The workflow comments the result.

The ready test issue for six Prague Rafael frames is legur/Simba#8.

## Direct A2E API

POST https://api.a2e.ai/v1/generation/quote

The body is:
   {
     "endpoint": "/api/v1/userImage2Video/start",
     "requestBody": {
       "name": "Prague",
       "image_url": "https://static.wixstatic.com/media/ACTUAL_IMAGE_ID.jpg",
       "prompt": "Slow push",
       "model_version": "a2e",
       "video_time": 5,
       "auto_add_audio": false,
       "number_of_images": 1
     }
   }

Authorization: Bearer A2E_API_KEY (from Actions secret ONLY).
Accept response only if code=0, data.available=true, data.exact=true
and data.coins is nonnegative and finite.

Official sources:
https://video.a2e.ai/dev
https://video.a2e.ai/dev/openapi-spec

## Safeguards

- Only issue label a2e-quote for issues authored by legur.
- Only HTTPS Wix CDN images, up to six per issue.
- Force one a2e, five-second, no-audio quote per image.
- No chargeable /v1/userImage2Video/start, no automatic retries.
- GitHub token needs contents read and issues write only.
- No raw API bodies, secrets or headers in logs.
- Quote does not reserve credits, prove model entitlement or start videos.
- No approval to spend credits follows from setting an API key.
- A paid workflow would need a separate user-approved exact credit ceiling,
  fresh quote, single-attempt safeguards and monitoring.

## Status

Code and tests should pass before merge. After merge, adding the a2e-quote
label to issue #8 triggers the real free quote. Report VERIFIED only after
GitHub Actions succeeds and issue comment includes real quoted credits.
