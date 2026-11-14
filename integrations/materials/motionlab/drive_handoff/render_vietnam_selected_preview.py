#!/usr/bin/env python3
"""Free source-pinned visual-only preview for the saved Vietnam/Cambodia Studio selection.

This is NOT the restricted production auto_render.py. It never produces a
release master, approves narration/music, publishes or calls a paid API.
It retains the exact 10 source videos and the user's selected effects.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import issue_ticket
import notify_montage

PROJECT = "vietnam-cambodia-2027"
LAUNCH = "14Ue0D5xyZCqPNVHSpOLnX4aNVtDKFIXO"
RECEIPT = "1-2BFlzjHdiqhVskR5ooCDP164SRwfzSd"
MEDIA = "1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj"
ARCHIVE = "14ZYeTB6a7Qd1K11npIdlwPGFYlcvdFvi"
FILENAME = "VietCamb_option2_visual_preview_NO_AUDIO_0847854b1353.mp4"
N, FPS, W, H, D, OVERLAP = 10, 24, 540, 960, 122/24, .9


class PreviewError(RuntimeError):
    pass


def require(ok, code):
    if not ok:
        raise PreviewError(code)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for data in iter(lambda: f.read(1024*1024), b""):
            h.update(data)
    return h.hexdigest()


def check(cmd, code, timeout=220):
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if proc.returncode:
        raise PreviewError(code)


def fp(path):
    proc = subprocess.run(["ffprobe", "-v", "error", "-of", "json",
        "-show_entries", "format=duration,size:stream=codec_type,width,height,avg_frame_rate",
        str(path)], capture_output=True, timeout=30)
    require(proc.returncode == 0, "FFPROBE_FAILED")
    return json.loads(proc.stdout)


def read_project(drive):
    record = notify_montage.validate(drive, RECEIPT)
    launch = issue_ticket.read_approved_launch(drive, LAUNCH)
    require(record.get("project_id") == PROJECT == launch.get("project_id"), "PROJECT_CHANGED")
    require(record.get("source_fingerprint") == launch.get("expected_input_fingerprint"),
            "SOURCE_FINGERPRINT_MISMATCH")
    selected = record["selection"]
    require(record.get("selection_sha256") ==
            "0847854b1353655904fc5459ef5b65e54c5739b33b2adf45daf47ebcbccebf10",
            "USER_SELECTION_CHANGED")
    require(record.get("receipt_id") == "14481802-0761-4ebd-bfbb-886a52f5f524",
            "RECEIPT_CHANGED")
    require(selected["decision"]["selected_option"] == 2, "OWNER_OPTION_CHANGED")
    require(selected["guards"]["run_render"] is False and
            selected["guards"]["auto_publish"] is False, "PREVIEW_SAFETY_GUARD")
    require(len(selected["scenes"]) == len(launch["scenes"]) == len(launch["preview_assets"]) == N,
            "SCENE_COUNT_CHANGED")
    require(selected["visual_draft"]["schema"] ==
            "bontours.motionlab.visual-layout-draft/v2", "VISUAL_DRAFT_MISSING")
    by_asset = {a["asset_id"]: a for a in launch["preview_assets"]}
    require(len(by_asset) == N, "ASSET_MANIFEST_INVALID")
    layouts = {x["scene_id"]: x for x in selected["visual_draft"]["scene_layout"]}
    require(len(layouts) == N, "VISUAL_LAYOUT_COUNT_CHANGED")
    for n, (scene, base) in enumerate(zip(selected["scenes"], launch["scenes"]), 1):
        require(scene["scene_id"] == base["scene_id"] == "s%02d" % n and
                scene["asset_id"] == base["asset_id"] and
                scene["title"]["display_text"] == base["title_text"] and
                scene["subtitles"]["preview_text"] == base["subtitle_preview"],
                "SOURCE_OR_TEXT_CHANGED")
        require(scene["camera"]["id"] == "cinematic-zoom" and
                scene["camera"]["intensity_percent"] == 20 and
                scene["title"]["effect_id"] == "fade-rise" and
                scene["subtitles"]["style_id"] == "clean" and
                scene["subtitles"]["word_motion_id"] == "karaoke",
                "EFFECTS_CHANGED")
        expected = None if n == 1 else {"id": "flash" if n == 2 else "crossfade",
                                            "duration_ms": 900}
        require(scene["transition"] == expected, "TRANSITION_CHANGED")
        require(abs(scene["duration_seconds"] - 5.0625) < .01, "DURATION_CHANGED")
        a = by_asset[scene["asset_id"]]
        require(a["sha256"] == base["media"]["asset_sha256"] and
                a["mime_type"] == "video/mp4" and a["size_bytes"] < 20*1024*1024,
                "VIDEO_MANIFEST_MISMATCH")
        g = layouts[scene["scene_id"]]
        require(g["title"]["layout"] == {"x": 50, "y": 47, "scale": 100} and
                g["subtitle"]["layout"] == {"x": 50, "y": 82, "scale": 100},
                "TEXT_LAYOUT_CHANGED")
    return record, launch, by_asset


def download(drive, asset, destination):
    fid = asset["file_id"]
    meta = drive.files().get(fileId=fid, fields=
        "id,mimeType,size,parents,trashed,permissions(type,role)").execute(num_retries=2)
    require(not meta.get("trashed") and meta.get("parents") == [MEDIA] and
            meta.get("mimeType") == "video/mp4" and
            int(meta.get("size", 0)) == asset["size_bytes"],
            "PRIVATE_SOURCE_INVALID")
    require(not any(p.get("type") not in ("user",)
            for p in meta.get("permissions", [])), "PRIVATE_SOURCE_SHARED")
    with open(destination, "wb") as stream:
        job = MediaIoBaseDownload(stream, drive.files().get_media(fileId=fid),
                                  chunksize=4*1024*1024)
        done = False
        while not done:
            _, done = job.next_chunk(num_retries=2)
    require(sha(destination) == asset["sha256"], "ORIGINAL_MP4_SHA_MISMATCH")
    require(abs(float(fp(destination)["format"]["duration"]) - 5.0625) < .07,
            "ORIGINAL_MP4_DURATION_CHANGED")


def clock(n):
    cent = round(n*100)
    return f"{cent//360000}:{cent//6000%60:02}:{cent//100%60:02}.{cent%100:02}"


def escaped_text(s):
    return str(s).replace("{", "").replace("}", "").replace("\\", "").replace("\n", " ")


def wrap(s, limit):
    words = s.split()
    lines, line = [], ""
    for word in words:
        nxt = (line + " " + word).strip()
        if len(nxt) > limit and line:
            lines.append(line)
            line = word
        else:
            line = nxt
    if line:
        lines.append(line)
    return r"\N".join(lines[:4])


ASS_HEADER = """[Script Info]
Title: Bon Tours / Vietnam Cambodia Studio exact owner option 2 / visual-only
ScriptType: v4.00+
PlayResX: 540
PlayResY: 960
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Liberation Serif,38,&H00FFFFFF,&H00FFFFFF,&H9C000000,&H8A000000,1,0,0,0,100,100,0,0,1,3,2,5,20,20,20,1
Style: Caption,DejaVu Sans,27,&H00FFFFFF,&H00F1C17B,&HBE000000,&H90000000,1,0,0,0,100,100,0,0,1,2.4,1.5,2,30,30,60,1
Style: Price,DejaVu Sans,32,&H00FFFFFF,&H00FFFFFF,&H99000000,&H70000000,1,0,0,0,100,100,0,0,1,3,2,5,25,25,25,1
Style: Contact,DejaVu Sans,26,&H00FFFFFF,&H00FFFFFF,&H99000000,&H90000000,1,0,0,0,100,100,0,0,1,2,1,2,25,25,35,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def make_ass(selection, path):
    step = D - OVERLAP
    lines = []
    def event(layer, a, b, style, content):
        if b > a:
            lines.append(f"Dialogue: {layer},{clock(a)},{clock(b)},{style},,0,0,0,,{content}")
    for i, scene in enumerate(selection["scenes"]):
        start = i*step
        end = start + (step - .08 if i < N-1 else D-.12)
        title = wrap(escaped_text(scene["title"]["display_text"]), 23)
        event(4, start+.30, min(end, start+3.78), "Title",
              r"{\an5\move(270,469,270,451,0,450)\fad(250,260)}" + title)
        words = escaped_text(scene["subtitles"]["preview_text"]).split()
        groups, group = [], []
        for word in words:
            group.append(word)
            if len(group) >= 5 or sum(map(len, group)) > 29:
                groups.append(group); group = []
        if group:
            groups.append(group)
        if groups:
            part = 3.55/len(groups)
            for j, items in enumerate(groups):
                a = start+.43+j*part
                b = min(end, start+.43+(j+1)*part)
                pace = max(1, round((b-a)*100/len(items)))
                phrase = "".join(r"{\k" + str(pace) + "}" + w + " " for w in items).strip()
                event(5, a, b, "Caption", r"{\an5\pos(270,788)\fad(80,80)}" + phrase)
        if i == 6:
            event(6, start+1, start+3.7, "Price",
                  r"{\an5\pos(270,315)\fad(170,260)}12–29 ЯНВАРЯ 2027")
        if i == 8:
            event(6, start+.75, start+3.7, "Price",
                  r"{\an5\pos(270,316)\fad(180,260)}$4 950  /  1 ЧЕЛ.\N+ $1 030  /  ОДНОМЕСТНЫЙ")
        if i == 9:
            event(6, start+.80, min(start+3.65, end), "Contact",
                  r"{\an5\pos(270,345)\fad(180,230)}BON TOURS\N058-677-8492\N08-996-1127\Nwww.letsgo-world.co.il")
    path.write_text(ASS_HEADER + "\n".join(lines) + "\n", encoding="utf8")


