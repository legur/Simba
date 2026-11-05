#!/usr/bin/env python3
"""One-time, at-most-30-credit A2E I2V test using a PREVIOUSLY uploaded image.

No presign, no storage PUT, no re-upload: the 3days-apac CDN image was already
verified with User-Agent: Genjutsu by GitHub Actions. A paid A2E generation
POST is attempted AT MOST ONCE after an exact free quote and durable journal.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request

from github_a2e_prague_one_clip_3days import (
    NAME, MAX_VIDEO, build_body, exact_quote, journal, Stopped,
)
from github_a2e_prague_upload_one import verify_staged_image
from github_a2e_prague_generate import (
    API_BASE, StopGeneration, a2e_start, a2e_status, checked_api,
    download_video, read_json,
)

ISSUE = 8
LABEL = "a2e-existing-cdn-one-video-30"
JOURNAL_MARKER = "A2E_PRAGUE_EXISTING_CDN_VIDEO_START_20261105_ONE_TIME"
SOURCE_CDN = ("https://3days-apac.downloadaivideo.com/adam2eve/stable/"
              "user/695cf6da60588c00590a9ad6/"
              "simba-prague-scene1-362e1a29e9e146cabd53ba7027b1a03c.jpg")
MAX_NEW_CREDITS = 30


def validate_event(event: dict, cap: int) -> None:
    issue = event.get("issue") or {}
    if (cap != MAX_NEW_CREDITS
            or event.get("action") != "labeled"
            or (event.get("label") or {}).get("name") != LABEL
            or (event.get("repository") or {}).get("full_name") != "legur/Simba"
            or issue.get("number") != ISSUE
            or (issue.get("user") or {}).get("login", "").lower() != "legur"
            or issue.get("pull_request") is not None):
        raise Stopped("Unauthorized event, label, repository, owner, or credit cap")


def already_started(key: str) -> None:
    """Read-only check before committing the no-retry marker."""
    req = Request(
        API_BASE + "/v1/userImage2Video/allRecords?pageNum=1&pageSize=100",
        method="GET",
        headers={"Authorization": "Bearer " + key,
                 "Accept": "application/json", "User-Agent": "Genjutsu"},
    )
    try:
        result = checked_api(read_json(req, timeout=25))
    except StopGeneration as exc:
        raise Stopped("Task history could not be verified: " + str(exc)) from None
    rows = result.get("rows")
    total = result.get("count")
    if (not isinstance(rows, list) or len(rows) >= 100
            or (type(total) is int and total > 100)):
        raise Stopped("Task history incomplete; no new paid generation")
    for row in rows:
        if not isinstance(row, dict):
            raise Stopped("Malformed task history; no paid generation")
        linked = row.get("image_urls") or []
        if (row.get("name") == NAME
                or row.get("image_url") == SOURCE_CDN
                or (isinstance(linked, list) and SOURCE_CDN in linked)):
            raise Stopped("Existing A2E task for this image/name found; no duplicate")


def run(event: dict, folder: Path, *, max_new: int = 30, pause=time.sleep) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    state = {
        "status": "NOT_STARTED", "new_credit_cap": MAX_NEW_CREDITS,
        "new_presign_credits": 0, "video_quote_credits": None,
        "cdn_image_verified": False, "task_id": None,
        "task_status": None, "mp4_filename": None, "video_url": None,
        "note": "",
    }
    def save():
        (folder / "status.json").write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        validate_event(event, max_new)
        key = os.environ.get("A2E_API_KEY", "")
        if len(key) < 15 or not key.startswith("sk_"):
            raise Stopped("A2E_API_KEY unavailable; no generation")
        # Explicit User-Agent is already set in this shared CDN GET helper.
        if not verify_staged_image(SOURCE_CDN):
            raise Stopped("Existing 3days CDN JPEG cannot be read with User-Agent")
        state["cdn_image_verified"] = True
        state["status"] = "CDN_VERIFIED"
        save()

        already_started(key)
        body = build_body(SOURCE_CDN)  # 5s, a2e, audio off, one video.
        credits = exact_quote(body, key)
        if credits > MAX_NEW_CREDITS or credits < 0:
            raise Stopped("Exact quote exceeds the approved 30-credit limit")
        state["video_quote_credits"] = credits
        state["status"] = "FREE_EXACT_QUOTE_ACCEPTED"
        save()

        # This journal is published BEFORE the sole potentially billable POST.
        journal(
            JOURNAL_MARKER,
            "Approved by owner for ONE Prague Charles Bridge 5-second I2V "
            "using the already uploaded and Genjutsu-verified 3days-apac JPEG. "
            "No new presign or upload. Exact price <=30 credits. "
            "No retry of this generation POST under any network failure.",
        )
        state["status"] = "PAID_START_ATTEMPT_JOURNALED"
        save()

        # Exactly one paid start call. Do not retry on any exception/timeout.
        try:
            response = a2e_start(body, key)
            accepted = checked_api(response)
        except StopGeneration as exc:
            raise Stopped(str(exc)) from None
        task_id = accepted.get("_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,96}", task_id):
            raise Stopped("A2E response lacks valid task ID; billing uncertain; no retry")
        state["task_id"] = task_id
        state["task_status"] = accepted.get("current_status")
        state["status"] = "VIDEO_TASK_ACCEPTED"
        save()

        # Read-only polls, including result video download when ready.
        deadline = time.monotonic() + 8 * 60
        while time.monotonic() < deadline:
            try:
                details = checked_api(a2e_status(task_id, key))
            except StopGeneration:
                pause(12)
                continue
            status = details.get("current_status")
            if isinstance(status, str):
                state["task_status"] = status
            if status == "completed":
                url = next(
                    (details.get(k) for k in ("result_url", "result_video_url", "video_url")
                     if isinstance(details.get(k), str) and details.get(k).startswith("https://")),
                    None,
                )
                if url is None:
                    state["status"] = "COMPLETE_BUT_VIDEO_URL_UNAVAILABLE"
                    save()
                    break
                state["video_url"] = url
                target = folder / "simba_prague_charles_bridge_5s.mp4"
                try:
                    download_video(url, target)  # Uses Genjutsu User-Agent.
                    state["mp4_filename"] = target.name
                    state["status"] = "VIDEO_READY"
                except StopGeneration as exc:
                    state["status"] = "VIDEO_COMPLETE_DOWNLOAD_FAILED"
                    state["note"] = str(exc)
                save()
                break
            if status in ("failed", "blocked"):
                state["status"] = "VIDEO_FAILED"
                state["refund_pending"] = details.get("refund_pending") is True
                state["has_refund_coin"] = details.get("hasRefundCoin") is True
                code = details.get("failed_code")
                if isinstance(code, (int, str)) and len(str(code)) < 40:
                    state["failure_code"] = str(code)
                save()
                break
            state["status"] = "VIDEO_PROCESSING"
            save()
            pause(15)
        else:
            state["status"] = "VIDEO_ACCEPTED_POLL_LATER"
            save()
    except Stopped as exc:
        state["status"] = "STOPPED"
        state["note"] = str(exc)
        save()

    report = [
        "### Simba A2E — one Prague clip using existing A2E CDN image",
        "",
        "**Status:** " + state["status"],
        "**New credit limit:** 30 (no presign/re-upload).",
        "**Exact pre-start quote:** " + str(state["video_quote_credits"]),
        "**3days CDN verified with User-Agent Genjutsu:** " + str(state["cdn_image_verified"]),
        "**A2E task ID:** " + str(state["task_id"]),
        "**A2E task status:** " + str(state["task_status"]),
        "**Result video URL:** " + str(state["video_url"]),
        "**MP4 in Actions artifact:** " + str(state["mp4_filename"]),
        "**Note:** " + state["note"],
        "",
        "No second paid POST is permitted, even after timeout or network error. "
        "No new file upload, additional clips, or social publishing.",
    ]
    (folder / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(state["status"], "task_id=", state["task_id"] or "none")
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-new", type=int, required=True)
    args = parser.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    result = run(event, args.out, max_new=args.max_new)
    return 0 if result["status"] not in ("STOPPED", "VIDEO_FAILED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
