"""Isolated end-to-end checks for Chloe initialization and exact shared inputs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
import chloe_resources as chloe
from chloe_init import initialize_workspace, initialize_video, initialize_asset


class ChloeResourcesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = initialize_workspace(self.base / 'Chloe Workspace')
        self.one = initialize_video(self.root, 'V001', '商品-细节')
        self.two = initialize_video(self.root, 'V002', '商品-场景')
        self.source = self.base / 'source.png'
        Image.new('RGB', (16, 24), 'red').save(self.source)

    def add(self, key='upload/one', **kwargs):
        return chloe.import_media(self.root, self.source, key, **kwargs)

    def test_fixed_skeleton_and_idempotent_initialization(self):
        for kind in ('图片', '视频', '音频'):
            self.assertTrue((self.root / '综合资料/资源' / kind).is_dir())
            self.assertTrue((self.one / '资源' / kind).is_dir())
        for directory in ('商品资料', '共用素材/AI模特', '共用素材/服装', '共用素材/造型', '共用素材/场景', '共用素材/声音'):
            self.assertTrue((self.root / '综合资料' / directory).is_dir())
        self.assertTrue((self.one / '成片').is_dir())
        self.assertTrue((self.one / '剪辑交接').is_dir())
        for kind, identity in [('商品', 'G001'), ('模特', 'M001'), ('服装', 'O001'), ('造型', 'L001'), ('场景', 'S001'), ('声音', 'A001')]:
            asset = initialize_asset(self.root, kind, identity, '测试')
            self.assertEqual(len(list(asset.iterdir())), 1)
        ref = self.add()
        chloe.bind_reference(self.root, self.one.name, 'shot/1', ref['resource_id'], ref['version'])
        saved = (self.one / '资源/共用引用.json').read_bytes()
        (self.one / 'README.md').write_text('用户已修改', encoding='utf-8')
        initialize_workspace(self.root)
        initialize_video(self.root, 'V001', '商品-细节')
        self.assertEqual((self.one / 'README.md').read_text(), '用户已修改')
        self.assertEqual((self.one / '资源/共用引用.json').read_bytes(), saved)
        self.assertEqual(len(chloe.resources.catalog(self.root / '综合资料')), 1)
        with self.assertRaises(ValueError):
            initialize_video(self.root, 'V001', '不同名称')
        self.assertEqual(len(list(self.root.rglob('账号运营配置.md'))), 0)
        self.assertFalse(any('{{' in p.read_text() for p in self.root.rglob('*.md')))

    def test_shared_version_reused_by_two_videos_and_old_inputs_stable(self):
        first = self.add()
        for video in (self.one, self.two):
            chloe.bind_reference(self.root, video.name, 'task/first/model', first['resource_id'], first['version'])
            self.assertEqual(chloe.resolve_reference(self.root, video.name, 'task/first/model'), Path(first['absolute_file']))
            self.assertEqual(list(video.rglob('*.png')), [])
        original = Path(first['absolute_file']).read_bytes()
        Image.new('RGB', (16, 24), 'blue').save(self.source)
        second = self.add('upload/revision', resource_id=first['resource_id'])
        self.assertNotEqual(first['version'], second['version'])
        self.assertEqual(Path(first['absolute_file']).read_bytes(), original)
        for video in (self.one, self.two):
            self.assertEqual(chloe.resolve_reference(self.root, video.name, 'task/first/model'), Path(first['absolute_file']))
        with self.assertRaises(ValueError):
            chloe.bind_reference(self.root, self.one.name, 'task/first/model', second['resource_id'], second['version'])
        chloe.bind_reference(self.root, self.one.name, 'task/second/model', second['resource_id'], second['version'])
        self.assertEqual(chloe.resolve_reference(self.root, self.one.name, 'task/second/model'), Path(second['absolute_file']))

    def test_retry_and_independent_identical_output_keep_correct_identity(self):
        first = self.add()
        retry = self.add()
        self.assertEqual(first['file'], retry['file'])
        independent = self.add('upload/independent')
        self.assertNotEqual(first['resource_id'], independent['resource_id'])
        self.assertTrue(Path(first['absolute_file']).samefile(independent['absolute_file']))
        self.assertEqual(len(chloe.resources.catalog(self.root / '综合资料')), 2)

    def test_reimport_missing_version_and_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            self.add('')
        ref = self.add()
        with self.assertRaises(ValueError):
            chloe.import_media(self.root, ref['absolute_file'], 'duplicate', project=self.one.name)
        with self.assertRaises(FileNotFoundError):
            chloe.bind_reference(self.root, self.one.name, 'bad', ref['resource_id'], 'latest')
        with self.assertRaises(ValueError):
            chloe.bind_reference(self.root, '../综合资料', 'bad', ref['resource_id'], ref['version'])
        chloe.bind_reference(self.root, self.one.name, 'good', ref['resource_id'], ref['version'])
        path = self.one / '资源/共用引用.json'
        data = json.loads(path.read_text())
        data['references']['good']['file'] = '/tmp/unrelated.png'
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            chloe.resolve_reference(self.root, self.one.name, 'good')
        (Path(ref['absolute_file']).parent / '版本信息.json').unlink()
        with self.assertRaises(ValueError):
            chloe.bind_reference(self.root, self.two.name, 'incomplete', ref['resource_id'], ref['version'])

    def test_project_new_output_and_actual_record(self):
        with self.assertRaises(ValueError):
            self.add('task/no-record', project=self.one.name, origin='generated')
        ref = self.add('task/output', project=self.one.name, origin='generated', record='制作记录.md')
        self.assertTrue(Path(ref['absolute_file']).is_relative_to(self.one / '资源'))
        self.assertEqual(chloe.resources.catalog(self.root / '综合资料'), [])
        self.assertEqual(len(chloe.resources.catalog(self.one)), 1)

    def test_concurrent_bindings_are_not_lost(self):
        ref = self.add()
        command = [sys.executable, str(Path(chloe.__file__)), '--workspace', str(self.root), 'bind',
                   '--project', self.one.name, '--resource-id', ref['resource_id'], '--version', ref['version']]
        processes = [subprocess.Popen(command + ['--key', f'task/{i}/model'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(4)]
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(json.loads(stdout)['version'], ref['version'])
        refs = json.loads((self.one / '资源/共用引用.json').read_text())['references']
        self.assertEqual(set(refs), {f'task/{i}/model' for i in range(4)})
        self.assertEqual(list(self.one.rglob('*.png')), [])


if __name__ == '__main__':
    unittest.main()
