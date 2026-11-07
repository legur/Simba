#!/usr/bin/env python3
"""Read-only list of account-accessible ElevenLabs default voice previews.
No TTS generation, no credits, no checkout, no change of production Simba.
"""
import json, os, re
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from run_male_prague import post_comment, StopTest

ENDPOINT="https://api.elevenlabs.io/v2/voices"

def main():
    key=os.environ.get("ELEVENLABS_API_KEY","").strip()
    if not key:
        raise StopTest("API key is missing")
    token=None
    found=[]
    count_pages=0
    while count_pages < 4:
        params={"voice_type":"default","page_size":"100","include_total_count":"false"}
        if token: params["next_page_token"]=token
        req=Request(ENDPOINT+"?"+urlencode(params),headers={
            "xi-api-key":key,"Accept":"application/json"},method="GET")
        try:
            with urlopen(req,timeout=35) as r:
                data=json.load(r)
        except HTTPError as e:
            post_comment("DEFAULT-TTS-VOICES: HTTP "+str(e.code)+" on read-only list. No TTS calls or credits.")
            raise StopTest("List not available")
        for v in data.get("voices",[]):
            labels=v.get("labels") or {}
            vr=v.get("verified_languages") or []
            lang=[str(x.get("language") or x.get("locale") or "") for x in vr if isinstance(x,dict)]
            voice_id=str(v.get("voice_id") or "")
            preview=str(v.get("preview_url") or "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}",voice_id): continue
            if not preview.startswith("https://"): continue
            age=str(labels.get("age") or "")
            accent=str(labels.get("accent") or "")
            gender=str(labels.get("gender") or "")
            name=str(v.get("name") or "")
            description=str(v.get("description") or "")[:200]
            if gender.lower() not in ("male","man","masculine"): continue
            traits=(name+" "+description+" "+age+" "+accent+" "+" ".join(lang)).lower()
            score=sum(weight for term,weight in (
                ("russian",20),("рус",20),("ru-ru",20),("mature",7),
                ("middle",6),("deep",4),("baritone",7),("warm",6),
                ("narrat",6),("story",5),("calm",4),("natural",2),
                ("gentle",2),("sincere",2),("convers",3),
                ("confident",3),("young",-5)) if term in traits)
            found.append({"name":name,"voice_id":voice_id,"age":age,
                          "accent":accent,"description":description,
                          "verified_languages":lang,"category":v.get("category"),
                          "preview_url":preview,"score":score})
        count_pages+=1
        token=data.get("next_page_token")
        if not data.get("has_more") or not token: break
    found.sort(key=lambda v:(-v["score"],v["name"]))
    shortlist=found[:35]
    result={"source":"ElevenLabs account available DEFAULT voices",
            "model_synthesis":False,"credits_used":0,"total_male":len(found),
            "pages":count_pages,"more":bool(token) and count_pages>=4,
            "male_candidates":shortlist}
    post_comment("ELEVENLABS DEFAULT VOICE PREVIEWS (NO SYNTHESIS):\n"+
                 json.dumps(result,ensure_ascii=False,indent=2)+
                 "\nPre-recorded provider preview audio only; English sample may not demonstrate Russian pronunciation.")
    print(json.dumps({"total":len(found),"top":shortlist[:5]},ensure_ascii=False))

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("Voice listing stopped:",type(e).__name__)
        raise SystemExit(1)
