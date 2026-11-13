"""Synthetic-only third ASR report semantics; no owner WAV/Drive/model."""
import sys
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import alaska_private_turbo_asr as turbo


class TurboASRTests(unittest.TestCase):
    def test_exact_synthetic_words_are_only_precandidate(self):
        observations=[
            {"word":"море","probability":0.99},
            {"word":"горы","probability":0.96}
        ]
        result=turbo.score("море горы",observations,"ru",0.98)
        self.assertEqual(result["status"],"PRECANDIDATE_TURBO_TEXT_MATCHED")
        self.assertFalse(result["word_timing_verified_for_canonical_v2"])
        self.assertFalse(result["canonical_audio_lock_approved"])
        self.assertFalse(result["render_authorized"])
        self.assertTrue(result["third_asr_not_independent_model_family"])

    def test_mismatched_word_stays_blocked(self):
        observations=[
            {"word":"море","probability":0.99},
            {"word":"леса","probability":0.96}
        ]
        result=turbo.score("море горы",observations,"ru",0.98)
        self.assertEqual(result["status"],"BLOCKED_TURBO_ASR_TEXT_OR_CONFIDENCE_DIFFERS")
        self.assertEqual(result["mismatch_positions"][0]["approved_index"],1)

    def test_low_confidence_blocks_perfection_claim(self):
        observations=[
            {"word":"море","probability":0.50},
            {"word":"горы","probability":0.99}
        ]
        result=turbo.score("море горы",observations,"ru",0.98)
        self.assertEqual(result["status"],"BLOCKED_TURBO_ASR_TEXT_OR_CONFIDENCE_DIFFERS")
        self.assertEqual(result["low_confidence_word_count"],1)

    def test_low_language_confidence_blocks(self):
        observations=[
            {"word":"море","probability":0.99},
            {"word":"горы","probability":0.99}
        ]
        result=turbo.score("море горы",observations,"ru",0.60)
        self.assertEqual(result["status"],"BLOCKED_TURBO_ASR_TEXT_OR_CONFIDENCE_DIFFERS")


if __name__=="__main__":
    unittest.main()
