"""Exercise the scene workflow on the real task store with simulated ComfyUI IO."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch
import wave

from backend.main import SubmissionPlanInput
from backend.services import comfy_tasks, execution_checks, result_registration, submission_plans
from prepared_documents import read_journal
from songssx_browser import songssx_contexts, songssx_scene
from songssx_workflow import aligned_frames, validate


PROMPT = ('subject_definitions: <Picture 1> sets the room.\nsummary: A pause.\n'
          'retention_analysis: Keep the room.\ndetailed_description: [Shot 1] Hold.\n'
          'overall_soundscape: Room tone.\nnon_diegetic_music: N/A')


class SongssxTests(unittest.IsolatedAsyncioTestCase):
    async def test_scene_binds_independent_audio_in_each_gen_order(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            project = workspace / 'projects/样本'
            project.mkdir(parents=True)
            endpoint = 'http://127.0.0.1:1'
            (workspace / 'comfyui-config.json').write_text(json.dumps({'remote-urls': [endpoint]}))
            (project / 'reference.png').write_bytes(b'fixture')
            for name, seconds in (('male.wav', 3), ('female.wav', 4)):
                with wave.open(str(project / name), 'wb') as audio:
                    audio.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
                    audio.writeframes(b'\0\0' * (8000 * seconds))
            plan = project / 'plan.json'
            prompt = PROMPT.replace('Room tone.', 'Voices from <Audio 1> and <Audio 2>.')
            plan.write_text(json.dumps({'tasks': [{
                'title': '独立音色样本', 'task_type': 'video-scene-generation',
                'authorization': '隔离样本，暂停登记',
                'record_dir': 'record', 'output': 'out/scene.mp4',
                'songssx': {'width': 1088, 'height': 1920, 'seed': 7, 'remote_prefix': 'video/test/audio',
                            'configuration': {'high_steps': 4, 'scene_type': 'dialogue', 'speed': None, 'loras': [2]},
                            'segments': [{'p': f'P{index:03d}', 'duration': 5, 'overlap_frames': 0,
                                          'images': ['reference.png'], 'audios': files, 'prompt': prompt}
                                         for index, files in enumerate(
                                             (['male.wav', 'female.wav'], ['female.wav', 'male.wav']), 1)]},
            }]}))
            desktop = dict(node='test', server='test', pipe='test', caller_thread='test')
            payload = SubmissionPlanInput(project=project.name, plan_file=plan.name,
                                          start_paused=True, desktop=desktop, thread_id='test')
            store = comfy_tasks.TaskStore(workspace / 'runtime', workspace)
            try:
                with patch.object(store, 'read_session_name', new_callable=AsyncMock), \
                        patch.object(store.client, 'submit', side_effect=AssertionError('paused cannot submit')), \
                        patch.object(store.client, 'upload', side_effect=AssertionError('paused cannot upload')):
                    await submission_plans.execute(store, payload)
                key, row = next(iter(store.rows.items()))
                self.assertEqual(row['state']['status'], 'paused')
                self.assertIsNone(row['state']['prompt_id'])
                task = read_journal(project / 'plan-装配结果.json')['tasks'][0]
                self.assertEqual([binding['json-path'] for binding in task['uploads']],
                                 [['images', 0, 'file'], ['audios', 0, 'file'], ['audios', 1, 'file']])

                def remote_upload(_, args, *, source):
                    path = Path(source)
                    remote = {'name': path.name, 'subfolder': 'record', 'type': 'input'}
                    return dict(remote=remote, input_path=f'record/{path.name}',
                                sha256=sha256(path.read_bytes()).hexdigest())

                # Exercise upload binding in isolation after verifying paused registration.
                with patch.object(store.client, 'upload', side_effect=remote_upload):
                    bound = await store.prepare(key)
                planner = bound['402']['inputs']
                timeline = json.loads(planner['timeline_data'])
                self.assertEqual([(item['file'], item['audioMode']) for item in timeline['audios']],
                                 [('record/male.wav', 'reference'), ('record/female.wav', 'reference')])
                segments = timeline['segmentConfig']['segments']
                self.assertEqual([segment['audios'] for segment in segments],
                                 [['audio-1', 'audio-2'], ['audio-2', 'audio-1']])
                prepared = {'workflow': task['workflow'], 'uploads': [
                    {**binding, 'file': Path(binding['file']).name} for binding in task['uploads']
                ]}
                contexts = songssx_contexts(project, prepared, bound, task['video_plan']['segments'],
                                            lambda _: {'issues': []})
                refs = [[(item['label'], item['kind'], item['name']) for item in ctx['references']['segment']]
                        for ctx in contexts]
                self.assertEqual(refs, [
                    [('<Picture 1>', 'image', 'reference.png'), ('<Audio 1>', 'audio', 'male.wav'),
                     ('<Audio 2>', 'audio', 'female.wav')],
                    [('<Picture 1>', 'image', 'reference.png'), ('<Audio 1>', 'audio', 'female.wav'),
                     ('<Audio 2>', 'audio', 'male.wav')],
                ])
                segments[0]['prompt'] = prompt.replace('<Audio 2>', '<Audio 3>')
                planner['timeline_data'] = json.dumps(timeline)
                data = comfy_tasks.TaskInput(**task, url=endpoint, desktop=desktop, thread_id='test')
                with self.assertRaisesRegex(ValueError, 'Audio 提示词标签'):
                    validate(bound, data.video_plan, data.outputs, data.uploads)
            finally:
                await store.close()

    def test_gen_duration_and_aligned_window_limits(self):
        for seconds, overlap, frames in [(4, 0, 107), (15, 0, 362), (15, 1, 362), (14, 22, 362)]:
            with self.subTest(seconds=seconds, overlap=overlap):
                self.assertEqual(aligned_frames(seconds, overlap), frames)
        for seconds in (3.999, 15.001):
            with self.subTest(seconds=seconds):
                with self.assertRaisesRegex(ValueError, '计划新增时长须在 4 至 15 秒之间'):
                    aligned_frames(seconds, 0)
        with self.assertRaisesRegex(ValueError, '396 帧.*22 帧重叠.*362 帧上限'):
            aligned_frames(15, 22)

    async def test_cached_preparation_does_not_bypass_current_shot_checks(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            project = workspace / 'projects/样本'
            project.mkdir(parents=True)
            endpoint = 'http://127.0.0.1:1'
            (workspace / 'comfyui-config.json').write_text(json.dumps({'remote-urls': [endpoint]}))
            (project / 'reference.png').write_bytes(b'fixture')
            plan = project / 'plan.json'
            plan.write_text(json.dumps({'tasks': [{
                'title': '旧准备报告样本', 'task_type': 'video-scene-generation',
                'record_dir': 'record', 'output': 'out/scene.mp4',
                'songssx': {'width': 1280, 'height': 736, 'seed': 7, 'remote_prefix': 'video/test/scene',
                            'configuration': {'high_steps': 4, 'scene_type': 'dialogue', 'speed': None, 'loras': []},
                            'segments': [{'p': 'P001', 'duration': 5, 'overlap_frames': 0,
                                          'images': ['reference.png'], 'prompt': PROMPT.replace('[Shot 1]', '')}]},
            }]}))
            desktop = dict(node='test', server='test', pipe='test', caller_thread='test')
            payload = SubmissionPlanInput(project=project.name, plan_file=plan.name,
                                          prepare_only=True, desktop=desktop, thread_id='test')
            store = comfy_tasks.TaskStore(workspace / 'runtime', workspace)
            try:
                with patch('songssx_workflow.validate_shots'):
                    self.assertEqual((await submission_plans.execute(store, payload))['status'], 'prepared')
                task = read_journal(project / 'plan-装配结果.json')['tasks'][0]
                data = comfy_tasks.TaskInput(**task, url=endpoint, desktop=desktop, thread_id='test')
                store.resolve_input(data)
                with self.assertRaisesRegex(ValueError, '连续镜号'):
                    execution_checks.check_prepared(store, data)
                with self.assertRaisesRegex(ValueError, '连续镜号'):
                    await submission_plans.execute(store, payload)
                self.assertFalse(execution_checks.read_report(data)['ok'])
                self.assertEqual(store.rows, {})
            finally:
                await store.close()

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
                            'segments': [{'p': f'P{i:03d}', 'duration': duration, 'overlap_frames': overlap,
                                          'images': [source.name], 'prompt': PROMPT, 'prompt_zh': f'第{i}段参考。'}
                                         for i, (duration, overlap) in enumerate(((15, 0), (15, 0), (14, 22)), 1)]},
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
                segments = task['video_plan']['segments']
                self.assertEqual([seg['overlap_frames'] for seg in segments], [0, 0, 22])
                self.assertEqual([seg['generation_frames'] for seg in segments], [[0, 362], [362, 724], [702, 1064]])
                self.assertEqual([seg['output_frames'] for seg in segments], [[0, 362], [362, 724], [724, 1064]])
                self.assertEqual(segments[2]['prompt_zh'], '第3段参考。')
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
                self.assertNotIn('prompt_zh', planner['segmentConfig']['segments'][2])
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

    async def test_gap_repair_uploads_two_visual_boundaries_and_collects_only_the_patch(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            project = workspace / 'projects/样本'
            project.mkdir(parents=True)
            endpoint = 'http://127.0.0.1:1'
            (workspace / 'comfyui-config.json').write_text(json.dumps({'remote-urls': [endpoint]}))
            for side, color in (('before', 'red'), ('after', 'blue')):
                run(['ffmpeg', '-loglevel', 'error', '-nostdin', '-f', 'lavfi', '-i',
                     f'color={color}:size=32x32:rate=24', '-frames:v', '3', '-c:v', 'libx264',
                     str(project / f'{side}.mp4')], check=True, capture_output=True)
            (project / 'reference.png').write_bytes(b'picture fixture')
            plan = project / 'plan.json'
            plan.write_text(json.dumps({'tasks': [{
                'title': '双边界返修样本', 'task_type': 'video-scene-generation',
                'record_dir': 'record', 'output': 'out/patch.mp4',
                'songssx': {'width': 640, 'height': 384, 'seed': 7, 'remote_prefix': 'video/test/patch',
                            'configuration': {'high_steps': 4, 'scene_type': 'dialogue', 'speed': None, 'loras': []},
                            'gap_repair': {'before': 'before.mp4', 'after': 'after.mp4'},
                            'segments': [{'p': 'P001', 'duration': 4, 'overlap_frames': 0,
                                          'images': ['reference.png'], 'prompt': PROMPT}]},
            }]}))
            desktop = dict(node='test', server='test', pipe='test', caller_thread='test')
            payload = SubmissionPlanInput(project=project.name, plan_file=plan.name,
                                          prepare_only=True, desktop=desktop, thread_id='test')
            store = comfy_tasks.TaskStore(workspace / 'runtime', workspace)
            try:
                with patch.object(store.client, 'upload', side_effect=AssertionError('no preparation upload')):
                    self.assertEqual((await submission_plans.execute(store, payload))['status'], 'prepared')
                task = read_journal(project / 'plan-装配结果.json')['tasks'][0]
                self.assertEqual(task['video_plan']['gap_repair'], {'before_source_frame': 2, 'replacement_frames': 96})
                self.assertEqual(task['video_plan']['segments'][0]['output_frames'], [0, 107])
                data = comfy_tasks.TaskInput(**task, url=endpoint, desktop=desktop, thread_id='test')
                with patch.object(store, 'read_session_name', new_callable=AsyncMock):
                    key = (await store.enqueue(data))['local_task_id']

                def uploaded(_, args, *, source):
                    return dict(remote={'name': source.name, 'subfolder': 'record', 'type': 'input'},
                                input_path='record/' + source.name, sha256=sha256(source.read_bytes()).hexdigest())

                with patch.object(store.client, 'upload', side_effect=uploaded) as upload:
                    bound = await store.prepare(key)
                self.assertEqual(upload.call_count, 3)
                timeline = json.loads(bound['402']['inputs']['timeline_data'])
                clips = timeline['videoClips']
                self.assertEqual([c['file'] for c in clips], ['record/before.mp4', 'record/after.mp4'])
                self.assertEqual([c['trimStart'] for c in clips], [2 / 24, 0])
                self.assertEqual(clips[0]['start'] + clips[0]['duration'], 0)
                self.assertEqual(clips[1]['start'], timeline['selection']['duration'])
                self.assertTrue(timeline['videoAudioEnabled'])
                self.assertEqual([c['hasAudio'] for c in clips], [False, False])
                self.assertEqual(timeline['images'][0]['file'], 'record/reference.png')
                self.assertEqual(timeline['segmentConfig']['segments'][0]['images'], ['image-1'])
                validate(bound, data.video_plan, data.outputs, data.uploads)

                for key_name, value in [('hasAudio', True), ('hasAudio', 0), ('start', 1)]:
                    invalid = deepcopy(bound)
                    bad = deepcopy(timeline)
                    bad['videoClips'][1][key_name] = value
                    invalid['402']['inputs']['timeline_data'] = json.dumps(bad)
                    with self.assertRaisesRegex(ValueError, '视频边界须紧贴'):
                        validate(invalid, data.video_plan, data.outputs, data.uploads)
                with self.assertRaisesRegex(ValueError, '逐一绑定实际上传目标'):
                    validate(bound, data.video_plan, data.outputs, data.uploads[:-1])
                with self.assertRaisesRegex(ValueError, '仅在 gap_repair'):
                    validate(bound, {k: v for k, v in data.video_plan.items() if k != 'gap_repair'},
                             data.outputs, data.uploads)

                with patch('backend.services.comfy_tasks.connect', new_callable=AsyncMock), \
                        patch.object(store, 'watch', new_callable=AsyncMock), \
                        patch.object(store, 'read_session_name', new_callable=AsyncMock), \
                        patch.object(store.client, 'submit', return_value={'prompt_id': 'simulated-gap'}) as submit:
                    receipt = await store.submit(data, key=key, workflow=bound)
                self.assertEqual(receipt['prompt_id'], 'simulated-gap')
                submit.assert_called_once()
                self.assertEqual(submit.call_args.kwargs['workflow'], bound)
                remote = {'filename': 'patch.mp4', 'subfolder': 'video/test', 'type': 'output'}
                result = {'state': 'success', 'files': [{'node_id': '404', 'output_key': 'images',
                                                         'index': 0, 'file': remote}]}

                def download(_, args):
                    destination = Path(args.output)
                    destination.parent.mkdir()
                    destination.write_bytes(b'mock patch')
                    return {'remote': remote, 'path': args.output, 'bytes': 10}

                with patch.object(store.client, 'download', side_effect=download) as fetch:
                    await store.finish_collection(key, result)
                fetch.assert_called_once()
                self.assertEqual(result_registration.register(store, key)['items'][0]['path'], 'out/patch.mp4')
                entry = {'songssx_execution': 'record', 'issues': [], 'segments': []}
                projected = songssx_scene(project, entry, None)
                self.assertFalse(projected['recorded'])
                self.assertIn('接回原片', entry['issues'][0])
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
                ('dialogue', 4, None, [], ('53',)),
                ('combat', 4, 4.0, [1, 2], ('343', '345', '344', '342', '407', '400', '53')),
                ('combat', 6, 4.0, [1], ('343', '345', '344', '342', '400', '53')),
                ('dialogue', 2, -2.5, [2], ('343', '407', '53')),
                ('dialogue', 994, None, [1, 2], ('407', '400', '53')),
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
                        if speed is not None:
                            self.assertEqual(api['343']['inputs']['strength_model'], speed)
                        active_loras = {key for key, node in api.items() if node['class_type'] == 'LoraLoaderModelOnly'}
                        self.assertEqual(active_loras, set(chain))
                        for target, source in zip(('331', *chain[:-1]), chain, strict=True):
                            self.assertEqual(api[target]['inputs']['model'], [source, 0])
                        canvas = json.loads((record / '任务.workflow.json').read_text())
                        nodes = {node['id']: node for node in canvas['nodes']}
                        self.assertEqual(nodes[261]['widgets_values_named']['steps'], 6 + high_steps)
                        if speed is not None:
                            self.assertEqual(nodes[343]['widgets_values_named']['strength_model'], speed)
                        self.assertEqual(nodes[343]['mode'], 4 if speed is None else 0)
                invalid_source = json.loads(plan.read_text())
                invalid_source['tasks'][0]['songssx']['configuration']['high_steps'] = 995
                (project / 'invalid-steps.json').write_text(json.dumps(invalid_source))
                invalid_payload = payload.model_copy(update={'plan_file': 'invalid-steps.json'})
                with self.assertRaisesRegex(ValueError, '高清采样步数须为 1 至 994'):
                    await submission_plans.execute(store, invalid_payload)
                self.assertFalse((project / 'invalid-steps-装配结果.json').exists())
                mistyped_options = invalid_source['tasks'][0]['songssx']
                mistyped_options['configuraton'] = mistyped_options.pop('configuration')
                mistyped_options.update(reference_image_center_crop=False, lowres_scale=.6)
                (project / 'mistyped-config.json').write_text(json.dumps(invalid_source))
                mistyped_payload = payload.model_copy(update={'plan_file': 'mistyped-config.json'})
                with self.assertRaisesRegex(ValueError, '未知 Songssx 配置字段：configuraton'):
                    await submission_plans.execute(store, mistyped_payload)
                self.assertFalse((project / 'mistyped-config-装配结果.json').exists())
                self.assertEqual(store.rows, {})
            finally:
                await store.close()
