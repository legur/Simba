#!/usr/bin/env python3
"""Private male Russian Gemini comparisons; existing A2E samples are intentionally skipped."""
import json
from pathlib import Path
from run_male_prague import make_drive, gemini_sample, save_drive, claim_once, post_comment, StopTest

SET = ("Iapetus", "Algenib")
STAMP = "20261107-GEMINI-OTHER-MALE"

def main():
    cfg=json.loads(Path(__file__).with_name("prague_male_voices.json").read_text(encoding="utf-8"))
    text=cfg["text"]
    if cfg.get("voice_gender")!="male_only" or not cfg["safety"].get("no_more_a2e_requests"):
        raise StopTest("Male-only / skip-A2E policy missing")
    available=cfg["candidates"]["gemini"]["voice_names"]
    if not 120 <= len(text) <= 300 or any(v not in available for v in SET):
        raise StopTest("Invalid benchmark text or voice")
    drive, folder=make_drive()
    outcomes=[]
    for voice in SET:
        key=f"PRAGUE-STORY-01-Gemini-{voice}-{STAMP}"
        try:
            claim_once(key)
            wav,duration=gemini_sample(text,voice)
            file=f"PRAGUE-STORY-01_Gemini_{voice}.wav"
            row=save_drive(drive, folder, file, wav, "Gemini", voice, duration)
            outcomes.append({"voice":voice,"status":"VERIFIED","seconds":round(duration,1)})
            post_comment(f"TTS-SAVED: {key}\nPrivate Drive verified: {row['file']}, {duration:.1f}s. No A2E requests.")
        except Exception as ex:
            reason=str(ex)[:160] if isinstance(ex,StopTest) else type(ex).__name__
            post_comment(f"TTS-FAILED: {key}\n{reason}; no retry. No A2E requests.")
            outcomes.append({"voice":voice,"status":"FAILED"})
    print(json.dumps({"samples":outcomes,"a2e":"skipped per user"},ensure_ascii=False))
    if any(row["status"]=="FAILED" for row in outcomes):
        raise StopTest("Some samples not verified; no automatic retries")

if __name__=="__main__":
    try: main()
    except Exception as ex:
        print("TTS ended:",type(ex).__name__)
        raise SystemExit(1)
