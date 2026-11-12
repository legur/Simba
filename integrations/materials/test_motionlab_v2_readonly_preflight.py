"""No-host/no-paid v2 source preflight using real Studio lock + byte SHA checks.

Only synthetic private clips and WAV/music; no Google Drive, network,
browser, paid media or imagined owner review. A valid private source is
readable, but cannot be selected/applied before real audio alignment QA.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/"video"))

import motionlab_v2_stage_writeback as stage
import motionlab_v2_contract as v2
from test_studio_v2_audio_stage import StudioV2SourceBoundAudioStageTests


class VerifiedPrivateV2SourceTests(unittest.TestCase):
    def setUp(self):
        f=StudioV2SourceBoundAudioStageTests(
            "test_existing_actual_wav_and_selected_text_promote_to_metadata_v2")
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.fixture=f
        self.path,self.project,_=f.v2candidate()
        self.root=f.case.root
        self.private=tempfile.TemporaryDirectory()
        self.addCleanup(self.private.cleanup)
        self.job=Path(self.private.name)/"example"
        self.job.mkdir()
        self.clip=self.job/"clip-01.mp4"
        self.clip.write_bytes(b"SYNTHETIC-NOT-A-PLAYABLE-MP4"*400)
        self.clip_hash=hashlib.sha256(self.clip.read_bytes()).hexdigest()
        asset=next(a for a in self.project["assets"] if a["kind"]=="animated_clip")
        asset.update(recorded_sha256=self.clip_hash,
                     recorded_duration_seconds=5.0,
                     drive_file_id="1VerifiedSyntheticA2EClipABCD",
                     task_id="synthetic-task-123")
        self.path.write_text(json.dumps(self.project,ensure_ascii=False),encoding="utf-8")
        self.media=[{"scene_id":"clip-01","asset_id":asset["id"],
                     "file":self.clip.name,"sha256":self.clip_hash,
                     "duration_s":5.0}]
        self.spec={"packageId":"example","size":"1080x1920",
                   "sourcePost":"approved-script.md",
                   "voice":{"source":"existing_approved_wav"},
                   "music":{"file":"music.bin","rights_confirmed":True},
                   "end":{"brand":"Bon Tours","cta":"Verified test only"},
                   "scenes":[{"clip":self.clip.name,"title":"Only synthetic test title",
                              "lines":[{"text":"Sample narration 2"}]}]}
        (self.job/stage.PRIVATE_MEDIA).write_text(
            json.dumps(self.media),encoding="utf-8")
        (self.job/stage.PRIVATE_FILE).write_text(
            json.dumps(self.spec),encoding="utf-8")
        (self.job/"approved.wav").write_bytes(f.case.wav)
        (self.job/"music.bin").write_bytes(f.case.music)
        lock=self.project["stage_handoffs"]["voice_music"]["audio_lock"]
        (self.job/"approved-audio-files.json").write_text(json.dumps({
            "audio_revision_sha256":lock["audio_revision_sha256"],
            "narration_file":"approved.wav","music_file":"music.bin"}),
            encoding="utf-8")
        self.probe=patch.object(v2.r,"_ffprobe",return_value={
            "duration_s":5.0,"width":1080,"height":1920,"has_audio":False})
        self.probe.start()
        self.addCleanup(self.probe.stop)

    def source(self):
        return stage.source_context(self.root,Path(self.private.name),
                                    "example","owner-test-request-01")

    def proposals(self, materials):
        def choice(n,camera):
            return {"option":n,"title":f"Concept {n}",
                    "rationale":"Synthetic review fixture only: not real agent video analysis.",
                    "recommended":n==1,
                    "scenes":[{
                        "scene_id":materials["scenes"][0]["scene_id"],
                        "camera":{"id":camera,"intensity_percent":35},
                        "transition":None,
                        "title_fx":"fade-rise",
                        "subtitle":{"style_id":"clean","word_motion_id":"karaoke"}
                    }]}
        return {
            "schema":v2.PROPOSALS,
            "project_id":materials["project_id"],
            "request_id":materials["request_id"],
            "expected_input_fingerprint":materials["expected_input_fingerprint"],
            "materials_sha256":v2.digest(materials),
            "renderer_revision_sha256":materials["renderer_capabilities"]["revision_sha256"],
            "analysis":{
                "status":"REAL_VIDEO_REVIEWED",
                "access_mode":"owner_private_material_bundle",
                "review_notes":"Synthetic fixture is not evidence of a real agent's review.",
                "inspected_assets":[{
                    "scene_id":materials["scenes"][0]["scene_id"],
                    "asset_sha256":materials["scenes"][0]["media"]["asset_sha256"],
                    "evidence_kind":"full_original_mp4",
                    "scene_notes":"Synthetic bytes, structurally validated only, never a real viewing."
                }]
            },
            "proposals":[choice(1,"cinematic-zoom"),choice(2,"float"),choice(3,"push-through")]
        }

    def test_private_wav_and_a2e_bytes_required_before_readonly_materials(self):
        data=self.source()
        m=data["materials"]
        self.assertEqual(m["schema"],v2.MATERIALS)
        self.assertNotIn("options",m)
        self.assertEqual(m["scenes"][0]["media"]["asset_sha256"],self.clip_hash)
        self.assertEqual(m["audio_preflight_status"],
                         "APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED")
        self.assertEqual(m["audio_alignment_status"],"TIMINGS_NOT_VERIFIED")
        self.assertFalse(data["audio_receipt"]["render_authorized"])
        self.assertEqual(data["audio_receipt"]["paid_calls"],0)
        self.assertEqual(data["packet"]["next_stage"],"edit_choice")

    def test_changed_clip_bytes_fail_without_receipt_or_render(self):
        self.clip.write_bytes(b"tampered synthetic MP4" * 600)
        with self.assertRaises(Exception):
            self.source()

    def test_changed_private_music_blocks_source(self):
        (self.job/"music.bin").write_bytes(b"altered music" * 300)
        with self.assertRaisesRegex(Exception,"APPROVED_MUSIC_SHA256_MISMATCH"):
            self.source()

    def test_missing_verified_wav_blocks_source(self):
        (self.job/"approved.wav").unlink()
        with self.assertRaisesRegex(Exception,"PRIVATE_AUDIO_FILE_UNAVAILABLE"):
            self.source()

    def test_no_source_outside_private_bundle(self):
        (self.job/stage.PRIVATE_FILE).unlink()
        with self.assertRaisesRegex(stage.V2SourceError,"Private approved source bundle"):
            self.source()

    def test_valid_synthetic_proposals_do_not_unlock_unverified_audio_timing(self):
        ctx=self.source()
        proposals=self.proposals(ctx["materials"])
        result=v2.validate_proposals_v2(ctx["materials"],proposals)
        self.assertEqual(result["status"],"MOTIONLAB_THREE_PROPOSALS_VALIDATED")
        self.assertFalse(result["actual_agent_video_review_proven_by_code"])
        selection={
            "schema":v2.SELECTION,
            "project_id":ctx["materials"]["project_id"],
            "request_id":ctx["materials"]["request_id"],
            "expected_input_fingerprint":ctx["materials"]["expected_input_fingerprint"],
            "materials_sha256":v2.digest(ctx["materials"]),
            "proposals_sha256":v2.digest(proposals),
            "format":"9:16","next_stage":"MONTAGE_PLANNING_REVIEW",
            "decision":{"selected_option":1,"options_presented":3,
                        "state":"USER_SELECTED_IN_CONNECTED_SESSION",
                        "explicit_approval":True,"visual_layout_edited":False,
                        "user_selected_at":"2026-11-12T15:00:00Z"},
            "guards":{"run_render":False,"run_tts":False,"run_a2e":False,
                      "run_paid_operations":False,"auto_publish":False,
                      "preserve_approved_voice":True,
                      "preserve_approved_music":True,
                      "preserve_approved_narration":True},
            "scenes":copy.deepcopy(proposals["proposals"][0]["scenes"])
        }
        with self.assertRaisesRegex(stage.V2SourceError,"TIMINGS_NOT_VERIFIED"):
            stage.check_current_v2(self.root,Path(self.private.name),"example",
                                   ctx["materials"],proposals,selection)

    def test_none_of_the_private_contents_written_into_canonical_project(self):
        original=self.path.read_bytes()
        self.source()
        self.assertEqual(self.path.read_bytes(),original)
        self.assertEqual(len(list(self.job.glob("*"))),6)


if __name__=="__main__":
    unittest.main()
