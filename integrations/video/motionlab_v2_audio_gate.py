"""Montage v2: private approved audio byte read-back and timing-evidence gate.

One owner-controlled directory containing approved.wav and approved music.
No TTS, ASR, downloads, synthesis, rendering or automatic authorization.
The Studio audio-lock metadata contract is imported from the *Studio* module;
no duplicate implementation of its schema is permitted.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import sys
import wave

HERE = Path(__file__).resolve().parent
MATERIALS = HERE.parent / "materials"
if str(MATERIALS) not in sys.path:
    sys.path.insert(0, str(MATERIALS))
import studio_audio_lock  # Studio owns this contract, PR #127
import handoff

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$")
MAX_SOURCE_BYTES = 100 * 1024 * 1024


class AudioGateError(ValueError):
    pass


def _fail(code: str):
    raise AudioGateError(code)


def _safe_file(directory: Path, filename: str) -> Path:
    if not isinstance(filename, str) or not SAFE_NAME.fullmatch(filename):
        _fail("UNSAFE_AUDIO_FILENAME")
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        _fail("PRIVATE_AUDIO_DIRECTORY_INVALID")
    path = root / filename
    if path.is_symlink() or not path.is_file() or path.resolve().parent != root.resolve():
        _fail("PRIVATE_AUDIO_FILE_UNAVAILABLE")
    if not 4096 <= path.stat().st_size <= MAX_SOURCE_BYTES:
        _fail("AUDIO_FILE_SIZE_INVALID")
    return path


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def verify_private_audio_lock(project: dict, private_dir: Path, *,
                              narration_name: str | None,
                              music_name: str) -> dict:
    """Check Studio metadata and actual trusted WAV/music bytes, still not render approval.

    Invoke only after loading a canonical project from a trusted checkout.
    Audio lock data are only accepted from canonical completed voice_music stage;
    browser JSON cannot supply or override either SHA.
    """
    if not isinstance(project, dict) or not isinstance(project.get("id"), str):
        _fail("CANONICAL_PROJECT_INVALID")
    try:
        revision = handoff.source_fingerprint(project)
        metadata = studio_audio_lock.inspect_v2_audio(project, revision)
    except (KeyError, TypeError, ValueError):
        _fail("STUDIO_AUDIO_LOCK_INVALID")
    if metadata.get("status") != "VALID_METADATA":
        _fail("STUDIO_AUDIO_LOCK_NOT_VERIFIED")
    stage = project["stage_handoffs"]["voice_music"]
    lock = stage["audio_lock"]
    mode = lock["mode"]
    if mode == "approved_clip_audio":
        _fail("APPROVED_CLIP_AUDIO_NEEDS_EXPLICIT_CLIP_GATE")
    if mode == "no_narration" and narration_name is not None:
        _fail("UNAPPROVED_NARRATION_PRESENT")
    if mode == "approved_wav" and narration_name is None:
        _fail("APPROVED_NARRATION_FILE_REQUIRED")
    music_path = _safe_file(private_dir, music_name)
    if _sha_file(music_path) != lock["music"]["sha256"]:
        _fail("APPROVED_MUSIC_SHA256_MISMATCH")
    result = {
        "schema": "bontours.montage.private-audio-preflight/v1",
        "status": "APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED",
        "project_id": project["id"],
        "source_revision_sha256": revision,
        "audio_revision_sha256": lock["audio_revision_sha256"],
        "music_asset_id": lock["music"]["asset_id"],
        "music_sha256": lock["music"]["sha256"],
        "music_bytes_verified": True,
        "narration_bytes_verified": mode == "no_narration",
        "audio_alignment_verified": False,
        "render_authorized": False,
        "paid_calls": 0,
    }
    if mode == "approved_wav":
        path = _safe_file(private_dir, narration_name)
        if path.suffix.lower() != ".wav":
            _fail("APPROVED_NARRATION_NOT_WAV")
        if _sha_file(path) != lock["narration"]["sha256"]:
            _fail("APPROVED_NARRATION_SHA256_MISMATCH")
        try:
            with wave.open(str(path), "rb") as src:
                if (src.getnchannels() not in (1, 2)
                    or src.getsampwidth() != 2
                    or src.getframerate() != 24000
                    or src.getcomptype() != "NONE"):
                    _fail("APPROVED_NARRATION_FORMAT_INVALID")
                duration_ms = round(src.getnframes() * 1000 / 24000)
        except (EOFError, wave.Error, OSError):
            _fail("APPROVED_NARRATION_WAV_CORRUPT")
        if not 300 <= duration_ms <= 120000:
            _fail("APPROVED_NARRATION_DURATION_INVALID")
        result.update(narration_asset_id=lock["narration"]["asset_id"],
                      narration_sha256=lock["narration"]["sha256"],
                      narration_duration_ms=duration_ms,
                      narration_bytes_verified=True)
    return result


def validate_alignment_evidence(preflight: dict, alignment: dict, expected_lines: list[dict]) -> dict:
    """Validate independent actual word-alignment evidence; never manufacture timings.

    This gate checks structural consistency and source/revision binding. It
    cannot establish ASR transcription accuracy; independent audio QA evidence
    and a real aligner are required before production use.
    """
    if preflight.get("status") != "APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED":
        _fail("AUDIO_BYTES_NOT_VERIFIED")
    if not preflight.get("narration_bytes_verified") or not preflight.get("music_bytes_verified"):
        _fail("AUDIO_BYTES_NOT_VERIFIED")
    if not isinstance(alignment, dict) or alignment.get("schema") != "bontours.montage.audio-alignment/v1":
        _fail("AUDIO_ALIGNMENT_SCHEMA_INVALID")
    for key in ("audio_revision_sha256", "narration_sha256", "project_id"):
        expected = preflight["narration_sha256"] if key == "narration_sha256" else preflight[key]
        if alignment.get(key) != expected:
            _fail("AUDIO_ALIGNMENT_REVISION_STALE")
    if alignment.get("status") != "AUDIO_ALIGNMENT_VERIFIED":
        _fail("AUDIO_ALIGNMENT_QA_NOT_VERIFIED")
    if not isinstance(alignment.get("method"), str) or not alignment["method"].strip():
        _fail("AUDIO_ALIGNMENT_METHOD_MISSING")
    if not isinstance(alignment.get("qa_evidence_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}",alignment["qa_evidence_sha256"]):
        _fail("AUDIO_ALIGNMENT_QA_EVIDENCE_MISSING")
    lines = alignment.get("lines")
    if not isinstance(lines, list) or not lines or len(lines) != len(expected_lines):
        _fail("AUDIO_ALIGNMENT_LINES_MISMATCH")
    duration = preflight["narration_duration_ms"]
    last_phrase_end = 0
    for actual, expected in zip(lines, expected_lines):
        if not isinstance(actual, dict) or not isinstance(expected, dict):
            _fail("AUDIO_ALIGNMENT_LINES_MISMATCH")
        if actual.get("line_id") != expected.get("line_id"):
            _fail("AUDIO_ALIGNMENT_LINE_ID_MISMATCH")
        if not isinstance(expected.get("words"), list) or not expected["words"]:
            _fail("APPROVED_WORDS_REQUIRED")
        pstart, pend = actual.get("phrase_start_ms"), actual.get("phrase_end_ms")
        if (type(pstart) is not int or type(pend) is not int
                or not last_phrase_end <= pstart < pend <= duration):
            _fail("AUDIO_ALIGNMENT_PHRASE_TIMES_INVALID")
        words = actual.get("words")
        if not isinstance(words, list) or len(words) != len(expected["words"]):
            _fail("AUDIO_ALIGNMENT_WORD_COUNT_MISMATCH")
        previous = pstart
        for word, expected_word in zip(words, expected["words"]):
            if not isinstance(word, dict) or word.get("text") != expected_word:
                _fail("AUDIO_ALIGNMENT_WORD_TEXT_MISMATCH")
            start, end = word.get("word_start_ms"), word.get("word_end_ms")
            if (type(start) is not int or type(end) is not int
                    or not previous <= start < end <= pend):
                _fail("AUDIO_ALIGNMENT_WORD_TIMES_INVALID")
            previous = end
        last_phrase_end = pend
    return {
        "status": "ALIGNMENT_METADATA_CONSISTENT_NEEDS_INDEPENDENT_AUDIO_QA",
        "audio_revision_sha256": preflight["audio_revision_sha256"],
        "narration_sha256": preflight["narration_sha256"],
        "line_count": len(lines),
        "independent_audio_qa_completed": False,
        "render_authorized": False,
        "paid_calls": 0,
    }
