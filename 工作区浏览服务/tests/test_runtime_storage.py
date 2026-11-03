"""Workspace registration and client routing share centralized task storage."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from backend import main
from backend.services.comfy_tasks import TaskStore
from backend.services.projects import ProjectStore
from backend.services.workspaces import Workspaces

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.agents/skills/studio-workspace-browser/scripts'))
from workspace_connection import read_connection


class RuntimeStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.primary = self.root / 'workspaces/Nora Workspace'
        self.luna = self.root / 'workspaces/Luna Workspace'
        for workspace in (self.primary, self.luna):
            (workspace / 'projects').mkdir(parents=True)
        self.runtime = self.root / '工作区浏览服务/runtime'
        self.runtime.mkdir(parents=True)
        self.registry = self.runtime / 'workspaces.json'
        self.registry.write_text(json.dumps([{'id': 'luna', 'name': 'Luna', 'path': str(self.luna)}]))

    def spaces(self):
        return Workspaces(self.primary, self.runtime, ProjectStore(self.primary / 'projects'), 'test')

    def test_new_workspace_owns_a_separate_database_and_reopens_original_records(self):
        spaces = self.spaces()
        for space in spaces.items.values():
            store = TaskStore(space.runtime, space.root)
            store.db.execute('INSERT INTO notification_reports VALUES (?, ?)', ('original', json.dumps({'owner': space.id})))
            store.db.commit()
            asyncio.run(store.close())
        for identity, space in self.spaces().items.items():
            store = TaskStore(space.runtime, space.root)
            saved = json.loads(store.db.execute('SELECT report FROM notification_reports WHERE batch_id=?', ('original',)).fetchone()[0])
            self.assertEqual(saved['owner'], identity)
            self.assertEqual(space.runtime, self.runtime / 'workspaces' / identity)
            self.assertFalse((space.root / '工作区浏览服务').exists())
            asyncio.run(store.close())

    def test_registered_connections_route_by_real_workspace_and_reject_unknown(self):
        for space in self.spaces().items.values():
            space.runtime.mkdir(parents=True)
            (space.runtime / 'task-service.json').write_text(json.dumps({
                'workspace': str(space.root), 'token': space.id, 'url': 'http://fixture.invalid',
                'api_prefix': space.api}))
        self.assertEqual(read_connection(self.root)['token'], 'nora')
        self.assertEqual(read_connection(self.primary)['token'], 'nora')
        self.assertEqual(read_connection(self.luna)['token'], 'luna')
        with self.assertRaisesRegex(ValueError, '未登记'):
            read_connection(self.root / 'workspaces/Unknown Workspace')

    def test_api_identifier_can_remain_while_storage_uses_iris(self):
        self.registry.write_text(json.dumps([{'id': 'commercial', 'runtime_id': 'iris', 'name': 'Iris', 'path': str(self.luna)}]))
        space = self.spaces().get('commercial')
        self.assertEqual(space.api, '/api/workspaces/commercial')
        self.assertEqual(space.runtime, self.runtime / 'workspaces/iris')

    def test_duplicate_or_escaping_runtime_identifier_is_rejected(self):
        for identity in ('nora', '../outside'):
            self.registry.write_text(json.dumps([{'id': 'luna', 'runtime_id': identity, 'path': str(self.luna)}]))
            with self.assertRaises(ValueError):
                self.spaces()

    def test_service_startup_writes_only_central_connections_on_each_restart(self):
        async def restart_twice():
            with patch.object(main, 'TOOL', self.runtime.parent), \
                 patch.object(main, 'WORKSPACE', self.primary), \
                 patch.object(main, 'store', ProjectStore(self.primary / 'projects')), \
                 patch.object(main, 'clear_downloads'), \
                 patch.object(main.prompt_library, 'initialize'), \
                 patch.object(main, 'RequestDiagnostics') as diagnostics:
                diagnostics.return_value.close = AsyncMock()
                for _ in range(2):
                    async with main.lifespan(main.app):
                        nora = read_connection(self.primary)
                        luna = read_connection(self.luna)
                        self.assertNotEqual(nora['token'], luna['token'])
                        self.assertEqual(luna['api_prefix'], '/api/workspaces/luna')
                        for space in main.app.state.workspaces.items.values():
                            database = space.tasks.db.execute('PRAGMA database_list').fetchone()[2]
                            self.assertEqual(Path(database), space.runtime / 'comfy-tasks.sqlite')
                            self.assertFalse((space.root / '工作区浏览服务').exists())
                self.assertFalse((self.runtime / 'task-service.json').exists())
        asyncio.run(restart_twice())

    def test_old_database_stops_startup_before_creating_an_empty_replacement(self):
        old = self.runtime / 'comfy-tasks.sqlite'
        old.write_bytes(b'old database fixture; must be migrated first')
        async def start():
            with patch.object(main, 'TOOL', self.runtime.parent), \
                 patch.object(main, 'WORKSPACE', self.primary), \
                 patch.object(main, 'store', ProjectStore(self.primary / 'projects')), \
                 patch.object(main, 'clear_downloads'), \
                 patch.object(main.prompt_library, 'initialize'):
                with self.assertRaisesRegex(RuntimeError, '旧任务库尚未迁移'):
                    async with main.lifespan(main.app):
                        self.fail('旧库存在时不能启动空库')
                self.assertFalse((self.runtime / 'workspaces/nora/comfy-tasks.sqlite').exists())
                self.assertEqual(old.read_bytes(), b'old database fixture; must be migrated first')
        asyncio.run(start())
