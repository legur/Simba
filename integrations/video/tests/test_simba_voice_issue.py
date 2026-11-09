import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simba_voice
import simba_voice_issue as issue_runner

class IssueVoiceTest(unittest.TestCase):
    def setUp(self):
        self.event = {'action':'labeled', 'repository':{'full_name':'legur/Simba'},
            'sender':{'login':'legur'}, 'label':{'name':'simba-approved-voice'},
            'issue':{'number':99,'user':{'login':'legur'}, 'body':json.dumps({
                'kind':'simba_approved_voice','text':'Тестовый текст.',
                'destination_folder_id':'folder_123456789'})}}
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        eventfile=Path(self.tmp.name)/'event.json'
        eventfile.write_text(json.dumps(self.event),encoding='utf-8')
        self.env={'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'issues',
            'GITHUB_EVENT_PATH':str(eventfile),'GITHUB_ACTOR':'legur',
            'GITHUB_TRIGGERING_ACTOR':'legur','GITHUB_REPOSITORY_OWNER':'legur',
            'GITHUB_REPOSITORY':'legur/Simba','GITHUB_REF':'refs/heads/main',
            'GITHUB_SHA':'a'*40,'GITHUB_WORKFLOW_SHA':'a'*40,
            'GITHUB_WORKFLOW':'Simba approved voice issue runner',
            'GITHUB_WORKFLOW_REF':'legur/Simba/.github/workflows/simba-approved-voice-issue.yml@refs/heads/main'}
    def test_valid(self):
        self.assertEqual(issue_runner.validate_event(self.event)[0],99)
        with patch.dict(os.environ,self.env,clear=True):
            simba_voice._require_github_secrets_workflow()
    def test_untrusted_label_and_sender(self):
        for key, value in [('sender',{'login':'attacker'}),('label',{'name':'other'})]:
            e=dict(self.event);e[key]=value
            with self.assertRaises(ValueError):issue_runner.validate_event(e)
            Path(self.env['GITHUB_EVENT_PATH']).write_text(json.dumps(e))
            with patch.dict(os.environ,self.env,clear=True):
                with self.assertRaises(simba_voice.VoiceError): simba_voice._require_github_secrets_workflow()
    def test_tampered_workflow_or_actor(self):
        for key in ('GITHUB_ACTOR','GITHUB_WORKFLOW_REF','GITHUB_SHA'):
            env=dict(self.env);env[key]='other'
            with patch.dict(os.environ,env,clear=True):
                with self.assertRaises(simba_voice.VoiceError): simba_voice._require_github_secrets_workflow()
    def test_replay_marker_stops_before_synthesis(self):
        with patch.object(issue_runner,'validate_event',return_value=(99,'hello','folder_123456789')), \
             patch.object(simba_voice,'_require_github_secrets_workflow'), \
             patch.object(issue_runner.store,'require_secret_environment'), \
             patch.object(issue_runner.store,'oauth_drive_client'), \
             patch.object(issue_runner.store,'validate_destination'), \
             patch.object(issue_runner.store,'_drive_matches',return_value=[]), \
             patch.object(issue_runner.store,'ensure_no_global_marker',side_effect=issue_runner.store.ReplayBlocked('marker')), \
             patch.object(simba_voice,'synthesize_lines') as call:
            with self.assertRaises(issue_runner.store.ReplayBlocked):issue_runner.run(self.event,Path(self.tmp.name))
            call.assert_not_called()

if __name__=='__main__':unittest.main()
