#!/usr/bin/env python3
"""Read-only, fail-closed stage handoffs for the existing Simba reel workflow.

No provider calls, paid actions, media downloads, approvals, or publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import catalog

# Completed producer -> next consumer. The stage order follows VIDEO_PIPELINE.md.
STAGES = (
    ("script", "SCENARIST", "RAFAEL", "script"),
    ("storyboard", "RAFAEL", "SCENARIST", "storyboard"),
    ("a2e_prompts", "SCENARIST", "A2E_RUNNER", "animation_prompt"),
    ("a2e_clips", "A2E_RUNNER", "VOICE_AND_MUSIC", "animated_clip"),
    ("voice_music", "VOICE_AND_MUSIC", "MONTAGE", "music"),
    ("edit_choice", "MONTAGE", "MONTAGE_RENDERER", "edit_plan"),
    ("render", "MONTAGE_RENDERER", "VIDEO_QA", "review_video"),
    ("qa", "VIDEO_QA", "LEO", "qa_report"),
)
OPTIONS_STAGES = {"script", "storyboard", "a2e_prompts", "edit_choice"}
EXECUTION_STAGES = {"a2e_clips", "voice_music", "render", "qa"}
STAGE_NAMES = tuple(row[0] for row in STAGES)


def fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def source_fingerprint(project: dict) -> str:
    """Changes whenever the project ID or canonical source revision changes."""
    refs = [{"path": row["path"], "sha256": row["sha256"]}
            for row in project.get("sources", [])]
    return fingerprint({"project_id": project["id"], "sources": sorted(refs, key=lambda x: x["path"])})


def _blocked(project: dict, reason: str, missing: list[str], *, next_owner: str = "PROCESS_OWNER") -> dict:
    return {
        "schema_version": 1, "project_id": project["id"], "title": project["title"],
        "state": "BLOCKED", "recipient": next_owner,
        "reason": reason, "missing": missing, "packet": None,
        "auto_dispatched": False, "external_media_verified": False,
        "paid_execution_authorized_by_handoff": False,
    }


def _asset_refs(project: dict, ids: list[str], required_kind: str) -> tuple[list[dict], list[str]]:
    available = {item.get("id"): item for item in project.get("assets", [])}
    selected, problems = [], []
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids):
        return [], ["stage.assets must be a nonempty list of asset IDs"]
    if len(ids) != len(set(ids)):
        problems.append("duplicate asset references")
    kinds = []
    for asset_id in ids:
        asset = available.get(asset_id)
        if not asset or asset.get("state") != "available":
            problems.append("asset unavailable in project.json: " + asset_id)
            continue
        if not asset.get("evidence"):
            problems.append("asset has no evidence: " + asset_id)
        # The payload is intentionally references only, not customer data/credentials.
        selected.append({"id": asset_id, "kind": asset.get("kind")})
        kinds.append(asset.get("kind"))
    if required_kind not in kinds:
        problems.append("missing required asset kind: " + required_kind)
    return selected, problems


def _validate_stage(project: dict, name: str, record: dict, expected_input: str) -> tuple[dict | None, list[str]]:
    problems: list[str] = []
    if not isinstance(record, dict):
        return None, [name + " record must be a JSON object"]
    if record.get("input_fingerprint") != expected_input:
        problems.append(name + ": stale or missing input_fingerprint")
    required_state = "completed" if name in EXECUTION_STAGES else "approved"
    if record.get("state") != required_state:
        problems.append(name + ": expected state " + required_state)
    if name != "qa" and not isinstance(record.get("approval_evidence"), str):
        problems.append(name + ": approval_evidence required")
    elif name != "qa" and not record["approval_evidence"].strip():
        problems.append(name + ": approval_evidence empty")
    if name in OPTIONS_STAGES:
        if record.get("options_presented") != 3:
            problems.append(name + ": evidence that three options were presented is required")
        if not isinstance(record.get("options_evidence"), str) or not record["options_evidence"].strip():
            problems.append(name + ": options_evidence required")
        opt = record.get("selected_option")
        if type(opt) is not int or opt not in (1, 2, 3):
            problems.append(name + ": selected_option must be 1, 2, or 3")
    if name == "a2e_prompts":
        cap = record.get("max_credits")
        quote = record.get("quoted_credits")
        if (type(cap) not in (int, float) or not math.isfinite(cap) or cap <= 0 or
            type(quote) not in (int, float) or not math.isfinite(quote) or quote < 0 or quote > cap):
            problems.append("a2e_prompts: quote/max_credits must be finite and within selected limit")
        if not isinstance(record.get("quote_evidence"), str) or not record["quote_evidence"].strip():
            problems.append("a2e_prompts: recorded quote evidence required")
    if name == "voice_music":
        if record.get("texts_presented") != 3 or record.get("music_presented") != 3:
            problems.append("voice_music: three text and three music options must be recorded")
        for field in ("text_option", "music_option"):
            opt = record.get(field)
            if type(opt) is not int or opt not in (1, 2, 3):
                problems.append("voice_music: " + field + " must be 1, 2, or 3")
        if record.get("voice_profile") not in ("simba_warmbaritone", "none"):
            problems.append("voice_music: unapproved or absent voice profile")
        if not isinstance(record.get("music_license_evidence"), str) or not record["music_license_evidence"].strip():
            problems.append("voice_music: licensed music evidence required")
    if name == "qa" and (record.get("qa_pass") is not True or
                          not isinstance(record.get("qa_evidence"), str) or
                          not record["qa_evidence"].strip()):
        problems.append("qa: pass and report evidence required")
    if name == "a2e_clips" and not isinstance(record.get("task_evidence"), str):
        problems.append("a2e_clips: A2E task evidence required")
    if name == "a2e_clips" and isinstance(record.get("task_evidence"), str) and not record["task_evidence"].strip():
        problems.append("a2e_clips: A2E task evidence empty")

    requirement = next(x[3] for x in STAGES if x[0] == name)
    selected, asset_problems = _asset_refs(project, record.get("assets"), requirement)
    problems.extend(name + ": " + item for item in asset_problems)
    if name == "voice_music" and record.get("voice_profile") != "none":
        if "narration" not in {item["kind"] for item in selected}:
            problems.append("voice_music: narration asset required for approved voice")
    if name == "a2e_clips":
        for asset_id in record.get("assets", []) if isinstance(record.get("assets"), list) else []:
            item = next((a for a in project["assets"] if a.get("id") == asset_id), None)
            if item and item.get("kind") == "animated_clip" and not item.get("task_id"):
                problems.append("a2e_clips: missing A2E task_id on " + asset_id)
    if problems:
        return None, problems
    receipt = fingerprint({
        "stage": name, "input_fingerprint": expected_input,
        "record": record, "assets": selected,
    })
    return {"receipt": receipt, "assets": selected}, []


def make_handoff(root: Path, path: Path, project: dict) -> dict:
    # A handoff must not bypass the validation from step 1.
    problems = catalog.project_issues(root, path, project)
    if problems:
        return _blocked(project, "PROJECT_INTEGRITY", problems)
    stages = project.get("stage_handoffs")
    if stages is None:
        # Preserve the existing Prague/Bavaria project manifests. No fake approvals.
        progress = catalog.project_progress(root, path, project)
        working_id = project.get("working_asset_id")
        assets = {a["id"]: a for a in project["assets"]}
        working = assets.get(working_id)
        approved_id = project.get("approved_asset_id")
        approved = assets.get(approved_id)
        if (approved and approved.get("state") == "available"
                and project.get("approvals", {}).get("editorial") == "approved"
                and project.get("approvals", {}).get("publication") != "approved"):
            return {
                "schema_version": 1, "project_id": project["id"], "title": project["title"],
                "state": "APPROVED_UNPUBLISHED", "recipient": "LEO",
                "reason": "EDITORIAL_APPROVED_PUBLICATION_SEPARATE",
                "missing": project.get("missing", []),
                "packet": {
                    "producer": "LEO", "next_stage": "publication_decision",
                    "source_revision": source_fingerprint(project),
                    "approved_asset_id": approved_id,
                    "assets": [{"id": approved_id, "kind": approved.get("kind")}],
                    "approval_evidence": project["approvals"].get("editorial_evidence"),
                    "external_media": "NOT_VERIFIED_BY_CATALOG",
                    "next_action": progress["next_action"],
                },
                "auto_dispatched": False, "external_media_verified": False,
                "paid_execution_authorized_by_handoff": False,
            }
        if progress["state"] == "NEEDS_LEO" and working and working.get("state") == "available":
            qa = [a for a in project["assets"] if a.get("kind") == "qa_report"
                  and a.get("state") == "available"]
            if not qa:
                return _blocked(project, "MISSING_QA_REPORT", ["available qa_report asset"])
            return {
                "schema_version": 1, "project_id": project["id"], "title": project["title"],
                "state": "NEEDS_LEO_REVIEW", "recipient": "LEO",
                "reason": "LEGACY_REVIEW_ONLY", "missing": project.get("missing", []),
                "packet": {
                    "producer": "MONTAGE", "next_stage": "editorial_review",
                    "source_revision": source_fingerprint(project),
                    "assets": [{"id": working_id, "kind": working["kind"]},
                               {"id": qa[0]["id"], "kind": "qa_report"}],
                    "qa_status": "RECORDED_NOT_REVERIFIED",
                    "next_action": progress["next_action"],
                },
                "auto_dispatched": False, "external_media_verified": False,
                "paid_execution_authorized_by_handoff": False,
            }
        if progress["state"] == "IN_PROGRESS" and "REVIEW" in project.get("stage", "").upper():
            return _blocked(project, "MISSING_SELECTED_REVIEW_ASSET",
                            ["working_asset_id for the actual latest video"])
        return _blocked(project, "STAGE_HANDOFFS_NOT_RECORDED",
                        ["approved stage choices and source-pinned assets"],
                        next_owner="SCENARIST")
    if not isinstance(stages, dict) or any(x not in STAGE_NAMES for x in stages):
        return _blocked(project, "INVALID_STAGE_HANDOFFS", ["known stage names only"])
    expected = source_fingerprint(project)
    prior = None
    lineage = []
    for name, producer, recipient, _ in STAGES:
        record = stages.get(name)
        if record is None:
            if any(later in stages for later in STAGE_NAMES[STAGE_NAMES.index(name) + 1:]):
                return _blocked(project, "STAGE_ORDER_GAP",
                                ["missing earlier stage: " + name],
                                next_owner="PROCESS_OWNER")
            if prior is None:
                return {
                    "schema_version": 1, "project_id": project["id"], "title": project["title"],
                    "state": "NEEDS_FIRST_STAGE", "recipient": "SCENARIST",
                    "reason": "SCRIPT_NOT_APPROVED",
                    "missing": ["three script options and explicit Leo choice"],
                    "expected_input_fingerprint": expected, "packet": None,
                    "auto_dispatched": False, "external_media_verified": False,
                    "paid_execution_authorized_by_handoff": False,
                }
            packet = {
                "producer": prior["producer"],
                "recipient": producer,
                "completed_stage": prior["stage"],
                "next_stage": name,
                "source_revision": source_fingerprint(project),
                "expected_input_fingerprint": expected,
                "receipt_sha256": prior["receipt"],
                "assets": [item for step in lineage for item in step["assets"]],
                "lineage": lineage,
                "decision": prior["decision"],
                "next_action": "Исполнить этап " + name + " по своему каноническому профилю; "
                               "проверить реальные файлы перед использованием.",
                "remote_assets": "NOT_VERIFIED_BY_CATALOG",
            }
            return {
                "schema_version": 1, "project_id": project["id"], "title": project["title"],
                "state": "READY_FOR_HANDOFF", "recipient": producer,
                "reason": None, "missing": [], "packet": packet,
                "auto_dispatched": False, "external_media_verified": False,
                "paid_execution_authorized_by_handoff": False,
            }
        validated, errors = _validate_stage(project, name, record, expected)
        if errors:
            return _blocked(project, "INVALID_OR_STALE_STAGE", errors, next_owner="PROCESS_OWNER")
        decision = {"approval_recorded": bool(record.get("approval_evidence"))}
        if name in OPTIONS_STAGES:
            decision["selected_option"] = record["selected_option"]
        if name == "a2e_prompts":
            decision.update(max_credits=record["max_credits"],
                            quoted_credits=record["quoted_credits"],
                            quote_recorded=True)
        if name == "voice_music":
            decision.update(text_option=record["text_option"], music_option=record["music_option"],
                            voice_profile=record["voice_profile"], license_recorded=True)
        if name == "qa":
            decision["qa_report_recorded"] = True
        prior = {"stage": name, "producer": producer, "recipient": recipient,
                 "receipt": validated["receipt"], "assets": validated["assets"],
                 "decision": decision}
        lineage.append(prior)
        expected = validated["receipt"]
    final_review_needed = project.get("approvals", {}).get("editorial") != "approved"
    return {
        "schema_version": 1, "project_id": project["id"], "title": project["title"],
        "state": "NEEDS_LEO_REVIEW" if final_review_needed else "APPROVED_UNPUBLISHED",
        "recipient": "LEO", "reason": None,
        "missing": (["explicit approval of the final MP4; publication remains separate"]
                    if final_review_needed else ["publication only on separate explicit request"]),
        "packet": {
            "producer": "VIDEO_QA", "next_stage": "editorial_review" if final_review_needed else "publication_decision",
            "source_revision": source_fingerprint(project),
            "receipt_sha256": prior["receipt"],
            "assets": [item for step in lineage for item in step["assets"]],
            "lineage": lineage,
            "decision": prior["decision"], "qa_status": "RECORDED_PASS_NOT_REVERIFIED",
            "next_action": ("Получить явное решение Лео по конкретному MP4; не публиковать."
                            if final_review_needed else
                            "При желании отдельно запросить разрешение на публикацию; не публиковать автоматически."),
        },
        "auto_dispatched": False, "external_media_verified": False,
        "paid_execution_authorized_by_handoff": False,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true",
                    help="Return success even for known project blockers; report states unchanged")
    ap.add_argument("project", help="Project name/ID, or 'all'")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.project == "all":
            results = [make_handoff(root, path, row) for path, row in catalog.load_projects(root)]
            output = results
        else:
            path, row = catalog.resolve_project(root, args.project)
            output = make_handoff(root, path, row)
            results = [output]
        if args.json:
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            for row in results:
                print(row["title"] + ": " + row["state"] + " → " + row["recipient"])
                print("Причина: " + str(row["reason"]))
                print("Передано: " + str((row["packet"] or {}).get("next_stage", "ничего")))
                if row["missing"]:
                    print("Не хватает: " + "; ".join(row["missing"]))
                print("Никаких запусков и публикаций.\n")
        return 2 if (not args.report_only and any(row["state"] == "BLOCKED" for row in results)) else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("HANDOFF_ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
