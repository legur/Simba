"""Zero-paid stage wiring tests for unattended v2 audio QA.

No real ASR model, paid API, private customer WAV or owner interaction.
The acceptance core has separate exhaustive rejection tests in /video/tests.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/"video"))

import motionlab_automatic_audio_qa as automatic
import motionlab_v2_stage_writeback as stage
from test_motionlab_v2_readonly_preflight import VerifiedPrivateV2SourceTests


class AutomaticGateIntegrationTests(unittest.TestCase):
    def setUp(self):
        fixture=VerifiedPrivateV2SourceTests(
            "test_private_wav_and_a2e_bytes_required_before_readonly_materials")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f=fixture
        self.data={
            "status":"AUDIO_ALIGNMENT_AUTO_QA_PASSED",
            "qa_evidence_sha256":"e"*64,
            "audio_revision_sha256":fixture.project["stage_handoffs"]["voice_music"]["audio_lock"]["audio_revision_sha256"],
            "automatic_audio_qa_completed":True,
            "independent_audio_qa_completed":False,
            "render_authorized":False,
            "publication_authorized":False,
            "paid_calls":0,
        }
        self.alignment={
            "schema":"bontours.montage.audio-alignment/v1",
            "status":"AUDIO_ALIGNMENT_VERIFIED",
            "qa_evidence_sha256":"e"*64,
            "lines":[],
            "render_authorized":False,
            "publication_authorized":False,
        }

    def source(self):
        with patch.dict(os.environ,{"SIMBA_AUTO_QA_ASR_MODEL_DIR":"/owner/models/ct2-ru",
                                     "SIMBA_AUTO_QA_DEVICE":"cpu"}):
            return self.f.source()

    def test_auto_model_is_called_without_any_user_review_or_qa_file(self):
        self.assertFalse((self.f.job/"alignment-listening-review.json").exists())
        original=self.f.path.read_bytes()
        with patch.object(automatic,"verify_automatic_audio_qa",
                          return_value=(self.alignment,self.data)) as checked:
            ctx=self.source()
        self.assertEqual(ctx["materials"]["audio_alignment_status"],
                         "AUDIO_ALIGNMENT_VERIFIED_AUTO")
        self.assertEqual(ctx["materials"]["audio_alignment_method"],
                         "INDEPENDENT_LOCAL_CTC_AND_ASR")
        self.assertEqual(ctx["materials"]["audio_alignment_qa_sha256"],"e"*64)
        self.assertFalse(ctx["listening_receipt"]["render_authorized"])
        self.assertEqual(self.f.path.read_bytes(),original)
        checked.assert_called_once()
        args,kwargs=checked.call_args
        self.assertEqual(args[0]["id"],self.f.project["id"])
        self.assertEqual(kwargs["asr_model_path"],"/owner/models/ct2-ru")

    def test_low_confidence_blocks_and_does_not_use_manual_attestation(self):
        with patch.object(automatic,"verify_automatic_audio_qa",
                          side_effect=automatic.AutomaticQAError("AUTO_QA_SPOKEN_TEXT_DIFFERS")):
            with self.assertRaisesRegex(stage.V2SourceError,
                                        "V2_AUTOMATIC_AUDIO_QA_BLOCKED"):
                self.source()
        self.assertNotIn("edit_choice",
                         json.loads(self.f.path.read_text())["stage_handoffs"])

    def test_automatic_mode_does_not_fall_back_to_explicit_owner_review(self):
        (self.f.job/"alignment-draft.json").write_text("{}")
        (self.f.job/"alignment-listening-review.json").write_text("{}")
        with patch.object(automatic,"verify_automatic_audio_qa",
                          side_effect=automatic.AutomaticQAError("AUTO_QA_MODEL_UNAVAILABLE")):
            with self.assertRaisesRegex(stage.V2SourceError,
                                        "V2_AUTOMATIC_AUDIO_QA_BLOCKED"):
                self.source()

    def test_wrong_asr_receipt_does_not_set_verified_status(self):
        receipt={**self.data,"status":"BLOCKED_LOW_CONFIDENCE"}
        with patch.object(automatic,"verify_automatic_audio_qa",
                          return_value=(self.alignment,receipt)):
            with self.assertRaisesRegex(stage.V2SourceError,
                                        "V2_AUTOMATIC_AUDIO_QA_BLOCKED"):
                self.source()

    def test_automatic_gate_is_disabled_without_explicit_local_model(self):
        with patch.dict(os.environ,{"SIMBA_AUTO_QA_ASR_MODEL_DIR":""}):
            ctx=self.f.source()
        self.assertEqual(ctx["materials"]["audio_alignment_status"],"TIMINGS_NOT_VERIFIED")
        self.assertIsNone(ctx["listening_receipt"])


if __name__=="__main__":
    unittest.main()
