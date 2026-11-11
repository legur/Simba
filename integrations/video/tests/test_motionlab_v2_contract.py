"""Draft v2 handoff: Montage provides media only; Motion Lab authors options.

Synthetic bytes in tests stand for private MP4 (real ffprobe exercised by the
separate existing renderer test). No uploads, ChatGPT calls, TTS or render.
"""
from __future__ import annotations

import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import motionlab_v2_contract as v2
import motionlab_render_contract as renderer
import make_video


def effects(cam="cinematic-zoom",pct=30,transition="crossfade",title="fade-rise",
            subtitle="clean", motion="karaoke",first=False):
    return {"camera":{"id":cam,"intensity_percent":pct},
            "transition":None if first else {"id":transition,"duration_ms":900},
            "title_fx":title,
            "subtitle":{"style_id":subtitle,"word_motion_id":motion}}


class V2ContractTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.job=Path(self.t.name)
        # Synthetic nonzero fixture: load_spec only checks file existence and
        # rights flag. This is NOT a licensed track or playable music.
        (self.job/"owner-cleared-music.mp3").write_bytes(b"synthetic-test-not-real-audio")
        self.asset=[]
        self.spec={
            "packageId":"v2-demo","size":"1080x1920",
            "sourcePost":"approved-copy-source.md",
            "voice":{"source":"existing_approved_wav"},
            "music":{"file":"owner-cleared-music.mp3","rights_confirmed":True},
            "end":{"brand":"Bon Tours","cta":"Готовый подтвержденный CTA"},
            "scenes":[],
        }
        for n in (1,2):
            fname=f"clip-{n}.mp4"
            raw=("synthetic-byte-source-%s"%n).encode()
            (self.job/fname).write_bytes(raw)
            sha=hashlib.sha256(raw).hexdigest()
            self.asset.append({"scene_id":f"scene-{n}","asset_id":f"a2e-{n}",
                               "file":fname,"sha256":sha,"duration_s":5.0})
            self.spec["scenes"].append({
                "clip":fname,"title":f"Титр №{n}",
                "move":"none","lines":[{"text":f"Озвучка сцены {n}"}],
            })
        self.materials=v2.make_materials_v2(
            "sample-project","request-v2-001","a"*64,
            self.spec,self.asset,self.job,probe=self.probe)
        scene_ids=[x["scene_id"] for x in self.materials["scenes"]]
        def proposal(option:int,cam:str,pct:int,transition:str):
            return {
                "option":option,"title":f"Концепция {option} Motion Lab",
                "rationale":f"Motion Lab reviewed actual verified media for style {option} and scene-cut design.",
                "recommended":option==1,
                "scenes":[dict(scene_id=sid,**effects(
                    cam=cam,pct=pct,transition=transition,first=(i==0)))
                    for i,sid in enumerate(scene_ids)],
            }
        self.proposals={
            "schema":v2.PROPOSALS,"project_id":self.materials["project_id"],
            "request_id":self.materials["request_id"],
            "expected_input_fingerprint":self.materials["expected_input_fingerprint"],
            "materials_sha256":v2.digest(self.materials),
            "renderer_revision_sha256":renderer.revision(),
            "analysis":{
                "status":"REAL_VIDEO_REVIEWED",
                "access_mode":"owner_private_material_bundle",
                "review_notes":"Synthetic attestation only for offline test of private media contract.",
                "inspected_assets":[{
                    "scene_id":s["scene_id"],
                    "asset_sha256":s["media"]["asset_sha256"],
                    "evidence_kind":"full_original_mp4",
                    "scene_notes":"Synthetic unit-test inspection note, not actual visual model analysis.",
                } for s in self.materials["scenes"]],
            },
            "proposals":[
                proposal(1,"cinematic-zoom",30,"crossfade"),
                proposal(2,"float",40,"postcard"),
                proposal(3,"push-through",55,"whip"),
            ],
        }
        self.selection={
            "schema":v2.SELECTION,"project_id":self.materials["project_id"],
            "request_id":self.materials["request_id"],
            "expected_input_fingerprint":self.materials["expected_input_fingerprint"],
            "materials_sha256":v2.digest(self.materials),
            "proposals_sha256":v2.digest(self.proposals),
            "format":"9:16","next_stage":"MONTAGE_PLANNING_REVIEW",
            "decision":{
                "selected_option":1,"options_presented":3,
                "state":"USER_SELECTED_IN_CONNECTED_SESSION",
                "explicit_approval":True,
                "user_selected_at":datetime.now(timezone.utc).isoformat(),
            },
            "guards":{
                "run_render":False,"run_tts":False,"run_a2e":False,
                "run_paid_operations":False,"auto_publish":False,
                "preserve_approved_voice":True,
                "preserve_approved_music":True,
                "preserve_approved_narration":True,
            },
            "scenes":copy.deepcopy(self.proposals["proposals"][0]["scenes"]),
        }

    def probe(self,filename):
        return {"duration_s":5.0,"width":1080,"height":1920,
                "has_audio":False}

    def mapped(self):
        return v2.map_selection_v2_to_spec(
            self.materials,self.proposals,self.selection,
            self.spec,self.asset,self.job,probe=self.probe)

    def blocked(self,code):
        with self.assertRaises(renderer.ContractError) as raised:
            self.mapped()
        self.assertEqual(raised.exception.code,code)
        self.assertFalse(raised.exception.report()["render_started"])
        self.assertEqual(raised.exception.report()["paid_calls"],0)

    def test_materials_launch_without_creative_options(self):
        self.assertEqual(self.materials["schema"],v2.MATERIALS)
        self.assertNotIn("options",self.materials)
        self.assertNotIn("proposals",self.materials)
        self.assertEqual(len(self.materials["scenes"]),2)
        self.assertEqual(self.materials["scenes"][0]["media"]["duration_s"],5.0)
        self.assertEqual(self.materials["analysis"]["status"],"PENDING_REAL_MEDIA_ACCESS")
        self.assertEqual(self.materials["constraints"]["allow_paid_operations"],False)
        self.assertEqual(self.materials["constraints"]["allow_publish"],False)
        self.assertNotIn("drive_file_id",json.dumps(self.materials))

    def test_three_motionlab_authored_proposals_and_user_approval_to_zero_paid_mapper(self):
        proposal_check=v2.validate_proposals_v2(self.materials,self.proposals)
        self.assertTrue(proposal_check["analysis_attestation_crosschecked"])
        self.assertFalse(proposal_check["actual_agent_video_review_proven_by_code"])
        self.assertEqual(v2.validate_selection_v2(
            self.materials,self.proposals,self.selection)["selected_option"],1)
        before=copy.deepcopy(self.spec)
        spec,report=self.mapped()
        self.assertEqual(report["status"],"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED")
        self.assertEqual(report["paid_calls"],0)
        self.assertFalse(report["project_written"])
        self.assertFalse(report["spec_written"])
        self.assertFalse(report["render_authorized"])
        self.assertFalse(report["preapproved_wav_reuse_verified"])
        self.assertEqual(report["scene_count"],2)
        self.assertEqual(self.spec,before)
        self.assertEqual(spec["voice"],before["voice"])
        self.assertEqual(spec["music"],before["music"])
        self.assertEqual(spec["sourcePost"],before["sourcePost"])
        self.assertEqual(spec["scenes"][0]["cameraEffect"]["id"],"cinematic-zoom")
        self.assertEqual(spec["scenes"][1]["transition"]["id"],"crossfade")
        self.assertEqual(spec["scenes"][0]["titleEffect"],"fade-rise")
        self.assertEqual(spec["subtitleStyle"]["style"],"clean")
        (self.job/"video-spec.json").write_text(json.dumps(spec,ensure_ascii=False))
        parsed=make_video.load_spec(self.job)
        self.assertEqual(parsed["scenes"][0]["cameraEffect"]["id"],"cinematic-zoom")

    def test_no_agent_video_evidence_blocks_proposals(self):
        self.proposals["analysis"]["status"]="ANALYSIS_INPUT_MISSING"
        self.blocked("ANALYSIS_INPUT_MISSING")
        self.proposals["analysis"]["status"]="REAL_VIDEO_REVIEWED"
        self.proposals["analysis"]["inspected_assets"][0]["asset_sha256"]="f"*64
        self.blocked("ANALYSIS_INPUT_MISSING")

    def test_proposal_source_sha_revision_and_recommendation_locked(self):
        self.proposals["materials_sha256"]="f"*64
        self.blocked("MOTIONLAB_PROPOSALS_STALE")
        self.proposals["materials_sha256"]=v2.digest(self.materials)
        self.proposals["renderer_revision_sha256"]="f"*64
        self.blocked("MOTIONLAB_PROPOSALS_STALE")
        self.proposals["renderer_revision_sha256"]=renderer.revision()
        self.proposals["proposals"][1]["recommended"]=True
        self.blocked("EXACTLY_ONE_RECOMMENDED_REQUIRED")

    def test_three_unique_effect_signatures_no_placeholder_options(self):
        self.proposals["proposals"][1]["scenes"]=copy.deepcopy(
            self.proposals["proposals"][0]["scenes"])
        self.blocked("THREE_DISTINCT_OPTIONS_REQUIRED")

    def test_unsupported_camera_and_title_and_transition_rejected(self):
        self.selection["scenes"][0]["camera"]["id"]="orbit"
        self.blocked("UNSUPPORTED_CAMERA_EFFECT")
        self.selection["scenes"][0]["camera"]["id"]="cinematic-zoom"
        self.selection["scenes"][0]["title_fx"]="punch-zoom"
        self.blocked("UNSUPPORTED_TITLE_EFFECT")
        self.selection["scenes"][0]["title_fx"]="fade-rise"
        self.selection["scenes"][1]["transition"]["id"]="none"
        self.blocked("UNSUPPORTED_TRANSITION")

    def test_global_subtitles_reject_distinct_per_scene_styles(self):
        self.selection["scenes"][1]["subtitle"]["style_id"]="luxury"
        self.blocked("UNSUPPORTED_PER_SCENE_SUBTITLE")

    def test_no_media_text_trim_or_source_id_override_in_selection(self):
        self.selection["scenes"][0]["title_text"]="Новая цена"
        self.blocked("SCENE_BINDING_MISMATCH")
        del self.selection["scenes"][0]["title_text"]
        self.selection["scenes"][1]["scene_id"]="wrong-scene"
        self.blocked("SCENE_BINDING_MISMATCH")
        self.selection["scenes"][1]["scene_id"]="scene-2"
        self.spec["scenes"][1]["in"]=2
        self.blocked("TRIM_REQUIRES_V2_EXTENSION")
        del self.spec["scenes"][1]["in"]
        self.spec["scenes"][0]["title"]="Подмененная цена"
        self.blocked("IMMUTABLE_TEXT_CHANGED")

    def test_no_paid_guard_and_explicit_approval_mandatory(self):
        self.selection["decision"]["explicit_approval"]=False
        self.blocked("EXPLICIT_USER_APPROVAL_REQUIRED")
        self.selection["decision"]["explicit_approval"]=True
        self.selection["guards"]["run_a2e"]=True
        self.blocked("UNAUTHORIZED_EXECUTION_GUARDS")
        self.selection["guards"]["run_a2e"]=False
        self.selection["decision"]["state"]="DRAFT_NOT_DELIVERED"
        self.blocked("EXPLICIT_USER_APPROVAL_REQUIRED")

    def test_local_mp4_full_sha_not_just_preview(self):
        (self.job/"clip-1.mp4").write_bytes(b"byte-tamper")
        self.blocked("MEDIA_SHA256_MISMATCH")

    def test_audio_lock_and_capability_revision(self):
        self.spec["voice"]["provider"]="new-unapproved-TTS"
        self.blocked("APPROVED_AUDIO_CHANGED")
        self.spec["voice"]={"source":"existing_approved_wav"}
        self.materials["renderer_capabilities"]["revision_sha256"]="0"*64
        self.blocked("RENDERER_CAPABILITIES_MISSING_OR_STALE")


if __name__=="__main__":
    unittest.main()
