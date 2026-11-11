"""Exercise the scene workflow on the real task store with simulated ComfyUI IO."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from backend.main import SubmissionPlanInput
from backend.services import comfy_tasks, result_registration, submission_plans
from prepared_documents import read_journal


PROMPT = ('subject_definitions: <Picture 1> sets the room.\nsummary: A pause.\n'
          'retention_analysis: Keep the room.\ndetailed_description: [Shot 1] Hold.\n'
          'overall_soundscape: Room tone.\nnon_diegetic_music: N/A')


class SongssxTests(unittest.IsolatedAsyncioTestCase):
    async def test_scene_prepare_upload_and_recovery_use_one_output(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            project = workspace / 'projects/样本'
            project.mkdir(parents=True)
            runtime = workspace / 'runtime'
            endpoint = 'http://127.0.0.1:1'
            (workspace / 'comfyui-config.json').write_text(json.dumps({'remote-urls': [endpoint]}))
            source = project / 'reference.png'
            source.write_bytes(b'fixture')
            plan = project / 'plan.json'
            plan.write_text(json.dumps({'tasks': [{
                'title': '场次样本', 'task_type': 'video-scene-generation',
                'record_dir': 'record', 'output': 'out/scene.mp4',
                'songssx': {'width': 640, 'height': 384, 'reference_image_center_crop': False,
                            'lowres_scale': .6, 'seed': 7, 'remote_prefix': 'video/test/scene',
                            'segments': [{'p': f'P{i:03d}', 'duration': 5, 'overlap_frames': overlap,
                                          'images': [source.name], 'prompt': PROMPT}
                                         for i, overlap in enumerate((0, 0, 22), 1)]},
            }]}))
            desktop = dict(node='test', server='test', pipe='test', caller_thread='test')
            payload = SubmissionPlanInput(project=project.name, plan_file=plan.name,
                                          prepare_only=True, desktop=desktop, thread_id='test')
            store = comfy_tasks.TaskStore(runtime, workspace)
            try:
                with patch.object(store.client, 'submit', side_effect=AssertionError('no generation')), \
                        patch.object(store.client, 'upload', side_effect=AssertionError('no preparation upload')):
                    self.assertEqual((await submission_plans.execute(store, payload))['status'], 'prepared')
                self.assertEqual(store.rows, {})
                task = read_journal(project / 'plan-装配结果.json')['tasks'][0]
                self.assertEqual([seg['overlap_frames'] for seg in task['video_plan']['segments']], [0, 0, 22])
                self.assertEqual(len(task['uploads']), 1)
                self.assertEqual(task['workflow']['331']['inputs']['model'], ['407', 0])
                self.assertNotIn('343', task['workflow'])
                data = comfy_tasks.TaskInput(**task, url=endpoint, desktop=desktop, thread_id='test')
                with patch.object(store, 'read_session_name', new_callable=AsyncMock):
                    key = (await store.enqueue(data))['local_task_id']
                remote = {'name': 'ref.png', 'subfolder': 'record', 'type': 'input'}
                response = dict(remote=remote, input_path='record/ref.png', sha256=sha256(b'fixture').hexdigest())
                with patch.object(store.client, 'upload', return_value=response) as upload:
                    bound = await store.prepare(key)
                upload.assert_called_once()
                planner = json.loads(bound['402']['inputs']['timeline_data'])
                self.assertEqual(planner['images'][0]['file'], 'record/ref.png')
                canvas = json.loads((project / 'record/任务.workflow.json').read_text())
                node = next(item for item in canvas['nodes'] if item['id'] == 402)
                self.assertEqual(json.loads(node['widgets_values'][3]), planner)
                store.save(key, prompt_id='simulated-prompt')
            finally:
                await store.close()

            store = comfy_tasks.TaskStore(runtime, workspace)
            try:
                with patch.object(store.client, 'upload', side_effect=AssertionError('reuse upload receipt')):
                    self.assertEqual(await store.prepare(key), bound)
                remote = {'filename': 'scene.mp4', 'subfolder': 'video/test', 'type': 'output'}
                result = {'state': 'success', 'files': [{'node_id': '404', 'output_key': 'images',
                                                       'index': 0, 'file': remote}]}

                def download(_, args):
                    destination = Path(args.output)
                    destination.parent.mkdir()
                    destination.write_bytes(b'mock mp4')
                    return {'remote': remote, 'path': args.output, 'bytes': 8}

                with patch.object(store.client, 'download', side_effect=download) as fetch:
                    await store.finish_collection(key, result)
                    self.assertEqual(await store.collect(key, result), [])
                fetch.assert_called_once()
                with patch('backend.services.video_records.probe', side_effect=AssertionError('no routine probe')):
                    report = result_registration.register(store, key)
                self.assertEqual(report['items'][0]['path'], 'out/scene.mp4')
            finally:
                await store.close()

    async def test_scene_prepare_applies_confirmed_configuration(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            project = workspace / 'projects/样本'
            project.mkdir(parents=True)
            (workspace / 'comfyui-config.json').write_text('{"remote-urls": ["http://127.0.0.1:1"]}')
            (project / 'reference.png').write_bytes(b'fixture')
            desktop = dict(node='test', server='test', pipe='test', caller_thread='test')
            store = comfy_tasks.TaskStore(workspace / 'runtime', workspace)
            cases = [
                ('dialogue', 4, 3.0, [], ('343', '53')),
                ('combat', 4, 4.0, [1, 2], ('343', '345', '344', '342', '407', '400', '53')),
                ('combat', 6, 4.0, [1], ('343', '345', '344', '342', '400', '53')),
                ('dialogue', 2, -2.5, [2], ('343', '407', '53')),
            ]
            try:
                for index, (scene, high_steps, speed, loras, chain) in enumerate(cases, 1):
                    with self.subTest(scene=scene, high_steps=high_steps, loras=loras):
                        record_dir = f'configuration-{index}'
                        plan = project / f'{record_dir}.json'
                        plan.write_text(json.dumps({'tasks': [{
                            'title': '六步配置样本', 'task_type': 'video-scene-generation',
                            'record_dir': record_dir, 'output': f'out/{record_dir}.mp4',
                            'songssx': {'width': 1280, 'height': 736, 'seed': 7,
                                        'remote_prefix': f'video/test/{record_dir}',
                                        'configuration': {'high_steps': high_steps, 'scene_type': scene,
                                                          'speed': speed, 'loras': loras},
                                        'segments': [{'p': 'P001', 'duration': 5, 'overlap_frames': 0,
                                                      'images': ['reference.png'], 'prompt': PROMPT}]},
                        }]}))
                        payload = SubmissionPlanInput(project=project.name, plan_file=plan.name,
                                                      prepare_only=True, desktop=desktop, thread_id='test')
                        result = await submission_plans.execute(store, payload)
                        self.assertEqual(result['status'], 'prepared')
                        record = project / record_dir
                        api = json.loads((record / '任务.api.json').read_text())
                        planner = api['402']['inputs']
                        timeline = json.loads(planner['timeline_data'])
                        self.assertEqual((planner['width'], planner['height']), (1280, 736))
                        self.assertEqual(api['261']['inputs']['steps'], 6 + high_steps)
                        self.assertEqual(timeline['secondPassHighSteps'], high_steps)
                        self.assertEqual(timeline['secondPassLowresScale'], 0.6)
                        self.assertIs(timeline['referenceImageCenterCrop'], False)
                        self.assertEqual(api['343']['inputs']['strength_model'], speed)
                        active_loras = {key for key, node in api.items() if node['class_type'] == 'LoraLoaderModelOnly'}
                        self.assertEqual(active_loras, set(chain))
                        for target, source in zip(('331', *chain[:-1]), chain, strict=True):
                            self.assertEqual(api[target]['inputs']['model'], [source, 0])
                        canvas = json.loads((record / '任务.workflow.json').read_text())
                        nodes = {node['id']: node for node in canvas['nodes']}
                        self.assertEqual(nodes[261]['widgets_values_named']['steps'], 6 + high_steps)
                        self.assertEqual(nodes[343]['widgets_values_named']['strength_model'], speed)
                        self.assertEqual(nodes[343]['mode'], 0)
                self.assertEqual(store.rows, {})
            finally:
                await store.close()
