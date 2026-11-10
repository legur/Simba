#!/usr/bin/env python3
"""Step 5G: Motion Lab PR #112 -> canonical Simba edit_choice handoff.

Uses the EXISTING motionlab_selection.validate. Two private owner-only Google
Drive JSON files (source launch and connected-session selection) are read back
and SHA256/MD5 verified before an owner dispatch can write a single canonical
project.json edit_plan entry. Offline/demo drafts cannot be promoted to approval.

Read-only default. No media is copied into GitHub; no paid TTS/A2E, renders or
publications. Browser SIMBA_MOTIONLAB_ACK requires an actual durable host write;
this workflow is an owner-driven recovery/import path, NOT a live browser host.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

MATERIALS = Path(__file__).resolve().parent
MOTIONLAB = MATERIALS / "motionlab"
if str(MATERIALS) not in sys.path:
    sys.path.insert(0, str(MATERIALS))
if str(MATERIALS.parent / "video") not in sys.path:
    sys.path.insert(0, str(MATERIALS.parent / "video"))
if str(MOTIONLAB) not in sys.path:
    sys.path.insert(0, str(MOTIONLAB))

import catalog
import handoff
import auto_script
import rafael_archive
import a2e_writeback
import motionlab_selection as selector

PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
REQUEST_ID = re.compile(r"^[A-Za-z0-9_:.-]{4,90}$")
DRIVE_ID = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
MAX_LAUNCH = 128_000
MAX_SELECTION = 128_000
MOTIONLAB_ORIGIN = "https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com"


class MotionLabStageError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _open_stage(root: Path, project_id: str) -> tuple[Path, dict, dict]:
    if not isinstance(project_id, str) or not PROJECT_ID.fullmatch(project_id):
        raise MotionLabStageError("invalid canonical project ID")
    root = root.resolve()
    path = catalog.inside(root, f"campaigns/{project_id}/project.json")
    try:
        project = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        raise MotionLabStageError("canonical source project not readable") from None
    if project.get("id") != project_id:
        raise MotionLabStageError("canonical project ID mismatch")
    stage = handoff.make_handoff(root, path, project)
    packet = stage.get("packet") or {}
    if (stage.get("state") != "READY_FOR_HANDOFF"
            or stage.get("recipient") != "MONTAGE"
            or packet.get("next_stage") != "edit_choice"
            or not isinstance(packet.get("receipt_sha256"), str)
            or not SHA.fullmatch(packet["receipt_sha256"])
            or "edit_choice" in project.get("stage_handoffs", {})):
        raise MotionLabStageError("current voice/music stage is not ready for edit_choice")
    return path, project, packet


def _clips(project: dict) -> list[dict]:
    approved = project["stage_handoffs"].get("a2e_clips") or {}
    ids = approved.get("assets")
    assets = {a["id"]: a for a in project.get("assets", []) if isinstance(a, dict) and a.get("id")}
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 6
            or len(ids) != len(set(ids))):
        raise MotionLabStageError("verified A2E clip list missing/invalid")
    result = []
    for aid in ids:
        a = assets.get(aid)
        duration = a.get("recorded_duration_seconds") if a else None
        if (not a or a.get("kind") != "animated_clip" or a.get("state") != "available"
                or not isinstance(a.get("task_id"), str) or not a.get("task_id")
                or not isinstance(a.get("recorded_sha256"), str)
                or not SHA.fullmatch(a["recorded_sha256"])
                or type(duration) not in (int, float) or not math.isfinite(duration)
                or not 3 <= duration <= 10
                or not isinstance(a.get("drive_file_id"), str)):
            raise MotionLabStageError("A2E clip not backed by verified private archive receipt")
        result.append(a)
    return result


def _options(options: object) -> list[dict]:
    """Only operator-provided three proposals, never generate fake choices."""
    if not isinstance(options, list) or len(options) != 3:
        raise MotionLabStageError("three actual edit proposals must be provided")
    clean = []
    for idx, x in enumerate(options, 1):
        if not isinstance(x, dict):
            raise MotionLabStageError("invalid edit option")
        settings = x.get("settings")
        if (not isinstance(settings, dict)
                or not isinstance(x.get("name"), str) or not 3 <= len(x["name"].strip()) <= 60
                or not isinstance(x.get("description"), str)
                or not 12 <= len(x["description"].strip()) <= 220
                or settings.get("camera") not in selector.CAMERAS
                or settings.get("transition") not in selector.TRANSITIONS
                or settings.get("titleFx") not in selector.TITLE_FX
                or settings.get("subtitleStyle") not in selector.SUBTITLE_STYLES
                or settings.get("wordMotion") not in selector.WORD_MOTIONS
                or type(settings.get("intensity")) not in (int, float)
                or not math.isfinite(settings["intensity"])
                or not 0 <= settings["intensity"] <= 100):
            raise MotionLabStageError("three variants have unsupported or incomplete effects")
        clean.append({"name":x["name"].strip(),"description":x["description"].strip(),
                      "label":str(x.get("label",f"ВАРИАНТ {idx}"))[:36],
                      "settings":{k:settings[k] for k in
                          ("camera","transition","titleFx","subtitleStyle","wordMotion","intensity")}})
    names = [x["name"].casefold() for x in clean]
    signatures = [json.dumps(x["settings"],sort_keys=True) for x in clean]
    if len(set(names)) != 3 or len(set(signatures)) != 3:
        raise MotionLabStageError("three visually distinct edit variants required")
    return clean


def build_launch(root: Path, project_id: str, options: list[dict], request_id: str) -> dict:
    """Create source-fingerprint-pinned Motion Lab START, no fabricated previews."""
    _, project, packet = _open_stage(root, project_id)
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise MotionLabStageError("unique safe request ID required")
    clips = _clips(project)
    opts = _options(options)
    scenes = []
    for number, a in enumerate(clips, 1):
        # No private Drive media link is passed into a public Wix page.
        # The user sees the exact asset_id; preview is unavailable unless
        # an independent, authorized public preview exists.
        scenes.append({
            "scene_id": f"clip-{number:02d}",
            "name": f"Сцена {number:02d}",
            "asset_id": a["id"],
            "duration_s": round(min(5.0, float(a["recorded_duration_seconds"])), 2),
            "title_text": "", "subtitle_preview": "",
        })
    return {
        "schema": selector.SCHEMA_LAUNCH,
        "request_id": request_id, "project_id": project_id, "stage": "edit_choice",
        "expected_input_fingerprint": packet["receipt_sha256"],
        "options": opts, "scenes": scenes,
        "selected_option": 1,
    }


def _verify_launch(root: Path, project_id: str, launch: dict, packet: dict, project: dict) -> None:
    if (not isinstance(launch, dict) or launch.get("schema") != selector.SCHEMA_LAUNCH
            or launch.get("stage") != "edit_choice" or launch.get("project_id") != project_id
            or launch.get("expected_input_fingerprint") != packet["receipt_sha256"]
            or not isinstance(launch.get("request_id"), str)
            or not REQUEST_ID.fullmatch(launch["request_id"])
            or launch.get("selected_option") != 1
            or _options(launch.get("options")) != launch["options"]):
        raise MotionLabStageError("stored Motion Lab launch is not current and canonical")
    clips = _clips(project)
    supplied = launch.get("scenes")
    if not isinstance(supplied, list) or len(supplied) != len(clips):
        raise MotionLabStageError("launch scenes differ from actually archived A2E clips")
    pairs = list(zip(supplied, clips))
    ids = set()
    for n,(scene,asset) in enumerate(pairs,1):
        if (not isinstance(scene, dict) or scene.get("scene_id") != f"clip-{n:02d}"
                or scene["scene_id"] in ids or scene.get("asset_id") != asset["id"]
                or not isinstance(scene.get("name"),str)
                or len(scene["name"].strip()) < 2
                or type(scene.get("duration_s")) not in (int,float)
                or not 1 <= scene["duration_s"] <= asset["recorded_duration_seconds"] + 0.5
                or (scene.get("preview_url") is not None
                    and not _safe_public_preview(scene["preview_url"]))):
            raise MotionLabStageError("launch has substituted, duplicated or unverified A2E scene")
        ids.add(scene["scene_id"])
    if sum(x["duration_s"] for x in supplied) > 60:
        raise MotionLabStageError("launch exceeds 60-second montage limit")


def _safe_public_preview(value: object) -> bool:
    if not isinstance(value,str) or len(value)>750:
        return False
    parsed=urlsplit(value)
    return (parsed.scheme=="https" and parsed.hostname=="static.wixstatic.com"
            and parsed.path.startswith("/media/")
            and not parsed.query and not parsed.fragment and not parsed.username
            and not parsed.password and parsed.port in (None,443))


def _verified_json(drive, file_id: str, sha: str, limit: int) -> tuple[bytes,dict]:
    if (not isinstance(file_id,str) or not DRIVE_ID.fullmatch(file_id)
            or not isinstance(sha,str) or not SHA.fullmatch(sha)):
        raise MotionLabStageError("private Drive file ID/SHA-256 required")
    try:
        meta = rafael_archive.drive_call(drive.files().get(
            fileId=file_id,fields="id,name,mimeType,parents,size,md5Checksum,permissions(type,role)"))
        if (meta.get("id")!=file_id or meta.get("mimeType")!="application/json"
                or rafael_archive.ARCHIVE_FOLDER not in (meta.get("parents") or [])
                or not isinstance(meta.get("permissions"),list) or not meta["permissions"]
                or any(p.get("type")!="user" for p in meta["permissions"])
                or not 100<=int(meta.get("size",0))<=limit):
            raise MotionLabStageError("private Motion Lab JSON metadata or permissions invalid")
        raw=rafael_archive.drive_call(drive.files().get_media(fileId=file_id))
        if (not isinstance(raw,bytes) or len(raw)!=int(meta["size"])
                or digest(raw)!=sha
                or hashlib.md5(raw).hexdigest()!=meta.get("md5Checksum")):
            raise MotionLabStageError("Motion Lab JSON bytes differ from pinned private Drive SHA")
        return raw,meta
    except MotionLabStageError:
        raise
    except Exception:
        raise MotionLabStageError("private Drive source unavailable or incomplete") from None


def _check_choice(launch: dict, choice: dict, project: dict) -> dict:
    try:
        validated = selector.validate(launch, choice)
    except (selector.InvalidSelection,ValueError,TypeError,KeyError):
        raise MotionLabStageError("Motion Lab selection violates existing v1 contract") from None
    # An exported DRAFT_NOT_DELIVERED is never silently promoted.
    decision = choice["decision"]
    prov = choice.get("provenance") or {}
    guards = choice.get("guards") or {}
    if (prov.get("origin") != "motion-lab-storyboard"
            or prov.get("mode") != "embedded-bridge"
            or decision.get("confirmation_scope") != "EDIT_CHOICES_ONLY"
            or guards.get("production_state") != "PREPRODUCTION"
            or choice.get("format") != "9:16"):
        raise MotionLabStageError("authenticated connected-session Motion Lab provenance required")
    try:
        selected_at = datetime.fromisoformat(decision["user_selected_at"].replace("Z","+00:00"))
        if selected_at.tzinfo is None:
            raise ValueError()
        elapsed = (datetime.now(timezone.utc)-selected_at.astimezone(timezone.utc)).total_seconds()
    except (ValueError,TypeError):
        raise MotionLabStageError("valid UTC selection timestamp required") from None
    if not -300 <= elapsed <= 7*24*3600:
        raise MotionLabStageError("selected option too old or future dated")
    pairs = choice["scenes"]
    approved = {a["id"]:a for a in _clips(project)}
    if len(pairs)!=len(approved) or len({row["asset_id"] for row in pairs})!=len(approved):
        raise MotionLabStageError("Motion Lab selection deleted or duplicated a verified clip")
    if {row["asset_id"] for row in pairs}!=set(approved):
        raise MotionLabStageError("Motion Lab selection substituted an unapproved clip")
    total = 0.0
    for row in pairs:
        if row.get("title",{}).get("display_text") is None:
            raise MotionLabStageError("missing edit title decisions")
        duration = row["duration_seconds"]
        if duration > approved[row["asset_id"]]["recorded_duration_seconds"]+0.5:
            raise MotionLabStageError("selected clip longer than verified available media")
        if len(row["title"]["display_text"])>140:
            raise MotionLabStageError("title text exceeds renderer safe bound")
        if len(row["subtitles"].get("preview_text", ""))>300:
            raise MotionLabStageError("subtitle preview exceeds renderer safe bound")
        total+=duration
    if total>60:
        raise MotionLabStageError("selected timeline exceeds 60 seconds")
    return validated


def build_candidate(root: Path, project_id: str, *,
                    launch_file_id: str, launch_sha256: str,
                    selection_file_id: str, selection_sha256: str,
                    drive=None) -> tuple[Path,dict,dict]:
    """Read-only until caller explicitly applies on owner main workflow."""
    root=root.resolve()
    path,project,packet=_open_stage(root,project_id)
    if launch_file_id == selection_file_id:
        raise MotionLabStageError("launch and selection must be distinct private files")
    if drive is None:
        drive=auto_script.drive_client()
    try:
        rafael_archive.check_private_folder(drive,rafael_archive.ARCHIVE_FOLDER)
    except Exception:
        raise MotionLabStageError("private folder verification unavailable") from None
    launch_bytes,_=_verified_json(drive,launch_file_id,launch_sha256,MAX_LAUNCH)
    selection_bytes,_=_verified_json(drive,selection_file_id,selection_sha256,MAX_SELECTION)
    try:
        launch=json.loads(launch_bytes)
        choice=json.loads(selection_bytes)
    except (UnicodeDecodeError,ValueError):
        raise MotionLabStageError("selected Motion Lab private JSON invalid") from None
    _verify_launch(root,project_id,launch,packet,project)
    receipt=_check_choice(launch,choice,project)
    # Selection JSON is the actual, immutable read-back evidence. Host must
    # only send an ACK after the later durable write/commit succeeds.
    asset_id = "motionlab-"+selection_sha256[:24]
    if any(a.get("id")==asset_id or a.get("drive_file_id")==selection_file_id
           for a in project.get("assets",[])):
        raise MotionLabStageError("edit-plan replay or previously registered asset")
    candidate=copy.deepcopy(project)
    candidate["assets"].append({
        "id":asset_id,"kind":"edit_plan","title":"Motion Lab selected montage plan",
        "state":"available",
        "url":f"https://drive.google.com/file/d/{selection_file_id}/view",
        "drive_file_id":selection_file_id,
        "recorded_sha256":selection_sha256,
        "launch_file_id":launch_file_id,
        "launch_sha256":launch_sha256,
        "evidence":"Read-only verified owner-private launch and connected-session "
                   "Motion Lab selection; checksum pinned; no render/paid approval",
    })
    candidate["stage_handoffs"]["edit_choice"]={
        "state":"approved",
        "input_fingerprint":packet["receipt_sha256"],
        "assets":[asset_id],
        "selected_option":receipt["selected_option"],
        "options_presented":3,
        "options_evidence":"Exact three distinct edit proposals pinned in owner-private "
                           f"Motion Lab launch SHA256 {launch_sha256}; source receipt checked",
        "approval_evidence":f"Owner-triggered Motion Lab selection accepted for request "
                            f"{receipt['request_id']} with immutable receipt {receipt['receipt_id']}; "
                            "edit_choice only, no rendering authorization",
        "motionlab_receipt_id":receipt["receipt_id"],
        "request_id":receipt["request_id"],
        "selection_sha256":selection_sha256,
        "source_clip_ids":[x["asset_id"] for x in choice["scenes"]],
        "no_paid_operations":True,
        "no_auto_publish":True,
    }
    candidate["stage"]="EDIT_CHOICE_RECORDED_AWAITING_MONTAGE_RENDER_PLAN"
    candidate["next_action"]=(
        "MONTAGE_RENDERER: сверить параметры Motion Lab с реальными "
        "возможностями рендера; сохранить утвержденную озвучку и музыку. "
        "Не запускать платный TTS/A2E и не публиковать автоматически."
    )
    candidate["updated_at"]=datetime.now(timezone.utc).date().isoformat()
    if (project.get("approvals")!=candidate.get("approvals")
            or project.get("approved_asset_id")!=candidate.get("approved_asset_id")
            or project.get("working_asset_id")!=candidate.get("working_asset_id")):
        raise MotionLabStageError("editing selection cannot modify publication or MP4 approval")
    outcome=handoff.make_handoff(root,path,candidate)
    after=outcome.get("packet") or {}
    if (outcome.get("state")!="READY_FOR_HANDOFF"
            or outcome.get("recipient")!="MONTAGE_RENDERER"
            or after.get("next_stage")!="render"):
        raise MotionLabStageError("existing montage renderer handoff rejected edit plan")
    return path,candidate,{
        "status":"MOTIONLAB_EDIT_CHOICE_VALIDATED_NOT_WRITTEN",
        "project_id":project_id,"request_id":receipt["request_id"],
        "selection_receipt_id":receipt["receipt_id"],
        "selection_number":receipt["selected_option"],
        "source_scene_count":receipt["scene_count"],
        "next_stage":"render","next_recipient":"MONTAGE_RENDERER",
        "source_fingerprint":packet["receipt_sha256"],
        "private_media_links_exported":False,"actual_render_started":False,
        "paid_calls":0,"auto_publish":False,"project_written":False,
        "browser_ack_sent":False,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--project",required=True)
    p.add_argument("--launch-file-id",required=True)
    p.add_argument("--launch-sha256",required=True)
    p.add_argument("--selection-file-id",required=True)
    p.add_argument("--selection-sha256",required=True)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--report",type=Path)
    args=p.parse_args(argv)
    try:
        root=args.root.resolve()
        source=catalog.inside(root,f"campaigns/{args.project}/project.json")
        original_sha=digest(source.read_bytes())
        target,candidate,receipt=build_candidate(
            root,args.project,launch_file_id=args.launch_file_id,
            launch_sha256=args.launch_sha256,
            selection_file_id=args.selection_file_id,
            selection_sha256=args.selection_sha256)
        if args.apply:
            a2e_writeback.apply_candidate(root,target,candidate,original_sha256=original_sha)
            receipt["status"]="MOTIONLAB_EDIT_CHOICE_APPLIED_LOCALLY_GIT_PUSH_PENDING"
            receipt["project_written"]=True
        exit_code=0
    except Exception:
        # Do not log uploaded titles or URLs: the GitHub repo is public.
        receipt={"status":"BLOCKED_MOTIONLAB_SELECTION",
                 "reason":"Current approval, connected-session selection, private Drive or source assets invalid",
                 "project_written":False,"paid_calls":0,"auto_publish":False,
                 "browser_ack_sent":False}
        exit_code=2
    output=json.dumps(receipt,ensure_ascii=False,indent=2)
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(output+"\n",encoding="utf-8")
    return exit_code


if __name__=="__main__":
    raise SystemExit(main())
