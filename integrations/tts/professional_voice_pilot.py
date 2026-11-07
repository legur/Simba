#!/usr/bin/env python3
"""One-shot professional Russian voice evaluation, audio-only and private.

Providers: ElevenLabs, MiniMax and Microsoft Azure Speech.
DRY RUN by default. Execute ONLY with --execute and required secrets.
Never create a video, publish audio, clone a person, or change the approved
Simba WarmBaritone voice. Every paid POST gets a durable issue claim first.
No automatic retries after ambiguous results or HTTP errors.
"""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from run_male_prague import (
    make_drive, save_drive, assert_wav, claim_once, post_comment, StopTest
)

ROOT = Path(__file__).resolve().parents[2]
MODEL = {"elevenlabs": "eleven_multilingual_v2", "minimax": "speech-2.8-hd",
         "azure": "ru-RU-Lev:MAI-Voice-2"}
AZURE_VOICES = {"ru-RU-Lev:MAI-Voice-2", "ru-RU-DmitryNeural"}
AZURE_STYLES = {"ru-RU-Lev:MAI-Voice-2": "reflective"}
MAX_CHARS = 300
MAX_OUTPUT = 18 * 1024 * 1024


def post_once(url, body, headers, timeout=140):
    req = Request(url, data=body, headers=headers, method="POST")
    # Exactly one HTTP call: timeout is AMBIGUOUS, do not retry automatically.
    with urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise StopTest("Unexpected synthesis HTTP status")
        blob = resp.read(MAX_OUTPUT + 1)
        if len(blob) > MAX_OUTPUT:
            raise StopTest("Provider audio response exceeds safety cap")
        return blob


def decode_mp3_to_wav(audio_bytes):
    if not audio_bytes or len(audio_bytes) > MAX_OUTPUT:
        raise StopTest("Invalid or oversized compressed speech audio")
    with tempfile.TemporaryDirectory(prefix="simba_pro_tts_") as dir:
        inp = Path(dir) / "voice.mp3"
        out = Path(dir) / "voice.wav"
        inp.write_bytes(audio_bytes)
        # Use file output rather than stdout to get a valid RIFF length header.
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                   "-y", "-i", str(inp), "-ac", "1", "-ar", "24000",
                   "-acodec", "pcm_s16le", str(out)]
        done = subprocess.run(command, capture_output=True, timeout=50, check=False)
        if done.returncode != 0 or not out.is_file():
            raise StopTest("Unable to decode speech audio as MP3")
        wav = out.read_bytes()
    assert_wav(wav)
    return wav


def elevenlabs(text, voice_id):
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise StopTest("ElevenLabs key not configured")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", voice_id):
        raise StopTest("ElevenLabs voice ID not valid")
    payload = {"text": text, "model_id": MODEL["elevenlabs"],
               "voice_settings": {"stability": 0.5,
                                  "similarity_boost": 0.75,
                                  "style": 0.0,
                                  "use_speaker_boost": True}}
    url = "https://api.elevenlabs.io/v1/text-to-speech/" + voice_id + "?output_format=mp3_44100_128"
    raw = post_once(url, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    {"xi-api-key": key, "Content-Type": "application/json",
                     "Accept": "audio/mpeg"})
    return decode_mp3_to_wav(raw)


def minimax(text, voice_id):
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        raise StopTest("MiniMax key not configured")
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,120}", voice_id):
        raise StopTest("MiniMax voice ID not valid")
    payload = {
        "model": MODEL["minimax"],
        "text": text,
        "stream": False,
        "output_format": "hex",
        "language_boost": "Russian",
        "voice_setting": {"voice_id": voice_id, "speed": 0.96, "vol": 1, "pitch": 0},
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000,
                          "format": "mp3", "channel": 1}
    }
    raw = post_once("https://api.minimax.io/v1/t2a_v2",
                    json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    {"Authorization": "Bearer " + key,
                     "Content-Type": "application/json",
                     "Accept": "application/json"})
    data = json.loads(raw)
    base = data.get("base_resp") or {}
    encoded = (data.get("data") or {}).get("audio")
    if base.get("status_code") != 0 or not isinstance(encoded, str):
        raise StopTest("MiniMax returned non-success/no audio; do not retry")
    if len(encoded) > MAX_OUTPUT * 2:
        raise StopTest("MiniMax result exceeds safety cap")
    try:
        mp3 = bytes.fromhex(encoded)
    except ValueError:
        raise StopTest("Invalid MiniMax hex audio")
    return decode_mp3_to_wav(mp3)


