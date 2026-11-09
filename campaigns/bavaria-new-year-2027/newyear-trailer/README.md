# Bavaria: full festive trailer, option 3

Leo requested the last option too on 2026-11-09, after receiving full options1/2.
This produces the selected third alternative, with all nine existing narration
lines and the unchanged complete soundtrack. No new paid generation.

Visuals: triptych, split screen, six-panel vertical wipes, bold burgundy labels,
large price pop and a stable final contact panel. The selected preview opening
is retained in style. Wipes move old panels out to reveal the new view; body
panels use crops of the current city's clip, not new photographic angles.

Dependencies: sibling `newyear-full`, `newyear-options` and `anime-festive`
recipes and their staged media. Local underscore staging names are supported.
Generate the dependent motion.json files, then run `node motion.mjs`,
`python3 render.py`, `python3 verify.py`. Node>=22, pinned Anime.js4.2.2,
Python Pillow/numpy and FFmpeg are required.

The render copies the complete existing AAC stream without re-encoding.
Output: Bavaria_NewYear_Trailer.mp4,54.625s,720x1280,24fps,1311frames.
Task motion is computed with actual paused Anime.js animations, composed in
Pillow and encoded by FFmpeg. No global renderer/workflow defaults change.

Media, dependencies and generated motion states stay outside Git.
Human full listening/final acceptance and publishing remain separate from
technical render verification.
