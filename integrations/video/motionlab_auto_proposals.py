#!/usr/bin/env python3
"""Generate three factual montage variants by sampling real SHA-verified MP4 pixels.

No model, paid calls, false semantic labels, render, user selection or publish.
This measures brightness/contrast/motion across each original clip's timeline.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import subprocess

import motionlab_render_contract as renderer
import motionlab_v2_contract as v2

ALGORITHM = "full_timeline_sampled_pixels_ffmpeg_v1"
FPS = 3
WIDTH, HEIGHT = 48, 48
FRAME_BYTES = WIDTH * HEIGHT
MAX_FRAMES = 47
MAX_RAW = FRAME_BYTES * MAX_FRAMES


def reject(code, scene=""):
    raise renderer.ContractError(code, scene_id=scene)


def measure_original(scene: dict, asset: dict, private_root: Path) -> dict:
    sid = scene["scene_id"]
    if (not isinstance(asset, dict) or sid != asset.get("scene_id")
            or scene.get("asset_id") != asset.get("asset_id")):
        reject("AUTOMATIC_ANALYSIS_SOURCE_BINDING_CHANGED", sid)
    video = renderer._safe_clip(private_root, asset.get("file"))
    # Read the full source file for SHA-256, then decode uniformly spaced frames
    # across the original timeline. Do not trust browser metadata.
    actual = v2.checked_mp4(sid, asset, {"clip": asset["file"]},
                            private_root, renderer._ffprobe)
    if actual != scene["media"]:
        reject("AUTOMATIC_ANALYSIS_MEDIA_CHANGED", sid)
    try:
        process = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
             "-i", str(video), "-an", "-sn", "-dn",
             "-vf", f"fps={FPS},scale={WIDTH}:{HEIGHT}:flags=area,format=gray",
             "-frames:v", str(MAX_FRAMES),
             "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            check=True, capture_output=True, timeout=40)
    except (OSError, subprocess.SubprocessError):
        reject("AUTOMATIC_ANALYSIS_VIDEO_DECODE_FAILED", sid)
    raw = process.stdout
    if (not raw or len(raw) > MAX_RAW or len(raw) % FRAME_BYTES
            or len(raw) // FRAME_BYTES < max(5, int(actual["duration_s"] * 2.2))):
        reject("AUTOMATIC_ANALYSIS_INSUFFICIENT_REAL_FRAMES", sid)
    frames = [memoryview(raw)[i:i+FRAME_BYTES]
              for i in range(0, len(raw), FRAME_BYTES)]
    brightness = sum(raw) / len(raw)
    mean_contrast = sum(
        math.sqrt(sum((pixel - (sum(frame) / FRAME_BYTES)) ** 2
                      for pixel in frame) / FRAME_BYTES)
        for frame in frames
    ) / len(frames)
    diffs = [
        sum(abs(a-b) for a,b in zip(left,right)) / FRAME_BYTES
        for left,right in zip(frames[:-1],frames[1:])]
    motion = sum(diffs)/len(diffs)
    last_sample_s = round((len(frames)-1)/FPS, 3)
    if last_sample_s < actual["duration_s"] - 1.0:
        reject("AUTOMATIC_ANALYSIS_TIMELINE_INCOMPLETE", sid)
    return {
        "scene_id": sid,
        "asset_sha256": actual["asset_sha256"],
        "sampled_frame_sha256": hashlib.sha256(raw).hexdigest(),
        "frames_sampled": len(frames),
        "sample_rate_fps": FPS,
        "first_sample_s": 0.0,
        "last_sample_s": last_sample_s,
        "mean_luminance": round(brightness, 3),
        "mean_contrast": round(mean_contrast, 3),
        "motion_delta": round(motion, 3),
        "peak_frame_delta": round(max(diffs), 3),
    }


def effects(variant: int, sources: list[dict], evidence: list[dict]) -> list[dict]:
    result = []
    for i, src in enumerate(sources):
        busy = evidence[i]["motion_delta"] > 12
        if variant == 1:
            cam, pct = ("float", 18) if busy else ("cinematic-zoom", 29)
            transition, duration, motion = "crossfade", 1100, "karaoke"
        elif variant == 2:
            cam, pct = ("cinematic-zoom", 25) if busy else ("push-through", 46)
            transition, duration, motion = "whip", 600, "active-pop"
        else:
            cam, pct = "float", 15
            transition, duration, motion = "crossfade", 1500, "word-reveal"
        result.append({
            "scene_id": src["scene_id"],
            "camera": {"id": cam, "intensity_percent": pct},
            "transition": None if i == 0 else {"id": transition, "duration_ms": duration},
            "title_fx": "fade-rise" if src["locked"]["title_text"].strip() else "none",
            "subtitle": {"style_id": "clean", "word_motion_id": motion},
        })
    return result


def build_automated_proposals(materials: dict, verified_media: list[dict],
                              private_job: Path) -> tuple[dict, dict]:
    """The trusted private worker must compute and later recheck these results."""
    v2.validate_materials(materials)
    if (not isinstance(verified_media, list)
            or not verified_media
            or len(verified_media) > v2.r.MAX_SCENES):
        reject("AUTOMATIC_ANALYSIS_MISSING_MEDIA")
    folder = Path(private_job)
    if folder.is_symlink() or not folder.is_dir():
        reject("AUTOMATIC_ANALYSIS_PRIVATE_DIRECTORY_INVALID")
    folder = folder.resolve()
    # The true A2E archive stores each file once. One clip may appear several
    # times on the approved timeline (Alaska has 10 scenes from 7 MP4s).
    if len(verified_media)==len(materials["scenes"]) and all(
       a.get("scene_id")==s["scene_id"] and a.get("asset_id")==s["asset_id"]
       for s,a in zip(materials["scenes"],verified_media)):
        per_scene=verified_media
    else:
        by_id={}
        for a in verified_media:
            if (not isinstance(a,dict) or not isinstance(a.get("asset_id"),str)
                    or a["asset_id"] in by_id):
                reject("AUTOMATIC_ANALYSIS_DUPLICATE_OR_MISSING_SOURCE")
            by_id[a["asset_id"]]=a
        per_scene=[]
        for s in materials["scenes"]:
            source=by_id.get(s["asset_id"])
            if source is None:
                reject("AUTOMATIC_ANALYSIS_MISSING_MEDIA",s["scene_id"])
            per_scene.append({**source,"scene_id":s["scene_id"]})
        if set(by_id)!={s["asset_id"] for s in materials["scenes"]}:
            reject("AUTOMATIC_ANALYSIS_UNUSED_SOURCE")
    cache={}
    evidence=[]
    for scene,asset in zip(materials["scenes"],per_scene):
        key=(asset["asset_id"],asset.get("sha256"),asset.get("file"))
        if key not in cache:
            cache[key]=measure_original(scene,asset,folder)
        evidence.append({**cache[key],"scene_id":scene["scene_id"]})
    mean_motion = sum(row["motion_delta"] for row in evidence)/len(evidence)
    mean_contrast = sum(row["mean_contrast"] for row in evidence)/len(evidence)
    winner = 1 if mean_motion < 14 else 3
    summaries = [
        ("Кинематографичный", "Плавные переходы и умеренное движение камеры по проверенной серии."),
        ("Энергичный", "Быстрые переходы и движение камеры с поправкой на подвижные клипы."),
        ("Информационный", "Сдержанное движение, длинные переходы и последовательное выделение слов."),
    ]
    variants = [{
        "option": n, "title": title,
        "rationale": (f"{explanation} Анализ {len(evidence)} исходных MP4: "
                      f"среднее движение {mean_motion:.2f}/255, "
                      f"контраст {mean_contrast:.2f}/255. "
                      "Объекты, география и сюжет автоматически не распознавались."),
        "recommended": n == winner,
        "scenes": effects(n, materials["scenes"], evidence)
    } for n, (title, explanation) in enumerate(summaries, 1)]
    proposed = {
        "schema": v2.PROPOSALS,
        "project_id": materials["project_id"],
        "request_id": materials["request_id"],
        "expected_input_fingerprint": materials["expected_input_fingerprint"],
        "materials_sha256": v2.digest(materials),
        "renderer_revision_sha256": materials["renderer_capabilities"]["revision_sha256"],
        "analysis": {
            "status": "REAL_VIDEO_AUTOMATICALLY_ANALYZED",
            "access_mode": "owner_private_material_bundle",
            "analysis_method": ALGORITHM,
            "review_notes": (
                "Выполнен численный видеоанализ кадров по всей временной шкале "
                "каждого оригинального MP4 с проверенным SHA-256. "
                "Измерялись яркость, контраст и движение. "
                "Смысл изображения и места съемки не определялись."),
            "pixel_evidence": evidence,
            "inspected_assets": [{
                "scene_id": row["scene_id"],
                "asset_sha256": row["asset_sha256"],
                "evidence_kind": "full_original_mp4",
                "scene_notes": (
                    f"SHA-проверенный исходный MP4, {row['frames_sampled']} "
                    f"декодированных кадров по шкале клипа; "
                    f"движение {row['motion_delta']:.2f}, "
                    f"яркость {row['mean_luminance']:.2f}, "
                    f"контраст {row['mean_contrast']:.2f}. "
                    "Без семантического распознавания объектов.")
            } for row in evidence],
        },
        "proposals": variants
    }
    v2.validate_proposals_v2(materials, proposed)
    return proposed, {
        "status": "THREE_REAL_VIDEO_AUTOMATED_PROPOSALS_NOT_OWNER_SELECTED",
        "proposals_sha256": v2.digest(proposed),
        "source_clip_count": len(cache),
        "scene_count": len(evidence),
        "frames_decoded": sum(row["frames_sampled"] for row in cache.values()),
        "semantic_review_performed": False,
        "paid_calls": 0,
        "render_authorized": False,
        "publication_authorized": False,
    }
