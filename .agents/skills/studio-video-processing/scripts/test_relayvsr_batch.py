"""Exercise exact local cuts, one task group, and ordered assembly with offline fixtures."""
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import relayvsr_batch
from relayvsr_batch import ffmpeg, join, media, prepare, prepare_after_rife, save_json
from test_video_workflow import Canvas, Documents, prepare_technical
from execution_records import write
from video_metadata import probe


def frame_hashes(path):
    result = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-map',
                                      '0:v:0', '-f', 'framemd5', '-'])
    return [line.rsplit(b',', 1)[-1].strip() for line in result.splitlines() if not line.startswith(b'#')]


class RelayVSRBatchTests(unittest.TestCase):
    def test_rife_first_then_split_join_and_restore_original_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / '源视频.mp4'
            ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=64x36:r=24:d=84',
                   '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=32000:duration=84',
                   '-c:v', 'libx264', '-g', '91', '-sc_threshold', '0', '-c:a', 'aac', source)
            record = root / 'relay'
            target = root / '最终.mp4'
            first = prepare(root, source, record, target, '隔离验证', fps=30)
            self.assertEqual((first['stage'], first['tasks']), ('rife', 1))
            self.assertFalse((record / '超分分段').exists())
            stage = json.loads((root / first['plan']).read_text(encoding='utf-8'))['tasks'][0]
            stage_request = prepare_technical(root, stage, Documents(root))
            self.assertEqual(stage_request['workflow']['12']['inputs']['target_fps'], 30)
            self.assertNotIn('1', stage_request['workflow'])
            self.assertEqual(stage_request['uploads'][0]['file'], str(source))
            report_path = root / stage['record_dir'] / '结果收尾报告.json'
            with self.assertRaises(FileNotFoundError):
                prepare_after_rife(root, record)
            self.assertFalse((record / '超分分段').exists())
            intermediate = root / stage['outputs'][0]['path']
            write(report_path, {'items': [{
                'identity': intermediate.name, 'path': source.name, 'metadata': probe(source)}]}, compact=True)
            with self.assertRaisesRegex(ValueError, '帧率或时长'):
                prepare_after_rife(root, record)
            self.assertFalse((record / '超分分段').exists())
            ffmpeg('-i', source, '-vf', 'fps=30', '-c:v', 'libx264', '-g', '91', '-sc_threshold', '0',
                   '-an', intermediate)
            write(report_path, {'items': [{
                'identity': intermediate.name, 'path': intermediate.relative_to(root).as_posix(),
                'metadata': probe(intermediate)}]}, compact=True)
            result = prepare_after_rife(root, record)
            self.assertEqual(result['tasks'], 9)
            group = json.loads((root / result['plan']).read_text(encoding='utf-8'))
            split = record / '超分分段'
            schedule = json.loads((split / '分段计划.json').read_text(encoding='utf-8'))
            self.assertEqual([segment['frames'] for segment in schedule['segments']], [300] * 8 + [120])
            self.assertEqual(schedule['source'], source.name)
            self.assertEqual(schedule['picture_source'], intermediate.relative_to(root).as_posix())
            samples = []
            for spec in group['tasks']:
                clip = root / spec['references'][0]['file']
                samples.extend(frame_hashes(clip))
                request = prepare_technical(root, spec, Documents(root))
                self.assertEqual(request['workflow']['104']['inputs']['detail'], 0.5)
                self.assertEqual(request['uploads'][0]['node'], '1')
                self.assertNotIn('12', request['workflow'])
                path = root / spec['outputs'][0]['path']
                ffmpeg('-i', clip, '-vf', 'scale=128:72', '-c:v', 'libx264', path)
                write(path.parent / '结果收尾报告.json', {'items': [{
                    'identity': path.name, 'path': path.relative_to(root).as_posix(), 'metadata': probe(path)}]},
                      compact=True)
            self.assertEqual(samples, frame_hashes(intermediate))
            original = path.stat()
            os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns + 10**9))
            with self.assertRaisesRegex(ValueError, '取回文件已变化'):
                join(root, split)
            self.assertFalse(target.exists())
            os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
            self.assertEqual(join(root, split)['frames'], 2520)
            video, audio = media(target, count=True)
            self.assertEqual((video['nb_read_frames'], video['duration'], audio[0]['codec_name']), ('2520', '84.000000', 'aac'))

    def test_fractional_fps_cuts_without_rounding_past_ten_seconds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'video.mp4'
            ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=64x36:r=30000/1001', '-frames:v', '350',
                   '-c:v', 'libx264', '-g', '89', '-sc_threshold', '0', source)
            record = root / 'relay'
            prepare(root, source, record, root / 'output.mp4', '隔离验证')
            split = json.loads((record / '分段计划.json').read_text(encoding='utf-8'))
            self.assertEqual(Fraction(split['fps']), Fraction(30000, 1001))
            self.assertEqual([segment['frames'] for segment in split['segments']], [299, 51])
            frames = [frame for item in split['segments'] for frame in frame_hashes(root / item['record_dir'] / '源片.mp4')]
            self.assertEqual(frames, frame_hashes(source))
            self.assertFalse((record / '插帧任务清单.json').exists())
            for item in split['segments']:
                folder = root / item['record_dir']
                result = folder / item['result']
                ffmpeg('-i', folder / '源片.mp4', '-vf', 'scale=128:72', '-c:v', 'libx264', result)
                save_json(folder / '结果收尾报告.json', {'items': [{
                    'identity': result.name, 'path': result.relative_to(root).as_posix(), 'metadata': probe(result)}]})
            self.assertEqual(join(root, record)['frames'], 350)
            merged, _ = media(root / 'output.mp4', count=True)
            self.assertEqual(Fraction(merged['avg_frame_rate']), Fraction(30000, 1001))

    def test_conflicting_output_and_changed_source_cannot_publish_a_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'video.mp4'
            ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=64x36:r=24', '-frames:v', '241',
                   '-c:v', 'libx264', source)
            record = root / 'relay'
            target = root / 'output.mp4'
            with self.assertRaisesRegex(ValueError, '补帧中间片同名'):
                prepare(root, source, record, record / '整条插帧/补帧中间片.mp4', '隔离验证', fps=60)
            with self.assertRaisesRegex(ValueError, '分段文件同名'):
                prepare(root, source, record, record / '分段-001/源片.mp4', '隔离验证')
            self.assertFalse(record.exists())
            original_trim = relayvsr_batch.trim

            def change_source(*args):
                original_trim(*args)
                current = source.stat()
                os.utime(source, ns=(current.st_atime_ns, current.st_mtime_ns + 10**9))

            with patch.object(relayvsr_batch, 'trim', side_effect=change_source):
                with self.assertRaisesRegex(ValueError, '裁剪期间源片已变化'):
                    prepare(root, source, record, target, '隔离验证')
            self.assertFalse(record.exists())
            self.assertEqual(prepare(root, source, record, target, '隔离验证')['tasks'], 2)
            self.assertEqual(frame_hashes(record / '分段-002/源片.mp4'), frame_hashes(source)[-1:])


if __name__ == '__main__':
    unittest.main()
