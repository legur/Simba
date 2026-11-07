#!/usr/bin/env python3
"""Create and audition two persistent ORIGINAL Russian male voices for Simba.

One-time paid calls only; never clone voices, never use A2E.
All voice IDs, metadata and WAVs remain in the user's PRIVATE Google Drive.
"""
import base64
import hashlib
import io
import json
import os
import re
import wave
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.http import MediaIoBaseUpload
from run_male_prague import (
    make_drive, save_drive, assert_wav, claim_once, post_comment,
    post_json, StopTest, GEMINI_URL
)

MODEL = "gemini-3.8-flash-tts"
DESIGN_URL = "https://generativelanguage.googleapis.com/v1beta/voices"
STAMP = "20261107-voice-design-v1"
PROFILES = [
  {
    "tag": "WarmBaritone",
    "label": "Simba — Теплый баритон",
    "description": (
      "Design an entirely original, consistent Russian-speaking male character voice. "
      "The character is a personable, experienced world traveler in his mid-to-late 50s. "
      "Native standard Russian without detectable foreign accent. "
      "Warm rich baritone in a comfortable low-middle pitch, nuanced resonance, "
      "gentle smoky grain at the edges but never a forced growl. "
      "Relaxed, naturally conversational diction; intelligent and trustworthy, "
      "curious about the world, quietly amused by life. "
      "A welcoming human companion who can tell travel stories with restrained wonder "
      "and also explain practical details clearly. "
      "Distinctly mature, not a young announcer. "
      "No high energy radio voice, no trailer bass, no affected dramatic intonation, "
      "no exaggerated rasp, no imitation of an actual person."
    )
  },
  {
    "tag": "VelvetCharacter",
    "label": "Simba — Бархатный характер",
    "description": (
      "Create a unique stable voice for an adult male Russian-language travel character, "
      "about 50 to 60 years old, with a deep-leaning expressive baritone. "
      "A supple velvety texture with a very slight dry, weathered rasp; native Russian "
      "with crisp consonants, naturally musical speech and easy warm humor. "
      "He has calm self-assurance, mild irony and an unhurried storyteller's timing. "
      "A charismatic, experienced traveler speaking across a table, never a corporate "
      "presenter, radio announcer or stage actor. "
      "Low-mid speaking register, not booming or rumbling. "
      "Can move from amused wonder to reassuring practical advice while keeping "
      "the same recognizable personality. No cartoon lion growl, no performance "
      "of a real celebrity or identifiable person's voice."
    )
  }
]

def token():
    key=os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise StopTest("GEMINI_API_KEY unavailable; no requests made")
    return {"x-goog-api-key":key,"Accept":"application/json"}

def original_text():
    c=json.loads(Path(__file__).with_name("prague_male_voices.json").read_text(encoding="utf-8"))
    if c.get("voice_gender")!="male_only" or not c.get("safety",{}).get("no_more_a2e_requests"):
        raise StopTest("Male-only and no-A2E policy are required")
    txt=c["text"]
    if not 120 <= len(txt) <= 300:
        raise StopTest("Unexpected benchmark text")
    return txt

def already_saved(drive,folder_id, filename):
    name=filename.replace("'", "\\'")
    q="name = '"+name+"' and '"+folder_id+"' in parents and trashed = false"
    rows=drive.files().list(q=q,fields="files(id,parents,shared),nextPageToken",pageSize=20).execute()
    if rows.get("nextPageToken"):
        raise StopTest("Drive duplicate query incomplete")
    return len(rows.get("files",[]))>0

def write_private_json(drive,folder_id,filename,content):
    if not re.fullmatch(r"SimbaDesign_[A-Za-z0-9_-]+\.json",filename):
        raise StopTest("Unapproved voice metadata filename")
    if already_saved(drive,folder_id,filename):
        raise StopTest("Voice metadata file already exists; do not overwrite")
    raw=json.dumps(content,ensure_ascii=False,indent=2).encode("utf-8")
    media=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/json",resumable=True)
    file=drive.files().create(
        body={"name":filename,"mimeType":"application/json","parents":[folder_id],
              "description":"Private Gemini voice design ID and character description"},
        media_body=media,fields="id,name,size,parents,shared").execute()
    check=drive.files().get(fileId=file["id"],fields="id,name,size,parents,shared").execute()
    if check.get("shared") or folder_id not in check.get("parents",[]) or int(check.get("size",0))!=len(raw):
        raise StopTest("Private metadata storage read-back failed")
    return file["id"]

