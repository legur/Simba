"""Owner-private, independent listening QA gate for the v2 approved WAV.

This module NEVER generates audio, runs WhisperX, infers word timestamps,
approves a render, or publishes. Its acceptance requires a separate
owner-authored *per-word* listening review file for the exact private acoustic
draft and the exact source-pinned approved WAV/text.

The explicit evidence is an owner attestation, not cryptographic proof that
a human listened. Runtime owner-only storage and manual review remain essential.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
MATERIALS = HERE.parent / "materials"
for folder in (str(HERE), str(MATERIALS)):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import catalog
import motionlab_audio_alignment_draft as acoustic
import motionlab_v2_audio_gate as audio_gate

DRAFT_FILE = "alignment-draft.json"
REVIEW_FILE = "alignment-listening-review.json"
SHA = re.compile(r"^[0-9a-f]{64}$")
REVIEW_SCHEMA = "bontours.montage.audio-listening-review/v1"
ALIGN_SCHEMA = "bontours.montage.audio-alignment/v1"
MAX_JSON = 160_000


class ListeningQAError(ValueError):
    pass


def reject(reason: str):
    raise ListeningQAError(reason)


def _read_private_json(directory: Path, name: str) -> tuple[bytes, dict]:
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        reject("PRIVATE_LISTENING_DIRECTORY_INVALID")
    root = root.resolve()
    target = root / name
    if (target.is_symlink() or not target.is_file()
            or target.resolve().parent != root):
        reject("PRIVATE_LISTENING_FILE_UNAVAILABLE")
    size = target.stat().st_size
    if not 2 <= size <= MAX_JSON:
        reject("PRIVATE_LISTENING_FILE_SIZE_INVALID")
    try:
        raw = target.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError):
        reject("PRIVATE_LISTENING_JSON_INVALID")
    if not isinstance(value, dict):
        reject("PRIVATE_LISTENING_JSON_INVALID")
    return raw, value


def private_review_presence(directory: Path) -> bool:
    root = Path(directory)
    draft = root / DRAFT_FILE
    review = root / REVIEW_FILE
    if not draft.exists() and not review.exists() and not draft.is_symlink() and not review.is_symlink():
        return False
    if (draft.is_symlink() or review.is_symlink()
            or not draft.is_file() or not review.is_file()):
        reject("V2_LISTENING_EVIDENCE_INCOMPLETE")
    return True


def _safe_text_source(project: dict, repository_root: Path) -> bytes:
    try:
        row = project["stage_handoffs"]["voice_music"]["audio_lock"]
        source_path = row["approved_text_source_path"]
        expected_sha = row["approved_text_sha256"]
        if not isinstance(source_path, str) or not SHA.fullmatch(expected_sha):
            reject("APPROVED_TEXT_SOURCE_LOCK_INVALID")
        target = catalog.inside(Path(repository_root).resolve(), source_path)
        if target.is_symlink() or not target.is_file() or target.stat().st_size > acoustic.MAX_TEXT_BYTES:
            reject("APPROVED_TEXT_SOURCE_UNAVAILABLE")
        raw = target.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha:
            reject("APPROVED_TEXT_SHA_CHANGED")
        return raw
    except (KeyError, TypeError, ValueError, OSError):
        reject("APPROVED_TEXT_SOURCE_UNAVAILABLE")


def _check_identity(document: dict, preflight: dict, source_sha: str):
    pairs = {"project_id": preflight["project_id"],
             "audio_revision_sha256": preflight["audio_revision_sha256"],
             "narration_sha256": preflight["narration_sha256"],
             "source_sha256": source_sha}
    if any(document.get(k) != v for k, v in pairs.items()):
        reject("LISTENING_QA_SOURCE_REVISION_MISMATCH")


def audit_review(preflight: dict, source: bytes, draft: dict, draft_raw: bytes,
                 review: dict, review_raw: bytes) -> tuple[dict, dict]:
    """Audit an *independently created* owner listening record (no auto-approval).

    Draft and review timestamps are not created here. The review must list each
    exact spoken word with actual manually confirmed/corrected time boundaries.
    """
    if (preflight.get("status") != "APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED"
            or preflight.get("narration_bytes_verified") is not True
            or preflight.get("music_bytes_verified") is not True
            or preflight.get("render_authorized") is not False):
        reject("APPROVED_WAV_AND_MUSIC_NOT_VERIFIED")
    text_sha = hashlib.sha256(source).hexdigest()
    if (draft.get("schema") != "bontours.montage.audio-alignment-draft/v1"
            or draft.get("status") != "DRAFT_ACOUSTIC_TIMINGS_REQUIRE_INDEPENDENT_LISTENING_QA"
            or draft.get("audio_alignment_verified") is not False
            or draft.get("render_authorized") is not False
            or draft.get("publication_authorized") is not False
            or draft.get("source_sha256") != text_sha):
        reject("ACOUSTIC_DRAFT_NOT_UNVERIFIED_OR_STALE")
    _check_identity(draft, preflight, text_sha)
    if review.get("schema") != REVIEW_SCHEMA:
        reject("LISTENING_QA_SCHEMA_INVALID")
    _check_identity(review, preflight, text_sha)
    if (review.get("draft_sha256") != hashlib.sha256(draft_raw).hexdigest()
            or not isinstance(review.get("reviewer"), str)
            or not re.fullmatch(r"owner:[A-Za-z0-9_-]{3,80}", review["reviewer"])
            or review.get("method") != "independent_manual_listening_against_original_wav"
            or review.get("every_word_listened") is not True
            or review.get("no_missing_spoken_words") is not True
            or review.get("no_render_or_publication_authorized") is not True
            or not isinstance(review.get("review_notes"), str)
            or len(review["review_notes"].strip()) < 30):
        reject("LISTENING_QA_OWNER_ATTESTATION_INCOMPLETE")
    try:
        approved = datetime.fromisoformat(review["reviewed_at_utc"].replace("Z", "+00:00"))
        if approved.tzinfo is None:
            raise ValueError()
        age = (datetime.now(timezone.utc) - approved.astimezone(timezone.utc)).total_seconds()
        if age < -300 or age > 30 * 86400:
            raise ValueError()
    except (ValueError, AttributeError, TypeError, KeyError):
        reject("LISTENING_QA_REVIEW_DATE_INVALID")
    try:
        expected = acoustic._script_lines(source.decode("utf-8"))
    except (UnicodeError, acoustic.AlignmentDraftError):
        reject("APPROVED_TEXT_UNREADABLE")
    lines = draft.get("lines")
    checks = review.get("line_reviews")
    if (not isinstance(lines, list) or not isinstance(checks, list)
            or len(lines) != len(expected) or len(checks) != len(expected)):
        reject("LISTENING_QA_LINE_COUNT_MISMATCH")
    verified_lines: list[dict] = []
    for original, acoustic_line, reviewed in zip(expected, lines, checks):
        if (not isinstance(acoustic_line, dict) or not isinstance(reviewed, dict)
                or acoustic_line.get("line_id") != original["line_id"]
                or reviewed.get("line_id") != original["line_id"]):
            reject("LISTENING_QA_LINE_ID_MISMATCH")
        predicted = acoustic_line.get("words")
        approved_words = reviewed.get("words")
        if (not isinstance(predicted, list) or not isinstance(approved_words, list)
                or len(predicted) != len(original["words"])
                or len(approved_words) != len(original["words"])):
            reject("LISTENING_QA_WORD_COUNT_MISMATCH")
        if (not isinstance(reviewed.get("listening_notes"), str)
                or len(reviewed["listening_notes"].strip()) < 15):
            reject("LISTENING_QA_LINE_NOT_REVIEWED")
        validated = []
        for text, proposed, confirmed in zip(original["words"], predicted, approved_words):
            if (not isinstance(proposed, dict) or not isinstance(confirmed, dict)
                    or proposed.get("text") != text or confirmed.get("text") != text
                    or confirmed.get("listened") is not True):
                reject("LISTENING_QA_WORD_NOT_REVIEWED")
            start = confirmed.get("word_start_ms")
            end = confirmed.get("word_end_ms")
            if type(start) is not int or type(end) is not int:
                reject("LISTENING_QA_WORD_TIME_INVALID")
            modified = (start != proposed.get("word_start_ms")
                        or end != proposed.get("word_end_ms"))
            if (modified and
                (not isinstance(confirmed.get("correction_note"), str)
                 or len(confirmed["correction_note"].strip()) < 10)):
                reject("LISTENING_QA_CORRECTION_NOT_EXPLAINED")
            validated.append({"text": text,
                              "word_start_ms": start,
                              "word_end_ms": end})
        verified_lines.append({
            "line_id": original["line_id"],
            "phrase_start_ms": validated[0]["word_start_ms"],
            "phrase_end_ms": validated[-1]["word_end_ms"],
            "words": validated
        })
    record = {
        "schema": ALIGN_SCHEMA,
        "project_id": preflight["project_id"],
        "source_sha256": text_sha,
        "audio_revision_sha256": preflight["audio_revision_sha256"],
        "narration_sha256": preflight["narration_sha256"],
        "status": "AUDIO_ALIGNMENT_VERIFIED",
        "method": "local_whisperx_ctc_plus_owner_manual_word_listening/v1",
        "qa_evidence_sha256": hashlib.sha256(review_raw).hexdigest(),
        "lines": verified_lines,
        "independent_audio_qa_completed": True,
        "render_authorized": False,
        "publication_authorized": False
    }
    # Authoritative structural cross-check; independently recorded listening
    # evidence is checked *above* (not automatically generated by this module).
    audio_gate.validate_alignment_evidence(preflight, record, expected)
    receipt = {
        "status": "AUDIO_ALIGNMENT_VERIFIED_BY_EXPLICIT_OWNER_LISTENING",
        "audio_revision_sha256": preflight["audio_revision_sha256"],
        "source_sha256": text_sha,
        "qa_evidence_sha256": record["qa_evidence_sha256"],
        "independent_audio_qa_completed": True,
        "word_count": sum(len(x["words"]) for x in verified_lines),
        "render_authorized": False,
        "paid_calls": 0,
        "publication_authorized": False
    }
    return record, receipt


def verify_owner_private_listening_qa(project: dict, private_dir: Path,
                                      repository_root: Path) -> tuple[dict, dict]:
    """Only call in an authenticated, owner-private existing v2 workflow."""
    if not private_review_presence(private_dir):
        reject("V2_LISTENING_EVIDENCE_MISSING")
    preflight = audio_gate.verify_private_audio_manifest(project, private_dir)
    source = _safe_text_source(project, repository_root)
    draft_raw, draft = _read_private_json(private_dir, DRAFT_FILE)
    review_raw, review = _read_private_json(private_dir, REVIEW_FILE)
    return audit_review(preflight, source, draft, draft_raw, review, review_raw)
