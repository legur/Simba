#!/usr/bin/env python3
"""Render source-pinned MotionLab Drive receipt using local free FFmpeg only.

No paid A2E, TTS, stock media, third-party video APIs or publication. Safe by
default: --apply is required to upload a technically validated MP4 to the
owner-only Drive archive. Only exact owner-approved project profiles are renderable.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload
from issue_ticket import drive, LAUNCH_DIR
from notify_montage import INBOX_ID, read_private, validate as validate_receipt, InboxError

ROOT=Path(__file__).resolve().parent
PROFILES=ROOT/"render_profiles"
DONE_FOLDER="1Ya87Y6FUUmstpSs8jG0mKvEVLRqTvwxH"
NAME_SAFE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
HASH=re.compile(r"^[0-9a-f]{64}$")

class RenderError(RuntimeError):pass

def require(ok,reason):
    if not ok:raise RenderError(reason)

def sha_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for part in iter(lambda:f.read(8*1024*1024),b""):
            h.update(part)
    return h.hexdigest()

def md5_file(path):
    h=hashlib.md5()
    with open(path,"rb") as f:
        for part in iter(lambda:f.read(8*1024*1024),b""):h.update(part)
    return h.hexdigest()

def execute(cmd,reason,stdout=False,limit=16000):
    try:
        result=subprocess.run(cmd,check=False,stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE if stdout else subprocess.DEVNULL,
                              stderr=subprocess.PIPE,timeout=1800)
    except (OSError,subprocess.TimeoutExpired):
        raise RenderError(reason+"_UNAVAILABLE_OR_TIMEOUT") from None
    if result.returncode!=0:
        raise RenderError(reason+"_FAILED") from None
    return result.stdout[:limit] if stdout else b""

def get_profile(project):
    require(isinstance(project,str) and NAME_SAFE.fullmatch(project), "INVALID_PROJECT_ID")
    p=PROFILES/(project+".json")
    require(p.is_file(),"NO_OWNER_APPROVED_RENDER_PROFILE")
    d=json.loads(p.read_text(encoding="utf-8"))
    require(d.get("schema")=="bontours.motionlab.free-render-profile/v1"
      and d.get("project_id")==project and d.get("publication_authorized") is False
      and d.get("applied_folder_id")==DONE_FOLDER,"INVALID_RENDER_PROFILE")
    for k in ("input_fingerprint","approved_selection_sha256"):
        require(isinstance(d.get(k),str) and HASH.fullmatch(d[k]),"INVALID_PROFILE_SHA")
    require(isinstance(d.get("approved_receipt_id"),str),"INVALID_PROFILE_RECEIPT")
    f=d.get("render") or {}
    require(f.get("width")==720 and f.get("height")==1280 and f.get("fps")==24
      and f.get("output_width")==1080 and f.get("output_height")==1920
      and f.get("output_fps")==30 and f.get("max_seconds",0)<=60
      and f.get("fade_kind")=="crossfade" and f.get("fade_ms")==900,
      "UNSUPPORTED_RENDER_PROFILE")
    return d

def source_launch(svc,record):
    ticket=read_private(svc,record["ticket_id"],
                        "1lHQS4Pfl3OhDoxeWEL768C-XkBIcCxjs",16000)
    launch_id=ticket.get("source_launch_file_id")
    require(isinstance(launch_id,str) and launch_id,"TICKET_MISSING_SOURCE")
    meta=svc.files().get(fileId=launch_id,
        fields="id,name,parents,trashed,size,mimeType").execute()
    require(meta.get("parents")==[LAUNCH_DIR] and not meta.get("trashed")
      and 0<int(meta.get("size") or 0)<=320000,"UNTRUSTED_SOURCE_LAUNCH")
    raw=svc.files().get_media(fileId=launch_id).execute()
    require(isinstance(raw,bytes) and len(raw)<=320000,"SOURCE_LAUNCH_TOO_BIG")
    actual=hashlib.sha256(raw).hexdigest()
    require(actual==ticket.get("source_launch_sha256"),"SOURCE_LAUNCH_SHA_CHANGED")
    launch=json.loads(raw.decode("utf-8"))
    require(launch.get("schema")=="bontours.motionlab.storyboard.launch/v1"
       and launch.get("project_id")==record["project_id"]
       and launch.get("request_id")==record["session_id"]
       and launch.get("expected_input_fingerprint")==record["source_fingerprint"]
       and launch.get("handoff") is None,"SOURCE_LAUNCH_MISMATCH")
    return launch

def prepare(svc,receipt_file_id):
    record=validate_receipt(svc,receipt_file_id)
    profile=get_profile(record["project_id"])
    selection=record["selection"]
    decision=selection.get("decision") or {}
    require(record["receipt_id"]==profile["approved_receipt_id"]
        and record["selection_sha256"]==profile["approved_selection_sha256"]
        and record["source_fingerprint"]==profile["input_fingerprint"]
        and decision.get("selected_option")==profile["selected_option"],
        "NOT_EXACT_OWNER_APPROVED_SELECTION")
    require(selection.get("format")=="9:16" and
      selection.get("next_stage")=="MONTAGE_PLANNING_REVIEW",
      "UNSUPPORTED_SELECTION_SCOPE")
    require(not selection.get("visual_draft") and not selection.get("visual_layout"),
      "UNIMPLEMENTED_VISUAL_OVERRIDES")
    source=source_launch(svc,record)
    rows=selection.get("scenes") or []
    original=source.get("scenes") or []
    require(len(rows)==len(original)==profile["required_scene_count"],
      "SCENE_COUNT_CHANGED")
    assets=source.get("preview_assets") or []
    lookup={a.get("asset_id"):a for a in assets if isinstance(a,dict)}
    require(len(lookup)==len(assets) and len(assets)<=24,
      "INVALID_PRIVATE_MEDIA_MANIFEST")
    total=0
    for i,(row,base) in enumerate(zip(rows,original)):
        require(row.get("order")==i+1 and row.get("scene_id")==base.get("scene_id")
            and row.get("asset_id")==base.get("asset_id"),
            "SCENE_ORDER_OR_SOURCE_CHANGED")
        d=row.get("duration_seconds")
        require(isinstance(d,(int,float)) and not isinstance(d,bool) and 1<=d<=20
            and abs(float(d)-float(base.get("duration_s",0)))<0.025,
            "SCENE_DURATION_SOURCE_MISMATCH")
        require(row.get("title",{}).get("display_text")==base.get("title_text"),
            "TITLE_APPROVAL_CHANGED")
        require(row.get("camera",{}).get("id")=="cinematic-zoom"
            and row.get("camera",{}).get("intensity_percent")==0,
            "UNIMPLEMENTED_CAMERA_MOVE")
        sub=row.get("subtitles") or {}
        require(sub.get("style_id")=="clean" and sub.get("word_motion_id")=="karaoke"
            and sub.get("preview_text")==base.get("subtitle_preview"),
            "UNIMPLEMENTED_SUBTITLE_VARIANT")
        t=row.get("transition")
        require((i==0 and t is None) or (i>0 and isinstance(t,dict)
            and t.get("id")=="crossfade" and t.get("duration_ms")==900),
            "UNIMPLEMENTED_TRANSITION")
        asset=lookup.get(row["asset_id"])
        require(bool(asset) and asset.get("mime_type")=="video/mp4"
            and isinstance(asset.get("file_id"),str)
            and HASH.fullmatch(asset.get("sha256","")) is not None
            and asset.get("sha256")==base.get("media",{}).get("asset_sha256")
            and 10000<int(asset.get("size_bytes",0))<21*1024*1024,
            "UNTRUSTED_VIDEO_SOURCE")
        total+=float(d)
    require(0<total<=profile["render"]["max_seconds"],"VIDEO_TOO_LONG")
    require(0<len(assets)<=24 and sum(x["size_bytes"] for x in assets)<=120*1024*1024,
        "MEDIA_DOWNLOAD_LIMIT_EXCEEDED")
    audio=profile.get("approved_audio_video") or {}
    require(isinstance(audio.get("drive_file_id"),str) and HASH.fullmatch(audio.get("sha256",""))
      and HASH.fullmatch(audio.get("audio_adts_sha256","")),
      "UNPINNED_APPROVED_AUDIO")
    return {"record":record,"profile":profile,"selection":selection,"launch":source,
            "assets":assets,"duration":total,"file_id":receipt_file_id}

def download(svc,file_id,path,expected_sha,expected_size=None):
    meta=svc.files().get(fileId=file_id,
        fields="id,name,mimeType,parents,trashed,size,md5Checksum").execute()
    require(not meta.get("trashed") and meta.get("mimeType")=="video/mp4"
      and meta.get("parents") and
      (expected_size is None or int(meta.get("size") or 0)==expected_size),
      "PRIVATE_MEDIA_METADATA_MISMATCH")
    fh=open(path,"wb")
    try:
        task=MediaIoBaseDownload(fh,svc.files().get_media(fileId=file_id),
                               chunksize=8*1024*1024)
        done=False
        while not done:
            _,done=task.next_chunk(num_retries=2)
    finally:
        fh.close()
    require(sha_file(path)==expected_sha,"PRIVATE_MEDIA_SHA_MISMATCH")
    return path

def timestamps(sec):
    cent=int(round(float(sec)*100))
    return f"{cent//360000}:{cent//6000%60:02}:{cent//100%60:02}.{cent%100:02}"

def ass_text(t):
    # Prevent arbitrary ASS override text from untrusted selection; only
    # pinned render profile supplies any control tags.
    return str(t).replace("{","").replace("}","").replace("\r","").replace("\n"," ")

def create_ass(profile,output):
    hdr=[
      "[Script Info]","Title: Simba Studio verified Drive renderer",
      "ScriptType: v4.00+","WrapStyle: 2","PlayResX: 720","PlayResY: 1280",
      "ScaledBorderAndShadow: yes","","[V4+ Styles]",
      "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
      "Style: Caption,DejaVu Sans,29,&H00FFFFFF,&H00FFC56E,&HBE101010,&H66000000,1,0,0,0,100,100,0,0,1,2.4,1,2,35,35,145,1",
      "Style: Title,DejaVu Sans,42,&H00FFFFFF,&H00FFFFFF,&HAD000000,&H66000000,1,0,0,0,100,100,0,0,1,3.5,2,8,30,30,76,1",
      "Style: Info,DejaVu Sans,32,&H00FFFFFF,&H00FFFFFF,&HAB000000,&H66000000,1,0,0,0,100,100,0,0,1,3,1,8,30,30,174,1",
      "Style: Price,DejaVu Sans,69,&H00FFC56E,&H00FFFFFF,&HAC000000,&H66000000,1,0,0,0,100,100,0,0,1,3.8,2,8,30,30,196,1",
      "Style: Contact,DejaVu Sans,31,&H00FFFFFF,&H00FFFFFF,&HAC000000,&H66000000,1,0,0,0,100,100,0,0,1,2.5,1,8,30,30,130,1",
      "","[Events]","Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]
    def dialogue(start,end,style,text,layer):
        require(0<=float(start)<float(end)<=60,"BAD_OVERLAY_TIME")
        hdr.append(f"Dialogue: {layer},{timestamps(start)},{timestamps(end)},{style},,0,0,0,,{text}")
    for start,end,words in profile["subtitle_chunks"]:
        chunks=words.split()
        require(0<len(chunks)<=60 and 0<=start<end<=60,"BAD_SUBTITLE_CHUNKS")
        for wi in range(len(chunks)):
            a=start+(end-start)*wi/len(chunks)
            b=start+(end-start)*(wi+1)/len(chunks)
            rich=[("{\\1c&H00FFC56E&}"+ass_text(w)+"{\\1c&H00FFFFFF&}") if i==wi
                  else ass_text(w) for i,w in enumerate(chunks)]
            text=""
            width=0
            for i,w in enumerate(rich):
                n=len(chunks[i])
                if width and width+1+n>34 and "\\N" not in text:
                    text+="\\N";width=n
                else:
                    if text and not text.endswith("\\N"):text+=" "
                    width+=n+1
                text+=w
            dialogue(a,b,"Caption",text,5)
    for a,b,s in profile["title_cues"]:dialogue(a,b,"Title",ass_text(s),9)
    for a,b,style,s in profile["info_cues"]:
        require(style in ("Info","Title","Price","Contact"),"UNSUPPORTED_OVERLAY_STYLE")
        # Position overrides are intentional owner-approved profile text only.
        dialogue(a,b,style,s,10)
    output.write_text("\n".join(hdr)+"\n",encoding="utf-8")
    return output

def video_probe(path):
    raw=execute(["ffprobe","-v","error","-show_entries",
      "format=duration,size:stream=codec_name,width,height,r_frame_rate",
      "-of","json",str(path)],"FFPROBE",stdout=True,limit=24000)
    return json.loads(raw)

def adts_hash(path):
    # Full audio payload read; exact copy of the approved source AAC stream.
    proc=subprocess.Popen(["ffmpeg","-hide_banner","-loglevel","error",
       "-nostdin","-i",str(path),"-map","0:a:0","-c:a","copy",
       "-f","adts","pipe:1"],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    sha=hashlib.sha256()
    for block in iter(lambda:proc.stdout.read(128*1024),b""):sha.update(block)
    if proc.wait(timeout=40)!=0:raise RenderError("AAC_EXTRACTION_FAILED")
    return sha.hexdigest()

def render(plan,folder):
    selection=plan["selection"];profile=plan["profile"];settings=profile["render"]
    fps=settings["fps"];w=settings["width"];h=settings["height"]
    scenes=selection["scenes"];fade=settings["fade_ms"]/1000
    assets={x["asset_id"]:x for x in plan["assets"]}
    cache={}
    svc=plan["svc"]
    for key,a in assets.items():
        dest=folder/("src_"+hashlib.sha256(key.encode()).hexdigest()[:12]+".mp4")
        cache[key]=download(svc,a["file_id"],dest,a["sha256"],a["size_bytes"])
    audio=profile["approved_audio_video"]
    approved=download(svc,audio["drive_file_id"],folder/"approved_audio_reference.mp4",audio["sha256"])
    require(adts_hash(approved)==audio["audio_adts_sha256"],
            "APPROVED_AUDIO_BITSTREAM_CHANGED")
    for i,s in enumerate(scenes):
        duration=float(s["duration_seconds"])
        wanted=duration+(fade/2 if i in (0,len(scenes)-1) else fade)
        media=next(x for x in plan["launch"]["scenes"] if x["scene_id"]==s["scene_id"])["media"]
        base=float(media["duration_s"])
        require(0.5<base<30,"ORIGINAL_CLIP_DURATION_INVALID")
        ratio=wanted/base
        filter_expr=(f"[0:v]split=2[bgsrc][fgsrc];"
             f"[bgsrc]scale={w}:{h}:force_original_aspect_ratio=increase,"
             f"crop={w}:{h},boxblur=16:6[bg];"
             f"[fgsrc]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
             f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,"
             f"format=yuv420p,setsar=1,setpts=(PTS-STARTPTS)*{ratio:.8f},"
             f"fps={fps},tpad=stop_mode=clone:stop_duration=0.20,"
             f"trim=duration={wanted:.5f},setpts=PTS-STARTPTS[v]")
        dest=folder/f"scene_{i:02}.mp4"
        execute(["ffmpeg","-hide_banner","-nostdin","-loglevel","error","-y",
            "-i",str(cache[s["asset_id"]]),"-filter_complex",filter_expr,
            "-map","[v]","-an","-c:v","libx264","-preset","veryfast",
            "-crf","20","-pix_fmt","yuv420p","-threads","2","-r",str(fps),
            "-movflags","+faststart",str(dest)],"SCENE_RENDER")
    ff=["ffmpeg","-hide_banner","-nostdin","-loglevel","error","-y",
        "-filter_complex_threads","2"]
    for i in range(len(scenes)):ff+=["-i",str(folder/f"scene_{i:02}.mp4")]
    parts=[];cumulative=float(scenes[0]["duration_seconds"])
    for i in range(1,len(scenes)):
        incoming=f"[{i}:v]";outgoing="[0:v]" if i==1 else f"[x{i-1}]"
        off=cumulative-fade/2
        parts.append(f"{outgoing}{incoming}xfade=transition=fade:duration={fade:.3f}:offset={off:.5f}[x{i}]")
        cumulative+=float(scenes[i]["duration_seconds"])
    blend=folder/"xfade_approved.mp4"
    ff+=["-filter_complex",";".join(parts),"-map",f"[x{len(scenes)-1}]",
          "-an","-t",str(plan["duration"]),"-r",str(fps),"-c:v","libx264",
          "-preset","veryfast","-crf","19","-pix_fmt","yuv420p",
          "-threads","2","-movflags","+faststart",str(blend)]
    execute(ff,"TRANSITIONS")
    caption=create_ass(profile,folder/"captions.ass")
    out=folder/"studio_render.mp4"
    subtitle=(f"[0:v]drawbox=x=0:y=1055:w=720:h=225:color=black@0.31:t=fill,"
      f"ass=filename={caption}:fontsdir=/usr/share/fonts/truetype/dejavu,"
      f"scale={settings['output_width']}:{settings['output_height']}:flags=lanczos,"
      f"fps={settings['output_fps']},format=yuv420p[v]")
    execute(["ffmpeg","-hide_banner","-nostdin","-loglevel","error","-y",
       "-i",str(blend),"-i",str(approved),"-filter_complex",subtitle,
       "-map","[v]","-map","1:a:0","-c:v","libx264","-preset","medium",
       "-crf","19","-pix_fmt","yuv420p","-threads","3","-r",
       str(settings["output_fps"]),"-c:a","copy","-t",str(plan["duration"]),
       "-movflags","+faststart",str(out)],"FINAL_RENDER")
    return out,approved

def qa_video(plan,video,reference):
    probe=video_probe(video)
    streams=probe.get("streams") or []
    require(any(s.get("codec_name")=="h264" and s.get("width")==1080
       and s.get("height")==1920 for s in streams),"OUTPUT_VIDEO_SHAPE_CHANGED")
    require(any(s.get("codec_name")=="aac" for s in streams),
       "MISSING_APPROVED_AUDIO")
    require(abs(float(probe.get("format",{}).get("duration",0))-plan["duration"])<0.15,
       "OUTPUT_TIMELINE_MISMATCH")
    require(video.stat().st_size>200000 and video.stat().st_size<180*1024*1024,
       "OUTPUT_FILE_SIZE_INVALID")
    execute(["ffmpeg","-hide_banner","-nostdin","-loglevel","error",
      "-i",str(video),"-f","null","-"],"FULL_DECODE")
    output_audio_sha=adts_hash(video)
    require(output_audio_sha==plan["profile"]["approved_audio_video"]["audio_adts_sha256"],
            "AUDIO_NOT_BIT_IDENTICAL")
    # Black detection is technical advisory; brief transition darkness is not
    # proof of corruption, so record without a false unconditional PASS claim.
    analyze=subprocess.run(["ffmpeg","-hide_banner","-nostdin","-loglevel",
       "info","-i",str(video),"-vf","blackdetect=d=0.5:pix_th=0.10",
       "-an","-f","null","-"],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
       timeout=120,check=False)
    black=[line for line in analyze.stderr.decode("utf-8","replace").splitlines()
             if "black_start:" in line]
    receipt=plan["record"];selected=plan["selection"]
    return {
      "schema":"bontours.motionlab.drive-automated-render/v1",
      "project_id":receipt["project_id"],"session_id":receipt["session_id"],
      "receipt_id":receipt["receipt_id"],
      "selection_sha256":receipt["selection_sha256"],
      "source_fingerprint":receipt["source_fingerprint"],
      "rendered_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "chosen_option":selected["decision"]["selected_option"],
      "scenes":len(selected["scenes"]),"transitions":len(selected["scenes"])-1,
      "transition_id":"crossfade","transition_ms":900,
      "source_assets_verified":len(plan["assets"]),
      "approved_audio_sha256":output_audio_sha,
      "sha256":sha_file(video),"md5":md5_file(video),
      "bytes":video.stat().st_size,"duration_seconds":float(probe["format"]["duration"]),
      "output_format":"1080x1920 H264/AAC","technical_decode":"PASS",
      "black_intervals_at_least_0_5_seconds":black[:20],
      "word_timings":plan["profile"]["subtitle_alignment"],
      "qa":"TECHNICAL_PASS_REQUIRES_FINAL_OWNER_REVIEW",
      "published":False,"paid_calls":0,"auto_publish":False,
      "canonical_render_applied":False
    }

def upload_checked(svc,folder,name,path,mime):
    quoted=name.replace("\\","\\\\").replace("'","\\'")
    q=f"'{folder}' in parents and name = '{quoted}' and trashed = false"
    matches=svc.files().list(q=q,fields="files(id,name,size,md5Checksum,parents,mimeType),nextPageToken",pageSize=100).execute()
    require(not matches.get("nextPageToken") and len(matches.get("files",[]))<=1,
      "DUPLICATE_OR_UNBOUNDED_ARCHIVE_FILE")
    expected_md5=md5_file(path)
    expected_size=path.stat().st_size
    if matches.get("files"):
        meta=matches["files"][0]
        require(int(meta.get("size") or 0)==expected_size
            and meta.get("md5Checksum")==expected_md5
            and meta.get("parents")==[folder],
            "ARCHIVE_NAME_COLLISION_WITH_DIFFERENT_CONTENT")
        return meta["id"],True
    media=MediaFileUpload(str(path),mimetype=mime,resumable=True,chunksize=8*1024*1024)
    request=svc.files().create(body={"name":name,"parents":[folder],
        "mimeType":mime},media_body=media,fields="id,name,size,md5Checksum,parents,mimeType")
    response=None
    while response is None:
        _,response=request.next_chunk(num_retries=2)
    require(int(response.get("size") or 0)==expected_size
       and response.get("md5Checksum")==expected_md5 and
       response.get("parents")==[folder], "DRIVE_UPLOAD_READBACK_MISMATCH")
    return response["id"],False

def secure_destination(svc,folder):
    folder_meta=svc.files().get(fileId=folder,
                   fields="id,mimeType,trashed").execute()
    require(folder_meta.get("mimeType")=="application/vnd.google-apps.folder"
         and not folder_meta.get("trashed"),"INVALID_PRIVATE_ARCHIVE_FOLDER")
    perms=svc.permissions().list(fileId=folder,fields="permissions(type,role)",pageSize=100).execute()
    require(all(p.get("type") not in ("anyone","domain") for p in perms.get("permissions",[])),
       "ARCHIVE_FOLDER_HAS_PUBLIC_OR_DOMAIN_ACCESS")

def apply(svc,plan,video,qa,path):
    out=plan["profile"]["archive_folder_id"]
    require(out and out!=INBOX_ID and out!=DONE_FOLDER,"UNSAFE_OUTPUT_FOLDER")
    secure_destination(svc,out)
    secure_destination(svc,DONE_FOLDER)
    stem="Alaska_Studio_Auto_"+plan["record"]["receipt_id"][:8]
    video_id,reuse=upload_checked(svc,out,stem+".mp4",video,"video/mp4")
    qa.update({"drive_video_file_id":video_id,
               "private_video_name":stem+".mp4",
               "receipt_drive_file_id":plan["file_id"]})
    qa_path=path/"render_qa.json"
    qa_path.write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    qa_id,_=upload_checked(svc,out,stem+"_QA.json",qa_path,"application/json")
    archive={"schema":"bontours.motionlab.drive-render-receipt/v1",
       "status":"RENDERED_PENDING_OWNER_REVIEW",
       "project_id":plan["record"]["project_id"],
       "receipt_id":plan["record"]["receipt_id"],
       "selection_sha256":plan["record"]["selection_sha256"],
       "video_file_id":video_id,"qa_file_id":qa_id,
       "video_sha256":qa["sha256"],"published":False}
    raw=json.dumps(archive,ensure_ascii=False,separators=(",",":")).encode()
    raw_path=path/"render_record.json";raw_path.write_bytes(raw)
    receipt_file_id,_=upload_checked(svc,DONE_FOLDER,
                "motionlab-"+plan["record"]["receipt_id"]+"-render.json",
                raw_path,"application/json")
    props={"motionlab_render_status":"RENDERED_PENDING_OWNER_REVIEW",
       "motionlab_video_file_id":video_id,"motionlab_qa_file_id":qa_id,
       "motionlab_record_id":receipt_file_id}
    svc.files().update(fileId=plan["file_id"],body={"appProperties":props},
                      fields="id,appProperties").execute()
    return {"status":"RENDERED_PENDING_OWNER_REVIEW","video_file_id":video_id,
       "qa_file_id":qa_id,"render_record_id":receipt_file_id,
       "sha256":qa["sha256"],"uploaded_reused":reuse}

def run(svc,receipt_file_id,do_apply=False):
    plan=prepare(svc,receipt_file_id)
    plan["svc"]=svc
    require(os.environ.get("MOTIONLAB_NO_PAID_APIS","true")=="true",
        "NONFREE_RUNTIME_DISABLED")
    data={"receipt_id":plan["record"]["receipt_id"],
          "project_id":plan["record"]["project_id"],
          "selected_option":plan["selection"]["decision"]["selected_option"],
          "scene_count":len(plan["selection"]["scenes"]),
          "verified":True,"performed_paid_operations":False}
    if not do_apply:return {**data,"status":"VALIDATED_NOT_RENDERED"}
    receipt_meta=svc.files().get(fileId=receipt_file_id,
        fields="id,appProperties,parents").execute()
    app=receipt_meta.get("appProperties") or {}
    if app.get("motionlab_render_status")=="RENDERED_PENDING_OWNER_REVIEW":
        require(app.get("motionlab_video_file_id") and app.get("motionlab_qa_file_id"),
          "INCONSISTENT_PRIOR_RENDER")
        return {**data,"status":"ALREADY_RENDERED",
            "video_file_id":app["motionlab_video_file_id"],
            "qa_file_id":app["motionlab_qa_file_id"]}
    with tempfile.TemporaryDirectory(prefix="simba-studio-") as tmp:
        temp=Path(tmp)
        movie,ref=render(plan,temp)
        qa=qa_video(plan,movie,ref)
        stored=apply(svc,plan,movie,qa,temp)
    return {**data,**stored}

def pending(svc):
    page=None
    while True:
        kw={"q":f"'{INBOX_ID}' in parents and trashed = false",
            "fields":"nextPageToken,files(id,appProperties)","pageSize":100}
        if page:kw["pageToken"]=page
        res=svc.files().list(**kw).execute()
        for f in res.get("files",[]):
            if not (f.get("appProperties") or {}).get("motionlab_render_status"):
                yield f["id"]
        page=res.get("nextPageToken")
        if not page:break

def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--apply",action="store_true")
    arg.add_argument("--receipt-file-id")
    args=arg.parse_args()
    require(sys.version_info>=(3,11),"PYTHON_TOO_OLD")
    svc=drive()
    report={"processed":0,"rendered":0,"skipped_unconfigured":0,"blocked":0,
            "dry_run":not args.apply,"paid_operations":0}
    targets=[args.receipt_file_id] if args.receipt_file_id else list(pending(svc))
    for fid in targets:
        try:
            result=run(svc,fid,do_apply=args.apply)
            print("MOTIONLAB_RENDER_RESULT",json.dumps(result,sort_keys=True))
            report["processed"]+=1
            if result["status"]=="RENDERED_PENDING_OWNER_REVIEW":report["rendered"]+=1
        except RenderError as e:
            if str(e)=="NO_OWNER_APPROVED_RENDER_PROFILE" and not args.receipt_file_id:
                report["skipped_unconfigured"]+=1
            else:
                report["blocked"]+=1
                print("MOTIONLAB_RENDER_BLOCKED",str(e),file=sys.stderr)
        except (InboxError,ValueError,KeyError,TypeError,OSError) as e:
            report["blocked"]+=1
            print("MOTIONLAB_RENDER_BLOCKED",type(e).__name__,file=sys.stderr)
    print("MOTIONLAB_RENDER_SUMMARY",json.dumps(report,sort_keys=True))
    return 2 if report["blocked"] else 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except RenderError as e:
        print("MOTIONLAB_RENDER_BLOCKED",str(e),file=sys.stderr)
        raise SystemExit(2) from None
