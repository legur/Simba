"""Cross-stage 3/10/15/24/25-scene regression. Synthetic MP4, no providers.

The project may reuse original A2E assets. An additional scene never implies
a new source file or silently changes approved voice, text or media.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
import unittest

VIDEO=Path(__file__).resolve().parents[1]
ROOT=VIDEO.parents[1]
sys.path.insert(0,str(VIDEO))
import make_video
import motionlab_scene_contract as limits
import motionlab_render_contract as render
import motionlab_v2_contract as v2


class CrossStageSceneCountTests(unittest.TestCase):
    def fixture(self):
        # Reuse existing source-pinned fixture with TWO synthetic approved MP4s.
        from test_motionlab_v2_contract import V2ContractTests
        fx=V2ContractTests("test_materials_launch_without_creative_options")
        fx.setUp()
        self.addCleanup(fx.doCleanups)
        return fx

    def spec_for(self,fx,count,seconds=None):
        spec=copy.deepcopy(fx.spec)
        seconds=seconds if seconds is not None else min(3.0,52.0/count)
        spec["scenes"]=[]
        for i in range(count):
            clip=fx.asset[i%len(fx.asset)]
            spec["scenes"].append({
                "scene_id":f"test-{i+1:02d}",
                "source_asset_id":clip["asset_id"],
                "scene_name":f"Approved scene {i+1}",
                "scene_duration_s":seconds,
                "source_playback":"freeze",
                "clip":clip["file"],"move":"none",
                "title":f"Approved title {i+1}",
                "lines":[{"text":f"Approved speech for scene {i+1}"}],
            })
        return spec

    def data_for(self,fx,count):
        spec=self.spec_for(fx,count)
        materials=v2.make_materials_v2(
            "dynamic-scenes-test","scene-count-request","a"*64,
            spec,fx.asset,fx.job,probe=fx.probe)
        proposals=copy.deepcopy(fx.proposals)
        proposals["project_id"]=materials["project_id"]
        proposals["request_id"]=materials["request_id"]
        proposals["expected_input_fingerprint"]=materials["expected_input_fingerprint"]
        proposals["materials_sha256"]=v2.digest(materials)
        proposals["renderer_revision_sha256"]=render.revision()
        proposals["analysis"]["inspected_assets"]=[
            {"scene_id":scene["scene_id"],
             "asset_sha256":scene["media"]["asset_sha256"],
             "evidence_kind":"full_original_mp4",
             "scene_notes":"Synthetic source metadata test; not a real visual review."}
            for scene in materials["scenes"]
        ]
        for option in proposals["proposals"]:
            template=copy.deepcopy(option["scenes"][0])
            trans={"id":{1:"crossfade",2:"postcard",3:"whip"}[option["option"]],
                   "duration_ms":900}
            option["scenes"]=[
                {**copy.deepcopy(template),"scene_id":s["scene_id"],
                 "transition":None if i==0 else copy.deepcopy(trans)}
                for i,s in enumerate(materials["scenes"])
            ]
        chosen=copy.deepcopy(fx.selection)
        chosen["project_id"]=materials["project_id"]
        chosen["request_id"]=materials["request_id"]
        chosen["expected_input_fingerprint"]=materials["expected_input_fingerprint"]
        chosen["materials_sha256"]=v2.digest(materials)
        chosen["proposals_sha256"]=v2.digest(proposals)
        chosen["scenes"]=copy.deepcopy(proposals["proposals"][0]["scenes"])
        return spec,materials,proposals,chosen

    def test_dynamic_scene_count_across_source_to_verified_selection_to_spec(self):
        for count in (3,10,15,24):
            with self.subTest(count=count):
                fx=self.fixture()
                spec,materials,proposals,selection=self.data_for(fx,count)
                self.assertEqual(materials["renderer_capabilities"]["max_scenes"],24)
                self.assertEqual(len(materials["scenes"]),count)
                self.assertEqual(len({s["asset_id"] for s in materials["scenes"]}),2)
                self.assertEqual(len(proposals["proposals"]),3)
                self.assertEqual(sum(
                    e["transition"] is not None for e in selection["scenes"]),count-1)
                receipt=v2.validate_selection_v2(materials,proposals,selection)
                self.assertFalse(receipt["render_authorized"])
                self.assertFalse(receipt["publication_authorized"])
                mapped,report=v2.map_selection_v2_to_spec(
                    materials,proposals,selection,spec,
                    fx.asset,fx.job,probe=fx.probe)
                self.assertEqual(report["status"],"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED")
                self.assertFalse(report["render_authorized"])
                self.assertEqual(len(mapped["scenes"]),count)
                self.assertEqual(len([s for s in mapped["scenes"] if "transition" in s]),count-1)
                self.assertEqual([s["title"] for s in mapped["scenes"]],
                                 [s["title"] for s in spec["scenes"]])
                self.assertEqual([s["clip"] for s in mapped["scenes"]],
                                 [s["clip"] for s in spec["scenes"]])
                self.assertEqual(mapped["voice"],spec["voice"])
                self.assertEqual(mapped["music"],spec["music"])
                self.assertTrue(all(x["run_paid_operations"] is False
                                    for x in [selection["guards"]]))

    def test_25_scenes_and_zero_scenes_are_rejected_before_any_video_io(self):
        fx=self.fixture()
        for count in (0,25):
            with self.subTest(count=count),self.assertRaises(render.ContractError) as c:
                v2.make_materials_v2(
                    "dynamic-scenes-test","scene-count-request","a"*64,
                    self.spec_for(fx,count),fx.asset,fx.job,probe=fx.probe)
            self.assertEqual(c.exception.code,"INVALID_SCENE_COUNT")
            self.assertEqual(c.exception.report()["paid_calls"],0)

    def test_15_full_five_second_scenes_reject_over_60s_without_trimming(self):
        fx=self.fixture()
        with self.assertRaises(render.ContractError) as exc:
            v2.make_materials_v2(
                "dynamic-scenes-test","scene-count-request","a"*64,
                self.spec_for(fx,15,seconds=5.0),
                fx.asset,fx.job,probe=fx.probe)
        self.assertEqual(exc.exception.code,"VIDEO_DURATION_LIMIT_EXCEEDED")
        self.assertEqual(exc.exception.report()["render_started"],False)

    def test_generic_renderer_spec_accepts_15_or_24_as_scene_count(self):
        fx=self.fixture()
        for count in (3,10,15,24):
            payload={"packageId":"synthetic-no-render",
                     "sourcePost":"approved-copy-source.md",
                     "scenes":[{"clip":"not-present.mp4"} for _ in range(count)]}
            (fx.job/"video-spec.json").write_text(json.dumps(payload),encoding="utf-8")
            with self.subTest(count=count),self.assertRaises(make_video.Stop) as stop:
                make_video.load_spec(fx.job)
            self.assertIn("file not found",str(stop.exception))
            self.assertNotIn("scenes:",str(stop.exception))
        payload["scenes"]=[{"clip":"not-present.mp4"} for _ in range(25)]
        (fx.job/"video-spec.json").write_text(json.dumps(payload),encoding="utf-8")
        with self.assertRaisesRegex(make_video.Stop,"scenes: 1–24 scenes"):
            make_video.load_spec(fx.job)

    def test_backend_editor_and_gas_scene_caps_never_diverge(self):
        self.assertEqual((limits.MIN_SCENES,limits.MAX_SCENES),(1,24))
        self.assertEqual(render.MAX_SCENES,limits.MAX_SCENES)
        self.assertEqual(render.renderer_capabilities()["max_film_seconds"],limits.MAX_FILM_SECONDS)
        self.assertEqual(limits.transitions_for_scene_count(15),14)
        paths={
            "studio_v1":(ROOT/"integrations/materials/motionlab/storyboard.js",r"const LIMIT\s*=\s*(\d+)\s*;"),
            "studio_v2":(ROOT/"integrations/materials/motionlab/studio-v2.js",r"const MAX_SCENES\s*=\s*(\d+)\s*;"),
            "gas_v1":(ROOT/"integrations/materials/motionlab/drive_handoff/Code.gs",r"maxScenes:\s*(\d+)\s*,"),
            "gas_v2":(ROOT/"integrations/materials/motionlab/drive_handoff/CodeV2.gs",r"maxScenes:\s*(\d+)\s*[\n,}]"),
            "v1_ticket":(ROOT/"integrations/materials/motionlab/drive_handoff/issue_ticket.py",r"MAX_SCENES\s*=\s*(\d+)\s*\n"),
        }
        for component,(path,pattern) in paths.items():
            with self.subTest(component=component):
                data=path.read_text(encoding="utf-8")
                match=re.search(pattern,data)
                self.assertIsNotNone(match,f"missing scene-limit constant in {path}")
                self.assertEqual(int(match.group(1)),limits.MAX_SCENES)


if __name__=="__main__":
    unittest.main()
