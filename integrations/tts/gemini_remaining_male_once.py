#!/usr/bin/env python3
"""Remaining 11 Gemini male voices for private Russian PRAGUE-STORY-01 comparison.

ONE paid interaction per new voice, never A2E, never remake previously sampled
or ambiguous calls. Previous approved WarmBaritone remains unchanged.
"""
import json
from pathlib import Path
from run_male_prague import (
    make_drive, gemini_sample, save_drive, claim_once,
    post_comment, StopTest
)

VOICES = (
    "Achird", "Alnilam", "Enceladus", "Fenrir", "Puck", "Rasalgethi",
    "Sadachbia", "Sadaltager", "Schedar", "Umbriel", "Zubenelgenubi"
)
STAMP = "PRAGUE-MALE-STANDARD-20261107-ONE-SHOT"
MAX_REQUESTS = 11
MAX_INPUT_CHARACTERS = 3200


def already_present(drive, folder_id, filename):
    q = "name = '" + filename + "' and '" + folder_id + "' in parents and trashed = false"
    result = drive.files().list(q=q, fields="files(id,shared,size,parents),nextPageToken",
                                pageSize=20).execute(num_retries=0)
    if result.get("nextPageToken") or len(result.get("files", [])) > 1:
        raise StopTest("Ambiguous Google Drive destination; no synthesis")
    if result.get("files"):
        f = result["files"][0]
        if f.get("shared") or not int(f.get("size", 0)) or folder_id not in f.get("parents", []):
            raise StopTest("Existing voice sample invalid; no automatic regeneration")
        return True
    return False


def main():
    config = json.loads(Path(__file__).with_name("prague_male_voices.json").read_text(encoding="utf-8"))
    if config.get("voice_gender") != "male_only" or not config.get("safety", {}).get("no_more_a2e_requests"):
        raise StopTest("Male-only and A2E exclusion required")
    if config["production_voice"]["profile"] != "WarmBaritone" or config["production_voice"]["selection_status"] != "approved_by_user":
        raise StopTest("Approved production voice must not change")
    candidates = config["candidates"]["gemini"]
    if (tuple(candidates["remaining_oneshot_20261107"]) != VOICES or
        any(voice in candidates["existing_samples"] + candidates["previous_ambiguous_do_not_retry"] for voice in VOICES) or
        len(set(VOICES)) != len(VOICES)):
        raise StopTest("Voice list does not match verified non-duplicate male catalog")
    text = config["text"]
    if not 120 <= len(text) <= 300 or len(VOICES) > MAX_REQUESTS or len(text)*len(VOICES) > MAX_INPUT_CHARACTERS:
        raise StopTest("Batch exceeds strict paid-call or text limits")
    drive, folder = make_drive()  # Storage access checked before ANY billable call.
    outcomes = []
    failures = 0
    for voice in VOICES:
        file = f"PRAGUE-STORY-01_Gemini_{voice}.wav"
        key = f"{STAMP}-{voice}"
        try:
            if already_present(drive, folder, file):
                post_comment(f"TTS-EXISTING: {voice}; private sample already exists. No new synthesis.")
                outcomes.append({"voice": voice, "status": "EXISTING"})
                continue
            claim_once(key)  # Issue comment persisted before potential charge.
            wav, duration = gemini_sample(text, voice)  # EXACTLY ONE POST (no retries).
            result = save_drive(drive, folder, file, wav, "Gemini", voice, duration)
            post_comment(f"TTS-SAVED: {key}\nVerified private WAV {result['file']} ({duration:.1f} seconds). No public audio, no A2E calls.")
            outcomes.append({"voice": voice, "status": "VERIFIED", "seconds": round(duration, 1)})
        except Exception as exc:
            reason = str(exc)[:140] if isinstance(exc, StopTest) else type(exc).__name__
            post_comment(f"TTS-FAILED: {key}\n{reason}. NO retry, check charges before manual recovery.")
            outcomes.append({"voice":voice,"status":"FAILED"})
            failures += 1
            # Provider/schema failures should not trigger a long list of billable requests.
            if failures >= 2:
                post_comment("TTS-BATCH-STOP: 2 failed voice requests. Remaining voices NOT attempted to avoid costs.")
                break
    print(json.dumps({"results": outcomes, "a2e_requests": 0,
                      "production_voice_changed": False}, ensure_ascii=False))
    if failures:
        raise StopTest("Some voice generations failed; no automatic retries")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("TTS male catalog run stopped:", type(exc).__name__)
        raise SystemExit(1)
