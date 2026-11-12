"""Step 5G v2 trusted source gate + canonical edit_choice candidate.

Works with the existing canonical project and private owner media; no Python/SQLite host is installed. Motion Lab alone
authors proposals; this module never synthesizes three options. Private staged
F2U MP4 and approved source spec are mandatory BEFORE a browser session/ACK.
No renderer execution or paid operations. Project edit_choice is marked approved
only after zero-paid v2 spec mapping, private Drive checksum readback, and a
successful canonical handoff check. SPEC_READY/VIDEO_QA are separate later gates.
"""
from __future__ import annotations

import copy
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
VIDEO=HERE.parent/"video"
for item in (str(HERE),str(VIDEO)):
    if item not in sys.path:sys.path.insert(0,item)

import handoff
import motionlab_stage_writeback as old
import motionlab_v2_contract as v2
import motionlab_render_contract as renderer

PRIVATE_FILE="approved-video-spec.json"
PRIVATE_MEDIA="verified-media.json"

class V2SourceError(ValueError):pass


def _private_job(root:Path,private_root:Path,project_id:str)->Path:
    if not isinstance(project_id,str) or not old.PROJECT_ID.fullmatch(project_id):
        raise V2SourceError("Invalid canonical project ID")
    if private_root is None:
        raise V2SourceError("Private job root must be provisioned by owner")
    repo=root.resolve()
    owned=Path(private_root).expanduser()
    if owned.is_symlink():
        raise V2SourceError("Private job root cannot be a symlink")
    owned=owned.resolve()
    if owned.is_relative_to(repo) or repo.is_relative_to(owned):
        raise V2SourceError("Private job root must be separate from repository")
    job=owned/project_id
    if job.is_symlink() or not job.is_dir() or job.resolve()!=job:
        raise V2SourceError("Private project job is unavailable")
    return job


def source_context(root:Path,private_root:Path,project_id:str,request_id:str):
    """Recover actual verified media and unchanged current voice/music handoff.

    HTTPS owner API gives only project ID; the path to private data is computed
    by this trusted server, never accepted from an untrusted request body.
    """
    if not isinstance(request_id,str) or not old.REQUEST_ID.fullmatch(request_id):
        raise V2SourceError("Invalid request ID")
    path,project,packet=old._open_stage(root,project_id)
    clips=old._clips(project)
    job=_private_job(root,private_root,project_id)
    for filename in (PRIVATE_FILE,PRIVATE_MEDIA):
        path=job/filename
        if path.is_symlink() or not path.is_file() or path.stat().st_size>512_000:
            raise V2SourceError("Private approved source bundle is missing")
    try:
        spec=json.loads((job/PRIVATE_FILE).read_text(encoding="utf-8"))
        media=json.loads((job/PRIVATE_MEDIA).read_text(encoding="utf-8"))
    except (OSError,UnicodeError,ValueError):
        raise V2SourceError("Private source metadata invalid") from None
    if not isinstance(media,list) or len(media)!=len(clips):
        raise V2SourceError("Private media count differs from approved F2U stage")
    for i,(asset,known) in enumerate(zip(media,clips),1):
        if (not isinstance(asset,dict)
                or asset.get("scene_id")!=f"clip-{i:02d}"
                or asset.get("asset_id")!=known.get("id")
                or asset.get("sha256")!=known.get("recorded_sha256")
                or abs(float(asset.get("duration_s",-1))-
                       float(known["recorded_duration_seconds"]))>.15):
            raise V2SourceError("F2U asset fingerprint or duration changed")
    if spec.get("packageId")!=project_id:
        raise V2SourceError("Approved spec package differs from canonical project")
    # Owner-controlled staged files; never accept filenames or hashes from Wix.
    # Studio owns the metadata contract (PR #127); Montage verifies bytes.
    try:
        import motionlab_v2_audio_gate as audio_gate
        audio_receipt = audio_gate.verify_private_audio_manifest(project, job)
    except (ImportError, ValueError):
        raise V2SourceError("V2_APPROVED_AUDIO_SOURCE_NOT_VERIFIED") from None

    materials=v2.make_materials_v2(project_id,request_id,packet["receipt_sha256"],
                                   spec,media,job)
    materials["audio_revision_sha256"] = audio_receipt["audio_revision_sha256"]
    materials["audio_preflight_status"] = audio_receipt["status"]
    # No timing approval is inferred from a verified WAV or CTC draft.
    # Only a separate, owner-private per-word listening review, explicitly
    # tied to current source/draft/approved audio SHA, can advance this gate.
    # Evidence stays private; the client receives bounded SHA/status only.
    import motionlab_audio_listening_qa as listening_qa
    materials["audio_alignment_status"] = "TIMINGS_NOT_VERIFIED"
    listening_receipt = None
    try:
        has_review = listening_qa.private_review_presence(job)
    except listening_qa.ListeningQAError:
        raise V2SourceError("V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED") from None
    if has_review:
        try:
            alignment, listening_receipt = listening_qa.verify_owner_private_listening_qa(
                project, job, root)
        except (listening_qa.ListeningQAError, ValueError, KeyError):
            raise V2SourceError("V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED") from None
        if listening_receipt.get("status") != "AUDIO_ALIGNMENT_VERIFIED_BY_EXPLICIT_OWNER_LISTENING":
            raise V2SourceError("V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED")
        materials["audio_alignment_status"] = "AUDIO_ALIGNMENT_VERIFIED"
        materials["audio_alignment_sha256"] = v2.digest(alignment)
        materials["audio_alignment_qa_sha256"] = listening_receipt["qa_evidence_sha256"]
    return {"project":project,"packet":packet,"job":job,"spec":spec,
            "media":media,"materials":materials,"audio_receipt":audio_receipt,
            "listening_receipt":listening_receipt}


