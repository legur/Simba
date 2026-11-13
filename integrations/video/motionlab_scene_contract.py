"""One authoritative bounded scene-count contract for Studio ↔ Montage.

Scene count is independent of how many *unique* A2E originals are reused.
Editors and the Apps Script receiver mirror this constant; CI requires parity.
No default per-project scene count, no rendering/paid operations here.
"""
from __future__ import annotations

MIN_SCENES = 1
MAX_SCENES = 24
MAX_FILM_SECONDS = 60
MAX_UNIQUE_SOURCE_MP4 = 24
MAX_SOURCE_MP4_BYTES = 20 * 1024 * 1024
MAX_TOTAL_SOURCE_MP4_BYTES = 120 * 1024 * 1024


def validate_scene_count(scenes: object) -> int:
    if not isinstance(scenes, list) or not MIN_SCENES <= len(scenes) <= MAX_SCENES:
        raise ValueError("INVALID_SCENE_COUNT")
    return len(scenes)


def transitions_for_scene_count(count: int) -> int:
    if type(count) is not int or not MIN_SCENES <= count <= MAX_SCENES:
        raise ValueError("INVALID_SCENE_COUNT")
    return count - 1
