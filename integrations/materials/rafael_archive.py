#!/usr/bin/env python3
"""Private Google Drive archive for ChatGPT-created Simba Rafael storyboards.

This is NOT an image generator or a background task. It uploads an existing,
verified ZIP only on an explicit --execute call. Archive readback is required
before reporting success. Never grants permissions or publishes media.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import auto_script
import studio_archive

ARCHIVE_FOLDER = "1GMoSVogs0SKuTAXCdMVcG-U7bTn-IuCt"
SHA = re.compile(r"^[a-f0-9]{64}$")
PID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
LIMIT = 40_000_000


class ArchiveError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_archive(file: Path) -> tuple[bytes, dict]:
    """Read real bytes and validate all 9 frame/3 preview SHA-256 values."""
    if not file.is_file() or file.stat().st_size > LIMIT or file.stat().st_size < 1000:
        raise ArchiveError("storyboard ZIP missing or outside safe size limit")
    data = file.read_bytes()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
            expected = {"manifest.json"}
            expected.update(f"option_{o}/scene_{s}.jpg" for o in (1, 2, 3) for s in (1, 2, 3))
            expected.update(f"option_{o}/preview.png" for o in (1, 2, 3))
            if set(names) != expected or len(names) != len(expected):
                raise ArchiveError("archive must contain precisely nine frames and three previews")
            if any(i.file_size > 12_000_000 for i in z.infolist()):
                raise ArchiveError("oversized media inside ZIP")
            manifest = json.loads(z.read("manifest.json"))
            if (manifest.get("schema_version") != 1
                    or manifest.get("stage") != "storyboard"
                    or manifest.get("status") != "STORYBOARD_OPTIONS_NEED_LEO"
                    or manifest.get("approval_recorded") is not False
                    or manifest.get("published") is not False
                    or manifest.get("archive_verified") is not False
                    or (manifest.get("generation_evidence") or {}).get("source") != "CHATGPT_IMAGE_TOOL"):
                raise ArchiveError("incorrect storyboard identity or approval state")
            pid, receipt = manifest.get("project_id"), manifest.get("input_receipt")
            if not isinstance(pid, str) or not PID.fullmatch(pid) or not isinstance(receipt, str) or not SHA.fullmatch(receipt):
                raise ArchiveError("unsafe storyboard source identity")
            options = manifest.get("options")
            if not isinstance(options, list) or len(options) != 3:
                raise ArchiveError("three distinct storyboard options required")
            hashes = set()
            for option_no, option in enumerate(options, 1):
                if option.get("option") != option_no:
                    raise ArchiveError("storyboard option sequence invalid")
                preview = f"option_{option_no}/preview.png"
                if option.get("preview") != preview or option.get("preview_sha256") != digest(z.read(preview)):
                    raise ArchiveError("preview file SHA-256 mismatch")
                scenes = option.get("scenes")
                if not isinstance(scenes, list) or len(scenes) != 3:
                    raise ArchiveError("three frames per option required")
                for scene_no, scene in enumerate(scenes, 1):
                    name = f"option_{option_no}/scene_{scene_no}.jpg"
                    if scene.get("scene") != scene_no or scene.get("image") != name:
                        raise ArchiveError("frame order differs from manifest")
                    frame_hash = digest(z.read(name))
                    if scene.get("image_sha256") != frame_hash or frame_hash in hashes:
                        raise ArchiveError("frame file SHA-256 mismatch or duplicate")
                    hashes.add(frame_hash)
    except (zipfile.BadZipFile, UnicodeDecodeError, KeyError, ValueError, TypeError):
        raise ArchiveError("ZIP or manifest cannot be validated") from None
    return data, manifest


def drive_call(request):
    try:
        return request.execute(num_retries=0)
    except Exception:
        raise ArchiveError("private Drive operation failed; no blind upload retry") from None


def check_private_folder(drive, folder: str) -> None:
    if not auto_script.FOLDER_ID_RE.fullmatch(folder):
        raise ArchiveError("invalid private folder")
    metadata = drive_call(drive.files().get(
        fileId=folder, fields="id,name,mimeType,permissions(type,role),capabilities(canAddChildren)"))
    if (metadata.get("id") != folder
            or metadata.get("mimeType") != "application/vnd.google-apps.folder"
            or not metadata.get("capabilities", {}).get("canAddChildren")):
        raise ArchiveError("archive folder inaccessible or not writable")
    permissions = metadata.get("permissions")
    if not isinstance(permissions, list) or not permissions:
        raise ArchiveError("folder permission metadata unavailable; refuse upload")
    if any(row.get("type") != "user" for row in permissions):
        raise ArchiveError("archive folder has broad sharing permissions; refuse upload")


def existing_files(drive, folder: str, name: str) -> list[dict]:
    if not re.fullmatch(r"Simba_[a-z0-9-]+_RAFAEL_[a-f0-9]{16}_3_STORYBOARDS\.zip", name):
        raise ArchiveError("invalid archive name")
    rows = drive_call(drive.files().list(
        q=f"'{folder}' in parents and name = '{name}' and trashed = false",
        fields="nextPageToken,files(id,name,parents,size,md5Checksum,appProperties)",
        pageSize=100))
    if rows.get("nextPageToken"):
        raise ArchiveError("incomplete Drive listing; refuse blind duplication")
    files = rows.get("files") or []
    if len(files) > 1:
        raise ArchiveError("ambiguous archived copies; require manual reconciliation")
    return files


def archive_private(drive, folder: str, path: Path) -> dict:
    payload, manifest = safe_archive(path)
    check_private_folder(drive, folder)
    pid, receipt = manifest["project_id"], manifest["input_receipt"]
    name = f"Simba_{pid}_RAFAEL_{receipt[:16]}_3_STORYBOARDS.zip"
    expected_sha = digest(payload)
    existing = existing_files(drive, folder, name)
    if existing:
        file_id = existing[0]["id"]
        status = "ALREADY_VERIFIED_PRIVATE"
    else:
        try:
            from googleapiclient.http import MediaInMemoryUpload
        except ImportError:
            raise ArchiveError("Google API client not installed") from None
        created = drive_call(drive.files().create(
            body={"name": name, "parents": [folder],
                  "appProperties": {"origin": "simba_chatgpt_rafael",
                                    "input_receipt": receipt, "sha256": expected_sha}},
            media_body=MediaInMemoryUpload(payload, mimetype="application/zip", resumable=False),
            fields="id"))
        file_id = created.get("id")
        if not file_id:
            raise ArchiveError("Drive did not return new file ID")
        status = "VERIFIED_PRIVATE_UPLOAD"
    metadata = drive_call(drive.files().get(
        fileId=file_id, fields="id,name,parents,size,md5Checksum,appProperties,permissions(type,role)"))
    if (metadata.get("id") != file_id or metadata.get("name") != name
            or folder not in (metadata.get("parents") or [])
            or int(metadata.get("size") or -1) != len(payload)
            or metadata.get("md5Checksum") != hashlib.md5(payload).hexdigest()
            or metadata.get("appProperties", {}).get("input_receipt") != receipt
            or metadata.get("appProperties", {}).get("sha256") != expected_sha):
        raise ArchiveError("private Drive metadata or checksum readback failed")
    permissions = metadata.get("permissions")
    if permissions is not None and any(p.get("type") != "user" for p in permissions):
        raise ArchiveError("uploaded archive unexpectedly shared broadly")
    remote = drive_call(drive.files().get_media(fileId=file_id))
    if not isinstance(remote, bytes) or digest(remote) != expected_sha:
        raise ArchiveError("remote ZIP byte readback SHA-256 mismatch")
    # Keep the ZIP only as the existing Montage transport; archive every
    # verified original separately for the owner in the project folder.
    with zipfile.ZipFile(io.BytesIO(payload)) as package:
        individual = {
            receipt[:16] + '_' + name.replace('/', '_'): package.read(name)
            for name in package.namelist()
        }
    try:
        source_archive = studio_archive.save_files(drive, pid, 'storyboard', individual)
    except studio_archive.ArchiveError:
        raise ArchiveError('individual storyboard archive failed; reconcile before retry') from None
    return {"status": status, "project_id": pid, "input_receipt": receipt,
            "drive_file_id": file_id, "folder_id": folder, "sha256": expected_sha,
            "actual_frames": 9, "actual_previews": 3, "leo_approved": False,
            "paid_api_calls": 0, "published": False, "archive_verified": True,
            "individual_files": source_archive}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--folder", default=ARCHIVE_FOLDER)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload, manifest = safe_archive(args.zip)
        if not args.execute:
            result = {"status": "LOCAL_ZIP_VERIFIED_UPLOAD_NOT_EXECUTED",
                      "project_id": manifest["project_id"],
                      "sha256": digest(payload), "archive_verified": False}
        else:
            result = archive_private(auto_script.drive_client(), args.folder, args.zip)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ArchiveError, auto_script.AgentError, ValueError, OSError) as exc:
        print("SIMBA_RAFAEL_ARCHIVE_BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
