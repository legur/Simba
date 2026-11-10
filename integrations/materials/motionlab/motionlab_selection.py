#!/usr/bin/env python3
"""Validate Motion Lab interactive edit-choice return against the initiating launch.

Pure read-only validator. Does NOT write project.json, assert approval, or dispatch work.
Intended for use by the trusted autonomous agent after a user selection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA_LAUNCH = "bontours.motionlab.storyboard.launch/v1"
SCHEMA_SELECTION = "bontours.motionlab.storyboard.selection/v1"
CAMERAS = set("cinematic-zoom dolly-zoom orbit focus-pull pan tilt parallax push-through roll float reveal speed-ramp".split())
TRANSITIONS = set("crossfade push zoom whip circle diagonal flash blur flip parallax shutter glitch split rotate tiles portal textmask lightleak speedramp particles ripple map postcard filmstrip pagecurl luma foreground mask morph match none".split())
TITLE_FX = set("none fade-rise soft-zoom blur-focus mask-up light-sweep slide-left bounce-pop punch-zoom rotate-in word-cascade counter date-flip line-draw badge-reveal letter-wave".split())
SUBTITLE_STYLES = set("none clean soft-shadow capsule bar outline two-line cinema letterbox editorial spotlight glow price-tag offer-pill gold-card gradient-bar countdown word-focus karaoke pop marker luxury glass neon travel-stamp".split())
WORD_MOTIONS = set("karaoke active-pop caption-swap highlight-strip word-reveal".split())
GUARDS = ("run_render", "run_tts", "run_a2e", "run_paid_operations", "auto_publish")


class InvalidSelection(ValueError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidSelection(message)


def validate(launch: dict, choice: dict) -> dict:
    """Fail closed when a source or a creative decision changes unexpectedly."""
    need(isinstance(launch, dict) and launch.get("schema") == SCHEMA_LAUNCH, "invalid launch schema")
    need(isinstance(choice, dict) and choice.get("schema") == SCHEMA_SELECTION, "invalid selection schema")
    need(launch.get("stage") == choice.get("stage") == "edit_choice", "stage must be edit_choice")
    need(launch.get("request_id") == choice.get("request_id") and isinstance(launch.get("request_id"), str), "request ID mismatch")
    need(launch.get("project_id") == choice.get("project_id") and isinstance(launch.get("project_id"), str), "project ID mismatch")
    fingerprint = launch.get("expected_input_fingerprint")
    need(isinstance(fingerprint, str) and len(fingerprint) == 64 and all(c in "0123456789abcdefABCDEF" for c in fingerprint), "bad source fingerprint")
    need(choice.get("expected_input_fingerprint") == fingerprint, "stale source fingerprint")
    original_scenes = launch.get("scenes")
    need(isinstance(original_scenes, list) and 1 <= len(original_scenes) <= 24, "launch scenes invalid")
    original = {row.get("scene_id") or row.get("id"): row for row in original_scenes if isinstance(row, dict)}
    need(len(original) == len(original_scenes) and all(isinstance(i, str) and i for i in original), "launch scene IDs invalid")
    options = launch.get("options")
    need(isinstance(options, list) and len(options) == 3 and all(isinstance(x, dict) for x in options), "exactly three choices required")
    decision = choice.get("decision")
    need(isinstance(decision, dict), "missing decision")
    need(type(decision.get("selected_option")) is int and decision["selected_option"] in (1, 2, 3), "selected option must be 1, 2, 3")
    need(decision.get("options_presented") == 3, "options presented must equal three")
    need(decision.get("state") == "USER_SELECTED_IN_CONNECTED_SESSION", "selection is an offline draft, not a delivered approval")
    need(isinstance(decision.get("user_selected_at"), str) and decision["user_selected_at"], "selection timestamp is missing")
    need(choice.get("format") in ("9:16", "1:1", "16:9"), "unknown video format")
    guards = choice.get("guards")
    need(isinstance(guards, dict), "missing execution guards")
    need(all(guards.get(k) is False for k in GUARDS), "selection must not authorize execution or publishing")
    need(guards.get("preserve_approved_voice") is True and guards.get("preserve_approved_music") is True and guards.get("preserve_approved_narration") is True, "approved content locks missing")
    rows = choice.get("scenes")
    need(isinstance(rows, list) and len(rows) == len(original), "unexpected addition or removal of approved scenes")
    seen = set()
    for ix, scene in enumerate(rows):
        need(isinstance(scene, dict), "scene must be an object")
        scene_id = scene.get("scene_id")
        need(isinstance(scene_id, str) and scene_id in original and scene_id not in seen, "unknown or duplicate scene ID")
        seen.add(scene_id)
        need(type(scene.get("order")) is int and scene["order"] == ix + 1, "incorrect scene order")
        need(isinstance(scene.get("name"), str) and scene["name"].strip(), "scene name missing")
        duration = scene.get("duration_seconds")
        need(type(duration) in (int, float) and 1 <= duration <= 20, "scene duration outside 1-20s")
        source_asset = original[scene_id].get("asset_id") or original[scene_id].get("asset_ref") or None
        need(scene.get("asset_id") == source_asset and bool(source_asset), "approved source asset changed or absent")
        camera = scene.get("camera")
        need(isinstance(camera, dict) and camera.get("id") in CAMERAS, "invalid camera ID")
        need(type(camera.get("intensity_percent")) in (int, float) and 0 <= camera["intensity_percent"] <= 100, "invalid camera intensity")
        transition = scene.get("transition")
        if ix == 0:
            need(transition is None, "first scene has no incoming transition")
        else:
            need(isinstance(transition, dict) and transition.get("id") in TRANSITIONS, "invalid transition")
            need(type(transition.get("duration_ms")) is int and 400 <= transition["duration_ms"] <= 2400, "transition duration invalid")
        title = scene.get("title")
        need(isinstance(title, dict) and title.get("effect_id") in TITLE_FX and isinstance(title.get("display_text"), str), "invalid title effect")
        subtitles = scene.get("subtitles")
        need(isinstance(subtitles, dict) and subtitles.get("style_id") in SUBTITLE_STYLES and subtitles.get("word_motion_id") in WORD_MOTIONS, "invalid subtitles")
    need(choice.get("next_stage") == "MONTAGE_PLANNING_REVIEW", "next stage may only be montage planning review")
    # A receipt binds an accepted selection to exactly these source-pinned bytes.
    canonical = json.dumps(choice, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "accepted": True,
        "receipt_id": "motionlab:" + hashlib.sha256(canonical).hexdigest(),
        "project_id": choice["project_id"],
        "request_id": choice["request_id"],
        "selected_option": decision["selected_option"],
        "scene_count": len(rows),
        "scope": "edit_choice_only",
        "status": "SELECTION_VALIDATED_NOT_DISPATCHED",
        "auto_dispatched": False,
        "paid_operations_authorized": False,
        "publication_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch", required=True, type=Path)
    parser.add_argument("--selection", required=True, type=Path)
    args = parser.parse_args()
    try:
        received = validate(json.loads(args.launch.read_text(encoding="utf-8")), json.loads(args.selection.read_text(encoding="utf-8")))
        print(json.dumps(received, indent=2, ensure_ascii=False))
        return 0
    except (OSError, json.JSONDecodeError, InvalidSelection) as exc:
        print(json.dumps({"accepted": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())