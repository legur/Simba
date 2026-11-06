#!/usr/bin/env python3
"""Read-only preflight for Russian TTS. Never calls a synthesis endpoint."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUT = Path(os.environ.get("TTS_PREFLIGHT_OUT", "tts-preflight.md"))
lines = ["# Simba Russian TTS preflight", "", "Only read-only metadata requests; no generation or credit spending.", ""]

def request_json(url, headers):
    req = Request(url, method="GET", headers=headers)
    with urlopen(req, timeout=18) as r:
        return json.load(r)

def voices_from(value, depth=0):
    if depth > 6:
        return
    if isinstance(value, list):
        for item in value[:500]:
            yield from voices_from(item, depth + 1)
    if isinstance(value, dict):
        if any(k in value for k in ("tts_id", "ttsId", "ttsRate")):
            yield value
        for k, v in value.items():
            if isinstance(v, (list, dict)) and k not in ("meta", "account", "user", "profile"):
                yield from voices_from(v, depth + 1)

def safe(value):
    return "".join(c for c in str(value) if c.isalnum() or c in " ._-")[:60]

a2e = os.environ.get("A2E_API_KEY", "").strip()
if not a2e:
    lines.append("- **A2E**: A2E_API_KEY secret missing; no request made.")
else:
    q = urlencode({"country":"ru","region":"RU","voice_map_type":"ru-RU"})
    url = "https://video.a2e.ai/api/v1/anchor/voice_list?" + q
    try:
        data = request_json(url, {"Authorization":"Bearer " + a2e, "Accept":"application/json"})
        if isinstance(data, dict) and data.get("code") not in (None, 0):
            lines.append("- **A2E**: endpoint returned a non-success result; no synthesis attempted.")
        else:
            voices = list(voices_from(data))
            lines.append(f"- **A2E**: authorized Russian voice-list query succeeded; detected {len(voices)} voice records.")
            if voices:
                lines += ["", "  First system voices (ID and rate; verify speaker before synthesis):"]
                for v in voices[:12]:
                    vid = safe(v.get("tts_id") or v.get("ttsId") or v.get("_id") or v.get("value") or "-")
                    rate = safe(v.get("ttsRate", "unknown"))
                    name = safe(v.get("name") or v.get("label") or v.get("voiceName") or "unnamed")
                    lines.append(f"  - \`{vid}\` | {name} | rate {rate} credits/10s")
            else:
                lines.append("  Voice-list format did not expose records; inspect schema before choosing tts_id.")
    except HTTPError as ex:
        lines.append(f"- **A2E**: catalog query HTTP {ex.code}; no synthesis attempted.")
    except (URLError, TimeoutError, OSError, ValueError) as ex:
        lines.append(f"- **A2E**: catalog query unavailable ({type(ex).__name__}); no synthesis attempted.")

gkey = os.environ.get("GEMINI_API_KEY", "").strip()
if not gkey:
    lines.append("- **Gemini**: GEMINI_API_KEY secret missing; no request made.")
else:
    try:
        data = request_json(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-tts",
            {"x-goog-api-key":gkey,"Accept":"application/json"}
        )
        model = safe(data.get("name", "unknown")) if isinstance(data, dict) else "unknown"
        lines.append(f"- **Gemini**: read-only model metadata available ({model}); no synthesis attempted.")
    except HTTPError as ex:
        lines.append(f"- **Gemini**: model metadata HTTP {ex.code}; no synthesis attempted.")
    except (URLError, TimeoutError, OSError, ValueError) as ex:
        lines.append(f"- **Gemini**: metadata query unavailable ({type(ex).__name__}); no synthesis attempted.")

lines.extend(["", "**No audio was generated.**", "To synthesize, first confirm a real voice ID and a separate credit cap."])
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Read-only TTS preflight finished; report prepared.")
