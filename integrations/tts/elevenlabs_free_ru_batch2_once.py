#!/usr/bin/env python3
"""Four ElevenLabs Free-default male voices speaking identical Russian benchmark.

One HTTP POST (no retries) per voice. Hard cap 4 calls and <= 1000 characters.
Use only user's already configured Free API key; no subscription or payment changes.
Audio only; store private Drive MP3; no video and no commercial publishing.
"""
import hashlib
import io
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from run_male_prague import make_drive, claim_once, post_comment, StopTest

VOICES = (
    ("Daniel", "onwK4e9ZLuTAKqWW03F9"),
    ("Chris", "iP95p4xoKVk53GoZ742B"),
    ("Eric", "cjVigY5qzO86Huf0OWal"),
    ("Callum", "N2lVS1w4EtoT3dr4eOWO"),
)
MODEL = "eleven_flash_v2_5"
STAMP = "ELEVENLABS-FREE-RU-DEFAULT-BATCH2-20261107-EXACTLY-ONCE"
ROOT = Path(__file__).resolve().parents[2]
MAX_TOTAL_CHARS = 1000
MAX_MP3_BYTES = 4 * 1024 * 1024


def api_get(url, headers):
    with urlopen(Request(url, headers=headers, method="GET"), timeout=35) as resp:
        return json.load(resp)


def validate_preflight():
    cfg=json.loads((ROOT / "integrations/tts/prague_male_voices.json").read_text(encoding="utf-8"))
    if (cfg.get("voice_gender") != "male_only" or
        cfg["production_voice"].get("profile") != "WarmBaritone" or
        cfg["production_voice"].get("selection_status") != "approved_by_user" or
        not cfg.get("safety",{}).get("no_more_a2e_requests")):
        raise StopTest("Production voice/no-A2E safety gate failed")
    text=cfg.get("text","")
    if not isinstance(text,str) or not 120 <= len(text) <= 250:
        raise StopTest("Benchmark source unexpectedly changed")
    if len(VOICES) != 4 or len(text)*len(VOICES) > MAX_TOTAL_CHARS:
        raise StopTest("Free-tier hard character/request budget exceeded")
    key=os.environ.get("ELEVENLABS_API_KEY","").strip()
    if not key:
        raise StopTest("GitHub ElevenLabs key missing")
    headers={"xi-api-key":key,"Accept":"application/json"}
    sub=api_get("https://api.elevenlabs.io/v1/user/subscription",headers)
    remaining=(sub.get("character_limit") or 0)-(sub.get("character_count") or 0)
    if not isinstance(remaining,int) or remaining < MAX_TOTAL_CHARS:
        raise StopTest("Insufficient credits for strict capped pilot; no paid calls")
    catalog=api_get("https://api.elevenlabs.io/v2/voices?"+
                    urlencode({"voice_type":"default","page_size":100,"include_total_count":"false"}),headers)
    available={v.get("voice_id"):v for v in catalog.get("voices",[]) if isinstance(v,dict)}
    if catalog.get("has_more"):
        raise StopTest("Voice catalog paginated; verify access before generation")
    for name,vid in VOICES:
        info=available.get(vid)
        if not info or str((info.get("labels") or {}).get("gender","")).lower()!="male":
            raise StopTest("Default male voice not currently available: "+name)
    return text,key,remaining


def has_private_file(drive, folder, filename):
    q="name = '"+filename+"' and '"+folder+"' in parents and trashed = false"
    rows=drive.files().list(q=q,fields="files(id,size,parents,shared),nextPageToken",
                            pageSize=20).execute(num_retries=0)
    if rows.get("nextPageToken") or len(rows.get("files",[]))>1:
        raise StopTest("Ambiguous private storage destination")
    if rows.get("files"):
        row=rows["files"][0]
        if row.get("shared") or folder not in row.get("parents",[]) or not int(row.get("size") or 0):
            raise StopTest("Private Drive file exists but cannot be verified")
        return True
    return False


