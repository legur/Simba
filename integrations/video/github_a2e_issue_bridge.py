#!/usr/bin/env python3
"""Quote-only A2E via GitHub Issues and the existing Wix backend.

This module NEVER calls paid start, even if an untrusted issue requests it.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit
from a2e_adapter import BridgeError, call_gateway

ALLOWED_OWNER = "legur"
TRIGGER_LABEL = "a2e-quote"
MAX_SCENES = 6

def build_bodies(event: dict) -> list[dict]:
    if event.get("action") != "labeled":
        raise ValueError("Requires labeled GitHub event")
    if (event.get("label") or {}).get("name") != TRIGGER_LABEL:
        raise ValueError("Wrong label")
    issue = event.get("issue") or {}
    if (issue.get("user") or {}).get("login", "").lower() != ALLOWED_OWNER:
        raise ValueError("Issue author must be legur")
    body = issue.get("body")
    if not isinstance(body, str) or len(body) > 20000:
        raise ValueError("Issue body must be compact raw JSON")
    try:
        data = json.loads(body)
    except (TypeError, ValueError) as ex:
        raise ValueError("Issue body must be raw JSON") from ex
    if not isinstance(data, dict) or data.get("kind") != "simba_a2e_quote":
        raise ValueError("Only simba_a2e_quote requests accepted")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= MAX_SCENES:
        raise ValueError("Must contain 1-6 scenes")
    result = []
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("Each scene must be an object")
        name, image_url, prompt = scene.get("name"), scene.get("image_url"), scene.get("prompt")
        if not isinstance(name, str) or not 1 <= len(name) <= 90:
            raise ValueError("Invalid scene name")
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 2000:
            raise ValueError("Invalid scene prompt")
        if not isinstance(image_url, str) or len(image_url) > 1000:
            raise ValueError("Invalid scene image URL")
        parts = urlsplit(image_url)
        if (parts.scheme != "https" or parts.hostname != "static.wixstatic.com"
            or parts.username or parts.password or parts.port not in (None, 443)
            or not parts.path.startswith("/media/")
            or not parts.path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
            raise ValueError("Only HTTPS Wix Media Manager image URLs accepted")
        result.append({
            "name": name, "image_url": image_url, "prompt": prompt,
            "model_version": "a2e", "video_time": 5
        })
    return result

def format_report(status: str, lines: list[str]) -> str:
    return "\n".join([
        "### Simba / A2E - GitHub bridge",
        "",
        "**Статус:** " + status,
        "**Операция:** только бесплатный расчет стоимости (quote).",
        "",
        *lines, "",
        "Платная генерация не запускалась и недоступна через этот workflow.",
        ""
    ])

def run(event: dict, quote_fn=call_gateway, gateway_token: str | None = None) -> str:
    try:
        bodies = build_bodies(event)
    except (ValueError, TypeError) as ex:
        return format_report("INVALID_REQUEST", [str(ex)])
    if gateway_token is None:
        gateway_token = os.environ.get("SIMBA_A2E_GATEWAY_TOKEN", "")
    if len(gateway_token) < 24:
        return format_report("SETUP_REQUIRED", [
            "Установите GitHub Actions secret SIMBA_A2E_GATEWAY_TOKEN.",
            "Его значение - действующий Wix Simba_Session_Key.",
            "Не копируйте ключ в issue, код или переписку."
        ])
    total = 0.0
    summary = []
    for i, body in enumerate(bodies, 1):
        try:
            response = quote_fn({"action": "quote", "request_body": body})
            quote = response.get("quote")
            credits = quote.get("credits") if isinstance(quote, dict) else None
            if (type(credits) not in (int, float) or not math.isfinite(credits)
                or credits < 0 or credits > 1_000_000):
                raise ValueError("Invalid quote credits")
            total += credits
            summary.append(f"{i}. {body['name']}: {credits:g} credits")
        except (BridgeError, OSError, KeyError, ValueError, TypeError):
            return format_report("QUOTE_FAILED", [
                *summary,
                f"Кадр {i}: шлюз недоступен или цена не получена.",
                "Безопасно проверить доступ и сделать новый запрос. Списаний не было."
            ])
    return format_report("QUOTED_NO_CHARGE", [
        *summary, "",
        f"**Итого: {total:g} credits за {len(bodies)} клипов по 5 секунд.**",
        "Расчет не резервирует цену. Платный запуск требует отдельного решения."
    ])

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--event", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if not args.event.is_file():
        raise SystemExit("Event file missing")
    event = json.loads(args.event.read_text(encoding="utf-8"))
    report = run(event)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(report.splitlines()[2])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
