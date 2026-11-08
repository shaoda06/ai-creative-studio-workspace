"""Real media paths and original evidence in temporary migration projects."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
import sys
from types import SimpleNamespace
from urllib.parse import unquote

from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.agents/skills/studio-workspace-browser/scripts'))
import project_resources as resources
import migrate_project_resources as migration


class ResourceMigrationTests(unittest.TestCase):
    def test_different_runs_with_identical_bytes_keep_versions_and_share_storage(self):
        first = self.project / '候选/EP001-C001-P001-R001-一采.mp4'
        first.parent.mkdir(); first.write_bytes(b'legacy-video-fixture')
        second = first.with_name('EP001-C001-P001-R002-一采.mp4'); second.write_bytes(first.read_bytes())
        report = migration.stage(self.project, self.audit)
        self.assertEqual(report['version_count'], 2)
        one, two = resources.reference(self.project, first), resources.reference(self.project, second)
        self.assertEqual(one['resource_id'], two['resource_id'])
        self.assertNotEqual(one['version'], two['version'])
        self.assertTrue((self.project / one['file']).samefile(self.project / two['file']))

    def test_formal_copy_cannot_merge_distinct_candidate_versions(self):
        one = self.picture('候选/CH001-全身-候选-v01.png', 'red')
        two = self.picture('候选/CH001-全身-候选-v02.png', 'red')
        self.picture('参考图/CH001-全身.png', 'red')
        report = migration.stage(self.project, self.audit)
        self.assertEqual(report['version_count'], 2)
        self.assertNotEqual(resources.reference(self.project, one)['version'], resources.reference(self.project, two)['version'])

    def test_extracted_picture_named_after_a_video_does_not_become_video_family(self):
        picture = self.picture('候选/EP001-C001-P001-R001-一采-首帧.png', 'red')
        video = self.project / '候选/EP001-C001-P001-R001-一采.mp4'
        video.write_bytes(b'legacy-video-fixture')
        report = migration.stage(self.project, self.audit)
        self.assertEqual({ref['kind'] for ref in report['versions']}, {'图片', '视频'})
        self.assertTrue(resources.reference(self.project, picture)['family_key'].startswith('图片/'))
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'projects/测试'
        self.project.mkdir(parents=True)
        self.audit = self.root / 'audit'

    def picture(self, key, color):
        path = self.project / key
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (12, 8), color).save(path)
        return path

    def test_copies_and_revisions_consolidate_and_evidence_keeps_original_bytes(self):
        one = self.picture('03-人物资料/其他资料/工作稿/素材/CH001-全身-候选-v01.png', 'red')
        two = self.picture('03-人物资料/其他资料/工作稿/素材/CH001-全身-候选-v02.png', 'blue')
        formal = self.project / '03-人物资料/CH001/参考图/CH001-全身.png'
        formal.parent.mkdir(parents=True); os.link(two, formal)
        snapshot = self.picture('99-综合资料/历史版本/封存快照/CH001-全身.png', 'blue')
        evidence = self.project / '03-人物资料/其他资料/执行附件/任务/请求.json'
        evidence.parent.mkdir(parents=True)
        raw = json.dumps({'file': str(one), 'original_file': str(formal)}, ensure_ascii=False).encode()
        evidence.write_bytes(raw)
        doc = self.project / '资料卡.md'
        doc.write_text('[采用](03-人物资料/CH001/参考图/CH001-全身.png)；用户已采用v02。\n')
        report = migration.stage(self.project, self.audit)
        self.assertEqual(report['media_count'], 3)
        self.assertEqual(report['version_count'], 2)
        self.assertEqual(report['aliases'][two.relative_to(self.project).as_posix()], report['aliases'][formal.relative_to(self.project).as_posix()])
        self.assertTrue(one.exists())
        self.assertIn('资源/', unquote(doc.read_text()))
        self.assertIn('用户已采用v02', doc.read_text())
        self.assertEqual(evidence.read_bytes(), raw)
        self.assertEqual(snapshot.read_bytes(), (self.project / report['aliases'][formal.relative_to(self.project).as_posix()]).read_bytes())
        self.assertFalse(resources.enabled(self.project))
        migration.finalize(self.project, self.audit)
        self.assertTrue(resources.enabled(self.project))
        self.assertFalse(one.exists())
        self.assertTrue(snapshot.exists())
        self.assertEqual(resources.resolve_file(self.project, one).read_bytes(), (self.project / report['aliases'][one.relative_to(self.project).as_posix()]).read_bytes())
        self.assertEqual(evidence.read_bytes(), raw)
        self.assertEqual(migration.finalize(self.project, self.audit)['version_count'], 2)

    def test_changed_source_stops_before_any_removal(self):
        one = self.picture('素材/一.png', 'red')
        two = self.picture('素材/二.png', 'blue')
        migration.stage(self.project, self.audit)
        one.unlink(); self.picture('素材/一.png', 'green')
        with self.assertRaisesRegex(ValueError, '已变化'):
            migration.finalize(self.project, self.audit)
        self.assertTrue(two.exists())
        self.assertFalse(resources.enabled(self.project))

    def test_independent_recorded_outputs_keep_two_versions_even_if_bytes_equal(self):
        one = self.picture('候选/R001/A001-人物-v01.png', 'red')
        two = self.picture('候选/R002/A001-人物-v02.png', 'red')
        doc = self.project / '任务清单.json'
        doc.write_text(json.dumps({'tasks': [{'record_dir': '执行附件/R001', 'outputs': [{'path': str(one)}]},
                                           {'record_dir': '执行附件/R002', 'outputs': [{'path': str(two)}]}]}))
        plan = migration.inspect(self.project)
        self.assertEqual(len(plan['groups']), 2)
        self.assertFalse((self.project / '资源').exists())

    def test_archived_project_is_not_migrated(self):
        (self.project / '.archived').write_text('只读')
        with self.assertRaises(PermissionError):
            migration.stage(self.project, self.audit)

    def test_old_preparation_keeps_exact_input_after_resource_migration(self):
        from backend.services import execution_checks as checks
        source = self.picture('参考图/旧输入.png', 'red')
        record = self.project / '执行附件/旧任务'; record.mkdir(parents=True)
        original = {'task_type': 'image', 'outputs': [], 'uploads': [{'file': '参考图/旧输入.png'}]}
        stamp = source.stat()
        report = {'ok': True, 'prepared_input': original, 'sources': {'参考图/旧输入.png': [stamp.st_size, stamp.st_mtime_ns]}}
        (record / checks.REPORT).write_text(json.dumps(report, ensure_ascii=False))
        evidence = (record / checks.REPORT).read_bytes()
        migration.stage(self.project, self.audit); migration.finalize(self.project, self.audit)
        current = deepcopy(original)
        current['uploads'][0]['file'] = resources.reference(self.project, source)['file']
        store = SimpleNamespace(portable_input=lambda data: deepcopy(current))
        data = SimpleNamespace(project=str(self.project), record_dir=str(record), task_type='image', record_format='legacy', video_plan=None)
        checks.check_prepared(store, data, legacy=True)
        self.assertEqual((record / checks.REPORT).read_bytes(), evidence)
