#!/usr/bin/env python3
"""Issue #113: draft materials.launch/v2 -> Motion Lab proposals/v2 -> selection/v2.

Montage owns verified inputs and renderer limits. Motion Lab alone authors
the three proposals after actually accessing the private MP4s. This module
never makes up recommendations, initiates paid providers or runs a render.
Analysis claims are cross-checked but cannot prove model visual inspection.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

import make_video
import motionlab_render_contract as r
import motionlab_layout_contract as geometry

MATERIALS = "bontours.motionlab.materials.launch/v2"
PROPOSALS = "bontours.motionlab.proposals/v2"
SELECTION = "bontours.motionlab.selection/v2"
SHA = re.compile(r"^[0-9a-f]{64}$")
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,89}$")


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def check(ok,code,scene="",field="",requested=""):
    if not ok:
        raise r.ContractError(code,scene_id=scene,field=field,requested=str(requested))


def numeric(x,lo,hi):
    return type(x) in (int,float) and math.isfinite(x) and lo<=x<=hi


def description(s,lo=12,hi=800):
    return isinstance(s,str) and lo<=len(s.strip())<=hi


def checked_mp4(scene_id,asset,base,job_dir,probe):
    check(isinstance(asset,dict) and isinstance(base,dict),"MISSING_VERIFIED_ASSET",scene_id)
    check(isinstance(asset.get("sha256"),str) and SHA.fullmatch(asset["sha256"])
          and base.get("clip")==asset.get("file"),"SOURCE_BINDING_CHANGED",scene_id)
    path=r._safe_clip(Path(job_dir).resolve(),asset["file"])
    check(r._actual_sha(path)==asset["sha256"],"MEDIA_SHA256_MISMATCH",scene_id)
    info=probe(path)
    seconds=info.get("duration_s")
    check(numeric(seconds,3,15) and numeric(info.get("width"),16,8192)
          and numeric(info.get("height"),16,8192)
          and type(info.get("has_audio")) is bool
          and numeric(asset.get("duration_s"),3,15)
          and abs(seconds-asset["duration_s"])<=r.TRIM_TOLERANCE,
          "INVALID_SOURCE_METADATA",scene_id)
    media={"kind":"video","asset_sha256":asset["sha256"],
           "duration_s":round(seconds,4),
           "width":int(info["width"]),"height":int(info["height"]),
           "has_audio":info["has_audio"]}
    fps=info.get("fps")
    if fps is not None:
        check(numeric(fps,1,240),"MEDIA_FFPROBE_FAILED",scene_id)
        media["fps"]=round(fps,4)
    return media


def make_materials_v2(project_id,request_id,fingerprint,approved_spec,
                      verified_media,job_dir,probe=None):
    """Read-only source package with zero Montage-authored creative options."""
    check(isinstance(project_id,str) and SAFE.fullmatch(project_id),"INVALID_PROJECT_ID")
    check(isinstance(request_id,str) and SAFE.fullmatch(request_id),"INVALID_REQUEST_ID")
    check(isinstance(fingerprint,str) and SHA.fullmatch(fingerprint),"SOURCE_FINGERPRINT_CHANGED")
    check(isinstance(approved_spec,dict) and isinstance(verified_media,list),
          "APPROVED_VIDEO_SPEC_REQUIRED")
    originals=approved_spec.get("scenes")
    check(isinstance(originals,list) and len(originals)==len(verified_media)
          and 1<=len(originals)<=8,"INVALID_SCENE_COUNT")
    check(approved_spec.get("size","1080x1920")=="1080x1920"
          and isinstance(approved_spec.get("voice"),dict)
          and isinstance(approved_spec.get("music"),dict)
          and isinstance(approved_spec.get("end"),dict)
          and isinstance(approved_spec.get("sourcePost"),str)
          and bool(approved_spec["sourcePost"])
          and isinstance(approved_spec.get("packageId"),str),
          "APPROVED_VIDEO_SPEC_REQUIRED")
    probe=probe or r._ffprobe
    scenes=[]; total=0; ids=set()
    for idx,(base,asset) in enumerate(zip(originals,verified_media),1):
        check(isinstance(asset,dict),"MISSING_VERIFIED_ASSET")
        sid,aid=asset.get("scene_id"),asset.get("asset_id")
        check(isinstance(sid,str) and SAFE.fullmatch(sid)
              and isinstance(aid,str) and SAFE.fullmatch(aid)
              and sid not in ids,"SCENE_BINDING_MISMATCH")
        ids.add(sid)
        media=checked_mp4(sid,asset,base,job_dir,probe)
        total+=media["duration_s"]
        title=base.get("title") or ""
        lines=base.get("lines",[])
        check(isinstance(title,str) and isinstance(lines,list)
              and all(isinstance(x,dict) and isinstance(x.get("text"),str)
                      for x in lines),"APPROVED_TEXT_UNAVAILABLE",sid)
        subtitle=" ".join(x["text"] for x in lines).strip()
        scenes.append({
            "scene_id":sid,"asset_id":aid,"name":f"Сцена {idx}",
            "media":media,
            "locked":{"title_text":title,
                      "title_sha256":hashlib.sha256(title.encode()).hexdigest(),
                      "subtitle_preview":subtitle,
                      "subtitle_sha256":hashlib.sha256(subtitle.encode()).hexdigest(),
                      "read_only":True},
        })
    check(total<=60,"VIDEO_DURATION_LIMIT_EXCEEDED")
    return {
        "schema":MATERIALS,"project_id":project_id,"request_id":request_id,
        "stage":"edit_choice","expected_input_fingerprint":fingerprint,
        "renderer_capabilities":r.renderer_capabilities(),
        "scenes":scenes,
        "approved_audio_sha256":digest({"voice":approved_spec["voice"],
                                        "music":approved_spec["music"]}),
        "constraints":{
            "format":"9:16","max_total_seconds":60,
            "source_ids_immutable":True,"approved_text_immutable":True,
            "approved_voice_music_immutable":True,
            "trim_requires_v2_extension":True,
            "allow_paid_operations":False,"allow_publish":False,
        },
        "analysis":{"status":"PENDING_REAL_MEDIA_ACCESS",
                    "required_kind":"full_original_mp4"},
    }


def validate_materials(materials):
    check(isinstance(materials,dict) and materials.get("schema")==MATERIALS
          and materials.get("stage")=="edit_choice","INVALID_MATERIALS_V2")
    check(isinstance(materials.get("expected_input_fingerprint"),str)
          and SHA.fullmatch(materials["expected_input_fingerprint"]),
          "SOURCE_FINGERPRINT_CHANGED")
    check(materials.get("renderer_capabilities")==r.renderer_capabilities(),
          "RENDERER_CAPABILITIES_MISSING_OR_STALE")
    constraints=materials.get("constraints")
    check(isinstance(constraints,dict) and
          constraints.get("format")=="9:16" and
          constraints.get("max_total_seconds")==60 and
          all(constraints.get(k) is True for k in (
              "source_ids_immutable","approved_text_immutable",
              "approved_voice_music_immutable","trim_requires_v2_extension"))
          and constraints.get("allow_paid_operations") is False
          and constraints.get("allow_publish") is False,
          "INVALID_RENDER_CONSTRAINTS")
    scenes=materials.get("scenes")
    check(isinstance(scenes,list) and 1<=len(scenes)<=8,"INVALID_SCENE_COUNT")
    ids=set();total=0
    for src in scenes:
        check(isinstance(src,dict),"SCENE_BINDING_MISMATCH")
        sid,aid=src.get("scene_id"),src.get("asset_id")
        check(isinstance(sid,str) and SAFE.fullmatch(sid)
              and isinstance(aid,str) and SAFE.fullmatch(aid) and sid not in ids,
              "SCENE_BINDING_MISMATCH")
        ids.add(sid)
        media=src.get("media")
        lock=src.get("locked")
        check(isinstance(media,dict) and media.get("kind")=="video"
              and isinstance(media.get("asset_sha256"),str)
              and SHA.fullmatch(media["asset_sha256"])
              and numeric(media.get("duration_s"),3,15)
              and numeric(media.get("width"),16,8192)
              and numeric(media.get("height"),16,8192)
              and type(media.get("has_audio")) is bool
              and ("fps" not in media or numeric(media["fps"],1,240)),
              "INVALID_SOURCE_METADATA",sid)
        check(isinstance(lock,dict) and lock.get("read_only") is True
              and isinstance(lock.get("title_text"),str)
              and isinstance(lock.get("subtitle_preview"),str)
              and lock.get("title_sha256")==hashlib.sha256(
                  lock["title_text"].encode()).hexdigest()
              and lock.get("subtitle_sha256")==hashlib.sha256(
                  lock["subtitle_preview"].encode()).hexdigest(),
              "APPROVED_TEXT_UNAVAILABLE",sid)
        total+=media["duration_s"]
    check(total<=60,"VIDEO_DURATION_LIMIT_EXCEEDED")


def validate_effects(scenes,materials):
    originals=materials["scenes"]
    check(isinstance(scenes,list) and len(scenes)==len(originals),
          "SCENE_BINDING_MISMATCH")
    signatures=[];subtitle_scopes=set()
    for i,(item,src) in enumerate(zip(scenes,originals)):
        sid=src["scene_id"]
        check(isinstance(item,dict) and
              set(item)=={"scene_id","camera","transition","title_fx","subtitle"}
              and item.get("scene_id")==sid,"SCENE_BINDING_MISMATCH",sid)
        cam=item["camera"];title=item["title_fx"];tran=item["transition"];sub=item["subtitle"]
        check(isinstance(cam,dict) and set(cam)=={"id","intensity_percent"}
              and cam.get("id") in r.CAMERA_EFFECTS
              and numeric(cam.get("intensity_percent"),0,100),
              "UNSUPPORTED_CAMERA_EFFECT",sid,"camera.id",
              cam.get("id") if isinstance(cam,dict) else "?")
        check(type(title) is str and title in r.TITLE_EFFECTS,
              "UNSUPPORTED_TITLE_EFFECT",sid,"title_fx",title)
        check(title!="none" or not src["locked"]["title_text"],
              "IMMUTABLE_TEXT_CHANGED",sid,"title_fx")
        if i==0:
            check(tran is None,"UNSUPPORTED_TRANSITION",sid)
        else:
            check(isinstance(tran,dict) and set(tran)=={"id","duration_ms"}
                  and tran.get("id") in make_video.TRANSITIONS
                  and type(tran.get("duration_ms")) is int
                  and 400<=tran["duration_ms"]<=2400,
                  "UNSUPPORTED_TRANSITION",sid,"transition.id",
                  tran.get("id") if isinstance(tran,dict) else "?")
        check(isinstance(sub,dict) and set(sub)=={"style_id","word_motion_id"}
              and sub.get("style_id") in make_video.SUBTITLE_STYLES
              and sub.get("word_motion_id") in make_video.SUBTITLE_MOTIONS,
              "UNSUPPORTED_SUBTITLE_EFFECT",sid,"subtitle.style_id",
              sub.get("style_id") if isinstance(sub,dict) else "?")
        subtitle_scopes.add((sub["style_id"],sub["word_motion_id"]))
        signatures.append(canonical(item))
    check(len(subtitle_scopes)==1,"UNSUPPORTED_PER_SCENE_SUBTITLE")
    return tuple(signatures)


def _validated_layout(items, materials):
    try:
        return geometry.canonical_scene_layouts(items, materials["scenes"])
    except geometry.LayoutError as exc:
        raise r.ContractError(exc.code, scene_id=exc.scene_id,
                              field=exc.field) from None


def _defaults_layout(materials):
    return [{
        "scene_id":source["scene_id"],
        "asset_id":source["asset_id"],
        "layout":{
            "title":dict(geometry.DEFAULTS["title"]),
            "subtitle":dict(geometry.DEFAULTS["subtitle"]),
        },
    } for source in materials["scenes"]]


def _preflight_visual_collisions(items, materials):
    for item,source in zip(items,materials["scenes"]):
        title=item["layout"]["title"]
        subtitle=item["layout"]["subtitle"]
        if (source["locked"]["title_text"].strip()
                and source["locked"]["subtitle_preview"].strip()
                and abs(title["y"]-subtitle["y"]) <
                    max(12, (title["scale"]+subtitle["scale"])/16)):
            raise r.ContractError(
                "VISUAL_LAYOUT_TEXT_COLLISION",
                scene_id=source["scene_id"],
                field="scene_layout.title/subtitle",
            )


def validate_proposals_v2(materials,proposals):
    validate_materials(materials)
    check(isinstance(proposals,dict) and proposals.get("schema")==PROPOSALS
          and proposals.get("request_id")==materials["request_id"]
          and proposals.get("project_id")==materials["project_id"]
          and proposals.get("expected_input_fingerprint")==
              materials["expected_input_fingerprint"]
          and proposals.get("materials_sha256")==digest(materials)
          and proposals.get("renderer_revision_sha256")==
              materials["renderer_capabilities"]["revision_sha256"],
          "MOTIONLAB_PROPOSALS_STALE")
    analysis=proposals.get("analysis")
    check(isinstance(analysis,dict)
          and analysis.get("status") in (
              "REAL_VIDEO_REVIEWED", "REAL_VIDEO_AUTOMATICALLY_ANALYZED")
          and analysis.get("access_mode")=="owner_private_material_bundle"
          and description(analysis.get("review_notes"),20,1500),
          "ANALYSIS_INPUT_MISSING")
    # Sampling pixel movement IS genuine inspection of original MP4 bytes,
    # not human/AI semantic viewing. Keep an explicit, audit-friendly branch:
    # browser claims alone remain untrusted; current-stage backend replays the
    # full sample analysis from source bytes before accepting owner selection.
    if analysis.get("status")=="REAL_VIDEO_AUTOMATICALLY_ANALYZED":
        check(analysis.get("analysis_method")==
              "full_timeline_sampled_pixels_ffmpeg_v1",
              "AUTOMATIC_VIDEO_ANALYSIS_METHOD_MISSING")
        samples=analysis.get("pixel_evidence")
        check(isinstance(samples,list)
              and len(samples)==len(materials["scenes"]),
              "AUTOMATIC_VIDEO_EVIDENCE_MISSING")
        for src,row in zip(materials["scenes"],samples):
            check(isinstance(row,dict)
                  and row.get("scene_id")==src["scene_id"]
                  and row.get("asset_sha256")==src["media"]["asset_sha256"]
                  and isinstance(row.get("sampled_frame_sha256"),str)
                  and SHA.fullmatch(row["sampled_frame_sha256"])
                  and type(row.get("frames_sampled")) is int
                  and row["frames_sampled"] >= 5
                  and row.get("sample_rate_fps")==3
                  and numeric(row.get("first_sample_s"),0,0)
                  and numeric(row.get("last_sample_s"),0,16)
                  and numeric(row.get("mean_luminance"),0,255)
                  and numeric(row.get("mean_contrast"),0,128)
                  and numeric(row.get("motion_delta"),0,255)
                  and numeric(row.get("peak_frame_delta"),0,255),
                  "AUTOMATIC_VIDEO_EVIDENCE_MISSING",src["scene_id"])
    inspected=analysis.get("inspected_assets")
    check(isinstance(inspected,list) and
          len(inspected)==len(materials["scenes"]),"ANALYSIS_INPUT_MISSING")
    for src,evidence in zip(materials["scenes"],inspected):
        check(isinstance(evidence,dict) and
              set(evidence)=={"scene_id","asset_sha256","evidence_kind","scene_notes"}
              and evidence["scene_id"]==src["scene_id"]
              and evidence["asset_sha256"]==src["media"]["asset_sha256"]
              and evidence["evidence_kind"]=="full_original_mp4"
              and description(evidence["scene_notes"],20,500),
              "ANALYSIS_INPUT_MISSING",src["scene_id"])
    options=proposals.get("proposals")
    check(isinstance(options,list) and len(options)==3,
          "THREE_MOTIONLAB_PROPOSALS_REQUIRED")
    names=set();signatures=set();recommended=0
    for i,option in enumerate(options,1):
        check(isinstance(option,dict) and
              set(option) in (
                  {"option","title","rationale","recommended","scenes"},
                  {"option","title","rationale","recommended","scenes","scene_layout"},
              )
              and type(option["option"]) is int and option["option"]==i
              and description(option["title"],3,90)
              and description(option["rationale"],20,800)
              and type(option["recommended"]) is bool,
              "INVALID_MOTIONLAB_PROPOSAL")
        name=option["title"].strip().casefold()
        check(name not in names,"THREE_DISTINCT_OPTIONS_REQUIRED")
        names.add(name)
        recommended+=int(option["recommended"])
        signature=validate_effects(option["scenes"],materials)
        if "scene_layout" in option:
            proposed=_validated_layout(option["scene_layout"],materials)
            _preflight_visual_collisions(proposed,materials)
            signature=signature+(canonical(proposed),)
        check(signature not in signatures,"THREE_DISTINCT_OPTIONS_REQUIRED")
        signatures.add(signature)
    check(recommended==1,"EXACTLY_ONE_RECOMMENDED_REQUIRED")
    return {"status":"MOTIONLAB_THREE_PROPOSALS_VALIDATED",
            "materials_sha256":digest(materials),
            "proposals_sha256":digest(proposals),
            "analysis_attestation_crosschecked":True,
            "actual_agent_video_review_proven_by_code":False,
            "paid_calls":0,"render_started":False}


def validate_selection_v2(materials,proposals,selection):
    report=validate_proposals_v2(materials,proposals)
    check(isinstance(selection,dict) and selection.get("schema")==SELECTION
          and set(selection) in (
              {
                  "schema","project_id","request_id","expected_input_fingerprint",
                  "materials_sha256","proposals_sha256","format","decision",
                  "guards","scenes","next_stage",
              },
              {
                  "schema","project_id","request_id","expected_input_fingerprint",
                  "materials_sha256","proposals_sha256","format","decision",
                  "guards","scenes","next_stage","scene_layout",
              },
          )
          and selection.get("project_id")==materials["project_id"]
          and selection.get("request_id")==materials["request_id"]
          and selection.get("expected_input_fingerprint")==
              materials["expected_input_fingerprint"]
          and selection.get("materials_sha256")==report["materials_sha256"]
          and selection.get("proposals_sha256")==report["proposals_sha256"]
          and selection.get("format")=="9:16"
          and selection.get("next_stage")=="MONTAGE_PLANNING_REVIEW",
          "MOTIONLAB_SELECTION_INVALID_OR_STALE")
    decision=selection.get("decision")
    check(isinstance(decision,dict)
          and type(decision.get("selected_option")) is int
          and decision["selected_option"] in (1,2,3)
          and decision.get("options_presented")==3
          and decision.get("state")=="USER_SELECTED_IN_CONNECTED_SESSION"
          and decision.get("explicit_approval") is True
          and type(decision.get("visual_layout_edited")) is bool,
          "EXPLICIT_USER_APPROVAL_REQUIRED")
    try:
        instant=datetime.fromisoformat(decision["user_selected_at"].replace("Z","+00:00"))
        age=(datetime.now(timezone.utc)-instant.astimezone(timezone.utc)).total_seconds()
        if not -300<=age<=7*86400:
            raise ValueError()
    except (KeyError,TypeError,ValueError,AttributeError):
        raise r.ContractError("EXPLICIT_USER_APPROVAL_REQUIRED") from None
    guards=selection.get("guards")
    check(isinstance(guards,dict)
          and all(guards.get(k) is False for k in (
              "run_render","run_tts","run_a2e","run_paid_operations","auto_publish"))
          and all(guards.get(k) is True for k in (
              "preserve_approved_voice","preserve_approved_music",
              "preserve_approved_narration")),
          "UNAUTHORIZED_EXECUTION_GUARDS")
    validate_effects(selection.get("scenes"),materials)
    edited=decision["visual_layout_edited"]
    chosen=proposals["proposals"][decision["selected_option"]-1]
    proposed=chosen.get("scene_layout")
    provided=selection.get("scene_layout")
    if provided is None:
        check(not edited and proposed is None,
              "VISUAL_LAYOUT_MISSING_FROM_SELECTION")
    else:
        actual=_validated_layout(provided,materials)
        _preflight_visual_collisions(actual,materials)
        if not edited:
            expected=_validated_layout(proposed,materials) if proposed is not None else _defaults_layout(materials)
            check(actual==expected,
                  "VISUAL_LAYOUT_CHANGE_NOT_APPROVED")
    report.update({
        "visual_layout_present":provided is not None,
        "visual_layout_edited":edited,
        "status":"V2_SELECTION_VALIDATED_NOT_WRITTEN",
        "receipt_id":"motionlab:v2:"+digest(selection),
        "selected_option":decision["selected_option"],
        "explicit_approval_recorded":True,
        "project_written":False,"spec_written":False,
        "render_authorized":False,"publication_authorized":False,
    })
    return report


def map_selection_v2_to_spec(materials,proposals,selection,approved_spec,
                             verified_media,job_dir,probe=None):
    """No legacy v1 fabricated options; maps edited v2 choice directly."""
    report=validate_selection_v2(materials,proposals,selection)
    check(isinstance(approved_spec,dict)
          and isinstance(verified_media,list)
          and isinstance(approved_spec.get("scenes"),list)
          and len(approved_spec["scenes"])==len(verified_media)==len(materials["scenes"]),
          "APPROVED_VIDEO_SPEC_REQUIRED")
    check(digest({"voice":approved_spec.get("voice"),
                  "music":approved_spec.get("music")})==
          materials.get("approved_audio_sha256"),"APPROVED_AUDIO_CHANGED")
    result=copy.deepcopy(approved_spec)
    probe=probe or r._ffprobe
    for i,(src,edited,base,asset) in enumerate(zip(
            materials["scenes"],selection["scenes"],result["scenes"],verified_media)):
        sid=src["scene_id"]
        check(asset.get("asset_id")==src["asset_id"],"SOURCE_BINDING_CHANGED",sid)
        current=checked_mp4(sid,asset,base,job_dir,probe)
        expected=src["media"]
        check(current["asset_sha256"]==expected["asset_sha256"]
              and abs(current["duration_s"]-expected["duration_s"])<=r.TRIM_TOLERANCE
              and current["width"]==expected["width"]
              and current["height"]==expected["height"]
              and current["has_audio"]==expected["has_audio"],
              "MISSING_OR_INVALID_MEDIA_BINDING",sid)
        check("in" not in base and "out" not in base,
              "TRIM_REQUIRES_V2_EXTENSION",sid)
        check("visualLayout" not in base,
              "UNAPPROVED_LAYOUT_ALREADY_PRESENT",sid)
        check((base.get("title") or "")==src["locked"]["title_text"],
              "IMMUTABLE_TEXT_CHANGED",sid)
        lines=base.get("lines",[])
        check(isinstance(lines,list) and
              all(isinstance(x,dict) and isinstance(x.get("text"),str) for x in lines)
              and " ".join(x["text"] for x in lines).strip()==src["locked"]["subtitle_preview"],
              "IMMUTABLE_TEXT_CHANGED",sid)
        base["move"]="none"
        base["cameraEffect"]={"id":edited["camera"]["id"],
                              "intensity_percent":edited["camera"]["intensity_percent"]}
        base["titleEffect"]=edited["title_fx"]
        if "scene_layout" in selection:
            base["visualLayout"]=copy.deepcopy(
                selection["scene_layout"][i]["layout"])
        if edited["title_fx"]=="none":
            base.pop("title",None)
        if i==0:
            base.pop("transition",None)
        else:
            base["transition"]=copy.deepcopy(edited["transition"])
    style,motion=next(iter({
        (item["subtitle"]["style_id"],item["subtitle"]["word_motion_id"])
        for item in selection["scenes"]
    }))
    existing=approved_spec.get("subtitleStyle") or {}
    check(isinstance(existing,dict),"INVALID_APPROVED_SUBTITLE")
    subtitle={
        "style":style,"motion":motion,
        "color":existing.get("color","gold"),
        "position":existing.get("position","bottom"),
        "scale_percent":existing.get("scale_percent",100),
    }
    check(subtitle["color"] in make_video.SUBTITLE_COLORS
          and subtitle["position"] in make_video.SUBTITLE_POSITIONS
          and type(subtitle["scale_percent"]) is int
          and 80<=subtitle["scale_percent"]<=135,
          "INVALID_APPROVED_SUBTITLE")
    result["subtitleStyle"]=subtitle
    report.update({
        "status":"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED",
        "renderer_revision_sha256":r.revision(),
        "scene_count":len(result["scenes"]),
        "preapproved_wav_reuse_verified":False,
        "total_timeline_verified":False,
        "render_authorized":False,
    })
    return result,report
