"""Independent listening QA path: explicit owner word-by-word verification only.

Fixtures are synthetic. CI does NOT inspect any real client audio and cannot
claim a real owner listened. Tests show what evidence must be supplied through
a separate private, owner-authored record before v2 advances.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "video"))

import motionlab_v2_stage_writeback as stage
import motionlab_audio_listening_qa as listening
from test_motionlab_v2_readonly_preflight import VerifiedPrivateV2SourceTests


class OwnerListeningEvidenceTests(unittest.TestCase):
    def setUp(self):
        example = VerifiedPrivateV2SourceTests(
            "test_private_wav_and_a2e_bytes_required_before_readonly_materials")
        example.setUp()
        self.addCleanup(example.doCleanups)
        self.f = example
        self.ctx = example.source()
        self.lock = example.project["stage_handoffs"]["voice_music"]["audio_lock"]
        self.sha = self.lock["approved_text_sha256"]
        self.draft = {
            "schema": "bontours.montage.audio-alignment-draft/v1",
            "status": "DRAFT_ACOUSTIC_TIMINGS_REQUIRE_INDEPENDENT_LISTENING_QA",
            "project_id": "example",
            "source_sha256": self.sha,
            "audio_revision_sha256": self.lock["audio_revision_sha256"],
            "narration_sha256": self.lock["narration"]["sha256"],
            "method": "whisperx-ctc-local",
            "language": "ru",
            "lines": [{
                "line_id": "line-01",
                "phrase_start_ms": 50, "phrase_end_ms": 830,
                "words": [
                    {"text": "sample", "word_start_ms": 50,
                     "word_end_ms": 280, "acoustic_score": .9},
                    {"text": "narration", "word_start_ms": 290,
                     "word_end_ms": 590, "acoustic_score": .88},
                    {"text": "2", "word_start_ms": 610,
                     "word_end_ms": 830, "acoustic_score": .87},
                ]
            }],
            "word_count": 3,
            "independent_audio_qa_completed": False,
            "audio_alignment_verified": False,
            "render_authorized": False,
            "paid_calls": 0,
            "publication_authorized": False
        }
        self.draft_path = self.f.job / listening.DRAFT_FILE
        self.review_path = self.f.job / listening.REVIEW_FILE
        self.draft_path.write_text(json.dumps(self.draft), encoding="utf-8")
        self.review = {
            "schema": listening.REVIEW_SCHEMA,
            "project_id": "example",
            "source_sha256": self.sha,
            "audio_revision_sha256": self.lock["audio_revision_sha256"],
            "narration_sha256": self.lock["narration"]["sha256"],
            "draft_sha256": hashlib.sha256(self.draft_path.read_bytes()).hexdigest(),
            "reviewer": "owner:legur",
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "method": "independent_manual_listening_against_original_wav",
            "every_word_listened": True,
            "no_missing_spoken_words": True,
            "no_render_or_publication_authorized": True,
            "review_notes": "SYNTHETIC TEST RECORD. Not a real listening session. Verified review code boundaries.",
            "line_reviews": [{
                "line_id": "line-01",
                "listening_notes": "Synthetic word-by-word QA contract fixture.",
                "words": [
                    {"text": w["text"],
                     "word_start_ms": w["word_start_ms"],
                     "word_end_ms": w["word_end_ms"],
                     "listened": True}
                    for w in self.draft["lines"][0]["words"]
                ],
            }]
        }
        self.save()

    def save(self):
        self.review_path.write_text(
            json.dumps(self.review,ensure_ascii=False), encoding="utf-8")

    def source(self):
        return self.f.source()

    def test_explicit_per_word_listening_allows_only_timing_stage_not_render(self):
        ctx = self.source()
        self.assertEqual(ctx["materials"]["audio_alignment_status"],
                         "AUDIO_ALIGNMENT_VERIFIED")
        self.assertEqual(ctx["listening_receipt"]["status"],
                         "AUDIO_ALIGNMENT_VERIFIED_BY_EXPLICIT_OWNER_LISTENING")
        self.assertTrue(ctx["listening_receipt"]["independent_audio_qa_completed"])
        self.assertFalse(ctx["listening_receipt"]["render_authorized"])
        self.assertEqual(ctx["listening_receipt"]["paid_calls"],0)
        self.assertEqual(len(ctx["materials"]["audio_alignment_sha256"]),64)
        self.assertEqual(ctx["materials"]["audio_alignment_qa_sha256"],
                         hashlib.sha256(self.review_path.read_bytes()).hexdigest())
        self.assertFalse(ctx["audio_receipt"]["render_authorized"])

    def test_acoustic_draft_without_review_never_advances_v2(self):
        self.review_path.unlink()
        with self.assertRaisesRegex(stage.V2SourceError,"V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED"):
            self.source()
        self.draft_path.unlink()
        self.assertEqual(self.source()["materials"]["audio_alignment_status"],
                         "TIMINGS_NOT_VERIFIED")

    def test_stale_draft_hash_or_modified_draft_blocks(self):
        self.review["draft_sha256"] = "0"*64
        self.save()
        with self.assertRaisesRegex(stage.V2SourceError,"V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED"):
            self.source()
        self.review["draft_sha256"] = hashlib.sha256(self.draft_path.read_bytes()).hexdigest()
        self.save()
        self.draft_path.write_text(self.draft_path.read_text()+" ",encoding="utf-8")
        with self.assertRaisesRegex(stage.V2SourceError,"V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED"):
            self.source()

    def test_unreviewed_word_blocks(self):
        self.review["line_reviews"][0]["words"][1]["listened"]=False
        self.save()
        with self.assertRaisesRegex(stage.V2SourceError,"V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED"):
            self.source()

    def test_changed_word_requires_explained_manual_correction(self):
        words=self.review["line_reviews"][0]["words"]
        words[1]["word_start_ms"]=310
        self.save()
        with self.assertRaisesRegex(stage.V2SourceError,"V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED"):
            self.source()
        words[1]["correction_note"]="Manually adjusted to the acoustic word onset."
        self.save()
        self.assertEqual(self.source()["materials"]["audio_alignment_status"],
                         "AUDIO_ALIGNMENT_VERIFIED")

    def test_overlap_or_outside_approved_wav_blocks(self):
        words=self.review["line_reviews"][0]["words"]
        words[1]["word_start_ms"]=200
        words[1]["correction_note"]="Synthetic deliberately overlapping word."
        self.save()
        with self.assertRaisesRegex(stage.V2SourceError,"V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED"):
            self.source()
        words[1]["word_start_ms"]=290
        words[2]["word_end_ms"]=3000
        words[2]["correction_note"]="Synthetic deliberately beyond approved WAV."
        self.save()
        with self.assertRaisesRegex(stage.V2SourceError,"V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED"):
            self.source()

    def test_changed_approved_wav_or_canonical_text_blocks(self):
        (self.f.job/"approved.wav").write_bytes(b"mutated wav")
        with self.assertRaisesRegex(stage.V2SourceError,"V2_APPROVED_AUDIO_SOURCE_NOT_VERIFIED"):
            self.source()

    def test_future_or_missing_qa_attestation_blocks(self):
        self.review["reviewed_at_utc"]="2050-01-01T00:00:00Z"
        self.save()
        with self.assertRaisesRegex(stage.V2SourceError,"V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED"):
            self.source()
        self.review["reviewed_at_utc"]=datetime.now(timezone.utc).isoformat()
        self.review["every_word_listened"]=False
        self.save()
        with self.assertRaisesRegex(stage.V2SourceError,"V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED"):
            self.source()

    def test_symlinked_review_file_blocks(self):
        target=self.f.job/"shadow-qa.json"
        target.write_text(self.review_path.read_text(),encoding="utf-8")
        self.review_path.unlink()
        self.review_path.symlink_to(target)
        with self.assertRaisesRegex(stage.V2SourceError,"V2_INDEPENDENT_LISTENING_QA_NOT_VERIFIED"):
            self.source()

    def test_same_read_only_source_has_no_canonical_project_mutation(self):
        original = self.f.path.read_bytes()
        self.source()
        self.assertEqual(self.f.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
