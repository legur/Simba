#!/usr/bin/env python3
"""Offline Piper Russian male samples (comparison only, never publish commercially without rights review).
No paid TTS; no video editing. Save generated WAV only in user's private Drive folder.
"""
from pathlib import Path
import json
import tempfile
import wave
from run_male_prague import make_drive, save_drive, assert_wav, post_comment, StopTest

VOICES = ["denis", "dmitri"]
REPO = Path(__file__).resolve().parents[2]
MODELS = Path("piper-models")
BENCHMARK = "PRAGUE-STORY-01"

def main():
    from piper import PiperVoice
    cfg=json.loads((REPO/"integrations/tts/prague_male_voices.json").read_text(encoding="utf-8"))
    assert cfg["production_voice"]["profile"] == "WarmBaritone"
    assert cfg["voice_gender"] == "male_only"
    txt=cfg["text"]
    assert 120<=len(txt)<=300
    drive,folder=make_drive()
    saved=[]
    for voice in VOICES:
        filename=f"PRAGUE-STORY-01_Piper_{voice}_EVAL_ONLY.wav"
        q="name = '"+filename+"' and '"+folder+"' in parents and trashed = false"
        existing=drive.files().list(q=q,fields="files(id,size,shared,parents),nextPageToken",pageSize=20).execute(num_retries=0)
        if existing.get("nextPageToken") or len(existing.get("files", []))>1:
            raise StopTest("Drive destination ambiguous")
        if existing.get("files"):
            f=existing["files"][0]
            if f.get("shared") or folder not in f.get("parents",[]) or not int(f.get("size") or 0):
                raise StopTest("Existing output invalid")
            post_comment("PIPER-EXISTS: "+voice+" privately stored; no rerender.")
            continue
        model=MODELS/f"ru_RU-{voice}-medium.onnx"
        if not model.is_file():
            raise StopTest("Piper model not downloaded: "+str(model))
        engine=PiperVoice.load(model)
        with tempfile.TemporaryDirectory(prefix="piper_test_") as tmp:
            p=Path(tmp)/filename
            with wave.open(str(p),"wb") as w:
                engine.synthesize_wav(txt,w)
            blob=p.read_bytes()
        duration=assert_wav(blob)
        out=save_drive(drive,folder,filename,blob,"Piper offline evaluation only",voice,duration)
        post_comment("PIPER-SAVED: "+voice+" | "+str(round(duration,1))+"s | "+out["file"]+" | private | eval only, voice license check required")
        saved.append({"voice":voice,"duration":round(duration,1)})
    print(json.dumps({"piper":saved,"privacy":"private","production_voice":"untouched","cost":"no paid synthesis","media":"audio only","license":"evaluation only"},ensure_ascii=False))

if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("PIPER-FAILED:",type(ex).__name__,str(ex)[:200])
        raise SystemExit(1)
