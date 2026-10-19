"""Regression checks for the effective Facebook payload, with no remote writes."""
import copy
from pathlib import Path
import tempfile
import threading
import unittest

import zernio
from test_zernio import FakeCLI, PAGE


class EffectivePayloadTests(unittest.TestCase):
    def setUp(self):
        root = zernio.STATE / 'readback-tests'
        root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.image = self.root / 'final.png'
        self.image.write_bytes(b'approved image fixture')
        self.package = {
            'packageId': 'effective-payload-fixture', 'content': 'Утверждённый текст',
            'image': str(self.image), 'status': 'PUBLICATION_PACKAGE_READY',
            'textStatus': 'APPROVED_TEXT', 'visualStatus': 'FINAL_VISUAL_READY',
        }
        self.remote = FakeCLI()

    def draft(self, run=None):
        return zernio.draft(self.package, PAGE, True, self.root / 'state', run or self.remote)

    def test_changed_platform_text_media_or_time_is_not_verified(self):
        self.draft()
        original = copy.deepcopy(self.remote.posts[0])
        overrides = [
            ('customContent', 'Другой текст'),
            ('customMedia', [{'type': 'image', 'url': 'https://media.example/other.png'}]),
            ('scheduledFor', '2030-01-01T00:00:00Z'),
            ('platformSpecificData', {'facebookSettings': {'draft': True}}),
        ]
        for field, value in overrides:
            with self.subTest(field=field):
                self.remote.posts[0] = copy.deepcopy(original)
                self.remote.posts[0]['platforms'][0][field] = value
                with self.assertRaises(zernio.Blocked):
                    self.draft()
        self.assertEqual(sum(call[0] == 'posts:create' for call in self.remote.calls), 1)

    def test_image_change_during_handoff_prevents_post_creation(self):
        def mutate_after_validation(*args):
            if args[0] == 'accounts:list':
                self.image.write_bytes(b'unapproved replacement')
            return self.remote(*args)

        with self.assertRaises(zernio.Blocked):
            self.draft(mutate_after_validation)
        self.assertEqual(sum(call[0] == 'posts:create' for call in self.remote.calls), 0)

    def test_published_platform_under_draft_root_is_not_verified(self):
        self.draft()
        self.remote.posts[0]['platforms'][0]['status'] = 'published'
        with self.assertRaises(zernio.Blocked):
            self.draft()

    def test_distinct_package_ids_cannot_create_same_payload_concurrently(self):
        scanned = threading.Event()
        resume = threading.Event()
        failures = []

        def pause_first_scan(*args):
            response = self.remote(*args)
            if args[0] == 'posts:list' and not scanned.is_set():
                scanned.set()
                if not resume.wait(5):
                    raise AssertionError('Timed out waiting for concurrent attempt')
            return response

        def first_run():
            try:
                self.draft(pause_first_scan)
            except Exception as error:
                failures.append(error)

        first = threading.Thread(target=first_run)
        first.start()
        try:
            self.assertTrue(scanned.wait(5))
            other = dict(self.package, packageId='same-payload-another-id')
            try:
                zernio.draft(other, PAGE, True, self.root / 'state', self.remote)
            except zernio.Blocked:
                pass
        finally:
            resume.set()
            first.join(5)
        self.assertFalse(first.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(sum(call[0] == 'posts:create' for call in self.remote.calls), 1)


if __name__ == '__main__':
    unittest.main()
