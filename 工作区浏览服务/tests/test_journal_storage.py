"""Exact preparation recovery with compact journals; no real projects or network."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.services import prepared_documents as documents


class JournalStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / '装配结果.json'

    def journal(self):
        workflow = {'1': {'class_type': 'Example', 'inputs': {'seed': 9223372036854775807,
                    'prompt': '保持已批准人物与镜头。' * 100}}}
        before = ''.join(f'已确认记录{i}：原文。\n' for i in range(200))
        after = before.replace('记录17：原文。', '记录17：修订。') + '本次明确批准。\n'
        return {'journal_encoding': 'shared-writes-v1', 'tasks': [{'workflow': workflow}],
                'source': {'authorization': '仅模拟准备'}, 'writes': [
                {'path': '执行附件/任务.api.json', 'old': None,
                 'new': json.dumps(workflow, ensure_ascii=False, indent=2)},
                {'path': '工作稿.md', 'old': before, 'new': after, 'original': before}]}

    def test_round_trip_preserves_full_inputs_exact_edits_and_big_integer(self):
        value = self.journal()
        original = json.dumps(value, ensure_ascii=False, indent=2)
        documents.write_journal(self.path, value)
        self.assertEqual(documents.read_journal(self.path), value)
        self.assertEqual(json.dumps(value, ensure_ascii=False, indent=2), original)
        stored = json.loads(self.path.read_text())
        self.assertEqual(stored['writes'][0]['new_from_workflow'], 0)
        self.assertIn('new_delta', stored['writes'][1])
        self.assertIn('original_delta', stored['writes'][1])
        self.assertLess(self.path.stat().st_size, len(original.encode()))

    def test_identical_workflows_share_storage_but_keep_independent_task_inputs(self):
        from copy import deepcopy
        value = self.journal()
        value['tasks'].append(deepcopy(value['tasks'][0]))
        documents.write_journal(self.path, value)
        stored = json.loads(self.path.read_text())
        self.assertEqual(stored['tasks'][1]['workflow_from_task'], 0)
        self.assertNotIn('workflow', stored['tasks'][1])
        restored = documents.read_journal(self.path)
        self.assertEqual(restored, value)
        restored['tasks'][0]['workflow']['1']['inputs']['prompt'] = '另一任务的绑定变化'
        self.assertEqual(restored['tasks'][1]['workflow'], value['tasks'][1]['workflow'])

    def test_recovered_writes_preserve_concurrent_user_edits(self):
        value = self.journal()
        value['writes'] = value['writes'][1:]
        draft = self.root / '工作稿.md'
        draft.write_text(value['writes'][0]['old'])
        documents.write_journal(self.path, value)
        recovered = documents.read_journal(self.path)
        documents.publish(self.root, recovered['writes'])
        self.assertEqual(draft.read_text(), value['writes'][0]['new'])
        rebuilt = documents.Documents(self.root, recovered['writes'])
        self.assertEqual(rebuilt.read('工作稿.md'), value['writes'][0]['original'])
        draft.write_text('用户另写的反馈。')
        with self.assertRaisesRegex(ValueError, '资料已变化'):
            documents.publish(self.root, recovered['writes'])
        self.assertEqual(draft.read_text(), '用户另写的反馈。')

    def test_empty_unicode_and_mixed_line_endings_remain_exact(self):
        for before, after in [('', '新\n'), ('旧\r\n第二行\n', '旧\r\n插入\r\n第二行\n'),
                              ('没有换行', ''), ('前\n中\n后', '先\n前\n改\n后\n末\n'),
                              ('甲\n乙\n丙\n', '甲\n丙\n'), ('同\n' * 200, '同\n' * 200)]:
            with self.subTest(before=before[:15], after=after[:15]):
                value = self.journal()
                value['writes'] = [{'path': '正文.md', 'old': before, 'new': after}]
                documents.write_journal(self.path, value)
                self.assertEqual(documents.read_journal(self.path), value)

    def test_legacy_journal_stays_full_and_read_does_not_rewrite(self):
        value = self.journal()
        value.pop('journal_encoding')
        documents.write_journal(self.path, value)
        original = self.path.read_bytes()
        self.assertEqual(json.loads(original), value)
        self.assertEqual(documents.read_journal(self.path), value)
        self.assertEqual(self.path.read_bytes(), original)

    def test_interrupted_write_removes_only_its_temporary_file(self):
        self.path.write_text('{"previous":"valid"}')
        def disk_full(value, stream, **options):
            stream.write('{\"partial\":')
            raise OSError('isolated disk full')
        with patch.object(documents.json, 'dump', side_effect=disk_full):
            with self.assertRaises(OSError):
                documents.write_json(self.path, {'valid': 'record'})
        self.assertEqual(self.path.read_text(), '{"previous":"valid"}')
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_failed_publish_leaves_valid_previous_journal_and_no_temporary(self):
        self.path.write_text('{"previous":"valid"}')
        with patch.object(Path, 'replace', side_effect=OSError('isolated disk failure')):
            with self.assertRaises(OSError):
                documents.write_journal(self.path, self.journal())
        self.assertEqual(self.path.read_text(), '{"previous":"valid"}')
        self.assertEqual(list(self.root.iterdir()), [self.path])
