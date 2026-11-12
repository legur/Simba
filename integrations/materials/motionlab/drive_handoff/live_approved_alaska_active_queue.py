#!/usr/bin/env python3
"""One-shot owner-authorized Alaska Studio ingress replay.

Posts a FRESH private Drive ticket + exact previously owner-approved
selection (changing only click timestamp) to the live Apps Script receiver.
This tests real Drive write -> Apps Script ACTIVE flag -> immediate GitHub
workflow_dispatch. It does NOT simulate a browser click, and MUST be reported
as backend API replay, not an interactive Studio E2E. No A2E/TTS/paid API.
"""
from __future__ import annotations
import copy
import datetime as dt
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from issue_ticket import drive, issue, read_approved_launch, LAUNCH_DIR, TICKET_DIR
from notify_montage import validate as validate_receipt, canonical, read_private, INBOX_ID

SOURCE_LAUNCH_ID="1G4xscgptReyp8F_aUjCbViyoUmyr_Djq"
SOURCE_SHA="e909aaecf7cc89ec2e9b7e3a287b818f63d0061ed544e621113b266cd896d6f7"
BASELINE_RECEIPT_ID="1pkLPldVVz45rUr2xmcIonwbHg4NQApC-"
BASELINE_SELECTION_SHA="9580ce34d60afd47c213270a5b9142a9d81ed93caaff179956d98720e4e2a2e3"
ENDPOINT=("https://script.google.com/macros/s/"
          "AKfycbwf4RNyK_76ASvV9k-0rv2Tc-F_m-_v8TqQyWg5t0G-t5wibx7IgpXSJo2GG6Dcc1Wc/exec")

def stop(reason):
    print("ALASKA_ACTIVE_TEST_BLOCKED:",reason,file=sys.stderr)
    raise SystemExit(2)

def safe_private_file(svc,id,folder):
    data=read_private(svc,id,folder,limit=320000)
    return data

