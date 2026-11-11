#!/usr/bin/env python3
"""GitHub Actions -> private Wix CMS inbox -> temporary GitHub branch.

NO renderer, no paid calls, no automatic project approval. Wix credentials are
read only from GitHub Actions secrets. The browser does not receive them.
Authoritative owner verification is via Wix's system-managed _owner field.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

WIX_COLLECTION = "SimbaMotionLabInboxV1"
GH_REPO = "legur/Simba"
MAX_PAYLOAD = 140_000
SHA = re.compile(r"^[a-f0-9]{64}$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
FORBIDDEN_KEYS = {"token", "secret", "password", "apikey", "api_key",
                  "authorization", "cookie", "privateurl", "mediaurl",
                  "drive_url", "downloadurl", "bearer", "credential",
                  "dataurl", "base64", "binary", "rawmedia"}
APPROVAL_STATES = {"USER_SELECTED_IN_CONNECTED_SESSION",
                   "DRAFT_NOT_DELIVERED"}


class QueueError(RuntimeError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def assert_sanitized(value):
    if isinstance(value, dict):
        for key, part in value.items():
            if not isinstance(key, str) or key.replace("-", "").replace("_", "").lower() in FORBIDDEN_KEYS:
                raise QueueError("FORBIDDEN_SELECTION_FIELD")
            assert_sanitized(part)
    elif isinstance(value, list):
        for part in value:
            assert_sanitized(part)
    elif isinstance(value, str):
        if len(value) > 8192:
            raise QueueError("SELECTION_STRING_TOO_LARGE")


def validate_item(item, allowed_owner):
    if not isinstance(item, dict) or not isinstance(item.get("data"), dict):
        raise QueueError("INVALID_WIX_ITEM")
    data = item["data"]
    # _owner is managed by Wix, not a submitted data field.
    if not allowed_owner or data.get("_owner") != allowed_owner:
        raise QueueError("WIX_MEMBER_NOT_ALLOWLISTED")
    if data.get("state") != "PENDING":
        raise QueueError("NOT_PENDING")
    for name in ("projectId", "sessionId", "sourceFingerprint"):
        if not isinstance(data.get(name), str):
            raise QueueError("INVALID_REQUIRED_FIELD")
    if not SAFE_ID.fullmatch(data["projectId"]) or not SAFE_ID.fullmatch(data["sessionId"]):
        raise QueueError("INVALID_PROJECT_OR_SESSION")
    delivery_id = data.get("deliveryId")
    if not isinstance(delivery_id, str) or not UUID.fullmatch(delivery_id):
        raise QueueError("INVALID_DELIVERY_ID")
    if not SHA.fullmatch(data["sourceFingerprint"]) or not isinstance(data.get("selectionSha256"), str):
        raise QueueError("INVALID_FINGERPRINT")
    selection = data.get("selection")
    if not isinstance(selection, dict):
        raise QueueError("INVALID_SELECTION")
    if len(encoded(selection)) > MAX_PAYLOAD or digest(selection) != data["selectionSha256"]:
        raise QueueError("SELECTION_HASH_OR_SIZE_MISMATCH")
    if selection.get("schema") not in (
            "bontours.motionlab.storyboard.selection/v1",
            "bontours.motionlab.selection/v2"):
        raise QueueError("UNSUPPORTED_SELECTION_SCHEMA")
    if (selection.get("project_id") != data["projectId"]
            or selection.get("expected_input_fingerprint") != data["sourceFingerprint"]):
        raise QueueError("SELECTION_SOURCE_MISMATCH")
    decision = selection.get("decision")
    if not isinstance(decision, dict) or decision.get("selected_option") not in (1, 2, 3):
        raise QueueError("SELECTED_OPTION_MISSING")
    if decision.get("state") not in APPROVAL_STATES:
        raise QueueError("UNKNOWN_APPROVAL_STATE")
    guards = selection.get("guards")
    if (not isinstance(guards, dict)
            or any(guards.get(key) is not False for key in
                   ("run_render", "run_tts", "run_a2e", "run_paid_operations", "auto_publish"))
            or any(guards.get(key) is not True for key in
                   ("preserve_approved_voice", "preserve_approved_music", "preserve_approved_narration"))):
        raise QueueError("PAID_OR_SOURCE_GUARD_VIOLATION")
    # Receiver preserves edits, it does not grant production approval.
    assert_sanitized(selection)
    if not isinstance(item.get("id"), str) or len(item["id"]) > 128:
        raise QueueError("WIX_ITEM_ID_INVALID")
    return {
        "schema": "bontours.motionlab.wix-inbox-receipt/v1",
        "source": "WIX_SITE_MEMBER_SUBMISSION_UNTRUSTED_FOR_RENDER",
        "wix_item_id": item["id"],
        "wix_owner_id": data["_owner"],
        "delivery_id": delivery_id,
        "session_id": data["sessionId"],
        "project_id": data["projectId"],
        "source_fingerprint": data["sourceFingerprint"],
        "selection_sha256": data["selectionSha256"],
        "selection": selection,
        "status": "STORED_IN_GITHUB_PENDING_MONTAGE_SOURCE_VERIFICATION",
        "render_authorized": False,
        "publication_authorized": False,
    }


class API:
    def __init__(self, wix_key, wix_site, github_token, *, opener=urlopen):
        if not wix_key or not wix_site or not github_token:
            raise QueueError("REQUIRED_GITHUB_ACTIONS_SECRETS_MISSING")
        self.wix_key = wix_key
        self.wix_site = wix_site
        self.github_token = github_token
        self.opener = opener

    def request(self, method, url, payload=None, *, wix=False, allow_404=False):
        body = encoded(payload) if payload is not None else None
        headers = ({"Authorization": self.wix_key, "wix-site-id": self.wix_site}
                   if wix else
                   {"Authorization": "Bearer " + self.github_token,
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"})
        headers["Content-Type"] = "application/json"
        try:
            with self.opener(Request(url, data=body, headers=headers, method=method), timeout=35) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            if allow_404 and exc.code == 404:
                return None
            # Never log the response body: it may contain private data.
            raise QueueError(f"{'WIX' if wix else 'GITHUB'}_API_HTTP_{exc.code}") from None

    def wix_pending(self):
        url = "https://www.wixapis.com/wix-data/v2/items/query"
        body = {"dataCollectionId": WIX_COLLECTION,
                "query": {"filter": {"state": "PENDING"}, "paging": {"limit": 100}}}
        result = self.request("POST", url, body, wix=True)
        return result.get("dataItems", [])

    def github_store(self, record):
        delivery_id = record["delivery_id"]
        branch = "motionlab-inbox/" + delivery_id
        path = "inbox/selection.json"
        contents_url = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
        url = contents_url + "?ref=" + quote(branch, safe="")
        existing = self.request("GET", url, allow_404=True)
        raw = encoded(record)
        if existing is not None:
            try:
                actual = base64.b64decode(existing["content"]).strip()
            except (KeyError, ValueError):
                raise QueueError("EXISTING_RECEIPT_CORRUPT")
            if actual != raw:
                raise QueueError("DUPLICATE_DELIVERY_ID_DIFFERENT_PAYLOAD")
            return existing["sha"]
        ref_url = f"https://api.github.com/repos/{GH_REPO}/git/ref/heads/main"
        base = self.request("GET", ref_url)
        new_ref = f"https://api.github.com/repos/{GH_REPO}/git/refs"
        try:
            self.request("POST", new_ref,
                         {"ref": "refs/heads/" + branch, "sha": base["object"]["sha"]})
        except QueueError as exc:
            # A racing poll or crash may already have created this branch;
            # check it explicitly before continuing, never force-update it.
            if str(exc) != "GITHUB_API_HTTP_422":
                raise
            check = self.request("GET", f"https://api.github.com/repos/{GH_REPO}/git/ref/heads/" +
                                 quote(branch, safe=""), allow_404=True)
            if check is None:
                raise
        saved = self.request("PUT", contents_url, {
            "message": "Store member-confirmed MotionLab selection pending Montage verification",
            "content": base64.b64encode(raw).decode("ascii"),
            "branch": branch,
        })
        return saved["content"]["sha"]

    def wix_ack(self, item_id, receipt_sha):
        patch = {
            "dataCollectionId": WIX_COLLECTION,
            "patch": {
                "dataItemId": item_id,
                "fieldModifications": [
                    {"fieldPath": "state", "action": "SET_FIELD",
                     "setFieldOptions": {"value": "SAVED_IN_GITHUB_PENDING_MONTAGE"}},
                    {"fieldPath": "githubReceipt", "action": "SET_FIELD",
                     "setFieldOptions": {"value": receipt_sha}},
                ]},
            "condition": {"filter": {"state": "PENDING"}}
        }
        return self.request("PATCH", "https://www.wixapis.com/wix-data/v2/items/" +
                            quote(item_id, safe=""), patch, wix=True)


def run(api, owner_id, *, dry_run=False):
    results = {"found": 0, "stored": 0, "blocked": 0,
               "dry_run": dry_run, "render_started": False, "paid_calls": 0}
    for item in api.wix_pending():
        results["found"] += 1
        try:
            record = validate_item(item, owner_id)
            if dry_run:
                continue
            gh_sha = api.github_store(record)
            api.wix_ack(item["id"], gh_sha)
            results["stored"] += 1
        except (QueueError, ValueError, KeyError, TypeError) as exc:
            # Fail closed: never mark a rejected item as delivered. Avoid
            # logging its body or site member identity.
            print("Blocked inbox item:", str(exc), file=sys.stderr)
            results["blocked"] += 1
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    api = API(os.getenv("WIX_API_KEY"), os.getenv("WIX_SITE_ID"),
              os.getenv("GITHUB_TOKEN"))
    owner = os.getenv("MOTIONLAB_WIX_OWNER_ID")
    if not owner:
        raise QueueError("MOTIONLAB_WIX_OWNER_ID_NOT_SET")
    result = run(api, owner, dry_run=args.dry_run)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["blocked"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
