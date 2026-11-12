"""Use actual self-generated MP4 pixels to test automatic montage choices.

No mock analysis or user attestation is counted as a real clip review.
FFmpeg synthesizes moving/static pixels; no private customer media, model,
A2E/TTS provider, paid API or render worker is called.
"""
from __future__ import annotations

import copy
from pathlib import Path
import hashlib
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
MATERIALS = HERE.parent / "materials"
for folder in (str(HERE),str(MATERIALS)):
    if folder not in sys.path:
        sys.path.insert(0,folder)

import motionlab_v2_contract as v2
import motionlab_auto_proposals as auto
import motionlab_render_contract as renderer
import motionlab_v2_stage_writeback as stage


class ActualPixelBasedProposalsTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.job=Path(tmp.name)
        self.media=[]
        spec={
            "packageId":"motionlab-test",
            "size":"1080x1920",
            "sourcePost":"approved-copy.md",
            "voice":{"source":"approved-existing-wav"},
            "music":{"file":"owner-cleared.mp3","rights_confirmed":True},
            "end":{"brand":"Bon Tours","cta":"Owner-reviewed final only"},
            "scenes":[],
        }
        for n,filter_expr in enumerate((
            "color=c=navy:s=240x426:r=12:d=4",
            "testsrc2=s=240x426:r=12:d=4",
        ),1):
            path=self.job/f"clip-{n}.mp4"
            subprocess.run([
                "ffmpeg","-nostdin","-hide_banner","-loglevel","error",
                "-f","lavfi","-i",filter_expr,
                "-an","-c:v","mpeg4","-q:v","8","-pix_fmt","yuv420p",
                "-movflags","+faststart","-y",str(path),
            ],check=True,capture_output=True,timeout=40)
            meta=renderer._ffprobe(path)
            self.media.append({
                "scene_id":f"scene-{n}",
                "asset_id":f"asset-{n}",
                "file":path.name,
                "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                "duration_s":meta["duration_s"],
            })
            spec["scenes"].append({
                "clip":path.name,
                "title":f"Scene {n}",
                "lines":[{"text":f"Approved scene {n} original narration"}],
            })
        self.materials=v2.make_materials_v2(
            "motionlab-test","req-real-pixels-01","a"*64,spec,
            self.media,self.job)
        self.proposals,self.receipt=auto.build_automated_proposals(
            self.materials,self.media,self.job)

    def test_real_frames_measured_with_correct_source_sha_and_three_variants(self):
        evidence=self.proposals["analysis"]["pixel_evidence"]
        self.assertEqual(self.receipt["status"],
            "THREE_REAL_VIDEO_AUTOMATED_PROPOSALS_NOT_OWNER_SELECTED")
        self.assertEqual(len(evidence),2)
        self.assertEqual([x["asset_sha256"] for x in evidence],
                         [m["sha256"] for m in self.media])
        self.assertTrue(all(x["frames_sampled"]>=10 for x in evidence))
        self.assertTrue(all(len(x["sampled_frame_sha256"])==64 for x in evidence))
        self.assertGreater(evidence[1]["motion_delta"],evidence[0]["motion_delta"])
        self.assertEqual(len(self.proposals["proposals"]),3)
        self.assertEqual(sum(x["recommended"] for x in self.proposals["proposals"]),1)
        self.assertEqual(v2.validate_proposals_v2(
            self.materials,self.proposals)["status"],
            "MOTIONLAB_THREE_PROPOSALS_VALIDATED")
        self.assertFalse(self.receipt["semantic_review_performed"])
        self.assertFalse(self.receipt["render_authorized"])
        self.assertFalse(self.receipt["publication_authorized"])
        self.assertEqual(self.receipt["paid_calls"],0)

    def test_reproducibility_from_same_actual_source_frames(self):
        second,_=auto.build_automated_proposals(self.materials,self.media,self.job)
        self.assertEqual(v2.digest(second),v2.digest(self.proposals))

    def test_source_file_mutation_is_blocked_despite_old_metadata(self):
        mp4=self.job/self.media[0]["file"]
        mp4.write_bytes(mp4.read_bytes()+b"tamper")
        with self.assertRaisesRegex(ValueError,"MEDIA_SHA256_MISMATCH"):
            auto.build_automated_proposals(self.materials,self.media,self.job)

    def test_unsupported_analysis_metadata_rejected_even_with_three_good_variants(self):
        tampered=copy.deepcopy(self.proposals)
        tampered["analysis"]["analysis_method"]="someone_declared_video_reviewed"
        with self.assertRaisesRegex(ValueError,
                                    "AUTOMATIC_VIDEO_ANALYSIS_METHOD_MISSING"):
            v2.validate_proposals_v2(self.materials,tampered)
        tampered=copy.deepcopy(self.proposals)
        tampered["analysis"]["pixel_evidence"][1]["asset_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"AUTOMATIC_VIDEO_EVIDENCE_MISSING"):
            v2.validate_proposals_v2(self.materials,tampered)

    def test_current_canonical_stage_recomputes_proposals_before_accepting(self):
        ctx={"materials":self.materials,"media":self.media,"job":self.job,
             "spec":{}}
        # Mock only the existing canonical project/source preparation, not
        # the real ffmpeg decode, hash verification or proposal recomputation.
        with patch.object(stage,"source_context",return_value=ctx):
            source,_,_=stage.check_current_v2(
                self.job,self.job,"motionlab-test",self.materials,
                self.proposals,selection=None)
            self.assertIs(source,ctx)
            tampered=copy.deepcopy(self.proposals)
            tampered["analysis"]["pixel_evidence"][0]["motion_delta"]=28.0
            # Structural contract alone would accept this false numerical claim.
            self.assertEqual(v2.validate_proposals_v2(
                self.materials,tampered)["status"],
                "MOTIONLAB_THREE_PROPOSALS_VALIDATED")
            with self.assertRaisesRegex(stage.V2SourceError,
                                         "AUTOMATIC_PROPOSALS_SOURCE_RECHECK_FAILED"):
                stage.check_current_v2(self.job,self.job,"motionlab-test",
                                       self.materials,tampered,None)

    def test_prepare_automatic_handoff_requires_unattended_audio_qa(self):
        ctx={"materials":self.materials,"media":self.media,"job":self.job,
             "spec":{}}
        with patch.object(stage,"source_context",return_value=ctx):
            with self.assertRaisesRegex(stage.V2SourceError,
                                        "AUTOMATIC_AUDIO_QA_REQUIRED"):
                stage.prepare_automatic_v2_proposals(
                    self.job,self.job,"motionlab-test","req-real-pixels-01")
        with patch.object(stage,"source_context",return_value={
            **ctx,"materials":{**self.materials,
                              "audio_alignment_status":"AUDIO_ALIGNMENT_VERIFIED_AUTO"}
        }):
            launch=stage.prepare_automatic_v2_proposals(
                self.job,self.job,"motionlab-test","req-real-pixels-01")
        self.assertTrue(launch["owner_selection_required"])
        self.assertFalse(launch["run_render"])
        self.assertFalse(launch["auto_publish"])
        self.assertFalse(launch["run_paid_operations"])
        self.assertEqual(len(launch["proposals"]["proposals"]),3)
        self.assertNotIn("decision",launch)

    def test_no_fake_semantic_claims_or_user_approval(self):
        self.assertEqual(self.proposals["analysis"]["status"],
                         "REAL_VIDEO_AUTOMATICALLY_ANALYZED")
        self.assertNotIn("selected_option",str(self.proposals))
        self.assertNotIn("USER_SELECTED_IN_CONNECTED_SESSION",str(self.proposals))
        self.assertEqual(self.materials["analysis"]["status"],
                         "PENDING_REAL_MEDIA_ACCESS")
        self.assertNotIn("approved",self.receipt["status"].lower())


if __name__=="__main__":
    unittest.main()
