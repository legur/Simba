# Real archive MP4/WAV technical QA — 2026-11-11

Scope: existing user-approved archive assets from private Bon Tours Google Drive, verified locally, without publication or paid model calls. **Not** a v2 producer/receiver/render E2E acceptance.

## Actual original MP4 checks

| | Bavaria | Prague |
|---|---|---|
| File | `Bavaria_AnimeJS_Festive_review.mp4` | `Prague_2027_A2E_Animated_Reel_Titles_Mixkit_REVIEW.mp4` |
| SHA256 | `72ced9ef5fad01c96dadb1180d25a36acd8c34c8c504afdf4f874fcf10eeee29` | `7ec84e9ce61b333894476544e995e410f562a374cddc8e9d2c45e52a33e37b37` |
| Duration | 54.625 s | 30.375 s |
| Video | H.264, 720×1280, 24 fps | H.264, 1080×1920, 16 fps |
| Audio | AAC stereo 96 kHz | AAC stereo 44.1 kHz |
| Full FFmpeg decode (`-xerror`) | PASS | PASS |
| Black intervals ≥0.1 s | 0 | 0 |
| Silence events ≥0.7 s at −45 dB | 0 | 0 |

Prague SHA matches the existing 2026-11-05 QA record. Hard cut detection at `scene>0.35` finds Prague visual boundaries at 5.0625, 10.125, 15.1875 and 25.3125 s. Bavaria uses soft overlaps (visible near t≈14s), so this threshold finds no hard cuts. **Zero hard cuts is not evidence of zero transitions.** Contact-sheet inspection was performed, but final editorial approval was not.

## Real previously saved Prague voice source

`SIMBA_Design_WarmBaritone_Prague.wav` from the archived TTS folder was downloaded and byte-verified: **21.36 s, 24 kHz, 16-bit PCM mono, 1,031,394 bytes**; SHA256 `b3a257d0b736c269d7d320862715e9b3d9ed5042e10a82b234371cfd32724a3f` matches the 2026-11-10 archival technical report.

A **new zero-paid FFmpeg technical preview** was produced from the archived Prague MP4 + that **existing WAV**, with voice start 1.05 s, music sidechain ducking and two-pass loudness normalization. New local test output `prague_WarmBaritone_reuse_14LUFS_TECH_PREVIEW.mp4`:
- ~30.4 s, 1080×1920, H.264 copied (bitstream SHA256 `693871439f269cc2f77fe6168fdf577edcada53b5c8959ee006839efaf1cb63a` **exactly matches the input**); AAC stereo 48 kHz.
- Integrated loudness measured **−13.7 LUFS**, true peak **−2.0 dBFS**.
- MP4 SHA256 `f00ec99e2b585d5c7d459ef4f26aa22fefa76cbe807426689391caef1e0a7090`.
- Full decode PASS, black intervals ≥0.1 s: zero, new A2E/TTS calls: zero, publication: none.
- **NOT** ASR/transcript-verified, not word-timed, not listened to or approved by owner, and no current commercial pricing verified.

## Production boundary

Prague canonical `campaigns/prague-new-year-2027/project.json` is already **closed and publication reported by Leo**, and it has **no voice_music narration asset** matching the newly introduced production WAV gate. This archive proof shows a real reuse mix is technically possible; it **does not pass** the `motionlab_approved_audio.py` canonical handoff or authorize changes to the closed project. Do not overwrite canonical Prague, distribute the test video as an approved marketing asset, or conflate this with the still-blocked `Motion Lab v2 → Montage` end-to-end renderer.

Status: **ARCHIVAL_MEDIA_TECH_QA_PASS / WAV_REUSE_FFMPEG_TEST_PASS / V2_E2E_NOT_VERIFIED / EDITORIAL_REVIEW_REQUIRED**.
