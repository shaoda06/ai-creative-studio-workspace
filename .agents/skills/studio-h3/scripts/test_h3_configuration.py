"""Offline six-step input assembly; no server, project media or generation."""
import copy
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS.parent.parent / '工作区浏览服务'))
for name in ('studio-h3', 'studio-comfyui', 'studio-workspace-browser', 'nora-drama-production'):
    sys.path.insert(0, str(SKILLS / name / 'scripts'))
from h3_workflow import configure_first_pass, prepare_technical
from workflow_graph import Canvas
from workflow_paths import workflow_file
from prepared_documents import Documents
from drama_video_plans import build_video


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.canvas = json.loads(workflow_file('Minimax-H3-导演台-视频生成-标准版', 'workflow').read_text())
        self.choice = dict(aspect_ratio='16:9', width=1024, height=576, steps=8,
                           scene_type='dialogue', speed=3.0, loras=[])

    def test_six_answers_reach_both_output_branches(self):
        for portrait, combat, loras in itertools.product((False, True), (False, True), ([], [1], [2], [1, 2])):
            with self.subTest(portrait=portrait, combat=combat, loras=loras):
                canvas = copy.deepcopy(self.canvas)
                choice = {**self.choice, 'aspect_ratio': '9:16' if portrait else '16:9',
                          'width': 576 if portrait else 1024, 'height': 1024 if portrait else 576,
                          'scene_type': 'combat' if combat else 'dialogue',
                          'speed': 4.0 if combat else 3.0, 'loras': loras}
                configure_first_pass(canvas, dict(task_type='video-first-pass', h3_first_pass=choice))
                for output in (504, 506):
                    api = Canvas(canvas).api(output)
                    director = api['502']['inputs']
                    timeline = json.loads(director['timeline_data'])
                    for dimensions in (director, timeline, timeline['output']):
                        self.assertEqual((dimensions['width'], dimensions['height']), (choice['width'], choice['height']))
                    self.assertEqual(timeline['output']['mode'], 'fixed')
                    self.assertEqual(timeline['output']['longEdge'], 1024)
                    self.assertEqual(timeline['output']['megapixels'], .5625)
                    self.assertEqual(api['261']['inputs']['steps'], 14 if combat else 12)
                    self.assertEqual(api['289']['inputs']['step'], 8)
                    self.assertEqual(director['sigmas'], ['289', 0])
                    self.assertEqual(api['407']['inputs']['sigmas'], ['289', 1])
                    self.assertTrue(api['407']['inputs']['confirm_first_pass'])
                    chain = [53] + ([128] if 1 in loras else []) + ([507] if 2 in loras else []) + ([342, 344, 345] if combat else []) + [343]
                    for parent, child in zip([331, *chain], [*chain, 405]):
                        self.assertEqual(api[str(child)]['inputs']['model'], [str(parent), 0])
                    for node, active, weight in ((128, 1 in loras, .5), (507, 2 in loras, .8), (342, combat, .65), (344, combat, .35), (345, combat, .35)):
                        self.assertEqual(str(node) in api, active)
                        if active:
                            self.assertEqual(api[str(node)]['inputs']['strength_model'], weight)
                    self.assertEqual(api['343']['inputs']['strength_model'], choice['speed'])

    def test_custom_values_override_presets_without_changing_content_or_timing(self):
        original = next(n for n in self.canvas['nodes'] if n['id'] == 502)['widgets_values_named']
        before = json.loads(original['timeline_data'])
        choice = dict(aspect_ratio='1:1', width=768, height=768, steps=12,
                      scene_type='combat', speed=-1.5, loras=[2])
        record = configure_first_pass(self.canvas, dict(task_type='video-first-pass', h3_first_pass=choice))
        api = Canvas(self.canvas).api([403, 504, 506])
        director = api['502']['inputs']
        timeline = json.loads(director['timeline_data'])
        self.assertEqual((director['width'], director['height'], director['steps']), (768, 768, 12))
        self.assertEqual(timeline['output']['aspectRatio'], '1:1')
        self.assertEqual((api['261']['inputs']['steps'], api['289']['inputs']['step']), (18, 12))
        self.assertEqual(record['sampling']['first_pass_with_zero'], 13)
        self.assertEqual(api['343']['inputs']['strength_model'], -1.5)
        self.assertNotIn('128', api)
        self.assertEqual(api['507']['inputs']['strength_model'], .8)
        self.assertEqual(api['407']['inputs']['width'], api['407']['inputs']['height'])
        for key in ('global', 'segments', 'batchWorkspaces', 'runSelection', 'totalFrames'):
            self.assertEqual(timeline[key], before[key])
        self.assertEqual(director['seed'], original['seed'])
        self.assertEqual(director['cache_name'], original['cache_name'])

    def test_invalid_answers_and_later_stages_fail_before_mutation(self):
        cases = [dict(width=1000), dict(width=1024, height=1024), dict(steps=0),
                 dict(steps=2.5), dict(speed=11), dict(speed=float('nan')),
                 dict(loras=[0, 1]), dict(loras=[3]), dict(loras=[1, 1]),
                 dict(aspect_ratio='0:9'), dict(scene_type='unknown')]
        for change in cases:
            with self.subTest(change=change):
                canvas = copy.deepcopy(self.canvas)
                with self.assertRaises(ValueError):
                    configure_first_pass(canvas, dict(task_type='video-first-pass', h3_first_pass={**self.choice, **change}))
                self.assertEqual(canvas, self.canvas)
        for stage in ('video-second-pass', 'video-postprocess'):
            with self.assertRaisesRegex(ValueError, '仅用于新一采'):
                configure_first_pass(self.canvas, dict(task_type=stage, h3_first_pass=self.choice))

    def test_real_technical_and_drama_preparation_use_shared_configuration(self):
        for adapter in ('technical', 'drama'):
            with self.subTest(adapter=adapter), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                source = root / 'content.workflow.json'
                original = json.dumps(self.canvas, ensure_ascii=False)
                source.write_text(original)
                documents = Documents(root)
                choice = {**self.choice, 'steps': 10, 'speed': 4.0, 'loras': [1, 2]}
                spec = dict(task_type='video-first-pass', title='isolated assembly test',
                            canvas=source.name, record_dir='execution', output_nodes=[403, 504, 506],
                            h3_first_pass=choice, video_plan={'adapter': 'technical'},
                            segment_plan={'targets': []}, mapping={'scene': 'EP001-C001',
                            'selected_indices': [0], 'segments': [{'segment': 'EP001-C001-P001', 'round': 'R001'}]})
                if adapter == 'technical':
                    result = prepare_technical(root, spec, documents)
                else:
                    with patch('drama_video_records.prepare_records'):
                        result = build_video(root, spec, documents)
                    mapping = json.loads(documents.read(root / 'execution/输入映射.json'))
                    self.assertEqual(mapping['baseline']['fixed_configuration']['sampling']['total_steps'], 14)
                self.assertEqual(result['workflow']['261']['inputs']['steps'], 14)
                self.assertEqual(result['workflow']['343']['inputs']['strength_model'], 4.0)
                self.assertEqual(result['workflow']['507']['inputs']['model'], ['128', 0])
                saved = json.loads(documents.read(root / 'execution/任务.api.json'))
                self.assertEqual(saved['289']['inputs']['step'], 10)
                self.assertEqual(source.read_text(), original)
                self.assertFalse((root / 'execution').exists())

    def test_absent_field_preserves_existing_second_pass_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            nodes = {n['id']: n for n in self.canvas['nodes']}
            nodes[343]['widgets_values_named']['strength_model'] = 2.25
            nodes[343]['widgets_values'] = list(nodes[343]['widgets_values_named'].values())
            (root / 'source.json').write_text(json.dumps(self.canvas))
            result = prepare_technical(root, dict(canvas='source.json', record_dir='execution',
                task_type='video-second-pass', title='resume', output_nodes=[506],
                video_plan={'adapter': 'technical'}), Documents(root))
            self.assertEqual(result['workflow']['343']['inputs']['strength_model'], 2.25)


if __name__ == '__main__':
    unittest.main()
