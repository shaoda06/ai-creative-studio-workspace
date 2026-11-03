"""Project resource families, immutable references and uploads in temporary projects."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.agents/skills/studio-workspace-browser/scripts'))
import project_resources as resources
from media_files import store_media


class ProjectResourcesTests(unittest.TestCase):
    def test_old_alias_never_rebinds_to_a_later_task(self):
        ref = resources.reserve(self.project, '候选/同名.png', key='task-1', producer='执行附件/1')
        with self.assertRaisesRegex(ValueError, '历史地址已绑定'):
            resources.reserve(self.project, '候选/同名.png', key='task-2', producer='执行附件/2')
        self.assertEqual(resources.reference(self.project, '候选/同名.png'), ref)
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / '项目'
        self.project.mkdir()
        self.source = self.root / '用户原件.png'
        self.png(self.source, 'red')

    def png(self, path, color):
        stream = BytesIO()
        Image.new('RGB', (12, 8), color).save(stream, format='PNG')
        path.write_bytes(stream.getvalue())

    def test_uploads_and_revisions_keep_one_family_and_exact_old_version(self):
        mode = self.source.stat().st_mode
        first = resources.register(self.project, self.source, key='upload-1', name='人物三视图')
        repeated = resources.register(self.project, self.source, key='upload-1')
        self.assertEqual(first, repeated)
        changed = self.root / '修改1.png'
        self.png(changed, 'blue')
        second = resources.register(self.project, changed, resource_id=first['resource_id'],
                                    key='edit-1', origin='process', parent=first['file'])
        self.assertEqual(second['resource_id'], first['resource_id'])
        self.assertEqual([first['version'], second['version']], ['V001', 'V002'])
        self.assertEqual(second['parent']['version'], 'V001')
        self.assertEqual(resources.version_file(self.project, first['resource_id'], 'V001').read_bytes(), self.source.read_bytes())
        self.assertEqual(self.source.stat().st_mode, mode)
        self.assertFalse((self.project / first['file']).samefile(self.source))
        self.assertEqual(len(resources.catalog(self.project)), 1)
        self.assertEqual(len(resources.catalog(self.project)[0]['versions']), 2)
        self.assertEqual(resources.read_index(self.project)['aliases'], {})

    def test_existing_resource_version_cannot_be_replaced_even_with_replace_flag(self):
        first = resources.register(self.project, self.source, key='upload')
        other = self.root / 'different.png'
        self.png(other, 'blue')
        with self.assertRaisesRegex(ValueError, '不可覆盖'):
            store_media(self.project, self.project / first['file'], other.read_bytes(), replace=True)
        self.assertEqual((self.project / first['file']).read_bytes(), self.source.read_bytes())
        with self.assertRaisesRegex(ValueError, '不可覆盖'):
            resources.register(self.project, other, key='upload')

    def test_separate_uploads_with_same_name_are_not_assumed_to_be_same_target(self):
        first = resources.register(self.project, self.source, key='u1')
        second = resources.register(self.project, self.source, key='u2')
        self.assertNotEqual(first['resource_id'], second['resource_id'])
        self.assertEqual((self.project / second['file']).read_bytes(), self.source.read_bytes())

    def test_parallel_results_receive_distinct_versions_but_retry_keeps_identity(self):
        resources.initialize(self.project)
        def reserve(index):
            return resources.reserve(self.project, f'候选/结果{index}.png', family='图片/同一目标', key=f'task/{index}')
        with ThreadPoolExecutor(max_workers=4) as workers:
            refs = list(workers.map(reserve, range(12)))
        self.assertEqual(len({ref['resource_id'] for ref in refs}), 1)
        self.assertEqual(len({ref['version'] for ref in refs}), 12)
        self.assertEqual(reserve(3), refs[3])
        self.assertEqual(resources.catalog(self.project), [])

    def test_parallel_finishes_share_only_byte_identical_outputs(self):
        refs = [resources.reserve(self.project, f'候选/结果{index}.png', key=f'task/{index}',
                                  family='图片/同一目标', producer=f'执行附件/{index}') for index in range(3)]
        paths = [self.project / ref['file'] for ref in refs]
        for path, data in zip(paths, (b'first', b'first', b'other')):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        def finish(path):
            return resources.finish(self.project, path, info={'bytes': 5}, share=True)

        with ThreadPoolExecutor(max_workers=3) as workers:
            self.assertEqual(list(workers.map(finish, paths)), refs)
        self.assertTrue(paths[0].samefile(paths[1]))
        self.assertFalse(paths[0].samefile(paths[2]))
        self.assertEqual([path.read_bytes() for path in paths], [b'first', b'first', b'other'])
        self.assertTrue(all(not path.stat().st_mode & 0o222 for path in paths))
        versions = resources.catalog(self.project)[0]['versions']
        self.assertEqual([item['producer'] for item in versions], [ref['producer'] for ref in refs])

    def test_reference_audio_is_an_import_and_extraction_can_link_to_other_media(self):
        source = self.root / '参考原声.wav'
        with wave.open(str(source), 'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
            audio.writeframes(b'\0\0' * 1600)
        ref = resources.register(self.project, source, key='audio-upload')
        self.assertEqual(ref['kind'], '音频')
        metadata = json.loads((self.project / ref['file']).with_name('版本信息.json').read_text())
        self.assertEqual(metadata['origin'], 'user_upload')
        self.assertAlmostEqual(metadata['facts']['duration_seconds'], .1)
        self.assertIsNone(metadata['producer'])
        self.assertNotIn('model', metadata)

    def test_project_boundary_and_resource_kind_are_checked_at_import(self):
        first = resources.register(self.project, self.source, key='upload')
        with self.assertRaisesRegex(ValueError, '越出'):
            resources.reserve(self.project, '../outside.png')
        with self.assertRaisesRegex(ValueError, '没有这个资源'):
            resources.reserve(self.project, 'new.png', resource_id='IMG-absent')
        with self.assertRaisesRegex(ValueError, '不同媒体类型'):
            resources.reserve(self.project, 'new.wav', resource_id=first['resource_id'])
        self.assertEqual(resources.reference(self.project, first['file']), first)
