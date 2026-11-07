#!/usr/bin/env python3
"""One distinct Gemini male voice after fixing REST parsing; private Drive WAV."""
import json
from pathlib import Path
from run_male_prague import make_drive, gemini_sample, save_drive, claim_once, post_comment, StopTest

VOICE = "Orus"
KEY = "PRAGUE-STORY-01-Gemini-Orus-20261107"
OUTPUT = "PRAGUE-STORY-01_Gemini_Orus.wav"

def main():
    config=json.loads(Path(__file__).with_name("prague_male_voices.json").read_text(encoding="utf-8"))
    if config.get("voice_gender")!="male_only" or VOICE not in config["candidates"]["gemini"]["voice_names"]:
        raise StopTest("Male voice config mismatch, no requests made")
    text=config["text"]
    if not 100 <= len(text) <= 280:
        raise StopTest("Invalid test text")
    drive,folder=make_drive()
    claim_once(KEY)
    try:
        wav, seconds=gemini_sample(text,VOICE)
        stored=save_drive(drive,folder,OUTPUT,wav,"Gemini",VOICE,seconds)
        post_comment(f"TTS-SAVED: {KEY}\nPrivate WAV in Drive verified: {stored['file']}, {seconds:.1f}s. Audio NOT published to GitHub.")
        print(f"Gemini Orus verified: {seconds:.1f} seconds, private Drive WAV only.")
    except Exception as exc:
        msg=str(exc)[:180] if isinstance(exc,StopTest) else type(exc).__name__
        post_comment(f"TTS-FAILED: {KEY}\n{msg}. No automatic retry.")
        raise

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("Orus test failed; no retries. Error class:",type(exc).__name__)
        raise SystemExit(1)
