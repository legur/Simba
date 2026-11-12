#!/usr/bin/env python3
"""Private, source-pinned Russian word-alignment DRAFT from an approved WAV.

Uses a local WhisperX CTC alignment model only on explicit owner CLI invocation.
Never calls commercial TTS/A2E services, uploads audio to a transcription API,
writes to git, creates a trusted QA receipt or authorizes render/publishing.

The acoustic model may mishear words/numbers and interpolate timestamps:
even an accepted draft ALWAYS requires independent listening/QA before v2
can claim AUDIO_ALIGNMENT_VERIFIED. Do not auto-promote this draft.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import unicodedata

VIDEO = Path(__file__).resolve().parent
MATERIALS = VIDEO.parent / "materials"
for folder in (str(VIDEO), str(MATERIALS)):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import catalog
import handoff
import motionlab_v2_audio_gate as audio_gate
import studio_audio_lock as studio_lock

SHA = re.compile(r"^[0-9a-f]{64}$")
WORD = re.compile(r"[^\W_]+(?:[-’'][^\W_]+)*", re.UNICODE)
LANGUAGES = {"ru", "en", "he"}
MAX_TEXT_BYTES = 100_000
MAX_WORDS = 1500
MAX_LINES = 120


class AlignmentDraftError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(code: str):
    raise AlignmentDraftError(code)


def _words(text: str) -> list[str]:
    value = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    return WORD.findall(value)


def _script_lines(source: str) -> list[dict]:
    if not isinstance(source, str) or not source.strip():
        _fail("APPROVED_TEXT_EMPTY")
    lines = []
    for row in source.splitlines():
        text = row.strip()
        if not text:
            continue
        words = _words(text)
        if not words:
            _fail("APPROVED_TEXT_LINE_NOT_SPOKEN")
        lines.append({"line_id": f"line-{len(lines) + 1:02d}",
                      "words": words})
    if not 1 <= len(lines) <= MAX_LINES:
        _fail("APPROVED_TEXT_LINE_COUNT")
    if sum(len(x["words"]) for x in lines) > MAX_WORDS:
        _fail("APPROVED_TEXT_TOO_LONG")
    return lines


def validate_acoustic_draft(preflight: dict, source_bytes: bytes,
                            expected_text_sha256: str, aligned: dict, *,
                            language: str = "ru",
                            method: str = "whisperx-ctc-local") -> dict:
    """Validate actual aligner word output without guessing missing timings.

    A returned draft is NOT production verified timing. The caller must run an
    independent listening review and a separate trusted promotion workflow.
    """
    if language not in LANGUAGES:
        _fail("AUDIO_ALIGNMENT_LANGUAGE_UNSUPPORTED")
    if (not isinstance(preflight, dict)
            or preflight.get("status") != "APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED"
            or preflight.get("narration_bytes_verified") is not True
            or preflight.get("music_bytes_verified") is not True
            or preflight.get("render_authorized") is not False):
        _fail("PRIVATE_APPROVED_AUDIO_NOT_VERIFIED")
    if not isinstance(source_bytes, bytes) or not 1 <= len(source_bytes) <= MAX_TEXT_BYTES:
        _fail("APPROVED_TEXT_SIZE_INVALID")
    if not isinstance(expected_text_sha256, str) or not SHA.fullmatch(expected_text_sha256):
        _fail("APPROVED_TEXT_SHA_INVALID")
    if hashlib.sha256(source_bytes).hexdigest() != expected_text_sha256:
        _fail("APPROVED_TEXT_BYTES_MISMATCH")
    for key in ("audio_revision_sha256", "narration_sha256", "project_id"):
        value = preflight.get(key)
        if not isinstance(value, str) or (
                key != "project_id" and not SHA.fullmatch(value)):
            _fail("PRIVATE_AUDIO_REVISION_INVALID")
    duration = preflight.get("narration_duration_ms")
    if type(duration) is not int or not 300 <= duration <= 120000:
        _fail("APPROVED_WAV_DURATION_INVALID")
    try:
        content = source_bytes.decode("utf-8")
    except UnicodeError:
        _fail("APPROVED_TEXT_NOT_UTF8")
    lines = _script_lines(content)
    words = [w for l in lines for w in l["words"]]
    row = aligned.get("word_segments") if isinstance(aligned, dict) else None
    if not isinstance(row, list) or len(row) != len(words):
        _fail("ACOUSTIC_WORD_COUNT_MISMATCH")
    if not isinstance(method, str) or not method.startswith("whisperx-ctc-"):
        _fail("ACOUSTIC_METHOD_MISSING")
    verified_spans = []
    previous_end = 0
    for index, (expected_word, actual) in enumerate(zip(words, row)):
        if not isinstance(actual, dict) or _words(str(actual.get("word", ""))) != [expected_word]:
            _fail("ACOUSTIC_WORD_TEXT_MISMATCH")
        start = actual.get("start")
        end = actual.get("end")
        score = actual.get("score")
        if (type(start) not in (float, int) or type(end) not in (float, int)
                or not math.isfinite(start) or not math.isfinite(end)
                or type(score) not in (float, int) or not math.isfinite(score)
                or not 0 <= score <= 1):
            _fail("ACOUSTIC_WORD_TIME_OR_SCORE_MISSING")
        start_ms = round(start * 1000)
        end_ms = round(end * 1000)
        if not previous_end <= start_ms < end_ms <= duration:
            _fail("ACOUSTIC_WORD_TIMELINE_INVALID")
        previous_end = end_ms
        verified_spans.append({"word_start_ms": start_ms,
                               "word_end_ms": end_ms,
                               "text": expected_word, "acoustic_score": round(float(score), 4)})
    phrases = []
    offset = 0
    for line in lines:
        count = len(line["words"])
        subset = verified_spans[offset:offset + count]
        if not subset:
            _fail("ACOUSTIC_LINE_WITHOUT_WORDS")
        phrases.append({
            "line_id": line["line_id"],
            "phrase_start_ms": subset[0]["word_start_ms"],
            "phrase_end_ms": subset[-1]["word_end_ms"],
            "words": subset,
        })
        offset += count
    return {
        "schema": "bontours.montage.audio-alignment-draft/v1",
        "status": "DRAFT_ACOUSTIC_TIMINGS_REQUIRE_INDEPENDENT_LISTENING_QA",
        "project_id": preflight["project_id"],
        "source_sha256": expected_text_sha256,
        "audio_revision_sha256": preflight["audio_revision_sha256"],
        "narration_sha256": preflight["narration_sha256"],
        "method": method,
        "language": language,
        "lines": phrases,
        "word_count": len(verified_spans),
        "independent_audio_qa_completed": False,
        "audio_alignment_verified": False,
        "render_authorized": False,
        "paid_calls": 0,
        "publication_authorized": False,
    }


def run_private_alignment(root: Path, project_id: str,
                          private_dir: Path, *, language: str = "ru",
                          device: str = "cpu") -> dict:
    """Run a real local CTC model on source-pinned private bytes, owner initiated.

    No source, transcript or private path is logged. Caller is responsible for
    opening the private draft and separately listening to its original WAV.
    """
    if device not in {"cpu", "cuda"} or language not in LANGUAGES:
        _fail("ACOUSTIC_RUNTIME_UNSUPPORTED")
    repo = Path(root).resolve()
    # Canonical project IDs must not permit traversal.
    if not isinstance(project_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", project_id):
        _fail("INVALID_CANONICAL_PROJECT_ID")
    job = Path(private_dir)
    if job.is_symlink() or not job.is_dir():
        _fail("PRIVATE_JOB_DIR_INVALID")
    job = job.resolve()
    if job.is_relative_to(repo) or repo.is_relative_to(job):
        _fail("PRIVATE_AUDIO_MUST_NOT_BE_IN_REPOSITORY")
    project_path = catalog.inside(repo, f"campaigns/{project_id}/project.json")
    try:
        project = json.loads(project_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _fail("CANONICAL_PROJECT_UNAVAILABLE")
    if project.get("id") != project_id:
        _fail("CANONICAL_PROJECT_ID_MISMATCH")
    metadata = studio_lock.inspect_v2_audio(project, handoff.source_fingerprint(project))
    if metadata.get("status") != "VALID_METADATA":
        _fail("V2_CANONICAL_AUDIO_LOCK_REQUIRED")
    locked = project["stage_handoffs"]["voice_music"]["audio_lock"]
    if locked.get("mode") != "approved_wav":
        _fail("V2_WAV_REQUIRED_FOR_ALIGNMENT")
    text_path = catalog.inside(repo, locked["approved_text_source_path"])
    if text_path.is_symlink() or not text_path.is_file():
        _fail("APPROVED_TEXT_NOT_FOUND")
    source = text_path.read_bytes()
    if hashlib.sha256(source).hexdigest() != locked["approved_text_sha256"]:
        _fail("APPROVED_TEXT_CHANGED")
    preflight = audio_gate.verify_private_audio_manifest(project, job)
    manifest = json.loads((job / "approved-audio-files.json").read_text(encoding="utf-8"))
    wav_path = audio_gate._safe_file(job, manifest["narration_file"])
    # Runtime-only optional dependency; PR CI never downloads acoustic models.
    try:
        import whisperx
    except ImportError:
        _fail("LOCAL_WHISPERX_NOT_INSTALLED")
    try:
        audio = whisperx.load_audio(str(wav_path))
        model, metadata = whisperx.load_align_model(language_code=language, device=device)
        result = whisperx.align(
            [{"start": 0.0, "end": preflight["narration_duration_ms"]/1000,
              "text": source.decode("utf-8")}],
            model, metadata, audio, device, return_char_alignments=False)
    except Exception:
        _fail("ACOUSTIC_MODEL_FAILED_OR_UNSUPPORTED")
    return validate_acoustic_draft(
        preflight, source, locked["approved_text_sha256"], result,
        language=language, method="whisperx-ctc-local")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=VIDEO.parents[1])
    parser.add_argument("--project", required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--language", choices=sorted(LANGUAGES), default="ru")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--run-local-acoustic-model", action="store_true",
                        help="Explicitly run local WhisperX on previously verified owner-private WAV")
    args = parser.parse_args(argv)
    if not args.run_local_acoustic_model:
        print(json.dumps({"status":"BLOCKED_OWNER_MODEL_EXECUTION_NOT_REQUESTED",
                          "paid_calls":0,"render_authorized":False}))
        return 2
    try:
        result = run_private_alignment(args.repo_root,args.project,args.private_dir,
                                       language=args.language,device=args.device)
        folder = args.private_dir.resolve()
        output = folder / "alignment-draft.json"
        # Exclusive private creation: do not overwrite reviewed artifacts.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(output, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
            file.write("\n")
        print(json.dumps({"status":result["status"],
                          "line_count":len(result["lines"]),
                          "word_count":result["word_count"],
                          "audio_alignment_verified":False,
                          "paid_calls":0,"render_authorized":False}))
        return 0
    except (AlignmentDraftError, OSError, ValueError) as exc:
        print(json.dumps({"status":"BLOCKED_PRIVATE_AUDIO_ALIGNMENT_DRAFT",
                          "reason":exc.code if isinstance(exc,AlignmentDraftError)
                                   else "INVALID_PRIVATE_INPUT",
                          "paid_calls":0,"render_authorized":False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