def render(drive, record, launch, assets, work):
    scenes = record["selection"]["scenes"]
    input_dir = work / "input"
    input_dir.mkdir()
    originals = []
    for i, row in enumerate(scenes, 1):
        p = input_dir / ("scene_%02d.mp4" % i)
        download(drive, assets[row["asset_id"]], p)
        originals.append(p)

    normalized = []
    for i, source in enumerate(originals, 1):
        output = work / ("normal_%02d.mp4" % i)
        check(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
               "-i", str(source), "-vf",
               f"fps={FPS},scale=556:989:flags=bicubic,"
               f"crop={W}:{H}:x='(in_w-out_w)*min(t/{D},1)':"
               f"y='(in_h-out_h)*min(t/{D},1)',"
               "format=yuv420p,setsar=1",
               "-t", str(D), "-an", "-c:v", "libx264", "-preset", "ultrafast",
               "-crf", "26", "-threads", "2", "-r", str(FPS),
               "-movflags", "+faststart", str(output)], "NORMALIZATION_FAILED")
        normalized.append(output)

    ass = work / "subtitles.ass"
    make_ass(record["selection"], ass)
    filters = []
    previous = "0:v"
    for i in range(1, N):
        new = "x" + str(i)
        transition = "fadewhite" if i == 1 else "fade"
        offset = round(i*(D-OVERLAP), 5)
        filters.append(
            f"[{previous}][{i}:v]xfade=transition={transition}:duration="
            f"{OVERLAP}:offset={offset}[{new}]")
        previous = new
    safe = str(ass).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
    filters.append(f"[{previous}]ass=filename='{safe}',format=yuv420p[vout]")
    target = work / FILENAME
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]
    for p in normalized:
        cmd.extend(["-i", str(p)])
    cmd.extend(["-filter_complex", ";".join(filters), "-map", "[vout]", "-an",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
                "-profile:v", "high", "-pix_fmt", "yuv420p", "-threads", "4",
                "-r", str(FPS), "-movflags", "+faststart", str(target)])
    check(cmd, "MONTAGE_FFMPEG_FAILED", timeout=240)
    probe = fp(target)
    require(len([s for s in probe["streams"] if s["codec_type"] == "video"]) == 1,
            "OUTPUT_VIDEO_INVALID")
    require(not any(s["codec_type"] == "audio" for s in probe["streams"]),
            "PREVIEW_MUST_NOT_FAKE_APPROVED_AUDIO")
    duration = float(probe["format"]["duration"])
    require(abs(duration - (N*D-(N-1)*OVERLAP)) < .35,
            "OUTPUT_DURATION_INVALID")
    return target, duration


