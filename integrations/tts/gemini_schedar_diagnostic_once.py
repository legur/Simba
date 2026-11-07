#!/usr/bin/env python3
"""Diagnose the remaining Google male catalog with ONE NEW Schedar sample.
No retries of failed Alnilam or Enceladus, no A2E, no paid fallback.
"""
import json
from pathlib import Path
from urllib.error import HTTPError
from run_male_prague import make_drive, gemini_sample, save_drive, claim_once, post_comment, StopTest

VOICE = "Schedar"
STAMP = "PRAGUE-STORY-01-Gemini-Schedar-SECOND-BATCH-20261107"
FILENAME = "PRAGUE-STORY-01_Gemini_Schedar.wav"

def main():
    cfg = json.loads(Path(__file__).with_name("prague_male_voices.json").read_text(encoding="utf-8"))
    assert VOICE in cfg["candidates"]["gemini"]["remaining_oneshot_20261107"]
    assert cfg["production_voice"]["profile"] == "WarmBaritone"
    assert cfg["safety"]["no_more_a2e_requests"]
    txt = cfg["text"]
    assert 120 <= len(txt) <= 300
    drive, folder = make_drive()
    rows = drive.files().list(q="name = '" + FILENAME + "' and '" + folder + "' in parents and trashed = false",fields="files(id),nextPageToken").execute(num_retries=0)
    if rows.get("files") or rows.get("nextPageToken"):
        print("Schedar already exists or Drive listing ambiguous: no generation.")
        return
    claim_once(STAMP)
    try:
        wav, duration = gemini_sample(txt, VOICE)
        result = save_drive(drive,folder,FILENAME,wav,"Gemini",VOICE,duration)
        post_comment(f"TTS-SAVED: {STAMP}\nVerified private WAV {result['file']} ({duration:.1f}s). Production Simba still WarmBaritone.")
        print("SUCCESS: private Schedar file verified.")
    except HTTPError as e:
        post_comment(f"TTS-FAILED: {STAMP}\nGemini returned HTTP {e.code}. No retry; no further samples until review.")
        print(f"ERROR: Gemini HTTP {e.code}. No retries.")
        raise
    except Exception as e:
        post_comment(f"TTS-FAILED: {STAMP}\n{type(e).__name__}, no retry.")
        print("ERROR:",type(e).__name__,"No retries.")
        raise

if __name__ == "__main__":
    try: main()
    except Exception: raise SystemExit(1)
