"""Zero-paid tests for exact-text acoustic word-alignment DRAFT.

No WhisperX/model download, real client audio, private Drive, renderer or ASR API.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))
sys.path.insert(0, str(VIDEO.parent / "materials"))

import motionlab_audio_alignment_draft as engine


class ForcedAlignmentDraftTests(unittest.TestCase):
    def setUp(self):
        self.source = "Привет, мир!\nМы едем в Прагу.".encode("utf-8")
        self.sha = hashlib.sha256(self.source).hexdigest()
        self.preflight = {
            "status": "APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED",
            "project_id": "test-project",
            "audio_revision_sha256": "a" * 64,
            "narration_sha256": "b" * 64,
            "narration_duration_ms": 5000,
            "narration_bytes_verified": True,
            "music_bytes_verified": True,
            "render_authorized": False,
        }
        self.aligned = {"word_segments": [
            {"word": text, "start": start, "end": end, "score": .8}
            for text, start, end in [
                ("Привет,", 0.05, .42), ("мир!", .44, .81),
                ("Мы", 1.04, 1.22), ("едем", 1.23, 1.6),
                ("в", 1.61, 1.7), ("Прагу.", 1.71, 2.2)]
        ]}

    def parsed(self, **kw):
        return engine.validate_acoustic_draft(
            self.preflight, self.source, self.sha, self.aligned, **kw)

    def test_russian_real_word_spans_are_unverified_and_never_render_authorized(self):
        result = self.parsed()
        self.assertEqual(result["status"],
                         "DRAFT_ACOUSTIC_TIMINGS_REQUIRE_INDEPENDENT_LISTENING_QA")
        self.assertEqual(result["word_count"], 6)
        self.assertEqual(len(result["lines"]), 2)
        self.assertEqual(result["lines"][0]["phrase_start_ms"], 50)
        self.assertEqual(result["lines"][0]["phrase_end_ms"], 810)
        self.assertEqual(result["lines"][1]["words"][-1]["word_end_ms"], 2200)
        for flag in ("independent_audio_qa_completed",
                     "audio_alignment_verified", "render_authorized",
                     "publication_authorized"):
            self.assertFalse(result[flag])
        self.assertEqual(result["paid_calls"], 0)
        self.assertNotEqual(result["schema"], "bontours.montage.audio-alignment/v1")

    def test_changed_transcript_or_source_sha_is_rejected(self):
        with self.assertRaisesRegex(engine.AlignmentDraftError, "APPROVED_TEXT_BYTES_MISMATCH"):
            engine.validate_acoustic_draft(self.preflight, b"different", self.sha, self.aligned)
        with self.assertRaisesRegex(engine.AlignmentDraftError, "APPROVED_TEXT_SHA_INVALID"):
            engine.validate_acoustic_draft(self.preflight, self.source, "wrong", self.aligned)

    def test_missing_or_extra_acoustic_words_block_instead_of_guessing(self):
        for replacement in (self.aligned["word_segments"][:-1],
                            self.aligned["word_segments"] + self.aligned["word_segments"][-1:]):
            with self.subTest(count=len(replacement)):
                with self.assertRaisesRegex(engine.AlignmentDraftError,
                                            "ACOUSTIC_WORD_COUNT_MISMATCH"):
                    engine.validate_acoustic_draft(
                        self.preflight, self.source, self.sha, {"word_segments":replacement})

    def test_misrecognized_number_or_word_blocks(self):
        altered = copy.deepcopy(self.aligned)
        altered["word_segments"][2]["word"] = "Они"
        with self.assertRaisesRegex(engine.AlignmentDraftError, "ACOUSTIC_WORD_TEXT_MISMATCH"):
            engine.validate_acoustic_draft(self.preflight,self.source,self.sha,altered)

    def test_missing_or_interpolated_word_time_or_score_blocks(self):
        for patch_value in ({"start": None}, {"score": None},
                            {"end": float("nan")}, {"start": True},
                            {"score": -1}):
            altered = copy.deepcopy(self.aligned)
            altered["word_segments"][3].update(patch_value)
            with self.subTest(patch=patch_value):
                with self.assertRaises(engine.AlignmentDraftError):
                    engine.validate_acoustic_draft(
                        self.preflight, self.source, self.sha, altered)

    def test_overlaps_and_outside_wav_block(self):
        for patch_value in ({"start": .5}, {"end": 5.5}, {"end": 0.01}):
            altered = copy.deepcopy(self.aligned)
            altered["word_segments"][3].update(patch_value)
            with self.subTest(patch=patch_value):
                with self.assertRaisesRegex(engine.AlignmentDraftError,
                                            "ACOUSTIC_WORD_TIMELINE_INVALID"):
                    engine.validate_acoustic_draft(
                        self.preflight, self.source, self.sha, altered)

    def test_not_private_approved_audio_blocks(self):
        for field,value in (("narration_bytes_verified",False),
                            ("music_bytes_verified",False),
                            ("render_authorized",True),
                            ("status","UNVERIFIED")):
            altered=copy.deepcopy(self.preflight)
            altered[field]=value
            with self.assertRaisesRegex(engine.AlignmentDraftError,
                                        "PRIVATE_APPROVED_AUDIO_NOT_VERIFIED"):
                engine.validate_acoustic_draft(altered,self.source,self.sha,self.aligned)

    def test_unsupported_language_rejected(self):
        with self.assertRaisesRegex(engine.AlignmentDraftError,
                                    "AUDIO_ALIGNMENT_LANGUAGE_UNSUPPORTED"):
            self.parsed(language="xx")

    def test_no_owner_execution_means_no_model_load(self):
        with patch.object(engine,"run_private_alignment",side_effect=AssertionError("must not run")):
            self.assertEqual(engine.main(["--project","test-project",
                "--private-dir","/tmp/not-used"]), 2)


class FakeRealPrivateRuntimeTests(unittest.TestCase):
    def test_whisperx_adapter_uses_real_studio_lock_and_private_wav_without_a_paid_call(self):
        # The actual Studio→Montage SHA source gate uses a real PCM WAV fixture.
        from test_motionlab_v2_real_studio_audio_lock import RealStudioToMontageAudioTests
        fixture = RealStudioToMontageAudioTests(
            "test_verified_bytes_still_do_not_authorize_render_or_timings")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)

        with tempfile.TemporaryDirectory() as repo:
            root = Path(repo)
            (root / "campaigns/test-reel").mkdir(parents=True)
            (root / "approved-script.md").write_text("approved text 1",
                                                       encoding="utf-8")
            (root / "campaigns/test-reel/project.json").write_text(
                json.dumps(fixture.project),encoding="utf-8")
            stub = types.ModuleType("whisperx")
            hits = []
            stub.load_audio = lambda filename: hits.append("private_wav") or object()
            stub.load_align_model = lambda language_code, device: (
                hits.append("local_ru_model") or object(), object())
            stub.align = lambda transcript, model, metadata, audio, device, **kwargs: {
                "word_segments": [
                    {"word":"approved","start":.05,"end":.34,"score":.9},
                    {"word":"text","start":.35,"end":.55,"score":.9},
                    {"word":"1","start":.56,"end":.8,"score":.8},
                ]}
            with patch.dict(sys.modules, {"whisperx":stub}):
                draft = engine.run_private_alignment(
                    root, "test-reel", fixture.root, language="ru")
            self.assertEqual(hits, ["private_wav", "local_ru_model"])
            self.assertEqual(draft["word_count"],3)
            self.assertFalse(draft["audio_alignment_verified"])
            self.assertFalse(draft["render_authorized"])
            self.assertEqual(draft["paid_calls"],0)


if __name__ == "__main__":
    unittest.main()
