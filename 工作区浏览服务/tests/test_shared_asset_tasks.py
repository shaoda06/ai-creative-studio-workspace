"""Workspace shared resources use the same queue without project copies."""
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
from tests import test_comfy_tasks as base
from tests import test_image_closeout as image_fixture
from backend.services import comfy_tasks as t, result_registration
from backend.services.project_files import ProjectFiles
from backend.services.task_details import file_info
from backend.services.workspaces import scope_links
from backend.services import submission_plans
import project_paths as paths
import project_resources as resources
import comfyui_config
from image_processing import assemble_rtx


class SharedAssetTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = base.TaskTests.asyncSetUp
    asyncTearDown = base.TaskTests.asyncTearDown
    request = image_fixture.ImageCloseoutTests.request
    output = image_fixture.ImageCloseoutTests.output
    rel = image_fixture.ImageCloseoutTests.rel

    def setup_shared(self):
        self.root = self.root.resolve()
        self.project = self.root / '综合资料'
        self.project.mkdir()
        resources.initialize(self.project, managed=True)
        source = self.root / 'source.png'
        source.write_bytes(image_fixture.png(32, 48))
        ref = resources.register(self.project, source, key='source')
        actual = self.project / ref['file']
        self.record = self.project / '共用素材/M001/E003'
        _, api, uploads, node = assemble_rtx(str(actual), prefix='shared-M001-E003')
        target = '共用素材/M001/E003/正式.png'
        self.data.project = '@shared'
        self.data.record_dir = '共用素材/M001/E003'
        self.data.task_type = 'image-upscale'
        self.data.workflow = api
        self.data.uploads = uploads
        self.data.outputs = [t.OutputTarget(node_id=node, output_key='images', index=0,
            path=target, response_name='取回响应.json', resource_id=ref['resource_id'], base_file=ref['file'])]
        self.data.image_plan = {'adapter':'technical','images':[{'path':target,'width':64,'height':96}]}
        return ref, actual

    async def test_shared_preparation_collection_and_immutable_parent(self):
        ref, source = self.setup_shared()
        original = source.read_bytes()
        result = await self.store.prepare_only(self.data)
        self.assertTrue(result['prepared'])
        self.assertEqual(Path(self.data.project), self.project)
        target = Path(self.data.outputs[0].path)
        self.assertTrue(target.is_relative_to(self.project / '资源'))
        newer = resources.reference(self.project, target)
        self.assertEqual(newer['resource_id'], ref['resource_id'])
        self.assertEqual(newer['parent']['version'], ref['version'])
        base.TaskTests.seed(self, status='completed')
        self.store.save('task', project='@shared', collected=1)
        self.request()
        # Actual upload receipt, so closeout verifies the exact input binding.
        import execution_records as recordio
        upload=self.data.uploads[0]
        recordio.write(self.record/upload['response-name'], {'data':{'input_path':'shared-M001-E003/'+source.name,'name':source.name,'subfolder':'shared-M001-E003','type':'input'}})
        request=recordio.read(self.record/self.data.request_name)
        request['prompt']['2']['inputs']['image']='shared-M001-E003/'+source.name
        recordio.write(self.record/self.data.request_name,request)
        self.output(target, image_fixture.png(64,96))
        projects=SimpleNamespace(get=Mock(side_effect=AssertionError('no business parser')))
        outcome=await result_registration.closeout_tasks(self.store, projects, ['task'])
        self.assertTrue(outcome['user_message_ready'],outcome)
        self.assertEqual(source.read_bytes(),original)
        self.assertEqual(resources.reference(self.project, target)['version'],'V002')
        self.assertEqual(ProjectFiles(self.root/'projects').file('@shared',target.relative_to(self.project)),target)
        self.assertIn('/projects/%40shared/files/',file_info(self.project,target)['url'])
        self.assertNotIn('@shared',[x['id'] for x in ProjectFiles(self.root/'projects').discover()])

    async def test_shared_queue_restart_and_workspace_move(self):
        self.setup_shared()
        self.data.start_paused=True
        with patch.object(self.store,'read_session_name',return_value=None):
            result=await self.store.enqueue(self.data)
        payload=json.loads(self.store.db.execute('SELECT payload FROM tasks').fetchone()[0])
        self.assertEqual(payload['project'],'@shared')
        self.assertNotIn(str(self.root),json.dumps(payload['outputs']))
        await self.store.close()
        moved=self.root/'moved';moved.mkdir()
        for name in ['projects','综合资料','runtime']:
            shutil.move(self.root/name,moved/name)
        self.store=t.TaskStore(moved/'runtime',moved)
        restored=self.store.rows[result['local_task_id']]['input']
        self.assertEqual(Path(restored.project),moved/'综合资料')
        self.assertTrue(Path(restored.uploads[0]['file']).is_file())
        self.assertEqual(self.store.rows[result['local_task_id']]['state']['project'],'@shared')

    async def test_shared_boundaries_reject_escape_and_wrong_workspace(self):
        self.setup_shared()
        self.assertEqual(comfyui_config.workspace_for_project(self.project),self.root)
        with self.assertRaises(ValueError): paths.scope_root(self.root,'../综合资料')
        with self.assertRaises(ValueError): paths.scope_root(self.root,str(self.root.parent/'综合资料'))
        with self.assertRaises(ValueError): paths.project_file(self.project,'../projects/测试项目/reference.png')
        self.project.rename(self.root/'saved-common')
        self.project.symlink_to(self.root/'projects/测试项目',target_is_directory=True)
        with self.assertRaises(ValueError): paths.scope_root(self.root,'@shared')
        with self.assertRaises(ValueError): ProjectFiles(self.root/'projects').project('@shared')

    async def test_shared_plan_prepare_and_scoped_links(self):
        self.setup_shared()
        plan=self.project/'task.json'
        plan.write_text(json.dumps({'tasks':[{'task_type':self.data.task_type,'title':'共用图超分',
            'record_dir':self.data.record_dir,'workflow':self.data.workflow,'uploads':self.data.uploads,
            'outputs':[x.model_dump() for x in self.data.outputs],'image_plan':self.data.image_plan,
            'authorization':'隔离测试'}]}))
        payload=SimpleNamespace(project='@shared',plan_file='task.json',reprepare=False,prepare_only=True,
            start_paused=False,thread_id=self.data.thread_id,desktop=self.data.desktop,timeout=30)
        result=await submission_plans.execute(self.store,payload)
        self.assertEqual(result['status'],'prepared')
        self.assertEqual(scope_links('/#/','/api/workspaces/demo'),'/#/spaces/demo')
