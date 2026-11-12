"""No network, paid providers, private Drive access or real client audio."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import motionlab_approved_audio as audio


class ApprovedWavSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.filename="approved.wav"
        self.path=self.root/self.filename
        with wave.open(str(self.path),"wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(24000)
            writer.writeframes(b"\x00\x04"*24000)
        sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
        aid="narration-"+sha[:24]
        self.asset={
            "id":aid,"kind":"narration",
            "recorded_sha256":sha,
            "recorded_size_bytes":self.path.stat().st_size,
            "recorded_duration_seconds":1.0,
        }
        self.project={
            "assets":[{"id":"music-other","kind":"music"},self.asset],
            "stage_handoffs":{"voice_music":{
                "state":"completed","assets":[aid,"music-other"]}},
        }

    def verify(self):
        return audio.verify_approved_narration(self.project,self.root,self.filename)

    def blocks(self,code):
        with self.assertRaises(audio.AudioSourceError) as caught:
            self.verify()
        self.assertIn(code,str(caught.exception))

    def test_exact_source_verified_but_never_authorized(self):
        receipt=self.verify()
        self.assertEqual(receipt["status"],
                         "EXISTING_APPROVED_WAV_SOURCE_VERIFIED_NOT_RENDER_READY")
        self.assertEqual(receipt["sha256"],self.asset["recorded_sha256"])
        self.assertEqual(receipt["paid_calls"],0)
        self.assertFalse(receipt["per_line_timing_verified"])
        self.assertFalse(receipt["mix_verified"])
        self.assertFalse(receipt["render_authorized"])
        self.assertNotIn("file",receipt)

    def test_bytes_tamper_cannot_be_mistaken_for_approved_voice(self):
        raw=bytearray(self.path.read_bytes())
        raw[-1]^=1
        self.path.write_bytes(raw)
        self.blocks("SHA256_MISMATCH")

    def test_inconsistent_metadata_stops(self):
        self.asset["recorded_duration_seconds"]=4
        self.blocks("DURATION_MISMATCH")
        self.asset["recorded_duration_seconds"]=1
        self.asset["recorded_size_bytes"]+=1
        self.blocks("SIZE_MISMATCH")

    def test_wrong_format_blocks_even_when_hash_matches(self):
        with wave.open(str(self.path),"wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16000)
            writer.writeframes(b"\x00\x04"*16000)
        sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.asset["id"]="narration-"+sha[:24]
        self.asset["recorded_sha256"]=sha
        self.asset["recorded_size_bytes"]=self.path.stat().st_size
        self.project["stage_handoffs"]["voice_music"]["assets"]=[
            self.asset["id"],"music-other"]
        self.blocks("FORMAT_INVALID")

    def test_duplicate_approved_narration_blocks(self):
        self.project["assets"].append(dict(self.asset))
        self.blocks("EXACTLY_ONE_APPROVED_NARRATION_REQUIRED")

    def test_stage_and_asset_must_match_canonical_selection(self):
        self.project["stage_handoffs"]["voice_music"]["state"]="pending"
        self.blocks("HANDOFF_NOT_COMPLETE")
        self.project["stage_handoffs"]["voice_music"]["state"]="completed"
        self.project["stage_handoffs"]["voice_music"]["assets"]=["music-other"]
        self.blocks("EXACTLY_ONE_APPROVED_NARRATION_REQUIRED")

    def test_no_path_traversal_or_symlink_escape(self):
        with self.assertRaisesRegex(audio.AudioSourceError,"UNSAFE_NARRATION_FILENAME"):
            audio.verify_approved_narration(self.project,self.root,"../approved.wav")
        self.path.unlink()
        target=self.root/"original.wav"
        with wave.open(str(target),"wb") as writer:
            writer.setnchannels(1);writer.setsampwidth(2)
            writer.setframerate(24000);writer.writeframes(b"\x00\x04"*24000)
        self.path.symlink_to(target)
        self.blocks("PRIVATE_NARRATION_UNAVAILABLE")


if __name__=="__main__":
    unittest.main()
