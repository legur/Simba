#!/usr/bin/env python3
"""Independent unprompted MEDIUM local ASR diagnostic for existing Alaska WAV.

This owner-only pre-canonical analysis does not alter WAV/music/approved text,
issue a v2 ticket, or authorize render. Public model weights are preloaded
before any private source is fetched. Only redacted scalar differences are
stored in Drive; no audio, text, words or tokens are logged or published.
"""
from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path
import difflib
import json
import re
import sys
import tempfile

from alaska_private_dual_audio_preflight import (
    PROJECT,AUDIO_DIR,DOCS_DIR,WAV_ID,MUSIC_ID,SPEC_ID,WAV_SHA,MUSIC_SHA,SOURCE_SHA,
    MAX_WAV,MAX_MP3,MAX_SPEC,Blocked,need,read_private,
    approved_narration,inspect_wav,normalize,words_from_whisper,issue_ticket,
)
NAME="Alaska_v2_unprompted_medium_asr_v1.json"
MODEL="medium"

def analyze_words(approved,observations,language,probability):
    """Never assert editorial approval from an ASR model's conjecture."""
    src=normalize(approved)
    heard=[word for item in observations for word in normalize(item["word"])]
    seq=difflib.SequenceMatcher(a=src,b=heard,autojunk=False)
    mismatch=[{
        "approved_index":i,"approved_count":k-i,
        "recognized_index":j,"recognized_count":l-j
    } for op,i,k,j,l in seq.get_opcodes() if op!="equal"]
    weak=[i for i,row in enumerate(observations)
          if not 0.64<=row["probability"]<=1]
    exact=src==heard
    strong=(exact and not weak and language=="ru" and probability>=.80)
    return {
        "status":("PRECANDIDATE_SECOND_ASR_TEXT_MATCHED"
                   if strong else "BLOCKED_MEDIUM_ASR_TEXT_OR_CONFIDENCE_DIFFERS"),
        "model_family":"faster-whisper-ct2",
        "unprompted_original_wav":True,
        "approved_text_as_prompt":False,
        "model":"medium_cpu_int8",
        "language":language,
        "language_probability":round(probability,4),
        "approved_token_count":len(src),
        "recognized_token_count":len(heard),
        "exact_token_match":exact,
        "token_sequence_similarity":round(seq.ratio(),4),
        "low_confidence_word_count":len(weak),
        "weak_word_indices":weak[:20],
        "mismatch_positions":mismatch[:20],
        "word_timing_verified_for_canonical_v2":False,
        "canonical_audio_lock_approved":False,
        "render_authorized":False,
        "note":"This is independent unprompted inference, not v2 owner approval."
    }


def evaluate(approved,path):
    try:
        from faster_whisper import WhisperModel
        model=WhisperModel(MODEL,device="cpu",compute_type="int8",
                           local_files_only=True)
        segments,info=model.transcribe(
            str(path),language="ru",beam_size=5,temperature=0.0,
            word_timestamps=True,condition_on_previous_text=False,
            vad_filter=False,initial_prompt=None,prefix=None)
        observations=words_from_whisper(list(segments))
    except ImportError:
        raise Blocked("MEDIUM_LOCAL_MODEL_NOT_INSTALLED") from None
    except Exception:
        raise Blocked("MEDIUM_LOCAL_ASR_FAILED") from None
    need(bool(observations),"MEDIUM_ASR_NO_RECOGNIZED_WORDS")
    return analyze_words(approved,observations,
        getattr(info,"language",None),
        float(getattr(info,"language_probability",0) or 0))


def audit(svc):
    wav=read_private(svc,WAV_ID,AUDIO_DIR,"WarmBaritone.wav",
                     WAV_SHA,MAX_WAV,{"audio/x-wav","audio/wav","audio/wave"})
    read_private(svc,MUSIC_ID,AUDIO_DIR,"Discover.mp3",
                 MUSIC_SHA,MAX_MP3,{"audio/mpeg"})
    spec=read_private(svc,SPEC_ID,DOCS_DIR,
                      "handoff_approved-video-spec.json",SOURCE_SHA,MAX_SPEC,
                      {"application/json"})
    duration=inspect_wav(wav)
    source=approved_narration(json.loads(spec))
    with tempfile.TemporaryDirectory(prefix="alaska-medium-unprompted-") as td:
        private_wav=Path(td)/"original.wav"
        private_wav.write_bytes(wav)
        recognition=evaluate(source,private_wav)
    return {
        "schema":"bontours.motionlab.precandidate-secondary-unprompted-asr/v1",
        "project_id":PROJECT,
        "status":recognition["status"],
        "run_utc":datetime.now(timezone.utc).isoformat(),
        "original_wav_sha256":WAV_SHA,
        "music_sha256":MUSIC_SHA,
        "approved_source_sha256":SOURCE_SHA,
        "original_wav_duration_s":duration,
        "source_bytes_verified":True,
        "secondary_recognition":recognition,
        "canonical_v2_audio_lock_recorded":False,
        "automatic_audio_qa_completed_for_canonical":False,
        "v2_owner_selection_created":False,
        "paid_calls":0,
        "run_tts":False,"run_a2e":False,"run_render":False,
        "publication_authorized":False,
    }


def store_once(svc,report):
    q=f"'{AUDIO_DIR}' in parents and name = '{NAME}' and trashed = false"
    found=svc.files().list(q=q,pageSize=100,
        fields="nextPageToken,files(id,name)").execute()
    need(not found.get("nextPageToken") and not found.get("files"),
         "SECOND_ASR_PRIVATE_EVIDENCE_ALREADY_PRESENT")
    return issue_ticket.upload(svc,AUDIO_DIR,NAME,report)


def main():
    try:
        svc=issue_ticket.drive()
        result=audit(svc)
        store_once(svc,result)
        # Never print the recognized speech or isolated customer place names.
        print(json.dumps({
            "status":result["status"],
            "private_report_saved":True,
            "original_source_verified":True,
            "canonical_v2_audio_approved":False,
            "render_started":False,"paid_calls":0
        },sort_keys=True))
        return 0
    except Blocked as err:
        reason=str(err)
        if not re.fullmatch(r"[A-Z0-9_]{4,90}",reason):
            reason="SECOND_ASR_PRECHECK_BLOCKED"
        print("ALASKA_MEDIUM_ASR_BLOCKED:"+reason,file=sys.stderr)
        return 2
    except Exception:
        print("ALASKA_MEDIUM_ASR_INTERNAL_ERROR",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
