"""Offline zero-paid tests for Montage v2 byte and alignment gates.

Test doubles stand in for Studio's independent metadata validator; once
PR #127 is merged, an additional real cross-module integration test is needed.
"""
from __future__ import annotations
import hashlib
import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
import wave

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))
# The Studio contract resides in draft PR #127; do not copy its implementation
# into the Montage branch and accidentally make two owners.
if "studio_audio_lock" not in sys.modules:
    stub = types.ModuleType("studio_audio_lock")
    stub.inspect_v2_audio = lambda project, revision: {"status": "VALID_METADATA"}
    sys.modules["studio_audio_lock"] = stub
if "handoff" not in sys.modules:
    stub = types.ModuleType("handoff")
    stub.source_fingerprint = lambda project: "a" * 64
    sys.modules["handoff"] = stub
import motionlab_v2_audio_gate as gate


class AudioGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with wave.open(str(self.root / "n.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(b"\x00\x00" * 24000)
        (self.root / "music.mp3").write_bytes(b"music-audio" * 600)
        self.nsha = hashlib.sha256((self.root / "n.wav").read_bytes()).hexdigest()
        self.msha = hashlib.sha256((self.root / "music.mp3").read_bytes()).hexdigest()
        self.project = {"id": "test-project", "stage_handoffs": {"voice_music": {
            "audio_lock": {"mode": "approved_wav",
                           "audio_revision_sha256": "b"*64,
                           "narration": {"asset_id": "narration-1","sha256": self.nsha},
                           "music": {"asset_id": "music-1", "sha256": self.msha}}
        }}}

    def verify(self):
        return gate.verify_private_audio_lock(self.project, self.root,
                                              narration_name="n.wav", music_name="music.mp3")

    def test_actual_audio_byte_success_does_not_authorize_render(self):
        result = self.verify()
        self.assertEqual(result["status"], "APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED")
        self.assertTrue(result["music_bytes_verified"])
        self.assertTrue(result["narration_bytes_verified"])
        self.assertFalse(result["render_authorized"])
        self.assertFalse(result["audio_alignment_verified"])

    def test_tampered_music_blocks(self):
        (self.root / "music.mp3").write_bytes(b"tampered" * 800)
        with self.assertRaisesRegex(gate.AudioGateError, "APPROVED_MUSIC_SHA256_MISMATCH"):
            self.verify()

    def test_tampered_wav_blocks(self):
        (self.root / "n.wav").write_bytes((self.root / "n.wav").read_bytes() + b"x")
        with self.assertRaisesRegex(gate.AudioGateError, "APPROVED_NARRATION_SHA256_MISMATCH"):
            self.verify()

    def test_no_symlink(self):
        (self.root / "music.mp3").unlink()
        (self.root / "music.mp3").symlink_to(self.root / "n.wav")
        with self.assertRaisesRegex(gate.AudioGateError, "PRIVATE_AUDIO_FILE_UNAVAILABLE"):
            self.verify()

    def test_no_unapproved_voice(self):
        with self.assertRaisesRegex(gate.AudioGateError, "APPROVED_NARRATION_FILE_REQUIRED"):
            gate.verify_private_audio_lock(self.project, self.root,
                                            narration_name=None, music_name="music.mp3")

    def test_word_alignment_requires_real_evidence_and_returns_no_render(self):
        p = self.verify()
        expected = [{"line_id": "line1", "words": ["Hello", "Prague"]}]
        valid = {"schema": "bontours.montage.audio-alignment/v1",
                 "project_id": "test-project", "narration_sha256": self.nsha,
                 "audio_revision_sha256": "b"*64, "status": "AUDIO_ALIGNMENT_VERIFIED",
                 "method": "external-forced-aligner-v1", "qa_evidence_sha256": "c"*64,
                 "lines": [{"line_id": "line1", "phrase_start_ms": 100,
                            "phrase_end_ms": 700, "words": [
                                {"text": "Hello", "word_start_ms":100, "word_end_ms":300},
                                {"text": "Prague", "word_start_ms":310, "word_end_ms":700}]}]}
        result = gate.validate_alignment_evidence(p, valid, expected)
        self.assertFalse(result["render_authorized"])
        self.assertFalse(result["independent_audio_qa_completed"])
        invalid = {**valid, "qa_evidence_sha256": None}
        with self.assertRaisesRegex(gate.AudioGateError, "AUDIO_ALIGNMENT_QA_EVIDENCE_MISSING"):
            gate.validate_alignment_evidence(p, invalid, expected)
        word = valid["lines"][0]["words"][1]
        word["word_start_ms"] = 290
        with self.assertRaisesRegex(gate.AudioGateError, "AUDIO_ALIGNMENT_WORD_TIMES_INVALID"):
            gate.validate_alignment_evidence(p, valid, expected)


    def test_private_revision_pinned_manifest_readback(self):
        (self.root / "approved-audio-files.json").write_text(json.dumps({
            "audio_revision_sha256": "b" * 64,
            "narration_file": "n.wav",
            "music_file": "music.mp3",
        }), encoding="utf-8")
        result = gate.verify_private_audio_manifest(self.project, self.root)
        self.assertEqual(result["status"], "APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED")
        self.assertFalse(result["render_authorized"])

    def test_private_manifest_revision_change_blocks(self):
        (self.root / "approved-audio-files.json").write_text(json.dumps({
            "audio_revision_sha256": "d" * 64,
            "narration_file": "n.wav",
            "music_file": "music.mp3",
        }), encoding="utf-8")
        with self.assertRaisesRegex(gate.AudioGateError, "PRIVATE_AUDIO_MANIFEST_REVISION_STALE"):
            gate.verify_private_audio_manifest(self.project, self.root)

    def test_private_manifest_path_traversal_blocks(self):
        (self.root / "approved-audio-files.json").write_text(json.dumps({
            "audio_revision_sha256": "b" * 64,
            "narration_file": "../stolen.wav",
            "music_file": "music.mp3",
        }), encoding="utf-8")
        with self.assertRaisesRegex(gate.AudioGateError, "UNSAFE_AUDIO_FILENAME"):
            gate.verify_private_audio_manifest(self.project, self.root)


if __name__ == "__main__":
    unittest.main()
