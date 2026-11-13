#!/usr/bin/env python3
"""Owner-private, one-time Alaska pronunciation listening excerpts.

Make TWO bounded copies from the unchanged, byte-verified original WAV,
never re-synthesize and never alter the approved full narration. Existing
archived unprompted ASR timings are hints for a human to listen, not
verification/approval. Store separate WAVs and redacted manifest in original
owner-only Drive audio folder, with source SHA and non-render guards.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import io
import json
import re
import sys
import wave

import alaska_private_medium_asr as original

# Original previously archived ASR word-window approximations, seconds.
# These are listening CONTEXT, not verified word-level subtitles.
SLICES=(
    ("Alaska_v2_QA_word22.wav",11.75,13.55,22),
    ("Alaska_v2_QA_word26.wav",14.45,16.40,26),
)
RECEIPT="Alaska_v2_two_phrase_listening_review_v1.json"


def checked_excerpt(raw, start, end):
    if type(raw) is not bytes or not 4096<len(raw)<=original.MAX_WAV:
        raise original.Blocked("QA_ORIGINAL_WAV_INVALID")
    try:
        with wave.open(io.BytesIO(raw),"rb") as source:
            rate=source.getframerate()
            channels=source.getnchannels()
            width=source.getsampwidth()
            frames=source.getnframes()
            original.need(rate==24000 and channels==1 and width==2
                          and source.getcomptype()=="NONE",
                          "QA_AUDIO_NOT_ORIGINAL_PCM")
            first=int(round(start*rate));last=int(round(end*rate))
            original.need(0<=first<last<=frames and last-first<=4*rate,
                          "QA_LISTENING_WINDOW_OUT_OF_RANGE")
            source.setpos(first)
            selection=source.readframes(last-first)
            original.need(len(selection)==(last-first)*channels*width,
                          "QA_EXCERPT_SOURCE_BYTES_MISSING")
        out=io.BytesIO()
        with wave.open(out,"wb") as clip:
            clip.setnchannels(channels)
            clip.setsampwidth(width)
            clip.setframerate(rate)
            clip.writeframes(selection)
        data=out.getvalue()
        original.need(4096<=len(data)<300_000,
                      "QA_EXCERPT_NOT_BOUNDED")
        return data
    except original.Blocked:
        raise
    except (ValueError,TypeError,OSError,EOFError,wave.Error):
        raise original.Blocked("QA_ORIGINAL_WAV_DECODE_FAILED") from None


def owner_only(svc, file_id):
    try:
        p=svc.permissions().list(
            fileId=file_id,fields="nextPageToken,permissions(type,role)",
            pageSize=100).execute()
        valid=(not p.get("nextPageToken")
               and isinstance(p.get("permissions"),list)
               and len(p["permissions"])==1
               and p["permissions"][0].get("type")=="user"
               and p["permissions"][0].get("role")=="owner")
        original.need(valid,"QA_DRIVE_NOT_OWNER_ONLY")
    except original.Blocked:
        raise
    except Exception:
        raise original.Blocked("QA_DRIVE_PERMISSIONS_UNAVAILABLE") from None


def save_private_once(svc,name,raw,mime):
    folder=original.AUDIO_DIR
    original.need(re.fullmatch(r"Alaska_v2_[A-Za-z0-9_]+\.(?:json|wav)",name),
                  "QA_PRIVATE_FILE_NAME_INVALID")
    owner_only(svc,folder)
    result=svc.files().list(
        q=f"'{folder}' in parents and name = '{name}' and trashed = false",
        pageSize=100,fields="nextPageToken,files(id,name)").execute()
    found=result.get("files") or []
    original.need(not result.get("nextPageToken") and len(found)<=1,
                  "QA_DUPLICATE_PRIVATE_EVIDENCE")
    if found:
        fid=found[0]["id"]
        owner_only(svc,fid)
        try:
            old=svc.files().get_media(fileId=fid).execute()
        except Exception:
            raise original.Blocked("QA_PRIVATE_EVIDENCE_READBACK_FAILED") from None
        original.need(old==raw,"QA_PRIVATE_EVIDENCE_COLLISION")
        return fid
    from googleapiclient.http import MediaIoBaseUpload
    uploaded=svc.files().create(
        body={"name":name,"parents":[folder],"mimeType":mime},
        media_body=MediaIoBaseUpload(io.BytesIO(raw),mimetype=mime,
                                     resumable=False),
        fields="id,name,parents,mimeType,size").execute()
    fid=uploaded.get("id")
    original.need(isinstance(fid,str),"QA_PRIVATE_UPLOAD_FAILED")
    owner_only(svc,fid)
    try:
        verified=svc.files().get_media(fileId=fid).execute()
    except Exception:
        raise original.Blocked("QA_PRIVATE_EVIDENCE_READBACK_FAILED") from None
    original.need(verified==raw and uploaded.get("parents")==[folder]
                  and uploaded.get("name")==name
                  and uploaded.get("mimeType")==mime,
                  "QA_PRIVATE_EVIDENCE_READBACK_MISMATCH")
    return fid


def audit(svc):
    original_wav=original.read_private(
        svc,original.WAV_ID,original.AUDIO_DIR,"WarmBaritone.wav",
        original.WAV_SHA,original.MAX_WAV,
        {"audio/x-wav","audio/wav","audio/wave"})
    owner_only(svc,original.WAV_ID)
    original.inspect_wav(original_wav)
    entries=[]
    for name,start,end,index in SLICES:
        sample=checked_excerpt(original_wav,start,end)
        fid=save_private_once(svc,name,sample,"audio/x-wav")
        entries.append({
            "approved_word_index":index,
            "private_clip_file_id":fid,
            "clip_sha256":hashlib.sha256(sample).hexdigest(),
            "approximate_context_start_s":start,
            "approximate_context_end_s":end,
            "reference_time_source":"HISTORICAL_ASR_APPROXIMATE_ONLY",
            "human_pronunciation_checked":False
        })
    document={
        "schema":"bontours.studio.private-targeted-listening/v1",
        "project_id":original.PROJECT,
        "status":"TWO_SHORT_OWNER_ONLY_LISTENING_EXCERPTS_READY_UNREVIEWED",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "original_wav_sha256":original.WAV_SHA,
        "clips":entries,
        "owner_v2_voice_music_lock_approved":False,
        "audio_alignment_verified_auto":False,
        "owner_edit_choice_approved":False,
        "render_authorized":False,
        "auto_publish":False,
        "paid_calls":0
    }
    # The file list itself stays private. The receipt contains NO tokens.
    receipt_raw=json.dumps(document,ensure_ascii=False,
                           sort_keys=True,separators=(",",":")).encode()
    save_private_once(svc,RECEIPT,receipt_raw,"application/json")
    return {"status":document["status"],"clip_count":len(entries),
            "render_authorized":False,"owner_review_recorded":False,
            "paid_calls":0}


def main():
    try:
        result=audit(original.issue_ticket.drive())
        print(json.dumps(result,sort_keys=True))
        return 0
    except original.Blocked as exc:
        code=str(exc)
        if not re.fullmatch(r"[A-Z0-9_]{4,90}",code):
            code="QA_TARGETED_REVIEW_BLOCKED"
        print("ALASKA_AUDIO_REVIEW_BLOCKED:"+code,file=sys.stderr)
        return 2
    except Exception:
        print("ALASKA_AUDIO_REVIEW_INTERNAL_ERROR",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
