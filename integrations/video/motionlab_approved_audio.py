"""Zero-paid private verification of an existing approved Simba WAV source.

The voice/music stage stores the real narration WAV in private Google Drive.
This module verifies an operator-staged *copy* outside the repository against
its canonical voice_music asset. It does not synthesize speech, edit audio,
guess word timings, authorize render, or certify the music license.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import wave

_SHA = re.compile(r"^[a-f0-9]{64}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.wav$")
_MAX_BYTES = 60 * 1024 * 1024


class AudioSourceError(ValueError):
    pass


def _reject(message: str):
    raise AudioSourceError(message)


def verify_approved_narration(project: dict, private_job: Path,
                              wav_name: str) -> dict:
    """Return a bounded, non-sensitive source receipt, never render approval.

    The owner is responsible for downloading the exact WAV from private Drive.
    Its fingerprint and metadata must already exist in canonical project.json.
    Only this direct source check is performed: transcription, split per-line
    timing, end/offer synchronization and mix/music QA remain separate gates.
    """
    if not isinstance(project, dict) or not isinstance(project.get("assets"), list):
        _reject("CANONICAL_PROJECT_REQUIRED")
    stages = project.get("stage_handoffs")
    stage = stages.get("voice_music") if isinstance(stages, dict) else None
    if not isinstance(stage, dict) or stage.get("state") != "completed":
        _reject("VOICE_MUSIC_HANDOFF_NOT_COMPLETE")
    ids = stage.get("assets")
    if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
        _reject("VOICE_MUSIC_ASSET_BINDING_INVALID")
    matches = [x for x in project["assets"]
               if isinstance(x, dict) and x.get("kind") == "narration"
               and x.get("id") in ids]
    if len(matches) != 1:
        _reject("EXACTLY_ONE_APPROVED_NARRATION_REQUIRED")
    asset = matches[0]
    asset_id = asset.get("id")
    sha = asset.get("recorded_sha256")
    size = asset.get("recorded_size_bytes")
    duration = asset.get("recorded_duration_seconds")
    if (not isinstance(asset_id, str) or not asset_id.startswith("narration-")
            or not isinstance(sha, str) or not _SHA.fullmatch(sha)
            or asset_id != "narration-" + sha[:24]
            or type(size) is not int or not 4096 <= size <= _MAX_BYTES
            or type(duration) not in (float, int)
            or not 0.3 <= duration <= 120):
        _reject("APPROVED_NARRATION_METADATA_INVALID")
    if (not isinstance(wav_name, str) or not _SAFE_NAME.fullmatch(wav_name)
            or wav_name in {".", ".."}):
        _reject("UNSAFE_NARRATION_FILENAME")
    root = Path(private_job)
    if root.is_symlink() or not root.is_dir():
        _reject("PRIVATE_AUDIO_FOLDER_INVALID")
    file = root / wav_name
    if file.is_symlink() or not file.is_file() or file.resolve().parent != root.resolve():
        _reject("PRIVATE_NARRATION_UNAVAILABLE")
    if file.stat().st_size != size:
        _reject("APPROVED_NARRATION_SIZE_MISMATCH")
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    if digest.hexdigest() != sha:
        _reject("APPROVED_NARRATION_SHA256_MISMATCH")
    try:
        with wave.open(str(file), "rb") as reader:
            if (reader.getnchannels() not in (1, 2)
                    or reader.getsampwidth() != 2
                    or reader.getframerate() != 24000
                    or reader.getcomptype() != "NONE"):
                _reject("APPROVED_NARRATION_FORMAT_INVALID")
            actual_duration = reader.getnframes() / reader.getframerate()
            if not 0.3 <= actual_duration <= 120:
                _reject("APPROVED_NARRATION_DURATION_INVALID")
            if abs(actual_duration - duration) > 0.15:
                _reject("APPROVED_NARRATION_DURATION_MISMATCH")
    except (EOFError, wave.Error, OSError):
        _reject("APPROVED_NARRATION_WAV_CORRUPT")
    return {
        "status": "EXISTING_APPROVED_WAV_SOURCE_VERIFIED_NOT_RENDER_READY",
        "asset_id": asset_id,
        "sha256": sha,
        "duration_seconds": round(actual_duration, 3),
        "bytes": size,
        "preapproved_wav_source_verified": True,
        "per_line_timing_verified": False,
        "music_source_verified": False,
        "mix_verified": False,
        "full_timeline_verified": False,
        "render_authorized": False,
        "paid_calls": 0,
    }
