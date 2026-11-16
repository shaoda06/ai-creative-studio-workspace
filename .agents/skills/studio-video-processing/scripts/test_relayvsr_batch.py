"""Exercise exact local cuts, one task group, and ordered assembly with offline fixtures."""
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from relayvsr_batch import ffmpeg, join, media, prepare, save_json
from test_video_workflow import Canvas, Documents, prepare_technical


def frame_hashes(path):
    result = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-map',
                                      '0:v:0', '-f', 'framemd5', '-'])
    return [line.rsplit(b',', 1)[-1].strip() for line in result.splitlines() if not line.startswith(b'#')]


class RelayVSRBatchTests(unittest.TestCase):
    def test_group_with_exact_split_and_rife_after_join(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / '源视频.mp4'
            ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=64x36:r=24:d=84',
                   '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=32000:duration=84',
                   '-c:v', 'libx264', '-g', '91', '-sc_threshold', '0', '-c:a', 'aac', source)
            record = root / 'relay'
            result = prepare(root, source, record, root / '最终.mp4', '隔离验证', fps=60)
            self.assertEqual(result['tasks'], 9)
            group = json.loads((record / '任务清单.json').read_text(encoding='utf-8'))
            schedule = json.loads((record / '分段计划.json').read_text(encoding='utf-8'))
            self.assertEqual([segment['frames'] for segment in schedule['segments']], [240] * 8 + [96])
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
                save_json(path.parent / '结果收尾报告.json', {'items': [{
                    'identity': path.name, 'path': path.relative_to(root).as_posix()}]})
            self.assertEqual(samples, frame_hashes(source))
            self.assertEqual(join(root, record)['frames'], 2016)
            video, audio = media(record / '超分合片.mp4', count=True)
            self.assertEqual((video['nb_read_frames'], video['duration'], audio[0]['codec_name']), ('2016', '84.000000', 'aac'))
            stage = json.loads((record / '插帧任务清单.json').read_text(encoding='utf-8'))['tasks'][0]
            stage_request = prepare_technical(root, stage, Documents(root))
            self.assertEqual(stage_request['workflow']['12']['inputs']['target_fps'], 60)
            self.assertNotIn('1', stage_request['workflow'])
            self.assertEqual(stage_request['workflow']['16']['inputs']['audio'], ['7', 1])

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
                    'identity': result.name, 'path': result.relative_to(root).as_posix()}]})
            self.assertEqual(join(root, record)['frames'], 350)
            merged, _ = media(root / 'output.mp4', count=True)
            self.assertEqual(Fraction(merged['avg_frame_rate']), Fraction(30000, 1001))


if __name__ == '__main__':
    unittest.main()
