"""Image tools run with explicit requests, without drama cards, EP paths or generation."""
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from tests import test_comfy_tasks as base
from backend.services import result_registration, image_tasks
from tests import test_image_closeout as image_fixture
png = image_fixture.png

SKILLS = Path(__file__).resolve().parents[2] / '.agents/skills'
for name in ('nora-qwen-image', 'nora-imagegen', 'nora-image-processing'):
    sys.path.insert(0, str(SKILLS / name / 'scripts'))
from qwen_image_workflow import assemble
from imagegen_tool import generation_call, preserve_original


class ImageToolBoundaryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = base.TaskTests.asyncSetUp
    asyncTearDown = base.TaskTests.asyncTearDown
    seed = base.TaskTests.seed
    request = image_fixture.ImageCloseoutTests.request
    output = image_fixture.ImageCloseoutTests.output
    rel = image_fixture.ImageCloseoutTests.rel

    async def test_qwen_technical_job_prepares_and_collects_without_drama_or_browser(self):
        prompt = '一块蓝色布料，展示本次明确要求的纹理。'
        _, api, uploads, node = assemble(prompt=dict(rewritten_prompt=prompt, wh_ratio='1:1'),
                                        size=[32, 32], seed=17, mode='t2i', prefix='plain-job')
        self.assertEqual(api['672']['inputs']['value'], prompt)
        self.data.workflow, self.data.uploads = api, uploads
        target = self.project / '生成结果/布料.png'
        self.data.outputs[0].node_id = node
        self.data.outputs[0].path = str(target)
        self.data.image_plan = dict(adapter='technical', images=[dict(path='生成结果/布料.png', width=32, height=32)])
        with patch.object(self.store.client.Client, 'json', side_effect=AssertionError('no remote request')):
            result = await self.store.prepare_only(self.data)
        self.assertTrue(result['prepared'])
        self.seed(status='completed')
        self.store.save('task', collected=1)
        self.request()
        self.output(target, png(32, 32))
        projects = SimpleNamespace(get=Mock(side_effect=AssertionError('no project parsing')))
        result = await result_registration.closeout_tasks(self.store, projects, ['task'])
        self.assertTrue(result['user_message_ready'], result)
        state = self.store.rows['task']['state']['closeout']
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['browser']['status'], 'not_requested')
        self.assertNotIn('draft', state['display_outputs'][0])
        self.assertFalse((self.project / '03-人物资料').exists())
        self.assertFalse((self.project / '09-剧集制作').exists())
        projects.get.assert_not_called()
        before = target.read_bytes()
        again = image_tasks.register(self.store, 'task', [], self.record / '结果收尾报告.json')
        self.assertEqual(again['adapter'], 'technical')
        self.assertEqual(target.read_bytes(), before)

    def test_qwen_edit_binds_order_and_keeps_agent_text(self):
        files = [self.project / '参考A.png', self.project / '参考B.png']
        for file in files:
            file.write_bytes(png())
        prompt = '保留图像1的形状，采用图像2的颜色。'
        _, api, uploads, _ = assemble(prompt=dict(rewritten_prompt=prompt, wh_ratio='1:1'),
                                    size=[64, 64], seed=19, mode='edit', references=files, prefix='plain-edit')
        self.assertEqual(api['680']['inputs']['value'], prompt)
        self.assertEqual([binding['file'] for binding in uploads], list(map(str, files)))
        self.assertEqual([binding['node'] for binding in uploads], ['475', '700'])
        self.assertEqual(api['497']['inputs']['images.image_2'], ['701', 0])

    def test_native_call_and_original_file_need_no_business_record(self):
        source, destination = self.project / '原生.png', self.project / '结果/原生.png'
        raw = png(7, 3)
        source.write_bytes(raw)
        call = generation_call('由Agent准备的实际正文', [source], 'plain-native')
        self.assertIn('tools.image_gen__imagegen', call)
        self.assertIn('referenced_image_paths', call)
        self.assertNotIn('prompt_id', call)
        facts = preserve_original(source, destination)
        self.assertEqual((facts['width'], facts['height']), (7, 3))
        self.assertEqual(destination.read_bytes(), raw)
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(preserve_original(source, destination), facts)
