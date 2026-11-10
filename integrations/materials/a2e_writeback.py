#!/usr/bin/env python3
"""Read-only reconciliation and opt-in project write-back for existing Simba A2E.

Input: REAL universal A2E status.json from an owner-authorized GitHub run.
Checks: original source/stage receipt, selected storyboard/prompt options,
each completed A2E GET task, archived private Drive MP4 metadata and full
remote byte SHA-256, video decode/duration. Only then prepares an additive
project.json stage_handoffs.a2e_clips record and routes to VOICE_AND_MUSIC.

No A2E quote/presign/start, no paid retries, no media uploads, no publication.
Default is --dry-run (read-only). --apply is restricted to an owner-initiated
main workflow_dispatch with a trusted GitHub Actions run/issue receipt.
"""
from __future__ import annotations

import argparse
import copy
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

MATERIALS = Path(__file__).resolve().parents[1] / "materials"
VIDEO = Path(__file__).resolve().parent
if str(MATERIALS) not in sys.path:
    sys.path.insert(0, str(MATERIALS))
if str(VIDEO) not in sys.path:
    sys.path.insert(0, str(VIDEO))
import catalog
import handoff
import a2e_drive_archiver as archive

PROJECT = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
DEFAULT_ARCHIVE = "1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj"


class WritebackError(RuntimeError):
    """Safe fixed-text errors only: never include media URLs, tokens or API bodies."""


def _read_project(root: Path, project_id: str) -> tuple[Path, dict]:
    if not isinstance(project_id, str) or not PROJECT.fullmatch(project_id):
        raise WritebackError("invalid project ID")
    path = catalog.inside(root, f"campaigns/{project_id}/project.json")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise WritebackError("canonical project.json unavailable") from None
    if document.get("id") != project_id:
        raise WritebackError("canonical project ID mismatch")
    return path, document


def _check_state(project: dict, hand: dict, state: dict, issue: int) -> list[dict]:
    if (not isinstance(state, dict) or state.get("status") != "COMPLETED"
            or state.get("private_source_readback_verified") is not True
            or type(state.get("owner_issue_number")) is not int
            or state["owner_issue_number"] != issue):
        raise WritebackError("A2E run not completed or not bound to trusted private issue")
    packet = hand.get("packet") or {}
    lineage = state.get("lineage")
    if (hand.get("state") != "READY_FOR_HANDOFF"
            or hand.get("recipient") != "A2E_RUNNER"
            or packet.get("next_stage") != "a2e_clips"
            or not isinstance(lineage, dict)
            or lineage.get("project_id") != project["id"]
            or not isinstance(packet.get("receipt_sha256"), str)
            or not SHA.fullmatch(packet["receipt_sha256"])
            or lineage.get("handoff_sha256") != packet["receipt_sha256"]):
        raise WritebackError("A2E result not pinned to current approved handoff")
    stages = project.get("stage_handoffs") or {}
    if "a2e_clips" in stages:
        raise WritebackError("A2E clip stage already recorded; no duplicates or silent overwrite")
    if (lineage.get("selected_storyboard") != stages["storyboard"]["selected_option"]
            or lineage.get("selected_prompts") != stages["a2e_prompts"]["selected_option"]
            or lineage.get("verified_at_source") is not False):
        raise WritebackError("A2E lineage and selected options differ")
    cap = stages["a2e_prompts"]["max_credits"]
    if (type(cap) not in (int, float) or cap <= 0
            or type(state.get("max_credits")) not in (int, float)
            or float(cap) != float(state["max_credits"])):
        raise WritebackError("recorded execution cap differs from selected user cap")
    scenes = state.get("scenes")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 6:
        raise WritebackError("A2E completed scenes list missing or invalid")
    ids = set()
    for number, row in enumerate(scenes, 1):
        if (not isinstance(row, dict) or type(row.get("number")) is not int
                or row["number"] != number or row.get("status") != "completed"
                or not isinstance(row.get("task_id"), str)
                or not archive.VALID_TASK.fullmatch(row["task_id"])
                or row["task_id"] in ids):
            raise WritebackError("A2E scene task, order or completion invalid")
        ids.add(row["task_id"])
    return scenes


def _check_archive_folder(drive, folder: str) -> None:
    if folder != DEFAULT_ARCHIVE:
        raise WritebackError("unexpected A2E archive folder")
    try:
        details = drive.files().get(
            fileId=folder, fields="id,mimeType,permissions(type,role)").execute(num_retries=0)
        if (details.get("id") != folder
                or details.get("mimeType") != "application/vnd.google-apps.folder"
                or not isinstance(details.get("permissions"), list)
                or not details["permissions"]
                or any(p.get("type") != "user" for p in details["permissions"])):
            raise WritebackError("A2E archive folder permissions not private")
    except WritebackError:
        raise
    except Exception:
        raise WritebackError("A2E archive folder read-only check failed") from None


