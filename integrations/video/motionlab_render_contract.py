#!/usr/bin/env python3
"""Motion Lab v1 -> real Simba video-spec.json, static zero-paid preflight.

Issue #113. This module is owned by Montage integration, NOT Motion Lab UI.

Inputs are an exact connected-session launch/selection, an approved upstream
video-spec template, and a trusted asset-id -> local A2E MP4 binding. It checks
actual local file SHA-256 and ffprobe metadata, renderer ID support, immutable
captions and all source fingerprints before returning a COPY of the spec.
No Gemini/A2E requests, uploads, file changes, renderer execution or paid calls.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
MOTIONLAB = HERE.parent / "materials" / "motionlab"
if str(MOTIONLAB) not in sys.path:
    sys.path.insert(0, str(MOTIONLAB))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import motionlab_selection as selector
import make_video

SHA = re.compile(r"^[0-9a-f]{64}$")
SAFE_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.mp4$")
CAMERA_EFFECTS = frozenset(make_video.MOTIONLAB_CAMERA_EFFECTS)
TITLE_EFFECTS = frozenset(make_video.MOTIONLAB_TITLE_EFFECTS)
TRIM_TOLERANCE = .15
MAX_CLIP_DURATION = 15.0
MAX_SCENES = 8
ARTIFACTS = ("make_video.py", "template/film.js",
             "template/transitions.js", "template/subtitle_styles.js")


class ContractError(ValueError):
    def __init__(self, code: str, *, scene_id: str = "", field: str = "",
                 requested: str = "", support: str = "unsupported"):
        self.code = code
        self.scene_id = scene_id
        self.field = field
        self.requested = requested[:90]
        self.support = support
        super().__init__(code)

    def report(self) -> dict:
        return {
            "status": "BLOCKED_RENDER_PREFLIGHT", "code": self.code,
            "scene_id": self.scene_id, "field": self.field,
            "requested": self.requested, "support": self.support,
            "paid_calls": 0, "render_started": False,
        }


def revision() -> str:
    """Changes when production renderer's capabilities/code change."""
    digest = hashlib.sha256()
    for name in ARTIFACTS:
        data = (HERE / name).read_bytes()
        digest.update(name.encode("utf-8") + b"\0" + data + b"\0")
    return digest.hexdigest()


def renderer_capabilities() -> dict:
    """Complete public, non-sensitive revision-pinned support table."""
    return {
        "schema": "bontours.montage.renderer-capabilities/v1",
        "revision_sha256": revision(),
        "renderer": "make_video.py + template/film.js",
        "max_scenes": MAX_SCENES,
        "max_film_seconds": 60,
        "source": {"kind": "video", "origin": "f2u_a2e", "max_clip_seconds": 15},
        "camera": {
            "renderable": sorted(CAMERA_EFFECTS),
            "preview_only": sorted(selector.CAMERAS - CAMERA_EFFECTS),
            "semantics": "opt_in_post_clip_canvas_2d_motion",
            "intensity_percent": {"min": 0, "max": 100},
        },
        "title_fx": {
            "renderable": sorted(TITLE_EFFECTS),
            "preview_only": sorted(selector.TITLE_FX - TITLE_EFFECTS),
            "scope": "per_scene",
        },
        "transition": {
            "renderable": sorted(make_video.TRANSITIONS),
            "preview_only": sorted(selector.TRANSITIONS - make_video.TRANSITIONS),
            "duration_ms": {"min": 400, "max": 2400},
            "scope": "incoming_scene_only",
        },
        "subtitle": {
            "styles": sorted(make_video.SUBTITLE_STYLES),
            "motions": sorted(make_video.SUBTITLE_MOTIONS),
            "preview_only_styles": sorted(selector.SUBTITLE_STYLES - make_video.SUBTITLE_STYLES),
            "scope": "global_one_style_and_motion_per_film",
        },
        "graphics": {"creative_plan": "demo_only_not_supported"},
        "whisper_word_timing": "renderer_generated_not_editor_provided",
        "trim": "v1_does_not_accept_in_out_changes",
        "publication_authorized": False,
    }


