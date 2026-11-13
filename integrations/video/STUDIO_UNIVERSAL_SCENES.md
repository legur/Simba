# Universal Studio → Montage scene-count contract

Studio does not require a different website or editor for every reel.
The scene list is taken from the approved project. It creates exactly one
editor for every source scene and one transition editor between adjacent
scenes (count minus one).

## One common limit

- 1–24 ordered scenes (3, 10 and 15 are all valid counts).
- At most 60 seconds of approved final video. More scenes are not a
  permission to exceed the reel duration.
- Original A2E source MP4: at most 20 MiB individually, 120 MiB combined
  for owner-private previews (current mobile/Apps Script transfer limit).
- Up to 24 unique sources; reusing one original MP4 in multiple scenes
  does not mean generating it again or duplicating it in Drive.
- Approved narration, music, prices and captions are immutable; only
  owner-selected supported editing effects reach Montage.

The canonical Python constant is in
integrations/video/motionlab_scene_contract.py. Both make_video.py and
motionlab_render_contract.py import it, while v2 source and mapper code
reuses motionlab_render_contract.MAX_SCENES.

The site (storyboard.js, studio-v2.js) and Google Apps Script (Code.gs,
CodeV2.gs) cannot import Python. Their matching 24-scene values are
explicitly tested for parity by Python CI. Renderer revision fingerprints
the canonical contract, preventing silently stale v2 handoffs.

Tests cover 3, 10, 15, 24 scenes with only two original SHA-pinned A2E
MP4s, each with scene-specific title and timing; unchanged audio, text,
scene order and N-1 transitions; 0 and 25 scenes must fail closed. The
v2 GAS inbox test also checks owner-only selections and no automatic
v1 queue dispatch.

## Important boundary

The original Alaska legacy render profile with required_scene_count=10
pins ONE historical private test approval to its exact source. That
number is not the global platform limit and must not be used for new
projects. Live v2 GAS must be redeployed on the existing /exec before
its new limit can take effect; merging a GitHub PR or updating the
site alone does NOT redeploy Google Apps Script.

A real project with 15 distinct A2E video sources can exceed the
existing 120 MiB transport budget. The present change removes only
fixed scene-count mismatches, not media bandwidth limits, audio QA
requirements or render/publication approval gates.

No rendering, TTS, A2E, paid call or publication is authorized here.
