#!/usr/bin/env python3
"""Studio v2 canonical *metadata* lock for user-approved narration and music.

Read-only. It never accesses the private Drive or asserts that registered
SHA-256 values match external bytes. Only Montage's trusted read-back and
audio alignment can complete the production proof.

Older projects without audio_lock remain valid in the legacy v1 handoff;
v2 callers MUST use inspect_v2_audio() and reject any non-VALID_METADATA result.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA = "bontours.studio.approved-audio-lock/v1"
STAGE_SCHEMA = "bontours.studio.voice-music/v2"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
MODES = {"approved_wav", "approved_clip_audio", "no_narration"}
FIELDS = frozenset({
    "schema", "source_revision_sha256", "stage_input_fingerprint",
    "approved_text_source_path", "approved_text_sha256", "voice_profile",
    "mode", "narration", "music", "music_license_sha256",
    "audio_revision_sha256",
})
ASSET_FIELDS = frozenset({"asset_id", "sha256"})


def canonical_sha256(value: object) -> str:
    """Stable canonical JSON: sorted keys, UTF-8, no float-dependent encoding."""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def revision_for(lock: dict) -> str:
    """Digest of all fixed lock fields, excluding the digest itself."""
    return canonical_sha256({key: value for key, value in lock.items()
                             if key != "audio_revision_sha256"})


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256.fullmatch(value))


def _id(value: object) -> bool:
    return isinstance(value, str) and bool(IDENTIFIER.fullmatch(value))


def _recorded_asset(project: dict, record: dict, item: object, kind: str,
                    issues: list[str], prefix: str) -> None:
    if not isinstance(item, dict) or set(item) != ASSET_FIELDS:
        issues.append(prefix + ": expected exactly asset_id and sha256")
        return
    asset_id = item.get("asset_id")
    locked_sha = item.get("sha256")
    if not _id(asset_id) or not _sha(locked_sha):
        issues.append(prefix + ": invalid asset identifier or full lowercase SHA-256")
        return
    if asset_id not in record.get("assets", []):
        issues.append(prefix + ": asset not selected in approved voice_music stage")
    matches = [asset for asset in project.get("assets", []) if asset.get("id") == asset_id]
    if len(matches) != 1:
        issues.append(prefix + ": asset missing or duplicated in canonical project")
    else:
        asset = matches[0]
        if asset.get("kind") != kind or asset.get("state") != "available":
            issues.append(prefix + ": wrong kind or unavailable asset")
        if not _sha(asset.get("sha256")) or asset["sha256"] != locked_sha:
            issues.append(prefix + ": asset metadata SHA-256 missing or different from lock")


def validate(project: dict, record: dict, source_revision: str) -> list[str]:
    """Validate a locked voice_music stage without fetching external media.

    The returned diagnostics are safe to log (no URLs, tokens, source bodies,
    user text, or voice IDs). Fail closed on absent/ambiguous/changed metadata.
    """
    issues: list[str] = []
    lock = record.get("audio_lock")
    if not isinstance(lock, dict):
        return ["audio_lock: canonical lock required for Studio v2"]
    if set(lock) != FIELDS:
        issues.append("audio_lock: unexpected or missing schema fields")
    if lock.get("schema") != SCHEMA:
        issues.append("audio_lock: schema mismatch")
    if not _sha(source_revision) or lock.get("source_revision_sha256") != source_revision:
        issues.append("audio_lock: stale canonical source revision")
    if not _sha(record.get("input_fingerprint")) or (
        lock.get("stage_input_fingerprint") != record.get("input_fingerprint")
    ):
        issues.append("audio_lock: upstream stage fingerprint changed")
    approved_path = lock.get("approved_text_source_path")
    approved_sha = lock.get("approved_text_sha256")
    sources = project.get("sources", [])
    if not isinstance(approved_path, str) or not approved_path or not _sha(approved_sha):
        issues.append("audio_lock: approved-text source path / SHA invalid")
    elif sum(1 for item in sources
             if item.get("path") == approved_path and item.get("sha256") == approved_sha) != 1:
        issues.append("audio_lock: approved-text source not pinned to canonical project")
    if lock.get("voice_profile") != record.get("voice_profile"):
        issues.append("audio_lock: voice profile does not match approved stage")
    mode = lock.get("mode")
    if not isinstance(mode, str) or mode not in MODES:
        issues.append("audio_lock: unsupported narration mode")
    if mode == "approved_wav":
        if record.get("voice_profile") != "simba_warmbaritone":
            issues.append("audio_lock: approved WAV requires approved voice profile")
        _recorded_asset(project, record, lock.get("narration"), "narration",
                        issues, "audio_lock.narration")
    elif mode == "approved_clip_audio":
        if record.get("voice_profile") != "none":
            issues.append("audio_lock: clip audio must not authorize additional TTS")
        _recorded_asset(project, record, lock.get("narration"), "animated_clip",
                        issues, "audio_lock.narration")
    elif mode == "no_narration" and lock.get("narration") is not None:
        issues.append("audio_lock: narration must be null when no narration approved")
    if mode == "no_narration" and record.get("voice_profile") != "none":
        issues.append("audio_lock: no-narration mode conflicts with voice profile")
    _recorded_asset(project, record, lock.get("music"), "music",
                    issues, "audio_lock.music")
    evidence = record.get("music_license_evidence")
    if not isinstance(evidence, str) or not evidence.strip() or (
        lock.get("music_license_sha256") != hashlib.sha256(evidence.encode("utf-8")).hexdigest()
    ):
        issues.append("audio_lock: music license evidence changed")
    if not _sha(lock.get("audio_revision_sha256")) or (
        lock.get("audio_revision_sha256") != revision_for(lock)
    ):
        issues.append("audio_lock: canonical audio revision digest mismatch")
    return issues


def inspect_v2_audio(project: dict, source_revision: str) -> dict[str, Any]:
    """Produce redacted, read-only preflight for a trusted Montage receiver.

    VALID_METADATA intentionally never implies byte-readback or render approval.
    """
    stage_handoffs = project.get("stage_handoffs")
    record = stage_handoffs.get("voice_music") if isinstance(stage_handoffs, dict) else None
    if not isinstance(record, dict) or record.get("state") != "completed":
        return _blocked("VOICE_MUSIC_NOT_APPROVED")
    if record.get("schema") != STAGE_SCHEMA:
        return _blocked("V2_VOICE_MUSIC_SCHEMA_REQUIRED")
    issues = validate(project, record, source_revision)
    if issues:
        return _blocked("V2_CANONICAL_AUDIO_NOT_VERIFIED", issues)
    lock = record["audio_lock"]
    return {
        "status": "VALID_METADATA",
        "reason": "EXTERNAL_AUDIO_BYTES_NOT_VERIFIED",
        "schema": SCHEMA,
        "source_revision_sha256": source_revision,
        "audio_revision_sha256": lock["audio_revision_sha256"],
        "narration_asset_id": (lock["narration"] or {}).get("asset_id"),
        "music_asset_id": lock["music"]["asset_id"],
        "external_media_verified": False,
        "audio_alignment_verified": False,
        "render_authorized": False,
        "paid_operations_authorized": False,
        "publication_authorized": False,
        "issues": [],
    }


def _blocked(reason: str, issues: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": "BLOCKED", "reason": reason,
        "external_media_verified": False,
        "audio_alignment_verified": False,
        "render_authorized": False, "paid_operations_authorized": False,
        "publication_authorized": False, "issues": issues or [],
    }