def with_capabilities(launch: dict, verified_media: dict) -> dict:
    """Add optional v1 fields without modifying the original launch/UI.

    verified_media is keyed by source asset_id and comes from Montage's
    verified private A2E archive (not an untrusted browser response).
    """
    if not isinstance(launch, dict) or launch.get("schema") != selector.SCHEMA_LAUNCH:
        raise ContractError("INVALID_LAUNCH")
    outgoing = copy.deepcopy(launch)
    outgoing["renderer_capabilities"] = renderer_capabilities()
    scenes = outgoing.get("scenes")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= MAX_SCENES:
        raise ContractError("INVALID_SCENE_COUNT")
    for scene in scenes:
        if not isinstance(scene, dict) or not scene.get("asset_id"):
            raise ContractError("MISSING_VERIFIED_ASSET")
        binding = verified_media.get(scene["asset_id"])
        if not isinstance(binding, dict):
            raise ContractError("MISSING_VERIFIED_ASSET", scene_id=str(scene.get("scene_id", "")))
        sha = binding.get("sha256")
        duration = binding.get("duration_s")
        if (not isinstance(sha, str) or not SHA.fullmatch(sha)
                or type(duration) not in (int, float)
                or not math.isfinite(duration) or not .5 <= duration <= MAX_CLIP_DURATION):
            raise ContractError("INVALID_SOURCE_METADATA", scene_id=scene.get("scene_id", ""))
        scene["media"] = {"kind": "video", "asset_sha256": sha, "duration_s": float(duration)}
    return outgoing


