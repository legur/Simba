"""Offline tests of approved Simba Gemini narration (NO network, billing or Drive)."""
import base64
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simba_voice
from make_video import voice_provider, load_spec, Stop


def fake_wav(duration_s=0.7):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x02\x00" * int(24000 * duration_s))
    return out.getvalue()


TRUSTED_WORKFLOW_ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_ACTOR": "legur",
    "GITHUB_TRIGGERING_ACTOR": "legur",
    "GITHUB_REPOSITORY_OWNER": "legur",
    "GITHUB_REPOSITORY": "legur/Simba",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_SHA": "a" * 40,
    "GITHUB_WORKFLOW_SHA": "a" * 40,
    "GITHUB_WORKFLOW": "Simba video — private GitHub Secrets render",
    "GITHUB_WORKFLOW_REF": (
        "legur/Simba/.github/workflows/"
        "simba-video-secrets-render.yml@refs/heads/main"
    ),
}


class SelectedVoiceTests(unittest.TestCase):
    def setUp(self):
        workflow = patch.dict(os.environ, TRUSTED_WORKFLOW_ENV)
        workflow.start()
        self.addCleanup(workflow.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.job = Path(self.tmp.name)
        self.cache = self.job / "cache"

    def test_voice_approval_is_canonical(self):
        d = simba_voice.approved_profile()
        self.assertEqual(d["profile"], "WarmBaritone")
        self.assertEqual(d["selection_status"], "approved_by_user")

    def test_voice_default_and_explicit_edge(self):
        self.assertEqual(voice_provider({}), "simba")
        self.assertEqual(voice_provider({"voice": {"name": "ru-RU-DmitryNeural"}}), "simba")
        self.assertEqual(voice_provider({"voice": {"provider": "edge"}}), "edge")
        with self.assertRaises(Stop):
            voice_provider({"voice": {"provider": "unknown"}})

    def test_private_voice_id_from_file(self):
        profile = {"voice_id": "voice_warmBaritone123", "label": "Simba — Теплый баритон",
                   "provider": "Google Gemini", "model": "gemini-3.8-flash-tts",
                   "gender": "male", "language_code": "ru-RU", "type": "prompted"}
        private = self.job / "voice.json"
        private.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        env = {"SIMBA_GEMINI_VOICE_ID": "", "SIMBA_GEMINI_VOICE_METADATA_FILE": str(private)}
        with patch.dict(os.environ, env):
            self.assertEqual(simba_voice.voice_id_from_private_store(), profile["voice_id"])
        profile["gender"] = "female"
        private.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        with patch.dict(os.environ, env):
            with self.assertRaises(simba_voice.VoiceError):
                simba_voice.voice_id_from_private_store()

    def test_response_parser_matches_working_gemini_rest_shape(self):
        wav = fake_wav()
        response = {"steps": [{"type": "model_output", "content": [
            {"type": "audio", "data": base64.b64encode(wav).decode()}]}]}
        self.assertEqual(simba_voice._audio_from_response(response), wav)
        with self.assertRaisesRegex(simba_voice.VoiceError, "missing"):
            simba_voice._audio_from_response({"output": []})

    def test_one_paid_attempt_then_exact_cache_reuse(self):
        calls = []
        wav = fake_wav()
        def generate(text, voice_id, model):
            calls.append((text, voice_id, model))
            journals = list(self.cache.glob("*.attempt.json"))
            self.assertEqual(len(journals), 1, "attempt journal must precede paid call")
            return wav
        lines = [{"id": "l01", "text": "Встречаем новый год в Праге."}]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-for-offline-test"}):
            first = simba_voice.synthesize_lines(lines, self.cache, voice_id="voice_private123",
                                                 generate=generate)
            second = simba_voice.synthesize_lines(lines, self.cache, voice_id="voice_private123",
                                                  generate=generate)
        self.assertEqual(len(calls), 1)
        self.assertEqual(first, second)
        self.assertEqual(next(iter(first.values())).read_bytes(), wav)

    def test_uncertain_result_cannot_double_bill(self):
        calls = []
        def fail(text, voice_id, model):
            calls.append(text)
            raise simba_voice.VoiceError("ambiguous timeout")
        lines = [{"id": "l01", "text": "Здравствуйте!"}]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-for-offline-test"}):
            with self.assertRaisesRegex(simba_voice.VoiceError, "ambiguous"):
                simba_voice.synthesize_lines(lines, self.cache, voice_id="voice_private123",
                                             generate=fail)
            with self.assertRaisesRegex(simba_voice.VoiceError, "Earlier Gemini attempt"):
                simba_voice.synthesize_lines(lines, self.cache, voice_id="voice_private123",
                                             generate=fail)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(list(self.cache.glob("*.attempt.json"))), 1)

    def test_preflight_cap_blocks_paid_calls(self):
        lines = [{"id": f"l{i:02d}", "text": f"Строка номер {i}"} for i in range(19)]
        calls = []
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-for-offline-test"}):
            with self.assertRaisesRegex(simba_voice.VoiceError, "cap exceeded"):
                simba_voice.synthesize_lines(lines, self.cache, voice_id="voice_private123",
                                             generate=lambda *_: calls.append(1))
        self.assertEqual(calls, [])
        self.assertEqual(list(self.cache.glob("*.attempt.json")), [])

    def test_clip_lines_not_sent_to_tts(self):
        calls=[]
        lines=[{"id":"l01","text":"Already in clip","fromClip":True}]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-for-offline-test"}):
            self.assertEqual(simba_voice.synthesize_lines(lines,self.cache,voice_id="voice_private123",
                                                          generate=lambda *_: calls.append(1)),{})
        self.assertEqual(calls,[])

    def test_clips_use_simba_tts_by_default(self):
        job = self.job
        (job / "scene.mp4").write_bytes(b"dummy")
        spec = {
            "packageId": "simba-voice-offline-test",
            "sourcePost": "not-read-in-load_spec",
            "size": "1080x1920",
            "scenes": [{"clip": "scene.mp4", "lines": [{"text": "Путешествие начинается."}]}],
        }
        (job / "video-spec.json").write_text(json.dumps(spec),encoding="utf-8")
        with patch("music_input.validate_music", return_value=None):
            loaded = load_spec(job)
        self.assertEqual(loaded["scenes"][0]["voice"], "tts")


if __name__ == "__main__":
    unittest.main()
