"""Offline, zero-paid regression: independent unprompted speech vs fixed CTC.

No real customer WAV, downloads, paid ASR or cloud TTS. Unit test transcription
is explicitly synthetic and cannot be used as a production QA report.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import motionlab_automatic_audio_qa as qa
from test_motionlab_audio_alignment_draft import ForcedAlignmentDraftTests


class IndependentASRValidationTests(unittest.TestCase):
    def setUp(self):
        t = ForcedAlignmentDraftTests(
            "test_russian_real_word_spans_are_unverified_and_never_render_authorized")
        t.setUp()
        self.original = t
        self.preflight = t.preflight
        self.source = t.source
        self.draft = t.parsed()
        self.sha_model = "c" * 64
        self.asr = {
            "schema": qa.AUTO_QA,
            "project_id": self.preflight["project_id"],
            "source_sha256": t.sha,
            "audio_revision_sha256": self.preflight["audio_revision_sha256"],
            "narration_sha256": self.preflight["narration_sha256"],
            "independent_model_family": "faster-whisper-ct2",
            "model_sha256": self.sha_model,
            "unprompted_original_wav": True,
            "word_timestamps": True,
            "language": "ru",
            "language_probability": .985,
            "segments": [{
                "avg_logprob": -.11,
                "no_speech_prob": .01,
                "words": [
                    {"word": "Привет,", "start": .07, "end": .41, "probability": .95},
                    {"word": "мир!", "start": .45, "end": .80, "probability": .97},
                    {"word": "Мы", "start": 1.06, "end": 1.24, "probability": .96},
                    {"word": "едем", "start": 1.25, "end": 1.63, "probability": .98},
                    {"word": "в", "start": 1.64, "end": 1.74, "probability": .91},
                    {"word": "Прагу.", "start": 1.73, "end": 2.22, "probability": .94},
                ]
            }],
        }
        # No model is run: these are demonstrative, synthetic results.
        self.asr["segments"][0]["words"][5]["start"] = 1.75

    def check(self, transcript=None, draft=None, preflight=None):
        return qa.audit_independent_asr(
            self.preflight if preflight is None else preflight,
            self.source,
            self.draft if draft is None else draft,
            self.asr if transcript is None else transcript,
            model_sha256=self.sha_model,
        )

    def test_agreement_issues_only_autonomous_qa_not_owner_or_render_approval(self):
        alignment, receipt = self.check()
        self.assertEqual(receipt["status"], "AUDIO_ALIGNMENT_AUTO_QA_PASSED")
        self.assertTrue(receipt["automatic_audio_qa_completed"])
        self.assertFalse(receipt["independent_audio_qa_completed"])
        self.assertFalse(receipt["render_authorized"])
        self.assertFalse(receipt["publication_authorized"])
        self.assertEqual(receipt["paid_calls"], 0)
        self.assertEqual(receipt["word_count"], 6)
        self.assertEqual(alignment["schema"], qa.ALIGNMENT)
        self.assertEqual(alignment["lines"][0]["words"][0]["word_start_ms"], 50)
        self.assertFalse(alignment["independent_audio_qa_completed"])
        self.assertEqual(len(receipt["qa_evidence_sha256"]), 64)

    def test_one_wrong_spoken_word_or_mismatched_number_blocks(self):
        for value in ("Всё", "два"):
            asr = copy.deepcopy(self.asr)
            asr["segments"][0]["words"][-1]["word"] = value
            with self.subTest(value=value):
                with self.assertRaisesRegex(qa.AutomaticQAError,
                                            "AUTO_QA_SPOKEN_TEXT_DIFFERS"):
                    self.check(transcript=asr)

    def test_omission_or_extra_spoken_word_blocks(self):
        asr = copy.deepcopy(self.asr)
        asr["segments"][0]["words"].pop()
        with self.assertRaisesRegex(qa.AutomaticQAError, "AUTO_QA_ASR_WORD_COUNT"):
            self.check(transcript=asr)
        asr = copy.deepcopy(self.asr)
        asr["segments"][0]["words"].append({
            "word":"extra","start":2.4,"end":2.6,"probability":.99})
        with self.assertRaisesRegex(qa.AutomaticQAError, "AUTO_QA_ASR_WORD_COUNT"):
            self.check(transcript=asr)

    def test_low_asr_confidence_fails_closed(self):
        for field, value, error in (
            ("language_probability", .5, "AUTO_QA_LANGUAGE_UNCERTAIN"),
            ("unprompted_original_wav", False, "AUTO_QA_ASR_EVIDENCE_UNTRUSTED"),
            ("word_timestamps", False, "AUTO_QA_ASR_EVIDENCE_UNTRUSTED"),
        ):
            asr = copy.deepcopy(self.asr);asr[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(qa.AutomaticQAError,error):
                    self.check(transcript=asr)
        for field, value in (
            ("avg_logprob", -.92),
            ("no_speech_prob", .75),
        ):
            asr = copy.deepcopy(self.asr);asr["segments"][0][field] = value
            with self.assertRaisesRegex(qa.AutomaticQAError,
                                        "AUTO_QA_ASR_SEGMENT_UNCERTAIN"):
                self.check(transcript=asr)
        asr=copy.deepcopy(self.asr)
        asr["segments"][0]["words"][2]["probability"] = .30
        with self.assertRaisesRegex(qa.AutomaticQAError,"AUTO_QA_ASR_WORD_UNCERTAIN"):
            self.check(transcript=asr)

    def test_timing_drift_and_asr_overlaps_block(self):
        asr = copy.deepcopy(self.asr)
        # Shift the final word but preserve monotonic ASR timestamps to
        # isolate disagreement between the two models from an overlap error.
        asr["segments"][0]["words"][5]["start"] = 2.00
        asr["segments"][0]["words"][5]["end"] = 2.53
        with self.assertRaisesRegex(qa.AutomaticQAError,"AUTO_QA_MODELS_DISAGREE"):
            self.check(transcript=asr)
        asr = copy.deepcopy(self.asr)
        asr["segments"][0]["words"][2]["start"] = .18
        with self.assertRaisesRegex(qa.AutomaticQAError,
                                    "AUTO_QA_ASR_WORD_TIMELINE_INVALID"):
            self.check(transcript=asr)

    def test_changed_revision_or_acoustic_low_score_blocks(self):
        asr=copy.deepcopy(self.asr);asr["narration_sha256"]="e"*64
        with self.assertRaisesRegex(qa.AutomaticQAError,"AUTO_QA_ASR_EVIDENCE_UNTRUSTED"):
            self.check(transcript=asr)
        draft=copy.deepcopy(self.draft)
        draft["lines"][0]["words"][0]["acoustic_score"]=.1
        with self.assertRaisesRegex(qa.AutomaticQAError,"AUTO_QA_CTC_BOUNDARIES_INVALID"):
            self.check(draft=draft)
        pre=copy.deepcopy(self.preflight);pre["music_bytes_verified"]=False
        with self.assertRaisesRegex(qa.AutomaticQAError,"AUTO_QA_APPROVED_WAV_NOT_VERIFIED"):
            self.check(preflight=pre)

    def test_no_whisper_model_download_or_owner_manual_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp=Path(tmp);(temp/"model").mkdir()
            (temp/"model/model.bin").write_bytes(b"m" * 100_004)
            (temp/"model/config.json").write_text("{}")
            model,sha=qa._safe_local_asr_model(str(temp/"model"), temp/"repo")
            self.assertEqual(sha,hashlib.sha256(b"m" * 100_004).hexdigest())
            called={}
            class FakeModel:
                def __init__(self,*args,**kwargs):
                    called["init"]=kwargs
                def transcribe(self,*args,**kwargs):
                    called["asr"]=kwargs
                    word=types.SimpleNamespace(word="Привет",start=.1,end=.4,
                                               probability=.99)
                    seg=types.SimpleNamespace(avg_logprob=-.05,
                                              no_speech_prob=.01,words=[word])
                    info=types.SimpleNamespace(language="ru",language_probability=.99)
                    return iter([seg]),info
            with patch.dict(sys.modules,{"faster_whisper":types.SimpleNamespace(WhisperModel=FakeModel)}):
                result=qa.run_local_asr(temp/"real.wav",model,sha)
            self.assertTrue(called["init"]["local_files_only"])
            self.assertTrue(called["asr"]["word_timestamps"])
            self.assertIsNone(called["asr"]["initial_prompt"])
            self.assertFalse(called["asr"]["condition_on_previous_text"])
            self.assertEqual(result["segments"][0]["words"][0]["word"],"Привет")
            with self.assertRaisesRegex(qa.AutomaticQAError,"AUTO_QA_LOCAL_ASR_MODEL_NOT_CONFIGURED"):
                qa._safe_local_asr_model("public-model-name",temp/"repo")


if __name__ == "__main__":
    unittest.main()
