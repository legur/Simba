"""No-credential, no-model unit tests for the private Alaska acoustic preflight."""
from __future__ import annotations
import io
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import alaska_private_dual_audio_preflight as a


class FakeDrive:
    def __init__(self,raw,name="WarmBaritone.wav",
                 folder=a.AUDIO_DIR,mime="audio/x-wav",public=False):
        self.raw=raw
        self.name=name
        self.folder=folder
        self.mime=mime
        self.public=public
        self.command=None
        self.requests=[]
    def files(self):return self
    def permissions(self):return self
    def get(self,fileId,fields):self.command="meta";self.requests.append(fileId);return self
    def get_media(self,fileId):self.command="media";self.requests.append(fileId);return self
    def list(self,fileId,fields,pageSize):
        self.command="permissions";self.requests.append(fileId);return self
    def execute(self):
        if self.command=="meta":
            return {"id":a.WAV_ID,"parents":[self.folder],"name":self.name,
                    "mimeType":self.mime,"size":len(self.raw),"trashed":False}
        if self.command=="media":return self.raw
        return {"permissions":[{"type":"anyone" if self.public else "user",
                                "role":"owner"}]}


def synthetic_wav(duration_s=41.36):
    buffer=io.BytesIO()
    with wave.open(buffer,"wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(b"\0\0"*int(24000*duration_s))
    return buffer.getvalue()


class AlaskaPrivateAudioSourceTests(unittest.TestCase):
    def test_real_named_source_requires_editorial_prefix_and_removes_it(self):
        actual={"packageId":a.PROJECT,
                "sourcePost":"Сводная утвержденная озвучка v1: " + "Ледники, горы и Аляска с моря. "*8}
        spoken=a.approved_narration(actual)
        self.assertNotIn("Сводная",spoken)
        self.assertTrue(spoken.startswith("Ледники"))
        with self.assertRaisesRegex(a.Blocked,"EXPECTED_V1_EDITORIAL_PREFIX_CHANGED"):
            a.approved_narration({**actual,"sourcePost":spoken})

    def test_24k_pcm_mono_wav_and_duration_pinned(self):
        raw=synthetic_wav()
        self.assertEqual(a.inspect_wav(raw),41.36)
        with self.assertRaisesRegex(a.Blocked,"WAV_FORMAT_OR_LENGTH_CHANGED"):
            a.inspect_wav(synthetic_wav(13.0))
        with self.assertRaisesRegex(a.Blocked,"WAV_ENCODING_INVALID"):
            a.inspect_wav(b"not a wav")

    def test_private_source_exact_filename_sha_and_parent(self):
        raw=synthetic_wav()
        fake=FakeDrive(raw)
        read=a.read_private(fake,a.WAV_ID,a.AUDIO_DIR,"WarmBaritone.wav",
                            a.digest(raw),a.MAX_WAV,{"audio/x-wav"})
        self.assertEqual(read,raw)
        self.assertEqual(fake.requests.count(a.WAV_ID),3)
        for invalid in (FakeDrive(raw,public=True),
                        FakeDrive(raw,folder="wrong-folder"),
                        FakeDrive(raw,name="other.wav")):
            with self.assertRaisesRegex(a.Blocked,
                                        "PRIVATE_SOURCE_"):
                a.read_private(invalid,a.WAV_ID,a.AUDIO_DIR,
                     "WarmBaritone.wav",a.digest(raw),a.MAX_WAV,{"audio/x-wav"})
        with self.assertRaisesRegex(a.Blocked,"PRIVATE_SOURCE_HASH_CHANGED"):
            a.read_private(FakeDrive(raw),a.WAV_ID,a.AUDIO_DIR,
                 "WarmBaritone.wav","f"*64,a.MAX_WAV,{"audio/x-wav"})

    def test_phrasewise_ctc_uses_unprompted_asr_time_anchors(self):
        spoken="Первый красивый лайнер на море. Второй лайнер идет домой. Третий большой лайнер прибыл вечером."
        words=a.normalize(spoken)
        observations=[]
        for i,word in enumerate(words):
            # Each lexical token carries genuine independent ASR timing
            # positions in the test, not any fabricated user-selected edit.
            observations.append({"word":word,
                                 "start":i*.45+(i//5)*.60,
                                 "end":i*.45+.26+(i//5)*.60,
                                 "probability":.98})
        windows=a.sentence_windows(spoken,observations,12.0)
        self.assertEqual(len(windows),3)
        self.assertEqual([a.normalize(x["text"]) for x in windows],
                         [a.normalize(x) for x in
                          ("Первый красивый лайнер на море.",
                           "Второй лайнер идет домой.",
                           "Третий большой лайнер прибыл вечером.")])
        for earlier,later in zip(windows,windows[1:]):
            self.assertLessEqual(earlier["end"],later["start"])
        self.assertTrue(all(0<=x["start"]<x["end"]<=12 for x in windows))

    def test_missing_unprompted_asr_sentence_anchors_blocks_ctc(self):
        spoken="Ледники возле моря. Возвращение через порт. Лайнер идет на север."
        observation=[{"word":word,"start":i*.25,
                      "end":i*.25+.15,"probability":.9}
                     for i,word in enumerate(a.normalize("Ледники возле моря. Лайнер идет на север."))]
        with self.assertRaisesRegex(a.Blocked,
                        "CTC_INSUFFICIENT_INDEPENDENT_SENTENCE_ANCHORS"):
            a.sentence_windows(spoken,observation,10)

    def test_redacted_diagnostic_pinpoints_missing_numeric_ctc_timings(self):
        approved=["двадцать","27","августа","джуно"]
        asr=[{"word":w,"start":i*.5,"end":i*.5+.3,"probability":.9}
             for i,w in enumerate(["двадцать","двадцать","августа","джуну"])]
        asr[-1]["probability"]=.51
        ctc=[{"word":word,"start":i*.5,"end":i*.5+.3}
             for i,word in enumerate(approved)]
        ctc[1].pop("start")
        detail=a.redacted_evidence(approved,asr,ctc,5)
        self.assertEqual(detail["approved_numeric_token_positions"],[1])
        self.assertEqual(detail["ctc_missing_timing_positions"],[1])
        self.assertEqual(detail["independent_asr_weak_word_positions"],[3])
        self.assertFalse("джуно" in str(detail))
        self.assertFalse("джуну" in str(detail))
        self.assertTrue(detail["independent_asr_mismatch_spans"])

    def test_numpy_style_real_timestamp_scalars_are_not_missing(self):
        from fractions import Fraction
        import math
        # Fraction is an alternative numbers.Real scalar with a different
        # exact type. WhisperX Pandas often uses np.float64/np.float32.
        self.assertTrue(a.verified_time(Fraction(2,5)))
        self.assertTrue(a.verified_time(Fraction(3,2)))
        self.assertFalse(a.verified_time(True))
        self.assertFalse(a.verified_time("0.2"))
        self.assertFalse(a.verified_time(float("nan")))
        self.assertFalse(a.verified_time(float("inf")))
        self.assertFalse(a.verified_time(None))
        approved=["ледники","алясκа"]
        asr=[{"word":"ледники","probability":.99},
             {"word":"алясκа","probability":.99}]
        ctc=[
          {"word":"ледники","start":Fraction(1,10),"end":Fraction(2,5)},
          {"word":"алясκа","start":Fraction(2,5),"end":Fraction(9,10)}
        ]
        evidence=a.redacted_evidence(approved,asr,ctc,1.0)
        self.assertEqual(evidence["ctc_missing_count"],0)
        self.assertEqual(evidence["ctc_invalid_type_count"],0)
        self.assertEqual(evidence["ctc_out_of_range_count"],0)
        self.assertEqual(evidence["ctc_nonmonotonic_count"],0)
        self.assertEqual(evidence["ctc_start_types"],{"Fraction":2})

    def test_timeline_diagnostic_still_blocks_bad_numeric_values(self):
        approved=["ледники"]
        asr=[{"word":"ледники","probability":.99}]
        ctc=[{"word":"ледники","start":True,"end":float("nan")}]
        e=a.redacted_evidence(approved,asr,ctc,3.0)
        self.assertEqual(e["ctc_invalid_type_count"],1)
        self.assertEqual(e["ctc_missing_count"],0)

    def test_narration_tokenizer_does_not_invent_subtitles(self):
        self.assertEqual(a.normalize("Джуно, Сиэтл!"),["джуно","сиэтл"])
        self.assertEqual(a.normalize("Voyager of the Seas"),["voyager","of","the","seas"])
        self.assertEqual(a.normalize("27 августа — 3 сентября"),["27","августа","3","сентября"])


if __name__=="__main__":
    unittest.main()
