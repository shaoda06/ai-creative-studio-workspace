"""Snapshots keep original records and restore exact media through fixed versions."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.agents/skills/studio-workspace-browser/scripts'))
import project_resources as resources
import project_snapshot as snapshots
from media_files import store_media


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / '项目'
        self.project.mkdir()
        self.source = self.root / '原件.png'
        Image.new('RGB', (12, 8), 'red').save(self.source)
        self.ref = resources.register(self.project, self.source)
        self.document = self.project / '制作/审阅.md'
        self.document.parent.mkdir()
        self.text = '# 原意见\n\n待确认，未批准。\n\n[原图](../' + self.ref['file'] + ')\n'
        self.document.write_text(self.text)

    def test_new_snapshot_saves_record_and_version_without_media_or_nested_bundle(self):
        archive = self.project / 'native.zip'
        archive.write_bytes(b'independent native handoff')
        (self.document.parent / '执行.json').write_text(json.dumps({'file': self.ref['file']}))
        target = self.project / '历史/快照.zip'
        result = snapshots.create(self.project, target, ['制作', self.ref['file'], 'native.zip'])
        self.assertEqual(result['documents'], 2)
        with ZipFile(target) as bundle:
            self.assertEqual(bundle.read('制作/审阅.md').decode(), self.text)
            self.assertFalse(any(resources.media_kind(name) for name in bundle.namelist()))
            self.assertNotIn('native.zip', bundle.namelist())
            manifest = json.loads(bundle.read(snapshots.MANIFEST))
            self.assertEqual(manifest['media'][self.ref['file']]['version'], 'V001')
            self.assertIn('native.zip', manifest['attachments'])
        revision = self.root / '修改.png'
        Image.new('RGB', (12, 8), 'blue').save(revision)
        resources.register(self.project, revision, resource_id=self.ref['resource_id'],
                           parent=self.ref['file'], origin='process')
        restored = self.root / '恢复'
        snapshots.restore(self.project, target, restored)
        self.assertEqual((restored / self.ref['file']).read_bytes(), self.source.read_bytes())
        self.assertEqual((restored / '制作/审阅.md').read_text(), self.text)
        self.assertEqual((restored / 'native.zip').read_bytes(), archive.read_bytes())
        with self.assertRaises(FileExistsError):
            snapshots.restore(self.project, target, restored)
        with self.assertRaises(FileExistsError):
            snapshots.create(self.project, target, ['制作'])

    def test_compact_preserves_records_and_restores_media_at_original_path(self):
        target = self.project / '旧完整快照.zip'
        original = {'原目录/原图.png': self.source.read_bytes(), '旧记录.md': self.text.encode(),
                    '参数.json': b'{"original": "unchanged"}', '空目录/': b''}
        with ZipFile(target, 'w') as bundle:
            bundle.comment = b'original comment'
            for key, value in original.items():
                bundle.writestr(key, value)
        result = snapshots.compact(self.project, target, {'原目录/原图.png': self.ref['file']})
        self.assertEqual(result['media_references'], 1)
        with ZipFile(target) as bundle:
            self.assertEqual(bundle.comment, b'original comment')
            self.assertNotIn('原目录/原图.png', bundle.namelist())
            self.assertEqual(bundle.read('旧记录.md'), original['旧记录.md'])
        restored = self.root / '旧快照恢复'
        snapshots.restore(self.project, target, restored)
        for key, raw in original.items():
            if not key.endswith('/'):
                self.assertEqual((restored / key).read_bytes(), raw)
        self.assertFalse(snapshots.compact(self.project, target, {})['changed'])

    def test_compact_different_bytes_or_missing_reference_does_not_change_original(self):
        target = self.project / '旧快照.zip'
        with ZipFile(target, 'w') as bundle:
            bundle.writestr('原图.png', b'different media')
            bundle.writestr('原意见.md', self.text)
        raw = target.read_bytes()
        with self.assertRaisesRegex(ValueError, '内容不同'):
            snapshots.compact(self.project, target, {'原图.png': self.ref['file']})
        self.assertEqual(target.read_bytes(), raw)
        with self.assertRaises(KeyError):
            snapshots.compact(self.project, target, {})
        self.assertEqual(target.read_bytes(), raw)

    def test_failed_zip_validation_keeps_original_and_removes_pending_file(self):
        target = self.project / '旧快照.zip'
        with ZipFile(target, 'w') as bundle:
            bundle.writestr('原图.png', self.source.read_bytes())
        raw = target.read_bytes()
        with patch.object(ZipFile, 'testzip', return_value='坏文件'):
            with self.assertRaisesRegex(ValueError, '完整读取'):
                snapshots.compact(self.project, target, {'原图.png': self.ref['file']})
        self.assertEqual(target.read_bytes(), raw)
        self.assertEqual(sorted(p.name for p in self.project.glob('*.zip')), ['旧快照.zip'])

    def test_new_snapshot_requires_registered_media_and_preserves_unparsed_raw_record(self):
        Image.new('RGB', (12, 8), 'blue').save(self.project / '未登记.png')
        target = self.project / '快照.zip'
        with self.assertRaisesRegex(ValueError, '先登记'):
            snapshots.create(self.project, target, ['未登记.png'])
        self.assertFalse(target.exists())
        bad = self.document.parent / '外部原响应.json'
        bad.write_bytes(b'{"one": 1}\n{"two": 2}')
        result = snapshots.create(self.project, target, ['制作'])
        self.assertIn('制作/外部原响应.json', result['unparsed_documents'])
        with ZipFile(target) as bundle:
            self.assertEqual(bundle.read('制作/外部原响应.json'), bad.read_bytes())

    def test_create_and_restore_reject_escaping_paths(self):
        with self.assertRaises(ValueError):
            snapshots.create(self.project, self.project / 'safe.zip', ['../原件.png'])
        target = self.project / '恶意.zip'
        with ZipFile(target, 'w') as bundle:
            bundle.writestr(snapshots.MANIFEST, json.dumps({'media': {}, 'attachments': {}}))
            bundle.writestr('../逃逸.txt', 'bad')
        with self.assertRaisesRegex(ValueError, '越界'):
            snapshots.restore(self.project, target, self.root / '恢复')
        self.assertFalse((self.root / '恢复').exists())
        self.assertFalse((self.root / '逃逸.txt').exists())

    def test_shared_historical_media_keeps_original_paths_bytes_and_mtime(self):
        case = self.root / '同一单历史'
        source = case / '主归档/原件.png'
        target = case / '旧入口/原件.png'
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        source.write_bytes(self.source.read_bytes())
        target.write_bytes(self.source.read_bytes())
        import os
        os.utime(target, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns))
        stamp = target.stat().st_mtime_ns
        store_media(case, target, source=source)
        self.assertTrue(target.samefile(source))
        self.assertFalse(source.stat().st_mode & 0o222)
        self.assertEqual(target.stat().st_mtime_ns, stamp)
        self.assertEqual(target.read_bytes(), self.source.read_bytes())


if __name__ == '__main__':
    unittest.main()
