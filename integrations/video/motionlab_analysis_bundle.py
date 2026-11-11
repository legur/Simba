#!/usr/bin/env python3
"""Make a PRIVATE media package for the separate multimodal Motion Lab agent.

The bundle contains verified original A2E MP4 bytes, four timestamped
contact-sheet frames per scene and source-pinned materials.launch/v2.
Creation does NOT deliver files to another ChatGPT conversation, grant
access, upload to Wix/GitHub, run A2E/TTS or imply any visual AI inspection.
An owner may securely attach the private ZIP to the Motion Lab conversation.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

import motionlab_render_contract as r
import motionlab_v2_contract as v2

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_CLIP_BYTES = 160 * 1024 * 1024
MAX_TOTAL_BYTES = 480 * 1024 * 1024
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def sha_file(path: Path) -> str:
    return r._actual_sha(path)


def _private_destination(path: Path, job_dir: Path) -> Path:
    path=Path(path).expanduser().absolute()
    if path.exists() or path.is_symlink():
        raise r.ContractError("PRIVATE_BUNDLE_ALREADY_EXISTS")
    if path.suffix.lower() != ".zip":
        raise r.ContractError("PRIVATE_BUNDLE_PATH_INVALID")
    parent=path.parent.resolve()
    job=Path(job_dir).resolve()
    if (parent.is_relative_to(REPO_ROOT) or
            parent.is_relative_to(job) or
            parent == Path.cwd().resolve()):
        raise r.ContractError("PRIVATE_BUNDLE_MUST_LIVE_OUTSIDE_GIT_AND_JOB")
    if not parent.is_dir():
        raise r.ContractError("PRIVATE_BUNDLE_PARENT_MISSING")
    return path


def _frame_ffmpeg(mp4: Path, seconds: float, output: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise r.ContractError("FFMPEG_REQUIRED_FOR_ANALYSIS")
    cmd = [
        "ffmpeg","-hide_banner","-nostdin","-loglevel","error","-y",
        "-ss", f"{seconds:.3f}","-i",str(mp4),"-frames:v","1",
        "-vf","scale=256:144:force_original_aspect_ratio=decrease,"
              "pad=256:144:(ow-iw)/2:(oh-ih)/2",
        "-f","image2",str(output),
    ]
    try:
        subprocess.run(cmd,check=True,timeout=35,capture_output=True)
    except (OSError,subprocess.SubprocessError):
        raise r.ContractError("CONTACT_SHEET_DECODE_FAILED") from None
    if (not output.is_file() or not 100 <= output.stat().st_size <= 4_000_000
            or output.read_bytes()[:8] != PNG_HEADER):
        raise r.ContractError("CONTACT_SHEET_DECODE_FAILED")


def _contact_sheet(mp4: Path, duration: float) -> tuple[bytes,list[float]]:
    try:
        from PIL import Image,ImageDraw
    except ImportError:
        raise r.ContractError("PILLOW_REQUIRED_FOR_ANALYSIS") from None
    # Four distinct source times, never extrapolate or invent missing frames.
    times=[round(0.25+(duration-0.5)*(i+.5)/4,3) for i in range(4)]
    with tempfile.TemporaryDirectory(prefix="simba-verified-frames-") as temp:
        frames=[]
        for i,ts in enumerate(times):
            frame=Path(temp)/f"frame-{i}.png"
            _frame_ffmpeg(mp4,ts,frame)
            with Image.open(frame) as img:
                frames.append(img.convert("RGB").copy())
        sheet=Image.new("RGB",(256*4,180),(19,29,44))
        draw=ImageDraw.Draw(sheet)
        for n,(image,ts) in enumerate(zip(frames,times)):
            sheet.paste(image,(n*256,0))
            draw.text((n*256+8,151),f"t = {ts:.3f} s",fill=(250,250,250))
        output=io.BytesIO()
        sheet.save(output,format="PNG",optimize=True)
        raw=output.getvalue()
        if not 200 <= len(raw) <= 20_000_000 or raw[:8] != PNG_HEADER:
            raise r.ContractError("CONTACT_SHEET_CREATION_FAILED")
        return raw,times


def build_private_analysis_bundle(materials: dict, verified_media: list[dict],
                                  job_dir: Path, output_zip: Path, *,
                                  probe=None) -> dict:
    """Write one exclusively private ZIP with verifiable originals + sheets.

    The caller must already possess legitimate private media access.
    Output is not uploaded anywhere and must be explicitly provided to
    the separate Motion Lab ChatGPT conversation by the authorized owner.
    """
    v2.validate_materials(materials)
    job=Path(job_dir).resolve()
    output=_private_destination(output_zip,job)
    if not isinstance(verified_media,list) or len(verified_media)!=len(materials["scenes"]):
        raise r.ContractError("MISSING_VERIFIED_ASSET")
    probe=probe or r._ffprobe
    checked=[];total=0
    for index,(scene,asset) in enumerate(zip(materials["scenes"],verified_media),1):
        sid=scene["scene_id"]
        if (not isinstance(asset,dict)
                or scene["asset_id"]!=asset.get("asset_id")
                or sid != asset.get("scene_id")):
            raise r.ContractError("SOURCE_BINDING_CHANGED",scene_id=sid)
        path=r._safe_clip(job,asset["file"])
        size=path.stat().st_size
        if not 200 <= size <= MAX_CLIP_BYTES:
            raise r.ContractError("PRIVATE_MEDIA_SIZE_INVALID",scene_id=sid)
        total+=size
        if total > MAX_TOTAL_BYTES:
            raise r.ContractError("PRIVATE_BUNDLE_TOO_LARGE")
        media=v2.checked_mp4(sid,asset,{"clip":asset["file"]},job,probe)
        if (media["asset_sha256"]!=scene["media"]["asset_sha256"]
                or abs(media["duration_s"]-scene["media"]["duration_s"])>r.TRIM_TOLERANCE
                or media["width"]!=scene["media"]["width"]
                or media["height"]!=scene["media"]["height"]
                or media["has_audio"]!=scene["media"]["has_audio"]):
            raise r.ContractError("PRIVATE_MEDIA_SOURCE_CHANGED",scene_id=sid)
        checked.append((index,scene,asset,path,media,size))
    evidence={
        "schema":"bontours.motionlab.private-analysis-bundle/v2",
        "source_schema":v2.MATERIALS,
        "project_id":materials["project_id"],
        "request_id":materials["request_id"],
        "materials_sha256":v2.digest(materials),
        "analysis_status":"NOT_YET_REVIEWED_BY_MOTIONLAB",
        "content_access":"owner_private_manual_delivery_only",
        "media":[],
    }
    old_umask=os.umask(0o077)
    try:
        # Mode x forbids quietly overwriting a previously delivered package.
        with zipfile.ZipFile(output,"x",allowZip64=True) as archive:
            archive.writestr("materials.launch.v2.json",
                             v2.canonical(materials),compress_type=zipfile.ZIP_DEFLATED)
            for index,scene,asset,path,media,size in checked:
                video=f"originals/scene-{index:02d}.mp4"
                sheet=f"contact-sheets/scene-{index:02d}.png"
                sheet_raw, times=_contact_sheet(path,media["duration_s"])
                archive.write(path,arcname=video,compress_type=zipfile.ZIP_STORED)
                archive.writestr(sheet,sheet_raw,compress_type=zipfile.ZIP_DEFLATED)
                evidence["media"].append({
                    "scene_id":scene["scene_id"],"asset_id":scene["asset_id"],
                    "video_file":video,
                    "video_sha256":asset["sha256"],"video_bytes":size,
                    "duration_s":media["duration_s"],
                    "sheet_file":sheet,
                    "sheet_sha256":hashlib.sha256(sheet_raw).hexdigest(),
                    "source_frame_seconds":times,
                })
            archive.writestr("analysis-evidence.json",v2.canonical(evidence),
                             compress_type=zipfile.ZIP_DEFLATED)
        os.chmod(output,0o600)
        # Reopen, CRC-verify every member, and compare the original bytes.
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise r.ContractError("PRIVATE_BUNDLE_VERIFICATION_FAILED")
            for row in evidence["media"]:
                h=hashlib.sha256(archive.read(row["video_file"])).hexdigest()
                if h!=row["video_sha256"]:
                    raise r.ContractError("PRIVATE_BUNDLE_VERIFICATION_FAILED")
        return {
            "status":"PRIVATE_MOTIONLAB_ANALYSIS_BUNDLE_CREATED_NOT_DELIVERED",
            "source_project_id":materials["project_id"],
            "scene_count":len(evidence["media"]),
            "bundle_sha256":sha_file(output),
            "materials_sha256":evidence["materials_sha256"],
            "private_output":str(output),
            "analysis_performed":False,
            "delivered_to_other_chat":False,
            "paid_calls":0,"render_started":False,
        }
    except Exception:
        if output.is_file():
            output.unlink()
        raise
    finally:
        os.umask(old_umask)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--materials",required=True,type=Path)
    p.add_argument("--verified-media",required=True,type=Path)
    p.add_argument("--job",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args(argv)
    # This CLI consumes a previously trusted PRIVATE manifest, not public Wix.
    materials=json.loads(args.materials.read_text(encoding="utf-8"))
    media=json.loads(args.verified_media.read_text(encoding="utf-8"))
    result=build_private_analysis_bundle(materials,media,args.job,args.output)
    # Never print the private path in a public GitHub Action log. Caller chose it.
    print(json.dumps({k:v for k,v in result.items() if k!="private_output"},
                     ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
