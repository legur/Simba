#!/usr/bin/env python3
"""Private independent unprompted ASR draft for already generated VN/Cambodia WarmBaritone.

No new TTS, no A2E, no publication, no final word-alignment approval.
Public Whisper weights load before private speech is downloaded.
"""
from __future__ import annotations
import argparse, difflib, hashlib, json, math, re, tempfile
from pathlib import Path
from googleapiclient.http import MediaIoBaseUpload
import io
import issue_ticket
import render_vietnam_selected_preview as visual
import mix_vietnam_approved_voice_preview as mix

DEST=mix.WAV_FOLDER
NAME="VN_CAM_2027_WarmBaritone_unprompted_ASR_DRAFT_0847854b1353.json"

def normalize(text):
    text=str(text).casefold().replace("ё","е")
    return re.findall(r"[^\W_]+(?:-[^\W_]+)*",text,flags=re.UNICODE)

def check_dir(drive):
    folder=drive.files().get(fileId=DEST,
        fields="id,mimeType,trashed,permissions(type,role),capabilities(canAddChildren)").execute(num_retries=2)
    if (folder.get("trashed") or
        folder.get("mimeType")!="application/vnd.google-apps.folder" or
        folder.get("capabilities",{}).get("canAddChildren") is not True or
        any(p.get("type")!="user" for p in folder.get("permissions",[]))):
        raise ValueError("PRIVATE_QA_FOLDER_INVALID")

def fetch_exact(drive, fid, tmp, sha, n):
    from googleapiclient.http import MediaIoBaseDownload
    meta=drive.files().get(fileId=fid,fields="id,size,mimeType,parents,trashed").execute(num_retries=2)
    if meta.get("trashed") or meta.get("parents")!=[DEST] or meta.get("mimeType")!="audio/wav" or int(meta.get("size") or 0)!=n:
        raise ValueError("VOICE_AUDIO_SOURCE_CHANGED")
    with open(tmp,"xb") as stream:
        job=MediaIoBaseDownload(stream,drive.files().get_media(fileId=fid),chunksize=4*1024*1024)
        done=False
        while not done:
            _,done=job.next_chunk(num_retries=2)
    if visual.sha(tmp)!=sha:raise ValueError("VOICE_BYTES_SHA_CHANGED")

def execute():
    # Public model weights only; no user audio leaves this process.
    from faster_whisper import WhisperModel
    model=WhisperModel("small",device="cpu",compute_type="int8")
    drive=issue_ticket.drive()
    check_dir(drive)
    record,launch,_=visual.read_project(drive)
    groups=[record["selection"]["scenes"][:7],record["selection"]["scenes"][7:]]
    keys=[item[2] for item in mix.FILES]
    q="'"+DEST+"' in parents and name = '"+NAME+"' and trashed = false"
    found=drive.files().list(q=q,fields="nextPageToken,files(id,size,parents,appProperties)",pageSize=20).execute(num_retries=2)
    if found.get("nextPageToken") or len(found.get("files",[]))>1:raise ValueError("ASR_IDEMPOTENCE_UNCERTAIN")
    if found.get("files"):
        item=found["files"][0]
        props=item.get("appProperties") or {}
        if props.get("voice_sha1")!=keys[0] or props.get("voice_sha2")!=keys[1]:
            raise ValueError("ASR_SOURCE_COLLISION")
        return {"status":"ASR_DRAFT_ALREADY_SAVED","private_file_id":item["id"],"new_paid_calls":0}

    parts=[]
    with tempfile.TemporaryDirectory(prefix="simba-vn-audio-asr-") as temp:
        for k,item in enumerate(mix.FILES):
            fid,name,sig,size,expected_dur=item
            wav=Path(temp)/name
            fetch_exact(drive,fid,wav,sig,size)
            segments,info=model.transcribe(
                str(wav),language="ru",task="transcribe",beam_size=5,
                word_timestamps=True,condition_on_previous_text=False,
                vad_filter=False,initial_prompt=None,prefix=None)
            segs=list(segments)
            expected=" ".join(row["subtitles"]["preview_text"] for row in groups[k])
            spoken=" ".join(seg.text.strip() for seg in segs)
            a,b=normalize(expected),normalize(spoken)
            ratio=difflib.SequenceMatcher(a=a,b=b,autojunk=False).ratio()
            words=[]
            for seg in segs:
                for word in (seg.words or []):
                    if (word.start is None or word.end is None or
                        not math.isfinite(word.start) or not math.isfinite(word.end)):
                        raise ValueError("WHISPER_WORD_TIMING_MISSING")
                    words.append({"text":word.word.strip(),
                                  "start_ms":round(word.start*1000),
                                  "end_ms":round(word.end*1000),
                                  "probability":round(float(word.probability),4)})
            if not words:raise ValueError("WHISPER_SPEECH_EMPTY")
            parts.append({
                "voice_part":k+1,"voice_file_sha256":sig,
                "approved_text":expected,"recognized_text":spoken,
                "expected_word_count":len(a),"recognized_word_count":len(b),
                "normalized_sequence_ratio":round(ratio,4),
                "language_probability":round(float(info.language_probability),4),
                "confidence_status":"DRAFT_REVIEW_REQUIRED",
                "whisper_segments":[
                  {"start_ms":round(s.start*1000),"end_ms":round(s.end*1000),
                   "avg_logprob":round(float(s.avg_logprob),3),
                   "no_speech_prob":round(float(s.no_speech_prob),3)}
                  for s in segs
                ],"words":words
            })
        document={
            "schema":"simba.vietnam-cambodia.voice-unprompted-asr-draft/v1",
            "project_id":mix.visual.PROJECT,
            "studio_receipt":record["receipt_id"],
            "studio_selection_sha256":record["selection_sha256"],
            "provider":"faster-whisper small CPU (unprompted independent)",
            "speech_files_source_sha256":keys,
            "all_audio_stored_owner_private":True,
            "parts":parts,
            "speech_text_spoken_accuracy_verified":False,
            "forced_alignment_verified":False,
            "final_voice_music_approved":False,
            "render_authorized":False,
            "publication_authorized":False,
            "new_paid_calls":0,
        }
        blob=json.dumps(document,ensure_ascii=False,indent=2).encode("utf8")
        from googleapiclient.http import MediaIoBaseUpload
        media=MediaIoBaseUpload(io.BytesIO(blob),mimetype="application/json",resumable=False)
        created=drive.files().create(body={
            "name":NAME,"mimeType":"application/json","parents":[DEST],
            "appProperties":{"voice_sha1":keys[0],"voice_sha2":keys[1],
                "source_selection":record["selection_sha256"],
                "source_kind":"unprompted_asr_draft"}
        },media_body=media,fields="id,name,size,parents,appProperties").execute(num_retries=0)
        if created.get("parents")!=[DEST] or created.get("size")!=str(len(blob)):
            raise ValueError("ASR_UPLOAD_READBACK_FAILED")
    return {"status":"ASR_DRAFT_SAVED_OWNER_PRIVATE","private_file_id":created["id"],
        "part_1_similarity":parts[0]["normalized_sequence_ratio"],
        "part_2_similarity":parts[1]["normalized_sequence_ratio"],
        "word_alignment_verified":False,"new_paid_calls":0,"published":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    try:result=execute();status=0
    except Exception as error:
        result={"status":"ASR_DRAFT_BLOCKED","reason":str(error)[:130],
                "new_paid_calls":0,"published":False};status=2
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print("Independent VN/Cambodia voice ASR:",result["status"])
    raise SystemExit(status)
