"""Regress Alaska's exact shape: 10 approved scenes/7 unique canonical A2E MP4s.

This test uses ONLY synthetic local fake media and mocked ffprobe/audio metadata.
It does not count as customer WAV QA, real audio approval, user montage selection,
a real render or Apps Script end-to-end.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

from test_motionlab_v2_readonly_preflight import VerifiedPrivateV2SourceTests
import motionlab_v2_stage_writeback as stage
import motionlab_v2_audio_gate as audio_gate


class SevenOriginalsTenSceneSourceTests(unittest.TestCase):
    def setUp(self):
        fixture=VerifiedPrivateV2SourceTests(
            "test_private_wav_and_a2e_bytes_required_before_readonly_materials")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f=fixture
        self.project=copy.deepcopy(fixture.project)
        original=next(a for a in self.project["assets"]
                      if a.get("kind")=="animated_clip")
        self.media=[]
        for i in range(7):
            source=copy.deepcopy(original)
            if i:
                source["id"]=f"a2e:synthetic-approved-{i:02d}"
                source["task_id"]=f"synthetic-task-{i:02d}"
                source["drive_file_id"]=f"1SyntheticSevenA2EPrivateSource{i:02d}"
                path=fixture.job/f"clip-{i+1:02d}.mp4"
                path.write_bytes(f"SYNTHETIC-SOURCE-{i}".encode()*800)
                source["recorded_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
                source["recorded_duration_seconds"]=5.0
                self.project["assets"].append(source)
            self.media.append({
                "scene_id":f"clip-{i+1:02d}",
                "asset_id":source["id"],
                "file":f"clip-{i+1:02d}.mp4",
                "sha256":source["recorded_sha256"],
                "duration_s":5.0
            })
        self.project["stage_handoffs"]["a2e_clips"]["assets"]=[
            row["asset_id"] for row in self.media]
        self.spec=copy.deepcopy(fixture.spec)
        self.spec["scenes"]=[
            {
                "scene_id":f"alaska-{i+1:02d}",
                "source_asset_id":self.media[i%7]["asset_id"],
                "clip":self.media[i%7]["file"],
                "scene_duration_s":8.1 if i==0 else 4.0,
                "source_playback":"stretch",
                "title":f"Approved fixture title {i+1}",
                "lines":[{"text":f"Approved fixture speech {i+1}"}]
            }
            for i in range(10)
        ]
        (fixture.job/stage.PRIVATE_MEDIA).write_text(
            json.dumps(self.media),encoding="utf-8")
        (fixture.job/stage.PRIVATE_FILE).write_text(
            json.dumps(self.spec),encoding="utf-8")

    def source(self):
        packet={"receipt_sha256":"b"*64}
        with patch.object(stage.old,"_open_stage",return_value=(
                    self.f.path,self.project,packet)),\
             patch.object(audio_gate,"verify_private_audio_manifest",
                           return_value={
                             "status":"APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED",
                             "audio_revision_sha256":"c"*64
                           }),\
             patch.dict(os.environ,{"SIMBA_AUTO_QA_ASR_MODEL_DIR":""}):
            return stage.source_context(self.f.root,Path(self.f.private.name),
                                        "example","alaska-originals-10-07")

    def test_seven_unique_canonical_a2e_sources_are_allowed_v2_only(self):
        result=stage._unique_approved_a2e_v2(self.project)
        self.assertEqual(len(result),7)
        self.assertEqual(len({a["id"] for a in result}),7)
        with self.assertRaisesRegex(stage.old.MotionLabStageError,
                                    "verified A2E clip list missing/invalid"):
            stage.old._clips(self.project)

    def test_ten_scene_source_context_maps_seven_sha_pinned_private_files(self):
        with patch.object(stage.old,"_clips",
                          side_effect=AssertionError("v1 cap must never be used")):
            context=self.source()
        self.assertEqual(len(context["media"]),7)
        self.assertEqual(len(context["materials"]["scenes"]),10)
        self.assertEqual(
            context["materials"]["audio_alignment_status"],
            "TIMINGS_NOT_VERIFIED"
        )
        self.assertEqual(
            [s["asset_id"] for s in context["materials"]["scenes"]],
            [self.media[i%7]["asset_id"] for i in range(10)]
        )
        self.assertFalse(context["audio_receipt"].get("render_authorized",False))
        self.assertNotIn("edit_choice",self.project["stage_handoffs"])

    def test_private_verified_files_do_not_need_to_be_in_timeline_order(self):
        self.media.reverse()
        (self.f.job/stage.PRIVATE_MEDIA).write_text(
            json.dumps(self.media),encoding="utf-8")
        result=self.source()
        self.assertEqual(len(result["materials"]["scenes"]),10)

    def test_changed_canonical_sha_blocks_before_materials(self):
        self.project["assets"][-1]["recorded_sha256"]="f"*64
        with self.assertRaisesRegex(stage.V2SourceError,
                                    "fingerprint or duration changed"):
            self.source()

    def test_undocumented_asset_in_timeline_fails_closed(self):
        self.spec["scenes"][9]["source_asset_id"]="a2e:unapproved-009"
        (self.f.job/stage.PRIVATE_FILE).write_text(
            json.dumps(self.spec),encoding="utf-8")
        with self.assertRaisesRegex(stage.V2SourceError,
                                    "SCENE_TO_SOURCE_BINDING_CHANGED"):
            self.source()

    def test_duplicate_private_clip_entry_blocks_before_audio(self):
        self.media[-1]=copy.deepcopy(self.media[0])
        (self.f.job/stage.PRIVATE_MEDIA).write_text(
            json.dumps(self.media),encoding="utf-8")
        with self.assertRaisesRegex(stage.V2SourceError,
                                    "SOURCE_MISSING_OR_DUPLICATED"):
            self.source()

    def test_no_canonical_f2u_approval_cannot_be_inferred_from_private_files(self):
        self.project["stage_handoffs"]["a2e_clips"]["assets"]=[]
        with self.assertRaisesRegex(stage.V2SourceError,
                                    "APPROVED_UNIQUE_A2E_LIST_INVALID"):
            self.source()


if __name__=="__main__":
    unittest.main()
