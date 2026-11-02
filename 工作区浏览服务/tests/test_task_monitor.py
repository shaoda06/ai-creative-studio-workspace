"""Global views over isolated stores; no submission or production writes."""
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from backend import main
from tests.http_case import HttpTestCase


class MonitorTests(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.spaces = {}
        for index, identity in enumerate(('nora', 'commercial')):
            state = dict(id='same-id', project='隔离项目', title=identity+'任务', task_type='image',
                         status='completed', created_at=f'2026-11-02T00:0{index}:00+00:00',
                         ended_at=f'2026-11-02T00:0{index}:30+00:00', source_session_name=identity+'会话',
                         credential='never-public')
            node = dict(url='https://node.invalid', name='共用节点', updated_at=state['created_at'],
                        queue=[dict(prompt_id='remote-nora', status='running', queue_position=None)],
                        running_count=1, queued_count=0, connection='connected', error=None, queue_error=None)
            active = dict(id=identity+'-running', title=identity, prompt_id='remote-'+identity,
                          remote_url=node['url'], source='local', status='running')
            data = dict(tasks=[active], local_tasks=[dict(active, queue='local')], remote_nodes=[node],
                        local_counts={node['url']:dict(queued=1,paused=0,history=1)},
                        history_updated_at={node['url']:state['ended_at']})
            tasks = SimpleNamespace(public=Mock(return_value=data), rows={'same-id':dict(state=state,input=SimpleNamespace(url=node['url']))})
            self.spaces[identity] = SimpleNamespace(id=identity,name=identity,api='/api/workspaces/'+identity,tasks=tasks)
        self.registry = SimpleNamespace(items=self.spaces, get=self.spaces.__getitem__)
        self.client = TestClient(main.app, base_url='http://127.0.0.1:8782')
        registry = patch.object(main.app.state,'workspaces',self.registry,create=True)
        registry.start()
        self.addCleanup(registry.stop)
        default = patch.object(main.app.state,'comfy_tasks',self.spaces['nora'].tasks,create=True)
        default.start()
        self.addCleanup(default.stop)

    def test_shared_remote_queue_matches_registered_task_from_other_space(self):
        data = self.client.get('/api/task-monitor').json()
        self.assertEqual({x['workspace_id'] for x in data['tasks']},{'nora','commercial'})
        self.assertEqual(len(data['remote_nodes']),1)
        registered = {x['prompt_id']:x for x in data['tasks']}
        remote = data['remote_nodes'][0]['queue'][0]
        self.assertEqual(registered[remote['prompt_id']]['workspace_id'],'nora')
        self.assertEqual(data['local_counts']['https://node.invalid'],dict(queued=2,paused=0,history=2))
        self.assertEqual(data['remote_nodes'][0]['updated_at'],'2026-11-02T00:01:00+00:00')
        for space in self.spaces.values():
            space.tasks.public.assert_called_once_with(include_history=False)

    def test_history_paging_search_filters_and_same_id_in_two_spaces(self):
        first = self.client.get('/api/task-monitor/history?limit=1').json()
        second = self.client.get('/api/task-monitor/history?offset=1&limit=1').json()
        self.assertEqual(first['total'],2)
        self.assertEqual(first['next_offset'],1)
        self.assertIsNone(second['next_offset'])
        self.assertEqual([first['items'][0]['workspace_id'],second['items'][0]['workspace_id']],['commercial','nora'])
        self.assertEqual(first['items'][0]['id'],second['items'][0]['id'])
        self.assertNotIn('credential',first['items'][0])
        self.assertEqual(self.client.get('/api/task-monitor/history?q=nora').json()['total'],1)
        self.assertEqual(self.client.get('/api/task-monitor/history?result=abnormal').json()['total'],0)
        self.assertEqual(self.client.get('/api/task-monitor/history?limit=101').status_code,422)

    def test_explicit_detail_owner_and_resource_links(self):
        async def detail(store, identity):
            owner = next(x for x in self.spaces.values() if x.tasks is store)
            return dict(summary=dict(id=identity,title=owner.name),outputs=[dict(url='/api/projects/隔离项目/files/图片.png')])
        with patch.object(main,'task_detail',AsyncMock(side_effect=detail)):
            for identity in self.spaces:
                result=self.client.get('/api/workspaces/'+identity+'/comfy/tasks/same-id/detail')
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.json()['summary']['title'],identity)
                self.assertTrue(result.json()['outputs'][0]['url'].startswith('/api/workspaces/'+identity+'/projects/'))