def generate_mp3_once(text, key, voice_id):
    url="https://api.elevenlabs.io/v1/text-to-speech/"+voice_id+"?output_format=mp3_44100_128"
    request={
        "text":text,
        "model_id":MODEL,
        "language_code":"ru",
        "voice_settings":{
            "stability":0.55, "similarity_boost":0.75,
            "style":0.0, "use_speaker_boost":True, "speed":0.96
        }
    }
    req=Request(url,data=json.dumps(request,ensure_ascii=False).encode("utf-8"),
                headers={"xi-api-key":key,"Content-Type":"application/json",
                         "Accept":"audio/mpeg"},method="POST")
    # ONE request only: even after timeouts, billing can be ambiguous.
    with urlopen(req,timeout=150) as response:
        if response.status != 200:
            raise StopTest("ElevenLabs returned non-200")
        blob=response.read(MAX_MP3_BYTES+1)
    if not 3000 < len(blob) <= MAX_MP3_BYTES:
        raise StopTest("Invalid audio size; no retry")
    if not (blob[:3]==b"ID3" or (blob[0]==0xff and blob[1]&0xe0==0xe0)):
        raise StopTest("ElevenLabs returned non-MP3 bytes; no retry")
    return blob


def save_mp3(drive,folder,filename,blob):
    from googleapiclient.http import MediaIoBaseUpload
    media=MediaIoBaseUpload(io.BytesIO(blob),mimetype="audio/mpeg",resumable=True)
    row=drive.files().create(body={
        "name":filename,"mimeType":"audio/mpeg","parents":[folder],
        "description":"Simba private RU TTS comparison; ElevenLabs Free standard voice; "+
                      "NON-COMMERCIAL demo only; not approved for publication",
        "appProperties":{"simba_benchmark":"PRAGUE-STORY-01","voice_test_model":MODEL,
                         "sha256":hashlib.sha256(blob).hexdigest()}
        },media_body=media,fields="id,name,size,md5Checksum,parents,shared").execute(num_retries=0)
    checked=drive.files().get(fileId=row["id"],
                              fields="id,name,size,md5Checksum,parents,shared").execute(num_retries=0)
    if (checked.get("shared") or folder not in checked.get("parents",[]) or
        int(checked.get("size",0))!=len(blob) or
        checked.get("md5Checksum")!=hashlib.md5(blob,usedforsecurity=False).hexdigest()):
        raise StopTest("Private MP3 upload verification failed; do not regenerate")
    return row["id"]


def main():
    text,key,remaining=validate_preflight()
    drive,folder=make_drive()
    results=[]
    total_calls=0
    for name,vid in VOICES:
        filename="PRAGUE-STORY-01_ElevenLabs_Free_"+name+"_ru.mp3"
        try:
            if has_private_file(drive,folder,filename):
                post_comment("ELEVEN-FREE-EXISTS: "+name+" | Private MP3 already stored, no credits spent.")
                results.append({"voice":name,"status":"EXISTING","file":filename})
                continue
            claim_once(STAMP+"-"+vid)
            total_calls+=1
            blob=generate_mp3_once(text,key,vid)
            file_id=save_mp3(drive,folder,filename,blob)
            post_comment("ELEVEN-FREE-SAVED: "+name+" | model="+MODEL+
                         " | "+filename+" | "+str(len(blob))+
                         " bytes | private Drive verified | no retries")
            results.append({"voice":name,"status":"VERIFIED","file":filename,
                            "drive_id":file_id,"bytes":len(blob)})
        except HTTPError as ex:
            status="unknown"
            try:
                detail=json.loads(ex.read(4096).decode("utf-8","replace")).get("detail",{})
                if isinstance(detail,dict):
                    candidate=detail.get("status")
                    if isinstance(candidate,str) and re.fullmatch(r"[a-z_]{3,50}",candidate):
                        status=candidate
            except Exception:
                pass
            post_comment("ELEVEN-FREE-FAILED-STOP: "+name+" | HTTP "+str(ex.code)+
                         " | status="+status+" | No retries; other voices not attempted")
            results.append({"voice":name,"status":"FAILED","http":ex.code,
                            "error_status":status})
            break
        except Exception as ex:
            post_comment("ELEVEN-FREE-FAILED-STOP: "+name+" | "+type(ex).__name__+
                         " | No retries, other voices not attempted")
            results.append({"voice":name,"status":"FAILED","reason":type(ex).__name__})
            break
    post_comment("ELEVEN-FREE-SUMMARY: "+
                 json.dumps({"model":MODEL,"starting_remaining":remaining,"results":results,
                             "calls":total_calls,"hard_request_cap":4,
                             "max_text_chars":MAX_TOTAL_CHARS,"video":False,
                             "production_voice_changed":False,
                             "commercial_usage":"NOT APPROVED ON FREE"},
                            ensure_ascii=False))
    if any(r["status"]=="FAILED" for r in results):
        raise StopTest("Stopped after first ElevenLabs TTS failure; no automatic retries")


if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("Free ElevenLabs voice pilot ended:",type(ex).__name__)
        raise SystemExit(1)
