"""Nested project roots remain separate while sharing a workspace task service."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote
from fastapi.testclient import TestClient
from tests.http_case import HttpTestCase
from backend import main
from backend.services.workspaces import Workspaces
from backend.services.project_files import ProjectFiles
from chloe_init import initialize_workspace, initialize_project, initialize_video, initialize_asset
from project_paths import scope_name, scope_root
from comfyui_config import load_config


class NamedProjectTests(HttpTestCase):
    def setUp(self):
        super().setUp()
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = initialize_workspace(self.base / 'Chloe Workspace')
        self.primary = self.base / 'primary'; (self.primary / 'projects').mkdir(parents=True)
        self.runtime = self.base / 'runtime'; self.runtime.mkdir()
        self.roots = [initialize_project(self.root, name) for name in ['甲项目', '乙项目']]
        for i, root in enumerate(self.roots):
            initialize_video(root, 'V001', '同名视频')
            initialize_asset(root, '模特', 'M001', '甲模特' if i == 0 else '乙模特')
        (self.runtime / 'workspaces.json').write_text(json.dumps([{
            'id':'demo', 'name':'示例空间', 'path':str(self.root), 'view':'chloe-commerce',
            'project_layout':'nested', 'production_adapter':'chloe-production'}]))
        self.spaces = Workspaces(self.primary, self.runtime, ProjectFiles(self.primary / 'projects'), 'test')
        self.spaces.get('demo').tasks = SimpleNamespace(token='demo-token')
        override = patch.object(main.app.state, 'workspaces', self.spaces, create=True)
        override.start(); self.addCleanup(override.stop)
        self.client = TestClient(main.app); self.addCleanup(self.client.close)

    def test_project_list_and_context_views_do_not_merge_same_ids(self):
        space = self.spaces.get('demo')
        self.assertEqual([p['id'] for p in space.public()['projects']], ['乙项目', '甲项目'])
        for i, root in enumerate(self.roots):
            api = '/api/workspaces/demo/contexts/' + quote(root.name)
            models = self.client.get(api + '/shared-models')
            self.assertEqual(models.status_code, 200, models.text)
            self.assertEqual(models.json()[0]['name'], '甲模特' if i == 0 else '乙模特')
            self.assertEqual(self.client.get(api + '/production-videos').status_code, 200)
            self.assertEqual(self.client.get(api + '/projects/V001-同名视频').status_code, 200)
            self.assertEqual(self.client.get(api + '/account-overview').status_code, 200)
            self.assertIs(space.select(root.name).tasks, space.tasks)
        self.assertEqual(self.client.get('/api/workspaces/demo/contexts/不存在/shared-models').status_code, 404)
        self.assertEqual(self.client.get('/api/workspaces/nora/contexts/甲项目/shared-models').status_code, 404)
        self.assertEqual(self.client.get('/api/workspaces/demo/projects/V001-同名视频').status_code, 404)

    def test_task_identities_resolve_to_exact_project_and_shared_area(self):
        projects = self.spaces.get('demo').projects
        for root in self.roots:
            for path in [root / 'projects/V001-同名视频', root / '综合资料']:
                key = scope_name(path, self.root)
                self.assertTrue(key.startswith(root.name + '::'))
                self.assertEqual(scope_root(self.root, key), path)
                self.assertEqual(scope_root(self.root, str(path), recorded=True), path)
                self.assertEqual(projects.project(key), path)
        for value in ['../外部::V001-同名视频', '甲项目::../乙项目', '甲项目::乙项目::@shared']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                scope_root(self.root, value)
        with self.assertRaises(FileNotFoundError): projects.project('V001-同名视频')

    def test_nested_registration_and_child_connection_use_one_runtime(self):
        from workspace_setup import register_workspace
        from workspace_connection import read_connection
        studio = self.base / 'studio'
        root = initialize_workspace(studio / 'workspaces/Chloe Workspace')
        child = initialize_project(root, '用户名称')
        runtime = studio / '工作区浏览服务/runtime'
        primary = runtime / 'workspaces/nora/task-service.json'
        primary.parent.mkdir(parents=True)
        primary.write_text(json.dumps({'workspace':str(studio / 'workspaces/Nora Workspace')}))
        register_workspace(root, identity='demo', name='示例', view='chloe-commerce', project_layout='nested')
        config = runtime / 'workspaces/demo/task-service.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'workspace':str(root),'workspace_id':'demo'}))
        self.assertEqual(read_connection(child), read_connection(root))
        self.assertFalse((root / 'projects').exists())
        self.assertEqual(json.loads((runtime / 'workspaces.json').read_text())[0]['project_layout'], 'nested')

    def test_projects_use_workspace_node_config_without_copy(self):
        (self.root / 'comfyui-config.json').write_text(json.dumps({'remote-urls':['http://example.invalid:8188']}))
        self.assertEqual(load_config(self.roots[0]), load_config(self.root))
        self.assertFalse((self.roots[0] / 'comfyui-config.json').exists())


from tests import test_comfy_tasks as task_fixtures
from backend.services.comfy_tasks import TaskStore
import unittest


class NamedProjectTaskTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = task_fixtures.TaskTests.asyncSetUp
    asyncTearDown = task_fixtures.TaskTests.asyncTearDown

    async def test_task_registration_and_restart_keep_same_named_videos_separate(self):
        keys = []
        for name in ['甲项目', '乙项目']:
            owner = self.root / name
            (owner / 'projects/V001-视频/执行附件/任务001').mkdir(parents=True)
            (owner / '综合资料').mkdir()
            (owner / 'README.md').write_text('# 项目')
            project = owner / 'projects/V001-视频'
            data = self.data.model_copy(deep=True)
            data.project = name + '::V001-视频'
            data.record_dir = '执行附件/任务001'
            data.outputs[0].path = '候选/result.png'
            data.start_paused = True
            registered = await self.store.enqueue(data)
            keys.append(registered['local_task_id'])
            self.assertEqual(self.store.rows[keys[-1]]['state']['project'], name + '::V001-视频')
            self.assertEqual(Path(self.store.rows[keys[-1]]['input'].project), project.resolve())
        await self.store.close()
        self.store = TaskStore(self.root / 'runtime', self.root)
        self.store.queue_notifications = False
        self.assertEqual(len(self.store.rows), 2)
        self.assertNotEqual(self.store.rows[keys[0]]['input'].project, self.store.rows[keys[1]]['input'].project)
        self.assertTrue(all(self.store.rows[key]['state']['status'] == 'paused' for key in keys))