def check_current_v2(root:Path,private_root:Path,project_id:str,
                     materials:dict,proposals:dict,selection:dict|None=None):
    if not isinstance(materials,dict):
        raise V2SourceError("Materials launch unavailable")
    ctx=source_context(root,private_root,project_id,materials.get("request_id"))
    if ctx["materials"]!=materials:
        raise V2SourceError("Private materials changed since user opened Motion Lab")
    v2.validate_proposals_v2(materials,proposals)
    if selection is None:
        return ctx,None,None
    # Product decision: accurately synchronized word timings must exist
    # before the owner can finalize a visual WYSIWYG selection.
    # A byte-verified WAV is not an ASR/forced-alignment receipt.
    if ctx["materials"].get("audio_alignment_status") != "AUDIO_ALIGNMENT_VERIFIED":
        raise V2SourceError("TIMINGS_NOT_VERIFIED")
    spec,report=v2.map_selection_v2_to_spec(
        materials,proposals,selection,ctx["spec"],ctx["media"],ctx["job"])
    # Whole source file copied into the private store at ACK (not the repository).
    # Context source remains pinned by fresh SHA/ffprobe before project commit.
    if report["status"]!="V2_VIDEO_SPEC_MAPPED_NOT_RENDERED":
        raise V2SourceError("Validated spec mapping did not complete")
    return ctx,spec,report


