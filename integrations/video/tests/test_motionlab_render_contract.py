"""Pure zero-paid Montage/Motion Lab #113 contract regression tests.

Uses real local bytes for SHA verification but injects synthetic ffprobe
metadata. Does not synthesize, render, access Drive/GitHub or publish.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import motionlab_render_contract as bridge
import make_video


def scene_option(name: str, camera: str, transition: str, title_fx: str, pct: int) -> dict:
    return {
        "name": name, "description": name + " — целостное оформление выбранных кадров",
        "settings": {
            "camera": camera, "transition": transition, "titleFx": title_fx,
            "subtitleStyle": "clean", "wordMotion": "karaoke", "intensity": pct,
        },
    }


class MotionLabRendererContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.job = Path(self.tmp.name)
        self.assets = {}
        self.launch = {
            "schema": bridge.selector.SCHEMA_LAUNCH,
            "project_id": "test-montage",
            "request_id": "motionlab-test-001",
            "expected_input_fingerprint": "a" * 64,
            "stage": "edit_choice",
            "options": [
                scene_option("Элегантный", "cinematic-zoom", "crossfade", "fade-rise", 30),
                scene_option("Спокойный", "float", "postcard", "fade-rise", 35),
                scene_option("Активный", "push-through", "whip", "fade-rise", 50),
            ],
            "scenes": [],
        }
        spec_scenes = []
        decision_scenes = []
        for i in range(2):
            sid = f"clip-{i + 1:02d}"
            aid = f"verified-a2e-{i + 1}"
            name = f"scene-{i + 1:02d}.mp4"
            data = f"synthetic-only-not-real-MP4-{i}".encode()
            (self.job / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.assets[aid] = {
                "file": name, "sha256": digest, "duration_s": 5.,
                "drive_file_id": f"private-drive-{i}",
            }
            self.launch["scenes"].append({
                "scene_id": sid, "asset_id": aid, "name": f"Сцена {i + 1}",
                "duration_s": 5.0,
                "title_text": f"Титр сцены {i + 1}",
                "subtitle_preview": f"Озвучка {i + 1}",
            })
            spec_scenes.append({
                "clip": name, "title": f"Титр сцены {i + 1}",
                "move": "none",
                "lines": [{"id": f"line-{i+1}", "text": f"Озвучка {i+1}"}],
            })
            decision_scenes.append({
                "scene_id": sid, "order": i + 1, "name": f"Сцена {i + 1}",
                "duration_seconds": 5.0, "asset_id": aid,
                "camera": {"id": "cinematic-zoom", "intensity_percent": 30,
                           "approximate_3d": False},
                "transition": None if i == 0 else {"id": "crossfade", "duration_ms": 900},
                "title": {"effect_id": "fade-rise", "display_text": f"Титр сцены {i + 1}"},
                "subtitles": {"style_id": "clean", "word_motion_id": "karaoke",
                              "preview_text": f"Озвучка {i + 1}",
                              "timing_source": "NOT_PROVIDED_IN_STORYBOARD"},
            })
        self.launch = bridge.with_capabilities(self.launch, self.assets)
        self.approved_spec = {
            "packageId": "test-montage", "size": "1080x1920",
            "sourcePost": "SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/fake-approved.md",
            "voice": {"provider": "simba"},
            "music": {"style": "calm"},
            "scenes": spec_scenes,
            "end": {"brand": "Simba by Bon Tours", "cta": "Спросите об этом путешествии"},
        }
        self.choice = {
            "schema": bridge.selector.SCHEMA_SELECTION,
            "project_id": self.launch["project_id"],
            "request_id": self.launch["request_id"],
            "stage": "edit_choice",
            "expected_input_fingerprint": self.launch["expected_input_fingerprint"],
            "decision": {"selected_option": 1, "options_presented": 3,
                         "user_selected_at": "2026-11-11T08:00:00Z",
                         "state": "USER_SELECTED_IN_CONNECTED_SESSION",
                         "confirmation_scope": "EDIT_CHOICES_ONLY"},
            "format": "9:16",
            "scenes": decision_scenes,
            "guards": {
                "run_render": False, "run_tts": False, "run_a2e": False,
                "run_paid_operations": False, "auto_publish": False,
                "preserve_approved_voice": True,
                "preserve_approved_music": True,
                "preserve_approved_narration": True,
                "production_state": "PREPRODUCTION",
            },
            "next_stage": "MONTAGE_PLANNING_REVIEW",
        }

    def probe(self, path):
        return {"duration_s": 5.0, "width": 1080, "height": 1920,
                "has_audio": False}

    def mapped(self):
        return bridge.map_selection_to_spec(
            self.launch, self.choice, self.approved_spec,
            self.job, self.assets, probe=self.probe,
        )

    def blocked(self, code):
        with self.assertRaises(bridge.ContractError) as ctx:
            self.mapped()
        self.assertEqual(ctx.exception.code, code)
        self.assertEqual(ctx.exception.report()["paid_calls"], 0)

    def test_renderer_capabilities_revision_is_exact_to_source_files(self):
        cap = bridge.renderer_capabilities()
        self.assertEqual(cap["revision_sha256"], bridge.revision())
        self.assertEqual(set(cap["transition"]["renderable"]), make_video.TRANSITIONS)
        self.assertEqual(len(cap["transition"]["renderable"]), 30)
        self.assertEqual(len(cap["subtitle"]["styles"]), 24)
        self.assertEqual(set(cap["camera"]["renderable"]),
                         {"cinematic-zoom", "push-through", "float"})
        self.assertIn("orbit", cap["camera"]["preview_only"])
        self.assertIn("punch-zoom", cap["title_fx"]["preview_only"])
        self.assertEqual(cap["subtitle"]["scope"], "global_one_style_and_motion_per_film")
        film = (HERE / "template" / "film.js").read_text(encoding="utf-8")
        for eid in cap["camera"]["renderable"]:
            self.assertIn("case '" + eid + "':", film)

    def test_verified_choice_maps_only_renderable_fields_preserves_approved_facts(self):
        source = copy.deepcopy(self.approved_spec)
        spec, report = self.mapped()
        self.assertEqual(report["status"], "VIDEO_SPEC_MAPPED_NOT_RENDERED")
        self.assertEqual(report["scene_count"], 2)
        self.assertEqual(report["paid_calls"], 0)
        self.assertFalse(report["render_authorized"])
        self.assertFalse(report["preapproved_wav_reuse_verified"])
        self.assertFalse(report["total_timeline_verified"])
        self.assertEqual(report["remaining_seconds_for_cards_and_voice"], 50.)
        self.assertEqual(spec["sourcePost"], source["sourcePost"])
        self.assertEqual(spec["voice"], source["voice"])
        self.assertEqual(spec["music"], source["music"])
        self.assertEqual(spec["end"], source["end"])
        self.assertEqual(spec["scenes"][0]["cameraEffect"],
                         {"id": "cinematic-zoom", "intensity_percent": 30})
        self.assertEqual(spec["scenes"][0]["move"], "none")
        self.assertEqual(spec["scenes"][0]["titleEffect"], "fade-rise")
        self.assertEqual(spec["scenes"][1]["transition"],
                         {"id": "crossfade", "duration_ms": 900})
        self.assertEqual(spec["subtitleStyle"]["style"], "clean")
        self.assertEqual(spec["subtitleStyle"]["motion"], "karaoke")
        self.assertEqual(self.approved_spec, source)
        # load_spec is strictly static: no paid Gemini/TTS/renderer calls.
        validated = make_video.load_spec(self.job) if (self.job/"video-spec.json").exists() else None
        self.assertIsNone(validated)
        (self.job/"video-spec.json").write_text(json.dumps(spec, ensure_ascii=False))
        parsed = make_video.load_spec(self.job)
        self.assertEqual(parsed["scenes"][0]["cameraEffect"]["id"], "cinematic-zoom")

    def test_preview_only_camera_title_subtitle_and_transition_fail_closed(self):
        self.choice["scenes"][0]["camera"]["id"] = "orbit"
        self.blocked("UNSUPPORTED_CAMERA_EFFECT")
        self.choice["scenes"][0]["camera"]["id"] = "cinematic-zoom"
        self.choice["scenes"][1]["title"]["effect_id"] = "punch-zoom"
        self.blocked("UNSUPPORTED_TITLE_EFFECT")
        self.choice["scenes"][1]["title"]["effect_id"] = "fade-rise"
        self.choice["scenes"][0]["subtitles"]["style_id"] = "none"
        self.blocked("UNSUPPORTED_SUBTITLE_EFFECT")
        self.choice["scenes"][0]["subtitles"]["style_id"] = "clean"
        self.choice["scenes"][1]["transition"]["id"] = "none"
        self.blocked("UNSUPPORTED_TRANSITION")

    def test_global_subtitles_cannot_be_silently_selected_per_scene(self):
        self.choice["scenes"][1]["subtitles"]["style_id"] = "gold-card"
        self.blocked("UNSUPPORTED_PER_SCENE_SUBTITLE")

    def test_source_tamper_and_missing_media_never_map(self):
        self.job.joinpath("scene-02.mp4").write_bytes(b"tampered")
        self.blocked("MEDIA_SHA256_MISMATCH")
        self.job.joinpath("scene-02.mp4").unlink()
        self.blocked("MISSING_VERIFIED_ASSET")

    def test_no_trim_in_v1_and_real_clip_duration_must_match(self):
        self.choice["scenes"][0]["duration_seconds"] = 4.0
        self.blocked("TRIM_REQUIRES_V2")
        self.choice["scenes"][0]["duration_seconds"] = 5.0
        self.approved_spec["scenes"][0]["in"] = 1.0
        self.blocked("TRIM_REQUIRES_V2")

    def test_locked_title_and_preview_text_cannot_be_rewritten(self):
        self.choice["scenes"][0]["title"]["display_text"] = "Новая цена"
        self.blocked("IMMUTABLE_TEXT_CHANGED")
        self.choice["scenes"][0]["title"]["display_text"] = "Титр сцены 1"
        self.choice["scenes"][0]["subtitles"]["preview_text"] = "Другой текст"
        self.blocked("IMMUTABLE_TEXT_CHANGED")

    def test_renderer_revision_and_optional_media_cannot_be_spoofed(self):
        self.launch["renderer_capabilities"]["revision_sha256"] = "0"*64
        self.blocked("RENDERER_CAPABILITIES_MISSING_OR_STALE")
        self.launch["renderer_capabilities"] = bridge.renderer_capabilities()
        self.launch["scenes"][0]["media"]["asset_sha256"] = "f"*64
        self.blocked("MISSING_OR_INVALID_MEDIA_BINDING")

    def test_identical_labels_are_not_three_options(self):
        self.launch["options"][1]["name"] = self.launch["options"][0]["name"]
        self.blocked("THREE_DISTINCT_OPTIONS_REQUIRED")

    def test_offline_draft_or_paid_execution_guard_fails_closed(self):
        self.choice["decision"]["state"] = "DRAFT_NOT_DELIVERED"
        self.blocked("MOTIONLAB_SELECTION_INVALID_OR_STALE")
        self.choice["decision"]["state"] = "USER_SELECTED_IN_CONNECTED_SESSION"
        self.choice["guards"]["run_tts"] = True
        self.blocked("MOTIONLAB_SELECTION_INVALID_OR_STALE")

    def test_untrusted_whisper_timing_rejected(self):
        self.choice["scenes"][0]["subtitles"]["timing_source"] = "FAKE_WHISPER"
        self.blocked("UNTRUSTED_WORD_TIMINGS")

    def test_first_renderable_title_requires_explicit_effect(self):
        self.choice["scenes"][0]["title"]["effect_id"] = "none"
        self.blocked("UNSUPPORTED_TITLE_EFFECT")

    def test_unapproved_source_asset_binding_rejected(self):
        self.assets["verified-a2e-2"]["file"] = "scene-01.mp4"
        self.blocked("SOURCE_BINDING_CHANGED")


if __name__ == "__main__":
    unittest.main()
