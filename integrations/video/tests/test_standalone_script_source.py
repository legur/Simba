"""Offline regression tests for owner-verified standalone approval (no provider calls)."""
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))
import make_video


SCRIPT = """STATUS: APPROVED_SCRIPT
APPROVAL_EVIDENCE: github-issue-comment:12345
SOURCE_REFERENCE: checked-brief-2026-11-17

## APPROVED_SCRIPT
Приезжаем во Вьетнам на 10 дней.
"""


def comment_for(script=SCRIPT, author='legur', source='checked-brief-2026-11-17'):
    body = re.search(r'^## APPROVED_SCRIPT\s*$(.*?)(?=^## |\Z)', script, re.M | re.S).group(1)
    return {
        'user': {'login': author},
        'html_url': 'https://github.com/legur/Simba/issues/314#issuecomment-12345',
        'body': ('SIMBA_SCRIPT_APPROVAL_V1\n'
                 'SCRIPT_SHA256: ' + hashlib.sha256(body.encode('utf-8')).hexdigest() + '\n'
                 'SOURCE_REFERENCE_SHA256: ' + hashlib.sha256(source.encode('utf-8')).hexdigest()),
    }


class StandaloneScriptSourceTests(unittest.TestCase):
    def test_owner_approved_exact_script_and_provenance(self):
        body, approved = make_video.parse_approved_script(
            SCRIPT, fetch_comment=lambda _: comment_for())
        self.assertTrue(approved)
        self.assertIn('10 дней', body)

    def test_unverified_fields_never_create_approval(self):
        for key, replacement in (
            ('STATUS: APPROVED_SCRIPT', 'STATUS: WORKING'),
            ('APPROVAL_EVIDENCE: github-issue-comment:12345', 'APPROVAL_EVIDENCE: Leo approved it'),
            ('SOURCE_REFERENCE: checked-brief-2026-11-17', 'SOURCE_REFERENCE:'),
        ):
            edited = SCRIPT.replace(key, replacement)
            _, approved = make_video.parse_approved_script(
                edited, fetch_comment=lambda _: comment_for())
            self.assertFalse(approved, key)

    def test_source_body_or_provenance_changed_after_owner_approval(self):
        original_record = comment_for()
        for edited in (
            SCRIPT.replace('10 дней', '14 дней'),
            SCRIPT.replace('checked-brief-2026-11-17', 'different-brief-2026-11-17'),
        ):
            _, approved = make_video.parse_approved_script(
                edited, fetch_comment=lambda _: original_record)
            self.assertFalse(approved)

    def test_wrong_actor_or_github_repo_does_not_approve(self):
        for record in (
            comment_for(author='github-actions[bot]'),
            {**comment_for(), 'html_url': 'https://github.com/another/repo/issues/1'},
        ):
            _, approved = make_video.parse_approved_script(
                SCRIPT, fetch_comment=lambda _, record=record: record)
            self.assertFalse(approved)

    def test_missing_comment_or_forged_private_link_fails_closed(self):
        _, approved = make_video.parse_approved_script(
            SCRIPT, fetch_comment=lambda _: {})
        self.assertFalse(approved)
        _, approved = make_video.parse_approved_script(
            SCRIPT.replace('checked-brief-2026-11-17', 'https://drive.google.com/file/d/secret'),
            fetch_comment=lambda _: comment_for())
        self.assertFalse(approved)

    def test_unavailable_github_evidence_is_a_blocker(self):
        with patch.object(make_video, 'fetch_script_approval_comment',
                          side_effect=OSError('offline')):
            with self.assertRaisesRegex(make_video.Stop, 'APPROVAL_EVIDENCE_UNAVAILABLE'):
                make_video.parse_approved_script(SCRIPT)

    def test_renderer_accepts_owner_verified_script_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'script.md').write_text(SCRIPT, encoding='utf-8')
            with patch.object(make_video, 'REPO', root), patch.object(
                make_video, 'fetch_script_approval_comment',
                return_value=comment_for()):
                body, approved = make_video.approved_text({'sourceScript': 'script.md'})
            self.assertTrue(approved)
            self.assertEqual(make_video.fact_gate(
                {'scenes': [{'lines': [{'text': '10 дней'}]}],
                 'end': {'brand': 'Simba by Bon Tours'}}, body), 'PASS')

    def test_unverified_script_rejected_except_nonpublishable_draft(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'script.md').write_text(SCRIPT, encoding='utf-8')
            with patch.object(make_video, 'REPO', root), patch.object(
                make_video, 'fetch_script_approval_comment',
                return_value=comment_for(author='other')):
                with self.assertRaises(make_video.Stop):
                    make_video.approved_text({'sourceScript': 'script.md'})
                _, approved = make_video.approved_text({'sourceScript': 'script.md'}, draft=True)
                self.assertFalse(approved)

    def test_source_fields_mutually_exclusive_and_paths_sandboxed(self):
        with tempfile.TemporaryDirectory() as folder:
            job = Path(folder)
            (job / 'photo.jpg').write_bytes(b'fixture')
            base = {'packageId': 'standalone', 'scenes': [
                {'image': 'photo.jpg', 'lines': []}]}

            def load(extra):
                (job / 'video-spec.json').write_text(json.dumps(
                    {**base, **extra}), encoding='utf-8')
                with patch('music_input.validate_music', return_value=None):
                    return make_video.load_spec(job)

            self.assertEqual(load({'sourceScript': 'script.md'})['sourceScript'], 'script.md')
            self.assertEqual(load({'sourcePost': 'post.md'})['sourcePost'], 'post.md')
            with self.assertRaisesRegex(make_video.Stop, 'exactly one'):
                load({'sourcePost': 'post.md', 'sourceScript': 'script.md'})
            with self.assertRaisesRegex(make_video.Stop, 'exactly one'):
                load({})
            with self.assertRaisesRegex(make_video.Stop, 'inside the repository'):
                load({'sourceScript': '../script.md'})


if __name__ == '__main__':
    unittest.main()
