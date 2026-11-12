#!/usr/bin/env python3
"""One-shot *TEST ONLY* live Drive handoff check with cleanup.

Uses the EXISTING GitHub Actions Drive OAuth. Creates a short-lived test-only
ticket, posts a fake harmless one-scene selection to the user's published Apps
Script receiver, verifies actual private Drive persistence/idempotency, and
always deletes both created Drive files. No user-approved selection, Montage,
media, TTS, A2E, render, or paid API is touched.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from issue_ticket import drive, upload, TICKET_DIR

INBOX_FOLDER = "1gYNUU3HUeWnu2jEcs1gEf4cu9LJEEPoD"
RECEIVER = ("https://script.google.com/macros/s/"
            "AKfycbwf4RNyK_76ASvV9k-0rv2Tc-F_m-_v8TqQyWg5t0G-t5wibx7IgpXSJo2GG6Dcc1Wc/exec")

def checksum(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def canonical(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)

def list_receipts(svc, filename):
    safe = filename.replace("\\", "\\\\").replace("'", "\\'")
    data = svc.files().list(
        q=f"'{INBOX_FOLDER}' in parents and name = '{safe}' and trashed = false",
        fields="files(id,name,parents),nextPageToken",
        pageSize=100,
    ).execute()
    if data.get("nextPageToken"):
        raise RuntimeError("SMOKE_INBOX_LIST_INCOMPLETE")
    return data.get("files", [])

def post(payload: dict) -> str:
    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(RECEIVER, data=encoded, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Simba-MotionLab-Owner-Approved-Smoke/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=28) as response:
            if response.status != 200:
                raise RuntimeError("SMOKE_RECEIVER_HTTP_NON_200")
            return response.read(22000).decode("utf-8", "replace")
    except urllib.error.HTTPError:
        raise RuntimeError("SMOKE_RECEIVER_HTTP_ERROR") from None

def execute():
    svc = drive()
    ticket_id = None
    inbox_ids = set()
    label = "SMOKE_TEST_ONLY_" + secrets.token_hex(5)
    project_id = "smoke-only-" + secrets.token_hex(5)
    session_id = "smoke-session-" + secrets.token_hex(5)
    fp = checksum("no-user-media:" + label)
    token = secrets.token_hex(32)
    selection = {
        "schema": "bontours.motionlab.storyboard.selection/v1",
        "test_only": True,
        "request_id": session_id,
        "project_id": project_id,
        "expected_input_fingerprint": fp,
        "stage": "edit_choice",
        "decision": {
            "selected_option": 1,
            "options_presented": 3,
            "state": "DRAFT_NOT_DELIVERED",
            "confirmation_scope": "EDIT_CHOICES_ONLY",
        },
        "scenes": [{"scene_id": "smoke-only", "duration_seconds": 1, "name": "TEST ONLY"}],
        "guards": {
            "run_render": False,
            "run_tts": False,
            "run_a2e": False,
            "run_paid_operations": False,
            "auto_publish": False,
            "preserve_approved_voice": True,
            "preserve_approved_music": True,
            "preserve_approved_narration": True,
        },
    }
    now = dt.datetime.now(dt.timezone.utc)
    ticket = {
        "schema": "bontours.motionlab.drive-ticket/v1",
        "state": "ISSUED",
        "test_only": True,
        "project_id": project_id,
        "session_id": session_id,
        "source_fingerprint": fp,
        "token_sha256": checksum(token),
        "expires_utc": (now + dt.timedelta(minutes=10)).isoformat().replace("+00:00","Z"),
        "issued_utc": now.isoformat().replace("+00:00", "Z"),
    }
    filename = None
    try:
        ticket_id = upload(svc, TICKET_DIR, label + "-ticket.json", ticket)
        filename = "motionlab-" + ticket_id + ".json"
        payload = {
            "nonce": str(uuid.uuid4()),
            "ticket_id": ticket_id,
            "ticket_token": token,
            "selection_json": canonical(selection),
            "selection_sha256": checksum(canonical(selection)),
        }
        first = post(payload)
        if "SAVED_IN_DRIVE_PENDING_MONTAGE" not in first:
            allowed_errors = [
                "TICKET_NOT_FOUND", "TICKET_REJECTED", "TICKET_EXPIRED",
                "INVALID_SELECTION", "RECEIVER_BUSY_RETRY", "INGRESS_FAILED",
                "SELECTION_HASH_MISMATCH", "FILE_OUTSIDE_PRIVATE_FOLDER",
            ]
            observed = next((e for e in allowed_errors if e in first), "UNKNOWN_RESPONSE")
            raise RuntimeError("SMOKE_RECEIVER_REFUSED_VALID_TICKET_" + observed)
        print("LIVE POST: receiver returned saved-in-Drive receipt marker")
        # Drive metadata and file contents are the authoritative proof; the
        # browser's HTML acknowledgement alone is insufficient.
        files = list_receipts(svc, filename)
        if len(files) != 1:
            raise RuntimeError("SMOKE_DRIVE_PERSISTENCE_COUNT_MISMATCH")
        inbox_ids.add(files[0]["id"])
        actual = svc.files().get_media(fileId=files[0]["id"]).execute()
        result = json.loads(actual.decode("utf-8"))
        if (result.get("status") != "SAVED_IN_DRIVE_PENDING_MONTAGE"
                or result.get("render_authorized") is not False
                or result.get("paid_operations_authorized") is not False
                or result.get("test_only") is True
                or result.get("selection", {}).get("test_only") is not True
                or result.get("selection_sha256") != payload["selection_sha256"]
                or result.get("ticket_id") != ticket_id):
            raise RuntimeError("SMOKE_DRIVE_CONTENT_MISMATCH")
        print("LIVE DRIVE READBACK: one correct private receipt with no-render guards")
        second = post(payload)
        if result["receipt_id"] not in second:
            raise RuntimeError("SMOKE_IDEMPOTENT_RECEIPT_NOT_MATCHED")
        if len(list_receipts(svc, filename)) != 1:
            raise RuntimeError("SMOKE_DUPLICATE_RECEIPT_FILE")
        print("LIVE RETRY: same receipt returned and no duplicate file")
        print("LIVE TEST PASS: no user media, render, A2E, TTS or production Montage job")
    finally:
        # Cleanup even when server ACK is missing or a validation stage fails.
        if filename:
            try:
                for item in list_receipts(svc, filename):
                    inbox_ids.add(item["id"])
            except Exception:
                print("CLEANUP_WARNING: could not query test-only inbox filename", file=sys.stderr)
        for fid in list(inbox_ids) + ([ticket_id] if ticket_id else []):
            try:
                svc.files().delete(fileId=fid).execute()
            except Exception:
                print("CLEANUP_WARNING: test-only Drive file could not be deleted", file=sys.stderr)
        print("LIVE TEST CLEANUP: delete requested for any created ticket / inbox receipt")

if __name__ == "__main__":
    try:
        execute()
    except Exception as exc:
        code = str(exc)
        safe = code if code.startswith("SMOKE_") else "UNEXPECTED_CHECK_ERROR"
        print("LIVE TEST FAILED:", safe, file=sys.stderr)
        raise SystemExit(2)