def _safe_clip(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not SAFE_FILE.fullmatch(name):
        raise ContractError("UNSAFE_LOCAL_MEDIA_PATH", field="clip")
    path = root / name
    if not path.is_file() or path.is_symlink() or path.resolve().parent != root.resolve():
        raise ContractError("MISSING_VERIFIED_ASSET", field="clip")
    return path


def _actual_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _ffprobe(path: Path) -> dict:
    try:
        raw = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height,rotation",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        data = json.loads(raw.stdout)
        videos = [x for x in data["streams"] if x.get("codec_type") == "video"]
        if len(videos) != 1:
            raise ValueError()
        return {
            "duration_s": float(data["format"]["duration"]),
            "width": int(videos[0]["width"]),
            "height": int(videos[0]["height"]),
            "has_audio": any(x.get("codec_type") == "audio" for x in data["streams"]),
        }
    except (OSError, subprocess.SubprocessError, KeyError, ValueError, TypeError):
        raise ContractError("MEDIA_FFPROBE_FAILED", field="clip") from None


def _distinct_options(launch: dict) -> None:
    options = launch.get("options")
    if not isinstance(options, list) or len(options) != 3:
        raise ContractError("THREE_MONTAGE_OPTIONS_REQUIRED")
    names = []
    ids = []
    for o in options:
        if not isinstance(o, dict) or not isinstance(o.get("settings"), dict):
            raise ContractError("THREE_MONTAGE_OPTIONS_REQUIRED")
        name = o.get("name")
        if not isinstance(name, str) or len(name.strip()) < 3:
            raise ContractError("THREE_MONTAGE_OPTIONS_REQUIRED")
        names.append(name.strip().casefold())
        ids.append(json.dumps(o["settings"], sort_keys=True))
    if len(set(names)) != 3 or len(set(ids)) != 3:
        raise ContractError("THREE_DISTINCT_OPTIONS_REQUIRED")


def map_selection_to_spec(
    launch: dict, selection: dict, approved_spec: dict,
    job_dir: Path, verified_media: dict, *, probe=None,
) -> tuple[dict, dict]:
    """Return (unwritten video-spec copy, diagnostics), never run renderer.

    The trusted approved_spec contains the only allowed voice/music, post,
    scenes' lines/say/asr, offer, end, source names, and read-only facts.
    """
    if not isinstance(approved_spec, dict) or not isinstance(verified_media, dict):
        raise ContractError("APPROVED_VIDEO_SPEC_REQUIRED")
    try:
        receipt = selector.validate(launch, selection)
    except (selector.InvalidSelection, TypeError, ValueError, KeyError):
        raise ContractError("MOTIONLAB_SELECTION_INVALID_OR_STALE") from None
    _distinct_options(launch)
    if launch.get("renderer_capabilities") != renderer_capabilities():
        raise ContractError("RENDERER_CAPABILITIES_MISSING_OR_STALE")
    scenes = launch.get("scenes")
    choices = selection.get("scenes")
    originals = approved_spec.get("scenes")
    if (not isinstance(scenes, list) or not isinstance(originals, list)
            or not 1 <= len(scenes) <= MAX_SCENES
            or len(originals) != len(scenes)):
        raise ContractError("SCENE_BINDING_MISMATCH")
    if selection.get("format") != "9:16" or approved_spec.get("size", "1080x1920") != "1080x1920":
        raise ContractError("UNSUPPORTED_RENDER_FORMAT")
    if (not isinstance(approved_spec.get("sourcePost"), str)
            or not approved_spec["sourcePost"]
            or not isinstance(approved_spec.get("end"), dict)
            or not isinstance(approved_spec.get("packageId"), str)
            or not isinstance(approved_spec.get("voice"), dict)
            or not isinstance(approved_spec.get("music"), dict)):
        raise ContractError("APPROVED_VIDEO_SPEC_REQUIRED")
    index = {x.get("scene_id"): (i, x) for i, x in enumerate(scenes)}
    if len(index) != len(scenes):
        raise ContractError("SCENE_BINDING_MISMATCH")
    job_dir = Path(job_dir).resolve()
    new_spec = copy.deepcopy(approved_spec)
    revised_scenes = []
    chosen_styles = set()
    full_duration = 0.0
    probe = probe or _ffprobe
    for selected in choices:
        scene_id = selected["scene_id"]
        if scene_id not in index:
            raise ContractError("SCENE_BINDING_MISMATCH", scene_id=str(scene_id))
        original_index, source = index[scene_id]
        base = originals[original_index]
        asset_id = source.get("asset_id")
        asset = verified_media.get(asset_id)
        if not isinstance(asset, dict) or not isinstance(base, dict):
            raise ContractError("MISSING_VERIFIED_ASSET", scene_id=scene_id)
        if not isinstance(asset.get("sha256"), str) or not SHA.fullmatch(asset["sha256"]):
            raise ContractError("MISSING_VERIFIED_ASSET", scene_id=scene_id)
        if base.get("clip") != asset.get("file"):
            raise ContractError("SOURCE_BINDING_CHANGED", scene_id=scene_id, field="clip")
        path = _safe_clip(job_dir, asset["file"])
        if _actual_sha(path) != asset["sha256"]:
            raise ContractError("MEDIA_SHA256_MISMATCH", scene_id=scene_id)
        info = probe(path)
        duration = info.get("duration_s")
        width = info.get("width")
        height = info.get("height")
        if (type(duration) not in (int, float) or not math.isfinite(duration)
                or not .5 <= duration <= MAX_CLIP_DURATION
                or type(width) is not int or type(height) is not int
                or width <= 0 or height <= 0 or type(info.get("has_audio")) is not bool):
            raise ContractError("MEDIA_FFPROBE_FAILED", scene_id=scene_id)
        if abs(duration - asset.get("duration_s", -1)) > TRIM_TOLERANCE:
            raise ContractError("INVALID_SOURCE_METADATA", scene_id=scene_id, field="duration_s")
        media = source.get("media")
        if (not isinstance(media, dict)
                or media.get("kind") != "video"
                or media.get("asset_sha256") != asset["sha256"]
                or type(media.get("duration_s")) not in (int, float)
                or abs(media["duration_s"] - duration) > TRIM_TOLERANCE):
            raise ContractError("MISSING_OR_INVALID_MEDIA_BINDING", scene_id=scene_id)
        if ("in" in base or "out" in base or
                abs(selected["duration_seconds"] - duration) > TRIM_TOLERANCE):
            raise ContractError("TRIM_REQUIRES_V2", scene_id=scene_id, field="duration_seconds")
        full_duration += duration

        if base.get("title", "") != source.get("title_text", "") or selected["title"]["display_text"] != source.get("title_text", ""):
            raise ContractError("IMMUTABLE_TEXT_CHANGED", scene_id=scene_id, field="title.display_text")
        if selected["subtitles"].get("preview_text", "") != source.get("subtitle_preview", ""):
            raise ContractError("IMMUTABLE_TEXT_CHANGED", scene_id=scene_id, field="subtitles.preview_text")
        if selected["subtitles"].get("timing_source") not in ("NOT_PROVIDED_IN_STORYBOARD", None):
            raise ContractError("UNTRUSTED_WORD_TIMINGS", scene_id=scene_id)

        cam = selected["camera"]
        if cam["id"] not in CAMERA_EFFECTS or cam.get("approximate_3d") is True:
            raise ContractError("UNSUPPORTED_CAMERA_EFFECT", scene_id=scene_id,
                                field="camera.id", requested=str(cam["id"]), support="preview_only")
        title_fx = selected["title"]["effect_id"]
        if title_fx not in TITLE_EFFECTS or (title_fx == "none" and source.get("title_text")):
            raise ContractError("UNSUPPORTED_TITLE_EFFECT", scene_id=scene_id,
                                field="title.effect_id", requested=str(title_fx), support="preview_only")
        style, word = (selected["subtitles"]["style_id"],
                       selected["subtitles"]["word_motion_id"])
        if style not in make_video.SUBTITLE_STYLES or word not in make_video.SUBTITLE_MOTIONS:
            raise ContractError("UNSUPPORTED_SUBTITLE_EFFECT", scene_id=scene_id,
                                field="subtitles.style_id", requested=str(style), support="preview_only")
        chosen_styles.add((style, word))
        if len(chosen_styles) > 1:
            raise ContractError("UNSUPPORTED_PER_SCENE_SUBTITLE", scene_id=scene_id,
                                field="subtitles.style_id")
        updated = copy.deepcopy(base)
        updated["move"] = "none"  # no silent legacy camera motion on an already animated clip
        updated["cameraEffect"] = {
            "id": cam["id"], "intensity_percent": cam["intensity_percent"],
        }
        updated["titleEffect"] = title_fx
        if title_fx == "fade-rise":
            updated["title"] = source.get("title_text", "")
        else:
            updated.pop("title", None)
        trans = selected["transition"]
        if trans is not None:
            if trans["id"] not in make_video.TRANSITIONS:
                raise ContractError("UNSUPPORTED_TRANSITION", scene_id=scene_id,
                                    field="transition.id", requested=str(trans["id"]),
                                    support="preview_only")
            updated["transition"] = {"id": trans["id"], "duration_ms": trans["duration_ms"]}
        else:
            updated.pop("transition", None)
        revised_scenes.append(updated)
    if full_duration > 60:
        raise ContractError("VIDEO_DURATION_LIMIT_EXCEEDED", field="scenes")
    new_spec["scenes"] = revised_scenes
    style, motion = next(iter(chosen_styles))
    # Preserve renderer-legal approved global colors/scale if present.
    existing = approved_spec.get("subtitleStyle") or {}
    if not isinstance(existing, dict):
        raise ContractError("INVALID_APPROVED_SUBTITLE")
    new_spec["subtitleStyle"] = {
        "style": style, "motion": motion,
        "color": existing.get("color", "gold"),
        "position": existing.get("position", "bottom"),
        "scale_percent": existing.get("scale_percent", 100),
    }
    # Strictly refuse any unrepresentable global subtitle config.
    if (new_spec["subtitleStyle"]["color"] not in make_video.SUBTITLE_COLORS
            or new_spec["subtitleStyle"]["position"] not in make_video.SUBTITLE_POSITIONS
            or type(new_spec["subtitleStyle"]["scale_percent"]) is not int
            or not 80 <= new_spec["subtitleStyle"]["scale_percent"] <= 135):
        raise ContractError("INVALID_APPROVED_SUBTITLE")
    # No executable output until a separate verified existing approved WAV and
    # TOTAL duration/QA preflight. make_video --plan-only can call paid TTS.
    diagnostic = {
        "status": "VIDEO_SPEC_MAPPED_NOT_RENDERED",
        "request_id": receipt["request_id"],
        "selection_receipt_id": receipt["receipt_id"],
        "selected_option": receipt["selected_option"],
        "renderer_revision_sha256": revision(),
        "scene_count": len(revised_scenes),
        "verified_video_seconds": round(full_duration, 3),
        "remaining_seconds_for_cards_and_voice": round(60-full_duration, 3),
        "video_spec_ready_for_static_review": True,
        "preapproved_wav_reuse_verified": False,
        "total_timeline_verified": False,
        "paid_calls": 0, "render_started": False,
        "render_authorized": False,
        "publication_authorized": False,
    }
    return new_spec, diagnostic
