#!/usr/bin/env python3
"""Generate ONLY the seven not-yet-tried Google 3.8 Flash-Lite Russian male samples.

All audio to PRIVATE Google Drive; fixed text; approved WarmBaritone unchanged.
One-shot claims in the triggering GitHub issue BEFORE a possibly billable request.
Stop the entire run on the first failed request; no retries after HTTP errors.
A2E strictly excluded. Not a batch of custom Voice Design recreations.
"""
import base64
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError

from run_male_prague import (
    make_drive, save_drive, claim_once, post_comment, post_json,
    assert_wav, StopTest, GEMINI_URL,
)

MODEL = "gemini-3.8-flash-lite-tts"
VOICES = (
    "Fenrir", "Puck", "Rasalgethi", "Sadachbia",
    "Sadaltager", "Umbriel", "Zubenelgenubi",
)
STAMP = "PRAGUE-STORY-01-GEMINI-38-LITE-20261107-ONCE"
MAX_CALLS = 7
MIN_GAP_SECONDS = 20
FILENAME_PREFIX = "PRAGUE-STORY-01_Gemini_38FlashLite_"
STYLE = (
    "A native Russian-speaking mature male travel storyteller. "
    "Natural calm conversational delivery, warm, understated, expressive; "
    "no exaggerated bass or advertising tone. Dates and price are pronounced clearly."
)


def generate_once(text, voice):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise StopTest("GEMINI_API_KEY missing; no synthesis sent")
    payload = {
        "model": MODEL,
        "input": [{
            "type": "user_input",
            "content": [{"type": "text", "text": text, "annotations": [
                {"type": "speech_metadata", "style": STYLE}
            ]}]
        }],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    # post_json is a single POST (no automatic retries, no hidden loop).
    result = post_json(GEMINI_URL, payload, {"x-goog-api-key": key, "Accept": "application/json"})
    encoded = []
    if isinstance(result, dict):
        direct = result.get("output_audio")
        if isinstance(direct, dict) and isinstance(direct.get("data"), str):
            encoded.append(direct["data"])
        for step in result.get("steps", []):
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            for part in step.get("content", []):
                if isinstance(part, dict) and part.get("type") == "audio" and isinstance(part.get("data"), str):
                    encoded.append(part["data"])
    if len(encoded) != 1:
        raise StopTest("Gemini output missing/ambiguous; no retry")
    wav = base64.b64decode(encoded[0], validate=True)
    return wav, assert_wav(wav)


def already_saved(drive, folder_id, filename):
    query = "name = '" + filename + "' and '" + folder_id + "' in parents and trashed = false"
    result = drive.files().list(
        q=query, fields="files(id,shared,size,parents),nextPageToken",
        pageSize=20
    ).execute(num_retries=0)
    if result.get("nextPageToken") or len(result.get("files", [])) > 1:
        raise StopTest("Private Drive filename ambiguity")
    rows = result.get("files", [])
    if rows:
        row = rows[0]
        if row.get("shared") or folder_id not in row.get("parents", []) or not int(row.get("size", 0)):
            raise StopTest("Existing Drive voice file is invalid; no auto-retry")
    return bool(rows)


def preflight():
    c = json.loads(Path(__file__).with_name("prague_male_voices.json").read_text(encoding="utf-8"))
    gm = c["candidates"]["gemini"]
    p = c["production_voice"]
    if (c.get("voice_gender") != "male_only" or
        c.get("safety", {}).get("no_more_a2e_requests") is not True or
        c.get("safety", {}).get("pause_additional_gemini_standard_sample_runs") is not True or
        p.get("profile") != "WarmBaritone" or p.get("selection_status") != "approved_by_user" or
        tuple(gm["remaining_oneshot_20261107"]) != VOICES or
        len(VOICES) > MAX_CALLS or len(set(VOICES)) != len(VOICES)):
        raise StopTest("No-A2E, stable Simba voice or non-duplicate voice list failed")
    excluded = set(gm["existing_samples"] + gm["previous_ambiguous_do_not_retry"])
    if excluded.intersection(VOICES):
        raise StopTest("A remaining candidate was already generated/attempted; refusing")
    text = c["text"]
    if not isinstance(text, str) or not 120 <= len(text) <= 300:
        raise StopTest("Unexpected benchmark text")
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        raise StopTest("Gemini key absent")
    return text


def main():
    text = preflight()
    drive, folder = make_drive()  # private storage must work before any paid API call
    outcomes = []
    calls_made = 0
    for voice in VOICES:
        filename = FILENAME_PREFIX + voice + ".wav"
        try:
            if already_saved(drive, folder, filename):
                post_comment("LITE-ALREADY-SAVED: " + voice + ". No new paid request.")
                outcomes.append({"voice": voice, "result": "existing_private"})
                continue
            if calls_made:
                time.sleep(MIN_GAP_SECONDS)
            claim_once(STAMP + "-" + voice)
            calls_made += 1
            wav, seconds = generate_once(text, voice)
            out = save_drive(drive, folder, filename, wav, "Gemini Flash-Lite TTS", voice, seconds)
            post_comment("LITE-SAVED: " + voice + " | duration " + str(round(seconds, 1))
                         + " s | private verified: " + out["file"] + " | no A2E")
            outcomes.append({"voice": voice, "result": "verified", "seconds": round(seconds, 1)})
        except HTTPError as ex:
            # HTTP 429/400/etc. may have a billing effect; never retry automatically.
            post_comment("LITE-FAILED-STOP: " + voice + " | Gemini HTTP "
                         + str(ex.code) + ". Remaining voices not submitted, no retry.")
            outcomes.append({"voice": voice, "result": "failed", "http": ex.code})
            break
        except Exception as ex:
            reason = str(ex)[:140] if isinstance(ex, StopTest) else type(ex).__name__
            post_comment("LITE-FAILED-STOP: " + voice + " | " + reason
                         + ". Remaining voices not submitted, no retry.")
            outcomes.append({"voice": voice, "result": "failed"})
            break
    print(json.dumps({"model": MODEL, "results": outcomes, "new_api_calls": calls_made,
                      "unattempted": list(VOICES[len(outcomes):]),
                      "a2e_api_calls": 0, "simba_default_unchanged": True}, ensure_ascii=False))
    if any(x["result"] == "failed" for x in outcomes):
        raise StopTest("Stopped on first failed Flash-Lite request; no retries")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print("Flash-Lite run ended:", type(ex).__name__)
        raise SystemExit(1)
