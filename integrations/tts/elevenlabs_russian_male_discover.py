#!/usr/bin/env python3
"""Read-only ElevenLabs Voice Library lookup for native Russian male TTS.

No synthesis, video, voice cloning, account mutation, or paid generation.
Uses already configured API key, posts only public shared-voice metadata.
"""
import json
import os
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from run_male_prague import post_comment, StopTest

URL="https://api.elevenlabs.io/v1/shared-voices"
MAX_RETURN = 7
def main():
    key = os.environ.get("ELEVENLABS_API_KEY","").strip()
    if not key:
        post_comment("ElevenLabs catalog: MISSING ELEVENLABS_API_KEY secret; no requests made.")
        raise StopTest("Missing ElevenLabs secret")
    query=urlencode({"language":"ru","gender":"male","page_size":50,
                     "sort":"usage_character_count_1y"})
    req=Request(URL+"?"+query,headers={"xi-api-key":key,"Accept":"application/json"},method="GET")
    try:
        with urlopen(req,timeout=35) as resp:
            if resp.status != 200:
                raise StopTest("Unexpected catalog status")
            obj=json.load(resp)
    except HTTPError as e:
        # Structured status is safe for diagnostics; never log tokens/response payload.
        try:
            details=json.loads(e.read(4096).decode("utf-8",errors="replace"))
            item=details.get("detail",{}) if isinstance(details,dict) else {}
            code=item.get("status") if isinstance(item,dict) else "unknown"
            if not isinstance(code,str) or not re.fullmatch(r"[a-z_]{3,50}",code):
                code="unknown"
            permission="unknown"
            if isinstance(item,dict) and code=="missing_permissions":
                msg=str(item.get("message") or "")
                m=re.search(r"permission ([a-z_]{3,50})",msg)
                if m:
                    permission=m.group(1)
        except Exception:
            code="unknown"
            permission="unknown"
        post_comment("ElevenLabs Russian male catalog: HTTP "+str(e.code)+
                     ", provider_status="+code+", required_permission="+permission+
                     ". No audio requests made.")
        raise StopTest("Voice Library lookup failed: "+code)
    voices=obj.get("voices",[])
    if not isinstance(voices,list):
        raise StopTest("No voice metadata returned")
    rows=[]
    for v in voices:
        if not isinstance(v,dict):continue
        name=str(v.get("name") or "Unnamed")[:85]
        voice_id=str(v.get("voice_id") or "")
        labels=v.get("labels") or {}
        descr=str(v.get("description") or "")[:200]
        category=str(v.get("category") or "")
        accent=str(v.get("accent") or labels.get("accent") or "")
        age=str(v.get("age") or labels.get("age") or "")
        use_cases=v.get("use_cases") or []
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}",voice_id):
            continue
        combined=(" ".join([name,descr,category,age,accent,str(use_cases),str(labels)])).lower()
        score=0
        for term,points in [
            ("native",5),("russian",6),("рус",7),("story",4),
            ("narrat",4),("audiobook",3),("convers",4),
            ("mature",3),("middle",3),("deep",2),("warm",2),
            ("calm",2),("baritone",4),("old",1),
        ]:
            if term in combined:score+=points
        if "young" in combined:score-=2
        if "female" in combined:score-=20
        rows.append({"voice":name,"voice_id":voice_id,"age":age,"accent":accent,
                     "description":descr,"use_cases":use_cases,"score":score,
                     "preview":str(v.get("preview_url") or "")[:200]})
    rows.sort(key=lambda r:r["score"],reverse=True)
    shortlist=rows[:MAX_RETURN]
    # Shared catalog voice IDs are public; no user/private voice metadata included.
    post_comment("ElevenLabs Voice Library RU MALE (READ-ONLY)\n"+
        json.dumps({"total_returned":len(voices),"has_more":bool(obj.get("has_more")),
                    "top_candidates":shortlist},ensure_ascii=False,indent=2)+
        "\nNo synthesis, no paid credits, no video. User voice remains WarmBaritone.")
    print(json.dumps({"count":len(rows),"top":shortlist[:3]},ensure_ascii=False))

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print("ElevenLabs voice lookup ended:",type(e).__name__)
        raise SystemExit(1)
