"""Offline output planning and real task-adapter exports; no remote submission."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS.parent.parent / '工作区浏览服务'))
for name in ('studio-h3', 'studio-h3-aimixer', 'studio-comfyui', 'studio-workspace-browser', 'nora-drama-production'):
    sys.path.insert(0, str(SKILLS / name / 'scripts'))
from video_workflow import plan_output, questions, assemble_output
from video_metadata import probe
from workflow_graph import Canvas
from h3_workflow import prepare_technical
from drama_video_plans import build_video
from prepared_documents import Documents


class OutputTests(unittest.TestCase):
    def meta(self, w=1920, h=1088, fps=24):
        return dict(width=w, height=h, frame_rate=fps)

    def api(self, meta, size, fps, fit=None):
        return Canvas(assemble_output('planned/video.mp4', 'isolated', plan_output(meta, size, fps, fit))).api('16')

    def test_dynamic_options_and_ratio_condition(self):
        q = questions(self.meta(), [1920, 1080])
        self.assertIn('1920×1088', q[0]['options'][0])
        self.assertIn('24fps', q[1]['options'][0])
        self.assertEqual(q[2]['options'], ['保留比例（输出1906×1080）', '裁切至1920×1080（上下各裁4像素）'])
        self.assertEqual(len(questions(self.meta(1536, 864), [1920, 1080])), 2)
        self.assertEqual(len(questions(self.meta(), 'original')), 2)
        self.assertIn('左右各裁4像素', questions(self.meta(1088, 1920), [1080, 1920])[2]['options'][1])
        self.assertIn('先缩放至1920×1440，', questions(self.meta(640, 480), [1920, 1080])[2]['options'][1])

    def test_same_size_fps_reuses_source_and_unchanged_rate_skips_rife(self):
        self.assertIsNone(assemble_output('source', 'out', plan_output(self.meta(), 'original', 'original')))
        api = self.api(self.meta(), [1920, 1080], 'original', 'crop')
        self.assertNotIn('12', api)
        self.assertNotIn('1', api)
        self.assertEqual(api['16']['inputs']['frame_rate'], ['7', 2])
        self.assertEqual(api['25']['inputs']['y'], 4)

    def test_fps_only_preserves_dimensions_audio_and_uses_actual_fps(self):
        api = self.api(self.meta(), 'original', 60)
        self.assertNotIn('1', api)
        self.assertNotIn('25', api)
        self.assertEqual(api['12']['inputs']['target_fps'], 60)
        self.assertEqual(api['12']['inputs']['source_fps'], ['7', 2])
        self.assertEqual(api['16']['inputs']['images'], ['12', 0])
        self.assertEqual(api['16']['inputs']['frame_rate'], ['12', 1])
        self.assertEqual(api['16']['inputs']['audio'], ['7', 1])
        self.assertFalse(api['16']['inputs']['trim_to_audio'])

    def test_resize_then_crop_in_both_directions(self):
        for source, target, offset in [((640, 480), [1920, 1080], (0, 180)), ((480, 640), [1080, 1920], (180, 0))]:
            api = self.api(self.meta(*source), target, 30, 'crop')
            self.assertEqual(api['1']['class_type'], 'RTXVideoSuperResolution')
            self.assertEqual(api['25']['inputs']['image'], ['1', 0])
            self.assertEqual((api['25']['inputs']['x'], api['25']['inputs']['y']), offset)
            self.assertEqual(api['16']['inputs']['images'], ['25', 0])
        api = self.api(self.meta(3840, 2160), [1920, 1080], 'original')
        self.assertEqual(api['1']['class_type'], 'ImageScale')
        self.assertEqual(api['1']['inputs']['crop'], 'disabled')
        self.assertEqual(api['16']['inputs']['frame_rate'], ['7', 2])
        self.assertNotIn('25', api)
        api = self.api(self.meta(), [1920, 1080], 30, 'contain')
        self.assertEqual((api['1']['inputs']['width'], api['1']['inputs']['height']), (1906, 1080))

    def test_invalid_inputs_do_not_silently_crop_or_round(self):
        for size, fps, fit in [([1920, 1080], 30, None), ([1919, 1080], 30, 'contain'),
                               ([1920, 1080], 0, 'crop'), ([1920, 1080], float('nan'), 'crop'),
                               ([1920, 1080], 241, 'crop'), ([1920, 1080], 30, 'stretch')]:
            with self.subTest(size=size, fps=fps, fit=fit), self.assertRaises(ValueError):
                plan_output(self.meta(), size, fps, fit)

    def test_actual_probe_and_both_task_adapters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'video.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=64x36:r=24:d=0.5',
                            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source)], check=True)
            facts = probe(source)
            self.assertEqual((facts['width'], facts['height'], facts['frame_rate']), (64, 36, 24))
            before = source.read_bytes()
            for adapter in ('technical', 'drama'):
                documents = Documents(root)
                spec = dict(task_type='video-postprocess', title='isolated', record_dir=adapter, output_nodes=['16'],
                    video_plan={'adapter': 'technical'}, references=[dict(file=source.name, placeholder='planned/video.mp4')],
                    video_postprocess=dict(source=source.name, resolution=[128, 72], fps='original'),
                    mapping={'scene': 'EP001-C001', 'selected_indices': [0],
                             'segments': [{'segment': 'EP001-C001-P001', 'round': 'R001'}]})
                if adapter == 'technical':
                    result = prepare_technical(root, spec, documents)
                else:
                    with patch('drama_video_records.prepare_records'):
                        result = build_video(root, spec, documents)
                    saved = json.loads(documents.read(root / adapter / '输入映射.json'))
                    self.assertEqual(saved['postprocess_configuration']['output_size'], [128, 72])
                api = result['workflow']
                self.assertEqual(api['1']['inputs']['resize_type.width'], 128)
                self.assertEqual(api['16']['inputs']['frame_rate'], ['7', 2])
                self.assertEqual(api['6']['inputs']['file'], 'planned/video.mp4')
                self.assertTrue(result['uploads'])
                self.assertEqual(source.read_bytes(), before)
                self.assertFalse((root / adapter).exists())
            spec['video_postprocess'].update(resolution='original', fps='original')
            with self.assertRaisesRegex(ValueError, '无需提交'):
                prepare_technical(root, spec, Documents(root))


if __name__ == '__main__':
    unittest.main()
