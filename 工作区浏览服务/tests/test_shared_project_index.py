"""Shared registration, migration and state transitions in isolated roots."""
from pathlib import Path
import tempfile
from tests.http_case import HttpTestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import main
from backend.services.workspaces import Workspaces
from backend.services.project_files import ProjectFiles
from workspace_project_index import index_entries, register_project, sync_index, read_index
from chloe_init import initialize_workspace, initialize_project
import json


class SharedProjectIndexTests(HttpTestCase):
    def setUp(self):
        super().setUp()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / 'projects'
        self.root.mkdir()
        for name in ('甲', '乙', '丙'):
            (self.root / name).mkdir()
            (self.root / name / 'README.md').write_text('# ' + name)

    def state(self, name, archived):
        (self.root / name / 'README.md').write_text(
            '# ' + name + '\n- 项目管理状态：' + ('已归档' if archived else '进行中')
            + '\n- 归档原因：暂缓制作\n- 最近归档时间：2026-11-08T12:00:00+08:00\n')

    def entries(self):
        return index_entries(read_index(self.root)[0])

    def test_legacy_migration_uses_readmes_and_preserves_order_notes_and_idempotence(self):
        self.state('甲', True)
        path = self.root / '项目总索引.md'
        path.write_text('# 项目总索引\n\n说明保留。\n\n1. 这是额外说明\n\n| 编号 | 项目名称 | 项目管理状态 | 归档原因 |\n'
                        '| --- | --- | --- | --- |\n| 01 | 甲 | 进行中 | 无 |\n| 02 | 丙 | 进行中 | 无 |\n| 03 | 乙 | 进行中 | 无 |\n')
        sync_index(self.root)
        self.assertEqual(self.entries(), [('进行中', '丙'), ('进行中', '乙'), ('已归档', '甲')])
        self.assertIn('说明保留。', path.read_text())
        self.assertIn('1. 这是额外说明', path.read_text())
        self.assertIn('| 01 | 甲 | 暂缓制作 |', path.read_text())
        before = path.read_bytes(), path.stat().st_mtime_ns
        sync_index(self.root)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_archive_restore_append_to_destination_and_register_does_not_move_existing(self):
        for name in ('甲', '乙', '丙'):
            register_project(self.root / name)
        self.state('丙', True)
        sync_index(self.root)
        self.state('甲', True)
        sync_index(self.root)
        self.assertEqual(self.entries(), [('进行中', '乙'), ('已归档', '丙'), ('已归档', '甲')])
        self.state('甲', False)
        sync_index(self.root)
        self.assertEqual(self.entries(), [('进行中', '乙'), ('进行中', '甲'), ('已归档', '丙')])
        self.assertFalse(register_project(self.root / '甲'))
        self.assertEqual(self.entries(), [('进行中', '乙'), ('进行中', '甲'), ('已归档', '丙')])

    def test_both_empty_tables_and_missing_stale_projects(self):
        empty = self.base / 'empty'
        empty.mkdir()
        sync_index(empty)
        text = read_index(empty)[0]
        self.assertIn('## 进行中', text)
        self.assertIn('## 已归档', text)
        self.assertEqual(index_entries(text), [])
        (self.root / '项目总索引.md').write_text('# 项目总索引\n\n1. 已移除\n2. 乙\n')
        sync_index(self.root)
        self.assertEqual([name for _, name in self.entries()], ['乙', *sorted(['甲', '丙'])])

    def test_duplicate_entries_fail_without_rewriting(self):
        path = self.root / '项目总索引.md'
        path.write_text('# 项目总索引\n\n1. 甲\n2. 甲\n')
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, '重复'):
            sync_index(self.root)
        self.assertEqual(path.read_bytes(), before)

    def test_chloe_initialization_and_scoped_document_endpoints(self):
        chloe = initialize_workspace(self.base / 'Chloe Workspace')
        for name in ('乙账号', '甲账号'):
            initialize_project(chloe, name)
        iris = self.base / 'Iris Workspace'
        (iris / 'projects/商业项目').mkdir(parents=True)
        sync_index(iris / 'projects')
        runtime = self.base / 'runtime'
        runtime.mkdir()
        (runtime / 'workspaces.json').write_text(json.dumps([
            {'id': 'iris', 'name': '商业空间', 'path': str(iris), 'view': 'iris-commercial'},
            {'id': 'chloe', 'name': '账号空间', 'path': str(chloe), 'view': 'chloe-commerce', 'project_layout': 'nested'}]))
        sync_index(self.root)
        spaces = Workspaces(self.base, runtime, ProjectFiles(self.root), 'test')
        self.assertEqual([row['id'] for row in spaces.get('chloe').public()['projects']], ['乙账号', '甲账号'])
        client = TestClient(main.app)
        self.addCleanup(client.close)
        with patch.object(main.app.state, 'workspaces', spaces, create=True):
            for identity, text in [('nora', '甲'), ('iris', '商业项目'), ('chloe', '乙账号')]:
                response = client.get('/api/workspaces/' + identity + '/project-index')
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn(text, response.json()['html'])
                self.assertIn('已归档', response.json()['html'])
                if identity != 'chloe':
                    self.assertNotIn('乙账号', response.json()['html'])
