#!/usr/bin/env python3
"""Zero-paid mix of existing approved Simba WarmBaritone WAVs with the Studio visual preview.

Not a production master: no verified word alignment, temp ORIGINAL synthesized
music, no publication. All inputs must exist privately on Drive with exact SHA.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import issue_ticket
import render_vietnam_selected_preview as visual

VISUAL_ID = "1ZvLpf5C579kK53fDGZZL2h1qLUV4L8yr"
VISUAL_SHA = "78789de8af96f241eb63a4db36a6ccb93ccae4e315ba8360ee9feb8bda36c3ba"
VISUAL_SIZE = 24086079
WAV_FOLDER = "1eRMI2qNpDntv057rfwwznDsxF5HCk-P0"
FILES = [
 ("1eDH5Nv3fcnGlgiZrJFEnaUSsIDocmD4J", "Simba_voice_issue_210.wav",
  "9bd2c1d171c8dde56395ea99aa5953b25d2b7a2fef1ddd97aeb7beac3727f2fe", 1345948, 27.88),
 ("1G3YAmv610UywU_jZIXVC_bprFRRPQRNo", "Simba_voice_issue_211.wav",
  "54023c2497f7c83caa50bcbded44ba3af61ccad33ac9f3936c93c08a4bbb5044", 1059868, 21.92),
]
OUT_NAME = "VietCamb_option2_WarmBaritone_AUDIO_DRAFT_NO_PUBLISH_0847854b1353.mp4"
DURATION = 42.75


class AudioPreviewError(RuntimeError):
    pass


def must(x, code):
    if not x:
        raise AudioPreviewError(code)


def run_ffmpeg(args, code, limit=240):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]
        + args, capture_output=True, timeout=limit)
    if p.returncode:
        raise AudioPreviewError(code)


def get_media(drive, file_id, destination, folder, sha, byte_size, mime):
    meta = drive.files().get(fileId=file_id,
        fields="id,name,mimeType,parents,size,trashed,permissions(type,role),appProperties").execute(num_retries=2)
    must(not meta.get("trashed") and meta.get("parents") == [folder]
         and int(meta.get("size", 0)) == byte_size
         and meta.get("mimeType") == mime, "PRIVATE_MEDIA_CHANGED")
    must(not any(p.get("type") != "user" for p in meta.get("permissions", [])),
         "MEDIA_SHARING_NOT_PRIVATE")
    with destination.open("xb") as file:
        job = MediaIoBaseDownload(file, drive.files().get_media(fileId=file_id), chunksize=4*1024*1024)
        done = False
        while not done:
            _, done = job.next_chunk(num_retries=2)
    must(visual.sha(destination) == sha, "MEDIA_CONTENT_SHA_CHANGED")
    return meta


def music(path):
    """Simple original synthesized pad/pluck backing for audition only, no licensed samples."""
    rate = 24000
    duration = DURATION
    chord = [
        (220.0, 277.18, 329.63),
        (196.0, 246.94, 293.66),
        (174.61, 220.0, 261.63),
        (196.0, 246.94, 329.63),
    ]
    block = bytearray()
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        for i in range(round(duration*rate)):
            t=i/rate
            f=chord[int(t/3.18)%4]
            # Quiet harmonics, a slow pulse and transient; normalized below full-scale.
            tone=(math.sin(2*math.pi*f[0]*t)
                 +.6*math.sin(2*math.pi*f[1]*t)
                 +.5*math.sin(2*math.pi*f[2]*t))
            attack=min(1.,t/1.15)
            tail=min(1.,max(0.,(duration-t)/1.3))
            gentle_pulse=.78+.22*math.sin(2*math.pi*.28*t)**2
            v=max(-.9,min(.9,tone*.018*attack*tail*gentle_pulse))
            block.extend(struct.pack("<h",int(v*32767)))
            if len(block)>96_000:
                target.writeframesraw(block);block.clear()
        if block:target.writeframesraw(block)


ASS = r"""[Script Info]
Title: Studio VN/Cambodia 2027 option 2 voiced audition only
ScriptType: v4.00+
PlayResX: 540
PlayResY: 960
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Header,DejaVu Sans,23,&H00FFFFFF,&H00FFFFFF,&H98000000,&H8A000000,1,0,0,0,100,100,0,0,1,2.5,2,5,15,15,10,1
Style: Footer,DejaVu Sans,24,&H00FFFFFF,&H00FFFFFF,&H97000000,&H85000000,1,0,0,0,100,100,0,0,1,2.4,2,5,15,15,10,1
Style: Draft,DejaVu Sans,13,&H00DDDDDD,&H00DDDDDD,&H70000000,&H8A000000,0,0,0,0,100,100,0,0,1,1,1,8,8,8,8,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 3,0:00:00.05,0:00:42.70,Draft,,0,0,0,,{\an8\pos(270,45)}ПРЕДПРОСМОТР  •  СИНХРОНИЗАЦИЯ НА ПРОВЕРКЕ
Dialogue: 7,0:00:17.30,0:00:24.10,Header,,0,0,0,,{\an5\pos(270,143)\fad(250,230)}12–29 ЯНВАРЯ 2027\NETIHAD ЧЕРЕЗ АБУ-ДАБИ
Dialogue: 7,0:00:27.10,0:00:35.65,Header,,0,0,0,,{\an5\pos(270,142)\fad(250,230)}$4 950  /  1 ЧЕЛОВЕК\N+$1 030  /  ОДНОМЕСТНЫЙ
Dialogue: 7,0:00:34.00,0:00:42.70,Footer,,0,0,0,,{\an5\pos(270,665)\fad(250,230)}НАПИШИТЕ «ВЬЕТНАМ»\N058-677-8492
"""


def look_for_existing(drive, sha1, sha2):
    q = f"'{visual.ARCHIVE}' in parents and name = '{OUT_NAME}' and trashed = false"
    rows = drive.files().list(q=q,
        fields="nextPageToken,files(id,name,size,parents,appProperties,md5Checksum)",
        pageSize=20).execute(num_retries=2)
    must(not rows.get("nextPageToken") and len(rows.get("files", [])) <= 1,
         "OUTPUT_IDEMPOTENCE_CHECK_FAILED")
    if not rows.get("files"):
        return None
    m=rows["files"][0]
    props=m.get("appProperties") or {}
    must(props.get("voice1_sha256")==sha1 and
         props.get("voice2_sha256")==sha2 and
         props.get("selection_sha256")==
         "0847854b1353655904fc5459ef5b65e54c5739b33b2adf45daf47ebcbccebf10" and
         props.get("preview_only")=="true" and props.get("final_master")=="false",
         "EXISTING_OUTPUT_OTHER_INPUTS")
    return m


def execute():
    drive = issue_ticket.drive()
    record, launch, clips = visual.read_project(drive)
    must(record["receipt_id"]=="14481802-0761-4ebd-bfbb-886a52f5f524",
         "STUDIO_SELECTION_RECEIPT_CHANGED")
    existing=look_for_existing(drive, FILES[0][2],FILES[1][2])
    if existing:
        return {"status":"AUDIO_DRAFT_ALREADY_ARCHIVED",
                "drive_file_id":existing["id"],"new_paid_calls":0,"published":False}
    with tempfile.TemporaryDirectory(prefix="vn-camb-owner-audio-audition-") as tmp:
        tmp=Path(tmp)
        picture=tmp/"verified_video.mp4"
        meta=get_media(drive,VISUAL_ID,picture,visual.ARCHIVE,VISUAL_SHA,VISUAL_SIZE,"video/mp4")
        props=meta.get("appProperties") or {}
        must(props.get("preview_only")=="true" and
             props.get("receipt_id")==record["receipt_id"],
             "VISUAL_NOT_SOURCE_PINNED")
        voices=[]
        for i,(fid,name,expected,bytes_count,duration) in enumerate(FILES):
            path=tmp/name
            get_media(drive,fid,path,WAV_FOLDER,expected,bytes_count,"audio/wav")
            info=visual.fp(path)
            must(abs(float(info["format"]["duration"])-duration)<.1,
                 "VOICE_WAV_DURATION_CHANGED")
            voices.append(path)

        joined=tmp/"joined_voice.wav"
        run_ffmpeg(["-i",str(voices[0]),"-f","lavfi","-t",".35",
               "-i","anullsrc=r=24000:cl=mono","-i",str(voices[1]),
               "-filter_complex",
               "[0:a][1:a][2:a]concat=n=3:v=0:a=1,atempo=1.185,"
               "aresample=48000,adelay=200|200[a]",
               "-map","[a]","-c:a","pcm_s16le",str(joined)],
               "NARRATION_MIX_FAILED")
        duration=float(visual.fp(joined)["format"]["duration"])
        must(41.5 < duration < DURATION, "NARRATION_DOES_NOT_FIT")
        score=tmp/"original_temp_score.wav"
        music(score)
        audio=tmp/"with_voice.mp4"
        run_ffmpeg(["-i",str(picture),"-i",str(joined),"-i",str(score),
              "-filter_complex",
              "[1:a]volume=1.0,apad,atrim=duration=42.75[voice];"
              "[2:a]volume=0.35,apad,atrim=duration=42.75[music];"
              "[voice][music]amix=inputs=2:duration=first:normalize=0,"
              "alimiter=limit=0.91:attack=4:release=60[aout]",
              "-map","0:v:0","-map","[aout]","-c:v","copy",
              "-c:a","aac","-b:a","192k","-ar","48000","-ac","2",
              "-movflags","+faststart",str(audio)],"AUDIO_JOIN_FAILED")
        subtitle=tmp/"timing_approximate.ass"
        subtitle.write_text(ASS,encoding="utf8")
        out=tmp/OUT_NAME
        run_ffmpeg(["-i",str(audio),"-vf","ass="+str(subtitle),
              "-map","0:v:0","-map","0:a:0",
              "-c:v","libx264","-preset","veryfast","-crf","22",
              "-threads","4","-pix_fmt","yuv420p","-c:a","copy",
              "-movflags","+faststart",str(out)],"VOICE_PREVIEW_RENDER_FAILED")
        probe=visual.fp(out)
        must(any(x["codec_type"]=="audio" for x in probe["streams"])
             and any(x["codec_type"]=="video" for x in probe["streams"])
             and abs(float(probe["format"]["duration"])-DURATION)<.15,
             "VOICE_PREVIEW_QA_FAIL")
        # One-attempt private Drive archival. No overwrites and no retry on
        # ambiguous upload, preserving both paid TTS attempts as immutable.
        sha=visual.sha(out)
        metadata={"name":OUT_NAME,"mimeType":"video/mp4","parents":[visual.ARCHIVE],
            "description":"Option 2 voice audition only; subtitle timings unverified, temporary original score.",
            "appProperties":{
                "preview_only":"true","final_master":"false","voice_profile":"WarmBaritone",
                "receipt_id":record["receipt_id"],
                "selection_sha256":record["selection_sha256"],
                "voice1_sha256":FILES[0][2],"voice2_sha256":FILES[1][2],
                "source_preview_sha256":VISUAL_SHA,"output_sha256":sha}}
        from googleapiclient.http import MediaFileUpload
        try:
            req=drive.files().create(body=metadata,
              media_body=MediaFileUpload(str(out),mimetype="video/mp4",
                                        chunksize=4*1024*1024,resumable=True),
              fields="id,name,size,parents,appProperties")
            uploaded=None
            while uploaded is None:
                _,uploaded=req.next_chunk(num_retries=2)
        except Exception:
            raise AudioPreviewError("UPLOAD_UNCERTAIN_NO_AUTOMATIC_RETRY")
        must(uploaded.get("parents")==[visual.ARCHIVE]
             and uploaded.get("name")==OUT_NAME
             and (uploaded.get("appProperties") or {}).get("output_sha256")==sha,
             "PRIVATE_DRIVE_OUTPUT_NOT_VERIFIED")
        return {"status":"AUDIO_DRAFT_ARCHIVED_QA_PASS",
            "drive_file_id":uploaded["id"],"source_clips":10,
            "selected_option":2,"duration_seconds":float(probe["format"]["duration"]),
            "voice":"WarmBaritone","voice_source_ids":[x[0] for x in FILES],
            "voice_source_sha256":[x[2] for x in FILES],
            "audio_preview_duration_seconds":round(duration,3),
            "original_temporary_music":True,
            "subtitle_alignment":"ESTIMATED_ONLY_REQUIRES_ASR_QA",
            "speech_text_spoken_accuracy_verified":False,
            "voice_and_music_owner_final_approval":False,
            "new_paid_calls":0,"published":False,"final_master":False,
            "output_sha256":sha,"bytes":out.stat().st_size}


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--report",required=True,type=Path)
    x=p.parse_args()
    try:
        report=execute();status=0
    except Exception as exc:
        report={"status":"AUDIO_DRAFT_BLOCKED","reason":str(exc)[:120],
                "new_paid_calls":0,"published":False}
        status=2
    x.report.parent.mkdir(parents=True,exist_ok=True)
    x.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print("Vietnam Bon Tours audio audition:",report["status"])
    raise SystemExit(status)