def decode_audio(asset):
    if not isinstance(asset,dict) or not isinstance(asset.get("data"),str):
        return None
    b=base64.b64decode(asset["data"],validate=True)
    mime=str(asset.get("mime_type") or asset.get("mimeType") or "audio/wav").lower()
    if mime.startswith("audio/l16"):
        with io.BytesIO() as f:
            with wave.open(f,"wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(b)
            b=f.getvalue()
    return b

def create_voice(profile):
    payload={"store":True,
      "voice":{
        "model":MODEL, "type":"prompted",
        "display_name":profile["label"],
        "gender":"male",
        "language_code":"ru-RU",
        "prompted":{"input":profile["description"]}
      }
    }
    response=post_json(DESIGN_URL,payload,token())
    item=response.get("voice",response) if isinstance(response,dict) else {}
    if not isinstance(item,dict):
        raise StopTest("Voice creation response unexpected; no retry")
    ident=item.get("id") or item.get("name")
    if not isinstance(ident,str) or not re.fullmatch(r"voice_[a-zA-Z0-9_-]{6,}",ident):
        raise StopTest("Voice creation ID not recognized; no retry")
    asset=item.get("sample_audio") or item.get("sampleAudio")
    return ident, asset, (response.get("usage") or item.get("usage"))

def generate_text(text,voice_id):
    payload={
      "model":MODEL,
      "input":[{"type":"user_input","content":[
        {"type":"text","text":text,
         "annotations":[{"type":"speech_metadata",
                         "style":"Natural warm Russian travel storytelling, easy unhurried conversational rhythm; gentle interest. Say dates and price clearly."}]}]}],
      "response_format":{"type":"audio"},
      "generation_config":{"speech_config":[{"voice":voice_id}]}
    }
    response=post_json(GEMINI_URL,payload,token())
    data=None
    if isinstance(response,dict):
        a=response.get("output_audio")
        if isinstance(a,dict) and isinstance(a.get("data"),str):
            data=a
        for step in response.get("steps",[]):
            if isinstance(step,dict) and step.get("type")=="model_output":
                for part in step.get("content",[]):
                    if isinstance(part,dict) and part.get("type")=="audio" and isinstance(part.get("data"),str):
                        data=part
    b=decode_audio(data)
    if b is None:
        raise StopTest("No Gemini audio part found; no retry after paid attempt")
    duration=assert_wav(b)
    return b,duration

def main():
    text=original_text()
    drive,folder=make_drive()  # Validate PRIVATE storage before any possible spend.
    if not os.environ.get("GEMINI_API_KEY"):
        raise StopTest("No Gemini key; never start")
    outcomes=[]
    for profile in PROFILES:
        tag=profile["tag"]
        voicekey="SIMBA-DESIGN-ONE-SHOT-"+tag+"-"+STAMP
        fullkey="SIMBA-DESIGN-TTS-ONE-SHOT-"+tag+"-"+STAMP
        metadata_filename="SimbaDesign_"+tag+".json"
        try:
            if already_saved(drive,folder,metadata_filename):
                # A previous run succeeded. Do not generate again.
                post_comment("SIMBA-VOICE: "+tag+" metadata already exists in private Drive. Skipping duplicate.")
                outcomes.append({"profile":tag,"status":"already_saved"})
                continue
            claim_once(voicekey)  # Durable record before potentially billable voice design
            voice_id, preview, usage=create_voice(profile)
            metadata={"voice_id":voice_id,"label":profile["label"],
                      "provider":"Google Gemini", "model":MODEL,
                      "type":"prompted","gender":"male","language_code":"ru-RU",
                      "design_prompt":profile["description"],
                      "created_at_utc":datetime.now(timezone.utc).isoformat(),
                      "sample_status":"pending","source":"voice_design_api",
                      "voice_usage":usage if isinstance(usage,dict) else None}
            write_private_json(drive,folder,metadata_filename,metadata)
            post_comment("SIMBA-VOICE-CREATED: "+tag+
                         "\nPersistent Google Voice Design ID saved privately; no ID published.")
            previewb=decode_audio(preview)
            if previewb is not None:
                try:
                    duration=assert_wav(previewb)
                    save_drive(drive,folder,"SIMBA_Design_"+tag+"_Preview.wav",
                               previewb,"Gemini Voice Design",tag,duration)
                    post_comment(f"SIMBA-PREVIEW-SAVED: {tag} ({duration:.1f}s), private Drive.")
                except Exception:
                    post_comment("SIMBA-PREVIEW-UNAVAILABLE: "+tag+
                                 " (design metadata remains safely stored).")
            claim_once(fullkey)  # Distinct auditable generation claim
            wav, seconds=generate_text(text,voice_id)
            info=save_drive(drive,folder,
                       "SIMBA_Design_"+tag+"_Prague.wav",wav,"Gemini Voice Design",tag,seconds)
            outcomes.append({"profile":tag,"status":"verified","seconds":round(seconds,1)})
            post_comment(f"SIMBA-VOICE-SAMPLE-SAVED: {tag}. Verified Russian Prague WAV ({seconds:.1f}s) in private Drive.")
        except Exception as exc:
            problem=str(exc)[:160] if isinstance(exc,StopTest) else type(exc).__name__
            post_comment("SIMBA-VOICE-ERROR: "+tag+" — "+problem+
                         ". No automatic generation retries; inspect private Drive.")
            outcomes.append({"profile":tag,"status":"failed"})
    print(json.dumps({"profile_results":outcomes,"a2e_requests":0},ensure_ascii=False))
    if not any(x["status"]=="verified" for x in outcomes):
        raise StopTest("No verified designed voice recording; no retries")

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("Voice design ended:",type(exc).__name__)
        raise SystemExit(1)
