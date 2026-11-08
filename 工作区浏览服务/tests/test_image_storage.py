"""PNG storage boundaries and real publication replacement, using temporary projects only."""
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.agents/skills/studio-imagegen/scripts'))
from backend.services import image_closeout
import image_files
from image_files import store_png
from image_processing import resize
from imagegen_tool import preserve_original


class ImageStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / '项目'
        self.project.mkdir()
        stream = BytesIO()
        Image.new('RGB', (12, 8), 'red').save(stream, format='PNG')
        self.raw = stream.getvalue()
        stream = BytesIO()
        Image.new('RGB', (12, 8), 'blue').save(stream, format='PNG')
        self.new = stream.getvalue()

    def test_native_repeated_outputs_share_project_data_and_keep_external_original(self):
        source = self.root / '工具原图.png'
        source.write_bytes(self.raw)
        mode = source.stat().st_mode
        one, two = self.project / '候选v01.png', self.project / '另一轮v01.png'
        preserve_original(source, one, project=self.project)
        preserve_original(source, two, project=self.project)
        self.assertTrue(one.samefile(two))
        self.assertFalse(one.samefile(source))
        self.assertEqual(source.stat().st_mode, mode)
        self.assertEqual(one.stat().st_mode & 0o222, 0)
        self.assertEqual(one.read_bytes(), self.raw)

    def test_equal_size_processing_keeps_bytes_and_inode_but_changed_size_gets_new_image(self):
        source, same, resized = [self.project / name for name in ('原图.png', '规格处理.png', '缩小.png')]
        store_png(self.project, source, self.raw)
        resize(source, same, (12, 8), [0.5, 0.5], project=self.project)
        resize(source, resized, (6, 4), [0.5, 0.5], project=self.project)
        self.assertTrue(source.samefile(same))
        self.assertFalse(source.samefile(resized))
        self.assertEqual(image_files.png(resized.read_bytes()), (6, 4))
        self.assertEqual(source.read_bytes(), self.raw)

    def test_formal_replacement_preserves_old_candidate_frozen_input_and_archive(self):
        old = self.project / '候选v01.png'
        frozen = self.project / '任务输入.png'
        formal = self.project / '正式.png'
        newer = self.project / '候选v02.png'
        archive = self.project / '历史.png'
        store_png(self.project, old, self.raw)
        store_png(self.project, frozen, self.raw, source=old)
        store_png(self.project, formal, self.raw, source=old)
        self.assertTrue(old.samefile(formal))
        store_png(self.project, newer, self.new)
        state = formal.stat()
        report = dict(updates=[], publication=dict(source=newer.name, formal=formal.name,
            archive=archive.name, prior=[state.st_size, state.st_mtime_ns]))
        image_closeout.apply_updates(self.project, report, self.project / '保存记录.json')
        for path in (old, frozen, archive):
            self.assertEqual(path.read_bytes(), self.raw)
            self.assertTrue(path.samefile(old))
        self.assertTrue(formal.samefile(newer))
        self.assertFalse(formal.samefile(old))
        self.assertEqual(formal.read_bytes(), self.new)
        image_closeout.apply_updates(self.project, report, self.project / '保存记录.json')
        self.assertEqual(archive.read_bytes(), self.raw)

    def test_other_project_is_never_a_hardlink_source(self):
        other = self.root / '另一项目'
        other.mkdir()
        source = other / '原图.png'
        store_png(other, source, self.raw)
        target = self.project / '候选.png'
        store_png(self.project, target, self.raw, source=source)
        self.assertFalse(source.samefile(target))

    def test_windows_replacement_branch_restores_old_shared_inode_protection(self):
        old, formal = self.project / '候选v01.png', self.project / '正式.png'
        store_png(self.project, old, self.raw)
        store_png(self.project, formal, self.raw, source=old)
        state = formal.stat()
        with patch.object(image_files.sys, 'platform', 'win32'):
            store_png(self.project, formal, self.new, replace=True, prior=[state.st_size, state.st_mtime_ns])
            copied = self.project / '复用.png'
            store_png(self.project, copied, self.new)
            self.assertTrue(copied.samefile(formal))
            self.assertEqual(copied.stat().st_mode & 0o222, 0)
        self.assertEqual(old.read_bytes(), self.raw)
        self.assertEqual(old.stat().st_mode & 0o222, 0)
        self.assertEqual(formal.read_bytes(), self.new)

    def test_immutable_output_conflict_and_outside_destination_fail(self):
        target = self.project / '候选.png'
        store_png(self.project, target, self.raw)
        with self.assertRaisesRegex(ValueError, '已有不同内容'):
            store_png(self.project, target, self.new)
        with self.assertRaisesRegex(ValueError, '越出项目'):
            store_png(self.project, '../越界.png', self.raw)
        self.assertEqual(target.read_bytes(), self.raw)

    def test_idempotence_and_recovered_download_coalesce_with_existing_readonly_image(self):
        kept, downloaded = self.project / '留存.png', self.project / '刚下载.png'
        store_png(self.project, kept, self.raw)
        downloaded.write_bytes(self.raw)
        store_png(self.project, downloaded, self.raw)
        inode = downloaded.stat().st_ino
        self.assertTrue(kept.samefile(downloaded))
        store_png(self.project, downloaded, self.raw)
        self.assertEqual(downloaded.stat().st_ino, inode)

    def test_unpublished_staging_file_is_never_a_reuse_source(self):
        folder = self.project / '.png-save-incomplete'
        folder.mkdir()
        pending = folder / 'image.png'
        pending.write_bytes(self.raw)
        pending.chmod(0o444)
        target = self.project / '实际结果.png'
        store_png(self.project, target, self.raw)
        self.assertFalse(pending.samefile(target))
        self.assertEqual(target.read_bytes(), self.raw)

    def test_concurrent_change_is_not_overwritten_and_staging_is_removed(self):
        source, target = self.project / '已存.png', self.project / '新路径.png'
        store_png(self.project, source, self.raw)
        link = image_files.os.link

        def changed(first, second):
            link(first, second)
            if Path(second).name == 'media.png':
                target.write_bytes(self.new)

        for platform in ('darwin', 'win32'):
            if target.exists():
                target.unlink()
            with self.subTest(platform=platform), patch.object(image_files.sys, 'platform', platform), \
                    patch.object(image_files.os, 'link', side_effect=changed), self.assertRaisesRegex(ValueError, '目标变化'):
                store_png(self.project, target, self.raw, source=source)
            self.assertEqual(target.read_bytes(), self.new)
            self.assertEqual(source.stat().st_mode & 0o222, 0)
            self.assertFalse(list(self.project.glob('.media-save-*')))

    def test_cli_preserves_previous_formal_before_replacing(self):
        formal, source, archive = [self.project / name for name in ('正式.png', '新原图.png', '旧正式.png')]
        store_png(self.project, formal, self.raw)
        source.write_bytes(self.new)
        command = [sys.executable, '-B', str(Path(image_files.__file__)), '--project', str(self.project),
                   '--source', str(source), '--output', formal.name]
        refused = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(formal.read_bytes(), self.raw)
        done = subprocess.run([*command, '--archive', archive.name], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)['width'], 12)
        self.assertEqual(archive.read_bytes(), self.raw)
        self.assertTrue(formal.samefile(source))


if __name__ == '__main__':
    unittest.main()
