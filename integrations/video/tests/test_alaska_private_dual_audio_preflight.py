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

    def test_narration_tokenizer_does_not_invent_subtitles(self):
        self.assertEqual(a.normalize("Джуно, Сиэтл!"),["джуно","сиэтл"])
        self.assertEqual(a.normalize("Voyager of the Seas"),["voyager","of","the","seas"])
        self.assertEqual(a.normalize("27 августа — 3 сентября"),["27","августа","3","сентября"])


if __name__=="__main__":
    unittest.main()
