"""Offline policy checks for new Simba Gemini TTS requests."""
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


def fake_wav():
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x01\x00" * 24000)
    return out.getvalue()


TRUSTED_WORKFLOW_ENV = {
    "GEMINI_API_KEY": "offline-placeholder",
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


class GitHubSecretsGuardTests(unittest.TestCase):
    def test_injected_generator_cannot_create_local_cache_miss(self):
        calls = []

        def injected_generator(*args):
            calls.append(args)
            return fake_wav()

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            with patch.dict(os.environ, {"GEMINI_API_KEY": "local-secret"}, clear=True):
                with self.assertRaisesRegex(simba_voice.VoiceError, "GitHub Actions workflow"):
                    simba_voice.synthesize_lines(
                        [{"id": "line", "text": "Привет."}], cache,
                        voice_id="voice_private123",
                        generate=injected_generator,
                    )

            self.assertEqual(calls, [])
            self.assertEqual(list(cache.glob("*.attempt.json")), [])

    def test_checkout_and_workflow_sha_must_match_full_commit(self):
        for field, value in (
                ("GITHUB_WORKFLOW_SHA", "b" * 40),
                ("GITHUB_SHA", "not-a-full-commit")):
            with self.subTest(field=field):
                env = dict(TRUSTED_WORKFLOW_ENV)
                env[field] = value
                network_calls = []

                def urlopen(*args, **kwargs):
                    network_calls.append((args, kwargs))
                    raise simba_voice.VoiceError("network boundary reached")

                with patch.dict(os.environ, env, clear=True), \
                        patch.object(simba_voice.urllib.request, "urlopen", urlopen):
                    with self.assertRaisesRegex(
                            simba_voice.VoiceError, "GitHub Actions workflow"):
                        simba_voice._generate_once(
                            "Привет.", "voice_private123", "gemini-3.8-flash-tts"
                        )

                self.assertEqual(network_calls, [])

    def test_local_drive_oauth_is_blocked_before_sdk_or_network(self):
        oauth_imports = []
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name.startswith("google"):
                oauth_imports.append(name)
                raise simba_voice.VoiceError("OAuth SDK boundary reached")
            return real_import(name, *args, **kwargs)

        env = {
            "GDRIVE_OAUTH_CLIENT_ID": "local-client",
            "GDRIVE_OAUTH_CLIENT_SECRET": "local-secret",
            "GDRIVE_OAUTH_REFRESH_TOKEN": "local-refresh",
        }
        with patch.dict(os.environ, env, clear=True), \
                patch("builtins.__import__", side_effect=guarded_import):
            with self.assertRaisesRegex(simba_voice.VoiceError, "GitHub Actions workflow"):
                simba_voice.voice_id_from_private_store()

        self.assertEqual(oauth_imports, [])

    def test_wrapper_cannot_bypass_guard_inside_real_generator(self):
        network_calls = []
        wav = fake_wav()
        body = json.dumps({
            "output_audio": {"data": base64.b64encode(wav).decode("ascii")}
        }).encode("utf-8")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return body

        def urlopen(*args, **kwargs):
            network_calls.append((args, kwargs))
            return Response()

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "local-secret"}, clear=True), \
                    patch.object(simba_voice.urllib.request, "urlopen", urlopen):
                with self.assertRaisesRegex(simba_voice.VoiceError, "GitHub Actions workflow"):
                    simba_voice.synthesize_lines(
                        [{"id": "line", "text": "Привет."}], Path(tmp),
                        voice_id="voice_private123",
                        generate=lambda *args: simba_voice._generate_once(*args),
                    )

        self.assertEqual(network_calls, [])

    def test_rerun_by_non_owner_cannot_start_real_synthesis(self):
        env = dict(TRUSTED_WORKFLOW_ENV)
        env["GITHUB_TRIGGERING_ACTOR"] = "other-user"
        calls = []

        def external_request(*args, **kwargs):
            calls.append(args)
            return fake_wav()

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            with patch.dict(os.environ, env, clear=True), \
                    patch.object(simba_voice, "_generate_once", external_request):
                with self.assertRaisesRegex(simba_voice.VoiceError, "GitHub Actions workflow"):
                    simba_voice.synthesize_lines(
                        [{"id": "line", "text": "Привет."}], cache,
                        voice_id="voice_private123",
                    )

            self.assertEqual(calls, [])
            self.assertEqual(list(cache.glob("*.attempt.json")), [])

    def test_local_environment_cannot_start_real_synthesis_or_attempt_journal(self):
        calls = []

        def external_request(*args, **kwargs):
            calls.append(args)
            return fake_wav()

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            with patch.dict(os.environ, {"GEMINI_API_KEY": "local-secret"}, clear=True), \
                    patch.object(simba_voice, "_generate_once", external_request):
                with self.assertRaisesRegex(simba_voice.VoiceError, "GitHub Actions workflow"):
                    simba_voice.synthesize_lines(
                        [{"id": "line", "text": "Привет."}], cache,
                        voice_id="voice_private123",
                    )

            self.assertEqual(calls, [])
            self.assertEqual(list(cache.glob("*.attempt.json")), [])
            self.assertEqual(list(cache.glob("*.wav")), [])

    def test_trusted_manual_main_workflow_can_start_real_synthesis(self):
        calls = []

        def external_request(text, voice_id, model, *, response_path=None):
            calls.append((text, voice_id, model))
            return fake_wav()

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            with patch.dict(os.environ, TRUSTED_WORKFLOW_ENV, clear=True), \
                    patch.object(simba_voice, "_generate_once", external_request):
                result = simba_voice.synthesize_lines(
                    [{"id": "line", "text": "Привет."}], cache,
                    voice_id="voice_private123",
                )

            self.assertEqual(calls, [(
                "Привет.", "voice_private123", "gemini-3.8-flash-tts"
            )])
            self.assertEqual(result["line"].read_bytes(), fake_wav())
            self.assertEqual(len(list(cache.glob("*.attempt.json"))), 1)

    def test_existing_cache_remains_available_outside_github_actions(self):
        calls = []

        def external_request(*args, **kwargs):
            calls.append(args)
            return fake_wav()

        lines = [{"id": "line", "text": "Привет."}]
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            with patch.dict(os.environ, TRUSTED_WORKFLOW_ENV, clear=True), \
                    patch.object(simba_voice, "_generate_once", external_request):
                created = simba_voice.synthesize_lines(
                    lines, cache, voice_id="voice_private123"
                )
            with patch.dict(os.environ, {}, clear=True), \
                    patch.object(simba_voice, "_generate_once", external_request):
                reused = simba_voice.synthesize_lines(
                    lines, cache, voice_id="voice_private123"
                )

            self.assertEqual(created, reused)
            self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()

