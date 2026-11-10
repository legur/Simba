"""Stage-5 real task routing: offline tests, no GitHub writes or paid services."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog
import handoff
import dispatcher


class FakeClient:
    def __init__(self, markers=()):
        self.markers = set(markers)
        self.issued = []

    def existing_markers(self):
        return self.markers

    def create(self, item):
        self.issued.append(item)
        return 100 + len(self.issued)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source.md'
        self.source.write_text('# approved story (no secret)\n', encoding='utf-8')
        self.project = {
            'schema_version': 1, 'id': 'project-a', 'title': 'Project A',
            'aliases': ['A'], 'updated_at': '2026-11-10',
            'stage': 'SCRIPT_OPTIONS_PENDING', 'next_action': 'Prepare script',
            'sources': [{'path': 'source.md', 'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()}],
            'assets': [], 'references': [], 'working_asset_id': None,
            'approved_asset_id': None,
            'approvals': {'editorial': 'pending', 'publication': 'pending'},
            'stage_handoffs': {},
        }
        self.path = self.root / 'campaigns/project-a/project.json'
        self.path.parent.mkdir(parents=True)
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.project, ensure_ascii=False), encoding='utf-8')

    def test_new_project_without_fake_assets_creates_first_stage_task(self):
        # New projects genuinely have zero materials before the first script.
        self.assertEqual(catalog.project_issues(self.root, self.path, self.project), [])
        plans, skipped = dispatcher.plans_for_paths(self.root, ['campaigns/project-a/project.json'])
        self.assertEqual(skipped, [])
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['stage'], 'script')
        self.assertEqual(plans[0]['recipient'], 'SCENARIST')
        self.assertEqual(plans[0]['state'], 'TASK_READY_NOT_EXECUTED')
        self.assertNotIn('source.md', plans[0]['body'])

    def test_after_real_user_selection_next_task_is_rafael_storyboard(self):
        self.project['assets'].append({
            'id': 'script-chosen', 'kind': 'script', 'state': 'available',
            'title': 'approved 2/3 scripts', 'url': 'https://github.com/legur/Simba',
            'evidence': 'Three actual complete scripts and Leo selected 2',
            'reuse': True,
        })
        self.project['stage_handoffs']['script'] = {
            'state': 'approved', 'input_fingerprint': handoff.source_fingerprint(self.project),
            'assets': ['script-chosen'], 'approval_evidence': 'Leo: 2',
            'options_presented': 3, 'options_evidence': 'full set shown',
            'selected_option': 2,
        }
        self.save()
        hand = handoff.make_handoff(self.root, self.path, self.project)
        self.assertEqual(hand['state'], 'READY_FOR_HANDOFF')
        plans, skipped = dispatcher.plans_for_paths(self.root, ['campaigns/project-a/project.json'])
        self.assertFalse(skipped)
        self.assertEqual(plans[0]['stage'], 'storyboard')
        self.assertEqual(plans[0]['recipient'], 'RAFAEL')

    def test_wrong_role_and_unapproved_states_never_queue(self):
        digest = 'f' * 64
        cases = [
            {'state': 'BLOCKED', 'recipient': 'PROCESS_OWNER', 'reason': 'STALE_SOURCE'},
            {'state': 'APPROVED_UNPUBLISHED', 'recipient': 'LEO', 'packet': {'next_stage': 'publication_decision'}},
            {'state': 'PUBLICATION_REPORTED_COMPLETE', 'recipient': 'PROCESS_OWNER'},
            {'state': 'SOMETHING_ELSE', 'recipient': 'RAFAEL'},
        ]
        for hand in cases:
            with self.subTest(hand=hand):
                self.assertIsNone(dispatcher.action_for(self.project, hand))
        with self.assertRaises(dispatcher.DispatchError):
            dispatcher.action_for(self.project, {
                'state': 'READY_FOR_HANDOFF', 'recipient': 'SCENARIST',
                'packet': {'next_stage': 'storyboard', 'receipt_sha256': digest}})
        with self.assertRaises(dispatcher.DispatchError):
            dispatcher.action_for(self.project, {
                'state': 'READY_FOR_HANDOFF', 'recipient': 'RAFAEL',
                'packet': {'next_stage': 'storyboard', 'receipt_sha256': 'wrong'}})

    def test_legacy_without_stage_handoffs_never_fakes_first_stage(self):
        self.project.pop('stage_handoffs')
        self.project['assets'] = [{
            'id': 'x', 'kind': 'review_video', 'title': 'old cut',
            'url': 'https://github.com/legur/Simba', 'state': 'available', 'evidence': 'old'}]
        self.save()
        plans, skipped = dispatcher.plans_for_paths(self.root, ['campaigns/project-a/project.json'])
        self.assertFalse(plans)
        self.assertEqual(skipped[0]['status'], 'BLOCKED')

    def test_fail_closed_on_source_stale_and_path_mismatch(self):
        self.source.write_text('# new source not approved\n')
        plans, skipped = dispatcher.plans_for_paths(self.root, ['campaigns/project-a/project.json'])
        self.assertEqual(plans, [])
        self.assertEqual(skipped[0]['status'], 'BLOCKED')
        self.project['id'] = 'different'
        self.save()
        with self.assertRaises(dispatcher.DispatchError):
            dispatcher.plans_for_paths(self.root, ['campaigns/project-a/project.json'])

    def test_stable_marker_and_no_private_details_in_public_issue(self):
        hand = {'state': 'READY_FOR_HANDOFF', 'recipient': 'A2E_RUNNER',
                'packet': {'next_stage': 'a2e_clips', 'receipt_sha256': 'f' * 64,
                           'assets': [{'url': 'https://drive.google.com/private',
                                       'secret': 'DO_NOT_LOG'}]}}
        self.project['secret_voice_id'] = 'VOICE_DO_NOT_LOG'
        first = dispatcher.action_for(self.project, hand)
        self.assertEqual(first, dispatcher.action_for(self.project, hand))
        self.assertNotIn('DO_NOT_LOG', first['body'])
        self.assertNotIn('drive.google.com', first['body'])
        self.assertNotIn('f' * 64, first['body'])
        self.assertIn('Никаких платных A2E/TTS-вызовов', first['body'])

    def test_idempotent_issue_dispatch_even_for_closed_task(self):
        hand = {'state': 'NEEDS_FIRST_STAGE', 'recipient': 'SCENARIST',
                'expected_input_fingerprint': 'a' * 64}
        plan = dispatcher.action_for(self.project, hand)
        client = FakeClient()
        first = dispatcher.dispatch([plan, plan], client)
        self.assertEqual(len(client.issued), 1)
        self.assertEqual(first[0]['status'], 'TASK_ISSUE_CREATED_NOT_EXECUTED')
        self.assertEqual(first[1]['status'], 'ALREADY_QUEUED')
        second = dispatcher.dispatch([plan], FakeClient([plan['marker']]))
        self.assertEqual(second[0]['status'], 'ALREADY_QUEUED')

    def test_paginated_existing_issue_scan_handles_a2e_digits_and_closed(self):
        plan = dispatcher.action_for(self.project, {
            'state': 'READY_FOR_HANDOFF', 'recipient': 'A2E_RUNNER',
            'packet': {'next_stage': 'a2e_clips', 'receipt_sha256': 'b'*64}})
        cl = object.__new__(dispatcher.GitHubIssueClient)
        calls = []
        def fake(method, path, payload=None):
            calls.append(path)
            if path.endswith('page=1'):
                return [{'number': i, 'body': None} for i in range(100)]
            return [{'number': 150, 'state': 'closed', 'body': plan['body']}]
        cl.request = fake
        markers = cl.existing_markers()
        self.assertIn(plan['marker'], markers)
        self.assertEqual(len(calls), 2)

    def test_private_url_does_not_escape_via_git_project_path(self):
        # No user-controlled filename can escape project dir or redirect a task.
        self.assertIsNone(dispatcher.PROJECT_PATH.fullmatch('campaigns/../evil/project.json'))
        self.assertIsNone(dispatcher.PROJECT_PATH.fullmatch('campaigns/project-a/data.json'))
        self.assertIsNone(dispatcher.PROJECT_PATH.fullmatch('campaigns/project-a/project.json/private'))

    def test_github_write_requires_trusted_main_push(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'other/other',
                                     'GITHUB_TOKEN': 'test-token',
                                     'GITHUB_EVENT_NAME': 'pull_request',
                                     'GITHUB_REF': 'refs/heads/feature'}, clear=True):
            code = dispatcher.main(['--root', str(self.root), '--before', 'a'*40,
                                    '--after', 'b'*40, '--execute'])
            self.assertEqual(code, 2)
        self.assertEqual(dispatcher.main(['--root', str(self.root), '--all', '--execute']), 2)

    def test_git_diff_selects_only_changed_project_json(self):
        root = self.root
        def run(*args):
            return subprocess.check_output(['git', *args], cwd=root).decode('utf-8').strip()
        run('init', '-q')
        run('config', 'user.email', 'test@example.com')
        run('config', 'user.name', 'Simba CI')
        run('add', '.')
        run('commit', '-qm', 'base')
        before = run('rev-parse', 'HEAD')
        self.project['stage'] = 'PENDING'
        self.save()
        (root/'README.md').write_text('changed', encoding='utf-8')
        run('add', '.')
        run('commit', '-qm', 'change')
        after = run('rev-parse', 'HEAD')
        paths = dispatcher.changed_projects(root, before, after)
        self.assertEqual(paths, ['campaigns/project-a/project.json'])
        self.assertEqual(dispatcher.changed_projects(root, '0'*40, after), [])
        with self.assertRaises(dispatcher.DispatchError):
            dispatcher.changed_projects(root, 'wrong', after)


if __name__ == '__main__':
    unittest.main()