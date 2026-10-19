import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import zernio


PAGE = "Leo's Travel Tips"


class FakeCLI:
    def __init__(self):
        self.calls = []
        self.posts = []
        self.fail_create = False

    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == 'accounts:list':
            return {'accounts': [{'_id': 'account1', 'displayName': PAGE,
                                  'platform': 'facebook', 'isActive': True}]}
        if args[0] == 'posts:list':
            return {'posts': copy.deepcopy(self.posts), 'pagination': {'pages': 1}}
        if args[0] == 'media:upload':
            return {'url': 'https://media.example/final.png'}
        if args[0] == 'posts:create':
            post = {'_id': 'draft1', 'status': 'draft',
                    'content': next(a[len('--text='):] for a in args if a.startswith('--text=')),
                    'platforms': [{'platform': 'facebook', 'accountId': 'account1'}],
                    'mediaItems': [{'type': 'image', 'url': 'https://media.example/final.png'}],
                    'metadata': json.loads(args[args.index('--metadata') + 1])}
            self.posts.append(post)
            if self.fail_create:
                raise zernio.Blocked('CLI_FAILED_OUTCOME_UNKNOWN')
            return {'post': post}
        if args[0] == 'posts:get':
            return {'post': copy.deepcopy(self.posts[0])}
        raise AssertionError(args)


class DraftTests(unittest.TestCase):
    def setUp(self):
        test_root = zernio.STATE / 'tests'
        test_root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=test_root)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / 'final.png'
        self.image.write_bytes(b'approved fixture')
        self.package = {'packageId': 'approved-test', 'content': 'Точный текст\n«Кавычки» $ `',
                        'textStatus': 'APPROVED_TEXT', 'visualStatus': 'FINAL_VISUAL_READY',
                        'status': 'PUBLICATION_PACKAGE_READY', 'image': str(self.image)}
        self.cli = FakeCLI()

    def run_draft(self, send=True, page=PAGE):
        return zernio.draft(self.package, page, send, self.root / 'state', self.cli)

    def test_missing_page_and_unapproved_inputs_do_not_call_cli(self):
        with self.assertRaisesRegex(zernio.Blocked, 'PAGE_REQUIRED'):
            self.run_draft(page=None)
        for field in ('textStatus', 'visualStatus', 'status'):
            changed = self.package.copy()
            changed[field] = 'NOT_READY'
            with self.assertRaises(zernio.Blocked):
                zernio.draft(changed, PAGE, True, self.root / 'state', self.cli)
        self.assertEqual(self.cli.calls, [])

    def test_dry_run_never_uploads_or_creates(self):
        self.assertEqual(self.run_draft(False)['status'], 'DRY_RUN')
        self.assertEqual(self.cli.calls, [])

    def test_create_readback_and_repeat_create_once(self):
        first = self.run_draft()
        second = self.run_draft()
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['content'], self.package['content'])
        creates = [a for a in self.cli.calls if a[0] == 'posts:create']
        self.assertEqual(len(creates), 1)
        self.assertIn('--draft', creates[0])
        self.assertFalse(any(a[0] == 'posts:update' for a in self.cli.calls))

    def test_lost_create_response_recovers_from_remote_metadata(self):
        self.cli.fail_create = True
        with self.assertRaises(zernio.Blocked):
            self.run_draft()
        self.assertEqual(self.run_draft()['id'], 'draft1')
        self.assertEqual(sum(a[0] == 'posts:create' for a in self.cli.calls), 1)

    def test_unknown_outcome_without_remote_match_blocks_retry(self):
        self.cli.fail_create = True
        with self.assertRaises(zernio.Blocked):
            self.run_draft()
        self.cli.posts.clear()
        with self.assertRaisesRegex(zernio.Blocked, 'OUTCOME_UNKNOWN'):
            self.run_draft()
        self.assertEqual(sum(a[0] == 'posts:create' for a in self.cli.calls), 1)

    def test_changed_package_requires_new_id(self):
        self.run_draft()
        self.package['content'] += '!'
        with self.assertRaisesRegex(zernio.Blocked, 'PACKAGE_CHANGED'):
            self.run_draft()

    def test_remote_change_fails_readback_without_new_post(self):
        self.run_draft()
        self.cli.posts[0]['content'] = 'changed remotely'
        with self.assertRaisesRegex(zernio.Blocked, 'READBACK_MISMATCH'):
            self.run_draft()

    def test_existing_published_post_never_recreated(self):
        self.run_draft()
        self.cli.posts[0]['status'] = 'published'
        with self.assertRaisesRegex(zernio.Blocked, 'NOT_DRAFT'):
            self.run_draft()
        self.assertEqual(sum(a[0] == 'posts:create' for a in self.cli.calls), 1)

    def test_extra_publish_fields_rejected(self):
        self.package['publishNow'] = True
        with self.assertRaises(zernio.Blocked):
            self.run_draft()
        self.assertEqual(self.cli.calls, [])

    def test_same_content_with_another_package_id_reuses_remote(self):
        self.run_draft()
        self.package['packageId'] = 'another-id'
        self.assertEqual(self.run_draft()['id'], 'draft1')
        self.assertEqual(sum(a[0] == 'posts:create' for a in self.cli.calls), 1)

    def test_ambiguous_account_blocks_before_mutation(self):
        def run(*args):
            response = self.cli(*args)
            if args[0] == 'accounts:list':
                response['accounts'] *= 2
            return response
        with self.assertRaisesRegex(zernio.Blocked, 'PAGE_NOT_UNIQUE'):
            zernio.draft(self.package, PAGE, True, self.root / 'state', run)
        self.assertEqual(len(self.cli.calls), 1)

    def test_parallel_local_run_is_blocked(self):
        _, key, _ = zernio.validate(self.package, PAGE)
        state = self.root / 'state'
        state.mkdir()
        with zernio.lock(state / (key + '.lock')):
            with self.assertRaisesRegex(zernio.Blocked, 'LOCKED'):
                self.run_draft()

    def test_known_upload_rejection_allows_corrected_rerun(self):
        def run(*args):
            if args[0] == 'media:upload':
                raise zernio.RejectedNoWrite('ZERNIO_REJECTED_HTTP_401')
            return self.cli(*args)
        with self.assertRaises(zernio.RejectedNoWrite):
            zernio.draft(self.package, PAGE, True, self.root / 'state', run)
        self.assertEqual(self.run_draft()['id'], 'draft1')

    def test_known_create_rejection_allows_corrected_rerun(self):
        def run(*args):
            if args[0] == 'posts:create':
                raise zernio.RejectedNoWrite('ZERNIO_REJECTED_HTTP_422')
            return self.cli(*args)
        with self.assertRaises(zernio.RejectedNoWrite):
            zernio.draft(self.package, PAGE, True, self.root / 'state', run)
        self.assertEqual(self.run_draft()['id'], 'draft1')

    def test_cli_error_redacts_message_but_keeps_safe_status(self):
        with patch.object(zernio, 'cli_command', return_value=['node', 'cli.js']), patch.object(
                zernio.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=1, stdout='', stderr='{"status":401,"message":"private value"}')):
            with self.assertRaises(zernio.RejectedNoWrite) as caught:
                zernio.cli('media:upload', 'image.png')
        self.assertIn('401', str(caught.exception))
        self.assertNotIn('private value', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
