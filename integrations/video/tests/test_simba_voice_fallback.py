"""Offline fallback checks: no network, credentials or billable synthesis."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from test_simba_voice import fake_wav
import simba_voice as voice

PRIMARY = 'gemini-3.8-flash-tts'
FALLBACK = 'gemini-3.8-flash-lite-tts'
TRUSTED_WORKFLOW_ENV = {
    'GITHUB_ACTIONS': 'true',
    'GITHUB_EVENT_NAME': 'workflow_dispatch',
    'GITHUB_ACTOR': 'legur',
    'GITHUB_TRIGGERING_ACTOR': 'legur',
    'GITHUB_REPOSITORY_OWNER': 'legur',
    'GITHUB_REPOSITORY': 'legur/Simba',
    'GITHUB_REF': 'refs/heads/main',
    'GITHUB_SHA': 'a' * 40,
    'GITHUB_WORKFLOW_SHA': 'a' * 40,
    'GITHUB_WORKFLOW': 'Simba video — private GitHub Secrets render',
    'GITHUB_WORKFLOW_REF': (
        'legur/Simba/.github/workflows/'
        'simba-video-secrets-render.yml@refs/heads/main'
    ),
}


class VoiceFallbackTests(unittest.TestCase):
    def setUp(self):
        workflow = patch.dict(os.environ, TRUSTED_WORKFLOW_ENV)
        workflow.start()
        self.addCleanup(workflow.stop)

    def test_duplicate_lines_generate_only_once(self):
        calls=[]
        lines=[{'id':'a','text':'Привет.'},{'id':'b','text':'Привет.'}]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY':'offline'}):
            def generate(*args):
                calls.append(args)
                return fake_wav()
            result=voice.synthesize_lines(lines,Path(tmp),voice_id='voice_private123',generate=generate)
            self.assertEqual(len(calls),1)
            self.assertEqual(result['a'],result['b'])

    def test_explicit_no_fallback_stops_after_one_uncertain_attempt(self):
        calls = []
        def generate(text, voice_id, model):
            calls.append(model)
            raise voice.ProviderUnavailable('timeout', may_have_been_billed=True)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY':'offline'}):
            for _ in range(2):
                with self.assertRaises(voice.VoiceError):
                    voice.synthesize_lines([{'id':'one','text':'Привет.'}], Path(tmp),
                        voice_id='voice_private123', generate=generate, allow_fallback=False)
            self.assertEqual(calls, [PRIMARY])
            self.assertEqual(len(list(Path(tmp).glob('*.attempt.json'))), 1)

    def test_explicit_flash_lite_uses_same_voice_without_primary_request(self):
        calls=[]
        def generate(text, voice_id, model):
            calls.append((voice_id,model))
            return fake_wav()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY':'offline'}):
            voice.synthesize_lines([{'id':'one','text':'Привет.'}],Path(tmp),voice_id='voice_private123',
                                   generate=generate,selected_model=FALLBACK)
        self.assertEqual(calls,[('voice_private123',FALLBACK)])

    def test_unapproved_model_is_blocked_before_request(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(voice.VoiceError):
            voice.synthesize_lines([{'id':'one','text':'Привет.'}],Path(tmp),voice_id='voice_private123',
                                   selected_model='unapproved-model',generate=lambda *a: self.fail('No request'))

    def test_successful_response_saved_before_parser_failure_without_headers(self):
        import base64
        audio = {'type':'audio','data':base64.b64encode(fake_wav()).decode()}
        payload = {'id':'interaction_test', 'output_audio':audio,
                   'steps':[{'type':'model_output','content':[audio]}],
                   'headers':{'x-goog-api-key':'NEVER_SAVE'}}
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n): return json.dumps(payload).encode()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY':'offline'}):
            target = Path(tmp)/'response.json'
            with patch('urllib.request.urlopen',return_value=Response()):
                with self.assertRaises(voice.VoiceError):
                    voice._generate_once('Привет.','voice_private123',PRIMARY,response_path=target)
            self.assertIn('output_audio',json.loads(target.read_text()))
            self.assertNotIn('NEVER_SAVE',target.read_text())

    def test_recorded_primary_outage_resumes_with_fallback_only(self):
        calls=[]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY':'offline'}):
            cache=Path(tmp)
            _,journal=voice._cache_paths(cache,PRIMARY,'voice_private123','Привет.')
            journal.write_text(json.dumps({'state':'provider_unavailable','model':PRIMARY}))
            def generate(text,voice_id,model):
                calls.append(model)
                return fake_wav()
            voice.synthesize_lines([{'id':'one','text':'Привет.'}],cache,voice_id='voice_private123',generate=generate)
            self.assertEqual(calls,[FALLBACK])

    def test_network_and_timeout_errors_allow_fallback(self):
        for error in (TimeoutError(),urllib.error.URLError('private network details'),ConnectionResetError()):
            with self.subTest(error=type(error).__name__),patch.dict(os.environ,{'GEMINI_API_KEY':'offline'}):
                with patch('urllib.request.urlopen',side_effect=error):
                    with self.assertRaises(voice.ProviderUnavailable) as raised:
                        voice._generate_once('Привет.','voice_private123',PRIMARY)
                self.assertTrue(raised.exception.may_have_been_billed)
                self.assertNotIn('private network details',str(raised.exception))

    def test_outage_switches_remaining_lines_and_reuses_fallback_cache(self):
        calls = []
        lines = [{'id': 'one', 'text': 'Здравствуйте.'}, {'id': 'two', 'text': 'Поехали.'}]
        def generate(text, voice_id, model):
            calls.append((text, voice_id, model))
            if model == PRIMARY:
                raise voice.ProviderUnavailable('http_429', may_have_been_billed=False)
            return fake_wav()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY': 'offline'}):
            result = voice.synthesize_lines(lines, Path(tmp), voice_id='voice_private123', generate=generate)
            cached = voice.synthesize_lines(lines, Path(tmp), voice_id='voice_private123', generate=generate)
            self.assertEqual(result, cached)
            self.assertEqual([c[2] for c in calls], [PRIMARY, FALLBACK, FALLBACK])
            self.assertEqual({c[1] for c in calls}, {'voice_private123'})
            journals = [json.loads(p.read_text()) for p in Path(tmp).glob('*.attempt.json')]
            self.assertEqual(len(journals), 3)
            failure = next(j for j in journals if j['model'] == PRIMARY)
            self.assertEqual(failure['state'], 'provider_unavailable')
            self.assertFalse(failure['may_have_been_billed'])

    def test_fallback_failure_is_never_repeated(self):
        calls = []
        def generate(text, voice_id, model):
            calls.append(model)
            raise voice.ProviderUnavailable('timeout', may_have_been_billed=True)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY': 'offline'}):
            for _ in range(2):
                with self.assertRaises(voice.VoiceError):
                    voice.synthesize_lines([{'id':'one', 'text':'Здравствуйте.'}], Path(tmp),
                                           voice_id='voice_private123', generate=generate)
            self.assertEqual(calls, [PRIMARY, FALLBACK])
            self.assertEqual(len(list(Path(tmp).glob('*.attempt.json'))), 2)

    def test_transport_failures_are_classified_without_leaking_server_text(self):
        for code in (429, 500, 502, 503, 504):
            with self.subTest(code=code), patch.dict(os.environ, {'GEMINI_API_KEY':'offline'}):
                error = urllib.error.HTTPError('https://example.invalid', code, 'private server text', {}, None)
                with patch('urllib.request.urlopen', side_effect=error):
                    with self.assertRaises(voice.ProviderUnavailable) as raised:
                        voice._generate_once('Привет.', 'voice_private123', PRIMARY)
                self.assertNotIn('private server text', str(raised.exception))
                self.assertEqual(raised.exception.may_have_been_billed, code != 429)

    def test_timeout_allows_one_fallback_with_billing_uncertainty_recorded(self):
        calls=[]
        def generate(text, voice_id, model):
            calls.append(model)
            if model == PRIMARY:
                raise voice.ProviderUnavailable('timeout', may_have_been_billed=True)
            return fake_wav()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY':'offline'}):
            voice.synthesize_lines([{'id':'one','text':'Привет.'}], Path(tmp), voice_id='voice_private123',generate=generate)
            journals=[json.loads(p.read_text()) for p in Path(tmp).glob('*.attempt.json')]
            primary=next(j for j in journals if j['model']==PRIMARY)
            self.assertTrue(primary['may_have_been_billed'])
            self.assertEqual(calls,[PRIMARY,FALLBACK])

    def test_credentials_and_invalid_requests_do_not_switch_model(self):
        for code in (400,401,403):
            with self.subTest(code=code), patch.dict(os.environ, {'GEMINI_API_KEY':'offline'}):
                error=urllib.error.HTTPError('https://example.invalid',code,'private',{},None)
                with patch('urllib.request.urlopen',side_effect=error):
                    with self.assertRaises(voice.VoiceError) as raised:
                        voice._generate_once('Привет.','voice_private123',PRIMARY)
                self.assertNotIsInstance(raised.exception,voice.ProviderUnavailable)


if __name__ == '__main__':
    unittest.main()

