#!/usr/bin/env python3
"""Read-only diagnosis following Prague TTS attempted generation; never POST to TTS."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPORT=["# Simba TTS read-only diagnostic", "", "No new synthesis requests issued.", ""]

def schema(value, depth=0):
    if depth > 3:
        return "..."
    if isinstance(value, list):
        return {"count":len(value),"first_item":schema(value[0],depth+1) if value else "none"}
    if isinstance(value, dict):
        return {str(k):schema(v,depth+1) for k,v in list(value.items())[:16]}
    return type(value).__name__

def inspect(url, env, label):
    key=os.getenv(env,"")
    if not key:
        REPORT.append(f"- {label}: secret missing.")
        return
    headers={"Accept":"application/json"}
    if env=="GEMINI_API_KEY":headers["x-goog-api-key"]=key
    else:headers["Authorization"]="Bearer "+key
    try:
        req=Request(url,headers=headers,method="GET")
        with urlopen(req, timeout=22) as response:
            data=json.load(response)
            if isinstance(data,dict):
                keys=sorted(str(k) for k in data.keys())
                summary=(", ".join(keys[:15]))[:200]
                size=[f"{k}={len(v)}" for k,v in data.items() if isinstance(v,list)]
                REPORT.append(f"- {label}: HTTP {response.status}; top-level fields: {summary}; list sizes: {', '.join(size)[:110]}.")
                if label=="A2E credit history":
                    REPORT.append("  Schema only: " + json.dumps(schema(data.get("data")),ensure_ascii=False)[:900])
                if label=="Gemini interactions list" and any(k in data for k in ("interactions","interaction_metadatas")):
                    REPORT.append("  Interaction enumeration available; recovery may be possible without resynthesis.")
                if label=="A2E previous previews":
                    REPORT.append("  Schema only: " + json.dumps(schema(data.get("data")),ensure_ascii=False)[:1100])
            else:
                REPORT.append(f"- {label}: HTTP {response.status}; response type {type(data).__name__}.")
    except HTTPError as ex:
        REPORT.append(f"- {label}: HTTP {ex.code}; no paid request attempted.")
    except (URLError,TimeoutError,OSError,ValueError) as ex:
        REPORT.append(f"- {label}: unavailable ({type(ex).__name__}).")

inspect("https://video.a2e.ai/api/v1/anchor/voice_list?country=ru&region=RU&voice_map_type=ru-RU",
        "A2E_API_KEY","A2E Russian voice list")
inspect("https://api.a2e.ai/v1/tts/preview/list","A2E_API_KEY","A2E previous previews")
inspect("https://api.a2e.ai/v1/transactionRecord/creditsHistory","A2E_API_KEY","A2E credit history")
inspect("https://generativelanguage.googleapis.com/v1beta/interactions",
        "GEMINI_API_KEY","Gemini interactions list")
REPORT.extend(["","The earlier two Gemini requests returned no inline audio to the client.",
               "No confirmed audio sample has been saved. A paid request must not be repeated automatically."])
print("\n".join(REPORT))
