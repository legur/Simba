"""Only synthetic text and tokens — no private audio, models, Drive or paid calls."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import alaska_private_medium_asr as m


class MediumASRDiagnosticTests(unittest.TestCase):
    def test_true_unprompted_exact_match_is_still_not_canonical_approval(self):
        text="Светлые горы вдали и корабль у берега"
        tokens=m.normalize(text)
        words=[{"word":x,"start":i*.4,"end":i*.4+.2,
                "probability":.96} for i,x in enumerate(tokens)]
        d=m.analyze_words(text,words,"ru",.97)
        self.assertEqual(d["status"],"PRECANDIDATE_SECOND_ASR_TEXT_MATCHED")
        self.assertTrue(d["exact_token_match"])
        self.assertFalse(d["canonical_audio_lock_approved"])
        self.assertFalse(d["word_timing_verified_for_canonical_v2"])
        self.assertFalse(d["render_authorized"])

    def test_phonetically_similar_place_name_never_makes_unprompted_asr_exact(self):
        text="Ледники и Аляска возле моря"
        heard=["ледники","и","оляска","возле","моря"]
        words=[{"word":w,"start":i*.4,"end":i*.4+.2,
                "probability":.99} for i,w in enumerate(heard)]
        d=m.analyze_words(text,words,"ru",.98)
        self.assertEqual(d["status"],"BLOCKED_MEDIUM_ASR_TEXT_OR_CONFIDENCE_DIFFERS")
        self.assertFalse(d["exact_token_match"])
        self.assertLess(d["token_sequence_similarity"],1)
        self.assertTrue(d["mismatch_positions"])
        self.assertNotIn("оляска",str(d))
        self.assertNotIn("аляска",str(d))

    def test_low_confidence_word_or_wrong_language_always_blocks(self):
        text="Погода и море"
        words=[{"word":w,"start":i*.4,"end":i*.4+.2,
                "probability":.42 if i==1 else .98}
               for i,w in enumerate(m.normalize(text))]
        weak=m.analyze_words(text,words,"ru",1)
        self.assertFalse(weak["exact_token_match"] is False)
        self.assertEqual(weak["status"],"BLOCKED_MEDIUM_ASR_TEXT_OR_CONFIDENCE_DIFFERS")
        self.assertEqual(weak["low_confidence_word_count"],1)
        words[1]["probability"]=.98
        wrong=m.analyze_words(text,words,"en",.99)
        self.assertEqual(wrong["status"],"BLOCKED_MEDIUM_ASR_TEXT_OR_CONFIDENCE_DIFFERS")


if __name__=="__main__":
    unittest.main()