def existing(drive):
    name = FILENAME.replace("'", r"\'")
    q = f"'{ARCHIVE}' in parents and name = '{name}' and trashed = false"
    x = drive.files().list(q=q, fields="nextPageToken,files(id,name,size,md5Checksum,parents,appProperties)",
                          pageSize=50).execute(num_retries=2)
    require(not x.get("nextPageToken"), "DUPLICATE_CHECK_PAGINATION")
    rows = x.get("files", [])
    require(len(rows) <= 1, "AMBIGUOUS_DRIVE_PREVIEW")
    return rows[0] if rows else None


def run(apply):
    drive = issue_ticket.drive()
    record, launch, assets = read_project(drive)
    previous = existing(drive)
    if previous:
        props = previous.get("appProperties") or {}
        require(props.get("receipt_id") == record["receipt_id"] and
                props.get("selection_sha256") == record["selection_sha256"] and
                props.get("preview_only") == "true",
                "EXISTING_FILE_COLLISION")
        return {"status": "ALREADY_ARCHIVED", "private_drive_file_id": previous["id"],
                "preview_only": True, "paid_calls": 0, "published": False}
    with tempfile.TemporaryDirectory(prefix="simba-vn-owner-selected-preview-") as temp:
        output, duration = render(drive, record, launch, assets, Path(temp))
        content_sha = sha(output)
        if not apply:
            return {"status": "PREVIEW_RENDERED_NOT_UPLOADED", "sha256": content_sha,
                    "duration": duration, "preview_only": True, "paid_calls": 0}
        body = {"name": FILENAME, "mimeType": "video/mp4", "parents": [ARCHIVE],
            "description": "Source-verified Studio option 2 silent preview; audio and final render not approved.",
            "appProperties": {
                "receipt_id": record["receipt_id"],
                "selection_sha256": record["selection_sha256"],
                "source_fingerprint": record["source_fingerprint"],
                "sha256": content_sha, "preview_only": "true",
            }}
        try:
            job = drive.files().create(body=body,
                media_body=MediaFileUpload(str(output),mimetype="video/mp4",
                                           resumable=True,chunksize=4*1024*1024),
                fields="id,name,size,parents,md5Checksum,appProperties")
            uploaded = None
            while uploaded is None:
                _, uploaded = job.next_chunk(num_retries=2)
        except Exception:
            possible = existing(drive)
            if possible and (possible.get("appProperties") or {}).get("sha256") == content_sha:
                uploaded = possible
            else:
                raise PreviewError("AMBIGUOUS_DRIVE_UPLOAD_NO_RETRY")
        require(uploaded.get("name") == FILENAME and
                uploaded.get("parents") == [ARCHIVE] and
                uploaded.get("appProperties",{}).get("sha256") == content_sha,
                "UPLOADED_PREVIEW_READBACK_INVALID")
        return {"status": "PREVIEW_ARCHIVED_QA_PASS",
                "private_drive_file_id": uploaded["id"],
                "duration_seconds": duration, "mp4_bytes": output.stat().st_size,
                "sha256": content_sha,
                "original_clips_verified": N, "selected_option": 2,
                "flash_cut": "scene_1_to_scene_2_900ms",
                "remaining_cuts": "crossfade_900ms",
                "subtitle_alignment_status": "UNVERIFIED_NO_AUDIO",
                "preview_only": True, "paid_calls": 0,
                "published": False, "final_master_rendered": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.apply)
        status = 0
    except Exception as exc:
        result = {"status": "PREVIEW_BLOCKED", "error": str(exc)[:120],
                  "paid_calls": 0, "published": False}
        status = 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print("Vietnam selected Studio visual preview:", result["status"])
    raise SystemExit(status)
