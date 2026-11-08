# Bavaria festive edit: selected option 3

Task-only render recipe, selected by Leo on 2026-11-08. No provider calls,
credentials, new TTS or A2E. Anime.js 4.2.2 calculates motion; Pillow draws;
FFmpeg encodes and copies the existing nine-line AAC without re-encoding.
This does not change the system-wide renderer defaults.

Stage this directory under a job folder. Input layout:

- `../fullinput/assets/scene_1.mp4` through `scene_6.mp4`, `regensburg.jpg`,
  `alley.jpg`: existing private Drive input `1pWc4i0ArwthwbX1AWNyDgukOQMbo9O5Y`.
- `current/Bavaria_Google_A2E_review.mp4`: the complete pre-edit review,
  private Drive `1OAKbxokeAGhgFtzh64YIw65ef5vW5JLn`, 54.625 seconds.
- `current/Bavaria_Reel.srt`: Library `libfile_e20625b2b830819182e3160c95dbd340`
  version 2 (35 short groups). Preserve Library identity when retrieving it.
- `alignment.json` contains the word timing from the unchanged complete mix.

Dependencies: Node >=22, npm, Python with Pillow and numpy, FFmpeg.
Run from this directory: `npm ci`, `python3 prepare.py`, `node motion.mjs`,
`python3 render.py`. The lockfile pins the Anime.js dependency.
Outputs: `Bavaria_Google_A2E_review.mp4`, generated `motion.json`, sampled JPEGs.
Generated frames, dependencies, media and render outputs stay outside Git.

Verified edit: 54.625 seconds, 720x1280, 24fps, 1311 frames;
video SHA256 `72ced9ef5fad01c96dadb1180d25a36acd8c34c8c504afdf4f874fcf10eeee29`.
Encoded output bytes may vary with FFmpeg/Pillow versions.
AAC packet SHA256 unchanged from input:
`cc4bcce52c2ba974dd7dd8d38cd00b5ebc2f84d6c38247651295ecc64a087341`.

KADR-002: hold the city headline across the Munich/Nuremberg background change;
separate readable offer and CTA. Gold glow is Leo's selected style, not borrowed
reference audio. Leo review and publication authorization remain separate.
