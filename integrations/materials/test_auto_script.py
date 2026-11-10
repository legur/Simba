"""Offline-only tests for no-cost local script drafting and private storage gates."""
from __future__ import annotations
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import auto_script
import handoff

SAMPLE = '''STATUS: APPROVED
# Рекламный источник
## APPROVED_TEXT
Новогодняя поездка в Баварию с 28.12 по 03.01. 6 ночей с завтраками. Мюнхен, Аугсбург, Регенсбург. Русскоязычный гид. Цена 1399 евро с человека. Телефон 0586778492. Напишите в WhatsApp «Бавария».\n\n## NOTES\nКонец.\n'''
SCRIPT_BASE = ('Представьте вечер в Баварии. Огни старинных площадей зовут в дорогу. '
               'Вас ждут Мюнхен, Аугсбург и Регенсбург. Прогуляемся по улицам, '
               'насладимся атмосферой путешествия, увидим архитектуру. '
               'В программе шесть ночей с завтраками и русскоязычный гид. '
               'Напишите в WhatsApp «Бавария», и я расскажу о поездке.')


class FakeDrive:
    pass


class ScriptRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/brief.md'
        self.source.parent.mkdir(parents=True)
        self.source.write_text(SAMPLE, encoding='utf-8')
        self.project = {
            'schema_version': 1, 'id': 'fresh-reel', 'title': 'Test reel',
            'aliases': ['Test'], 'updated_at': '2026-11-10',
            'stage': 'SCRIPT_OPTIONS_PENDING', 'next_action': 'Generate 3 options',
            'sources': [{'path': self.source.relative_to(self.root).as_posix(),
                         'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()}],
            'assets': [], 'references': [], 'working_asset_id': None,
            'approved_asset_id': None, 'approvals': {'editorial': 'pending', 'publication': 'pending'},
            'stage_handoffs': {},
        }
        self.path = self.root / 'campaigns/fresh-reel/project.json'
        self.path.parent.mkdir(parents=True)
        self.save()
        self.report = {'mode': 'ISSUE_DISPATCH', 'paid_jobs': 0,
                       'dispatch': [{'project_id': 'fresh-reel', 'stage': 'script',
                                     'status': 'TASK_ISSUE_CREATED_NOT_EXECUTED'}]}
        self.folder = '1GMoSVogs0SKuTAXCdMVcG-U7bTn-IuCt'

    def save(self):
        self.path.write_text(json.dumps(self.project, ensure_ascii=False), encoding='utf-8')

    def test_real_handoff_creates_one_script_plan(self):
        tasks = auto_script.read_created_script_tasks(self.root, self.report)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0][0]['id'], 'fresh-reel')
        self.assertEqual(tasks[0][1], handoff.source_fingerprint(self.project))
        source, rev, source_hash = auto_script.extract_approved_source(self.root, self.project)
        self.assertIn('Баварию', source)
        self.assertNotIn('NOTES', source)
        self.assertEqual(len(rev), 64)
        self.assertEqual(len(source_hash), 64)

    def test_no_fabricated_approval_or_automatic_publication(self):
        drafts = [SCRIPT_BASE+' История.', SCRIPT_BASE+' Интрига.', SCRIPT_BASE+' Трейлер.']
        for d in drafts:
            auto_script.draft_guard(SAMPLE, d)
        result = auto_script.render_markdown(self.project, 'a'*64, 'b'*64, drafts)
        self.assertIn('DRAFT_OPTIONS_NEED_LEO', result)
        self.assertIn('Вариант 3', result)
        self.assertNotIn('STATUS: APPROVED', result)
        self.assertEqual(self.project['approvals']['editorial'], 'pending')

    def test_reject_generated_numbers_and_links(self):
        auto_script.draft_guard(SAMPLE, SCRIPT_BASE)
        with self.assertRaises(auto_script.AgentError):
            auto_script.draft_guard(SAMPLE, SCRIPT_BASE + ' Стоимость 777777 евро.')
        with self.assertRaises(auto_script.AgentError):
            auto_script.draft_guard(SAMPLE, SCRIPT_BASE + ' https://untrusted.example')
        with self.assertRaises(auto_script.AgentError):
            auto_script.draft_guard(SAMPLE, 'No Russian, 1234567')

    def test_stale_or_unapproved_or_untrusted_source_rejected(self):
        self.source.write_text(SAMPLE.replace('STATUS: APPROVED', 'STATUS: DRAFT'))
        with self.assertRaises(auto_script.AgentError):
            auto_script.extract_approved_source(self.root, self.project)
        self.project['sources'][0]['sha256'] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaises(auto_script.AgentError):
            auto_script.extract_approved_source(self.root, self.project)
        self.project['sources'][0]['path'] = 'outside/other.md'
        with self.assertRaises(auto_script.AgentError):
            auto_script.extract_approved_source(self.root, self.project)

    def test_stage_permissions_fail_closed(self):
        self.project['approvals']['editorial'] = 'approved'
        self.save()
        with self.assertRaises(auto_script.AgentError):
            auto_script.read_created_script_tasks(self.root, self.report)
        self.project['approvals']['editorial'] = 'pending'
        self.project['stage_handoffs'] = None
        self.save()
        with self.assertRaises(auto_script.AgentError):
            auto_script.read_created_script_tasks(self.root, self.report)
        self.project['stage_handoffs'] = {}
        self.save()
        self.assertEqual(auto_script.read_created_script_tasks(self.root, {
            'mode': 'ISSUE_DISPATCH', 'paid_jobs': 0,
            'dispatch': [{'project_id': 'fresh-reel', 'stage': 'storyboard',
                          'status': 'TASK_ISSUE_CREATED_NOT_EXECUTED'}]}), [])
        with self.assertRaises(auto_script.AgentError):
            auto_script.read_created_script_tasks(self.root, {**self.report, 'paid_jobs': 1})

    def test_private_write_idempotent_no_reinference(self):
        calls = []
        def fake_model(messages):
            calls.append(messages)
            return SCRIPT_BASE + ' ' + ('История.' if len(calls)==1 else 'Интрига.' if len(calls)==2 else 'Трейлер.')
        uploaded = []
        with patch.object(auto_script, 'find_existing', return_value=None) as find, \
             patch.object(auto_script, 'upload_private', side_effect=lambda *a: uploaded.append(a) or 'PRIVATE_ARCHIVED_FOR_LEO_REVIEW'):
            result = auto_script.run(self.root, self.report, self.folder, infer=fake_model,
                                     drive_factory=FakeDrive)
        self.assertEqual(len(calls), 3)
        self.assertEqual(result[0]['status'], 'PRIVATE_ARCHIVED_FOR_LEO_REVIEW')
        self.assertEqual(result[0]['approved'], False)
        self.assertEqual(result[0]['publishing'], False)
        self.assertEqual(len(uploaded), 1)
        self.assertIn('Вариант 3', uploaded[0][3])
        with patch.object(auto_script, 'find_existing', return_value='existing_file'):
            result = auto_script.run(self.root, self.report, self.folder,
                                     infer=lambda *_: self.fail('Must not call model if already saved'),
                                     drive_factory=FakeDrive)
        self.assertEqual(result[0]['status'], 'ALREADY_PRIVATE_ARCHIVED')

    def test_untrusted_local_model_endpoint_forbidden(self):
        with self.assertRaises(auto_script.AgentError):
            auto_script.ollama_chat([], url='https://api.example.com/steal')
        with self.assertRaises(auto_script.AgentError):
            auto_script.private_name('bad/name', 'f'*64)
        with self.assertRaises(auto_script.AgentError):
            auto_script.render_markdown(self.project, 'f'*64, 'a'*64,
                                       [SCRIPT_BASE, SCRIPT_BASE, SCRIPT_BASE])

    def test_cli_dry_run_does_not_need_key_or_model(self):
        file = self.root / 'dispatch.json'
        file.write_text(json.dumps(self.report), encoding='utf-8')
        output = io.StringIO()
        with patch('sys.stdout', output), patch.dict(os.environ, {}, clear=True):
            rc = auto_script.main(['--root', str(self.root), '--dispatch-report', str(file),
                                   '--private-folder', self.folder])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(output.getvalue())['results'][0]['status'], 'LOCAL_AI_DRY_RUN_NO_MODEL')
        self.assertNotIn('Баварию', output.getvalue())
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(auto_script.main(['--root', str(self.root), '--dispatch-report', str(file),
                                               '--private-folder', self.folder, '--execute']), 2)


if __name__ == '__main__':
    unittest.main()