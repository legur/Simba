#!/usr/bin/env python3
"""Run the approved voice from a hash-addressed private Drive request."""
import argparse
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import re

import github_secret_job as store
import simba_voice

MAX_REQUEST_BYTES = 8192
MAX_OUTPUT_TOKENS_PER_PART = 1400


def request_digest(event, env):
    inputs = event.get("inputs") or {}
    digest = inputs.get("request_sha256")
    if (env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or (event.get("repository") or {}).get("full_name") != "legur/Simba"
            or (event.get("sender") or {}).get("login") != "legur"
            or set(inputs) != {"request_sha256"}
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise ValueError("Invalid private voice dispatch")
    return digest


def parse_request(body, digest):
    if not isinstance(body, bytes) or not 0 < len(body) <= MAX_REQUEST_BYTES:
        raise ValueError("Invalid private request size")
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("Private request hash mismatch")
    data = json.loads(body)
    if (not isinstance(data, dict) or set(data) != {"kind", "parts"}
            or data["kind"] != "simba_approved_voice"):
        raise ValueError("Invalid private voice request")
    parts = data["parts"]
    if (not isinstance(parts, list) or not 1 <= len(parts) <= 2
            or any(not isinstance(part, str) or not part.strip() or len(part) > 450
                   for part in parts)
            or len(set(parts)) != len(parts)):
        raise ValueError("Expected one or two distinct parts of up to 450 characters")
    return parts


def read_private_request(drive, digest):
    name = f"simba-voice-request-{digest}.json"
    matches = store._drive_list_all(drive, f"name = '{name}' and trashed = false")
    if len(matches) != 1:
        raise store.JobError("Exactly one matching private Drive request is required")
    file_id = store.validate_drive_id(matches[0]["id"])
    item = store._get_drive_item(drive, file_id)
    store._assert_private(item)
    parents = item.get("parents") or []
    size = item.get("size", "")
    if (item.get("name") != name or item.get("mimeType") != "application/json"
            or len(parents) != 1 or not str(size).isdigit() or not 0 < int(size) <= MAX_REQUEST_BYTES
            or (item.get("capabilities") or {}).get("canDownload") is not True):
        raise store.JobError("Private voice request metadata is invalid")
    folder = store.validate_drive_id(parents[0])
    store.validate_destination(drive, folder)
    try:
        body = drive.files().get_media(fileId=file_id).execute(num_retries=0)
    except Exception:
        raise store.JobError("Private voice request download failed") from None
    if not isinstance(body, bytes) or len(body) != int(size):
        raise store.JobError("Private voice request byte count mismatch")
    return folder, parse_request(body, digest)


def upload_voice(drive, folder, name, audio, marker):
    from googleapiclient.http import MediaFileUpload

    try:
        item = drive.files().create(
            body={"name": name, "parents": [folder], "mimeType": "audio/wav",
                  "appProperties": {"simba_render_marker_id": marker["id"]}},
            media_body=MediaFileUpload(str(audio), mimetype="audio/wav", resumable=True),
            fields="id",
        ).execute(num_retries=0)
        observed = store._get_drive_item(drive, item["id"])
        store._assert_private(observed, expected_parent=folder)
        if (observed.get("name") != name or observed.get("mimeType") != "audio/wav"
                or observed.get("size") != str(audio.stat().st_size)):
            raise store.JobError("Voice upload read-back failed")
    except Exception:
        raise store.JobError("Voice upload uncertain; inspect private Drive before retrying") from None


def run(event, workdir):
    simba_voice._require_github_secrets_workflow()
    digest = request_digest(event, os.environ)
    store.require_secret_environment(os.environ)
    drive = store.oauth_drive_client(os.environ)
    folder, parts = read_private_request(drive, digest)
    jobs = []
    for index, part in enumerate(parts, 1):
        name = f"simba-voice-{digest}-part-{index}.wav"
        replay_key = hashlib.sha256(part.encode("utf-8")).hexdigest()
        if store._drive_matches(drive, folder, name):
            raise store.ReplayBlocked("Verified or possible output exists; inspect private Drive")
        store.ensure_no_global_marker(drive, replay_key)
        jobs.append((name, replay_key, part))
    voice_id = simba_voice.voice_id_from_private_store()
    generate = partial(simba_voice._generate_once, max_output_tokens=MAX_OUTPUT_TOKENS_PER_PART)
    for name, replay_key, part in jobs:
        marker = store.create_attempt_marker(drive, folder, replay_key, os.environ)
        audio = simba_voice.synthesize_lines(
            [{"id": "narration", "text": part}], workdir / "cache",
            voice_id=voice_id, generate=generate, allow_fallback=False,
        )["narration"]
        upload_voice(drive, folder, name, audio, marker)
    return len(jobs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        count = run(json.loads(args.event.read_text(encoding="utf-8")), args.out)
    except Exception:
        # Public Actions logs must not disclose request data or Drive identifiers.
        print("Voice stopped. Inspect private Drive markers before any retry.")
        return 1
    print(f"Completed: {count} PCM WAV part(s) verified in private Drive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
