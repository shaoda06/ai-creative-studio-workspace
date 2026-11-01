import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import main
from backend.services.projects import ProjectStore
from backend.services.workspaces import Workspaces
from tests.http_case import HttpTestCase


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
        self.assertEqual(self.spaces.get('commercial').runtime, (self.other / '工作区浏览服务/runtime').resolve())

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
    def test_client_prefix_keeps_legacy_and_registered_agent_routes(self):
        import importlib.util
        import io
        path = Path(__file__).resolve().parents[2] / '.agents/skills/nora-workspace-browser/scripts/browser_tasks.py'
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
