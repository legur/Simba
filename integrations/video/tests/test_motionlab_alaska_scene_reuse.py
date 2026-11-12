"""Alaska regression: 10 approved scenes from 7 unique SHA-pinned MP4 assets.

CI uses tiny *actually decoded* synthetic FFmpeg sources. Never uploads
Alaska's private MP4s, invents a new owner approval, invokes TTS/A2E or
renders/publishes a customer video.
"""
from __future__ import annotations

import copy
from datetime import datetime,timezone
import sys
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import motionlab_v2_contract as v2
import motionlab_auto_proposals as automatic
from test_motionlab_auto_proposals import ActualPixelBasedProposalsTests


class AlaskaTenSceneReuseTests(unittest.TestCase):
    def setUp(self):
        fixture=ActualPixelBasedProposalsTests(
            "test_real_frames_measured_with_correct_source_sha_and_three_variants")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fx=fixture
        self.media=copy.deepcopy(fixture.media)  # only 2 unique original MP4s
        self.spec={
            "packageId":"alaska-test-10",
            "size":"1080x1920","sourcePost":"original-approved-text.md",
            "voice":{"source":"approved-existing-wav"},
            "music":{"file":"private-music.wav","rights_confirmed":True},
            "end":{"brand":"Bon Tours","cta":"Final owner review only"},
            "scenes":[],
        }
        for index in range(10):
            source=self.media[index%2]
            extended=index in (0,6,7,8,9)
            self.spec["scenes"].append({
                "scene_id":f"alaska-{index+1:02d}",
                "source_asset_id":source["asset_id"],
                "scene_name":f"Alaska scene {index+1}",
                "clip":source["file"],
                "scene_duration_s":5.5 if extended else 2.7,
                "source_playback":"loop" if extended else "freeze",
                "title":f"Approved title {index+1}",
                "lines":[{"text":f"Approved original line number {index+1}"}]
            })
        self.materials=v2.make_materials_v2(
            self.spec["packageId"],"alaska-reuse-real-test",
            "a"*64,self.spec,self.media,self.fx.job)
        self.proposals,self.receipt=automatic.build_automated_proposals(
            self.materials,self.media,self.fx.job)

    def selection(self):
        return {
            "schema":v2.SELECTION,
            "project_id":self.materials["project_id"],
            "request_id":self.materials["request_id"],
            "expected_input_fingerprint":self.materials["expected_input_fingerprint"],
            "materials_sha256":v2.digest(self.materials),
            "proposals_sha256":v2.digest(self.proposals),
            "format":"9:16",
            "next_stage":"MONTAGE_PLANNING_REVIEW",
            "decision":{
                "selected_option":1,"options_presented":3,
                "state":"USER_SELECTED_IN_CONNECTED_SESSION",
                "explicit_approval":True,"visual_layout_edited":False,
                "user_selected_at":datetime.now(timezone.utc).isoformat()
            },
            "guards":{
                "run_render":False,"run_tts":False,"run_a2e":False,
                "run_paid_operations":False,"auto_publish":False,
                "preserve_approved_voice":True,
                "preserve_approved_music":True,
                "preserve_approved_narration":True
            },
            "scenes":copy.deepcopy(self.proposals["proposals"][0]["scenes"])
        }

    def test_ten_scene_two_clip_reuse_decodes_actual_mp4_only_twice(self):
        self.assertEqual(len(self.media),2)
        self.assertEqual(len(self.materials["scenes"]),10)
        self.assertEqual(len(self.proposals["proposals"]),3)
        self.assertEqual(self.receipt["source_clip_count"],2)
        self.assertEqual(self.receipt["scene_count"],10)
        self.assertEqual(len(self.proposals["analysis"]["pixel_evidence"]),10)
        self.assertEqual(
            [x["asset_id"] for x in self.materials["scenes"]],
            [self.media[i%2]["asset_id"] for i in range(10)])
        self.assertEqual(
            [x["scene_duration_s"] for x in self.materials["scenes"]][:2],
            [5.5,2.7])
        self.assertEqual(self.materials["scenes"][0]["source_playback"],"loop")
        self.assertEqual(self.materials["scenes"][1]["source_playback"],"freeze")
        self.assertTrue(all(row["asset_sha256"] in
            {a["sha256"] for a in self.media}
            for row in self.proposals["analysis"]["pixel_evidence"]))
        self.assertEqual(v2.validate_proposals_v2(self.materials,self.proposals)
                         ["status"],"MOTIONLAB_THREE_PROPOSALS_VALIDATED")
        self.assertFalse(self.receipt["render_authorized"])

    def test_ten_scene_selection_maps_exact_source_playback_no_render(self):
        spec,receipt=v2.map_selection_v2_to_spec(
            self.materials,self.proposals,self.selection(),
            self.spec,self.media,self.fx.job)
        self.assertEqual(receipt["status"],"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED")
        self.assertFalse(receipt["render_authorized"])
        self.assertEqual(len(spec["scenes"]),10)
        self.assertEqual([x["clipPlayback"] for x in spec["scenes"]],
            ["loop" if i in (0,6,7,8,9) else "freeze" for i in range(10)])
        self.assertEqual(spec["scenes"][0]["clip"],self.media[0]["file"])
        self.assertEqual(spec["scenes"][6]["clip"],self.media[0]["file"])
        self.assertEqual(spec["scenes"][8]["clip"],self.media[0]["file"])

    def test_original_alaska_time_stretch_preserves_entire_clips_without_loop(self):
        # The actual approved legacy Alaska renderer uses setpts to fit the
        # whole 5.0625 s A2E source into longer/shorter narration scenes.
        spec=copy.deepcopy(self.spec)
        for scene in spec["scenes"]:
            scene["source_playback"]="stretch"
        materials=v2.make_materials_v2(self.spec["packageId"],
            "alaska-reuse-real-test","a"*64,spec,self.media,self.fx.job)
        self.assertEqual(len(materials["scenes"]),10)
        self.assertTrue(all(x["source_playback"]=="stretch"
                            for x in materials["scenes"]))
        proposals,receipt=automatic.build_automated_proposals(
            materials,self.media,self.fx.job)
        choice=self.selection()
        choice["materials_sha256"]=v2.digest(materials)
        choice["proposals_sha256"]=v2.digest(proposals)
        choice["scenes"]=copy.deepcopy(proposals["proposals"][0]["scenes"])
        mapped,report=v2.map_selection_v2_to_spec(materials,proposals,choice,
                                                  spec,self.media,self.fx.job)
        self.assertEqual(report["status"],"V2_VIDEO_SPEC_MAPPED_NOT_RENDERED")
        self.assertEqual(len(mapped["scenes"]),10)
        self.assertEqual({s["clipPlayback"] for s in mapped["scenes"]},
                         {"stretch"})
        self.assertFalse(report["render_authorized"])

    def test_long_scene_without_explicit_loop_is_rejected(self):
        broken=copy.deepcopy(self.spec)
        broken["scenes"][0]["source_playback"]="freeze"
        with self.assertRaisesRegex(ValueError,"EXPLICIT_SOURCE_REPEAT_REQUIRED"):
            v2.make_materials_v2("alaska-test-10","alaska-reuse-real-test",
                "a"*64,broken,self.media,self.fx.job)

    def test_replaced_or_extra_unique_sources_are_not_silently_accepted(self):
        wrong=copy.deepcopy(self.spec)
        wrong["scenes"][7]["source_asset_id"]="unapproved-unknown"
        with self.assertRaisesRegex(ValueError,"SOURCE_BINDING_CHANGED"):
            v2.make_materials_v2("alaska-test-10","alaska-reuse-real-test",
                "a"*64,wrong,self.media,self.fx.job)
        duplicates=copy.deepcopy(self.media)+[copy.deepcopy(self.media[0])]
        with self.assertRaisesRegex(ValueError,"DUPLICATE_VERIFIED_SOURCE_ASSET"):
            v2.make_materials_v2("alaska-test-10","alaska-reuse-real-test",
                "a"*64,self.spec,duplicates,self.fx.job)

    def test_scene_time_over_60_seconds_stops_before_proposals(self):
        long=copy.deepcopy(self.spec)
        for s in long["scenes"]:
            s["scene_duration_s"]=8.5
            s["source_playback"]="loop"
        with self.assertRaisesRegex(ValueError,"VIDEO_DURATION_LIMIT_EXCEEDED"):
            v2.make_materials_v2("alaska-test-10","alaska-reuse-real-test",
                "a"*64,long,self.media,self.fx.job)

    def test_mutation_of_original_mp4_rejected_even_when_used_in_many_scenes(self):
        first=self.fx.job/self.media[0]["file"]
        first.write_bytes(first.read_bytes()+b"unapproved")
        with self.assertRaisesRegex(ValueError,"MEDIA_SHA256_MISMATCH"):
            automatic.build_automated_proposals(
                self.materials,self.media,self.fx.job)


if __name__=="__main__":
    unittest.main()
