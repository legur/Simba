# Montage Audio Engine: owner-private acoustic timing draft

**Status 12.11.2026:** `LOCAL_WHISPERX_DRAFT_ONLY`. This code is a real local acoustic CTC alignment adapter, **not** production `AUDIO_ALIGNMENT_VERIFIED` and does not switch on v2. The model's own acoustic predictions and interpolation may be wrong, especially spoken numbers and short Russian words. Independent listening/QA is obligatory.

The script `motionlab_audio_alignment_draft.py` accepts ONLY a canonical v2 `voice_music.audio_lock` with approved narration text bytes exactly pinned in `project.sources[]` and existing private WAV/music byte hashes verified against `approved-audio-files.json`. Missing source, changed asset revision, unknown model language, hallucinated/missing words, missing acoustic scores, word overlaps, impossible times, symlinks, private directory inside repo, or accidental overwrites cause `BLOCKED`. It does not use A2E/TTS credentials or download/POST audio to a cloud transcription service.

The optional **owner-invoked local-only** acoustic adapter uses the open-source WhisperX Python API and a language-appropriate CTC alignment model (Russian by default). On a private computer or isolated owned runner with installed WhisperX and model weights, the operator invokes:

```bash
python integrations/video/motionlab_audio_alignment_draft.py \
  --repo-root /private/simba-repository \
  --project YOUR_APPROVED_PROJECT_ID \
  --private-dir /private/owner-audio/YOUR_APPROVED_PROJECT_ID \
  --language ru --device cpu --run-local-acoustic-model
```

The private directory must contain the original already-approved `approved.wav`, music file, and owner-verified `approved-audio-files.json` from the existing Montage gate. The script creates an exclusive owner-private `alignment-draft.json` (mode 0600), never commits source text, WAV or timestamps to GitHub.

**Output remains `DRAFT_ACOUSTIC_TIMINGS_REQUIRE_INDEPENDENT_LISTENING_QA`.** The result cannot be submitted as `bontours.montage.audio-alignment/v1`, cannot set `AUDIO_ALIGNMENT_VERIFIED`, `SPEC_READY`, `render_authorized`, or `published`. The owner must compare word timings while listening to the exact locked WAV and record separate independently verified evidence bound to the audio/source SHA. The existing `motionlab_v2_audio_gate.validate_alignment_evidence()` also cannot certify acoustic truth on its own.

CI only tests mocked local acoustic output and SHA/monotonic/source guards without downloading models or touching private media. No production workflow is enabled by this PR. See the authoritative [v2 activation gates](../../SIMBA%20KNOWLEDGE%20BASE/06_AGENT_WORKFLOWS/STUDIO_MOTIONLAB_MONTAGE_OWNERSHIP_V2.md).
