#!/usr/bin/env python3
"""Third *unprompted* ASR model diagnostic for existing owner Alaska WAV.

The original SHA-pinned WAV/music/text are read from owner-private Drive only.
All audio inference happens offline on a trusted main-branch worker after
PUBLIC model weights are installed. This is a diagnostic, not a substitute
for independent CTC, an owner voice/music lock or canonical v2 approval.
No transcript, tokens, private IDs, WAV or music are uploaded to GitHub.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re
import sys
import tempfile

import alaska_private_medium_asr as medium

MODEL="large-v3-turbo"
OUTPUT="Alaska_v2_unprompted_turbo_asr_v1.json"


def score(approved, observed, language, probability):
    """Do not convert a model agreement into a verified v2 selection."""
    result=medium.analyze_words(approved,observed,language,probability)
    exact=result["exact_token_match"]
    strong=exact and result["low_confidence_word_count"]==0 and language=="ru" and probability>=0.80
    result.update({
        "status":("PRECANDIDATE_TURBO_TEXT_MATCHED"
                  if strong else "BLOCKED_TURBO_ASR_TEXT_OR_CONFIDENCE_DIFFERS"),
        "model":"large_v3_turbo_cpu_int8",
        "third_asr_not_independent_model_family":True,
        "word_timing_verified_for_canonical_v2":False,
        "canonical_audio_lock_approved":False,
        "render_authorized":False,
    })
    return result


def evaluate(approved, wav_path):
    try:
        from faster_whisper import WhisperModel
        engine=WhisperModel(MODEL,device="cpu",compute_type="int8",
                            local_files_only=True)
        segments,info=engine.transcribe(
            str(wav_path),language="ru",beam_size=5,temperature=0.0,
            word_timestamps=True,condition_on_previous_text=False,
            vad_filter=False,initial_prompt=None,prefix=None)
        observed=medium.words_from_whisper(list(segments))
    except ImportError:
        raise medium.Blocked("TURBO_ASR_LOCAL_MODEL_NOT_INSTALLED") from None
    except Exception:
        raise medium.Blocked("TURBO_ASR_ACOUSTIC_INFERENCE_FAILED") from None
    medium.need(bool(observed),"TURBO_ASR_NO_OBSERVATIONS")
    return score(approved,observed,
            getattr(info,"language",None),
            float(getattr(info,"language_probability",0) or 0))


def audit(svc):
    wav=medium.read_private(
        svc,medium.WAV_ID,medium.AUDIO_DIR,"WarmBaritone.wav",
        medium.WAV_SHA,medium.MAX_WAV,{"audio/x-wav","audio/wav","audio/wave"})
    medium.read_private(
        svc,medium.MUSIC_ID,medium.AUDIO_DIR,"Discover.mp3",
        medium.MUSIC_SHA,medium.MAX_MP3,{"audio/mpeg"})
    spec=medium.read_private(
        svc,medium.SPEC_ID,medium.DOCS_DIR,"handoff_approved-video-spec.json",
        medium.SOURCE_SHA,medium.MAX_SPEC,{"application/json"})
    duration=medium.inspect_wav(wav)
    approved=medium.approved_narration(json.loads(spec))
    with tempfile.TemporaryDirectory(prefix="alaska-turbo-asr-") as folder:
        wav_file=Path(folder)/"original.wav"
        wav_file.write_bytes(wav)
        recognition=evaluate(approved,wav_file)
    return {
        "schema":"bontours.motionlab.precandidate-third-unprompted-asr/v1",
        "project_id":medium.PROJECT,
        "status":recognition["status"],
        "run_utc":datetime.now(timezone.utc).isoformat(),
        "original_wav_sha256":medium.WAV_SHA,
        "music_sha256":medium.MUSIC_SHA,
        "approved_source_sha256":medium.SOURCE_SHA,
        "original_wav_duration_s":duration,
        "source_bytes_verified":True,
        "third_recognition":recognition,
        "canonical_v2_audio_lock_recorded":False,
        "automatic_audio_qa_completed_for_canonical":False,
        "v2_owner_selection_created":False,
        "paid_calls":0,
        "run_tts":False,"run_a2e":False,"run_render":False,
        "publication_authorized":False
    }


def store_once(svc,report):
    q=f"'{medium.AUDIO_DIR}' in parents and name = '{OUTPUT}' and trashed = false"
    found=svc.files().list(q=q,pageSize=100,
        fields="nextPageToken,files(id,name)").execute()
    medium.need(not found.get("nextPageToken") and not found.get("files"),
                "TURBO_PRIVATE_REPORT_ALREADY_EXISTS")
    return medium.issue_ticket.upload(svc,medium.AUDIO_DIR,OUTPUT,report)


def main():
    try:
        svc=medium.issue_ticket.drive()
        record=audit(svc)
        store_once(svc,record)
        print(json.dumps({
            "status":record["status"],
            "source_bytes_verified":True,
            "private_report_saved":True,
            "third_asr_only_not_independent_model_family":True,
            "canonical_v2_audio_approved":False,
            "render_started":False,
            "paid_calls":0
        },sort_keys=True))
        return 0
    except medium.Blocked as exc:
        reason=str(exc)
        if not re.fullmatch(r"[A-Z0-9_]{4,90}",reason):
            reason="TURBO_ASR_SOURCE_GATE_BLOCKED"
        print("ALASKA_TURBO_ASR_BLOCKED:"+reason,file=sys.stderr)
        return 2
    except Exception:
        print("ALASKA_TURBO_ASR_INTERNAL_ERROR",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
