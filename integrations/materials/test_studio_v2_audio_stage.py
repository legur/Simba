"""Real cross-module v2 audio-lock regression on synthetic approved bytes only.

No Google Drive, provider, GitHub mutation, paid generation, rendering or ASR.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import catalog
import handoff
import studio_audio_lock
import studio_v2_audio_stage as stage_v2
from test_voice_music_writeback import VoiceMusicWritebackTests


class StudioV2SourceBoundAudioStageTests(unittest.TestCase):
    def setUp(self):
        self.case = VoiceMusicWritebackTests(
            "test_approved_selected_text_and_track_to_existing_montage")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

        # A v2 canonical project must actually list EXACT owner-approved
        # narration text as its source. Updating the source invalidates all
        # previous handoffs, so recompute their real receipts before testing.
        self.source = self.case.root / "source.md"
        self.source.write_bytes(b"Sample narration 2")
        self.case.fixture.project["sources"][0]["sha256"] = catalog.digest(self.source)
        self.assertEqual(self.case.fixture.project["sources"][0]["sha256"],
                         self.case.manifest["voice"]["text_sha256"])
        self.case.fixture.project["stage_handoffs"] = {}
        receipt = handoff.source_fingerprint(self.case.fixture.project)
        for name in ("script", "storyboard", "a2e_prompts", "a2e_clips"):
            receipt = self.case.fixture.complete_stage(name, receipt)
        self.case.fixture.save()
        self.case.manifest["input_fingerprint"] = receipt
        self.case.sync()

    def v2candidate(self):
        return self.case.candidate(v2_approved_text_source="source.md")

    def test_existing_actual_wav_and_selected_text_promote_to_metadata_v2(self):
        path, candidate, receipt = self.v2candidate()
        self.assertEqual(path, self.case.path)
        self.assertEqual(receipt["v2_audio_lock_metadata"],
                         "VALID_METADATA_NOT_ALIGNED")
        record = candidate["stage_handoffs"]["voice_music"]
        self.assertEqual(record["schema"], studio_audio_lock.STAGE_SCHEMA)
        self.assertEqual(record["audio_lock"]["mode"], "approved_wav")
        inspection = studio_audio_lock.inspect_v2_audio(
            candidate, handoff.source_fingerprint(candidate))
        self.assertEqual(inspection["status"], "VALID_METADATA")
        self.assertFalse(inspection["external_media_verified"])
        self.assertFalse(inspection["audio_alignment_verified"])
        self.assertFalse(inspection["render_authorized"])
        nxt = handoff.make_handoff(self.case.root, self.case.path, candidate)
        self.assertEqual((nxt["state"], nxt["recipient"]),
                         ("READY_FOR_HANDOFF", "MONTAGE"))
        # CLI build is still read-only; the workflow must explicitly apply.
        before = json.loads(self.case.path.read_text(encoding="utf-8"))
        self.assertNotIn("voice_music", before["stage_handoffs"])
        self.assertFalse(receipt["project_written"])
        self.assertEqual(receipt["paid_calls"], 0)

    def test_legacy_stays_legacy_without_explicit_source_opt_in(self):
        _, candidate, receipt = self.case.candidate()
        stage = candidate["stage_handoffs"]["voice_music"]
        self.assertNotIn("schema", stage)
        self.assertNotIn("audio_lock", stage)
        self.assertEqual(receipt["v2_audio_lock_metadata"],
                         "LEGACY_V1_NO_CANONICAL_AUDIO_LOCK")

    def test_unpinned_or_stale_spoken_text_fails_closed(self):
        with self.assertRaisesRegex(stage_v2.V2AudioLockError,
                                    "V2_APPROVED_VOICE_TEXT_DIFFERS_FROM_CANONICAL_SOURCE"):
            self.case.candidate(v2_approved_text_source="wrong-script.md")
        self.case.fixture.project["sources"][0]["sha256"] = "0" * 64
        self.case.fixture.save()
        with self.assertRaises(Exception):
            self.case.candidate(v2_approved_text_source="source.md")
        self.assertNotIn("voice_music",
                         json.loads(self.case.path.read_text())["stage_handoffs"])

    def test_sha_or_music_license_change_revokes_v2_metadata(self):
        _, project, _ = self.v2candidate()
        modified = copy.deepcopy(project)
        music_id = modified["stage_handoffs"]["voice_music"]["audio_lock"]["music"]["asset_id"]
        music = next(a for a in modified["assets"] if a["id"] == music_id)
        music["recorded_sha256"] = "b" * 64
        self.assertEqual(studio_audio_lock.inspect_v2_audio(
            modified,handoff.source_fingerprint(modified))["status"],"BLOCKED")
        modified = copy.deepcopy(project)
        modified["stage_handoffs"]["voice_music"]["music_license_evidence"] += " altered"
        self.assertEqual(studio_audio_lock.inspect_v2_audio(
            modified,handoff.source_fingerprint(modified))["status"],"BLOCKED")

    def test_validator_does_not_approve_render_or_publish(self):
        _, project, _ = self.v2candidate()
        lock = project["stage_handoffs"]["voice_music"]["audio_lock"]
        self.assertEqual(lock["approved_text_sha256"],
                         self.case.manifest["voice"]["text_sha256"])
        self.assertFalse(studio_audio_lock.inspect_v2_audio(
            project,handoff.source_fingerprint(project))["publication_authorized"])


if __name__ == "__main__":
    unittest.main()
