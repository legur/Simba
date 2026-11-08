# Bavaria: three new-year editing previews

Leo requested a substantially different New Year edit after the previous
gold-glow version proved too subtle. These are three 14-second visual previews,
not three final reels and not a new choice of voice or music. None selected yet.

1. Midnight: oversized 3-2-1 countdown, flash into 2027, fir corners, ornaments,
   warm lights, snow and restrained gold burst over the existing city footage.
   Full-edit plan: city highlights after the opening, then price as a holiday
   invitation and a clean gold/cream contact card.
2. Postcards: cream-bordered moving cards on burgundy, rotating/sliding card
   exchange, serif heading, festive corners. Full-edit plan: a new postcard per
   city, a large price postcard, final invitation with phone number.
3. Trailer: triptych, split screen and vertical-panel wipes; bold burgundy labels,
   large year and snow. Full-edit plan: alternating layouts for city scenes,
   full-screen price reveal and a stable high-contrast final contact.

All use the same existing narration/music excerpt (first two complete lines),
14 seconds, 720x1280, 24fps, 336 frames. No new paid generation. The final full
reel remains pending Leo's choice and later review; publishing is separate.
The decorative countdown/2027 is a New Year graphic, not a new offer fact.

This recipe depends on the sibling `../anime-festive/` recipe and its staged
media as described there. Local staging may retain the folder name `anime_edit`;
both names are supported. Install the pinned Anime.js package in that sibling.
Run `node motion.mjs` followed by `python3 render.py` here. Pillow/numpy/FFmpeg
are required. Generated states, media and previews stay out of Git.

Output checks are recorded in `verification.json`: all three decode completely,
zero black intervals, identical preview AAC packets, ASR0.93684, spoken excerpt
ends at13.52s before the closing music fade. This is technical review, not human
full listening or final acceptance. Source video animations are reused; snow,
ornaments, countdown and card frames are editorial decoration.
