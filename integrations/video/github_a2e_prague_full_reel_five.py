#!/usr/bin/env python3
"""Generate the remaining five 5s Prague clips with A2E (no automatic paid retries).

Issue #8 supplies six already-approved shot prompts/URLs. Scene 1 is completed.
This one-shot workflow uses only scenes 2-6, <=5 one-credit R2 presigns and
<=5 30-credit video starts. All credit-bearing POSTs are journaled first.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from github_a2e_issue_bridge import build_bodies, request_quote, validate_generation_body
from github_a2e_prague_generate import (
    API_BASE, EXPECTED_URLS, a2e_start, a2e_status, checked_api,
    download_video, read_json, StopGeneration,
)
from github_a2e_prague_upload_one import (
    api_get_pricing, charged_presign, upload_bytes, verify_staged_image,
    UploadStopped,
)
from github_a2e_prague_one_clip_3days import (
    Stopped, journal, image_cdn_is_expected,
)

ISSUE = 8
LABEL = "a2e-prague-five-scenes-full-reel-155-20261105"
MARKER_PREFIX = "A2E_PRAGUE_FULL_REEL_20261105_SINGLE_ATTEMPT"
MAX_NEW_CREDITS = 155.0
MAX_STAGE_CREDITS = 1.0
MAX_VIDEO_CREDITS = 30.0
FIRST_TASK = "6aec681b899ba60e0500350a"
FIRST_VIDEO = "https://3days-apac.downloadaivideo.com/AzureDragon/FS/e131e14b3ad94b9d871234c5e54b0614.mp4"

SCENE_NAMES = [
    "Prague Charles Bridge", "Prague Old Town Market",
    "Simba winter traveller", "Prague Astronomical Clock",
    "Vintage Prague tram", "Prague New Year skyline",
]


def validate_event(event: dict, max_new: int) -> list[dict]:
    issue = event.get("issue") or {}
    if (max_new != int(MAX_NEW_CREDITS)
            or event.get("action") != "labeled"
            or (event.get("label") or {}).get("name") != LABEL
            or (event.get("repository") or {}).get("full_name") != "legur/Simba"
            or issue.get("number") != ISSUE
            or (issue.get("user") or {}).get("login") != "legur"
            or issue.get("pull_request") is not None):
        raise Stopped("Unapproved issue/owner/label or changed credit ceiling")
    fake = dict(event)
    fake["label"] = {"name": "a2e-quote"}
    try:
        bodies = build_bodies(fake)
    except (ValueError, TypeError) as ex:
        raise Stopped("Source issue validation failed: " + str(ex)) from None
    if len(bodies) != 6 or [b["image_url"] for b in bodies] != EXPECTED_URLS:
        raise Stopped("Six source URLs differ from the pinned approved Prague media")
    if [b["name"] for b in bodies] != SCENE_NAMES:
        raise Stopped("Source shot names differ from approved six scenes")
    for b in bodies:
        try:
            validate_generation_body(b)
        except ValueError as ex:
            raise Stopped("Required A2E prompt validation failed: " + str(ex)) from None
        if (b.get("model_version") != "a2e"
                or b.get("video_time") != 5
                or b.get("number_of_images") != 1
                or b.get("auto_add_audio") is not False):
            raise Stopped("Unsupported model, duration, audio, or output count")
    return bodies


def read_source_jpeg(url: str) -> bytes:
    if url not in EXPECTED_URLS:
        raise Stopped("Unapproved source JPEG URL")
    req = Request(url, headers={
        "User-Agent": "Genjutsu", "Accept": "image/jpeg"
    })
    try:
        with urlopen(req, timeout=35) as resp:
            if resp.status != 200 or "image/" not in resp.headers.get("Content-Type", ""):
                raise Stopped("Source JPEG returned invalid content type/status")
            raw = resp.read(12 * 1024 * 1024 + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise Stopped("Approved source image unavailable; no billable A2E request") from None
    if not (1000 < len(raw) <= 12 * 1024 * 1024 and
            raw[:2] == bytes.fromhex("ffd8")):
        raise Stopped("Approved source image not a valid size/signature JPEG")
    return raw


def exact_quote(body: dict, key: str) -> float:
    try:
        validate_generation_body(body)
        reply = request_quote(body, key)
    except Exception:
        raise Stopped("A2E free quote unavailable/invalid for a staged shot") from None
    if not isinstance(reply, dict) or reply.get("code") != 0:
        raise Stopped("A2E free quote rejected")
    data = reply.get("data")
    if not isinstance(data, dict) or data.get("available") is not True or data.get("exact") is not True:
        raise Stopped("A2E quote is not exact or unavailable")
    amount = data.get("coins")
    if (type(amount) not in (int, float)
            or not math.isfinite(amount) or not 0 <= amount <= MAX_VIDEO_CREDITS):
        raise Stopped("A2E per-video price exceeds 30 credits")
    # generationRequestValidated=false does NOT itself invalidate the price;
    # validate_generation_body above is the local schema preflight.
    return float(amount)


def ensure_no_duplicate_tasks(key: str, bodies: list[dict]) -> None:
    req = Request(
        API_BASE + "/v1/userImage2Video/allRecords?pageNum=1&pageSize=100",
        method="GET",
        headers={
            "Authorization": "Bearer " + key,
            "Accept": "application/json", "User-Agent": "Genjutsu",
        },
    )
    try:
        response = checked_api(read_json(req, timeout=30))
    except StopGeneration as ex:
        raise Stopped("A2E task reconciliation unavailable: " + str(ex)) from None
    rows = response.get("rows")
    count = response.get("count")
    if (not isinstance(rows, list) or len(rows) >= 100
            or (type(count) is int and count > 100)):
        raise Stopped("A2E task list incomplete, no paid request allowed")
    forbidden_names = {x["name"] for x in bodies[1:]}
    forbidden_urls = {x["image_url"] for x in bodies[1:]}
    for row in rows:
        if not isinstance(row, dict):
            raise Stopped("Malformed task history")
        if (row.get("name") in forbidden_names
                or row.get("image_url") in forbidden_urls
                or (isinstance(row.get("image_urls"), list)
                    and any(u in forbidden_urls for u in row["image_urls"]))):
            raise Stopped("A previously submitted scene 2-6 is already in the A2E task ledger")


def poll_to_completion(task_id: str, key: str, out: Path, pause=time.sleep) -> None:
    """GET only after paid task acceptance. No second billed start ever."""
    deadline = time.monotonic() + 11 * 60
    while time.monotonic() < deadline:
        try:
            info = checked_api(a2e_status(task_id, key))
        except StopGeneration:
            pause(12)
            continue
        current = info.get("current_status")
        if current == "completed":
            url = next(
                (info.get(x) for x in ("result_url", "result_video_url", "video_url")
                 if isinstance(info.get(x), str) and info[x].startswith("https://")),
                None,
            )
            if not url:
                raise Stopped("Completed task lacks a result video URL: " + task_id)
            try:
                download_video(url, out)
            except StopGeneration as ex:
                raise Stopped("Completed clip download error: " + str(ex)) from None
            return
        if current in ("failed", "blocked"):
            code = info.get("failed_code")
            safe = str(code)[:40] if isinstance(code, (int, str)) else "unspecified"
            raise Stopped("A2E task terminal failure, code=" + safe + ", task=" + task_id)
        pause(15)
    raise Stopped("Task still processing; no retry permitted; task=" + task_id)


def run(event: dict, out: Path, *, max_new: int = 155, pause=time.sleep) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    state = {
        "status": "NOT_STARTED", "max_new_credits": MAX_NEW_CREDITS,
        "staging_spend_credits": 0.0, "video_spend_estimate_credits": 0.0,
        "completed": [], "pending_task_id": None, "current_scene": None,
        "note": "", "started_utc": datetime.now(timezone.utc).isoformat(),
    }

    def persist() -> None:
        (out / "state.json").write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def create_report() -> None:
        lines = [
            "### A2E Prague full 6-scene reel — five remaining shots",
            "",
            "**Status:** " + state["status"],
            "**Authorization ceiling:** 155 new credits (5 uploads × up to 1, 5 videos × up to 30).",
            "**Estimated staging credits spent:** " + str(state["staging_spend_credits"]),
            "**Estimated accepted video costs:** " + str(state["video_spend_estimate_credits"]),
            "**Completed additional scenes:** " + str(len(state["completed"])) + "/5",
            "**Pending task ID:** " + str(state["pending_task_id"]),
            "**Note:** " + state["note"],
            "",
        ]
        for record in state["completed"]:
            lines.append(
                "- Scene " + str(record["index"]) + ": " + record["name"] +
                ", task " + record["task_id"] +
                ", MP4 " + record["clip_file"]
            )
        lines += [
            "", "Scene 1 (Charles Bridge) was already generated before this run.",
            "No automatic paid POST retries; paid journaling precedes every presign/start.",
            "Videos are available in the workflow artifact. Montage follows media validation.",
        ]
        (out / "report.md").write_text("\n".join(lines), encoding="utf-8")

    try:
        bodies = validate_event(event, max_new)
        key = os.environ.get("A2E_API_KEY", "")
        if not key.startswith("sk_") or len(key) < 15:
            raise Stopped("GitHub A2E_API_KEY is unavailable")
        stage_price = api_get_pricing(key)  # GET; free
        if (type(stage_price) not in (int, float)
                or not math.isfinite(stage_price)
                or not 0 <= stage_price <= MAX_STAGE_CREDITS):
            raise Stopped("A2E R2 presign fee exceeds 1 credit per image")
        ensure_no_duplicate_tasks(key, bodies)
        # Read-only first, before ANY expenditure.
        originals = [read_source_jpeg(b["image_url"]) for b in bodies[1:]]
        prices = [exact_quote(b, key) for b in bodies[1:]]
        if 5 * stage_price + sum(prices) > MAX_NEW_CREDITS:
            raise Stopped("Five-scene estimated cost exceeds the 155-credit ceiling")

        first_path = out / "scene_01.mp4"
        try:
            download_video(FIRST_VIDEO, first_path)
        except StopGeneration as ex:
            raise Stopped("Already completed first A2E video is unavailable: " + str(ex)) from None
        state["status"] = "PRECHECK_PASSED"
        persist()

        for index, (body, raw) in enumerate(zip(bodies[1:], originals), start=2):
            state["current_scene"] = index
            state["status"] = "SCENE_" + str(index) + "_PRESIGN_READY"
            persist()
            if (state["staging_spend_credits"]
                    + state["video_spend_estimate_credits"]
                    + stage_price + MAX_VIDEO_CREDITS > MAX_NEW_CREDITS):
                raise Stopped("Remaining authorized 155-credit budget is insufficient")

            journal(
                f"{MARKER_PREFIX}_SCENE_{index}_PRESIGN",
                f"Owner-approved full Prague reel. Scene {index} source: pinned image "
                f"({len(raw)} bytes). Up to {stage_price} credit for ONE presign; "
                "never repeat this POST automatically.",
            )
            # Charge may occur on presign, even if response is lost.
            state["staging_spend_credits"] += float(stage_price)
            state["status"] = "SCENE_" + str(index) + "_PRESIGN_ATTEMPTED"
            persist()
            try:
                signed, cdn = charged_presign(key, len(raw))
            except UploadStopped as ex:
                raise Stopped(str(ex)) from None
            if not image_cdn_is_expected(cdn):
                raise Stopped("A2E returned an unexpected CDN bucket")
            try:
                upload_bytes(signed, raw)
            except UploadStopped as ex:
                raise Stopped(str(ex)) from None
            if not verify_staged_image(cdn):
                raise Stopped("Uploaded scene cannot be read from A2E CDN with Genjutsu")
            staged_body = dict(body, image_url=cdn)
            # Exact quote of precisely the object sent to the paid endpoint.
            price = exact_quote(staged_body, key)
            if price + state["video_spend_estimate_credits"] + state["staging_spend_credits"] > MAX_NEW_CREDITS:
                raise Stopped("Exact staged-scene quote exceeds remaining budget")
            journal(
                f"{MARKER_PREFIX}_SCENE_{index}_PAID_VIDEO_START",
                f"Exactly ONE 5-second A2E video for scene {index}; "
                f"quote {price} credits, a2e model, audio off, required negative_prompt. "
                "Do not retry POST on timeout, HTTP failure, or ambiguous outcome.",
            )
            state["video_spend_estimate_credits"] += float(price)  # count possible spend
            state["status"] = "SCENE_" + str(index) + "_PAID_START_ATTEMPTED"
            persist()
            try:
                accepted = checked_api(a2e_start(staged_body, key))
            except StopGeneration as ex:
                raise Stopped(str(ex)) from None
            task_id = accepted.get("_id")
            if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,96}", task_id):
                raise Stopped("Accepted start returned invalid task id; do not retry")
            state["pending_task_id"] = task_id
            state["status"] = "SCENE_" + str(index) + "_ACCEPTED"
            persist()
            clip = out / ("scene_%02d.mp4" % index)
            poll_to_completion(task_id, key, clip, pause=pause)
            state["completed"].append({
                "index": index, "name": body["name"],
                "task_id": task_id, "clip_file": clip.name, "quoted_credits": price,
            })
            state["pending_task_id"] = None
            state["status"] = "SCENE_" + str(index) + "_READY"
            persist()
        state["status"] = "ALL_SIX_CLIPS_READY"
        persist()
    except (Stopped, UploadStopped, StopGeneration) as ex:
        state["note"] = str(ex)
        state["status"] = "STOPPED"
        persist()
    except Exception as ex:
        # Only exception type is safe to report. Raw API errors can echo credentials.
        state["note"] = "Unexpected error: " + type(ex).__name__
        state["status"] = "STOPPED"
        persist()
    create_report()
    print(state["status"], "ready_additional=", len(state["completed"]))
    return state


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--event", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-new", type=int, required=True)
    args = p.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    result = run(event, args.out, max_new=args.max_new)
    return 0 if result["status"] == "ALL_SIX_CLIPS_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
