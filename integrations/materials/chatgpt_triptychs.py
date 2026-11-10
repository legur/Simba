#!/usr/bin/env python3
"""Import three ChatGPT-generated triptych storyboards into nine 9:16 scene PNGs.

The importer is media-only: it cannot approve a script, upload to Drive, spend
credits, or create a stage handoff. Use chatgpt_rafael.py after this step.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps


class ImportErrorRafael(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def import_triptychs(inputs: list[Path], output: Path, *, generation_ids: list[str]) -> dict:
    if len(inputs) != 3 or len(generation_ids) != 3 or any(not x.strip() for x in generation_ids):
        raise ImportErrorRafael("three source images and three ChatGPT generation receipts required")
    if output.exists() and any(output.iterdir()):
        raise ImportErrorRafael("refuse to overwrite existing generated scenes")
    if len(set(generation_ids)) != 3:
        raise ImportErrorRafael("repeated ChatGPT generation IDs")
    originals, outputs = [], {}
    hashes = set()
    for option, (path, gen_id) in enumerate(zip(inputs, generation_ids), 1):
        if not path.is_file() or not 200 <= path.stat().st_size <= 15_000_000:
            raise ImportErrorRafael("generated triptych file missing or invalid")
        source_bytes = path.read_bytes()
        try:
            with Image.open(io.BytesIO(source_bytes)) as im:
                im.load()
                if im.width < 1350 or im.height < 420 or not 2.6 <= im.width/im.height <= 3.5:
                    raise ImportErrorRafael("source is not a sufficiently large 3-panel triptych")
                rgb = ImageOps.exif_transpose(im).convert("RGB")
        except OSError:
            raise ImportErrorRafael("source cannot be decoded as an image") from None
        width, height = rgb.size
        originals.append({"option": option, "generation_id": gen_id,
                          "original_file_sha256": sha(source_bytes),
                          "original_dimensions": [width, height],
                          "source_name": path.name})
        for panel in (1, 2, 3):
            left = round((panel - 1) * width/3) + 3
            right = round(panel * width/3) - 3
            picture = rgb.crop((left, 3, right, height-3))
            picture = ImageOps.fit(picture, (720, 1280), method=Image.Resampling.LANCZOS)
            memory = io.BytesIO()
            picture.save(memory, format="PNG", optimize=True)
            name = f"option_{option}/scene_{panel}.png"
            binary = memory.getvalue()
            if sha(binary) in hashes:
                raise ImportErrorRafael("two storyboard panels have identical pixel bytes")
            hashes.add(sha(binary))
            outputs[name] = binary
    output.mkdir(parents=True, exist_ok=True)
    for relative, value in outputs.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(value)
    provenance = {
        "source": "CHATGPT_IMAGE_TOOL",
        "session_evidence": "Three separate ChatGPT native image generations; IDs recorded, not independently authenticated",
        "input_composites": originals,
        "origin": "3 generated triptychs with 3 distinct panels each (not 9 separate generation calls)",
        "source_image_count": 3, "extracted_scene_count": 9,
        "frames": [{"path": p, "sha256": sha(b)} for p,b in outputs.items()],
        "approval_recorded": False, "published": False, "paid_external_api_calls": 0,
    }
    (output / "chatgpt_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "NINE_PANELS_EXTRACTED_NOT_APPROVED",
            "output": str(output), "image_count": 9,
            "provenance": str(output / "chatgpt_provenance.json"),
            "private_archive_verified": False, "ready_for_a2e": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=Path, required=True,
                        help="3 ordered source triptych PNG files")
    parser.add_argument("--generation-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = import_triptychs(args.input, args.output, generation_ids=args.generation_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ImportErrorRafael, ValueError, OSError) as exc:
        print("SIMBA_RAFAEL_TRIPTYCH_BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
