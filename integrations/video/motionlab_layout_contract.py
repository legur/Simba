"""Issue #113: exact WYSIWYG text layout geometry for real Canvas2D renderer.

A public renderer capabilities contract: full frame 9:16, percentages, center
anchor, 72% MAX text wrap width. Pixel positions are never accepted from Wix;
the user's chosen source coordinates are preserved (not silently clamped).
Only per-scene title/subtitle GEOMETRY is editable. Style and word timing stay
film-global; offer/end layout is not yet renderable.
"""
from __future__ import annotations

from copy import deepcopy

SCHEMA = "bontours.montage.visual-layout/v1"
LAYOUT_KEYS = frozenset(("title", "subtitle"))
DEFAULTS = {
    "title": {"x": 50, "y": 47, "scale": 100},
    "subtitle": {"x": 50, "y": 82, "scale": 100},
}
X_MIN, X_MAX = 36, 64
Y_MIN, Y_MAX = 13, 87
SCALE_MIN, SCALE_MAX, SCALE_STEP = 70, 140, 5
WRAP_WIDTH_PERCENT = 72
SAFE_INSET_PERCENT = 6

class LayoutError(ValueError):
    def __init__(self, code: str, scene_id: str = "", field: str = ""):
        self.code, self.scene_id, self.field = code, scene_id, field
        super().__init__(code)


def capabilities() -> dict:
    return {
        "schema": SCHEMA,
        "coordinate_space": "full_frame_percent_9x16",
        "anchor": "center",
        "max_wrap_width_percent": WRAP_WIDTH_PERCENT,
        "safe_inset_percent": SAFE_INSET_PERCENT,
        "position": {"x_min": X_MIN, "x_max": X_MAX,
                     "y_min": Y_MIN, "y_max": Y_MAX},
        "scale": {"min": SCALE_MIN, "max": SCALE_MAX, "step": SCALE_STEP},
        "layers": {
            "title": {"scope": "per_scene_geometry",
                      "defaults": deepcopy(DEFAULTS["title"])},
            "subtitle": {"scope": "per_scene_geometry_only_global_style_motion",
                         "defaults": deepcopy(DEFAULTS["subtitle"])},
        },
        "offer_card": "not_renderable",
        "end_card": "not_renderable",
        "safe_zone_implementation": "exact_center_and_wrap_with_runtime_bbox_fail_closed",
    }


def validate_layer(value: object, scene_id: str, kind: str) -> dict:
    if not isinstance(value, dict) or set(value) != {"x", "y", "scale"}:
        raise LayoutError("UNSUPPORTED_VISUAL_LAYOUT", scene_id, f"{kind}")
    x, y, scale = value["x"], value["y"], value["scale"]
    if (type(x) is not int or type(y) is not int or type(scale) is not int
            or not X_MIN <= x <= X_MAX
            or not Y_MIN <= y <= Y_MAX
            or not SCALE_MIN <= scale <= SCALE_MAX
            or (scale - SCALE_MIN) % SCALE_STEP != 0):
        raise LayoutError("UNSAFE_VISUAL_LAYOUT", scene_id, f"{kind}.x_y_scale")
    return {"x": x, "y": y, "scale": scale}


def validate_scene_layout(value: object, scene_id: str = "") -> dict:
    if not isinstance(value, dict) or set(value) != LAYOUT_KEYS:
        raise LayoutError("UNSUPPORTED_VISUAL_LAYOUT", scene_id, "layout")
    return {
        "title": validate_layer(value["title"], scene_id, "title"),
        "subtitle": validate_layer(value["subtitle"], scene_id, "subtitle"),
    }


def canonical_scene_layouts(items: object, sources: list[dict]) -> list[dict]:
    """Check against original scene order/IDs; forbid foreign scene/asset IDs.

    Mirrors the already-shipped Motion Lab visual-layout-draft/v2 shape.
    Does not promote DRAFT_NOT_DELIVERED into a connected approval.
    """
    if not isinstance(items, list) or len(items) != len(sources):
        raise LayoutError("SCENE_LAYOUT_BINDING_MISMATCH", field="scene_layout")
    result = []
    for index,(item,source) in enumerate(zip(items,sources),1):
        sid=source["scene_id"]
        if (not isinstance(item,dict)
                or set(item)!={"scene_id","asset_id","layout"}
                or item.get("scene_id")!=sid
                or item.get("asset_id")!=source.get("asset_id")):
            raise LayoutError("SCENE_LAYOUT_BINDING_MISMATCH", sid, f"scene_layout[{index}]")
        layout=validate_scene_layout(item["layout"],sid)
        result.append({
            "scene_id":sid,
            "asset_id":source["asset_id"],
            "layout":layout,
        })
    return result
