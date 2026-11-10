#!/usr/bin/env python3
"""Approved Rafael -> EXISTING Simba universal A2E issue contract (NO paid execution).

This is an input adapter, not a second A2E runner. It validates the existing
stage_handoffs, the actual private storyboard ZIP, source-frame fingerprints,
selected English prompt plan, approved limit, and Wix Media byte content.
It then writes a private, owner-reviewable JSON issue body using the exact
simba_a2e_generate contract consumed by github_a2e_universal.py.

Never creates/issues/labels a GitHub Issue, invokes A2E, approves an option,
publishes media, or stores private prompts/images in the public repository.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from PIL import Image, ImageOps, ImageChops, ImageStat

import catalog
import handoff
import rafael_archive

# Reuse strict Wix URL/body gates from the EXISTING universal A2E.
VIDEO = Path(__file__).resolve().parents[1] / "video"
if str(VIDEO) not in sys.path:
    sys.path.insert(0, str(VIDEO))
from github_a2e_issue_bridge import build_bodies  # noqa: E402
from github_a2e_universal import validate as validate_universal  # noqa: E402

MAX_WIX_BYTES = 10_000_000
SHA = re.compile(r"^[a-f0-9]{64}$")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
DRIVE_ID = re.compile(r"^[A-Za-z0-9_-]{10,120}$")


class BridgeError(RuntimeError):
    pass


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _valid_id(value: object, *, drive: bool = False) -> bool:
    return isinstance(value, str) and (DRIVE_ID if drive else ID).fullmatch(value) is not None


def _require_verified_asset(project: dict, stage_name: str, kind: str) -> dict:
    record = project["stage_handoffs"][stage_name]
    ids = record["assets"]
    candidates = [row for row in project["assets"]
                  if row.get("id") in ids and row.get("kind") == kind
                  and row.get("state") == "available"]
    if len(candidates) != 1:
        raise BridgeError("exactly one referenced available " + kind + " asset required")
    if not SHA.fullmatch(candidates[0].get("recorded_sha256", "")):
        raise BridgeError(kind + " asset missing actual ZIP/plan SHA-256")
    return candidates[0]


def _parse_private_plan(path: Path) -> tuple[dict, bytes]:
    if not path.is_file() or not 300 <= path.stat().st_size <= 16000:
        raise BridgeError("private A2E plan absent or outside safe size")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError):
        raise BridgeError("private plan is not valid JSON") from None
    if not isinstance(value, dict):
        raise BridgeError("A2E plan must be an object")
    if set(value) != {"schema_version", "project_id", "stage_receipt",
                      "storyboard_option", "prompt_option", "storyboard_archive",
                      "scenes"}:
        raise BridgeError("A2E plan schema fields invalid")
    return value, raw


def _private_zip_identity(project: dict, zipfile_path: Path,
                          manifest: dict, storyboard: dict, script_receipt: str) -> list[dict]:
    if (manifest.get("project_id") != project["id"] or
            manifest.get("input_receipt") != script_receipt):
        raise BridgeError("private storyboard is not for this approved script revision")
    if not isinstance(storyboard.get("drive_file_id"), str) or not _valid_id(storyboard["drive_file_id"], drive=True):
        raise BridgeError("private Drive file ID absent")
    asset = _require_verified_asset(project, "storyboard", "storyboard")
    if (asset.get("drive_file_id") != storyboard["drive_file_id"] or
            not SHA.fullmatch(storyboard.get("sha256", "")) or
            storyboard["sha256"] != asset["recorded_sha256"]):
        raise BridgeError("private Drive receipt or ZIP digest differs from approved project asset")
    # A URL alone is not remote verification; a separate private readback
    # performed before approval must be recorded in the project.
    if asset.get("drive_readback_verified") is not True or not asset.get("drive_readback_evidence"):
        raise BridgeError("missing audited private Drive readback evidence")
    approved_opt = project["stage_handoffs"]["storyboard"]["selected_option"]
    choices = manifest["options"]
    if len(choices) != 3 or choices[approved_opt - 1]["option"] != approved_opt:
        raise BridgeError("selected storyboard option absent from actual ZIP")
    return choices[approved_opt - 1]["scenes"]


def _wix_jpeg_match(source: bytes, received: bytes) -> bool:
    """Verify the Wix picture still depicts the same selected frame.

    Pixel comparison is a bounded visual check, not a cryptographic identity
    proof. Wix may resize or compress JPEG; large substitutions are blocked.
    """
    try:
        with Image.open(io.BytesIO(source)) as s, Image.open(io.BytesIO(received)) as r:
            s.load()
            r.load()
            if r.width < 360 or r.height < 500 or r.width / r.height > 1.0:
                return False
            a = ImageOps.fit(ImageOps.exif_transpose(s).convert("RGB"), (96, 128))
            b = ImageOps.fit(ImageOps.exif_transpose(r).convert("RGB"), (96, 128))
            diff = ImageChops.difference(a, b)
            average = sum(ImageStat.Stat(diff).mean) / 3
            return average <= 11
    except (OSError, SyntaxError, ValueError):
        return False


def fetch_wix(url: str, *, limit: int = MAX_WIX_BYTES) -> bytes:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "static.wixstatic.com"
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.port not in (None, 443)
            or not parsed.path.startswith("/media/") or
            not parsed.path.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))):
        raise BridgeError("untrusted Wix Media URL")
    req = Request(url, headers={"User-Agent": "Simba-A2E-Preflight/1.0", "Accept": "image/*"})
    try:
        with urlopen(req, timeout=22) as resp:
            result_url = urlsplit(resp.geturl())
            if resp.status != 200 or result_url.hostname != "static.wixstatic.com":
                raise BridgeError("Wix remote image redirect/status rejected")
            media = resp.read(limit + 1)
            if not 500 <= len(media) <= limit:
                raise BridgeError("Wix image missing or exceeds size cap")
            if not str(resp.headers.get("Content-Type", "")).lower().startswith("image/"):
                raise BridgeError("Wix image is not a media response")
            return media
    except (OSError, TimeoutError):
        raise BridgeError("Wix image read-only verification failed") from None


def create_owner_issue(root: Path, project_id: str, plan_path: Path, zip_path: Path,
                       *, fetch=fetch_wix, verify_remote: bool = True) -> tuple[dict, dict]:
    if not _valid_id(project_id):
        raise BridgeError("invalid project ID")
    root = root.resolve()
    path = catalog.inside(root, f"campaigns/{project_id}/project.json")
    project = json.loads(path.read_text(encoding="utf-8"))
    current = handoff.make_handoff(root, path, project)
    packet = current.get("packet") or {}
    if (project.get("id") != project_id
            or current.get("state") != "READY_FOR_HANDOFF"
            or current.get("recipient") != "A2E_RUNNER"
            or packet.get("next_stage") != "a2e_clips"
            or not SHA.fullmatch(packet.get("receipt_sha256", ""))):
        raise BridgeError("approved sequential storyboard and A2E prompts handoff not ready")
    stages = project["stage_handoffs"]
    for stage in ("script", "storyboard", "a2e_prompts"):
        if stages[stage].get("state") != "approved" or type(stages[stage].get("selected_option")) is not int:
            raise BridgeError("missing explicit Leo selection for " + stage)
    private, raw = _parse_private_plan(plan_path)
    approved_prompt_asset = _require_verified_asset(project, "a2e_prompts", "animation_prompt")
    if (approved_prompt_asset["recorded_sha256"] != digest(raw)
            or private["schema_version"] != 1
            or private["project_id"] != project_id
            or private["stage_receipt"] != packet["receipt_sha256"]
            or private["storyboard_option"] != stages["storyboard"]["selected_option"]
            or private["prompt_option"] != stages["a2e_prompts"]["selected_option"]):
        raise BridgeError("private prompt plan does not match the approved source and option")
    zip_bytes, manifest = rafael_archive.safe_archive(zip_path)
    if digest(zip_bytes) != private["storyboard_archive"].get("sha256"):
        raise BridgeError("private frame archive SHA-256 mismatch")
    script_receipt = handoff._validate_stage(
        project, "script", stages["script"], handoff.source_fingerprint(project))[0]["receipt"]
    selected = _private_zip_identity(project, zip_path, manifest,
                                     private["storyboard_archive"], script_receipt)
    specs = private["scenes"]
    if (not isinstance(specs, list) or len(specs) != len(selected)
            or not 1 <= len(specs) <= 6):
        raise BridgeError("selected storyboard and A2E scene count differ")
    scenes, wix_hashes, to_verify = [], [], []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for index, (entry, source) in enumerate(zip(specs, selected), 1):
            if (not isinstance(entry, dict)
                    or set(entry) != {"scene", "frame_sha256", "image_url", "prompt_en", "wix_upload_evidence"}
                    or type(entry.get("scene")) is not int or entry["scene"] != index
                    or entry.get("frame_sha256") != source["image_sha256"]
                    or not isinstance(entry.get("wix_upload_evidence"), str)
                    or not 8 <= len(entry["wix_upload_evidence"]) <= 400):
                raise BridgeError("Wix scene mapping is stale, missing or out of order")
            if not isinstance(entry.get("image_url"), str) or len(entry["image_url"]) > 1000:
                raise BridgeError("Wix image URL invalid")
            prompt = entry.get("prompt_en")
            if not isinstance(prompt, str) or not 15 <= len(prompt) <= 2000 or not prompt.strip():
                raise BridgeError("selected English motion prompt absent")
            name = source["image"]
            image = z.read(name)
            if digest(image) != source["image_sha256"]:
                raise BridgeError("selected frame mismatch in ZIP")
            # The existing Wix-only URL validator runs again inside the
            # universal A2E. No private Google Drive link enters the issue.
            scenes.append({"name": f"scene-{index:02d}", "image_url": entry["image_url"],
                           "prompt": prompt})
            to_verify.append((entry["image_url"], image))
    cap = stages["a2e_prompts"]["max_credits"]
    quote = stages["a2e_prompts"]["quoted_credits"]
    if (type(cap) not in (int, float) or not 0 < cap <= 1000 or
            type(quote) not in (int, float) or quote > cap):
        raise BridgeError("approved amount unavailable, over budget or over universal runner cap")
    issue = {"kind": "simba_a2e_generate", "max_credits": cap, "scenes": scenes}
    # Run through the real downstream consumer's validator, not a parallel
    # homemade A2E request format.
    fake_event = {
        "action": "labeled", "repository": {"full_name": "legur/Simba"},
        "sender": {"login": "legur"}, "label": {"name": "a2e-generate-approved"},
        "issue": {"number": 1, "user": {"login": "legur"},
                  "body": json.dumps(issue, ensure_ascii=False)},
    }
    issue_id, checked_cap, actual_bodies = validate_universal(fake_event)
    if checked_cap != float(cap) or len(actual_bodies) != len(scenes):
        raise BridgeError("downstream universal A2E contract mismatch")
    if not verify_remote:
        raise BridgeError("Wix bytes were not verified; no issue payload may be emitted")
    # The validated universal schema has already rejected non-Wix hosts
    # before any supplied URL can reach the network.
    for wix_url, source in to_verify:
        raw_remote = fetch(wix_url)
        if not _wix_jpeg_match(source, raw_remote):
            raise BridgeError("Wix content differs from the approved selected frame")
        wix_hashes.append(digest(raw_remote))
    receipt = {
        "status": "OWNER_ISSUE_PAYLOAD_READY_NOT_SUBMITTED",
        "project_id": project_id, "handoff_receipt": packet["receipt_sha256"],
        "selected_storyboard": stages["storyboard"]["selected_option"],
        "selected_prompts": stages["a2e_prompts"]["selected_option"],
        "scene_count": len(scenes), "wix_media_sha256": wix_hashes,
        "quoted_credits_recorded": quote, "approved_ceiling_recorded": cap,
        "issue_body_sha256": digest(json.dumps(issue, sort_keys=True, ensure_ascii=False).encode()),
        "issued": False, "label_applied": False, "a2e_started": False,
        "price_requote_required_by_existing_runner": True,
        "paid_calls": 0, "publication": False,
    }
    return issue, receipt


def private_write(out: Path, project_root: Path, issue: dict) -> None:
    out = out.resolve()
    if out.is_relative_to(project_root.resolve()):
        raise BridgeError("refuse to write private issue body inside public repository")
    if out.exists():
        raise BridgeError("refuse to replace existing owner-approved issue request")
    # Avoid world-readable or symlink target paths; keep actual prompts outside Git.
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(issue, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except Exception:
        out.unlink(missing_ok=True)
        raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--project", required=True)
    ap.add_argument("--private-plan", type=Path, required=True)
    ap.add_argument("--private-storyboard-zip", type=Path, required=True)
    ap.add_argument("--owner-issue-file", type=Path)
    ap.add_argument("--verify-wix", action="store_true")
    args = ap.parse_args(argv)
    try:
        # Network verification is mandatory before exporting a paid-ready owner
        # issue body. Preview-only behavior intentionally does not emit secrets.
        issue, receipt = create_owner_issue(
            args.root, args.project, args.private_plan, args.private_storyboard_zip,
            verify_remote=args.verify_wix)
        if args.owner_issue_file is None:
            receipt["status"] = "VALIDATED_NO_ISSUE_FILE_WRITTEN"
        else:
            private_write(args.owner_issue_file, args.root, issue)
            receipt["status"] = "PRIVATE_OWNER_ISSUE_FILE_READY_NOT_SUBMITTED"
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    except (BridgeError, ValueError, TypeError, KeyError, OSError,
            rafael_archive.ArchiveError) as exc:
        # Never print private prompt text, URLs, or the raw issue body.
        print("SIMBA_A2E_HANDOFF_BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
