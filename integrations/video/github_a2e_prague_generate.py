#!/usr/bin/env python3
"""One-time, owner-approved A2E Prague video generation (6 x 5 sec; 180 credits max).

Only one source issue is accepted. A GitHub issue comment acts as durable
'start attempted' journal: it is posted before ANY billable A2E HTTP POST.
Never automatically retry a paid POST when the response is ambiguous.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from datetime import datetime, timezone
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from github_a2e_issue_bridge import build_bodies, request_quote

APPROVED_ISSUE = 8
APPROVED_CAP = 180
PER_SCENE_LIMIT = 30
TRIGGER_LABEL = "a2e-recover-180"
JOURNAL_MARKER = "A2E_PRAGUE_RECOVERY_VERIFIED_ZERO_START_20261103_ISSUE8"
API_BASE = "https://api.a2e.ai"
GITHUB_COMMENTS = "https://api.github.com/repos/legur/Simba/issues/8/comments"
EXPECTED_MEDIA_SUFFIXES = [
    "377e66bfa46b4a87a0223b02bec5d6f0",
    "2eb605400d914b6da8f84ff0700b40e0",
    "f208d7e3ca3b4a06b1e4d9fca4ccb969",
    "f203b5cc44ab4f4a99db77cc8fec717c",
    "76f420f19600473d8f7739da27e85b1c",
    "60d4cd52cae94899982832c7cc30a670",
]
# IDs are pinned to the six existing uploaded Rafael images.
EXPECTED_URLS = [
    "https://static.wixstatic.com/media/7fd7b8_" + suffix + "~mv2.jpg"
    for suffix in EXPECTED_MEDIA_SUFFIXES
]


class StopGeneration(Exception):
    pass


def checked_api(response: object) -> dict:
    if not isinstance(response, dict) or response.get("code") != 0:
        code = response.get("code") if isinstance(response, dict) else None
        safe_code = str(code) if type(code) in (int, str) and len(str(code)) <= 28 and str(code).replace("_", "").isalnum() else "UNKNOWN"
        raise StopGeneration("A2E_REJECTED_CODE_" + safe_code + "; no automatic retry")
    data = response.get("data")
    if not isinstance(data, dict):
        raise StopGeneration("A2E returned an invalid data envelope")
    return data


def read_json(req: Request, *, timeout: int = 30) -> dict:
    try:
        with urlopen(req, timeout=timeout) as response:
            if response.status != 200 and response.status != 201:
                raise StopGeneration("Remote HTTP status not accepted")
            data = json.load(response)
            if not isinstance(data, dict):
                raise StopGeneration("Remote response must be JSON object")
            return data
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        # No raw body, no API key, no automatic repeat after a start attempt.
        raise StopGeneration("Remote request error; reconcile before retry") from None


def a2e_start(body: dict, key: str) -> dict:
    req = Request(
        API_BASE + "/v1/userImage2Video/start",
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    )
    try:
        with urlopen(req, timeout=40) as response:
            if response.status != 200:
                raise StopGeneration("A2E_START_HTTP_" + str(response.status))
            payload = json.load(response)
            if not isinstance(payload, dict):
                raise StopGeneration("A2E_START_INVALID_RESPONSE")
            return payload
    except HTTPError as ex:
        # The numeric HTTP status and documented business code are safe to report.
        # Never show raw response bodies or request headers.
        code = ""
        try:
            payload = json.load(ex)
            value = payload.get("code") if isinstance(payload, dict) else None
            if type(value) in (int, str) and len(str(value)) <= 28 and str(value).replace("_", "").isalnum():
                code = "_CODE_" + str(value)
        except (ValueError, OSError, TypeError):
            pass
        raise StopGeneration("A2E_START_HTTP_" + str(ex.code) + code + "; no automatic retry") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise StopGeneration("A2E_START_NETWORK_AMBIGUOUS; do not retry automatically") from None


def a2e_status(task_id: str, key: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,96}", task_id):
        raise StopGeneration("Invalid A2E task ID")
    req = Request(
        API_BASE + "/v1/userImage2Video/" + quote(task_id, safe=""),
        headers={"Authorization": "Bearer " + key}
    )
    return read_json(req, timeout=25)


def github_request(method: str, *, json_body: dict | None = None) -> object:
    token = os.environ.get("GH_TOKEN", "")
    if len(token) < 20:
        raise StopGeneration("GitHub issues-write credential is missing")
    req = Request(
        GITHUB_COMMENTS + ("?per_page=100" if method == "GET" else ""),
        method=method,
        data=(json.dumps(json_body).encode("utf-8") if json_body is not None else None),
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    )
    try:
        with urlopen(req, timeout=20) as response:
            if response.status not in (200, 201):
                raise StopGeneration("GitHub journal is unavailable")
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise StopGeneration("GitHub journal unavailable; no paid start") from None


def claim_start() -> None:
    comments = github_request("GET")
    if not isinstance(comments, list) or len(comments) >= 100:
        raise StopGeneration("Existing start journal could not be verified")
    for item in comments:
        if isinstance(item, dict) and JOURNAL_MARKER in str(item.get("body", "")):
            raise StopGeneration("A paid generation has already been attempted for this issue")
    receipt = github_request("POST", json_body={
        "body": JOURNAL_MARKER + "\n\nStart authorized: six A2E clips, maximum quoted total 180 credits.\n"
                "Persistent no-retry journal established BEFORE any paid API POST.\n"
                "If an outcome becomes ambiguous, manually inspect A2E tasks and billing."
    })
    if not isinstance(receipt, dict) or not receipt.get("id"):
        raise StopGeneration("Start journal not durably acknowledged")
    # A second explicit preflight guards against issue state conflicts.
    # The workflow also serializes concurrent runs with the same issue number.


def validated_request(event: dict, cap: int) -> list[dict]:
    if cap != APPROVED_CAP:
        raise StopGeneration("Only the explicitly authorized 180-credit cap is allowed")
    if (event.get("repository") or {}).get("full_name") not in (None, "legur/Simba"):
        raise StopGeneration("Unexpected repository")
    issue = event.get("issue") or {}
    if issue.get("number") != APPROVED_ISSUE or event.get("action") != "labeled":
        raise StopGeneration("Only issue #8's labeled event may start")
    if (event.get("label") or {}).get("name") != TRIGGER_LABEL:
        raise StopGeneration("Missing the approved spend label")
    # Reuse the no-charge quote validator by mapping the trigger event label.
    fake = dict(event)
    fake["label"] = {"name": "a2e-quote"}
    bodies = build_bodies(fake)
    if len(bodies) != 6 or [x["image_url"] for x in bodies] != EXPECTED_URLS:
        raise StopGeneration("Approved six images have changed; paid start blocked")
    for body in bodies:
        body["auto_add_audio"] = False
        body["number_of_images"] = 1
    return bodies


def priced_within_cap(bodies: list[dict], key: str, quote_fn=request_quote) -> list[float]:
    quotes = []
    for body in bodies:
        data = checked_api(quote_fn(body, key))
        available = data.get("available") is True and data.get("exact") is True
        price = data.get("coins")
        if (not available or type(price) not in (float, int)
                or not math.isfinite(price) or price > PER_SCENE_LIMIT or price < 0):
            raise StopGeneration("Quote exceeds per-scene limit or is unavailable")
        quotes.append(float(price))
    if sum(quotes) > APPROVED_CAP:
        raise StopGeneration("Total A2E quote exceeds user-approved 180 credits")
    return quotes


def _recent(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed >= datetime(2026, 11, 3, 20, 9, tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return False


def verify_no_paid_effect_since_first_attempt(key: str) -> None:
    """Fail closed unless BOTH the task ledger and the credits ledger show zero."""
    api = [
        ("/v1/userImage2Video/allRecords?pageNum=1&pageSize=100", "rows"),
        ("/v1/transactionRecord/creditsHistory?pageNum=1&pageSize=100&is_consumption=true&startDate=2026-11-03T20%3A09%3A00Z", "rows"),
    ]
    for endpoint, field in api:
        req = Request(
            API_BASE + endpoint,
            method="GET",
            headers={"Authorization": "Bearer " + key, "Accept": "application/json"}
        )
        data = checked_api(read_json(req, timeout=30))
        rows = data.get(field)
        if not isinstance(rows, list) or len(rows) >= 100 or (isinstance(data.get("count"), int) and data["count"] > 100):
            raise StopGeneration("Reconciliation incomplete; no paid retry")
        if any(not isinstance(x, dict) or _recent(x.get("createdAt")) for x in rows):
            raise StopGeneration("A2E shows a recent task or charge; no paid retry")


def download_video(result_url: str, target: Path) -> None:
    url = urlsplit(result_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise StopGeneration("Result URL is not safe HTTPS")
    if url.hostname in ("localhost", "127.0.0.1", "::1"):
        raise StopGeneration("Result URL refers to a local host")
    req = Request(result_url, headers={"Accept": "video/mp4,application/octet-stream"})
    try:
        with urlopen(req, timeout=90) as stream, target.open("xb") as output:
            if stream.geturl().startswith("http://"):
                raise StopGeneration("Untrusted result redirect")
            max_bytes = 180 * 1024 * 1024
            size = 0
            while True:
                part = stream.read(1024 * 1024)
                if not part:
                    break
                size += len(part)
                if size > max_bytes:
                    raise StopGeneration("Downloaded video too large")
                output.write(part)
            if size < 1000:
                raise StopGeneration("Downloaded video empty")
    except (HTTPError, URLError, TimeoutError, OSError):
        raise StopGeneration("Result download unavailable") from None


def run(event: dict, workdir: Path, *, cap: int = 180) -> dict:
    output = {"status": "NOT_STARTED", "approved_cap": cap, "task_ids": [],
              "quoted_credits": [], "scenes": [], "note": ""}
    workdir.mkdir(parents=True, exist_ok=True)
    jsonpath = workdir / "generation_status.json"

    def persist() -> None:
        jsonpath.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        bodies = validated_request(event, cap)
        key = os.environ.get("A2E_API_KEY", "")
        if not key.startswith("sk_") or len(key) < 15:
            raise StopGeneration("GitHub Actions A2E_API_KEY missing")
        prices = priced_within_cap(bodies, key)
        output["quoted_credits"] = prices
        output["status"] = "QUOTED_AND_UNDER_CAP"
        persist()

        verify_no_paid_effect_since_first_attempt(key)
        claim_start()  # NEW DURABLE JOURNAL AFTER VERIFIED ZERO; BEFORE FIRST PAID POST.
        output["status"] = "PAID_START_JOURNALED"
        persist()

        confirmed_charges = 0.0
        for index, (body, price) in enumerate(zip(bodies, prices), start=1):
            # Requote each exact body just before the paid POST, fail closed.
            fresh = priced_within_cap([body], key)[0]
            if fresh > PER_SCENE_LIMIT or confirmed_charges + fresh > APPROVED_CAP:
                raise StopGeneration("Remaining credit allowance insufficient")
            output["status"] = "START_ATTEMPT_IN_PROGRESS"
            output["current_scene"] = index
            persist()
            # NO retry: POST can create/bill an A2E task even if response is lost.
            data = checked_api(a2e_start(body, key))
            task_id = data.get("_id")
            if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,96}", task_id):
                raise StopGeneration("Start response has no task ID; billing outcome uncertain")
            billed = data.get("coins")
            if type(billed) in (int, float) and math.isfinite(billed) and billed >= 0:
                confirmed_charges += float(billed)
            else:
                confirmed_charges += float(fresh)
            output["task_ids"].append(task_id)
            output["scenes"].append({"name": body["name"], "task_id": task_id,
                                      "quoted": fresh, "reported_coins": billed,
                                      "current_status": "submitted"})
            persist()
            if confirmed_charges > APPROVED_CAP:
                raise StopGeneration("A2E billed more than approved; stopped all further submissions")
        output["status"] = "ALL_SIX_TASKS_SUBMITTED"
        output.pop("current_scene", None)
        persist()

        # A2E is asynchronous: poll details without further billable POSTs.
        started = time.monotonic()
        while time.monotonic() - started < 18 * 60:
            pending = 0
            for index, row in enumerate(output["scenes"], start=1):
                if row["current_status"] in ("completed", "failed", "blocked"):
                    continue
                try:
                    detail = checked_api(a2e_status(row["task_id"], key))
                except StopGeneration:
                    pending += 1
                    continue
                status = detail.get("current_status")
                if isinstance(status, str):
                    row["current_status"] = status
                if status == "completed":
                    result_url = detail.get("result_url")
                    if isinstance(result_url, str) and result_url.startswith("https://"):
                        clip = workdir / ("scene_%02d.mp4" % index)
                        try:
                            download_video(result_url, clip)
                            row["artifact_file"] = clip.name
                        except StopGeneration:
                            row["download"] = "failed"
                    else:
                        row["download"] = "result_url_missing"
                elif status not in ("failed", "blocked"):
                    pending += 1
            persist()
            if pending == 0:
                break
            time.sleep(13)

        completed = sum(1 for row in output["scenes"] if row["current_status"] == "completed")
        output["status"] = ("COMPLETED_" + str(completed) + "_OF_6"
                            if completed == 6 else "PARTIALLY_READY_OR_PROCESSING")
        persist()
    except StopGeneration as ex:
        output["status"] = "STOPPED"
        output["note"] = str(ex)
        persist()
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--cap", type=int, required=True)
    args = parser.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    result = run(event, args.dir, cap=args.cap)
    report = "\n".join([
        "### Simba A2E paid generation — Prague",
        "",
        "**Status:** " + result["status"],
        "**Approved ceiling:** 180 credits for 6 clips of 5 seconds",
        "**Quoted total:** " + str(sum(result["quoted_credits"])) + " credits",
        "**Started task IDs:** " + ", ".join(result["task_ids"]),
        "**Note:** " + result.get("note", ""),
        "",
        "No automatic retries of paid start requests. On ambiguous result inspect A2E billing before continuing.",
    ])
    (args.dir / "report.md").write_text(report, encoding="utf-8")
    print(result["status"], "tasks=", len(result["task_ids"]))
    return 0 if result["status"] not in ("STOPPED", "NOT_STARTED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
