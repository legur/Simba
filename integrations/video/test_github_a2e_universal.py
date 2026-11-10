import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_a2e_universal as u

class UniversalTest(unittest.TestCase):
    def setUp(self):
        self.event = {'action': 'labeled', 'repository': {'full_name': 'legur/Simba'}, 'sender': {'login': 'legur'}, 'label': {'name': u.LABEL}, 'issue': {'number': 100, 'user': {'login': 'legur'}, 'body': json.dumps({'kind': 'simba_a2e_generate', 'max_credits': 60, 'scenes': [{'name': 'fjord', 'image_url': 'https://static.wixstatic.com/media/example.jpg', 'prompt': 'slow aerial motion'}]})}}

    def test_general_project_validates_and_enforces_model(self):
        number, cap, bodies = u.validate(self.event)
        self.assertEqual((number, cap), (100, 60))
        self.assertEqual(bodies[0]['model_version'], 'a2e')
        self.assertEqual(bodies[0]['negative_prompt'], 'blurry, distorted, static')

    def test_untrusted_actor_or_repository_blocked(self):
        for key, value in [('sender', {'login': 'other'}), ('repository', {'full_name': 'other/repo'})]:
            event = deepcopy(self.event)
            event[key] = value
            with self.assertRaises(ValueError): u.validate(event)

    def test_bad_cap_and_untrusted_image_blocked(self):
        for update in ({'max_credits': 0}, {'max_credits': True}, {'max_credits': 1001}, {'scenes': [{'name':'x','image_url':'https://example.com/x.jpg','prompt':'move'}]}):
            event = deepcopy(self.event)
            body = json.loads(event['issue']['body']); body.update(update)
            event['issue']['body'] = json.dumps(body)
            with self.assertRaises(ValueError): u.validate(event)

    def test_verified_lineage_is_preserved_without_any_a2e_start(self):
        event=deepcopy(self.event)
        body=json.loads(event['issue']['body'])
        body.update(project_id='synthetic-bridge',
                    handoff_sha256='a'*64,
                    selected_storyboard=2,selected_prompts=1)
        event['issue']['body']=json.dumps(body)
        number, ceiling, scenes=u.validate(event)
        self.assertEqual((number,ceiling),(100,60))
        with TemporaryDirectory() as tmp, patch.dict(u.os.environ, {'A2E_API_KEY':'sk_'+'x'*20}), patch.object(u,'price',return_value=[61]), patch.object(u.core,'a2e_start') as start:
            result=u.run(event,Path(tmp))
            self.assertEqual(result['status'],'STOPPED')
            self.assertEqual(result['lineage']['project_id'],'synthetic-bridge')
            self.assertEqual(result['lineage']['handoff_sha256'],'a'*64)
            self.assertFalse(result['lineage']['verified_at_source'])
            start.assert_not_called()

    def test_incomplete_lineage_is_rejected(self):
        event=deepcopy(self.event)
        body=json.loads(event['issue']['body'])
        body.update(project_id='../bad',handoff_sha256='z'*64,
                    selected_storyboard=True,selected_prompts=1)
        event['issue']['body']=json.dumps(body)
        with self.assertRaises(ValueError):
            u.validate(event)

    def test_cap_prevents_paid_start(self):
        with TemporaryDirectory() as tmp, patch.dict(u.os.environ, {'A2E_API_KEY': 'sk_' + 'x' * 20}), patch.object(u, 'price', return_value=[61]), patch.object(u.core, 'a2e_start') as start:
            result = u.run(self.event, Path(tmp))
            self.assertEqual(result['status'], 'STOPPED')
            start.assert_not_called()

    def test_existing_journal_prevents_paid_start(self):
        with TemporaryDirectory() as tmp, patch.dict(u.os.environ, {'A2E_API_KEY': 'sk_' + 'x' * 20}), patch.object(u, 'price', return_value=[30]), patch.object(u, 'no_existing_tasks'), patch.object(u.core, 'github_request', return_value=[{'body': u.MARKER}]), patch.object(u.core, 'a2e_start') as start:
            result = u.run(self.event, Path(tmp))
            self.assertEqual(result['status'], 'STOPPED')
            start.assert_not_called()

    def test_ambiguous_start_is_not_retried(self):
        with TemporaryDirectory() as tmp, patch.dict(u.os.environ, {'A2E_API_KEY': 'sk_' + 'x' * 20}), patch.object(u, 'price', return_value=[30]), patch.object(u, 'no_existing_tasks'), patch.object(u.core, 'github_request', side_effect=[[], {'id': 1}]), patch.object(u.core, 'a2e_start', side_effect=u.core.StopGeneration('ambiguous')) as start:
            result = u.run(self.event, Path(tmp))
            self.assertEqual(result['status'], 'STOPPED')
            self.assertEqual(start.call_count, 1)

if __name__ == '__main__': unittest.main()
