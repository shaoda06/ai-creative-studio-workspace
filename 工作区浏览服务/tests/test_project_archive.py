"""Archive labels use isolated project roots; no Codex mutations or real files."""
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import main
from backend.services.project_files import ProjectFiles
from backend.services.workspaces import Workspaces
from tests.http_case import HttpTestCase
from workspace_project_index import read_archive
from project_init import initialize
from chloe_init import initialize_workspace, initialize_project
import chloe_documents


ARCHIVED = ('- 项目管理状态：已归档\n- 归档原因：暂缓制作\n'
            '- 最近归档时间：2026-11-08T12:00:00+08:00\n- 最近恢复时间：无\n')


class ProjectArchiveTests(HttpTestCase):
    def setUp(self):
        super().setUp()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.nora, self.iris, self.chloe = [self.base / name for name in ('nora', 'iris', 'Chloe Workspace')]
        for root in (self.nora, self.iris):
            for name in ('甲项目', '乙项目'):
                path = root / 'projects' / name
                path.mkdir(parents=True)
                (path / 'README.md').write_text('# ' + name + '\n')
                (path / '项目进度.md').write_text('原制作进度保持不变\n')
        initialize_workspace(self.chloe)
        self.account = initialize_project(self.chloe, '甲项目')
        runtime = self.base / 'runtime'
        runtime.mkdir()
        (runtime / 'workspaces.json').write_text(json.dumps([
            {'id': 'iris', 'name': '商业空间', 'path': str(self.iris), 'view': 'iris-commercial'},
            {'id': 'chloe', 'name': '账号空间', 'path': str(self.chloe), 'view': 'chloe-commerce', 'project_layout': 'nested'}]))
        self.store = ProjectFiles(self.nora / 'projects')
        self.spaces = Workspaces(self.nora, runtime, self.store, 'test')
        for override in (patch.object(main, 'store', self.store),
                         patch.object(main.app.state, 'workspaces', self.spaces, create=True)):
            override.start()
            self.addCleanup(override.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def test_three_spaces_read_whole_project_and_restore_without_changing_progress(self):
        paths = [self.nora / 'projects/甲项目', self.iris / 'projects/甲项目', self.account]
        for path, reason in zip(paths, ['暂缓制作', '停止合作', '停止运营']):
            readme = path / 'README.md'
            readme.write_text(readme.read_text() + '\n' + ARCHIVED.replace('暂缓制作', reason))
        before = {p: p.read_bytes() for root in paths for p in root.rglob('*') if p.is_file()}
        response = self.client.get('/api/workspaces')
        self.assertEqual(response.status_code, 200, response.text)
        for space, reason in zip(response.json(), ['暂缓制作', '停止合作', '停止运营']):
            item = next(p for p in space['projects'] if p['id'] == '甲项目')
            self.assertEqual(item['archive']['status'], 'archived')
            self.assertEqual(item['archive']['reason'], reason)
        self.assertEqual(next(p for p in self.client.get('/api/projects').json() if p['id'] == '甲项目')['archive']['status'], 'archived')
        self.assertEqual(next(p for p in self.client.get('/api/workspaces/iris/projects').json() if p['id'] == '甲项目')['archive']['reason'], '停止合作')
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        readme = paths[0] / 'README.md'
        readme.write_text(readme.read_text().replace('项目管理状态：已归档', '项目管理状态：进行中')
                          .replace('最近恢复时间：无', '最近恢复时间：2026-11-08T13:00:00+08:00'))
        state = next(p for p in self.client.get('/api/projects').json() if p['id'] == '甲项目')['archive']
        self.assertEqual(state['status'], 'active')
        self.assertEqual(state['reason'], '暂缓制作')
        self.assertEqual(state['restoredAt'], '2026-11-08T13:00:00+08:00')
        self.assertEqual((paths[0] / '项目进度.md').read_text(), '原制作进度保持不变\n')

    def test_unmarked_completed_text_and_child_video_do_not_archive_project(self):
        readme = self.nora / 'projects/甲项目/README.md'
        readme.write_text('# 项目\n制作已完成，历史方案已归档。\n\n```md\n' + ARCHIVED + '```\n')
        child = self.account / 'projects/V001-视频'
        child.mkdir()
        (child / 'README.md').write_text(ARCHIVED)
        for space in self.client.get('/api/workspaces').json():
            self.assertTrue(all('archive' not in project for project in space['projects']))
        self.assertEqual(read_archive(self.base / 'missing'), {})

    def test_invalid_labels_report_read_error_and_recover_after_edit(self):
        path = self.nora / 'projects/甲项目/README.md'
        for text in (ARCHIVED.replace('已归档', '制作完成'), ARCHIVED.replace('暂缓制作', '无'),
                     ARCHIVED + '- 项目管理状态：进行中\n'):
            path.write_text(text)
            for url in ('/api/projects', '/api/workspaces', '/api/workspaces/nora/projects'):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 409, response.text)
                self.assertIn('甲项目', response.json()['detail'])
        path.write_text(ARCHIVED)
        self.assertEqual(self.client.get('/api/workspaces').status_code, 200)

    def test_old_migration_marker_stays_hidden_and_readonly(self):
        path = self.nora / 'projects/甲项目'
        (path / '.archived').write_text('已迁移')
        (path / 'README.md').write_text(ARCHIVED)
        self.assertEqual([item['id'] for item in self.store.discover()], ['乙项目'])
        self.assertEqual(self.store.project('甲项目'), path.resolve())
        with self.assertRaises(PermissionError):
            self.store.project('甲项目', writable=True)

    def test_index_status_is_display_only_and_initializer_keeps_four_columns(self):
        index = self.nora / 'projects/项目总索引.md'
        index.write_text('# 项目总索引\n\n| 编号 | 项目名称 | 项目管理状态 | 归档原因 |\n'
                         '| --- | --- | --- | --- |\n| 01 | 乙项目 | 已归档 | 已完成 |\n| 02 | 甲项目 | 进行中 | 无 |\n')
        initialize(self.nora / 'projects/新项目')
        response = self.client.get('/api/projects')
        self.assertEqual([row['id'] for row in response.json()], ['乙项目', '甲项目', '新项目'])
        self.assertNotIn('archive', response.json()[0])
        self.assertIn('| 03 | 新项目 | 进行中 | 无 |', index.read_text())

    def test_chloe_markers_fit_existing_document_schema(self):
        path = self.account / 'README.md'
        path.write_text(path.read_text() + '\n' + ARCHIVED.replace('暂缓制作', '暂停运营'))
        source = chloe_documents.template('chloe-positioning', '项目README模板.md')
        result = chloe_documents.read_document(self.account, path, source, {'title': self.account.name})
        self.assertEqual(result['title'], self.account.name + '｜Chloe视频项目')
