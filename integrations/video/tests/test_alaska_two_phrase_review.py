"""Synthetic-only tests: two bounded original WAV excerpts. No client audio."""
import io
import struct
import sys
import wave
from pathlib import Path
import unittest

VIDEO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(VIDEO))
import alaska_two_phrase_review as review


def wav_bytes(rate=24000,seconds=41.36):
    output=io.BytesIO()
    with wave.open(output,"wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(b"\x00\x00"*int(rate*seconds))
    return output.getvalue()


class PhraseReviewTests(unittest.TestCase):
    def setUp(self):
        self.wav=wav_bytes()

    def test_two_bounded_original_pcm_excerpts_no_tts(self):
        self.assertEqual(len(review.SLICES),2)
        for name,start,end,index in review.SLICES:
            self.assertTrue(0<end-start<4)
            clip=review.checked_excerpt(self.wav,start,end)
            with wave.open(io.BytesIO(clip),"rb") as w:
                self.assertEqual(w.getframerate(),24000)
                self.assertEqual(w.getnchannels(),1)
                self.assertEqual(w.getsampwidth(),2)
                self.assertLessEqual(abs(w.getnframes()/24000-(end-start)),.0001)
            self.assertTrue(name.endswith(".wav"))
            self.assertIn(index,(22,26))

    def test_wrong_sample_rate_fails(self):
        with self.assertRaisesRegex(review.original.Blocked,"AUDIO_NOT_ORIGINAL"):
            review.checked_excerpt(wav_bytes(rate=16000),12.0,13.0)

    def test_audio_outside_wav_fails(self):
        with self.assertRaisesRegex(review.original.Blocked,"WINDOW_OUT_OF_RANGE"):
            review.checked_excerpt(self.wav,40.0,44.0)

    def test_more_than_four_seconds_fails(self):
        with self.assertRaisesRegex(review.original.Blocked,"WINDOW_OUT_OF_RANGE"):
            review.checked_excerpt(self.wav,0.0,9.0)

    def test_non_pcm_bytes_fails(self):
        with self.assertRaisesRegex(review.original.Blocked,"DECODE_FAILED"):
            review.checked_excerpt(b"x"*10000,11.0,13.0)

    def test_no_duplicate_target_names_or_indices(self):
        self.assertEqual(len(set(x[0] for x in review.SLICES)),2)
        self.assertEqual(len(set(x[3] for x in review.SLICES)),2)


if __name__=="__main__":
    unittest.main()
