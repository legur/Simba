#!/usr/bin/env python3
"""Autonomous, owner-private v2 subtitle QA: independent local ASR vs CTC alignment.

The already-approved source text and WAV/music are SHA-verified by Studio and
Montage. An independent *unprompted* local faster-whisper transcription must
exactly match every approved spoken word; word boundaries from the independent
ASR and WhisperX CTC must be close, monotonic and within WAV duration.

No manual per-word review is required. If any prerequisite, score, text, or
timestamp fails, v2 is BLOCKED rather than declaring a false approval.
Machine agreement is not proof of perfection and NEVER approves rendering,
publication, TTS or new A2E generation. Never transmit client audio to a
remote ASR provider; ASR model weights must be provisioned locally.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
MATERIALS = HERE.parent / "materials"
for directory in (str(HERE), str(MATERIALS)):
    if directory not in sys.path:
        sys.path.insert(0, directory)

import catalog
import handoff
import motionlab_audio_alignment_draft as ctc
import motionlab_audio_listening_qa as private
import motionlab_v2_audio_gate as audio_gate
import studio_audio_lock

SHA = re.compile(r"^[a-f0-9]{64}$")
AUTO_QA = "bontours.montage.automatic-audio-qa/v1"
ALIGNMENT = "bontours.montage.audio-alignment/v1"
MAX_BOUNDARY_DIFF_MS = 220
MIN_WORD_PROB = 0.64
MIN_LANGUAGE_PROB = 0.80
MIN_AVG_LOGPROB = -0.45
MAX_NO_SPEECH_PROB = 0.30


class AutomaticQAError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def fail(code):
    raise AutomaticQAError(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def audit_independent_asr(preflight: dict, approved_source: bytes,
                          ctc_draft: dict, recognition: dict, *,
                          model_sha256: str) -> tuple[dict, dict]:
    """Strictly compare independent unprompted ASR to original approved words.

    A false/missing recognizer result cannot create verified timestamps.
    This does not claim any actual human listening or final MP4 approval.
    """
    if (not isinstance(preflight, dict)
            or preflight.get("status") != "APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED"
            or preflight.get("narration_bytes_verified") is not True
            or preflight.get("music_bytes_verified") is not True
            or preflight.get("render_authorized") is not False):
        fail("AUTO_QA_APPROVED_WAV_NOT_VERIFIED")
    if not isinstance(approved_source, bytes) or not 1 <= len(approved_source) <= ctc.MAX_TEXT_BYTES:
        fail("AUTO_QA_APPROVED_TEXT_INVALID")
    source_sha = _sha(approved_source)
    if not isinstance(model_sha256, str) or not SHA.fullmatch(model_sha256):
        fail("AUTO_QA_MODEL_NOT_PINNED")
    if (not isinstance(ctc_draft, dict)
            or ctc_draft.get("schema") != "bontours.montage.audio-alignment-draft/v1"
            or ctc_draft.get("status") != "DRAFT_ACOUSTIC_TIMINGS_REQUIRE_INDEPENDENT_LISTENING_QA"
            or ctc_draft.get("audio_alignment_verified") is not False
            or ctc_draft.get("render_authorized") is not False
            or ctc_draft.get("publication_authorized") is not False):
        fail("AUTO_QA_CTC_DRAFT_NOT_UNVERIFIED")
    for key, expected in (
        ("project_id", preflight.get("project_id")),
        ("source_sha256", source_sha),
        ("audio_revision_sha256", preflight.get("audio_revision_sha256")),
        ("narration_sha256", preflight.get("narration_sha256")),
    ):
        if not isinstance(expected, str) or ctc_draft.get(key) != expected:
            fail("AUTO_QA_CTC_SOURCE_REVISION_STALE")
    try:
        lines = ctc._script_lines(approved_source.decode("utf-8"))
    except (ctc.AlignmentDraftError, UnicodeError):
        fail("AUTO_QA_APPROVED_TEXT_UNSUPPORTED")
    draft_lines = ctc_draft.get("lines")
    if not isinstance(draft_lines, list) or len(draft_lines) != len(lines):
        fail("AUTO_QA_CTC_LINE_COUNT_MISMATCH")
    expected_words = [word for line in lines for word in line["words"]]
    if ctc_draft.get("word_count") != len(expected_words):
        fail("AUTO_QA_CTC_WORD_COUNT_MISMATCH")
    if (not isinstance(recognition, dict)
            or recognition.get("schema") != AUTO_QA
            or recognition.get("unprompted_original_wav") is not True
            or recognition.get("source_sha256") != source_sha
            or recognition.get("narration_sha256") != preflight.get("narration_sha256")
            or recognition.get("audio_revision_sha256") != preflight.get("audio_revision_sha256")
            or recognition.get("project_id") != preflight.get("project_id")
            or recognition.get("model_sha256") != model_sha256
            or recognition.get("independent_model_family") != "faster-whisper-ct2"
            or recognition.get("word_timestamps") is not True):
        fail("AUTO_QA_ASR_EVIDENCE_UNTRUSTED")
    language = ctc_draft.get("language")
    if (language not in ctc.LANGUAGES
            or recognition.get("language") != language
            or not _number(recognition.get("language_probability"))
            or recognition["language_probability"] < MIN_LANGUAGE_PROB):
        fail("AUTO_QA_LANGUAGE_UNCERTAIN")
    segments = recognition.get("segments")
    if not isinstance(segments, list) or not segments or len(segments) > 300:
        fail("AUTO_QA_ASR_SEGMENTS_INVALID")
    recognized_words = []
    previous_asr_end = 0
    duration = preflight.get("narration_duration_ms")
    if type(duration) is not int or duration <= 0:
        fail("AUTO_QA_WAV_DURATION_INVALID")
    for segment in segments:
        if (not isinstance(segment, dict)
                or not _number(segment.get("avg_logprob"))
                or not _number(segment.get("no_speech_prob"))
                or segment["avg_logprob"] < MIN_AVG_LOGPROB
                or not 0 <= segment["no_speech_prob"] <= MAX_NO_SPEECH_PROB
                or not isinstance(segment.get("words"), list)
                or not segment["words"]):
            fail("AUTO_QA_ASR_SEGMENT_UNCERTAIN")
        for token in segment["words"]:
            if not isinstance(token, dict):
                fail("AUTO_QA_ASR_WORD_UNCERTAIN")
            text = ctc._words(str(token.get("word", "")))
            if len(text) != 1 or not _number(token.get("start")) or not _number(token.get("end")):
                fail("AUTO_QA_ASR_WORD_UNCERTAIN")
            if not _number(token.get("probability")) or token["probability"] < MIN_WORD_PROB or token["probability"] > 1:
                fail("AUTO_QA_ASR_WORD_UNCERTAIN")
            start = round(token["start"] * 1000)
            end = round(token["end"] * 1000)
            if not previous_asr_end <= start < end <= duration:
                fail("AUTO_QA_ASR_WORD_TIMELINE_INVALID")
            recognized_words.append((text[0], start, end))
            previous_asr_end = end
    if len(recognized_words) != len(expected_words):
        fail("AUTO_QA_ASR_WORD_COUNT_MISMATCH")
    if [w[0] for w in recognized_words] != expected_words:
        fail("AUTO_QA_SPOKEN_TEXT_DIFFERS_FROM_APPROVED_SCRIPT")
    verified_lines = []
    offset = 0
    previous_ctc_end = 0
    for script_line, draft_line in zip(lines, draft_lines):
        if not isinstance(draft_line, dict) or draft_line.get("line_id") != script_line["line_id"]:
            fail("AUTO_QA_CTC_LINE_ID_MISMATCH")
        ctc_words = draft_line.get("words")
        if not isinstance(ctc_words, list) or len(ctc_words) != len(script_line["words"]):
            fail("AUTO_QA_CTC_WORD_COUNT_MISMATCH")
        valid_words = []
        for text, ctc_word in zip(script_line["words"], ctc_words):
            _, asr_start, asr_end = recognized_words[offset]
            offset += 1
            if not isinstance(ctc_word, dict) or ctc_word.get("text") != text:
                fail("AUTO_QA_CTC_WORD_TEXT_MISMATCH")
            start = ctc_word.get("word_start_ms")
            end = ctc_word.get("word_end_ms")
            score = ctc_word.get("acoustic_score")
            if (type(start) is not int or type(end) is not int
                    or not previous_ctc_end <= start < end <= duration
                    or not _number(score) or not 0.6 <= score <= 1):
                fail("AUTO_QA_CTC_BOUNDARIES_INVALID")
            if (abs(start - asr_start) > MAX_BOUNDARY_DIFF_MS
                    or abs(end - asr_end) > MAX_BOUNDARY_DIFF_MS):
                fail("AUTO_QA_MODELS_DISAGREE_ON_WORD_TIMINGS")
            valid_words.append({"text": text,
                                "word_start_ms": start,
                                "word_end_ms": end})
            previous_ctc_end = end
        verified_lines.append({
            "line_id": script_line["line_id"],
            "phrase_start_ms": valid_words[0]["word_start_ms"],
            "phrase_end_ms": valid_words[-1]["word_end_ms"],
            "words": valid_words,
        })
    qa_evidence_sha = _sha(_canonical_json({
        "qa_schema": AUTO_QA,
        "recognition": recognition,
        "ctc_draft": ctc_draft,
        "source_sha256": source_sha,
    }))
    alignment = {
        "schema": ALIGNMENT,
        "status": "AUDIO_ALIGNMENT_VERIFIED",
        "project_id": preflight["project_id"],
        "source_sha256": source_sha,
        "audio_revision_sha256": preflight["audio_revision_sha256"],
        "narration_sha256": preflight["narration_sha256"],
        "method": "local_whisperx_ctc_plus_independent_faster_whisper_asr_v1",
        "qa_evidence_sha256": qa_evidence_sha,
        "automatic_audio_qa_completed": True,
        "independent_audio_qa_completed": False,
        "render_authorized": False,
        "publication_authorized": False,
        "lines": verified_lines,
    }
    audio_gate.validate_alignment_evidence(preflight, alignment, lines)
    return alignment, {
        "status": "AUDIO_ALIGNMENT_AUTO_QA_PASSED",
        "qa_evidence_sha256": qa_evidence_sha,
        "audio_revision_sha256": preflight["audio_revision_sha256"],
        "source_sha256": source_sha,
        "model_sha256": model_sha256,
        "word_count": offset,
        "automatic_audio_qa_completed": True,
        "independent_audio_qa_completed": False,
        "render_authorized": False,
        "publication_authorized": False,
        "paid_calls": 0,
    }


def _safe_local_asr_model(model_path: str, repository_root: Path) -> tuple[Path, str]:
    if not isinstance(model_path, str) or not model_path.startswith("/"):
        fail("AUTO_QA_LOCAL_ASR_MODEL_NOT_CONFIGURED")
    candidate = Path(model_path)
    if candidate.is_symlink() or not candidate.is_dir():
        fail("AUTO_QA_LOCAL_ASR_MODEL_UNAVAILABLE")
    candidate = candidate.resolve()
    repository = Path(repository_root).resolve()
    if candidate.is_relative_to(repository) or repository.is_relative_to(candidate):
        fail("AUTO_QA_LOCAL_ASR_MODEL_INSIDE_REPOSITORY")
    model = candidate / "model.bin"
    config = candidate / "config.json"
    if (model.is_symlink() or config.is_symlink()
            or not model.is_file() or not config.is_file()
            or not 100_000 <= model.stat().st_size <= 16_000_000_000):
        fail("AUTO_QA_LOCAL_ASR_MODEL_FILES_INVALID")
    # Exact model revision is pinned for each trusted QA result. No model
    # download occurs, and raw client audio is not sent to an external API.
    with model.open("rb") as fh:
        digest = hashlib.file_digest(fh, "sha256").hexdigest()
    return candidate, digest


def run_local_asr(wav_path: Path, model_path: Path, model_sha: str,
                  *, language: str = "ru", device: str = "cpu") -> dict:
    """Run independently decoded speech recognition, no approved transcript prompt."""
    if language not in ctc.LANGUAGES or device not in {"cpu", "cuda"}:
        fail("AUTO_QA_ASR_RUNTIME_INVALID")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        fail("AUTO_QA_FASTER_WHISPER_NOT_INSTALLED")
    try:
        model = WhisperModel(str(model_path), device=device,
                             compute_type="int8" if device == "cpu" else "float16",
                             local_files_only=True)
        chunks, info = model.transcribe(
            str(wav_path), language=language, task="transcribe",
            beam_size=5, temperature=0.0,
            word_timestamps=True, condition_on_previous_text=False,
            vad_filter=False, initial_prompt=None, prefix=None)
        segments = []
        for segment in chunks:
            segments.append({
                "avg_logprob": segment.avg_logprob,
                "no_speech_prob": segment.no_speech_prob,
                "words": [
                    {"word": word.word, "start": word.start,
                     "end": word.end, "probability": word.probability}
                    for word in (segment.words or [])
                ],
            })
    except Exception:
        fail("AUTO_QA_LOCAL_ASR_FAILED")
    return {
        "schema": AUTO_QA,
        "independent_model_family": "faster-whisper-ct2",
        "model_sha256": model_sha,
        "unprompted_original_wav": True,
        "word_timestamps": True,
        "language": info.language,
        "language_probability": info.language_probability,
        "segments": segments,
    }


def verify_automatic_audio_qa(project: dict, private_dir: Path,
                              repository_root: Path, *, asr_model_path: str,
                              device: str = "cpu") -> tuple[dict, dict]:
    """Automatic owner-private QA, no user listening or clicks.

    The source v2 server calls this when the approved project becomes ready.
    Missing local models/changed bytes means a clear BLOCKED status, not a
    request to the user to perform the technical verification manually.
    """
    root = Path(repository_root).resolve()
    private_job = Path(private_dir)
    if private_job.is_symlink() or not private_job.is_dir():
        fail("AUTO_QA_PRIVATE_JOB_INVALID")
    private_job = private_job.resolve()
    if private_job.is_relative_to(root) or root.is_relative_to(private_job):
        fail("AUTO_QA_PRIVATE_FILES_IN_REPOSITORY")
    preflight = audio_gate.verify_private_audio_manifest(project, private_job)
    source = private._safe_text_source(project, root)
    lock = project["stage_handoffs"]["voice_music"]["audio_lock"]
    if lock.get("mode") != "approved_wav":
        fail("AUTO_QA_REQUIRES_LOCKED_WAV")
    manifest = json.loads((private_job / "approved-audio-files.json").read_text("utf-8"))
    wav = audio_gate._safe_file(private_job, manifest["narration_file"])
    model, model_sha = _safe_local_asr_model(asr_model_path, root)
    if (private_job / private.DRAFT_FILE).is_file():
        _, draft = private._read_private_json(private_job, private.DRAFT_FILE)
    else:
        # Existing WhisperX CTC adapter runs automatically when needed.
        # Its package/model availability is an infrastructure responsibility.
        draft = ctc.run_private_alignment(root, project["id"], private_job,
                                         language="ru", device=device)
    recognition = run_local_asr(wav, model, model_sha, language=draft.get("language","ru"),
                                device=device)
    recognition.update(project_id=preflight["project_id"],
                       source_sha256=_sha(source),
                       narration_sha256=preflight["narration_sha256"],
                       audio_revision_sha256=preflight["audio_revision_sha256"])
    return audit_independent_asr(preflight, source, draft, recognition,
                                  model_sha256=model_sha)
