#!/usr/bin/env python3
"""Export pre-existing ElevenLabs default MALE voice preview MP3s.

READ-ONLY ElevenLabs metadata & provider's published preview audio GET.
ZERO TTS syntheses, ZERO credits, NO video, NO API mutations in ElevenLabs.
Save to already established private Google Drive and verify stored checksums.
"""
import hashlib
import io
import json
import os
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from run_male_prague import make_drive, post_comment, StopTest

MAX_PREVIEWS = 30
MAX_FILE_BYTES = 5 * 1024 * 1024
KNOWN_HOSTS = {"api.us.elevenlabs.io", "api.elevenlabs.io", "storage.googleapis.com",
               "cdn.elevenlabs.io", "api.eu.residency.elevenlabs.io"}
NAME_PREFIX="ElevenLabs_DEFAULT_MALE_PREVIEW_"

def get_voices():
    key=os.environ.get("ELEVENLABS_API_KEY","").strip()
    if not key: raise StopTest("Missing ElevenLabs key")
    query=urlencode({"voice_type":"default","page_size":100,"include_total_count":"false"})
    req=Request("https://api.elevenlabs.io/v2/voices?"+query,
                headers={"xi-api-key":key,"Accept":"application/json"},method="GET")
    with urlopen(req, timeout=35) as res:
        data=json.load(res)
    voices=[]
    for item in data.get("voices",[]):
        labels=item.get("labels") or {}
        if str(labels.get("gender") or "").lower()!="male":continue
        id=str(item.get("voice_id") or "")
        url=str(item.get("preview_url") or "")
        if (not re.fullmatch(r"[A-Za-z0-9_-]{10,100}",id) or
            not url.startswith("https://") or urlsplit(url).hostname not in KNOWN_HOSTS):
            continue
        voices.append({"id":id,"name":str(item.get("name") or "Voice")[:90],
                       "age":str(labels.get("age") or ""),
                       "accent":str(labels.get("accent") or ""),
                       "preview_url":url,"category":str(item.get("category") or "")})
    if data.get("has_more"):
        raise StopTest("Unexpected paginated default voice catalog; no partial batch export")
    if not 1<=len(voices)<=MAX_PREVIEWS:
        raise StopTest("No male previews or unexpected count")
    return voices

def ensure_private_destination(drive,folder,filename):
    query="name = '"+filename+"' and '"+folder+"' in parents and trashed = false"
    result=drive.files().list(q=query,fields="files(id,size,md5Checksum,parents,shared),nextPageToken",
                              pageSize=20).execute(num_retries=0)
    if result.get("nextPageToken") or len(result.get("files",[]))>1:
        raise StopTest("Ambiguous Drive destination")
    if result.get("files"):
        f=result["files"][0]
        if f.get("shared") or folder not in f.get("parents",[]) or not int(f.get("size") or 0):
            raise StopTest("Existing Drive preview invalid")
        return True
    return False

def fetch_preview(url):
    parsed=urlsplit(url)
    if parsed.scheme!="https" or parsed.hostname not in KNOWN_HOSTS:
        raise StopTest("Preview destination not approved")
    req=Request(url,headers={"User-Agent":"Simba-ElevenLabs-Voice-Preview-Exporter/1.0",
                             "Accept":"audio/mpeg,audio/mp3,*/*"},method="GET")
    with urlopen(req,timeout=60) as res:
        blob=res.read(MAX_FILE_BYTES+1)
        mime=str(res.headers.get("Content-Type") or "").lower()
    if not 1000<len(blob)<=MAX_FILE_BYTES:
        raise StopTest("Preview empty or too large")
    if not (blob.startswith(b"ID3") or (blob[0]==0xff and (blob[1]&0xe0)==0xe0)):
        raise StopTest("Preview is not MP3 (not an audio response)")
    if mime and "html" in mime:
        raise StopTest("Preview returned HTML instead of MP3")
    return blob

def upload(drive,folder,name,blob,details):
    from googleapiclient.http import MediaIoBaseUpload
    media=MediaIoBaseUpload(io.BytesIO(blob),mimetype="audio/mpeg",resumable=False)
    item=drive.files().create(
      body={"name":name,"mimeType":"audio/mpeg","parents":[folder],
            "description":"ElevenLabs existing default male voice provider preview (no TTS; listening demo only). "
                          "Voice: "+details["name"]+". Accent "+details["accent"]},
      media_body=media,
      fields="id,name,size,md5Checksum,parents,shared").execute(num_retries=0)
    check=drive.files().get(fileId=item["id"],
                            fields="id,name,size,md5Checksum,parents,shared").execute(num_retries=0)
    if (check.get("shared") or folder not in check.get("parents",[]) or
        int(check.get("size") or 0)!=len(blob) or
        check.get("md5Checksum")!=hashlib.md5(blob,usedforsecurity=False).hexdigest()):
        raise StopTest("Drive checksum readback mismatch")
    return {"filename":name,"size":len(blob),"drive_id":item["id"],"status":"saved"}

def main():
    voices=get_voices()
    drive,folder=make_drive()
    results=[]
    errors=0
    for v in voices:
        filename=NAME_PREFIX+v["id"]+".mp3"
        try:
            if ensure_private_destination(drive,folder,filename):
                row={"filename":filename,"status":"already_saved"}
            else:
                data=fetch_preview(v["preview_url"])
                row=upload(drive,folder,filename,data,v)
            results.append({"name":v["name"],"id":v["id"],"accent":v["accent"],
                            "age":v["age"],**row})
        except Exception as e:
            errors+=1
            # Errors may indicate preview URLs not directly downloadable.
            results.append({"name":v["name"],"id":v["id"],"status":"failed",
                            "error":type(e).__name__})
    payload={"provider":"ElevenLabs","type":"existing_default_voice_previews",
             "synthesized_new_audio":False,"credits_spent":0,
             "male_voices":len(voices),"files":results,"failed":errors,
             "drive_folder":"Simba Private TTS Prague 2026-11-07",
             "production_voice":"WarmBaritone unchanged"}
    post_comment("ELEVENLABS PREVIEW AUDIO EXPORT RESULTS:\n"+
                 json.dumps(payload,ensure_ascii=False,indent=2))
    print(json.dumps({"total":len(voices),"uploaded_or_exists":len(voices)-errors,
                      "failed":errors,"no_tts_calls":True}))
    if errors:
        raise StopTest("One or more existing previews couldn't be exported; no automatic retry")

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("Existing preview export stopped:",type(e).__name__,str(e)[:100])
        raise SystemExit(1)
