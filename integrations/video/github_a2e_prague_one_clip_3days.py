#!/usr/bin/env python3
"""One-time A2E Prague bridge: one staged JPEG + at most one 5s video.

Maximum NEW possible spend: 1 R2 presign credit + 30 video credits.
Only A2E model "a2e" and the exact approved Prague Charles Bridge image.
Before any credit-bearing request create a permanent GitHub issue journal.
The A2E start endpoint has no documented idempotency guarantee: NEVER retry.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from github_a2e_prague_upload_one import (
    SOURCE_IMAGE, UploadStopped, api_get_pricing, read_source_image,
    charged_presign, upload_bytes, verify_staged_image, gh_request,
)
from github_a2e_issue_bridge import request_quote
from github_a2e_prague_generate import a2e_start, a2e_status, checked_api, download_video, StopGeneration

ISSUE = 8
TRIGGER = "a2e-one-clip-3days-31"
PRESIGN_MARKER = "A2E_PRAGUE_3DAYS_ONE_PRESIGN_20261104"
START_MARKER = "A2E_PRAGUE_3DAYS_ONE_VIDEO_START_20261104"
MAX_STAGE = 1.0
MAX_VIDEO = 30.0
MAX_NEW = 31.0

NAME = "Prague Charles Bridge - Simba proof 20261104"
PROMPT = ("Slow cinematic dolly toward Charles Bridge, realistic gentle winter "
          "snowfall, golden reflections in the Vltava, preserve Prague architecture "
          "and bridge structure, no captions and no logos.")
A2E_API_HOST = "api.a2e.ai"

class Stopped(Exception):
    pass


def validate_event(event: dict) -> None:
    issue = event.get("issue") or {}
    if (event.get("action") != "labeled" or
        (event.get("label") or {}).get("name") != TRIGGER or
        (event.get("repository") or {}).get("full_name") != "legur/Simba" or
        issue.get("number") != ISSUE or
        (issue.get("user") or {}).get("login", "").lower() != "legur"):
        raise Stopped("Unapproved request; no credits spent")


def journal(marker: str, note: str) -> None:
    """Claim a unique irreversible issue-comment marker, checked before paid action."""
    try:
        items = gh_request("GET")
    except UploadStopped as exc:
        raise Stopped(str(exc)) from None
    if not isinstance(items, list) or len(items) >= 100:
        raise Stopped("Incomplete GitHub journal; cannot authorize a paid request")
    if any(marker in str(x.get("body", "")) for x in items if isinstance(x, dict)):
        raise Stopped("Previous credit-bearing attempt already journaled; no retry")
    try:
        receipt = gh_request("POST", {"body": marker + "\n\n" + note})
    except UploadStopped as exc:
        raise Stopped(str(exc)) from None
    if not isinstance(receipt, dict) or not receipt.get("id"):
        raise Stopped("GitHub journal not acknowledged; no paid request")


def image_cdn_is_expected(url: str) -> bool:
    try:
        obj = urlsplit(url)
        host = obj.hostname or ""
        return (obj.scheme == "https" and not obj.username and not obj.password
                and obj.port in (None, 443) and host.startswith("3days-apac.")
                and (host.endswith(".makefun.ai") or
                     host.endswith(".downloadaivideo.com")))
    except (ValueError, AttributeError):
        return False


def build_body(cdn_url: str) -> dict:
    if not image_cdn_is_expected(cdn_url):
        raise Stopped("Wrong A2E CDN bucket; expected 3days-apac")
    return {
        "name": NAME,
        "image_url": cdn_url,
        "prompt": PROMPT,
        "model_version": "a2e",
        "video_time": 5,
        "number_of_images": 1,
        "auto_add_audio": False,
    }


def exact_quote(body: dict, key: str) -> float:
    try:
        reply = request_quote(body, key)
    except Exception:
        raise Stopped("Free A2E quote unavailable") from None
    data = reply.get("data") if isinstance(reply, dict) else None
    fee = data.get("coins") if isinstance(data, dict) else None
    if (not isinstance(reply, dict) or reply.get("code") != 0
            or not isinstance(data, dict) or data.get("available") is not True
            or data.get("exact") is not True
            or type(fee) not in (float, int)
            or not math.isfinite(fee) or not 0 <= fee <= MAX_VIDEO):
        raise Stopped("Free quote is missing, inexact, or exceeds 30 video credits")
    return float(fee)


def run(event: dict, output_dir: Path, *, max_new: int = 31, pause=time.sleep) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "NOT_STARTED",
        "max_new_credits": MAX_NEW,
        "stage_price": None,
        "video_quote": None,
        "image_cdn_url": None,
        "cdn_verified": False,
        "task_id": None,
        "task_status": None,
        "clip_file": None,
        "note": ""
    }
    def persist() -> None:
        (output_dir / "state.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        validate_event(event)
        if max_new != MAX_NEW:
            raise Stopped("Unauthorized change to the 31-credit ceiling")
        key = os.environ.get("A2E_API_KEY", "")
        if not key.startswith("sk_") or len(key) < 15:
            raise Stopped("A2E_API_KEY missing from GitHub Actions")
        fee = api_get_pricing(key)  # GET only
        if not isinstance(fee, (int, float)) or not 0 <= fee <= MAX_STAGE:
            raise Stopped("R2 upload price exceeds the one-credit cap")
        result["stage_price"] = float(fee)
        original = read_source_image()  # GET only
        persist()

        # Durable claim BEFORE the one possibly chargeable R2-presign POST.
        journal(PRESIGN_MARKER,
                "One owner-approved A2E presign at a live price <=1 credit. "
                "Using 3days-apac. No automatic repeat.")
        result["status"] = "PRESIGN_ATTEMPTED"
        persist()
        try:
            signed_url, cdn_url = charged_presign(key, len(original))
        except UploadStopped as exc:
            raise Stopped(str(exc)) from None
        result["image_cdn_url"] = cdn_url
        result["status"] = "PRESIGN_ISSUED"
        persist()

        if not image_cdn_is_expected(cdn_url):
            raise Stopped("A2E returned unexpected image bucket; no video start")
        try:
            upload_bytes(signed_url, original)
        except UploadStopped as exc:
            raise Stopped(str(exc)) from None
        result["status"] = "IMAGE_BYTES_UPLOADED"
        persist()
        if not verify_staged_image(cdn_url):
            raise Stopped("A2E 3days CDN image GET not verifiable; stop without video charge")
        result["cdn_verified"] = True
        result["status"] = "CDN_IMAGE_VERIFIED"
        persist()

        # The priced object and paid start object must be exactly identical.
        body = build_body(cdn_url)
        price = exact_quote(body, key)
        result["video_quote"] = price
        result["status"] = "EXACT_FREE_QUOTE_OK"
        persist()
        if result["stage_price"] + price > max_new:
            raise Stopped("Total new cost exceeds the 31-credit allowance")
        journal(START_MARKER,
                "One image-to-video paid start only, a2e model, 5 seconds, "
                "latest exact quote <=30 credits; total new spend <=31. "
                "No automatic repeat after a lost response.")
        result["status"] = "VIDEO_POST_ATTEMPTED"
        persist()

        # This is the ONLY possibly paid video POST. No retries or fallback.
        try:
            reply = a2e_start(body, key)
            data = checked_api(reply)
        except StopGeneration as exc:
            raise Stopped(str(exc)) from None
        task_id = data.get("_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,96}", task_id):
            raise Stopped("Video start did not provide a task ID; do not retry")
        result["task_id"] = task_id
        result["status"] = "VIDEO_TASK_ACCEPTED"
        persist()

        # Read-only polls. Full generation may exceed the runner's wait budget.
        deadline = time.monotonic() + 8 * 60
        while time.monotonic() < deadline:
            try:
                details = checked_api(a2e_status(task_id, key))
            except StopGeneration:
                pause(12)
                continue
            status = details.get("current_status")
            if isinstance(status, str):
                result["task_status"] = status
            if status == "completed":
                url = details.get("result_url")
                if not isinstance(url, str) or not url.startswith("https://"):
                    raise Stopped("Generation completed but result_url missing")
                video_file = output_dir / "prague_charles_bridge_5sec.mp4"
                try:
                    download_video(url, video_file)
                except StopGeneration as exc:
                    raise Stopped("Completed task; MP4 download failed: " + str(exc)) from None
                result["clip_file"] = video_file.name
                result["status"] = "VIDEO_READY"
                persist()
                break
            if status in ("failed", "blocked"):
                reason = details.get("failed_code")
                if isinstance(reason, (int, str)) and len(str(reason)) <= 35:
                    result["failure_code"] = str(reason)
                result["refund_pending"] = details.get("refund_pending") is True
                result["has_refund_coin"] = details.get("hasRefundCoin") is True
                result["status"] = "VIDEO_FAILED"
                persist()
                break
            result["status"] = "VIDEO_PROCESSING"
            persist()
            pause(15)
        else:
            result["status"] = "VIDEO_TASK_ACCEPTED_POLL_LATER"
            persist()
    except Stopped as exc:
        result["note"] = str(exc)
        result["status"] = "STOPPED"
        persist()

    summary = [
        "### A2E Prague — one guarded 3days-apac test clip",
        "",
        "**Status:** " + result["status"],
        "**New credit ceiling:** 31 credits (1 staging + up to 30 video).",
        "**Stage price:** " + str(result["stage_price"]),
        "**Video quote:** " + str(result["video_quote"]),
        "**Image CDN:** " + (result["image_cdn_url"] or "none"),
        "**Image CDN GET verified:** " + str(result["cdn_verified"]),
        "**Task ID:** " + (result["task_id"] or "none"),
        "**Task status:** " + str(result["task_status"]),
        "**MP4 artifact:** " + str(result["clip_file"]),
        "**Notes:** " + result["note"],
        "",
        "A paid POST is never automatically retried. This run cannot start other clips or publish anything."
    ]
    (output_dir / "report.md").write_text("\n".join(summary), encoding="utf-8")
    print(result["status"], "task_id_present=", bool(result["task_id"]))
    return result


def main() -> int:
    argp = argparse.ArgumentParser()
    argp.add_argument("--event", type=Path, required=True)
    argp.add_argument("--out", type=Path, required=True)
    argp.add_argument("--max-new", type=int, required=True)
    a = argp.parse_args()
    event = json.loads(a.event.read_text(encoding="utf-8"))
    result = run(event, a.out, max_new=a.max_new)
    return 0 if result["status"] in ("VIDEO_READY", "VIDEO_PROCESSING",
                                    "VIDEO_TASK_ACCEPTED_POLL_LATER") else 2

if __name__ == "__main__":
    raise SystemExit(main())
