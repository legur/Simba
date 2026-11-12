"""Studio v2 audio-lock regression and fail-closed contract tests. No real media/provider writes."""
from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import handoff
import studio_audio_lock as audio


def sha(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class StudioAudioLockTests(unittest.TestCase):
    def setUp(self):
        self.project = {
            "id": "test-reel",
            "sources": [{"path": "approved-script.md", "sha256": sha("approved text 1")}],
            "assets": [
                {"id": "voice-a", "kind": "narration", "state": "available",
                 "sha256": sha("private wav bytes"), "evidence": "approved bytes"},
                {"id": "music-a", "kind": "music", "state": "available",
                 "sha256": sha("private music bytes"), "evidence": "license"},
                {"id": "clip-a", "kind": "animated_clip", "state": "available",
                 "sha256": sha("private A2E clip bytes"), "evidence": "approved clip"},
            ],
            "stage_handoffs": {},
        }
        self.record = {
            "schema": audio.STAGE_SCHEMA,
            "state": "completed", "input_fingerprint": sha("upstream stage receipt"),
            "assets": ["voice-a", "music-a"],
            "approval_evidence": "Owner approved specific WAV and licensed music",
            "voice_profile": "simba_warmbaritone",
            "texts_presented": 3, "music_presented": 3,
            "text_option": 1, "music_option": 2,
            "music_license_evidence": "commercial use license checked",
        }
        self.lock()
        self.project["stage_handoffs"]["voice_music"] = self.record

    def lock(self, mode="approved_wav", narration="voice-a", music="music-a"):
        assets = {a["id"]: a for a in self.project["assets"]}
        self.record["voice_profile"] = ("simba_warmbaritone" if mode == "approved_wav" else "none")
        if mode == "approved_clip_audio":
            self.record["assets"] = [narration, music]
        elif mode == "no_narration":
            self.record["assets"] = [music]
        else:
            self.record["assets"] = [narration, music]
        item = {
            "schema": audio.SCHEMA,
            "source_revision_sha256": handoff.source_fingerprint(self.project),
            "stage_input_fingerprint": self.record["input_fingerprint"],
            "approved_text_source_path": "approved-script.md",
            "approved_text_sha256": self.project["sources"][0]["sha256"],
            "voice_profile": self.record["voice_profile"],
            "mode": mode,
            "narration": ({"asset_id": narration, "sha256": assets[narration]["sha256"]}
                          if mode != "no_narration" else None),
            "music": {"asset_id": music, "sha256": assets[music]["sha256"]},
            "music_license_sha256": sha(self.record["music_license_evidence"]),
        }
        item["audio_revision_sha256"] = audio.revision_for(item)
        self.record["audio_lock"] = item
        return item

    def inspect(self):
        return audio.inspect_v2_audio(self.project, handoff.source_fingerprint(self.project))

    def test_valid_canonical_metadata_is_not_media_approval(self):
        result = self.inspect()
        self.assertEqual(result["status"], "VALID_METADATA")
        self.assertEqual(result["reason"], "EXTERNAL_AUDIO_BYTES_NOT_VERIFIED")
        self.assertEqual(result["audio_revision_sha256"],
                         self.record["audio_lock"]["audio_revision_sha256"])
        for name in ("external_media_verified", "audio_alignment_verified",
                     "render_authorized", "paid_operations_authorized",
                     "publication_authorized"):
            self.assertIs(result[name], False)
        parsed, issues = handoff._validate_stage(
            self.project, "voice_music", self.record, self.record["input_fingerprint"])
        self.assertEqual(issues, [])
        self.assertIsNotNone(parsed["receipt"])

    def test_legacy_stage_readable_but_not_sufficient_for_v2(self):
        self.record.pop("audio_lock")
        self.record.pop("schema")
        parsed, issues = handoff._validate_stage(
            self.project, "voice_music", self.record, self.record["input_fingerprint"])
        self.assertEqual(issues, [])
        self.assertIsNotNone(parsed)
        self.assertEqual(self.inspect()["reason"], "V2_VOICE_MUSIC_SCHEMA_REQUIRED")

    def test_v2_declared_without_lock_blocks(self):
        self.record.pop("audio_lock")
        parsed, errors = handoff._validate_stage(
            self.project, "voice_music", self.record, self.record["input_fingerprint"])
        self.assertIsNone(parsed)
        self.assertIn("audio_lock", " ".join(errors))
        self.assertEqual(self.inspect()["reason"], "V2_CANONICAL_AUDIO_NOT_VERIFIED")

    def test_lock_without_v2_schema_is_not_silent_upgrade(self):
        self.record.pop("schema")
        _, problems = handoff._validate_stage(
            self.project, "voice_music", self.record, self.record["input_fingerprint"])
        self.assertIn("requires Studio v2", " ".join(problems))

    def test_audio_asset_sha_change_invalidates_stage(self):
        prior = handoff._validate_stage(
            self.project, "voice_music", self.record, self.record["input_fingerprint"])[0]["receipt"]
        self.project["assets"][0]["sha256"] = sha("new approved WAV bytes")
        self.assertEqual(self.inspect()["status"], "BLOCKED")
        self.assertIn("metadata SHA", " ".join(self.inspect()["issues"]))
        self.lock()
        new = handoff._validate_stage(
            self.project, "voice_music", self.record, self.record["input_fingerprint"])[0]["receipt"]
        self.assertNotEqual(prior, new)
        later = {"state": "approved", "input_fingerprint": prior,
                 "approval_evidence": "owner approval on old audio",
                 "assets": ["music-a"], "selected_option": 2,
                 "options_presented": 3, "options_evidence": "shown"}
        _, issues = handoff._validate_stage(self.project, "edit_choice", later, new)
        self.assertIn("stale", " ".join(issues))

    def test_existing_montage_recorded_sha256_is_compatible(self):
        wav = self.project["assets"][0]
        music = self.project["assets"][1]
        wav["recorded_sha256"] = wav.pop("sha256")
        music["recorded_sha256"] = music.pop("sha256")
        self.assertEqual(self.inspect()["status"], "VALID_METADATA")

    def test_conflicting_dual_audio_hashes_fail_closed(self):
        self.project["assets"][0]["recorded_sha256"] = sha("contradiction")
        self.assertEqual(self.inspect()["status"], "BLOCKED")
        self.assertIn("metadata SHA", " ".join(self.inspect()["issues"]))

    def test_music_asset_sha_change_blocks(self):
        self.project["assets"][1]["sha256"] = sha("different music file")
        self.assertIn("metadata SHA", " ".join(self.inspect()["issues"]))

    def test_source_revision_change_blocks(self):
        self.project["sources"][0]["sha256"] = sha("updated approved script")
        self.assertIn("stale canonical source", " ".join(self.inspect()["issues"]))

    def test_music_license_change_blocks(self):
        self.record["music_license_evidence"] = "different license text"
        self.assertIn("music license", " ".join(self.inspect()["issues"]))

    def test_voice_profile_change_blocks(self):
        self.record["voice_profile"] = "none"
        self.assertIn("voice profile", " ".join(self.inspect()["issues"]))

    def test_audio_revision_tamper_blocks(self):
        self.record["audio_lock"]["audio_revision_sha256"] = sha("forgery")
        self.assertIn("revision digest", " ".join(self.inspect()["issues"]))

    def test_unsupported_modes_and_extra_fields_block(self):
        self.record["audio_lock"]["mode"] = {"nested": "invalid"}
        self.assertEqual(self.inspect()["status"], "BLOCKED")
        self.lock()
        self.record["audio_lock"]["unexpected"] = "field"
        self.assertIn("unexpected", " ".join(self.inspect()["issues"]))

    def test_voice_and_music_kind_swap_blocks(self):
        self.record["audio_lock"]["music"]["asset_id"] = "voice-a"
        self.assertIn("wrong kind", " ".join(self.inspect()["issues"]))

    def test_unselected_narration_blocks(self):
        self.record["assets"] = ["music-a"]
        self.assertIn("not selected", " ".join(self.inspect()["issues"]))

    def test_approved_clip_audio_is_supported_without_tts(self):
        self.lock(mode="approved_clip_audio", narration="clip-a")
        status = self.inspect()
        self.assertEqual(status["status"], "VALID_METADATA")
        self.assertEqual(self.record["voice_profile"], "none")
        self.assertFalse(status["render_authorized"])

    def test_no_narration_mode_is_explicit(self):
        self.lock(mode="no_narration")
        self.assertEqual(self.inspect()["status"], "VALID_METADATA")
        self.record["audio_lock"]["narration"] = {"asset_id": "voice-a", "sha256": sha("x")}
        self.assertIn("must be null", " ".join(self.inspect()["issues"]))

    def test_incomplete_approved_voice_stage_blocks(self):
        self.record["state"] = "pending"
        self.assertEqual(self.inspect()["reason"], "VOICE_MUSIC_NOT_APPROVED")

    def test_missing_owner_approval_blocks_standalone_v2_inspection(self):
        self.record["approval_evidence"] = ""
        self.assertEqual(self.inspect()["reason"], "VOICE_MUSIC_APPROVAL_EVIDENCE_MISSING")

    def test_missing_three_choices_blocks_standalone_v2_inspection(self):
        self.record["texts_presented"] = 2
        self.assertEqual(self.inspect()["reason"], "VOICE_MUSIC_SELECTED_OPTIONS_NOT_VERIFIED")
        self.record["texts_presented"] = 3
        self.record["music_option"] = 4
        self.assertEqual(self.inspect()["reason"], "VOICE_MUSIC_SELECTED_OPTIONS_NOT_VERIFIED")

    def test_schema_and_lock_do_not_modify_canonical_project(self):
        snapshot = copy.deepcopy(self.project)
        self.inspect()
        handoff._validate_stage(self.project, "voice_music",
                                self.record, self.record["input_fingerprint"])
        self.assertEqual(self.project, snapshot)


if __name__ == "__main__":
    unittest.main()