def build_candidate_v2(root:Path,private_root:Path,project_id:str,
                       materials:dict,proposals:dict,selection:dict,spec:dict,
                       references:dict,receipt_id:str) -> tuple[dict,dict]:
    ctx,recomputed,report=check_current_v2(root,private_root,project_id,
                                            materials,proposals,selection)
    if recomputed!=spec or report["receipt_id"]!=receipt_id:
        raise V2SourceError("Verified spec or chosen receipt changed")
    for key in ("materials","proposals","selection-v2","video-spec"):
        info=references.get(key)
        if (not isinstance(info,dict)
                or not isinstance(info.get("id"),str)
                or not old.DRIVE_ID.fullmatch(info["id"])
                or not isinstance(info.get("sha256"),str)
                or not old.SHA.fullmatch(info["sha256"])):
            raise V2SourceError("Private Drive receipt missing")
    if len({references[k]["id"] for k in references})!=4:
        raise V2SourceError("Private source files are not distinct")
    project=ctx["project"]
    asset_id="motionlab-v2-"+references["selection-v2"]["sha256"][:24]
    if any(a.get("id")==asset_id for a in project.get("assets",[])):
        raise V2SourceError("Edit-plan already committed")
    candidate=copy.deepcopy(project)
    cid=references["selection-v2"]["id"]
    candidate["assets"].append({
        "id":asset_id,"kind":"edit_plan","title":"Motion Lab v2 selected visual montage",
        "state":"available","url":f"https://drive.google.com/file/d/{cid}/view",
        "drive_file_id":cid,
        "recorded_sha256":references["selection-v2"]["sha256"],
        "evidence":"Connected explicit v2 selection, exact proposals SHA and original"
                   " F2U media verified; private spec mapped, NOT render-authorized",
    })
    candidate["stage_handoffs"]["edit_choice"]={
        "state":"approved",
        "input_fingerprint":ctx["packet"]["receipt_sha256"],
        "assets":[asset_id],
        "selected_option":report["selected_option"],
        "options_presented":3,
        "options_evidence":"Motion Lab authored three distinct proposals, private SHA256 "+
                           references["proposals"]["sha256"],
        "approval_evidence":"Explicit v2 visual layout and edit choice pinned to receipt "+
                            receipt_id+", NO paid/render/publish authorization",
        "motionlab_receipt_id":receipt_id,
        "request_id":materials["request_id"],
        "selection_sha256":references["selection-v2"]["sha256"],
        "materials_sha256":references["materials"]["sha256"],
        "proposals_sha256":references["proposals"]["sha256"],
        "video_spec_sha256":references["video-spec"]["sha256"],
        "video_spec_private_file_id":references["video-spec"]["id"],
        "visual_layout_preserved":bool(report.get("visual_layout_present")),
        "source_clip_ids":[x["asset_id"] for x in materials["scenes"]],
        "no_paid_operations":True,
        "no_auto_publish":True,
        "render_authorized":False,
    }
    candidate["stage"]="EDIT_CHOICE_V2_RECORDED_AWAITING_PRIVATE_MONTAGE_PLAN"
    candidate["next_action"]=(
        "MONTAGE_RENDERER: load private spec JSON and F2U originals by verified "
        "SHA; check reuse of approved WAV/music and full 60s timeline; "
        "do NOT trigger TTS, A2E, publish or auto-render."
    )
    candidate["updated_at"]=datetime.now(timezone.utc).date().isoformat()
    for field in ("approvals","approved_asset_id","working_asset_id"):
        if candidate.get(field)!=project.get(field):
            raise V2SourceError("Publication/MP4 approval must not be changed")
    outcome=handoff.make_handoff(root,_safe_path(root,project_id),candidate)
    if (outcome.get("state")!="READY_FOR_HANDOFF"
            or outcome.get("recipient")!="MONTAGE_RENDERER"
            or (outcome.get("packet") or {}).get("next_stage")!="render"):
        raise V2SourceError("Canonical stage handoff did not accept v2 edit choice")
    return candidate,{
        "status":"MOTIONLAB_V2_EDIT_APPROVED_NOT_RENDERED",
        "receipt_id":receipt_id,
        "next_stage":"render",
        "next_recipient":"MONTAGE_RENDERER",
        "private_spec_preserved":True,
        "render_started":False,"paid_calls":0,
        "project_written":False,"publication_authorized":False,
    }


def _safe_path(root:Path,project_id:str)->Path:
    return root.resolve()/"campaigns"/project_id/"project.json"