def azure(text, voice_id):
    key = os.environ.get("AZURE_SPEECH_KEY", "").strip()
    region = os.environ.get("AZURE_SPEECH_REGION", "").strip()
    if not key or not region:
        raise StopTest("Azure key/region not configured")
    if not re.fullmatch(r"[a-z0-9]{3,30}", region):
        raise StopTest("Invalid Azure region")
    if voice_id not in AZURE_VOICES:
        raise StopTest("Unexpected Azure Russian male voice")
    voice = html.escape(voice_id, quote=True)
    safe_text = html.escape(text, quote=False)
    if voice_id in AZURE_STYLES:
        safe_text = (
            '<mstts:express-as style="reflective" styledegree="1.1">' +
            safe_text + '</mstts:express-as>'
        )
    xml = ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
           'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="ru-RU">'
           '<voice name="' + voice + '">' + safe_text + '</voice></speak>')
    raw = post_once("https://" + region + ".tts.speech.microsoft.com/cognitiveservices/v1",
                    xml.encode("utf-8"),
                    {"Ocp-Apim-Subscription-Key": key,
                     "Content-Type": "application/ssml+xml",
                     "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                     "User-Agent": "SimbaVoiceEvaluation"})
    assert_wav(raw)
    return raw


def preflight(provider, voice_id):
    cfg = json.loads((ROOT / "integrations/tts/prague_male_voices.json").read_text(encoding="utf-8"))
    approved = cfg["production_voice"]
    if (cfg["voice_gender"] != "male_only" or
        approved.get("selection_status") != "approved_by_user" or
        approved.get("profile") != "WarmBaritone" or
        cfg["safety"].get("no_more_a2e_requests") is not True):
        raise StopTest("Approved Simba production voice or A2E safety gate failed")
    benchmark = cfg["text"]
    if not 120 <= len(benchmark) <= MAX_CHARS:
        raise StopTest("Prague benchmark text changed; refusing evaluation")
    if not voice_id:
        raise StopTest("No specific verified voice ID selected")
    if provider == "azure" and voice_id not in AZURE_VOICES:
        raise StopTest("Only verified Russian male Azure voice names allowed")
    if provider in ("elevenlabs", "minimax") and not re.fullmatch(r"[A-Za-z0-9_-]{3,120}", voice_id):
        raise StopTest("Voice ID contains unsafe characters")
    return benchmark


def drive_exists(drive, folder, filename):
    q = "name = '" + filename + "' and '" + folder + "' in parents and trashed = false"
    records = drive.files().list(
        q=q, fields="files(id,size,parents,shared),nextPageToken",
        pageSize=20).execute(num_retries=0)
    if records.get("nextPageToken") or len(records.get("files", [])) > 1:
        raise StopTest("Ambiguous Drive target; no paid request")
    for record in records.get("files", []):
        if (record.get("shared") or not int(record.get("size") or 0) or
                folder not in record.get("parents", [])):
            raise StopTest("Existing Drive sample invalid; no paid retry")
    return bool(records.get("files"))


def main():
    cli = argparse.ArgumentParser(description="Professional TTS one-shot private voice pilot")
    cli.add_argument("--provider", choices=tuple(MODEL), required=True)
    cli.add_argument("--voice-id", required=True)
    cli.add_argument("--execute", action="store_true", help="Allow ONE billable provider request")
    args = cli.parse_args()
    text = preflight(args.provider, args.voice_id)
    digest = hashlib.sha256((args.provider + "|" + MODEL[args.provider] + "|" +
                             args.voice_id + "|" + text).encode()).hexdigest()[:14]
    filename = "PRAGUE-STORY-01_Pro_" + args.provider + "_" + digest + ".wav"
    if not args.execute:
        print(json.dumps({"dry_run": True, "provider": args.provider,
                          "model": MODEL[args.provider], "chars": len(text),
                          "filename": filename, "audio_created": False,
                          "voice": "WarmBaritone unchanged", "video": False}))
        return
    if os.environ.get("SIMBA_PRO_TTS_ONE_REQUEST") != "YES_ONCE":
        raise StopTest("No explicit per-job one-request cost authorization")
    # Storage and authentication preflight BEFORE any potentially billable call.
    if args.provider == "elevenlabs" and not os.environ.get("ELEVENLABS_API_KEY"):
        raise StopTest("ElevenLabs API secret missing")
    if args.provider == "minimax" and not os.environ.get("MINIMAX_API_KEY"):
        raise StopTest("MiniMax API secret missing")
    if args.provider == "azure" and not (os.environ.get("AZURE_SPEECH_KEY") and
                                         os.environ.get("AZURE_SPEECH_REGION")):
        raise StopTest("Azure API secret/region missing")
    drive, folder = make_drive()
    if drive_exists(drive, folder, filename):
        post_comment("PRO-TTS-EXISTS: " + args.provider + " / " + digest + ", no new request.")
        return
    claim = "PRO-TTS-" + args.provider + "-" + digest
    claim_once(claim)  # Durable issue marker before one request; no retries.
    try:
        wav = {"elevenlabs": elevenlabs, "minimax": minimax,
               "azure": azure}[args.provider](text, args.voice_id)
        duration = assert_wav(wav)
        out = save_drive(drive, folder, filename, wav, args.provider, digest, duration)
        post_comment("PRO-TTS-SAVED: " + args.provider + " | " + str(round(duration, 2))
                     + "s | private " + out["file"] + " | one request, no A2E or video")
        print("Success: private WAV read-back verified, seconds:", round(duration, 2))
    except HTTPError as ex:
        post_comment("PRO-TTS-FAILED: " + args.provider + " HTTP " + str(ex.code)
                     + ". No retry, check billing before any new call.")
        raise
    except Exception as ex:
        post_comment("PRO-TTS-FAILED: " + args.provider + " " + type(ex).__name__
                     + ". No retry, check billing before any new call.")
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print("Voice pilot stopped:", type(ex).__name__)
        raise SystemExit(1)
