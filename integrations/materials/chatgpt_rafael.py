#!/usr/bin/env python3
"""ChatGPT Rafael file adapter, not an external-image or unattended agent.

ChatGPT creates image files using the native image tool. This adapter verifies
the upstream script handoff and packages externally supplied real image bytes
for human review. It NEVER calls a paid API, infers Leo's selection, or publishes.
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

import catalog
import handoff

STYLES = (
    "Атмосферная история",
    "Архитектурное путешествие",
    "Динамичный трейлер",
)
EXPECTED_IMAGES = 9
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SHA = re.compile(r"^[a-f0-9]{64}$")


class RafaelError(ValueError):
    pass


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validated_stage(root: Path, pid: str) -> tuple[dict, str]:
    if not ID.fullmatch(pid):
        raise RafaelError("invalid project ID")
    path = catalog.inside(root, f"campaigns/{pid}/project.json")
    project = json.loads(path.read_text(encoding="utf-8"))
    state = handoff.make_handoff(root, path, project)
    packet = state.get("packet") or {}
    stage = (project.get("stage_handoffs") or {}).get("script") or {}
    if (project.get("id") != pid
            or state.get("state") != "READY_FOR_HANDOFF"
            or state.get("recipient") != "RAFAEL"
            or packet.get("next_stage") != "storyboard"
            or not SHA.fullmatch(packet.get("receipt_sha256", ""))
            or stage.get("state") != "approved"
            or stage.get("selected_option") not in (1, 2, 3)
            or not stage.get("approval_evidence")):
        raise RafaelError("Rafael is not authorized by an approved script handoff")
    return project, packet["receipt_sha256"]


def prompt_set() -> list[dict]:
    """Visual differences are creative instructions, never claims of execution."""
    approaches = (
        ("Живая прогулка", "Теплый естественный свет, человеческий масштаб, "
         "детали улиц и неспешное повествование."),
        ("Город через архитектуру", "Геометричные общие планы, исторические "
         "формы, выразительная симметрия."),
        ("Энергия путешествия", "Контраст масштабов, необычные ракурсы, "
         "быстрая визуальная смена впечатлений."),
    )
    return [{"option": n, "title": title, "visual_approach": approach,
             "requirements": "3 последовательных кадра 9:16 без текста и логотипов; "
             "связать с утвержденными фразами сценария; не добавлять коммерческих данных",
             "generator": "ChatGPT native image generation ONLY"}
            for n, (title, approach) in enumerate(approaches, 1)]


def _picture(path: Path) -> tuple[bytes, dict]:
    try:
        from PIL import Image, ImageOps
        data = path.read_bytes()
        if len(data) < 200 or len(data) > 12_000_000:
            raise RafaelError("image size out of allowed bounds")
        with Image.open(io.BytesIO(data)) as item:
            item.load()
            if item.width < 500 or item.height < 500:
                raise RafaelError("real image dimensions below minimum")
            im = ImageOps.exif_transpose(item).convert("RGB")
            resized = ImageOps.fit(im, (720, 1280), method=Image.Resampling.LANCZOS)
        output = io.BytesIO()
        resized.save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue(), {
            "input_sha256": sha_bytes(data), "input_dimensions": [im.width, im.height],
            "output_dimensions": [720, 1280], "crop": "center-crop from ChatGPT image",
            "input_format": path.suffix.lower(),
        }
    except (OSError, SyntaxError):
        raise RafaelError("cannot decode image bytes") from None


def _board(images: list[bytes], title: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    sheet = Image.new("RGB", (3 * 360 + 40, 740), "#f4f2ee")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 12), title, font=font, fill="#17202d")
    for index, photo in enumerate(images):
        with Image.open(io.BytesIO(photo)) as im:
            im.thumbnail((350, 622))
            sheet.paste(im, (20 + index * 360, 55))
        draw.text((20 + index * 360, 685), f"Сцена {index + 1}",
                  font=font, fill="#17202d")
    output = io.BytesIO()
    sheet.save(output, "PNG", optimize=True)
    return output.getvalue()


def package(root: Path, pid: str, frames: Path, output: Path, *, provenance: dict) -> dict:
    """Actual file bytes required; no scenario is approved by this function."""
    project, receipt = validated_stage(root, pid)
    if provenance.get("source") != "CHATGPT_IMAGE_TOOL":
        raise RafaelError("ChatGPT render evidence required")
    if not isinstance(provenance.get("session_evidence"), str) or not provenance["session_evidence"].strip():
        raise RafaelError("missing ChatGPT generation/session evidence")
    images, options, seen = {}, [], set()
    for index, title in enumerate(STYLES, 1):
        scenes, variants = [], []
        for scene in range(1, 4):
            path = frames / f"option_{index}" / f"scene_{scene}.png"
            if not path.is_file():
                raise RafaelError("missing real image: " + str(path.relative_to(frames)))
            value, info = _picture(path)
            if info["input_sha256"] in seen:
                raise RafaelError("reused image bytes across scenes; distinct render required")
            seen.add(info["input_sha256"])
            name = f"option_{index}/scene_{scene}.jpg"
            images[name] = value
            scenes.append({"scene": scene, "image": name,
                           "image_sha256": sha_bytes(value), **info})
            variants.append(value)
        board = _board(variants, title)
        name = f"option_{index}/preview.png"
        images[name] = board
        options.append({"option": index, "title": title,
                        "preview": name, "preview_sha256": sha_bytes(board),
                        "scenes": scenes})
    if len(seen) != EXPECTED_IMAGES:
        raise RafaelError("expected nine distinct images")
    manifest = {
        "schema_version": 1, "project_id": pid, "stage": "storyboard",
        "input_receipt": receipt, "selected_script_option": project["stage_handoffs"]["script"]["selected_option"],
        "status": "STORYBOARD_OPTIONS_NEED_LEO",
        "generation_evidence": provenance,
        "options": options, "original_image_count": EXPECTED_IMAGES,
        "approval_recorded": False, "archive_verified": False,
        "paid_calls_from_adapter": 0, "published": False,
        "warning": "Technical pixel verification only. Creative QA and true model provenance require human review.",
    }
    images["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    if output.exists():
        raise RafaelError("refuse overwrite of existing archive")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in images.items():
            archive.writestr(name, payload)
    with zipfile.ZipFile(output) as check:
        for item in check.infolist():
            if check.read(item.filename) != images[item.filename]:
                raise RafaelError("ZIP roundtrip failed")
    return {"status": "STORYBOARD_OPTIONS_NEED_LEO", "project_id": pid,
            "input_receipt": receipt, "storyboard_options": 3,
            "verified_distinct_input_images": EXPECTED_IMAGES,
            "verified_previews": 3, "archive_local_sha256": sha_bytes(output.read_bytes()),
            "archive_verified_on_private_drive": False,
            "approved": False, "paid_api_calls": 0, "published": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--project", required=True)
    parser.add_argument("--frames-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--provenance-json", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        _, receipt = validated_stage(args.root.resolve(), args.project)
        if args.prepare_only:
            result = {"stage": "storyboard", "status": "CHATGPT_RENDER_REQUIRED",
                      "input_receipt": receipt, "options": prompt_set(),
                      "ready_for_a2e": False}
        else:
            if not args.frames_dir or not args.output or not args.provenance_json:
                raise RafaelError("real frames, output and ChatGPT provenance are required")
            provenance = json.loads(args.provenance_json.read_text(encoding="utf-8"))
            result = package(args.root.resolve(), args.project,
                             args.frames_dir, args.output, provenance=provenance)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (RafaelError, ValueError, OSError, KeyError, TypeError,
            json.JSONDecodeError) as exc:
        print("SIMBA_CHATGPT_RAFAEL_BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
