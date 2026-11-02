#!/usr/bin/env python3
"""Simba -> Wix A2E gateway. No A2E key on this machine or in Git."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_GATEWAY = "https://www.letsgo-world.co.il/_functions/simbaA2e"
MAX_DOWNLOAD = 200 * 1024 * 1024


class BridgeError(RuntimeError):
    pass


def gateway_url() -> str:
    url = os.environ.get("SIMBA_A2E_GATEWAY_URL", DEFAULT_GATEWAY)
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
        raise BridgeError("Only HTTPS gateway URL without credentials is allowed")
    return url


def token() -> str:
    secret = os.environ.get("SIMBA_A2E_GATEWAY_TOKEN", "")
    if len(secret) < 24:
        raise BridgeError("SIMBA_A2E_GATEWAY_TOKEN missing (the Wix Simba_Session_Key value)")
    return secret


def call_gateway(body: dict) -> dict:
    req = Request(
        gateway_url(),
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        # No automatic retries: paid start operations can have ambiguous outcomes.
        with urlopen(req, timeout=35) as response:
            result = json.load(response)
    except HTTPError as ex:
        try:
            reason = json.load(ex)
            error = str(reason.get("error", "HTTP_ERROR"))
        except (ValueError, OSError):
            error = "HTTP_ERROR"
        raise BridgeError(f"Gateway HTTP {ex.code}: {error}") from None
    except (URLError, TimeoutError, OSError) as ex:
        raise BridgeError("Network failure; do not retry a paid start automatically") from ex
    if not isinstance(result, dict) or not result.get("ok"):
        raise BridgeError(str(result.get("error", "INVALID_GATEWAY_RESPONSE"))
                          if isinstance(result, dict) else "INVALID_GATEWAY_RESPONSE")
    return result


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp = Path(handle.name)
    temp.replace(path)


def quote_body(args: argparse.Namespace) -> dict:
    if not args.image_url.startswith("https://"):
        raise BridgeError("Provide a publicly accessible HTTPS image URL")
    if not 0 < len(args.prompt) <= 2000:
        raise BridgeError("Prompt must be 1-2000 characters")
    return {"name": args.name, "image_url": args.image_url, "prompt": args.prompt,
            "model_version": "a2e", "video_time": 5}


def start_once(quote_path: Path, max_credits: float) -> dict:
    saved = json.loads(quote_path.read_text(encoding="utf-8"))
    body = saved.get("request_body")
    credits = (saved.get("quote") or {}).get("credits")
    if not isinstance(body, dict) or not isinstance(credits, (float, int)):
        raise BridgeError("Quote file is invalid; run quote again")
    if not 0 <= credits <= max_credits:
        raise BridgeError(f"Credits not approved: quoted {credits}, limit {max_credits}")
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:20]
    journal = quote_path.parent / (".a2e-start-" + fingerprint + ".json")
    journal.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(journal, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise BridgeError(f"Start already attempted: {journal}. Check task before any retry") from None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"status": "SUBMISSION_OUTCOME_UNKNOWN", "request_body_sha256": fingerprint}, handle)
    try:
        result = call_gateway({"action": "start", "request_body": body,
                               "max_credits": max_credits, "confirm_credits": True})
    except Exception:
        # Keep the journal, because the A2E POST may have charged already.
        raise
    write_json(journal, {"status": result.get("status", "OUTCOME_UNKNOWN"),
                         "task_id": result.get("task_id"), "request_body_sha256": fingerprint})
    return result


def safe_video_url(url: str) -> None:
    p = urlsplit(url)
    if p.scheme != "https" or not p.netloc or p.username or p.password:
        raise BridgeError("A2E returned a non-HTTPS result URL")
    if p.hostname in {"localhost", "127.0.0.1", "::1"} or (
            p.hostname and re.match(r"^(10|127|169\.254|192\.168)\.", p.hostname)):
        raise BridgeError("A2E returned a local result URL")


def download_video(task_id: str, output: Path) -> dict:
    result = call_gateway({"action": "status", "task_id": task_id})
    if result.get("status") != "completed":
        raise BridgeError("Task not completed: " + str(result.get("status")))
    url = result.get("result_url")
    if not isinstance(url, str):
        raise BridgeError("Completed task has no result URL")
    safe_video_url(url)
    if output.exists():
        raise BridgeError("Output exists; refusing overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".partial")
    try:
        request = Request(url, headers={"Accept": "video/mp4,application/octet-stream"})
        with urlopen(request, timeout=90) as source, open(temp, "xb") as out:
            if source.headers.get("Content-Length") and int(source.headers["Content-Length"]) > MAX_DOWNLOAD:
                raise BridgeError("Video exceeds download size limit")
            received = 0
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > MAX_DOWNLOAD:
                    raise BridgeError("Video exceeds download size limit")
                out.write(chunk)
        if received == 0:
            raise BridgeError("Downloaded video is empty")
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    return {"task_id": task_id, "file": str(output), "bytes": received,
            "handoff": "Use the filename as scenes[].clip in integrations/video/jobs/<packageId>/video-spec.json"}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("doctor", help="Read-only A2E token/quote check; no generation")
    q = sub.add_parser("quote", help="Free credit quote; saves request body")
    q.add_argument("--image-url", required=True)
    q.add_argument("--prompt", required=True)
    q.add_argument("--name", default="Simba A2E clip")
    q.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("start", help="Paid task: only with explicit --send and limit")
    s.add_argument("--quote-file", required=True, type=Path)
    s.add_argument("--max-credits", type=float, required=True)
    s.add_argument("--send", action="store_true")
    t = sub.add_parser("status")
    t.add_argument("task_id")
    d = sub.add_parser("download")
    d.add_argument("task_id")
    d.add_argument("--output", required=True, type=Path)
    return p


def main() -> int:
    a = parser().parse_args()
    try:
        if a.action == "doctor":
            result = call_gateway({"action": "doctor"})
        elif a.action == "quote":
            result = call_gateway({"action": "quote", "request_body": quote_body(a)})
            write_json(a.out, {"request_body": result["request_body"], "quote": result["quote"]})
            result = {"quote": result["quote"], "saved": str(a.out)}
        elif a.action == "start":
            if not a.send:
                raise BridgeError("Paid start blocked: add --send after approving the quoted credits")
            if not (0 <= a.max_credits < float("inf")):
                raise BridgeError("Invalid credit limit")
            result = start_once(a.quote_file, a.max_credits)
        elif a.action == "status":
            result = call_gateway({"action": "status", "task_id": a.task_id})
        else:
            result = download_video(a.task_id, a.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (BridgeError, ValueError, KeyError, OSError) as ex:
        print("A2E_BLOCKED: " + str(ex), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
