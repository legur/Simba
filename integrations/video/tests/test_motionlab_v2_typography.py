"""Renderer-owned v2 typography: only explicitly approved, source-pinned values render."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from test_motionlab_v2_contract import V2ContractTests
import make_video
import motionlab_v2_contract as v2


class TypographyV2Tests(unittest.TestCase):
    def setUp(self):
        f=V2ContractTests("test_materials_launch_without_creative_options")
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.f=f

    def enable_typography(self):
        self.f.selection["global_theme"]={"typography":{
            "title":{"family":"Georgia","color":"#ABCDEF","size":105},
            "subtitle":{"family":"Arial","color":"#ffffff","size":100},
        }}
        self.f.selection["scene_typography"]=[
            {"scene_id":s["scene_id"],"asset_id":s["asset_id"],
             "typography":({"title":{"family":"Arial","color":"#123456","size":110}}
                           if i==1 else {})}
            for i,s in enumerate(self.f.materials["scenes"])]

    def test_inherited_and_overridden_scene_settings_pass_into_timeline(self):
        self.enable_typography()
        raw=copy.deepcopy(self.f.spec)
        result, report=self.f.mapped()
        self.assertTrue(report["visual_typography_present"])
        self.assertFalse(report["render_authorized"])
        self.assertEqual(result["scenes"][0]["visualTypography"]["title"],
                         {"family":"Georgia","color":"#abcdef","size":105})
        self.assertEqual(result["scenes"][1]["visualTypography"]["title"],
                         {"family":"Arial","color":"#123456","size":110})
        self.assertEqual(result["scenes"][1]["visualTypography"]["subtitle"]["family"],"Arial")
        self.assertEqual(self.f.spec,raw)
        (self.f.job/"video-spec.json").write_text(json.dumps(result,ensure_ascii=False))
        verified=make_video.load_spec(self.f.job)
        self.assertEqual(verified["scenes"][1]["visualTypography"]["title"]["size"],110)
        video_timeline=make_video.timeline(verified)
        self.assertEqual(video_timeline["scenes"][1]["visualTypography"]["title"]["color"],"#123456")

    def test_missing_half_selection_blocks(self):
        self.enable_typography()
        del self.f.selection["scene_typography"]
        self.f.blocked("MOTIONLAB_SELECTION_INVALID_OR_STALE")

    def test_unsupported_font_or_foreign_asset_blocks(self):
        self.enable_typography()
        self.f.selection["scene_typography"][1]["asset_id"]="wrong"
        self.f.blocked("TYPOGRAPHY_SOURCE_MISMATCH")
        self.f.selection["scene_typography"][1]["asset_id"]=self.f.materials["scenes"][1]["asset_id"]
        self.f.selection["global_theme"]["typography"]["title"]["family"]="Unknown font"
        self.f.blocked("UNSUPPORTED_TYPOGRAPHY")

    def test_unapproved_upstream_typography_rejected(self):
        self.enable_typography()
        self.f.spec["scenes"][0]["visualTypography"]=self.f.selection["global_theme"]["typography"]
        self.f.blocked("UNAPPROVED_TYPOGRAPHY_ALREADY_PRESENT")

    def test_invalid_raw_spec_typography_fails_closed(self):
        self.f.spec["scenes"][0]["visualTypography"]={
            "title":{"family":"Arial","color":"not-color","size":100},
            "subtitle":{"family":"Georgia","color":"#ffffff","size":100}}
        (self.f.job/"video-spec.json").write_text(json.dumps(self.f.spec))
        with self.assertRaises(make_video.Stop) as cm:
            make_video.load_spec(self.f.job)
        self.assertIn("UNSUPPORTED_TYPOGRAPHY",str(cm.exception))


if __name__=="__main__":
    unittest.main()
