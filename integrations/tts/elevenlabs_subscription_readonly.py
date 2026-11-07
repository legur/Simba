#!/usr/bin/env python3
"""Read-only ElevenLabs subscription/credits diagnostic. NO GENERATION.

This compares account tier and quota with the failed 402 TTS request,
without posting account identifiers, API key, raw response, invoices or
workspace metadata. One GET, no retries and no mutation.
"""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from run_male_prague import post_comment, StopTest

URL = "https://api.elevenlabs.io/v1/user/subscription"
def main():
    key=os.environ.get("ELEVENLABS_API_KEY","").strip()
    if not key:
        raise StopTest("ElevenLabs API secret missing")
    req=Request(URL, headers={"xi-api-key":key, "Accept":"application/json"}, method="GET")
    try:
        with urlopen(req,timeout=30) as r:
            if r.status!=200: raise StopTest("Unexpected subscription status")
            info=json.load(r)
    except HTTPError as e:
        status="unknown"
        permission="unknown"
        try:
            detail=json.loads(e.read(4096).decode("utf-8","replace")).get("detail",{})
            if isinstance(detail,dict):
                item=detail.get("status")
                if isinstance(item,str) and re.fullmatch(r"[a-z_]{3,50}",item): status=item
                m=re.search(r"permission ([a-z_]{3,50})",str(detail.get("message") or ""))
                if m: permission=m.group(1)
        except Exception: pass
        post_comment(f"ElevenLabs CREDIT READ-ONLY: GET subscription returned HTTP {e.code}, status={status}, permission={permission}. No TTS or paid request.")
        return
    if not isinstance(info,dict): raise StopTest("Invalid subscription response")
    tier=info.get("tier")
    state=info.get("status")
    used=info.get("character_count")
    limit=info.get("character_limit")
    quota=max(0,limit-used) if isinstance(used,int) and isinstance(limit,int) else None
    row={"tier":tier,"subscription_status":state,"used":used,
         "period_limit":limit,"approx_remaining":quota,
         "is_free_tier":tier=="free","no_TTS_requests":True}
    post_comment("ElevenLabs CREDIT READ-ONLY (API key's actual workspace):\n"+
                 json.dumps(row,ensure_ascii=False,indent=2)+
                 "\nNote: remaining is only an estimate from character usage; shared Library voices may be unavailable on Free via API.")
    print(json.dumps(row,ensure_ascii=False))

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("Subscription diagnostic:",type(e).__name__)
        raise SystemExit(1)
