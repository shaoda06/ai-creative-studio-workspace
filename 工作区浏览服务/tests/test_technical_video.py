"""Generic H3/video jobs work without a drama hierarchy, script or adoption record."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import AsyncMock, patch

from backend.services import comfy_tasks as tasks, execution_checks, result_registration, result_summary
from tests import test_comfy_tasks as base


class TechnicalVideoTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = base.TaskTests.asyncSetUp
    asyncTearDown = base.TaskTests.asyncTearDown

    def configure(self, native=True):
        self.data.task_type = 'video-first-pass' if native else 'video-postprocess'
        self.data.title = '客户产品镜头'
        self.data.video_plan = {'adapter': 'technical', 'metadata': 'ffprobe'}
        if native:
            timeline = dict(global_={'commonEnabled': False}, segments=[{'durationSec': 3,
                'prompt': 'integrated_multimodal_description:\n[Shot 1] A product turns.\noverall_soundscape:\nSilence.\nnon_diegetic_music:\nN/A'}],
                output={'exportMode': 'segments'})
            timeline['global'] = timeline.pop('global_')
            self.data.workflow = {'director': {'class_type': 'MiniMaxH3Director', 'inputs': {
                'timeline_data': json.dumps(timeline), 'task_type': 't2v'}},
                'report': {'class_type': 'PreviewAny', 'inputs': {'source': ['director', 5]}}}
            self.data.outputs = []
            self.data.segment_plan = tasks.segments.SegmentPlan(director_node='director', report_node='report',
                output_root='/remote/output', targets=[dict(index=0, path=str(self.project/'客户镜头.mp4'), response_name='取回.json')])
        else:
            self.data.workflow = {'save': {'class_type': 'SaveVideo', 'inputs': {'filename_prefix': 'client/shot'}}}
            self.data.outputs = [tasks.OutputTarget(node_id='save', output_key='videos', index=0,
                path=str(self.project/'客户镜头.mp4'), response_name='取回.json')]
        return self.data

    async def test_h3_preparation_and_submit_do_not_read_drama_sources(self):
        self.configure()
        unrelated_mapping = self.record/'输入映射.json'
        unrelated_mapping.write_text('{"client_order":"commercial-format"}')
        with patch.object(self.store.generation_context, 'prepare_generation_context', side_effect=AssertionError('no drama')), \
             patch.object(self.store.generation_context, 'scene_round_basis', side_effect=AssertionError('no drama')):
            prepared = await self.store.prepare_only(self.data)
            self.assertTrue(prepared['prepared'])
            self.assertEqual(json.loads(unrelated_mapping.read_text()), {'client_order': 'commercial-format'})
            self.assertFalse((self.project/'09-剧集制作').exists())
            with patch.object(tasks, 'connect', AsyncMock(return_value=AsyncMock())), \
                 patch.object(tasks.client, 'submit', return_value={'prompt_id': 'technical-id', 'submission_state': 'accepted'}) as submit, \
                 patch.object(self.store, 'check_target_cache', AsyncMock()), patch.object(self.store, 'watch', AsyncMock()):
                accepted = await self.store.submit(self.data)
            self.assertEqual(submit.call_count, 1)
            key = accepted['monitor_id']
            self.assertEqual(self.store.rows[key]['state']['prompt_id'], 'technical-id')
        report = json.loads((self.record/'执行检查报告.json').read_text())
        self.assertNotIn('scene_composition', report['prepared_input'])
        self.assertNotIn('content_checks', report)

    async def test_real_media_registers_without_project_browser_or_adoption(self):
        self.configure(native=False)
        output = Path(self.data.outputs[0].path)
        subprocess.run([shutil.which('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i', 'color=s=64x48:r=24:d=1',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(output)], check=True)
        receipt = self.record/'取回.json'
        receipt.write_text(json.dumps({'prompt_id': 'technical-id', 'data': {'path': str(output)}}))
        self.store.rows['technical'] = {'input': self.data, 'state': dict(id='technical', project=self.project.name,
            title=self.data.title, task_type=self.data.task_type, status='completed', prompt_id='technical-id',
            collected=1, expected=1, created_at=tasks.client.now(), saved_outputs=[str(output)])}
        self.store.save('technical')
        with patch.object(result_registration, 'verify', wraps=result_registration.verify), \
             patch.object(self.store, 'refresh_reports'), patch.object(self.store, 'wake_group'):
            result = await result_registration.closeout_tasks(self.store, None, ['technical'])
            reused = await result_registration.closeout_tasks(self.store, None, ['technical'])
        self.assertTrue(result['user_message_ready'])
        self.assertTrue(reused['user_message_ready'])
        state = self.store.rows['technical']['state']
        self.assertEqual(state['closeout']['browser']['status'], 'not_requested')
        item = state['closeout']['video_outputs'][0]
        self.assertEqual((item['metadata']['width'], item['metadata']['height']), (64, 48))
        self.assertFalse((self.project/'09-剧集制作').exists())
        delivery = result_summary.video_delivery(self.store, [result_summary.summary(self.store, 'technical')])
        self.assertIsNone(delivery['tasks'][0]['videos'][0]['draft_file'])
        report = self.store.result_report(['technical'])
        self.assertNotIn('rounds', report)
        self.assertTrue(report['user_message_ready'])

    async def test_native_collect_failure_restart_and_retry_keep_original_task(self):
        self.configure()
        source = self.project/'技术输入.mp4'
        subprocess.run([shutil.which('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i', 'color=s=64x48:r=24:d=1',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source)], check=True)
        media = source.read_bytes()
        self.store.rows['technical'] = {'input': self.data, 'state': dict(id='technical', project=self.project.name,
            title=self.data.title, task_type=self.data.task_type, status='completed', prompt_id='original-id',
            collected=0, expected=1, created_at=tasks.client.now())}
        self.store.save('technical')
        terminal = {'history': {'outputs': {'report': {'text': [
            'Segment 1: 一采 mp4 saved → /remote/output/minimax_seg_export/run/seg_0000_pre.mp4']}}}}
        with patch.object(tasks.client, 'download', side_effect=tasks.client.ClientError('download_failed', 'isolated timeout')):
            failed = await tasks.segments.finish(self.store, 'technical', terminal)
        self.assertEqual(len(failed), 1)
        self.assertFalse(Path(self.data.segment_plan.targets[0].path).exists())
        await self.store.close()
        self.store = tasks.TaskStore(self.root/'runtime', self.root)
        self.store.queue_notifications = False
        def download(remote, args):
            path = Path(args.output)
            path.write_bytes(media)
            return dict(path=str(path), bytes=len(media), sha256=None,
                        remote={name: getattr(args, name) for name in ('filename', 'subfolder', 'type')})
        with patch.object(tasks.client, 'submit', side_effect=AssertionError('never regenerate')), \
             patch.object(tasks.client, 'download', side_effect=download) as collect:
            self.assertEqual(await tasks.segments.finish(self.store, 'technical', terminal), [])
            self.assertEqual(await tasks.segments.finish(self.store, 'technical', terminal), [])
            self.assertEqual(collect.call_count, 1)
        self.assertEqual(self.store.rows['technical']['state']['prompt_id'], 'original-id')
        with patch.object(self.store, 'refresh_reports'), patch.object(self.store, 'wake_group'):
            result = await result_registration.closeout_tasks(self.store, None, ['technical'])
        self.assertTrue(result['user_message_ready'])
        self.assertFalse((self.project/'09-剧集制作').exists())
        self.assertEqual(source.read_bytes(), media)

    def test_mixed_technical_results_do_not_require_a_business_page(self):
        self.configure(native=False)
        self.store.rows['technical'] = {'input': self.data, 'state': {'project': self.project.name}}
        result = result_registration.verify(None, self.store, 'technical', {'items': [
            {'technical': True, 'path': '客户镜头.mp4'}, {'image': True, 'path': '客户产品.png'}]})
        self.assertEqual(result['status'], 'not_requested')

    async def test_unknown_adapter_and_missing_explicit_native_target_reject_before_post(self):
        self.configure()
        self.data.video_plan['adapter'] = 'arbitrary-script'
        with self.assertRaisesRegex(ValueError, '未登记'):
            await self.store.prepare_only(self.data)
        self.data.video_plan['adapter'] = 'technical'
        self.data.segment_plan.targets = []
        with self.assertRaisesRegex(ValueError, '显式提供'):
            await self.store.prepare_only(self.data)
        self.assertFalse(self.store.rows)
