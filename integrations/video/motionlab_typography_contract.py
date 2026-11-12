"""Motion Lab typography contract: strict, source-bound global theme and scene exceptions.

This validator does not itself approve a Motion Lab draft, load fonts, or
authorize a render. The v2 bridge must carry these values in a connected
owner-approved selection before Montage consumes them.
"""
from __future__ import annotations

import re
from copy import deepcopy

FAMILIES = frozenset(("Unbounded", "Manrope", "Arial", "Georgia"))
COLORS = re.compile(r"^#[0-9a-fA-F]{6}$")
LAYERS = frozenset(("title", "subtitle"))
DEFAULT = {
    "title": {"family": "Unbounded", "color": "#ffffff", "size": 100},
    "subtitle": {"family": "Manrope", "color": "#ffffff", "size": 100},
}


class TypographyError(ValueError):
    def __init__(self, code: str, scene_id: str = "", field: str = ""):
        self.code, self.scene_id, self.field = code, scene_id, field
        super().__init__(f"{code}: {scene_id} {field}".strip())


def validate_style(value: object, scene_id: str = "", kind: str = "") -> dict:
    if not isinstance(value, dict) or set(value) != {"family", "color", "size"}:
        raise TypographyError("INVALID_TYPOGRAPHY", scene_id, kind)
    family, color, size = value["family"], value["color"], value["size"]
    if (type(family) is not str or family not in FAMILIES
            or type(color) is not str or not COLORS.fullmatch(color)
            or type(size) is not int or not 70 <= size <= 140 or size % 5 != 0):
        raise TypographyError("UNSUPPORTED_TYPOGRAPHY", scene_id, kind)
    return {"family": family, "color": color.lower(), "size": size}


def validate_theme(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != LAYERS:
        raise TypographyError("INVALID_GLOBAL_THEME", field="global_theme.typography")
    return {kind: validate_style(value[kind], kind=kind) for kind in ("title", "subtitle")}


def resolve_scenes(theme: object, overrides: object, source_scenes: object) -> list[dict]:
    """Return exact resolved appearance, preserving scene/asset bindings.

    Empty overrides inherit the common style; only title/subtitle overrides are
    allowed. A stale/foreign asset, unknown key, or invalid font blocks output.
    """
    global_theme = validate_theme(theme)
    if (not isinstance(source_scenes, list) or not isinstance(overrides, list)
            or len(overrides) != len(source_scenes)):
        raise TypographyError("TYPOGRAPHY_SOURCE_MISMATCH")
    result = []
    for source, item in zip(source_scenes, overrides):
        if not isinstance(source, dict) or not isinstance(item, dict):
            raise TypographyError("TYPOGRAPHY_SOURCE_MISMATCH")
        sid, aid = source.get("scene_id"), source.get("asset_id")
        if (not isinstance(sid, str) or not isinstance(aid, str)
                or set(item) != {"scene_id", "asset_id", "typography"}
                or item["scene_id"] != sid or item["asset_id"] != aid):
            raise TypographyError("TYPOGRAPHY_SOURCE_MISMATCH", str(sid))
        changed = item["typography"]
        if not isinstance(changed, dict) or not set(changed) <= LAYERS:
            raise TypographyError("INVALID_SCENE_TYPOGRAPHY", sid)
        resolved = deepcopy(global_theme)
        for kind, style in changed.items():
            resolved[kind] = validate_style(style, sid, kind)
        result.append({"scene_id": sid, "asset_id": aid, "typography": resolved})
    return result


def renderer_capability() -> dict:
    """Advertise strict validation, not a false WYSIWYG render guarantee."""
    return {
        "families": sorted(FAMILIES),
        "color": "hex_rgb",
        "size_percent": {"min": 70, "max": 140, "step": 5},
        "global_theme": "validated",
        "scene_overrides": "validated",
        "native_families_ready": ["Arial", "Georgia"],
        "custom_font_files_required": ["Manrope", "Unbounded"],
        "connected_v2_selection": "not_integrated",
        "font_loading_and_visual_parity": "not_verified",
        "render_authorized": False,
    }
