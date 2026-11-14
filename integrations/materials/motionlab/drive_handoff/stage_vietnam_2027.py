#!/usr/bin/env python3
"""Owner-only, no-paid stage of 10 completed Vietnam Cambodia A2E MP4s in existing Studio v1.

Verifies A2E task IDs, actual private Drive source metadata and immutable SHA/size
against committed project receipts, writes exactly one private launch, then issues
one-use ticket through EXISTING issue_ticket.py. Never starts A2E/TTS/Montage.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
VIDEO = ROOT / "integrations" / "video"
if str(VIDEO) not in sys.path:
    sys.path.insert(0, str(VIDEO))
import a2e_drive_archiver as archive
import issue_ticket

PROJECT = "vietnam-cambodia-2027"
MEDIA_FOLDER = "1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj"
SCENE_COUNT = 10
REQUEST = "vn-camb-2027-motionlab-20261114"
LAUNCH_FILENAME = "motionlab-vietnam-cambodia-2027-selected-a2e-v1.json"

OPTIONS = [
    {
        "name": "Путевой дневник", "label": "ТЕПЛЫЙ",
        "description": "Теплая бумажная типографика, спокойные растворения, деликатные титры.",
        "settings": {
            "camera": "float", "transition": "crossfade", "titleFx": "fade-rise",
            "subtitleStyle": "editorial", "wordMotion": "caption-swap", "intensity": 25
        },
    },
    {
        "name": "Киноистория", "label": "КИНО",
        "description": "Контрастные титры, более строгая композиция, мягкие кинопереходы.",
        "settings": {
            "camera": "cinematic-zoom", "transition": "crossfade", "titleFx": "fade-rise",
            "subtitleStyle": "clean", "wordMotion": "karaoke", "intensity": 20
        },
    },
    {
        "name": "Энергичный маршрут", "label": "ДИНАМИЧНЫЙ",
        "description": "Крупные заголовки, яркие акценты и ритмичные сдвиги.",
        "settings": {
            "camera": "push-through", "transition": "push", "titleFx": "punch-zoom",
            "subtitleStyle": "capsule", "wordMotion": "active-pop", "intensity": 60
        },
    },
]

def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def existing_only(drive, folder, name):
    entries = archive.drive_matches(drive, folder, name)
    if len(entries) > 1:
        raise RuntimeError("Ambiguous existing private file")
    return entries[0] if entries else None

def stage(renew: bool = False):
    selection = load("campaigns/vietnam-cambodia-2027/selected_images_2026-11-14.json")
    receipt = load("campaigns/vietnam-cambodia-2027/a2e_preflight_2026-11-14.json")
    editorial = load("campaigns/vietnam-cambodia-2027/storyboard_option_2_SCENE_EDITOR.json")
    selected = selection.get("images", [])
    videos = receipt.get("local_mp4_manifest", [])
    copy = editorial.get("scenes", [])
    if not (len(selected) == len(videos) == len(copy) == SCENE_COUNT):
        raise RuntimeError("Selected images / clips / script count mismatch")
    if receipt.get("completed_mp4_count") != SCENE_COUNT or receipt.get("paid_start_attempted") is not True:
        raise RuntimeError("A2E completion receipt missing")
    if any(x["scene_number"] != i+1 or x["option"] != ("B" if i == 4 else "A")
           for i,x in enumerate(selected)):
        raise RuntimeError("Selected source assets differ from owner approval")

    drive = archive.oauth_drive_client()
    previews = []
    scenes = []
    hashes = []
    total = 0
    for i, (source, video, story) in enumerate(zip(selected, videos, copy), start=1):
        if video.get("scene_number") != i or story.get("scene_number") != i:
            raise RuntimeError("Scene order mismatch")
        task = video.get("task_id")
        if not isinstance(task, str) or not archive.VALID_TASK.fullmatch(task):
            raise RuntimeError("Invalid A2E task ID")
        verified = archive.already_verified_on_drive(drive, MEDIA_FOLDER, task)
        if not verified:
            raise RuntimeError("Required separate original MP4 not yet archived: scene %02d" % i)
        if verified["sha256"] != video["sha256"] or verified["bytes"] != video["size_bytes"]:
            raise RuntimeError("Private Drive original content differs from pinned MP4: scene %02d" % i)
        if verified["bytes"] > 20*1024*1024:
            raise RuntimeError("Private video too large for Studio preview: scene %02d" % i)
        fid = verified["file_id"]
        meta = drive.files().get(
            fileId=fid,
            fields="id,name,mimeType,size,parents,trashed,permissions(type,role)"
        ).execute(num_retries=2)
        if (meta.get("mimeType") != "video/mp4" or meta.get("trashed")
            or MEDIA_FOLDER not in (meta.get("parents") or [])
            or str(meta.get("size")) != str(video["size_bytes"])):
            raise RuntimeError("Original video metadata mismatch")
        if any(p.get("type") != "user" for p in (meta.get("permissions") or [])):
            raise RuntimeError("Original Drive video is not private")
        duration = 5.0625
        asset = "vn-camb-2027-clip-%02d" % i
        previews.append({
            "asset_id": asset, "file_id": fid, "sha256": video["sha256"],
            "size_bytes": video["size_bytes"], "mime_type": "video/mp4"
        })
        scenes.append({
            "scene_id": story["scene_id"], "name": story["title"], "asset_id": asset,
            "duration_s": duration,
            "title_text": str(story["screen_text"]).split("\n")[0][:140],
            "subtitle_preview": str(story["voice_text"])[:300],
            "media": {
                "kind": "video", "asset_sha256": video["sha256"], "duration_s": duration
            },
        })
        hashes.append(video["sha256"])
        total += video["size_bytes"]

    if total > 120*1024*1024:
        raise RuntimeError("Originals exceed Studio project cap")

    fingerprint = digest({
        "project_id": PROJECT, "selected_source_images": [row["image_drive_file_id"] for row in selected],
        "a2e_tasks": [row["task_id"] for row in videos],
        "original_mp4_sha256": hashes,
        "approved_words": [row["voice_text"] for row in copy],
    })
    launch = {
        "schema": "bontours.motionlab.storyboard.launch/v1",
        "request_id": REQUEST, "project_id": PROJECT, "stage": "edit_choice",
        "expected_input_fingerprint": fingerprint,
        "options": OPTIONS, "scenes": scenes, "preview_assets": previews,
        "selected_option": 1,
    }
    issue_ticket.validate_launch(launch)

    existing_launch = existing_only(drive, issue_ticket.LAUNCH_DIR, LAUNCH_FILENAME)
    if existing_launch:
        launch_id = existing_launch["id"]
        current = issue_ticket.read_approved_launch(drive, launch_id)
        if current != launch:
            raise RuntimeError("Existing launch has changed; do not overwrite")
    else:
        launch_id = issue_ticket.upload(
            drive, issue_ticket.LAUNCH_DIR, LAUNCH_FILENAME, launch)
        current = issue_ticket.read_approved_launch(drive, launch_id)
        if current != launch:
            raise RuntimeError("New launch failed exact content readback")

    ticket_name = "motionlab-" + REQUEST + "-ticket.json"
    # Renewal is an explicit owner-only operation; do not discard an existing
    # approved launch or change any immutable video sources.
    if not renew and archive.drive_matches(drive, issue_ticket.TICKET_DIR, ticket_name):
        return {"status": "ALREADY_ISSUED_CHECK_OWNER_DRIVE", "launch_file_id": launch_id,
                "scene_count": len(scenes), "media_verified": True,
                "paid_calls": 0, "token_printed": False}
    ticket = issue_ticket.issue(drive, launch_id)
    return {
        "status": "STUDIO_V1_PRIVATE_TICKET_ISSUED",
        "project_id": PROJECT, "scene_count": len(scenes), "option_count": 3,
        "source_fingerprint": fingerprint,
        "launch_file_id": launch_id,
        "authorized_launch_file_id": ticket["authorized_launch_file_id"],
        "ticket_file_id": ticket["ticket_file_id"],
        "ticket_expires_utc": ticket["ticket_expires_utc"],
        "all_previews_private_drive": True,
        "clips_qa": "PINNED_MP4_SHA256_AND_BYTES_VERIFIED",
        "paid_calls": 0, "render_authorized": False, "publication_authorized": False,
        "live_browser_ack": False, "token_printed": False,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--renew", action="store_true",
                        help="Issue a new 3-hour owner-private Studio ticket for the same verified clips.")
    args = parser.parse_args()
    try:
        result = stage(renew=args.renew)
    except Exception as exc:
        # Do not print secret bearer tokens, raw remote responses or signed URLs.
        result = {"status": "STUDIO_LAUNCH_BLOCKED", "reason": str(exc)[:160], "paid_calls": 0}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2),encoding="utf-8")
    print("Studio Vietnam private launch:", result["status"])
    sys.exit(0 if result["status"] in ("STUDIO_V1_PRIVATE_TICKET_ISSUED", "ALREADY_ISSUED_CHECK_OWNER_DRIVE") else 2)
