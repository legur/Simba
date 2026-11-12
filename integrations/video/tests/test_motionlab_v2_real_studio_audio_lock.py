"""Cross-module zero-paid validation: real Studio audio-lock and Montage byte gate.

All files are synthetic temporary local fixtures; no Google Drive access,
TTS, ASR, paid calls, rendering or browser tokens.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

VIDEO = Path(__file__).resolve().parents[1]
MATERIALS = VIDEO.parent / "materials"
for folder in (str(VIDEO), str(MATERIALS)):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import studio_audio_lock as studio
import handoff
import motionlab_v2_audio_gate as montage
from test_studio_audio_lock import StudioAudioLockTests


class RealStudioToMontageAudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

        self.wav = self.root / "approved.wav"
        with wave.open(str(self.wav), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(24000)
            writer.writeframes(b"\\x00\\x01" * 24000)
        self.music = self.root / "music.bin"
        self.music.write_bytes(b"test synthetic music bytes" * 300)

        source = StudioAudioLockTests(methodName="test_valid_canonical_metadata_is_not_media_approval")
        source.setUp()
        self.project = source.project
        self.record = source.record
        assets = {a["id"]: a for a in self.project["assets"]}
        assets["voice-a"]["sha256"] = hashlib.sha256(self.wav.read_bytes()).hexdigest()
        assets["music-a"]["sha256"] = hashlib.sha256(self.music.read_bytes()).hexdigest()
        source.lock()
        self.assertEqual(
            studio.inspect_v2_audio(self.project, handoff.source_fingerprint(self.project))["status"],
            "VALID_METADATA",
        )
        self.manifest = self.root / "approved-audio-files.json"
        self.manifest.write_text(json.dumps({
            "audio_revision_sha256": self.record["audio_lock"]["audio_revision_sha256"],
            "narration_file": self.wav.name,
            "music_file": self.music.name,
        }), encoding="utf-8")

    def test_verified_bytes_still_do_not_authorize_render_or_timings(self):
        result = montage.verify_private_audio_manifest(self.project, self.root)
        self.assertEqual(result["status"], "APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED")
        self.assertTrue(result["music_bytes_verified"])
        self.assertTrue(result["narration_bytes_verified"])
        self.assertFalse(result["audio_alignment_verified"])
        self.assertFalse(result["render_authorized"])
        self.assertEqual(result["paid_calls"], 0)

    def test_mutated_private_music_blocks_even_when_metadata_unchanged(self):
        self.music.write_bytes(b"tampered synthetic music" * 400)
        with self.assertRaisesRegex(montage.AudioGateError, "APPROVED_MUSIC_SHA256_MISMATCH"):
            montage.verify_private_audio_manifest(self.project, self.root)

    def test_invalid_manifest_revision_cannot_pair_with_approved_audio(self):
        wrong = json.loads(self.manifest.read_text(encoding="utf-8"))
        wrong["audio_revision_sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(wrong), encoding="utf-8")
        with self.assertRaisesRegex(montage.AudioGateError, "PRIVATE_AUDIO_MANIFEST_REVISION_STALE"):
            montage.verify_private_audio_manifest(self.project, self.root)

    def test_missing_studio_lock_fails_closed(self):
        self.record.pop("audio_lock")
        with self.assertRaisesRegex(montage.AudioGateError, "STUDIO_AUDIO_LOCK_NOT_VERIFIED"):
            montage.verify_private_audio_lock(self.project, self.root,
                                              narration_name="approved.wav", music_name="music.bin")


if __name__ == "__main__":
    unittest.main()
