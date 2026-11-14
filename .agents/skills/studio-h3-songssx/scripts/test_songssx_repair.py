import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

import songssx_repair as repair
from songssx_repair import execution_records, resources
from songssx_browser import playback_video


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), '需要 FFmpeg 和 ffprobe')
class SongssxRepairTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        resources.initialize(self.project, managed=True)
        self.production = self.project / '06-视频生产'
        self.original = self.task('R005', 'red', 192, 8)
        self.patch = self.task('R006', 'blue', 107, 4)

    def task(self, run, color, frames, requested, gap=False):
        raw = self.root / (run + '.mp4')
        repair.ffmpeg('-f', 'lavfi', '-i', f'color={color}:s=96x64:r=24',
                      '-f', 'lavfi', '-i', 'sine=frequency=660:sample_rate=32000',
                      '-t', f'{frames / 24:.8f}', '-c:v', 'libx264', '-c:a', 'aac', raw)
        directory = self.production / run
        key = directory.relative_to(self.project).as_posix()
        ref = resources.register(self.project, raw, producer=key)
        plan = {'workflow_id': repair.WORKFLOW, 'segments': [
            {'p': 'P001', 'planned_seconds': requested, 'output_frames': [0, frames]},
        ]}
        if gap:
            plan['gap_repair'] = {'replacement_frames': requested * 24}
        execution_records.write_entries(directory, {
            '执行检查报告.json': {'ok': True, 'prepared_input': {
                'task_type': repair.TASK_TYPE, 'record_dir': key,
                'video_plan': plan, 'outputs': [{'path': ref['file']}]},
            },
            '后台任务状态.json': {'id': run, 'status': 'completed'},
            '结果收尾报告.json': {'task_id': run, 'adapter': 'technical', 'status': 'registered',
                           'items': [{'path': ref['file'], 'technical': True}]},
        })
        return ref

    def plan(self, nora=False):
        index = self.production / ('EP001-修改轮次.json' if nora else '制作轮次.json')
        round_record = {'segments': [{'id': 'P001', 'duration': 8, 'file': self.original['file']}],
                        'review_outputs': [{'label': '局部试片', 'file': self.patch['file']}]}
        scene = 'C001' if nora else 'S001'
        if nora:
            round_record['songssx_execution'] = self.original['producer']
            row = {'number': 6, 'scenes': {scene: round_record}}
        else:
            plan = self.production / '分镜.md'
            plan.write_text('| 生成段 | 场次 |\n| --- | --- |\n| P001 | S001 |\n', 'utf-8')
            round_record.update(batches=['R005'], storyboard={'file': str(plan)})
            row = {'number': 6, **round_record}
        before = {'number': 5, 'segments': round_record['segments']}
        repair.write_json(index, {'rounds': [before, row]})
        return index, {
            'source': self.original['file'], 'record_dir': self.patch['producer'],
            'round_index': index.relative_to(self.project).as_posix(),
            'round': 6, 'scene': scene, 'run': 'R006', 'frames': [48, 144],
            'audio': 'replacement', 'fit': 'retime',
        }, before

    def color_at(self, path, frame):
        raw = subprocess.run([
            'ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'select=eq(n\\,{frame}),scale=1:1',
            '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-',
        ], check=True, capture_output=True).stdout
        return 'red' if raw[0] > raw[2] else 'blue'

    def test_retime_middle_with_audio_register_and_retry(self):
        self.patch = self.task('R008', 'blue', 107, 4, gap=True)
        index, plan, before = self.plan()
        plan['run'] = 'R008'
        output = repair.repair(self.project, plan)
        path = self.project / output['file']
        self.assertEqual([self.color_at(path, frame) for frame in (47, 48, 143, 144)],
                         ['red', 'blue', 'blue', 'red'])
        rows = json.loads(index.read_text('utf-8'))['rounds']
        self.assertEqual(rows[0], before)
        self.assertEqual(rows[1]['segments'], before['segments'])
        self.assertEqual(rows[1]['review_outputs'][0]['file'], self.patch['file'])
        self.assertEqual(repair.scene_playbacks(rows[1]['review_outputs'])['S001']['file'], output['file'])
        actual = playback_video(self.project, rows[1]['review_outputs'][1])
        self.assertEqual((actual['key'], actual['run']), (output['file'], 'R008'))
        self.assertEqual(resources.reference(self.project, path)['parent']['file'], self.original['file'])
        self.assertEqual(repair.repair(self.project, plan), output)
        with self.assertRaisesRegex(ValueError, '已有不同的接回记录'):
            repair.repair(self.project, {**plan, 'frames': [49, 145]})

    def test_exact_tail_and_nora_scene_preserve_source_audio(self):
        index, plan, before = self.plan(nora=True)
        output = repair.repair(self.project, {
            **plan, 'frames': [96, 192], 'clip_frames': [0, 96], 'fit': 'exact', 'audio': 'source',
        })
        rows = json.loads(index.read_text('utf-8'))['rounds']
        self.assertEqual(rows[0], before)
        selected = repair.scene_playbacks(rows[1]['scenes']['C001']['review_outputs'])['C001']
        self.assertEqual(selected['file'], output['file'])
        self.assertEqual(self.color_at(self.project / output['file'], 191), 'blue')
        def audio(path):
            return subprocess.run(['ffmpeg', '-v', 'error', '-i', str(self.project / path),
                                   '-map', '0:a:0', '-c', 'copy', '-f', 'adts', '-'],
                                  check=True, capture_output=True).stdout
        self.assertEqual(audio(output['file']), audio(self.original['file']))

    def test_reject_wrong_scene_or_missing_timing_decision(self):
        index, plan, _ = self.plan()
        snapshot = index.read_bytes()
        with self.assertRaisesRegex(ValueError, '不属于本轮指定的场次'):
            repair.repair(self.project, {**plan, 'scene': 'S002'})
        with self.assertRaisesRegex(ValueError, '请明确选帧'):
            repair.repair(self.project, {**plan, 'fit': 'exact'})
        self.assertEqual(index.read_bytes(), snapshot)
        self.assertFalse((self.project / self.patch['producer'] / '局部返修接回.json').exists())


if __name__ == '__main__':
    unittest.main()
