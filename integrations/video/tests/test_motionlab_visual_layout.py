"""Montage visual WYSIWYG geometry; source-bound v2 approval and fail-closed tests.

Exercises public preview PR117's per-scene title/subtitle percentages without
editing internal Motion Lab code or starting A2E/TTS/video rendering.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import make_video
import motionlab_layout_contract as geometry
import motionlab_v2_contract as v2
import motionlab_render_contract as r
from test_motionlab_v2_contract import V2ContractTests


class WysiwygMontageContracts(unittest.TestCase):
    def setUp(self):
        f=V2ContractTests("test_materials_launch_without_creative_options")
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.f=f

    def layout(self,title=None,subtitle=None):
        title=title or {"x":55,"y":42,"scale":110}
        subtitle=subtitle or {"x":45,"y":80,"scale":90}
        return [{
            "scene_id":m["scene_id"],
            "asset_id":m["asset_id"],
            "layout":{"title":copy.deepcopy(title),"subtitle":copy.deepcopy(subtitle)},
        } for m in self.f.materials["scenes"]]

    def set_user_layout(self):
        self.f.selection["scene_layout"]=self.layout()
        self.f.selection["decision"]["visual_layout_edited"]=True

    def test_exact_layout_from_visual_editor_maps_to_spec_and_timeline(self):
        self.set_user_layout()
        orig=copy.deepcopy(self.f.spec)
        result,diagnostic=self.f.mapped()
        self.assertTrue(diagnostic["visual_layout_present"])
        self.assertTrue(diagnostic["visual_layout_edited"])
        self.assertFalse(diagnostic["render_authorized"])
        self.assertFalse(diagnostic["spec_written"])
        self.assertEqual(result["scenes"][0]["visualLayout"],
                         self.f.selection["scene_layout"][0]["layout"])
        self.assertEqual(result["scenes"][0]["title"],orig["scenes"][0]["title"])
        self.assertEqual(result["scenes"][1]["lines"],orig["scenes"][1]["lines"])
        self.assertEqual(result["voice"],orig["voice"])
        self.assertEqual(result["music"],orig["music"])
        self.assertEqual(self.f.spec,orig)
        (self.f.job/"video-spec.json").write_text(json.dumps(result,ensure_ascii=False))
        loaded=make_video.load_spec(self.f.job)
        self.assertEqual(loaded["scenes"][0]["visualLayout"]["title"]["x"],55)
        self.assertEqual(loaded["scenes"][1]["visualLayout"]["subtitle"]["y"],80)

    def test_missing_edit_payload_never_becomes_approved(self):
        self.f.selection["decision"]["visual_layout_edited"]=True
        self.f.blocked("VISUAL_LAYOUT_MISSING_FROM_SELECTION")
        self.set_user_layout()
        self.f.selection["decision"]["visual_layout_edited"]=False
        self.f.blocked("VISUAL_LAYOUT_CHANGE_NOT_APPROVED")
        self.f.selection["decision"]["visual_layout_edited"]=True
        self.f.selection["decision"]["explicit_approval"]=False
        self.f.blocked("EXPLICIT_USER_APPROVAL_REQUIRED")

    def test_stolen_clip_and_malformed_coords_and_collision_block(self):
        self.set_user_layout()
        scene=self.f.selection["scene_layout"][0]
        scene["asset_id"]="foreign-asset"
        self.f.blocked("SCENE_LAYOUT_BINDING_MISMATCH")
        scene["asset_id"]=self.f.materials["scenes"][0]["asset_id"]
        scene["layout"]["title"]["x"]=99
        self.f.blocked("UNSAFE_VISUAL_LAYOUT")
        scene["layout"]["title"]["x"]=55
        scene["layout"]["title"]["scale"]=73
        self.f.blocked("UNSAFE_VISUAL_LAYOUT")
        scene["layout"]["title"]["scale"]=110
        scene["layout"]["subtitle"]["y"]=48
        self.f.blocked("VISUAL_LAYOUT_TEXT_COLLISION")
        scene["layout"]["subtitle"]["y"]=80
        self.f.selection["offer_layout"]={"x":50,"y":50,"scale":100}
        self.f.blocked("MOTIONLAB_SELECTION_INVALID_OR_STALE")

    def test_proposed_layout_requires_exact_forwarding_without_new_edit(self):
        shown=self.layout(title={"x":52,"y":44,"scale":100},
                          subtitle={"x":48,"y":81,"scale":100})
        self.f.proposals["proposals"][0]["scene_layout"]=shown
        self.f.selection["proposals_sha256"]=v2.digest(self.f.proposals)
        self.f.blocked("VISUAL_LAYOUT_MISSING_FROM_SELECTION")
        self.f.selection["scene_layout"]=copy.deepcopy(shown)
        mapped,report=self.f.mapped()
        self.assertEqual(mapped["scenes"][0]["visualLayout"]["title"]["x"],52)
        self.assertFalse(report["visual_layout_edited"])
        self.f.selection["scene_layout"][0]["layout"]["title"]["x"]=54
        self.f.blocked("VISUAL_LAYOUT_CHANGE_NOT_APPROVED")
        self.f.selection["decision"]["visual_layout_edited"]=True
        mapped,_=self.f.mapped()
        self.assertEqual(mapped["scenes"][0]["visualLayout"]["title"]["x"],54)

    def test_layout_schema_matches_current_ui_draft_and_denies_card_layout(self):
        cap=r.renderer_capabilities()["visual_layout"]
        self.assertEqual(cap["coordinate_space"],"full_frame_percent_9x16")
        self.assertEqual(cap["anchor"],"center")
        self.assertEqual(cap["max_wrap_width_percent"],72)
        self.assertEqual(cap["scale"]["max"],140)
        self.assertEqual(cap["offer_card"],"not_renderable")
        self.assertEqual(cap["end_card"],"not_renderable")
        ui=(ROOT.parent/"materials"/"motionlab"/"visual_editor.js").read_text()
        self.assertIn("x:50,y:47,scale:100",ui)
        self.assertIn("x:50,y:82,scale:100",ui)
        self.assertIn("schema:'bontours.motionlab.visual-layout-draft/v2'",ui)
        self.assertIn("scene_layout:state.scenes.map",ui)

    def test_direct_video_spec_cannot_bypass_layout_checks(self):
        raw={"x":50,"y":47,"scale":100}
        invalid_layout={"title":dict(raw),"subtitle":dict(raw)}
        invalid_layout["title"]["scale"]=143
        self.f.spec["scenes"][0]["visualLayout"]=invalid_layout
        (self.f.job/"video-spec.json").write_text(json.dumps(self.f.spec))
        with self.assertRaises(make_video.Stop) as e:
            make_video.load_spec(self.f.job)
        self.assertIn("UNSAFE_VISUAL_LAYOUT",str(e.exception))

    def test_v2_layout_cannot_replace_existing_upstream_visual_approval(self):
        self.set_user_layout()
        self.f.spec["scenes"][0]["visualLayout"]=self.f.selection["scene_layout"][0]["layout"]
        self.f.blocked("UNAPPROVED_LAYOUT_ALREADY_PRESENT")


if __name__=="__main__":
    unittest.main()
