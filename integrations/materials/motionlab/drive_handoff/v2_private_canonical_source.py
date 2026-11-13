"""Owner-private canonical v2 source intake (read-only).

Accept source bytes only from an exact owner-private Google Drive folder/file,
with a SHA-256 supplied independently by the trusted owner worker. A previous
v1 archive or a v2 *candidate* is not a canonical project and is rejected.

This module deliberately does NOT issue v2 tickets, mark audio QA passed,
write GitHub project.json, render, or publish. No sensitive IDs in source.
"""
from __future__ import annotations

import hashlib
import json
import re

import v2_receipt_preflight as private

MAX_PROJECT_BYTES = 300_000
PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class PrivateCanonicalError(ValueError):
    pass


def require(condition: bool, reason: str):
    if not condition:
        raise PrivateCanonicalError(reason)


def verify_private_folder(svc, folder_id: str):
    """Both folder and file must have exclusively user permissions."""
    require(isinstance(folder_id, str) and private.IDENTIFIER.fullmatch(folder_id),
            "V2_PRIVATE_CANONICAL_FOLDER_ID_INVALID")
    try:
        info = svc.files().get(fileId=folder_id,
            fields="id,mimeType,trashed").execute()
        perms = svc.permissions().list(fileId=folder_id,
            fields="nextPageToken,permissions(type,role)",pageSize=100).execute()
    except Exception:
        raise PrivateCanonicalError("V2_PRIVATE_CANONICAL_FOLDER_UNAVAILABLE") from None
    require(info.get("id", folder_id) == folder_id
            and info.get("mimeType") == "application/vnd.google-apps.folder"
            and info.get("trashed") is False
            and not perms.get("nextPageToken")
            and isinstance(perms.get("permissions"), list)
            and len(perms["permissions"]) == 1
            and perms["permissions"][0].get("type") == "user"
            and perms["permissions"][0].get("role") == "owner",
            "V2_PRIVATE_CANONICAL_FOLDER_ACL_UNTRUSTED")


def check_canonical_shape(document: object, project_id: str) -> None:
    """Admission-only checks, NOT a substitute for media/audio replay."""
    require(isinstance(project_id, str) and PROJECT_ID.fullmatch(project_id),
            "V2_PRIVATE_CANONICAL_PROJECT_ID_INVALID")
    require(isinstance(document, dict) and document.get("id") == project_id,
            "V2_PRIVATE_CANONICAL_PROJECT_MISMATCH")
    # Historical archive evidence is NOT a new v2 voice_music approval.
    for key in ("private_staging_status", "archive_provenance", "missing"):
        require(key not in document, "V2_PRIVATE_CANONICAL_CANDIDATE_NOT_APPROVED")
    handoffs = document.get("stage_handoffs")
    require(isinstance(handoffs, dict) and "edit_choice" not in handoffs,
            "V2_PRIVATE_CANONICAL_STAGE_INVALID")
    audio = handoffs.get("voice_music")
    require(isinstance(audio, dict)
            and audio.get("state") == "completed"
            and isinstance(audio.get("audio_lock"), dict)
            and isinstance(audio["audio_lock"].get("audio_revision_sha256"), str)
            and private.SHA.fullmatch(audio["audio_lock"]["audio_revision_sha256"]),
            "V2_PRIVATE_CANONICAL_AUDIO_LOCK_REQUIRED")
    approved = handoffs.get("a2e_clips")
    approved_ids = approved.get("assets") if isinstance(approved, dict) else None
    require(isinstance(approved_ids, list)
            and 1 <= len(approved_ids) <= 12
            and all(isinstance(value, str) and value for value in approved_ids)
            and len(approved_ids) == len(set(approved_ids)),
            "V2_PRIVATE_CANONICAL_A2E_APPROVAL_REQUIRED")
    assets = document.get("assets")
    require(isinstance(assets, list) and len(assets) >= len(approved_ids)
            and isinstance(document.get("sources"), list),
            "V2_PRIVATE_CANONICAL_STRUCTURE_INVALID")
    ids = {a.get("id") for a in assets if isinstance(a, dict)
           and isinstance(a.get("id"), str)}
    require(all(aid in ids for aid in approved_ids),
            "V2_PRIVATE_CANONICAL_A2E_SOURCE_MISSING")
    require(document.get("stage") not in
            (None, "ARCHIVED_SOURCE_AND_SCRIPT_APPROVED__V2_AUDIO_QA_BLOCKED"),
            "V2_PRIVATE_CANONICAL_STAGE_INVALID")


def inspect_private_canonical(svc, *, folder_id: str, file_id: str,
                              project_id: str, expected_sha256: str) -> dict:
    """Authenticated, pinned read. Returns no raw private content/IDs.

    expected_sha256 MUST come from independent owner-controlled provenance.
    Later voice/music, MP4, offline ASR and edit-choice gates remain mandatory.
    """
    require(isinstance(expected_sha256, str)
            and private.SHA.fullmatch(expected_sha256),
            "V2_PRIVATE_CANONICAL_EXPECTED_SHA_REQUIRED")
    verify_private_folder(svc, folder_id)
    # A user-only share with a second named user is not *owner-private*.
    # Check the FILE as well, before any content download.
    try:
        perms = svc.permissions().list(fileId=file_id,
            fields="nextPageToken,permissions(type,role)",pageSize=100).execute()
    except Exception:
        raise PrivateCanonicalError("V2_PRIVATE_CANONICAL_FILE_ACL_UNAVAILABLE") from None
    require(not perms.get("nextPageToken")
            and isinstance(perms.get("permissions"), list)
            and len(perms["permissions"]) == 1
            and perms["permissions"][0].get("type") == "user"
            and perms["permissions"][0].get("role") == "owner",
            "V2_PRIVATE_CANONICAL_FILE_ACL_UNTRUSTED")
    try:
        raw = private.secure_private_bytes(svc, file_id, folder_id,
            MAX_PROJECT_BYTES, mime={"application/json"}, filename="project.json")
    except private.V2InboxError:
        raise PrivateCanonicalError("V2_PRIVATE_CANONICAL_FILE_NOT_TRUSTED") from None
    actual_sha = hashlib.sha256(raw).hexdigest()
    require(actual_sha == expected_sha256,
            "V2_PRIVATE_CANONICAL_SHA_MISMATCH")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise PrivateCanonicalError("V2_PRIVATE_CANONICAL_JSON_INVALID") from None
    check_canonical_shape(doc, project_id)
    return {
        "status": "V2_OWNER_PRIVATE_CANONICAL_BYTES_PINNED_NOT_APPLIED",
        "project_id": project_id,
        "source_sha256": actual_sha,
        "canonical_applied": False,
        "audio_alignment_verified": False,
        "render_authorized": False,
        "published": False,
        "paid_calls": 0,
    }
