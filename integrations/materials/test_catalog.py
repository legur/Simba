import copy
import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

spec = importlib.util.spec_from_file_location('materials_catalog', Path(__file__).with_name('catalog.py'))
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.put('source.md', '# Project\n')
        self.record = {
            'schema_version': 1, 'id': 'project-a', 'title': 'Прага', 'aliases': ['Prague'],
            'stage': 'REVIEW', 'next_action': 'Проверить ролик', 'updated_at': '2026-11-08',
            'sources': [{'path': 'source.md', 'sha256': catalog.digest(self.root/'source.md')}],
            'assets': [{'id': 'clip', 'kind': 'animated_clip', 'title': 'Готовый клип',
                        'state': 'available', 'url': 'https://drive.google.com/file/d/example/view',
                        'reuse': True, 'evidence': 'Recorded in source'}],
            'references': [], 'working_asset_id': 'clip', 'approved_asset_id': None,
            'approvals': {'editorial': 'pending', 'publication': 'pending'},
        }
        self.manifest = self.root/'campaigns/project-a/project.json'
        self.save()

    def put(self, path, content):
        target = self.root/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')

    def save(self):
        self.put('campaigns/project-a/project.json', json.dumps(self.record, ensure_ascii=False))

    def check(self):
        return catalog.project_issues(self.root, self.manifest, self.record)

    def test_unchanged_source_is_current(self):
        self.assertEqual(self.check(), [])

    def test_source_change_invalidates_resume_snapshot(self):
        self.put('source.md', '# New decision\n')
        self.assertTrue(any('STALE_SOURCE' in x for x in self.check()))

    def test_missing_source_is_reported(self):
        (self.root/'source.md').unlink()
        self.assertTrue(any('MISSING_SOURCE' in x for x in self.check()))

    def test_alias_and_cyrillic_lookup(self):
        for query in ('prague', 'ПРАГА', 'project-a'):
            self.assertEqual(catalog.resolve_project(self.root, query)[1]['id'], 'project-a')

    def test_ambiguous_alias_does_not_choose_project(self):
        other = dict(self.record, id='project-b')
        self.put('campaigns/project-b/project.json', json.dumps(other))
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            catalog.resolve_project(self.root, 'Prague')

    def test_duplicate_project_ids_rejected(self):
        self.put('campaigns/project-b/project.json', json.dumps(self.record))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            catalog.load_projects(self.root)

    def test_asset_selection_is_not_approval(self):
        self.assertEqual(self.check(), [])
        self.record['approved_asset_id'] = 'clip'
        self.assertTrue(any('approval' in x for x in self.check()))

    def test_approval_without_evidence_rejected(self):
        self.record['approved_asset_id'] = 'clip'
        self.record['approvals']['editorial'] = 'approved'
        self.assertTrue(any('evidence' in x for x in self.check()))

    def test_missing_selected_asset_is_reported(self):
        self.record['working_asset_id'] = 'deleted'
        self.assertTrue(any('working_asset_id' in x for x in self.check()))

    def test_duplicate_asset_ids_rejected(self):
        self.record['assets'].append(copy.deepcopy(self.record['assets'][0]))
        self.assertTrue(any('Duplicate' in x for x in self.check()))

    def test_signed_urls_are_not_permanent_sources(self):
        self.record['assets'][0]['url'] = 'https://example.com/movie?X-Amz-Signature=temporary'
        self.assertTrue(any('Temporary' in x for x in self.check()))

    def test_repository_path_escape_rejected(self):
        self.record['sources'][0]['path'] = '../outside.md'
        with self.assertRaises(ValueError):
            self.check()

    def test_external_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root/'escape').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                catalog.inside(self.root, 'escape/file')

    def test_cyrillic_search_and_test_status_are_preserved(self):
        self.put('Кадр/База/cards/KADR-001.md', '# Заголовок\nSTATUS: TEST\nКрупные титры\n')
        result = catalog.search(self.root, 'КРУПНЫЕ ТИТРЫ', 'kadr', 10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'TEST')

    def test_prompt_body_cannot_override_header_status(self):
        self.put('Archivarius/cards/AR-1.md', '---\ntitle: Demo\nstatus: draft\n---\n## Промпт\nSTATUS: active\nпостер\n')
        result = catalog.search(self.root, 'постер', 'archivarius', 10)
        self.assertEqual(result[0]['status'], 'draft')

    def test_latest_tia_registry_marks_corrupt_source(self):
        self.put('Archivarius/TIA/TIA-023.txt', '# TIA-023\nПроверяемый текст\n')
        self.put('Archivarius/TIA/INDEX_v9.txt', '| TIA-023 | organic |\n')
        self.put('Archivarius/TIA/INDEX_v15.txt', '| TIA-023 | SOURCE_BLOCKED_CORRUPT |\n')
        result = catalog.search(self.root, 'Проверяемый', 'tia', 10)
        self.assertEqual(result[0]['status'], 'SOURCE_BLOCKED_CORRUPT')

    def test_quarantine_and_service_indexes_not_search_results(self):
        self.put('Archivarius/99_REVIEW/AR-1.md', '# quarantined needle\n')
        self.put('SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/_INDEX.md', '# service needle\n')
        self.assertEqual(catalog.search(self.root, 'needle', None, 10), [])

    def test_cli_resume_returns_failure_for_stale_source(self):
        self.put('source.md', 'Changed by another agent\n')
        with redirect_stdout(StringIO()) as captured:
            code = catalog.main(['--root', str(self.root), '--json', 'resume', 'Prague'])
        self.assertEqual(code, 2)
        self.assertIn('STALE_SOURCE', captured.getvalue())

    def test_cli_read_commands_do_not_modify_project(self):
        before = self.manifest.read_bytes()
        for command in (['list'], ['resume', 'Prague'], ['reuse', 'Prague'], ['check']):
            with redirect_stdout(StringIO()):
                self.assertEqual(catalog.main(['--root', str(self.root), *command]), 0)
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_reuse_can_select_existing_clips_only(self):
        self.record['assets'].append(dict(self.record['assets'][0], id='qa',kind='qa_report',reuse=False))
        self.save()
        with redirect_stdout(StringIO()) as captured:
            code = catalog.main(['--root', str(self.root), '--json', 'reuse', 'Prague', '--kind', 'animated_clip'])
        result = json.loads(captured.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual([a['id'] for a in result['assets']], ['clip'])


if __name__ == '__main__':
    unittest.main()
