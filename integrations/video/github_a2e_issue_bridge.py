#!/usr/bin/env python3
"""Direct A2E quote-only bridge: ChatGPT -> GitHub Issues -> Actions -> A2E.

This entry point NEVER invokes any paid A2E generation endpoint.
Secrets stay in GitHub Actions secrets and never enter issues or comments.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

A2E_QUOTE_URL = "https://api.a2e.ai/v1/generation/quote"
A2E_GENERATION_ENDPOINT = "/api/v1/userImage2Video/start"
ALLOWED_OWNER = "legur"
TRIGGER_LABEL = "a2e-quote"
MAX_SCENES = 6
DEFAULT_NEGATIVE_PROMPT = "blurry, distorted, static"


def validate_generation_body(body: dict) -> None:
    """Local A2E validation: exact price quotes do NOT validate all fields.

    Support confirmed that POST /v1/userImage2Video/start rejects requests
    without a nonempty prompt AND negative_prompt unless lora is supplied.
    These Simba workflows do not use lora, so both fields are mandatory here.
    """
    if not isinstance(body, dict) or body.get("lora"):
        raise ValueError("Simba I2V requires a JSON body without Lora")
    for key in ("prompt", "negative_prompt"):
        value = body.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("A2E generation requires nonempty " + key)




class QuoteError(RuntimeError):
    """Safe error class: no credentials or raw response body."""


def build_bodies(event: dict) -> list[dict]:
    """Build an allowlisted A2E body from an owner-authored labeled issue."""
    if event.get("action") != "labeled":
        raise ValueError("Requires a labeled issue event")
    if (event.get("label") or {}).get("name") != TRIGGER_LABEL:
        raise ValueError("Wrong trigger label")
    issue = event.get("issue") or {}
    if (issue.get("user") or {}).get("login", "").lower() != ALLOWED_OWNER:
        raise ValueError("Only owner-created issues may request quotes")
    raw = issue.get("body")
    if not isinstance(raw, str) or len(raw) > 20000:
        raise ValueError("Issue body must contain compact JSON")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as ex:
        raise ValueError("Issue body must be raw JSON") from ex
    if not isinstance(data, dict) or data.get("kind") != "simba_a2e_quote":
        raise ValueError("Only simba_a2e_quote requests are accepted")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= MAX_SCENES:
        raise ValueError("Requires one to six scenes")
    bodies = []
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("Scene must be an object")
        name, url, prompt = scene.get("name"), scene.get("image_url"), scene.get("prompt")
        if not isinstance(name, str) or not 1 <= len(name) <= 90 or "\n" in name:
            raise ValueError("Scene name must be 1-90 characters on one line")
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 2000:
            raise ValueError("Scene prompt must be 1-2000 characters")
        if not isinstance(url, str) or len(url) > 1000:
            raise ValueError("Source image URL is required")
        parsed = urlsplit(url)
        if (parsed.scheme != "https"
            or parsed.hostname != "static.wixstatic.com"
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not parsed.path.startswith("/media/")
            or not parsed.path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
            or parsed.query or parsed.fragment):
            raise ValueError("Only clean HTTPS Wix Media Manager image URLs allowed")
        # Ignore any instructions to use start, alter the model, time, or prices.
        bodies.append({
            "name": name,
            "image_url": url,
            "prompt": prompt,
            "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
            "model_version": "a2e",
            "video_time": 5,
            "auto_add_audio": False,
            "number_of_images": 1
        })
    return bodies


def request_quote(body: dict, key: str) -> dict:
    """The *only* external request: A2E POST /v1/generation/quote."""
    payload = {"endpoint": A2E_GENERATION_ENDPOINT, "requestBody": body}
    req = Request(
        A2E_QUOTE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )
    try:
        with urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise QuoteError("A2E returned non-200 HTTP status")
            result = json.load(response)
    except HTTPError as ex:
        # Never echo A2E bodies (they could reflect sensitive request data).
        raise QuoteError("A2E_HTTP_" + str(ex.code)) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise QuoteError("A2E_NETWORK_OR_JSON_ERROR") from None
    if not isinstance(result, dict):
        raise QuoteError("A2E_RESPONSE_INVALID")
    return result


def format_report(status: str, lines: list[str]) -> str:
    return "\n".join([
        "### Simba / A2E — прямой GitHub-мост",
        "",
        "**Статус:** " + status,
        "**Операция:** бесплатный расчет стоимости через официальный A2E API.",
        "",
        *lines,
        "",
        "Точный расчет цены не подтверждает валидность запроса генерации (generationRequestValidated может быть false).",
        "Платная генерация не запускалась. Ключ API не выводится.",
        ""
    ])


def run(event: dict, quote_fn=request_quote, api_key: str | None = None) -> str:
    try:
        bodies = build_bodies(event)
    except (ValueError, TypeError) as ex:
        return format_report("INVALID_REQUEST", [str(ex)])
    if api_key is None:
        api_key = os.environ.get("A2E_API_KEY", "")
    if not api_key.startswith("sk_") or len(api_key) < 15:
        return format_report("SETUP_REQUIRED", [
            "В GitHub Actions отсутствует рабочий секрет A2E_API_KEY.",
            "Укажите действительный API token A2E только в Settings > Secrets and variables > Actions."
        ])
    total = 0.0
    summary = []
    for index, body in enumerate(bodies, 1):
        try:
            result = quote_fn(body, api_key)
            if not isinstance(result, dict) or type(result.get("code")) is not int or result["code"] != 0:
                raise QuoteError("A2E_QUOTE_REJECTED")
            data = result.get("data")
            if not isinstance(data, dict) or data.get("available") is not True:
                raise QuoteError("A2E_PRICE_NOT_AVAILABLE")
            coins = data.get("coins")
            if (type(coins) not in (float, int) or
                not math.isfinite(coins) or coins < 0 or coins > 1_000_000):
                raise QuoteError("A2E_COINS_INVALID")
            if data.get("exact") is not True:
                raise QuoteError("A2E_PRICE_NOT_EXACT")
            total += coins
            summary.append(f"{index}. {body['name']}: **{coins:g} credits**")
        except (QuoteError, ValueError, TypeError, OSError, KeyError):
            return format_report("QUOTE_FAILED", [
                *summary,
                f"Кадр {index}: расчет не подтвержден. Проверьте GitHub Actions.",
                "Никаких платных запросов не выполнялось."
            ])
    return format_report("QUOTED_NO_CHARGE", [
        *summary,
        "",
        f"**Итого: {total:g} credits за {len(bodies)} клипов по 5 секунд.**",
        "Это оценка, а не резервирование цены или разрешение на генерацию."
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.event.is_file():
        raise SystemExit("GITHUB_EVENT_PATH not found")
    event = json.loads(args.event.read_text(encoding="utf-8"))
    report = run(event)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(report.splitlines()[2])  # Safe status only, no secrets, no JSON payload
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
