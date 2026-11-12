#!/usr/bin/env python3
"""Opt-in canonical v2 audio-lock from already byte-verified owner audio.

Pure metadata transformation. Caller MUST first verify the existing approved
WAV/music bytes, voice Issue, explicit text/music selection and licence in
voice_music_writeback.build_candidate(). This module never reads Drive, starts
TTS, authorizes render, generates timestamps or changes owner approvals.
"""
from __future__ import annotations

import copy
import hashlib
import re

import handoff
import studio_audio_lock as lock_schema

SHA = re.compile(r"^[a-f0-9]{64}$")


class V2AudioLockError(ValueError):
    pass


def bind_verified_voice_music(project: dict, *,
                              approved_text_source_path: str,
                              approved_voice_text_sha256: str) -> dict:
    """Create a v2 lock only when exact canonical text = prior owner voice Issue.

    Existing v1 projects remain unchanged unless the caller explicitly requests
    this promotion and supplies the canonical approved script source path.
    """
    if not isinstance(project, dict):
        raise V2AudioLockError("V2_CANONICAL_PROJECT_MISSING")
    if (not isinstance(approved_text_source_path, str)
            or not approved_text_source_path
            or not isinstance(approved_voice_text_sha256, str)
            or not SHA.fullmatch(approved_voice_text_sha256)):
        raise V2AudioLockError("V2_APPROVED_TEXT_SOURCE_MISSING")
    sources = project.get("sources") or []
    pinned = [row for row in sources if isinstance(row, dict)
              and row.get("path") == approved_text_source_path
              and row.get("sha256") == approved_voice_text_sha256]
    if len(pinned) != 1:
        raise V2AudioLockError("V2_APPROVED_VOICE_TEXT_DIFFERS_FROM_CANONICAL_SOURCE")
    candidate = copy.deepcopy(project)
    records = candidate.get("stage_handoffs")
    stage = records.get("voice_music") if isinstance(records, dict) else None
    if not isinstance(stage, dict) or stage.get("state") != "completed":
        raise V2AudioLockError("V2_APPROVED_VOICE_MUSIC_STAGE_REQUIRED")
    if stage.get("schema") is not None or stage.get("audio_lock") is not None:
        raise V2AudioLockError("V2_AUDIO_LOCK_ALREADY_PRESENT")

    selected = stage.get("assets")
    assets = candidate.get("assets")
    if not isinstance(selected, list) or not isinstance(assets, list):
        raise V2AudioLockError("V2_APPROVED_ASSET_LIST_MISSING")

    def exact(kind: str) -> dict:
        matches = [item for item in assets if isinstance(item, dict)
                   and item.get("kind") == kind and item.get("id") in selected]
        if len(matches) != 1:
            raise V2AudioLockError("V2_SELECTED_AUDIO_ASSET_MISSING_OR_DUPLICATE")
        item = matches[0]
        sha = item.get("recorded_sha256")
        if (not isinstance(item.get("id"), str) or not isinstance(sha, str)
                or not SHA.fullmatch(sha) or item.get("state") != "available"):
            raise V2AudioLockError("V2_SELECTED_AUDIO_SHA_MISSING")
        if item.get("sha256") is not None and item["sha256"] != sha:
            raise V2AudioLockError("V2_AUDIO_SHA_FIELDS_DISAGREE")
        return {"asset_id": item["id"], "sha256": sha}

    music = exact("music")
    profile = stage.get("voice_profile")
    if profile == "simba_warmbaritone":
        mode, narration = "approved_wav", exact("narration")
    elif profile == "none":
        if any(a.get("kind") == "narration" and a.get("id") in selected for a in assets):
            raise V2AudioLockError("V2_UNAPPROVED_NARRATION_ASSET")
        mode, narration = "no_narration", None
    else:
        raise V2AudioLockError("V2_VOICE_PROFILE_UNSUPPORTED")
    evidence = stage.get("music_license_evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        raise V2AudioLockError("V2_LICENSE_EVIDENCE_REQUIRED")
    stage["schema"] = lock_schema.STAGE_SCHEMA
    audio_lock = {
        "schema": lock_schema.SCHEMA,
        "source_revision_sha256": handoff.source_fingerprint(candidate),
        "stage_input_fingerprint": stage.get("input_fingerprint"),
        "approved_text_source_path": approved_text_source_path,
        "approved_text_sha256": approved_voice_text_sha256,
        "voice_profile": profile,
        "mode": mode,
        "narration": narration,
        "music": music,
        "music_license_sha256": hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
    }
    audio_lock["audio_revision_sha256"] = lock_schema.revision_for(audio_lock)
    stage["audio_lock"] = audio_lock
    metadata = lock_schema.inspect_v2_audio(
        candidate, handoff.source_fingerprint(candidate))
    if metadata.get("status") != "VALID_METADATA":
        raise V2AudioLockError("V2_AUDIO_LOCK_VALIDATION_FAILED")

    # VALID_METADATA != WAV/word alignment or renderer authorization. Only the
    # independent Montage byte readback and Audio Engine can advance the gate.
    return candidate
