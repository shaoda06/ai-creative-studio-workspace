"""Two films may share P/R names and media without sharing state or review notes."""
import json
from urllib.parse import quote, unquote
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import main
from backend.services.projects import ProjectStore
from backend.services.workspaces import Workspaces
from backend.services import episode_downloads
from tests.http_case import HttpTestCase


class IrisWorksTests(HttpTestCase):
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.iris = self.root / 'iris'
        self.project = self.iris / 'projects/C001-隔离项目'
        self.project.mkdir(parents=True)
        (self.root / 'nora/projects').mkdir(parents=True)
        runtime = self.root / 'runtime'
        runtime.mkdir()
        (runtime / 'workspaces.json').write_text(json.dumps([{
            'id': 'commercial', 'name': 'Iris', 'path': str(self.iris), 'view': 'iris-commercial',
            'production_adapter': 'iris-commercial-production',
        }]))
        spaces = Workspaces(self.root / 'nora', runtime, ProjectStore(self.root / 'nora/projects'), 'test')
        for space in spaces.items.values():
            space.tasks = SimpleNamespace(token='test', public=lambda **kwargs: {'tasks': []})
        override = patch.object(main.app.state, 'workspaces', spaces, create=True)
        override.start()
        self.addCleanup(override.stop)
        self.client = TestClient(main.app, base_url='http://localhost:8782', client=('127.0.0.1', 50000),
                                 headers={'Origin': 'http://localhost:8782'})
        self.addCleanup(self.client.close)
        download_override = patch.object(episode_downloads, 'DOWNLOAD_DIRECTORY', self.root / 'downloads')
        download_override.start()
        self.addCleanup(download_override.stop)
        self.api = '/api/workspaces/commercial/projects/C001-隔离项目'
        self.write('README.md', '# 共同项目\n两支片')
        self.write('01-客户资料/客户原稿.md', '# 共用原稿')
        self.write('08-完单复盘/项目复盘.md', '# 整单复盘')
        self.write('资源/视频/片段.mp4', 'shared local fixture')
        self.works = {}
        for identity, name in [('F001', '产品片'), ('F002', '品牌片')]:
            key = f'作品/{identity}-{name}'
            self.works[identity] = key
            self.write(key + '/README.md', '# ' + name)
            script = key + '/03-创意脚本/制作脚本-v01.md'
            self.write(script, '# ' + name + '\n## 正文\n' + identity + '专属正文')
            manifest = key + '/07-返修交接/草稿.jianying.json'
            self.write(manifest, json.dumps({'name': name, 'media': [{'file': '资源/视频/片段.mp4', 'member': 'P001.mp4'}]}))
            self.write(key + '/作品状态.md',
                       '| 对象 | 当前版本/文件 |\n| --- | --- |\n| 制作脚本 | ' + script + ' |\n\n'
                       '| 交付成果 | 类型 | 项目文件 | 版本 | 用途 |\n| --- | --- | --- | --- | --- |\n'
                       f'| {name} | 剪映草稿 | [清单](<{manifest}>) | 横版v01 | 本片交接 |\n')
            self.journal(key, key + '/06-视频生产/执行记录/R001-一采', identity)

    def write(self, key, text):
        path = self.project / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def journal(self, work, record, identity):
        output = work + '/06-视频生产/候选/P001-一采.mp4'
        self.write(output, identity + '候选')
        self.write(record + '/提交任务清单-装配结果.json', json.dumps({
            'accepted': [{'local_task_id': identity}], 'tasks': [{
                'task_type': 'video-first-pass', 'project': str(self.project), 'record_dir': str(self.project / record),
                'outputs': [{'path': output}],
            }]}))

    def test_works_keep_stage_documents_and_project_resources_in_their_scope(self):
        project = self.client.get(self.api).json()
        self.assertEqual([item['id'] for item in project['works']], ['F001', 'F002'])
        for identity, key in self.works.items():
            response = self.client.get(self.api + '/works/' + identity)
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data['irisPresentation']['primary']['03-创意脚本'], [key + '/03-创意脚本/制作脚本-v01.md'])
            source, = data['irisPresentation']['brief']['sources']
            self.assertEqual(source['key'], '01-客户资料/客户原稿.md')
            self.assertEqual(self.client.get(source['url']).status_code, 200)
            self.assertEqual(data['irisPresentation']['primary']['08-完单复盘'], ['08-完单复盘/项目复盘.md'])
            self.assertEqual(data['productionSection'], key + '/06-视频生产')

    def test_project_reads_current_work_status_from_the_work_document(self):
        key = self.works['F001'] + '/作品状态.md'
        project_status = self.write('项目状态.md', f'## 作品入口\n\n[作品状态](<{key}>)\n')
        self.write(key, '# 作品状态\n\n- 制作状态：前期准备\n')
        self.assertEqual([item['statusLabel'] for item in self.client.get(self.api).json()['works']], ['前期准备', ''])
        self.write(key, '# 作品状态\n\n制作状态: 待审阅\n')
        self.assertEqual([item['statusLabel'] for item in self.client.get(self.api).json()['works']], ['待审阅', ''])
        self.assertIn('[作品状态]', project_status.read_text())

    def test_duplicate_segment_and_run_names_keep_notes_and_results_separate(self):
        for identity in self.works:
            api = self.api + '/works/' + identity
            data = self.client.get(api + '/production').json()
            segment, = data['segments']
            video, = segment['videos']
            self.assertEqual((segment['id'], video['run']), ('P001', 'R001'))
            self.assertEqual(self.client.get(video['url']).text, identity + '候选')
            self.assertFalse(video['approved'])
            note = {'segment': 'P001', 'stage': '一采', 'run': 'R001', 'text': identity + '意见',
                    'fileRevision': video['fileRevision'], 'expectedText': ''}
            self.assertEqual(self.client.put(api + '/production-notes', json=note).status_code, 200)
        for identity in self.works:
            data = self.client.get(self.api + '/works/' + identity + '/production-notes').json()
            self.assertEqual(data['notes']['P001/一采/R001']['text'], identity + '意见')
        self.assertFalse((self.project / '06-视频生产/视频修改意见.json').exists())

    def test_historical_records_remain_recoverable_from_the_same_task(self):
        key = self.works['F001']
        old = self.project / '旧执行记录/R001-一采'
        old.parent.mkdir()
        (self.project / key / '06-视频生产/执行记录/R001-一采').rename(old)
        self.journal(key, '旧执行记录/R001-一采', 'F001')
        self.write(key + '/06-视频生产/历史执行入口.json', json.dumps({'records': ['旧执行记录'], 'archives': []}))
        api = self.api + '/works/F001/production'
        candidate = self.project / key / '06-视频生产/候选/P001-一采.mp4'
        contents = candidate.read_bytes()
        candidate.unlink()
        self.assertEqual(self.client.get(api).json()['segments'][0]['videos'][0]['deliveryStatus'], '未取回')
        candidate.write_bytes(contents)
        video = self.client.get(api).json()['segments'][0]['videos'][0]
        self.assertEqual(video['deliveryStatus'], '已取回')
        self.assertTrue(unquote(video['taskStateUrl']).endswith('/旧执行记录/R001-一采/后台任务状态.json'))
        self.assertEqual(len(self.client.get(self.api + '/works/F002/production').json()['segments']), 1)

    def test_only_user_download_calls_package_script_with_project_scoped_media(self):
        with patch.object(episode_downloads.jianying_export, 'export_archive') as export:
            for identity in self.works:
                data = self.client.get(self.api + '/works/' + identity).json()
                item, = data['irisPresentation']['delivery']['items']
                export.assert_not_called()
                self.assertIn(quote(self.works[identity], safe=''), item['file']['jianying']['jypack'])
            def write_package(files, path, name, timeline_members, archive_format):
                Path(path).write_bytes(b'isolated-package')
            export.side_effect = write_package
            response = self.client.get(item['file']['jianying']['jypack'])
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(export.call_args.args[0], [(self.project / '资源/视频/片段.mp4', 'P001.mp4')])

    def test_unknown_empty_and_invalid_work_sources_do_not_fall_back_to_project(self):
        for suffix in ('', '/production', '/production-notes'):
            self.assertEqual(self.client.get(self.api + '/works/F999' + suffix).status_code, 404)
        self.assertEqual(self.client.get(self.api + '/works/not-a-work/production').status_code, 404)
        (self.project / '作品/F003-空作品').mkdir()
        empty = self.client.get(self.api + '/works/F003/production').json()
        self.assertEqual(empty['segments'], [])
        self.write(self.works['F001'] + '/06-视频生产/历史执行入口.json', '{')
        self.assertEqual(self.client.get(self.api + '/works/F001').status_code, 409)
        self.write(self.works['F001'] + '/06-视频生产/历史执行入口.json', json.dumps({'records': ['../'], 'archives': []}))
        self.assertEqual(self.client.get(self.api + '/works/F001/production').status_code, 409)
        (self.project / '作品/F001-重复编号').mkdir()
        self.assertEqual(self.client.get(self.api).status_code, 409)