def post_selection(ticket_id, token, selection):
    import uuid
    raw=canonical(selection)
    sha=hashlib.sha256(raw.encode("utf-8")).hexdigest()
    params={
        "nonce":str(uuid.uuid4()),
        "ticket_id":ticket_id,
        "ticket_token":token,
        "selection_json":raw,
        "selection_sha256":sha
    }
    req=urllib.request.Request(ENDPOINT,
        data=urllib.parse.urlencode(params).encode("utf-8"),method="POST",
        headers={"User-Agent":"Simba-Approved-Alaska-ActiveQueue-BackendSmoke/1.0",
                 "Content-Type":"application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req,timeout=50) as response:
            if response.status!=200:stop("APPS_SCRIPT_HTTP_NON_200")
            html=response.read(42000).decode("utf-8","replace")
    except (urllib.error.URLError,TimeoutError):
        stop("APPS_SCRIPT_NETWORK_ERROR")
    match=re.search(r"var msg=(\{.*?\});var origin=",html,re.DOTALL)
    if not match:stop("APPS_SCRIPT_ACK_MISSING")
    try:msg=json.loads(match.group(1))
    except ValueError:stop("APPS_SCRIPT_ACK_PARSE_ERROR")
    if msg.get("type")!="SIMBA_DRIVE_INGRESS_RECEIPT" or msg.get("nonce")!=params["nonce"]:
        stop("APPS_SCRIPT_ACK_NONCE_MISMATCH")
    if (msg.get("status")!="SAVED_IN_DRIVE_PENDING_MONTAGE" or
        msg.get("selection_sha256")!=sha):
        print("ALASKA_ACTIVE_TEST_STATUS:",str(msg.get("status")))
        print("ALASKA_ACTIVE_TEST_REASON:",str(msg.get("error_code") or "INVALID_RECEIPT"))
        stop("APPS_SCRIPT_INGEST_FAILED")
    if not re.fullmatch(r"[0-9a-f-]{36}",msg.get("receipt_id") or ""):
        stop("INVALID_NEW_RECEIPT")
    # Explicitly distinguish actual workflow dispatch from durable Drive
    # acceptance. No claim of automation if token/owner/permission is missing.
    return msg,sha

def main():
    svc=drive()
    baseline=validate_receipt(svc,BASELINE_RECEIPT_ID)
    assert baseline["selection_sha256"]==BASELINE_SELECTION_SHA
    assert baseline["project_id"]=="alaska-voyager-2027"
    source,raw=read_approved_launch(svc,SOURCE_LAUNCH_ID,include_raw=True)
    assert hashlib.sha256(raw).hexdigest()==SOURCE_SHA
    assert source["request_id"]==baseline["session_id"]
    assert source["expected_input_fingerprint"]==baseline["source_fingerprint"]
    assert len(source["scenes"])==10 and len(source["preview_assets"])==7
    approved=baseline["selection"]
    assert approved["decision"]["selected_option"]==1
    assert approved["guards"]["run_paid_operations"] is False
    assert approved["guards"]["run_render"] is False
    assert approved["guards"]["run_a2e"] is False
    assert approved["guards"]["run_tts"] is False
    assert approved["guards"]["auto_publish"] is False

    # Use the exact source+approved scene/effect selection: no invented
    # artwork, text, new voices or scene edits; user authorized this replay.
    repeated=copy.deepcopy(approved)
    repeated["decision"]["user_selected_at"]=(
       dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
       .replace("+00:00","Z"))

    issued=issue(svc,SOURCE_LAUNCH_ID)
    tid=issued["ticket_file_id"]
    authorized=issued["authorized_launch_file_id"]
    print("ALASKA_ACTIVE_TEST_NEW_TICKET_ID",tid)
    try:
        data=safe_private_file(svc,authorized,LAUNCH_DIR)
        handoff=data["handoff"]
        assert handoff["ticket_id"]==tid
        token=handoff["ticket_token"]  # never log or store token outside Drive
        msg,sha=post_selection(tid,token,repeated)
        print("ALASKA_ACTIVE_TEST_RECEIPT_ID",msg["receipt_id"])
        print("ALASKA_ACTIVE_TEST_SERVER_AUTOMATION",msg.get("automation_status","MISSING"))
        items=svc.files().list(
          q=f"'{INBOX_ID}' in parents and name = 'motionlab-{tid}.json' and trashed = false",
          fields="files(id,parents,mimeType,name),nextPageToken",pageSize=100).execute()
        if items.get("nextPageToken") or len(items.get("files",[]))!=1:
            stop("DRIVE_RECEIPT_NOT_UNIQUE")
        receipt_file_id=items["files"][0]["id"]
        record=validate_receipt(svc,receipt_file_id)
        if record["receipt_id"]!=msg["receipt_id"] or record["selection_sha256"]!=sha:
            stop("DRIVE_REAL_RECEIPT_CONTENT_MISMATCH")
        print("ALASKA_ACTIVE_TEST_PRIVATE_RECEIPT_FILE_ID",receipt_file_id)
        print("ALASKA_ACTIVE_TEST_RESULT_INGEST_SHA_VERIFIED",True)
        if msg.get("automation_status")!="GITHUB_DISPATCHED":
            stop("APPS_SCRIPT_DID_NOT_DISPATCH_GITHUB")
        print("ALASKA_ACTIVE_TEST_GITHUB_DISPATCH_ACCEPTED",True)
        # GitHub's workflow run and Applied result must be inspected separately.
    finally:
        # No need to retain a second owner-only launch that includes a fresh
        # bearer token. The ticket's SHA and original launch remain immutable.
        try:
            svc.files().delete(fileId=authorized).execute()
            print("ALASKA_ACTIVE_TEST_AUTHORIZED_COPY_REVOKED",True)
        except Exception:
            print("ALASKA_ACTIVE_TEST_AUTHORIZED_COPY_CLEANUP_REQUIRED",True)

if __name__=="__main__":
    try:main()
    except AssertionError:
        stop("OWNER_APPROVED_ALASKA_SOURCE_GUARD_FAILED")