def _verified_video(drive, folder: str, task_id: str, *,
                    verify_video=None) -> tuple[dict, float]:
    """Read-only reconciliation against the EXISTING A2E Drive archiver."""
    verify_video = verify_video or archive.verify_mp4
    try:
        existing = archive.already_verified_on_drive(drive, folder, task_id)
        if existing is None:
            raise WritebackError("completed task MP4 not yet archived in private Drive")
        file_id = existing["file_id"]
        meta = drive.files().get(
            fileId=file_id,
            fields="id,mimeType,name,size,md5Checksum,parents,permissions(type,role),appProperties"
        ).execute(num_retries=0)
        if (meta.get("id") != file_id
                or meta.get("name") != f"A2E_{task_id}.mp4"
                or meta.get("mimeType") != "video/mp4"
                or folder not in (meta.get("parents") or [])
                or not isinstance(meta.get("permissions"), list)
                or any(p.get("type") != "user" for p in meta["permissions"])
                or int(meta.get("size", 0)) != existing["bytes"]
                or (meta.get("appProperties") or {}).get("source") != "A2E"
                or (meta.get("appProperties") or {}).get("task_id") != task_id
                or (meta.get("appProperties") or {}).get("sha256") != existing["sha256"]
                or not SHA.fullmatch(existing["sha256"])):
            raise WritebackError("A2E archived MP4 metadata or private permissions invalid")
        # Full downloaded remote bytes must match the archive record. The A2E
        # CDN URL is not a durable asset reference; only private Drive is used.
        data = drive.files().get_media(fileId=file_id).execute(num_retries=0)
        if (not isinstance(data, bytes) or len(data) != existing["bytes"]
                or len(data) > archive.MAX_BYTES or len(data) < 1024
                or data[4:8] != b"ftyp"
                or hashlib.sha256(data).hexdigest() != existing["sha256"]
                or hashlib.md5(data).hexdigest() != meta.get("md5Checksum")):
            raise WritebackError("A2E archived MP4 full-byte readback mismatch")
        with tempfile.TemporaryDirectory(prefix="simba-a2e-verified-mp4-") as d:
            target = Path(d) / "clip.mp4"
            target.write_bytes(data)
            duration = verify_video(target)
        if type(duration) not in (int, float) or not 3 <= duration <= 10:
            raise WritebackError("A2E clip duration not compatible with 5-second model")
        return existing, float(duration)
    except WritebackError:
        raise
    except (archive.ArchiveError, KeyError, TypeError, ValueError, OSError):
        raise WritebackError("A2E archive readback or MP4 validation unavailable") from None
    except Exception:
        raise WritebackError("A2E private Drive read-only operation failed") from None


def _live_status(task_id: str) -> dict:
    key = os.environ.get("A2E_API_KEY", "")
    if not key.startswith("sk_") or len(key) < 15:
        raise WritebackError("A2E read-only status credential unavailable")
    try:
        return archive.detail_for_task(key, task_id)
    except archive.ArchiveError:
        raise WritebackError("A2E task status read-only GET failed") from None


