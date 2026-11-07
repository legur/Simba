#!/usr/bin/env python3
"""Recover an existing A2E TTS preview created by PRAGUE-STORY-01; NEVER synthesize."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from run_male_prague import (
    make_drive, save_drive, assert_wav, safe_audio_url,
    MAX_AUDIO_BYTES, A2E_SYNTH_URL
)

VOICE_ID = "63a549c1ad2a27fe43d966d2"
CUTOFF = "2026-11-07T04:43:00"
FILE = "PRAGUE-STORY-01_A2E_DmitryNeural.wav"

def main():
    config=json.loads(Path(__file__).with_name("prague_male_voices.json").read_text(encoding="utf-8"))
    text=config["text"]
    token=os.getenv("A2E_API_KEY","")
    if not token:
        print("RECOVERY: A2E_API_KEY missing")
        return
    url="https://api.a2e.ai/v1/tts/preview/list"
    req=Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/json"},method="GET")
    with urlopen(req,timeout=25) as r:
        response=json.load(r)
    if not isinstance(response,dict) or response.get("code")!=0:
        print("RECOVERY: preview list API rejected")
        return
    rows=((response.get("data") or {}).get("data") or [])
    if not isinstance(rows,list):
        print("RECOVERY: malformed preview list")
        return
    match=[]
    for row in rows:
        if not isinstance(row,dict):continue
        voice=row.get("tts_id")
        if isinstance(voice,dict):
            voice=voice.get("_id") or voice.get("value")
        if voice!=VOICE_ID:continue
        if row.get("text")!=text and row.get("msg")!=text:continue
        if str(row.get("createdAt",""))[:19]<CUTOFF:continue
        if not row.get("audio_url"):continue
        match.append(row)
    print("RECOVERY: exact-text voice-specific recent preview matches",len(match))
    if len(match)!=1:
        print("RECOVERY: no unambiguous preview. No new synthesis.")
        return
    drive,folder=make_drive()
    direct=safe_audio_url(match[0]["audio_url"])
    with urlopen(Request(direct,headers={"Accept":"audio/*,application/octet-stream"}),timeout=65) as r:
        b=r.read(MAX_AUDIO_BYTES+1)
    if not 2000<len(b)<=MAX_AUDIO_BYTES:
        print("RECOVERY: preview download invalid; no retry of generation")
        return
    with tempfile.TemporaryDirectory() as td:
        inp=Path(td)/"audio.source";out=Path(td)/"audio.wav"
        inp.write_bytes(b)
        result=subprocess.run(["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
              "-i",str(inp),"-ar","24000","-ac","1","-sample_fmt","s16",str(out)],
              capture_output=True,text=True,timeout=45)
        if result.returncode!=0 or not out.exists():
            print("RECOVERY: conversion failed; no new synthesis")
            return
        wav=out.read_bytes()
    duration=assert_wav(wav)
    info=save_drive(drive,folder,FILE,wav,"A2E","DmitryNeural",duration)
    print("RECOVERY: private Drive WAV verified, voice DmitryNeural, duration",round(duration,1),"seconds")
    print("RECOVERY: filename",info["file"])

if __name__=="__main__":
    try:
        main()
    except Exception as ex:
        print("RECOVERY: blocked - "+type(ex).__name__)
        raise SystemExit(1)
