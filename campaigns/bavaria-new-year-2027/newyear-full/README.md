# Bavaria: complete New Year variants 1 and 2

Leo chose both `1 и 2` after reviewing the three 14-second editing previews.
This task renders both full alternatives, not a merged design and not variant3.
All nine narration lines, soundtrack and original six A2E clips are reused.
No paid generation and no publication.

1. Countdown: the selected 3-2-1/2027 opening continues into full-screen city
   scenes with fir corners, ornaments, snow and warm transitions. Price and
   final contact become separate holiday-invitation cards.
2. Postcards: the selected burgundy/cream moving postcards continue through
   every city. Separate cream postcards carry the price and final invitation.

This folder depends on the sibling `newyear-options` and `anime-festive`
recipes, their pinned Anime.js dependency and staged media. Local staging may
retain underscore folder names; both spellings are supported.
See `../anime-festive/README.md` for clip/current-mix staging.

Generate both dependencies' frame/timing inputs first. Run:
`node ../newyear-options/motion.mjs`, `node motion.mjs`,
`python3 render.py 1`, `python3 render.py 2`, `python3 verify.py`.
Python requires Pillow/numpy; encoding requires FFmpeg. A full human listening
check is not implemented by these scripts.

Generated outputs: Bavaria_NewYear_Countdown.mp4 and
Bavaria_NewYear_Postcards.mp4, each54.625s/720x1280/24fps/1311frames.
The script copies the complete original AAC without re-encoding.
Keep source media, extracted frames, dependencies and outputs outside Git.
Saved deliverables and QA links are in the canonical production/project record.

Selection authorizes producing these two edits. Final acceptance and publication
remain separate. Countdown, snow and ornaments are graphic decoration, not
documentary claims about the future trip.