def build_candidate(root: Path, project_id: str, state: dict, *,
                    owner_issue_number: int, source_run_id: int,
                    drive=None, task_detail=None, verify_video=None) -> tuple[Path, dict, dict]:
    """Pure proposal; no project writes or paid operations."""
    if (type(owner_issue_number) is not int or owner_issue_number <= 0
            or type(source_run_id) is not int or source_run_id <= 0):
        raise WritebackError("trusted owner issue and workflow run ID required")
    root = root.resolve()
    path, project = _read_project(root, project_id)
    hand = handoff.make_handoff(root, path, project)
    rows = _check_state(project, hand, state, owner_issue_number)
    drive = drive if drive is not None else archive.oauth_drive_client()
    task_detail = task_detail or _live_status
    _check_archive_folder(drive, DEFAULT_ARCHIVE)

    # Probe all tasks before changing the manifest. A failed/partial task, an
    # unavailable remote MP4, or a mismatched owner receipt blocks every write.
    new_assets, numbers = [], []
    for row in rows:
        tid = row["task_id"]
        try:
            detail = task_detail(tid)
        except WritebackError:
            raise
        except Exception:
            raise WritebackError("A2E status cannot be independently verified") from None
        if (not isinstance(detail, dict)
                or detail.get("_id") not in (None, tid)
                or detail.get("current_status") != "completed"):
            raise WritebackError("A2E server did not confirm completed task")
        media, duration = _verified_video(
            drive, DEFAULT_ARCHIVE, tid, verify_video=verify_video)
        number = row["number"]
        asset_id = "a2e-" + tid
        if any(a.get("id") == asset_id or a.get("task_id") == tid
               for a in project["assets"]):
            raise WritebackError("A2E task already appears in canonical project assets")
        new_assets.append({
            "id": asset_id, "kind": "animated_clip",
            "title": f"A2E verified scene {number:02d}",
            "url": f"https://drive.google.com/file/d/{media['file_id']}/view",
            "drive_file_id": media["file_id"],
            "recorded_sha256": media["sha256"],
            "recorded_size_bytes": media["bytes"],
            "recorded_duration_seconds": round(duration, 3),
            "task_id": tid, "state": "available", "reuse": True,
            "evidence": (
                f"owner GitHub Issue #{owner_issue_number}; run {source_run_id}; "
                "A2E task completed via GET; private Drive MP4 full-byte SHA-256 "
                "and ffprobe verified; not final Video QA or publication"
            ),
        })
        numbers.append(tid)

    candidate = copy.deepcopy(project)
    candidate["assets"].extend(new_assets)
    candidate.setdefault("stage_handoffs", {})["a2e_clips"] = {
        "state": "completed",
        "input_fingerprint": state["lineage"]["handoff_sha256"],
        "assets": [x["id"] for x in new_assets],
        "approval_evidence": (
            f"Previously selected A2E prompts and max credits; authorized owner Issue "
            f"#{owner_issue_number}, completed GitHub run {source_run_id}; "
            "no new editorial approval of final reel implied"
        ),
        "task_evidence": (
            f"{len(new_assets)} A2E tasks GET=completed; all original MP4 files "
            "archived privately in Google Drive; remote SHA-256 and video decoded"
        ),
    }
    candidate["stage"] = "A2E_CLIPS_ARCHIVED_VERIFIED"
    candidate["next_action"] = (
        "VOICE_AND_MUSIC: подготовить три варианта текста и музыки; "
        "согласовать голос и лицензию перед монтажом. Не публиковать.")
    candidate["updated_at"] = datetime.now(timezone.utc).date().isoformat()
    # Editorial approval and publication cannot be produced by A2E.
    if (candidate.get("approvals") != project.get("approvals")
            or candidate.get("approved_asset_id") != project.get("approved_asset_id")
            or candidate.get("working_asset_id") != project.get("working_asset_id")):
        raise WritebackError("A2E stage would modify an unrelated approval")
    outcome = handoff.make_handoff(root, path, candidate)
    packet = outcome.get("packet") or {}
    if (outcome.get("state") != "READY_FOR_HANDOFF"
            or outcome.get("recipient") != "VOICE_AND_MUSIC"
            or packet.get("next_stage") != "voice_music"):
        raise WritebackError("candidate failed next-stage handoff validation")
    summary = {
        "status": "A2E_WRITEBACK_CANDIDATE_VERIFIED_NOT_WRITTEN",
        "project_id": project_id, "source_run_id": source_run_id,
        "source_issue_number": owner_issue_number,
        "handoff_sha256": state["lineage"]["handoff_sha256"],
        "task_ids": numbers, "archived_mp4_count": len(new_assets),
        "next_recipient": "VOICE_AND_MUSIC", "next_stage": "voice_music",
        "paid_calls": 0, "publication": False,
        "project_written": False,
    }
    return path, candidate, summary


def apply_candidate(root: Path, path: Path, candidate: dict,
                    *, original_sha256: str) -> None:
    """One-file atomic local write only in an explicitly trusted Actions job."""
    if (os.environ.get("GITHUB_REPOSITORY") != "legur/Simba"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_ACTOR") != "legur"
            or not os.environ.get("GITHUB_RUN_ID", "").isdigit()):
        raise WritebackError("write-back is restricted to owner main workflow_dispatch")
    if not path.is_relative_to(root.resolve()):
        raise WritebackError("project path leaves repository")
    now = path.read_bytes()
    if hashlib.sha256(now).hexdigest() != original_sha256:
        raise WritebackError("project changed since preflight; do not overwrite")
    result = (json.dumps(candidate, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=".simba-writeback-",
                                     suffix=".tmp", delete=False) as out:
        tmp = Path(out.name)
        out.write(result)
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--project", required=True)
    parser.add_argument("--state-json", required=True, type=Path)
    parser.add_argument("--owner-issue", required=True, type=int)
    parser.add_argument("--source-run", required=True, type=int)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    result = None
    try:
        if not args.state_json.is_file() or args.state_json.stat().st_size > 32768:
            raise WritebackError("universal A2E status.json missing or too large")
        state = json.loads(args.state_json.read_text(encoding="utf-8"))
        root = args.root.resolve()
        path, _ = _read_project(root, args.project)
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        target, candidate, result = build_candidate(
            root, args.project, state, owner_issue_number=args.owner_issue,
            source_run_id=args.source_run)
        if args.apply:
            apply_candidate(root, target, candidate, original_sha256=before)
            result["status"] = "A2E_WRITEBACK_APPLIED_LOCALLY_GIT_PUSH_PENDING"
            result["project_written"] = True
    except (WritebackError, archive.ArchiveError, OSError, ValueError, TypeError, KeyError):
        result = {"status": "BLOCKED_A2E_WRITEBACK",
                  "reason": "Stage, task status, private MP4 readback or trusted source not verified",
                  "paid_calls": 0, "project_written": False}
    except Exception:
        result = {"status": "BLOCKED_A2E_WRITEBACK",
                  "reason": "Unexpected A2E read-only verification failure",
                  "paid_calls": 0, "project_written": False}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    return 0 if not result["status"].startswith("BLOCKED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
