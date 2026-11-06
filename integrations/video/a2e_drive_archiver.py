#!/usr/bin/env python3
"""Archive completed A2E image-to-video tasks in private Google Drive.

Only A2E GETs: this process NEVER invokes A2E start, quote, or presign.
Google Drive OAuth2 refresh and resumable uploads are separate write operations.
A2E CDN expiry is short; run this as a frequent scheduled GitHub Action.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

A2E_BASE = "https://api.a2e.ai"
VALID_TASK = re.compile(r"[A-Za-z0-9_-]{8,96}\Z")
VALID_FOLDER = re.compile(r"[A-Za-z0-9_-]{10,150}\Z")
PAGE_SIZE = 100
MAX_PAGES = 20
MAX_BYTES = 200 * 1024 * 1024
MAX_RECENT_TASKS = 75
SCAN_DAYS = 7


class ArchiveError(RuntimeError):
    pass


def _safe_a2e_error(message: str) -> ArchiveError:
    # Never include remote response bodies, signed URLs, auth tokens or headers.
    return ArchiveError(message)


def _api_get(url: str, key: str) -> dict:
    if not url.startswith(A2E_BASE + "/v1/userImage2Video/"):
        raise _safe_a2e_error("A2E endpoint not on the approved read-only API")
    req = Request(url, method="GET", headers={
        "Authorization": "Bearer " + key,
        "Accept": "application/json",
        "User-Agent": "Genjutsu",
    })
    try:
        with urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise _safe_a2e_error("A2E GET returned unexpected status")
            value = json.load(response)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError):
        raise _safe_a2e_error("A2E read-only GET failed") from None
    if not isinstance(value, dict) or value.get("code") != 0 or not isinstance(value.get("data"), dict):
        raise _safe_a2e_error("A2E response envelope invalid")
    return value["data"]


def list_records(key: str) -> list[dict]:
    """Exhaust paginated records; never silently omit pages."""
    results = []
    count = None
    for page in range(1, MAX_PAGES + 1):
        data = _api_get(
            A2E_BASE + "/v1/userImage2Video/allRecords?" +
            urlencode({"pageNum": page, "pageSize": PAGE_SIZE}), key)
        rows = data.get("rows")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ArchiveError("Malformed A2E records list")
        if len(rows) > PAGE_SIZE:
            raise ArchiveError("A2E records page exceeds requested page size")
        if type(data.get("count")) is int:
            if data["count"] < 0 or data["count"] > MAX_PAGES * PAGE_SIZE:
                raise ArchiveError("Too many A2E records to scan safely")
            count = data["count"]
        results.extend(rows)
        if len(rows) < PAGE_SIZE or (count is not None and len(results) >= count):
            return results
    raise ArchiveError("A2E history pagination incomplete; no silent partial archive")


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except ValueError:
        return None


def recent_completed_ids(rows: list[dict], now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    floor = now - timedelta(days=SCAN_DAYS)
    ids = []
    seen = set()
    for row in rows:
        task_id = row.get("_id")
        if not isinstance(task_id, str) or not VALID_TASK.fullmatch(task_id):
            raise ArchiveError("Malformed task ID in A2E list")
        created = parse_time(row.get("createdAt"))
        if created is not None and created < floor:
            continue
        if row.get("current_status") != "completed":
            continue
        if task_id not in seen:
            ids.append(task_id)
            seen.add(task_id)
    if len(ids) > MAX_RECENT_TASKS:
        raise ArchiveError("More recent completed tasks than safe run cap")
    return ids


def detail_for_task(key: str, task_id: str) -> dict:
    if not VALID_TASK.fullmatch(task_id):
        raise ArchiveError("Invalid task ID")
    info = _api_get(A2E_BASE + "/v1/userImage2Video/" + quote(task_id, safe=""), key)
    if info.get("_id") not in (None, task_id):
        raise ArchiveError("A2E task detail ID does not match requested ID")
    return info


def safe_video_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    value = urlsplit(url)
    if value.scheme != "https" or value.username or value.password or not value.hostname:
        return False
    host = value.hostname.lower()
    return (host.endswith(".downloadaivideo.com") or
            host in ("downloadaivideo.com", "video.a2e.ai", "api.a2e.ai"))


def selected_video_url(detail: dict) -> str:
    for key in ("result_url", "result_video_url", "video_url"):
        candidate = detail.get(key)
        if safe_video_url(candidate):
            return candidate
    raise ArchiveError("Completed task lacks a supported public A2E CDN MP4 URL")


def download_mp4(url: str, dest: Path) -> tuple[str, str, int]:
    if not safe_video_url(url):
        raise ArchiveError("Video URL is not on an allowed A2E CDN")
    req = Request(url, headers={
        "Accept": "video/mp4,application/octet-stream",
        "User-Agent": "Genjutsu",
    })
    sha = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    size = 0
    try:
        with urlopen(req, timeout=90) as stream, dest.open("xb") as output:
            if not safe_video_url(stream.geturl()):
                raise ArchiveError("A2E media redirected to an unexpected host")
            while True:
                part = stream.read(1024 * 1024)
                if not part:
                    break
                size += len(part)
                if size > MAX_BYTES:
                    raise ArchiveError("A2E video exceeds 200 MB archive limit")
                sha.update(part)
                md5.update(part)
                output.write(part)
    except (HTTPError, URLError, OSError, TimeoutError):
        raise ArchiveError("A2E CDN download failed") from None
    if size < 1024:
        raise ArchiveError("A2E video empty or truncated")
    with dest.open("rb") as stream:
        header = stream.read(16)
    if header[4:8] != b"ftyp":
        raise ArchiveError("A2E download is not an MP4 media file")
    return sha.hexdigest(), md5.hexdigest(), size


def verify_mp4(path: Path) -> float:
    """Check a real video stream and plausible duration, not just .mp4 suffix."""
    if shutil.which("ffprobe") is None:
        raise ArchiveError("ffprobe unavailable on GitHub runner")
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30, check=True)
        doc = json.loads(result.stdout)
        duration = float(doc.get("format", {}).get("duration"))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        raise ArchiveError("MP4 failed ffprobe validation") from None
    if not 0.5 <= duration <= 300 or not any(
        stream.get("codec_type") == "video" for stream in doc.get("streams", [])):
        raise ArchiveError("MP4 missing valid video stream or duration")
    return duration


def oauth_drive_client():
    """Create a Drive v3 user-OAuth client, never log auth responses."""
    required = ("GDRIVE_OAUTH_CLIENT_ID", "GDRIVE_OAUTH_CLIENT_SECRET",
                "GDRIVE_OAUTH_REFRESH_TOKEN")
    if any(not os.environ.get(field) for field in required):
        raise ArchiveError("Google Drive OAuth GitHub secrets not configured")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
        from googleapiclient.discovery import build
        creds = Credentials(
            token=None,
            refresh_token=os.environ["GDRIVE_OAUTH_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GDRIVE_OAUTH_CLIENT_ID"],
            client_secret=os.environ["GDRIVE_OAUTH_CLIENT_SECRET"],
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        creds.refresh(GoogleRequest())
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        raise ArchiveError("Google Drive OAuth authorization failed") from None


def drive_matches(drive, folder: str, name: str) -> list[dict]:
    escaped = name.replace("\\", "\\\\").replace("'", "\\'")
    query = f"'{folder}' in parents and name = '{escaped}' and trashed = false"
    try:
        response = drive.files().list(
            q=query, fields="nextPageToken,files(id,name,size,md5Checksum,parents,appProperties)",
            pageSize=100).execute(num_retries=2)
    except Exception:
        raise ArchiveError("Google Drive duplicate check failed") from None
    if response.get("nextPageToken"):
        raise ArchiveError("Drive duplicate check returned incomplete results")
    return response.get("files", [])


def verify_existing(row: dict, *, folder: str, size: int, md5: str, sha: str) -> str:
    if (row.get("size") != str(size) or row.get("md5Checksum") != md5 or
            folder not in row.get("parents", []) or
            (row.get("appProperties") or {}).get("sha256") != sha):
        raise ArchiveError("Drive filename collision or checksum mismatch; no overwrite")
    return str(row["id"])


def archive_mp4(drive, folder: str, task_id: str, source: Path,
                sha: str, md5: str, size: int, detail: dict, duration: float) -> tuple[str, str]:
    if not VALID_TASK.fullmatch(task_id) or not VALID_FOLDER.fullmatch(folder):
        raise ArchiveError("Invalid archive task or folder identifier")
    filename = f"A2E_{task_id}.mp4"
    matches = drive_matches(drive, folder, filename)
    if len(matches) > 1:
        raise ArchiveError("Multiple Drive files with same A2E task ID")
    if matches:
        return "already_archived", verify_existing(
            matches[0], folder=folder, size=size, md5=md5, sha=sha)

    metadata = {
        "name": filename, "mimeType": "video/mp4", "parents": [folder],
        "description": ("Auto-archived A2E image-to-video. Task: " + task_id +
                        "; source name: " + str(detail.get("name", ""))[:100] +
                        "; duration: " + f"{duration:.2f}s" +
                        "; SHA-256: " + sha),
        "appProperties": {
            "source": "A2E", "task_id": task_id, "sha256": sha,
            "a2e_created_at": str(detail.get("createdAt") or "")[:100],
        },
    }
    try:
        from googleapiclient.http import MediaFileUpload
        upload = drive.files().create(
            body=metadata,
            media_body=MediaFileUpload(str(source), mimetype="video/mp4",
                                      chunksize=4 * 1024 * 1024, resumable=True),
            fields="id,name,size,md5Checksum,parents,appProperties")
        result = None
        while result is None:
            _, result = upload.next_chunk(num_retries=2)
    except Exception:
        # An ambiguous response may still have written the file.
        matches = drive_matches(drive, folder, filename)
        if len(matches) == 1:
            return "already_archived", verify_existing(
                matches[0], folder=folder, size=size, md5=md5, sha=sha)
        raise ArchiveError("Google Drive upload failed; check Drive before retry") from None

    try:
        observed = drive.files().get(
            fileId=result["id"],
            fields="id,name,size,md5Checksum,parents,appProperties").execute(num_retries=2)
    except Exception:
        raise ArchiveError("Google Drive upload completed but read-back failed") from None
    if observed.get("name") != filename:
        raise ArchiveError("Google Drive read-back filename mismatch")
    verified_id = verify_existing(observed, folder=folder, size=size, md5=md5, sha=sha)
    return "uploaded", verified_id


def run(a2e_key: str, folder_id: str, *, scan_rows=None, client=None) -> dict:
    if not isinstance(a2e_key, str) or not a2e_key.startswith("sk_"):
        raise ArchiveError("A2E_API_KEY missing; only read-only A2E access is used")
    if not VALID_FOLDER.fullmatch(folder_id):
        raise ArchiveError("GDRIVE_A2E_FOLDER_ID invalid or missing")
    rows = scan_rows if scan_rows is not None else list_records(a2e_key)
    ids = recent_completed_ids(rows)
    report = {"status": "OK", "scanned_records": len(rows), "completed_recent": len(ids),
              "uploaded": [], "already_archived": [], "expired": [], "errors": []}
    if not ids:
        return report
    drive = client if client is not None else oauth_drive_client()
    for task_id in ids:
        try:
            detail = detail_for_task(a2e_key, task_id)
            if detail.get("current_status") != "completed":
                continue
            if detail.get("isExpired") is True:
                report["expired"].append(task_id)
                continue
            url = selected_video_url(detail)
            with tempfile.TemporaryDirectory(prefix="simba-a2e-drive-") as directory:
                target = Path(directory) / (task_id + ".mp4")
                sha, md5, size = download_mp4(url, target)
                duration = verify_mp4(target)
                disposition, file_id = archive_mp4(
                    drive, folder_id, task_id, target, sha, md5, size, detail, duration)
            report[disposition].append({"task_id": task_id, "file_id": file_id,
                                        "bytes": size, "sha256": sha})
        except ArchiveError as exc:
            # No raw remote bodies or sensitive URLs in output.
            report["errors"].append({"task_id": task_id, "problem": str(exc)})
    if report["errors"] or report["expired"]:
        report["status"] = "ATTENTION_REQUIRED"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-id", default=os.getenv("GDRIVE_A2E_FOLDER_ID", ""))
    parser.add_argument("--report", type=Path, default=Path("a2e-drive-archive-report.json"))
    args = parser.parse_args()
    try:
        report = run(os.getenv("A2E_API_KEY", ""), args.folder_id)
    except ArchiveError as ex:
        report = {"status": "CONFIG_OR_SCAN_ERROR", "error": str(ex)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("A2E Drive archive", report["status"],
          "new", len(report.get("uploaded", [])),
          "existing", len(report.get("already_archived", [])),
          "errors", len(report.get("errors", [])))
    return 0 if report["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
