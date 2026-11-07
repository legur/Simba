#!/usr/bin/env python3
"""Silero Russian male voices, NON-COMMERCIAL EVALUATION ONLY (CC-BY-NC).
No billing, no video editing, no production voice changes.
"""
import json
import tempfile
from pathlib import Path
from run_male_prague import make_drive, save_drive, assert_wav, post_comment, StopTest

VOICES=("aidar","eugene")
MODEL_ID="v5_6_ru"
REPO=Path(__file__).resolve().parents[2]

def main():
    import torch
    import numpy as np
    import soundfile as sf
    cfg=json.loads((REPO/"integrations/tts/prague_male_voices.json").read_text(encoding="utf-8"))
    if cfg["voice_gender"]!="male_only" or cfg["production_voice"]["profile"]!="WarmBaritone":
        raise StopTest("Simba approved voice gate failed")
    text=cfg["text"]
    if not 120<=len(text)<=300:
        raise StopTest("Unexpected source text")
    drive,folder=make_drive()
    torch.set_num_threads(2)
    model,_=torch.hub.load(repo_or_dir="snakers4/silero-models",model="silero_tts",
                           language="ru",speaker=MODEL_ID,trust_repo=True)
    model.to(torch.device("cpu"))
    outputs=[]
    for voice in VOICES:
        filename=f"PRAGUE-STORY-01_Silero_{MODEL_ID}_{voice}_NONCOMMERCIAL.wav"
        q="name = '"+filename+"' and '"+folder+"' in parents and trashed = false"
        found=drive.files().list(q=q,fields="files(id,parents,size,shared),nextPageToken",pageSize=10).execute(num_retries=0)
        if found.get("nextPageToken") or len(found.get("files",[]))>1:
            raise StopTest("Ambiguous Drive destination")
        if found.get("files"):
            f=found["files"][0]
            if f.get("shared") or folder not in f.get("parents",[]) or not int(f.get("size") or 0):
                raise StopTest("Existing output invalid")
            post_comment("SILERO-EXISTS: "+voice)
            continue
        signal=model.apply_tts(text=text,speaker=voice,sample_rate=24000)
        if hasattr(signal,"detach"):
            signal=signal.detach().cpu().numpy()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/filename
            sf.write(str(p), np.asarray(signal), 24000,subtype="PCM_16")
            data=p.read_bytes()
        dur=assert_wav(data)
        record=save_drive(drive,folder,filename,data,"Silero v5.6 RU NONCOMMERCIAL",voice,dur)
        post_comment(f"SILERO-SAVED: {voice} | {dur:.1f}s | private {record['file']} | CC-BY-NC, noncommercial comparison only")
        outputs.append({"voice":voice,"dur":round(dur,1)})
    print(json.dumps({"noncommercial_only":True,"model":MODEL_ID,"samples":outputs,
                      "paid_calls":0,"video":False,"approved_voice_unchanged":True}))

if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("SILERO-FAILED:",type(ex).__name__,str(ex)[:180])
        raise SystemExit(1)
