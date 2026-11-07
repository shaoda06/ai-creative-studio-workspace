import json
import shutil
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import main
from backend.services.projects import ProjectStore
from backend.services.workspaces import Workspaces
from tests.http_case import HttpTestCase
import project_resources as resources


class WorkspaceTests(HttpTestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.primary, self.other = self.root / 'primary', self.root / 'other'
        for root, content in [(self.primary, '本项目'), (self.other, '商业资料')]:
            project = root / 'projects/同名项目'
            project.mkdir(parents=True)
            (project / '说明.md').write_text('# 说明\n\n' + content + '\n\n[图片](图片.png)')
            (project / '图片.png').write_bytes(content.encode())
            (project / '子目录').mkdir()
        runtime = self.primary / '工作区浏览服务/runtime'
        runtime.mkdir(parents=True)
        (runtime / 'workspaces.json').write_text(json.dumps([
            {'id': 'commercial', 'name': '商业视频', 'path': str(self.other)}]))
        self.spaces = Workspaces(self.primary, runtime, ProjectStore(self.primary / 'projects'), 'test')
        for identity, space in self.spaces.items.items():
            space.tasks = SimpleNamespace(token=identity + '-token',
                public=lambda include_history=True, identity=identity: {'tasks': [{'id': identity}]},
                group_status=lambda group, identity=identity: {'id': group, 'owner': identity})
        for override in [patch.object(main.app.state, 'workspaces', self.spaces, create=True),
                         patch.object(main.app.state, 'comfy_tasks', self.spaces.get('nora').tasks, create=True)]:
            override.start()
            self.addCleanup(override.stop)
        self.client = TestClient(main.app, client=('127.0.0.1', 50000))
        self.addCleanup(self.client.close)
        self.api = '/api/workspaces/commercial'

    def test_account_overview_uses_registered_root_and_reports_invalid_documents(self):
        self.spaces.get('commercial').view = 'chloe-commerce'
        fixture = Path(__file__).resolve().parents[1]/'examples/chloe-overview/new'
        shutil.copytree(fixture, self.other, dirs_exist_ok=True)
        url = self.api + '/account-overview'
        self.assertEqual(list(self.client.get(url).json()), ['direction', 'videos'])
        path = self.other/'综合资料/账号定位.md'
        path.write_text(path.read_text().replace('| 目标人群 | 待确定 |', '| 目标人群 | 隔离人群 |'))
        self.assertEqual(self.client.get(url).json()['direction']['目标人群'], '隔离人群')
        self.assertEqual(self.client.get('/api/workspaces/nora/account-overview').status_code, 404)
        self.assertEqual(self.client.get('/api/workspaces/unknown/account-overview').status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 405)
        path.write_text(path.read_text().replace('## 账号方向', '## 临时写法'))
        self.assertEqual(self.client.get(url).status_code, 409)
        path.unlink()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_iris_overview_config_is_optional_and_leaves_source_readable(self):
        self.spaces.get('commercial').view = 'iris-commercial'
        root = self.other / 'projects/同名项目'
        (root / 'README.md').write_text('# 说明\n\n## 附件入口\n\n原文链接。', encoding='utf-8')
        url = self.api + '/projects/同名项目'
        self.assertEqual(self.client.get(url).json()['irisPresentation']['overviewHiddenSections'], {})

        config = root / '99-综合资料/项目概况展示.json'
        config.parent.mkdir()
        config.write_text(json.dumps({'README.md': ['附件入口']}, ensure_ascii=False), encoding='utf-8')
        self.assertEqual(self.client.get(url).json()['irisPresentation']['overviewHiddenSections'],
                         {'README.md': ['附件入口']})
        self.assertIn('原文链接。', self.client.get(url + '/document', params={'path': 'README.md'}).json()['html'])

    def test_iris_projects_prioritize_explicit_main_versions_and_adopted_media(self):
        self.spaces.get('commercial').view = 'iris-commercial'
        root = self.other / 'projects/同名项目'
        for directory in ('04-分镜声音', '05-资产'):
            (root / directory).mkdir()
        (root / '项目状态.md').write_text(
            '| 对象 | 当前版本/文件 |\n| --- | --- |\n'
            '| 资产 | 05-资产/资产清单-v01.md |\n\n'
            '| 分镜 | [现行稿](04-分镜声音/分镜与声音制作稿-v01.md) |\n\n'
            '## 历史\n\n| 对象 | 当前版本/文件 |\n| --- | --- |\n'
            '| 分镜 | 04-分镜声音/分镜与声音制作稿-v02.md |\n')
        for version in ('v01', 'v02'):
            (root / f'04-分镜声音/分镜与声音制作稿-{version}.md').write_text(version)
        (root / '05-资产/资产清单-v02.md').write_text('旧版')
        ref = resources.reserve(root, '05-资产/采用/定稿.png', key='adopted', producer='隔离测试')
        (root / ref['file']).parent.mkdir(parents=True, exist_ok=True)
        (root / ref['file']).write_bytes(b'approved image')
        (root / '05-资产/资产清单-v01.md').write_text(
            '| 编号 | 名称及具体状态 | 已有／需制作 | 当前文件及版本 |\n'
            '| --- | --- | --- | --- |\n'
            '| A001 | 已确认场景 | 已采用 | 采用/定稿.png；执行记录/生成.md |\n'
            '| A002 | 候选 | 待审 | 采用/定稿.png |\n')
        response = self.client.get(self.api + '/projects/同名项目')
        self.assertEqual(response.status_code, 200)
        presentation = response.json()['irisPresentation']
        self.assertEqual(presentation['primary'], {
            '04-分镜声音': ['04-分镜声音/分镜与声音制作稿-v01.md'],
            '05-资产': ['05-资产/资产清单-v01.md'],
        })
        adopted, = presentation['adopted']
        self.assertEqual(adopted['title'], 'A001 · 已确认场景')
        self.assertEqual(adopted['version'], 'V001')
        self.assertEqual(adopted['media']['key'], ref['file'])
        self.assertEqual(self.client.get(adopted['media']['url']).content, b'approved image')

    def test_iris_delivery_shows_only_registered_project_files(self):
        self.spaces.get('commercial').view = 'iris-commercial'
        root = self.other / 'projects/同名项目'
        (root / '交接.jianying.json').write_text('{}')
        (root / '预览.mp4').write_bytes(b'video')
        (root / '候选.mp4').write_bytes(b'candidate')
        (root / '历史交接.md').write_text('# 历史交接')
        (root / '项目状态.md').write_text(
            '| 交付状态 | 交付说明 | 归档交接记录 |\n| --- | --- | --- |\n'
            '| 已交接 | 内部剪辑交接 | [说明](历史交接.md) |\n\n'
            '| 交付成果 | 类型 | 项目文件 | 版本 | 用途 |\n| --- | --- | --- | --- | --- |\n'
            '| 草稿 | 剪映草稿 | [清单](交接.jianying.json) | R006 | 剪辑 |\n'
            '| 预览 | 审阅样片 | [文件](预览.mp4) | v01 | 审阅 |\n'
            '| 缺失 | 成片 | [文件](不存在.mp4) | v01 | 交付 |\n'
            '| 项目外 | 附件 | [文件](../说明.md) | v01 | 交付 |\n')
        url = self.api + '/projects/同名项目'
        delivery = self.client.get(url).json()['irisPresentation']['delivery']
        self.assertEqual(delivery['status'], '已交接')
        self.assertEqual(delivery['archivedHandoff'], '历史交接.md')
        draft, preview = delivery['items']
        self.assertTrue(draft['file']['jianying']['jypack'].endswith('&format=jypack'))
        self.assertEqual(preview['file']['kind'], 'video')
        self.assertEqual(self.client.get(preview['file']['url']).content, b'video')

    def test_iris_brief_preserves_originals_and_offers_archived_documents(self):
        self.spaces.get('commercial').view = 'iris-commercial'
        root = self.other / 'projects/同名项目'
        customer = root / '01-客户资料'
        customer.mkdir()
        (customer / '需求与来源-v01.md').write_text('# 当前需求')
        (customer / 'SRC003-甲方原稿.md').write_text('# 原稿')
        (customer / '工作稿').mkdir()
        (customer / '工作稿/临时说明.md').write_text('# 临时')
        ref = resources.reserve(root, '01-客户资料/原始参考/SRC001-参考图.png', key='fixture', producer='隔离测试')
        picture = root / ref['file']
        picture.parent.mkdir(parents=True, exist_ok=True)
        picture.write_bytes(b'customer image')
        archive = root / '归档/原项目'
        (archive / '01-甲方资料').mkdir(parents=True)
        (archive / '01-甲方资料/来源记录.md').write_text('# 历史来源')
        (archive / '制作简报.md').write_text('# 历史简报')
        for folder, filename in [('03-创意与脚本', '旧脚本.md'), ('04-分镜与视觉方案', '旧分镜.md')]:
            (archive / folder).mkdir()
            (archive / folder / filename).write_text('# 历史资料')
        (archive / '05-资产准备/历史版本').mkdir(parents=True)
        (archive / '05-资产准备/资产清单.md').write_text('# 归档清单')
        (archive / '05-资产准备/历史版本/资产清单-v01.md').write_text('# 旧工作版本')

        url = self.api + '/projects/同名项目'
        view = self.client.get(url).json()['irisPresentation']
        self.assertEqual(view['primary']['01-客户资料'], ['01-客户资料/需求与来源-v01.md'])
        original, image = view['brief']['sources']
        self.assertEqual(original['key'], '01-客户资料/SRC003-甲方原稿.md')
        self.assertEqual(image['key'], ref['file'])
        self.assertEqual(image['kind'], 'image')
        self.assertEqual(self.client.get(image['url']).content, b'customer image')
        self.assertEqual(view['brief']['archived'], [])
        for stage, folder, filename in [('03-创意脚本', '03-创意与脚本', '旧脚本.md'),
                                        ('04-分镜声音', '04-分镜与视觉方案', '旧分镜.md')]:
            entry, = view['stageArchives'][stage]
            self.assertEqual(entry['children'][0]['key'], f'归档/原项目/{folder}/{filename}')
            self.assertEqual(self.client.get(entry['children'][0]['url']).text, '# 历史资料')
        historical_assets, = view['stageArchives']['05-资产']
        self.assertEqual(historical_assets['key'], '归档/原项目/05-资产准备/资产清单.md')
        self.assertEqual(self.client.get(historical_assets['url']).text, '# 归档清单')

        (customer / '需求与来源-v01.md').unlink()
        (customer / 'SRC003-甲方原稿.md').unlink()
        picture.unlink()
        view = self.client.get(url).json()['irisPresentation']
        self.assertEqual(view['brief']['sources'], [])
        brief, sources = view['brief']['archived']
        self.assertEqual(brief['key'], '归档/原项目/制作简报.md')
        self.assertEqual(self.client.get(brief['url']).text, '# 历史简报')
        self.assertEqual(sources['children'][0]['key'], '归档/原项目/01-甲方资料/来源记录.md')

    def test_archived_projects_leave_discovery_but_keep_file_access(self):
        for identity, root in [('nora', self.primary), ('commercial', self.other)]:
            project = root / 'projects/同名项目'
            (project / '.archived').write_text('已迁移，原地址只读')
            (root / 'projects/项目总索引.md').write_text('| 01 | 同名项目 |')
            self.assertEqual(self.spaces.get(identity).projects.discover(), [])
            self.assertEqual(self.client.get(f'/api/workspaces/{identity}/projects/同名项目/files/说明.md').status_code, 200)
            with self.assertRaises(PermissionError):
                self.spaces.get(identity).projects.project('同名项目', writable=True)
            for path in ['../说明.md', '.archived']:
                self.assertEqual(self.client.get(f'/api/workspaces/{identity}/projects/同名项目/files/{path}').status_code, 404)

    def test_catalogue_lists_projects_without_private_runtime_details(self):
        response = self.client.get('/api/workspaces')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([s['id'] for s in response.json()], ['nora', 'commercial'])
        self.assertEqual(response.json()[1]['projects'], [{'id': '同名项目', 'name': '同名项目'}])
        self.assertNotIn(str(self.root), response.text)
        self.assertNotIn('token', response.text)

    def test_same_named_projects_and_links_remain_in_their_space(self):
        for identity, content in [('nora', '本项目'), ('commercial', '商业资料')]:
            base = f'/api/workspaces/{identity}/projects/同名项目'
            response = self.client.get(base + '/document', params={'path': '说明.md'})
            self.assertEqual(response.status_code, 200)
            self.assertIn(content, response.json()['html'])
            self.assertIn(f'/api/workspaces/{identity}/projects/', response.json()['html'])
            self.assertEqual(self.client.get(base + '/files/图片.png').content, content.encode())

    def test_tree_and_file_boundaries(self):
        root = self.other / 'projects/同名项目'
        (root / '.private').write_text('hidden')
        (root / 'escape.md').symlink_to(self.primary / 'projects/同名项目/说明.md')
        response = self.client.get(self.api + '/projects/同名项目')
        self.assertEqual(response.status_code, 200)
        names = [item['name'] for item in response.json()['files']]
        self.assertIn('子目录', names)
        self.assertNotIn('.private', names)
        self.assertNotIn('escape.md', names)
        for path in ['../../primary/projects/同名项目/说明.md', '.private', 'escape.md']:
            self.assertEqual(self.client.get(self.api + '/projects/同名项目/document', params={'path': path}).status_code, 404)
        response = self.client.get(self.api + '/projects/同名项目/files/说明.md')
        self.assertIn('sandbox', response.headers['content-security-policy'])

    def test_task_handlers_select_the_owning_store(self):
        self.assertEqual(self.client.get('/api/comfy/tasks').json()['tasks'], [{'id': 'nora'}])
        self.assertEqual(self.client.get(self.api + '/comfy/tasks').json()['tasks'], [{'id': 'commercial'}])
        self.assertEqual(self.spaces.get('commercial').runtime, (self.primary / '工作区浏览服务/runtime/workspaces/commercial').resolve())

    def test_internal_credentials_cannot_cross_spaces(self):
        url = self.api + '/internal/comfy/groups/original-group'
        for token in ['', 'nora-token']:
            self.assertEqual(self.client.get(url, headers={'x-nora-task-token': token}).status_code, 403)
        response = self.client.get(url, headers={'x-nora-task-token': 'commercial-token'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'id': 'original-group', 'owner': 'commercial'})
        self.assertEqual(self.client.get(url, headers={'x-nora-task-token': 'commercial-token',
                                                     'Origin': 'http://testserver'}).status_code, 403)

    def test_unknown_space_does_not_fall_back_to_primary(self):
        self.assertEqual(self.client.get('/api/workspaces/missing/comfy/tasks').status_code, 404)
        self.assertEqual(self.client.get('/api/workspaces/missing/projects').status_code, 404)


class WorkspaceClientTests(HttpTestCase):
    def test_shared_query_selects_explicit_workspace_without_changing_default(self):
        import importlib.util
        import io
        path = Path(__file__).resolve().parents[2] / '.agents/skills/studio-workspace-browser/scripts/browser_tasks.py'
        spec = importlib.util.spec_from_file_location('shared_workspace_query_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / '.agents/skills/studio-workspace-browser/scripts/browser_tasks.py'
            script.parent.mkdir(parents=True)
            script.touch()
            other = root / 'workspaces/Iris Workspace'
            runtime = root / '工作区浏览服务/runtime'
            (runtime / 'workspaces.json').parent.mkdir(parents=True)
            (runtime / 'workspaces.json').write_text(json.dumps([
                {'id': 'commercial', 'runtime_id': 'iris', 'path': str(other)}]))
            for owner, folder, prefix in [('nora', root, '/api'), ('commercial', other, '/api/workspaces/commercial')]:
                config = runtime / 'workspaces' / ('iris' if owner == 'commercial' else 'nora') / 'task-service.json'
                config.parent.mkdir(parents=True)
                config.write_text(json.dumps({'url': 'http://fixture.invalid', 'token': owner,
                    'api_prefix': prefix, 'workspace': str(folder)}))

            def reply(request, timeout):
                owner = 'commercial' if '/api/workspaces/commercial/' in request.full_url else 'nora'
                self.assertEqual(request.get_header('X-nora-task-token'), owner)
                return io.BytesIO(json.dumps({'id': 'same-id', 'owner': owner}).encode())

            with patch.object(module, '__file__', str(script)), patch.object(module.urllib.request, 'build_opener', return_value=SimpleNamespace(open=reply)):
                self.assertEqual(module.service_call('groups/same-id')['owner'], 'nora')
                self.assertEqual(module.service_call('groups/same-id', workspace=other)['owner'], 'commercial')
                self.assertEqual(module.service_call('groups/same-id', workspace=root)['owner'], 'nora')

    def test_client_prefix_keeps_legacy_and_registered_agent_routes(self):
        import importlib.util
        import io
        path = Path(__file__).resolve().parents[2] / '.agents/skills/studio-workspace-browser/scripts/browser_tasks.py'
        spec = importlib.util.spec_from_file_location('workspace_client_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for prefix, expected in [(None, '/api/internal/comfy/prepare'),
                                 ('/api/workspaces/commercial', '/api/workspaces/commercial/internal/comfy/prepare')]:
            configuration = {'url': 'http://127.0.0.1:8782', 'token': 'fixture-token'}
            if prefix:
                configuration['api_prefix'] = prefix
            opener = SimpleNamespace(open=lambda request, timeout: io.BytesIO(b'{"ok":true}'))
            with patch.object(module.urllib.request, 'build_opener', return_value=opener), patch.object(opener, 'open', wraps=opener.open) as opened:
                self.assertEqual(module.local_post(configuration, '/prepare', {}, 5), {'ok': True})
                self.assertEqual(opened.call_args.args[0].full_url, configuration['url'] + expected)
