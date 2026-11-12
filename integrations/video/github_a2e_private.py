#!/usr/bin/env python3
"""Resolve a *minimal* owner-authored GitHub Issue to the existing A2E runner.

A GitHub Issue contains no Wix URLs, creative prompts, client data or private
files: only project_id + two Drive file IDs. The existing Github Actions OAuth
reads private Drive bytes and Rafael's approved stages, verifies actual Wix
media identity, then creates an in-memory simba_a2e_generate issue body.
Paid generation is performed ONLY by the existing github_a2e_universal.run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

MATERIALS = Path(__file__).resolve().parents[1] / "materials"
if str(MATERIALS) not in sys.path:
    sys.path.insert(0, str(MATERIALS))

import auto_script
import catalog
import handoff
import rafael_archive
import rafael_a2e_handoff as bridge

KIND = "simba_a2e_from_private_drive"
FOLDER = rafael_archive.ARCHIVE_FOLDER
ID = re.compile(r"^[A-Za-z0-9_-]{10,120}$")
PROJECT = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_PLAN = 16000


class PrivateBridgeError(RuntimeError):
    pass


def _trusted_issue(event: dict) -> dict:
    issue = event.get("issue") or {}
    if (event.get("action") != "labeled"
            or (event.get("repository") or {}).get("full_name") != "legur/Simba"
            or (event.get("sender") or {}).get("login") != "legur"
            or (event.get("label") or {}).get("name") != "a2e-generate-approved"
            or (issue.get("user") or {}).get("login") != "legur"
            or issue.get("pull_request") is not None
            or type(issue.get("number")) is not int or issue["number"] <= 0):
        raise PrivateBridgeError("private A2E handoff requires trusted owner label event")
    raw = issue.get("body")
    if not isinstance(raw, str) or len(raw) > 4000:
        raise PrivateBridgeError("private A2E issue body invalid")
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        raise PrivateBridgeError("private A2E request is not JSON") from None
    if (not isinstance(doc, dict)
            or set(doc) != {"kind", "project_id", "plan_file_id", "storyboard_file_id"}
            or doc["kind"] != KIND
            or not isinstance(doc["project_id"], str)
            or not PROJECT.fullmatch(doc["project_id"])
            or not all(isinstance(doc.get(k), str) and ID.fullmatch(doc[k])
                       for k in ("plan_file_id", "storyboard_file_id"))
            or doc["plan_file_id"] == doc["storyboard_file_id"]):
        raise PrivateBridgeError("private A2E issue schema invalid")
    return doc


def _pinned_assets(root: Path, request: dict) -> dict:
    path = catalog.inside(root, f"campaigns/{request['project_id']}/project.json")
    try:
        project = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        raise PrivateBridgeError("approved project cannot be read") from None
    stage = handoff.make_handoff(root, path, project)
    if (stage.get("state") != "READY_FOR_HANDOFF"
            or stage.get("recipient") != "A2E_RUNNER"
            or (stage.get("packet") or {}).get("next_stage") != "a2e_clips"):
        raise PrivateBridgeError("project does not have approved A2E handoff")
    try:
        plan = bridge._require_verified_asset(project, "a2e_prompts", "animation_prompt")
        board = bridge._require_verified_asset(project, "storyboard", "storyboard")
    except (KeyError, bridge.BridgeError):
        raise PrivateBridgeError("selected private assets not registered") from None
    if (plan.get("drive_file_id") != request["plan_file_id"]
            or board.get("drive_file_id") != request["storyboard_file_id"]):
        raise PrivateBridgeError("private Issue does not match the approved Drive asset IDs")
    return project


def _read_verified(drive, file_id: str, expected_sha: str, limit: int) -> bytes:
    """Drive get/list/read only. No copying to public actions artifacts."""
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        raise PrivateBridgeError("private Drive SHA-256 not pinned")
    try:
        meta = rafael_archive.drive_call(drive.files().get(
            fileId=file_id, fields="id,parents,size,md5Checksum,permissions(type,role)"))
        if (meta.get("id") != file_id or FOLDER not in (meta.get("parents") or [])
                or not 1 <= int(meta.get("size", 0)) <= limit):
            raise PrivateBridgeError("selected source not in the approved private Drive folder")
        perms = meta.get("permissions")
        if perms is not None and any(row.get("type") != "user" for row in perms):
            raise PrivateBridgeError("selected private source has broad permissions")
        value = rafael_archive.drive_call(drive.files().get_media(fileId=file_id))
        if (not isinstance(value, bytes) or len(value) != int(meta["size"])
                or hashlib.sha256(value).hexdigest() != expected_sha
                or hashlib.md5(value).hexdigest() != meta.get("md5Checksum")):
            raise PrivateBridgeError("private Drive full-byte readback verification failed")
        return value
    except rafael_archive.ArchiveError:
        raise PrivateBridgeError("private Drive read-only source unavailable") from None


def resolve_private_issue(event: dict, *, root: Path | None = None,
                          drive=None, fetch_wix=bridge.fetch_wix) -> dict:
    """Return a new in-memory event for the EXISTING paid universal runner."""
    request = _trusted_issue(event)
    root = (root or Path(__file__).resolve().parents[2]).resolve()
    project = _pinned_assets(root, request)
    assets = {row["id"]: row for row in project["assets"]}
    board_id = project["stage_handoffs"]["storyboard"]["assets"]
    prompts_id = project["stage_handoffs"]["a2e_prompts"]["assets"]
    board = next(assets[x] for x in board_id if assets[x]["kind"] == "storyboard")
    plan = next(assets[x] for x in prompts_id if assets[x]["kind"] == "animation_prompt")
    try:
        drive = drive or auto_script.drive_client()
        rafael_archive.check_private_folder(drive, FOLDER)
        archive = _read_verified(drive, request["storyboard_file_id"],
                                 board["recorded_sha256"], rafael_archive.LIMIT)
        private_plan = _read_verified(drive, request["plan_file_id"],
                                      plan["recorded_sha256"], MAX_PLAN)
        with tempfile.TemporaryDirectory(prefix="simba-private-a2e-") as temp:
            t = Path(temp)
            zipped = t / "rafael-private.zip"
            planned = t / "motion-private.json"
            zipped.write_bytes(archive)
            planned.write_bytes(private_plan)
            # The source was independently verified above; the adapter
            # verifies all stage receipts, 9 frames and Wix pixel content.
            paid_issue, receipt = bridge.create_owner_issue(
                root, request["project_id"], planned, zipped, fetch=fetch_wix,
                verify_remote=True,
                drive_check=lambda fid, raw: fid == request["storyboard_file_id"]
                               and hashlib.sha256(raw).hexdigest() == board["recorded_sha256"])
        if receipt.get("paid_calls") != 0 or receipt.get("a2e_started") is not False:
            raise PrivateBridgeError("Rafael-to-A2E resolver unexpectedly executed paid work")
        result = dict(event)
        result["issue"] = dict(event["issue"], body=json.dumps(paid_issue, ensure_ascii=False))
        return result
    except (KeyError, ValueError, TypeError, OSError, bridge.BridgeError,
            auto_script.AgentError, rafael_archive.ArchiveError):
        raise PrivateBridgeError("private A2E inputs did not pass end-to-end read-only verification") from None


def perhaps_resolve(event: dict, **kwargs) -> tuple[dict, bool]:
    """The old public-Wix issue format stays fully backwards compatible."""
    raw = (event.get("issue") or {}).get("body")
    if not isinstance(raw, str) or len(raw) > 20000:
        return event, False
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return event, False
    if not isinstance(value, dict) or value.get("kind") != KIND:
        return event, False
    return resolve_private_issue(event, **kwargs), True


def dry_run_readonly(project_id: str, plan_file_id: str,
                     storyboard_file_id: str, *, root: Path | None = None,
                     **dependencies) -> dict:
    """Read all approved sources and Wix frames, never quote/start/post/label."""
    candidate = {
        "kind": KIND, "project_id": project_id,
        "plan_file_id": plan_file_id, "storyboard_file_id": storyboard_file_id,
    }
    # A synthetic event is used ONLY to reuse strict read-only validation.
    # It is not an authentic GitHub event and cannot trigger the paid workflow.
    synthetic = {
        "action": "labeled", "repository": {"full_name": "legur/Simba"},
        "sender": {"login": "legur"},
        "label": {"name": "a2e-generate-approved"},
        "issue": {"number": 1, "user": {"login": "legur"},
                  "body": json.dumps(candidate)},
    }
    resolved = resolve_private_issue(synthetic, root=root, **dependencies)
    import github_a2e_universal as universal
    _, cap, bodies = universal.validate(resolved)
    lineage = json.loads(resolved["issue"]["body"])
    return {
        "status": "DRIVE_AND_WIX_SOURCES_VERIFIED_NO_A2E_EXECUTION",
        "project_id": lineage["project_id"],
        "handoff_sha256": lineage["handoff_sha256"],
        "selected_storyboard": lineage["selected_storyboard"],
        "selected_prompts": lineage["selected_prompts"],
        "verified_scene_count": len(bodies),
        "recorded_approved_max_credits": cap,
        "model_version": "a2e",
        "video_time_seconds_per_scene": 5,
        "actual_A2E_quote_checked": False,
        "private_bytes_readback_verified": True,
        "wix_frames_verified": True,
        "github_issue_created": False,
        "a2e_paid_calls": 0,
        "a2e_task_ids": [],
        "published": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Simba approved Rafael -> Drive -> Wix -> existing universal A2E preflight")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--project", required=True)
    parser.add_argument("--plan-file-id", required=True)
    parser.add_argument("--storyboard-file-id", required=True)
    args = parser.parse_args(argv)
    try:
        report = dry_run_readonly(
            args.project, args.plan_file_id, args.storyboard_file_id, root=args.root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (PrivateBridgeError, bridge.BridgeError, ValueError, TypeError, KeyError,
            OSError, auto_script.AgentError, rafael_archive.ArchiveError):
        print(json.dumps({"status": "BLOCKED_READ_ONLY_PREFLIGHT",
                          "no_a2e_calls": True, "no_github_issue": True,
                          "reason": "Approved project/Drive/Wix source verification failed or unavailable"},
                         ensure_ascii=False))
        return 2
    except Exception:
        # Any unknown library/auth error is also fail-closed. Never show
        # private media links, tokens or contents of exception responses.
        print(json.dumps({"status": "BLOCKED_READ_ONLY_PREFLIGHT",
                          "no_a2e_calls": True, "no_github_issue": True,
                          "reason": "Unexpected private source verification failure"},
                         ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
