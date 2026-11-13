#!/usr/bin/env python3
"""One-time owner-private Alaska WAV+music proof and two acoustic methods.

This is a PRE-CANONICAL diagnostic, never a voice_music approval, never the
canonical v2 AUDIO_ALIGNMENT_VERIFIED_AUTO receipt and never a render ticket.
Private WAV+music are downloaded from the owner's existing Drive into an
ephemeral trusted CI worker, checked by exact bytes and deleted afterward.
No paid API, no remote ASR, no WAV/text in GitHub comments or artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata
import wave

REPO_MATERIALS=Path(__file__).resolve().parents[1]/"materials"
DRIVE_HELPER=REPO_MATERIALS/"motionlab"/"drive_handoff"
sys.path.insert(0,str(DRIVE_HELPER))
import issue_ticket

PROJECT="alaska-voyager-2027"
AUDIO_DIR="1bEI3IwZoQFs6M8xounxI7AyjcfmOBJyB"
DOCS_DIR="1xudu3oIiHq6cWqYIGIZLOrGBnjt8UZ_V"
WAV_ID="1l3YcEVoaRwvTME5OrfmHEcqiX9KjEYah"
MUSIC_ID="1m6oJrO6B82az6z5ePqhrRQFmL_N5OIbf"
SPEC_ID="1O1MT_CgTfyH-s1uBFCSQLR5CT1tyrAli"
WAV_SHA="0a503ad3656f5a44e5921558f19c75d4dfe696a46bf53a7b990e601321b2570e"
MUSIC_SHA="cc92050b8e2e3a1c8a13d4ee85bc74cd95799c2088096e680167a73b2b390560"
SOURCE_SHA="bdf88225ce6771281484f00123791cd8bfd89d22b4d19cf577b4f475249a233f"
NAME="Alaska_v2_offline_dual_asr_phrasewise_v2.json"
MAX_WAV=4*1024*1024
MAX_MP3=6*1024*1024
MAX_SPEC=100_000

class Blocked(ValueError):pass

def need(ok,code):
    if not ok:raise Blocked(code)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def normalize(text):
    return re.findall(r"[^\W_]+",unicodedata.normalize("NFKC",text).lower(),
                      flags=re.UNICODE)

def approved_narration(spec):
    need(isinstance(spec,dict) and spec.get("packageId")==PROJECT,
         "SPEC_PROJECT_CHANGED")
    source=spec.get("sourcePost")
    need(isinstance(source,str) and 100<len(source)<2000,
         "APPROVED_NARRATION_MISSING")
    prefix="Сводная утвержденная озвучка v1:"
    # This is a provenance LABEL, not spoken text. Do not send it to CTC.
    need(source.startswith(prefix),"EXPECTED_V1_EDITORIAL_PREFIX_CHANGED")
    spoken=source[len(prefix):].strip()
    need(len(normalize(spoken))>40,"APPROVED_TEXT_TOO_SHORT")
    return spoken

def inspect_wav(raw):
    import io
    try:
        with wave.open(io.BytesIO(raw)) as src:
            channels=src.getnchannels()
            rate=src.getframerate()
            width=src.getsampwidth()
            duration=src.getnframes()/rate
            compressed=src.getcomptype()
    except (wave.Error,OSError,EOFError,ZeroDivisionError):
        raise Blocked("WAV_ENCODING_INVALID") from None
    need(channels==1 and rate==24000 and width==2 and compressed=="NONE"
         and 41.2<duration<41.6,"WAV_FORMAT_OR_LENGTH_CHANGED")
    return round(duration,4)

def read_private(svc,file_id,folder,filename,expected_sha,max_size,mime):
    """Source is private with exact owner archive folder, ACL, name and bytes."""
    try:
        meta=svc.files().get(fileId=file_id,
            fields="id,parents,name,mimeType,size,trashed").execute()
        need(meta.get("id",file_id)==file_id and meta.get("name")==filename
             and meta.get("parents")==[folder]
             and meta.get("mimeType") in mime and meta.get("trashed") is False
             and 4096<=int(meta.get("size",0))<=max_size,
             "PRIVATE_SOURCE_METADATA_CHANGED")
        access=svc.permissions().list(fileId=file_id,
            fields="nextPageToken,permissions(type,role)",pageSize=100).execute()
        need(not access.get("nextPageToken")
             and isinstance(access.get("permissions"),list)
             and bool(access["permissions"])
             and all(x.get("type")=="user" for x in access["permissions"]),
             "PRIVATE_SOURCE_ACL_UNVERIFIED")
        raw=svc.files().get_media(fileId=file_id).execute()
        need(type(raw) is bytes and len(raw)==int(meta["size"])
             and digest(raw)==expected_sha,"PRIVATE_SOURCE_HASH_CHANGED")
        return raw
    except Blocked:raise
    except Exception:
        raise Blocked("PRIVATE_SOURCE_UNAVAILABLE") from None

def words_from_whisper(segments):
    words=[]
    for seg in segments:
        for row in seg.words or []:
            word=normalize(row.word)
            if not word:continue
            need(row.start is not None and row.end is not None
                 and row.start<=row.end,"ASR_WORD_TIME_MISSING")
            words.append({
                "word":"".join(word),
                "start":float(row.start),"end":float(row.end),
                "probability":float(row.probability or 0),
            })
    return words

def sentence_windows(approved, observations, duration):
    """Place short approved utterances in acoustic windows using UNPROMPTED ASR.

    The whole-41-second CTC segment was too coarse to locate problem words.
    Each sentence requires independent unprompted ASR anchors before any
    forced alignment; a missing sentence blocks, never guesses timing.
    These ASR anchors are window hints, NOT proof that words were spoken.
    """
    import difflib
    sentences=[part.strip() for part in re.split(r'(?<=[.!?])\s+',approved)
               if part.strip()]
    need(1<len(sentences)<=24,"CTC_SENTENCE_SEGMENTATION_INVALID")
    expected=normalize(approved)
    heard=[word for row in observations for word in normalize(row["word"])]
    matches=difflib.SequenceMatcher(
        a=expected,b=heard,autojunk=False).get_matching_blocks()
    locations={i+at:j+at for i,j,size in matches for at in range(size)}
    offset=0
    positions=[]
    for phrase in sentences:
        size=len(normalize(phrase))
        need(size>0,"CTC_EMPTY_APPROVED_SENTENCE")
        indices=[j for i,j in sorted(locations.items())
                 if offset<=i<offset+size]
        # Two independent lexical anchors per sentence; one is too weak
        # for an accurate phrase window, particularly for place names.
        need(len(indices)>=2,"CTC_INSUFFICIENT_INDEPENDENT_SENTENCE_ANCHORS")
        start=max(0.0,float(observations[indices[0]]["start"])-0.40)
        end=min(float(duration),float(observations[indices[-1]]["end"])+0.40)
        need(start+0.10<end,"CTC_SENTENCE_WINDOW_INVALID")
        positions.append({"text":phrase,"start":start,"end":end,
                          "_asr_first":indices[0],"_asr_last":indices[-1]})
        offset+=size
    need(offset==len(expected),"CTC_APPROVED_SENTENCE_TOKENS_INVALID")
    for i in range(1,len(positions)):
        previous,current=positions[i-1],positions[i]
        need(previous["_asr_last"]<current["_asr_first"],
             "CTC_SENTENCE_ANCHORS_OUT_OF_ORDER")
        if current["start"]<previous["end"]:
            previous_end=observations[previous["_asr_last"]]["end"]
            current_start=observations[current["_asr_first"]]["start"]
            border=(float(previous_end)+float(current_start))/2.0
            need(previous["start"]+0.03<border<current["end"]-0.03,
                 "CTC_SENTENCE_BOUNDARY_UNRESOLVED")
            previous["end"]=min(previous["end"],border)
            current["start"]=max(current["start"],border)
    for item in positions:
        need(0<=item["start"]<item["end"]<=duration+.05,
             "CTC_SENTENCE_WINDOW_INVALID")
    # Preserve no ASR text, no source content in diagnostics.
    return [{"text":item["text"],
             "start":round(item["start"],3),
             "end":round(item["end"],3)} for item in positions]


def redacted_evidence(approved_tokens,observations,ctc,duration):
    """Private review only: positions/scores, NO spoken words or transcript."""
    import difflib
    heard=[t for w in observations for t in normalize(w["word"])]
    differing=[{
        "source_position":i,
        "source_token_count":end-i,
        "asr_position":j,
        "asr_token_count":other-j,
    } for code,i,end,j,other in difflib.SequenceMatcher(
        a=approved_tokens,b=heard,autojunk=False).get_opcodes()
        if code!="equal"]
    absent=[];nonmonotonic=[];outofrange=[]
    previous_end=0.0
    for i,row in enumerate(ctc):
        begin,end=row.get("start"),row.get("end")
        if type(begin) not in (int,float) or type(end) not in (int,float):
            absent.append(i)
        elif not 0<=begin<end<=duration+.1:
            outofrange.append(i)
        elif begin+0.08<previous_end:
            nonmonotonic.append(i)
        if type(end) in (int,float):
            previous_end=max(previous_end,float(end))
    return {
        "approved_numeric_token_positions":[i for i,t in enumerate(approved_tokens)
                                            if any(char.isdigit() for char in t)],
        "independent_asr_mismatch_spans":differing[:24],
        "independent_asr_weak_word_positions":[i for i,x in enumerate(observations)
                                              if x["probability"]<.64][:25],
        "ctc_missing_timing_positions":absent[:25],
        "ctc_invalid_timing_positions":outofrange[:25],
        "ctc_nonmonotonic_positions":nonmonotonic[:25],
        "ctc_output_tokens":len(ctc),
        "approved_tokens":len(approved_tokens),
        "notes":"Indices only; no transcript, audio or client text is included."
    }


def check_two_methods(approved,wav_path,duration):
    """Locally downloaded MODEL weights; NO remote audio calls.

    The CTC stage consumes only approved text, while CTranslate2 ASR receives
    the WAV with no initial_prompt, preserving method independence.
    """
    from faster_whisper import WhisperModel
    import whisperx
    model=WhisperModel("small",device="cpu",compute_type="int8",
                       local_files_only=True)
    segments,info=model.transcribe(str(wav_path),language="ru",
        beam_size=5,temperature=0.0,
        word_timestamps=True,condition_on_previous_text=False,
        vad_filter=False,initial_prompt=None,prefix=None)
    speech=list(segments)
    observations=words_from_whisper(speech)
    spoken=[token for row in observations for token in normalize(row["word"])]
    expected=normalize(approved)
    import difflib
    similarity=difflib.SequenceMatcher(
        a=expected,b=spoken,autojunk=False).ratio()
    language=getattr(info,"language",None)
    confidence=float(getattr(info,"language_probability",0) or 0)
    # WhisperX alignment is a distinct CTC family from Whisper/CT2 ASR.
    audio=whisperx.load_audio(str(wav_path))
    model_a,metadata=whisperx.load_align_model(language_code="ru",device="cpu")
    windows=sentence_windows(approved,observations,duration)
    mapped=whisperx.align(windows,model_a,metadata,audio,device="cpu",
         return_char_alignments=False)
    ctc=mapped.get("word_segments") or []
    ctc_tokens=[token for x in ctc for token in normalize(str(x.get("word","")))]
    ctc_valid=True
    previous_ctc_end=0.0
    for row in ctc:
        start,end=row.get("start"),row.get("end")
        if (type(start) not in (int,float)
                or type(end) not in (int,float)
                or not 0<=start<end<=duration+.1
                or start+.05<previous_ctc_end):
            ctc_valid=False
        if type(end) in (int,float):
            previous_ctc_end=max(previous_ctc_end,float(end))
    # No metadata promotion from a forced alignment alone. Even with a
    # very plausible CTC timeline, the unprompted independent ASR must agree.
    match=(spoken==expected and ctc_tokens==expected and ctc_valid
           and language=="ru" and confidence>=.80
           and len(ctc)>=len(expected)-2
           and all(x["probability"]>=.64 for x in observations))
    return {
      "status":("PRECANONICAL_TWO_MODEL_AUDIO_EVIDENCE_PASSED"
                if match else "BLOCKED_INDEPENDENT_AUDIO_EVIDENCE_DISAGREES"),
      "asr_model":"local_faster_whisper_small",
      "ctc_method":"local_whisperx_wav2vec2_alignment",
      "asr_language":language,
      "asr_language_probability":round(confidence,4),
      "approved_tokens":len(expected),
      "independent_asr_tokens":len(spoken),
      "ctc_forced_alignment_tokens":len(ctc_tokens),
      "asr_string_agreement":spoken==expected,
      "ctc_word_agreement":ctc_tokens==expected,
      "ctc_timeline_valid":ctc_valid,
      "asr_approved_similarity":round(similarity,4),
      "weak_asr_words":sum(x["probability"]<.64 for x in observations),
      "ctc_sentence_windows":len(windows),
      "review_diagnostics":redacted_evidence(expected,observations,ctc,duration),
      "word_timing_verified_for_canonical_v2":False,
      "reasons":([] if match else [
        "Canonical owner audio revision and dual-model current stage replay remain mandatory.",
        "Low-confidence or discrepant ASR/CTC output must not be auto-promoted."]),
    }

def audit(svc):
    from datetime import datetime,timezone
    # This report does NOT provide a v2 approval even if its two models agree.
    result={
      "schema":"bontours.motionlab.precanonical-offline-audio-evidence/v1",
      "project_id":PROJECT,
      "status":"BLOCKED_NO_CANONICAL_AUDIO_LOCK",
      "run_utc":datetime.now(timezone.utc).isoformat(),
      "paid_calls":0,
      "run_tts":False,"run_a2e":False,
      "run_render":False,"publication_authorized":False,
      "canonical_v2_audio_lock_recorded":False,
      "owner_v2_montage_selection_created":False,
      "automatic_audio_qa_completed_for_canonical":False,
      "source_pins":{"narration_sha256":WAV_SHA,"music_sha256":MUSIC_SHA,
                     "approved_source_sha256":SOURCE_SHA},
    }
    wav=read_private(svc,WAV_ID,AUDIO_DIR,"WarmBaritone.wav",
                     WAV_SHA,MAX_WAV,{"audio/x-wav","audio/wav","audio/wave"})
    music=read_private(svc,MUSIC_ID,AUDIO_DIR,"Discover.mp3",
                       MUSIC_SHA,MAX_MP3,{"audio/mpeg"})
    spec_bytes=read_private(svc,SPEC_ID,DOCS_DIR,
              "handoff_approved-video-spec.json",SOURCE_SHA,MAX_SPEC,
              {"application/json"})
    duration=inspect_wav(wav)
    source=approved_narration(json.loads(spec_bytes))
    result["source_bytes_verified"]=True
    result["original_voice_duration_s"]=duration
    result["private_music_bytes_verified"]=len(music)>4000
    with tempfile.TemporaryDirectory(prefix="alaska-audio-qa-") as td:
        path=Path(td)/"approved.wav"
        path.write_bytes(wav)
        # Local Whisper/WhisperX only; models cannot access the Drive bearer.
        try:
            independent=check_two_methods(source,path,duration)
        except Blocked as exc:
            independent={"status":str(exc),
                         "source_audio_verified":True,
                         "word_timing_verified_for_canonical_v2":False}
        except (ImportError,RuntimeError,OSError,ValueError,KeyError):
            independent={"status":"BLOCKED_MODEL_OR_ALIGNMENT_FAILED",
                         "source_audio_verified":True,
                         "word_timing_verified_for_canonical_v2":False}
        result["independent_acoustic_methods"]=independent
    result["status"]=independent["status"]
    result["automatic_audio_qa_completed_for_canonical"]=False
    return result

def upload_once(svc,report):
    # Do not overwrite prior evidence, falsely upgrade to approved, or
    # produce an unbounded number of repeated owner-private receipts.
    q=f"'{AUDIO_DIR}' in parents and name = '{NAME}' and trashed = false"
    found=svc.files().list(q=q,
         fields="nextPageToken,files(id,name)",pageSize=100).execute()
    need(not found.get("nextPageToken") and not found.get("files"),
         "PRIVATE_AUDIO_EVIDENCE_ALREADY_EXISTS_DO_NOT_OVERWRITE")
    file_id=issue_ticket.upload(svc,AUDIO_DIR,NAME,report)
    return file_id

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--owner-once",action="store_true",required=True)
    args=p.parse_args()
    try:
        svc=issue_ticket.drive()
        report=audit(svc)
        new_id=upload_once(svc,report)
        print(json.dumps({
          "status":report["status"],
          "source_bytes_verified":report.get("source_bytes_verified",False),
          "audio_report_saved_privately":True,
          "canonical_stage_approved":False,
          "render_started":False,"publication_authorized":False,
          "paid_calls":0
        },sort_keys=True))
        return 0
    except Blocked as exc:
        code=str(exc)
        if not re.fullmatch(r"[A-Z0-9_]{4,90}",code):
            code="ALASKA_AUDIO_EVIDENCE_BLOCKED"
        print("ALASKA_OFFLINE_QA_BLOCKED:"+code,file=sys.stderr)
        return 2
    except Exception:
        print("ALASKA_OFFLINE_QA_INTERNAL_ERROR",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
