"""The authorized flat-to-work migration preserves originals and rewrites current links."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

script = Path(__file__).resolve().parents[2] / '.agents/skills/iris-commercial-brief/scripts/migrate_work.py'
spec = importlib.util.spec_from_file_location('migrate_work', script)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
layout_spec = importlib.util.spec_from_file_location('migrate_layout', script.with_name('migrate_layout.py'))
layout = importlib.util.module_from_spec(layout_spec)
layout_spec.loader.exec_module(layout)


class WorkMigrationTests(unittest.TestCase):
    def test_dry_run_then_migration_keeps_raw_media_task_evidence_and_current_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'C003-隔离'
            def write(key, text):
                path = project / key
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                return path
            headings = ['项目说明', '项目专用约定', '目录与资料入口', '进度与版本入口', '接续要求', '历史与特殊事项']
            body = '\n\n'.join('## ' + heading + '\n\n' + (
                '[脚本](03-创意脚本/制作脚本-v01.md)' if heading == '目录与资料入口' else '已确认内容') for heading in headings)
            write('README.md', '# 隔离项目\n\n' + body)
            state = '| 对象 | 当前版本/文件 |\n| --- | --- |\n| 脚本 | 03-创意脚本/制作脚本-v01.md |\n'
            write('项目状态.md', '# 项目状态\n项目：隔离\n当前阶段与下一步：等待审阅\n' + state)
            write('01-客户资料/甲方原稿.md', '原文不能改变')
            write('01-客户资料/需求与来源-v01.md', '[原稿](甲方原稿.md)')
            script_file = write('03-创意脚本/制作脚本-v01.md', '[原稿](../01-客户资料/甲方原稿.md)\n[状态](../项目状态.md)\n[图](../05-资产/采用/图.png)')
            write('资源/图片/IMG-test/V001/图.png', 'actual-media')
            write('资源/资源索引.json', json.dumps({'aliases': {'05-资产/采用/图.png': '资源/图片/IMG-test/V001/图.png'}}))
            evidence = write('06-视频生产/执行记录/R001/请求.json', '{"original":"03-创意脚本/制作脚本-v01.md"}')
            original_evidence = evidence.read_bytes()
            write('07-返修交接/交接.jianying.json', json.dumps({'name': '隔离', 'media': [{'file': '05-资产/采用/图.png', 'member': '图.png'}]}))
            plan = migration.migrate(project, 'F001-隔离片', '隔离片', '按已有脚本制作')
            self.assertTrue(script_file.exists())
            self.assertFalse((project / '作品').exists())
            self.assertEqual(plan['records'], ['06-视频生产/执行记录'])
            migration.migrate(project, 'F001-隔离片', '隔离片', '按已有脚本制作', apply=True)
            work = project / '作品/F001-隔离片'
            self.assertTrue((work / '07-返修交接/成片').is_dir())
            self.assertFalse(script_file.exists())
            self.assertEqual(evidence.read_bytes(), original_evidence)
            self.assertEqual((project / '01-客户资料/甲方原稿.md').read_text(), '原文不能改变')
            content = (work / '03-创意脚本/制作脚本-v01.md').read_text()
            self.assertIn('../../../01-客户资料/甲方原稿.md', content)
            self.assertIn('../作品状态.md', content)
            self.assertIn('../../../资源/图片/IMG-test/V001/图.png', content)
            self.assertIn('作品/F001-隔离片/03-创意脚本/制作脚本-v01.md', (work / '作品状态.md').read_text())
            self.assertIn('03-创意脚本/制作脚本-v01.md', (work / 'README.md').read_text())
            self.assertEqual(list(migration.sections((project / 'README.md').read_text())), headings)
            self.assertEqual(len(migration.sections((work / 'README.md').read_text())), 6)
            self.assertEqual(json.loads((work / '07-返修交接/交接.jianying.json').read_text())['media'][0]['file'], '资源/图片/IMG-test/V001/图.png')
            with zipfile.ZipFile(project / '归档/多作品迁移前文档-20261106.zip') as archive:
                self.assertEqual(archive.read('项目状态.md').decode().splitlines()[-1], '| 脚本 | 03-创意脚本/制作脚本-v01.md |')
            with self.assertRaises(FileExistsError):
                migration.migrate(project, 'F001-隔离片', '隔离片', '不重复迁移', apply=True)


class NumberedLayoutMigrationTests(unittest.TestCase):
    def test_numbered_layout_rewrites_live_references_and_preserves_execution_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            work = '作品/F001-隔离'
            old_export = work + '/07-返修交接/成片/成片.mp4'
            old_resource = '资源/视频/VID-test/V001/素材.mp4'
            for folder in ('归档', '08-完单复盘', work + '/99-综合资料'):
                (project / folder).mkdir(parents=True)

            def write(relative, data):
                target = project / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(data)

            write(old_export, 'final')
            write(old_resource, 'resource')
            write('资源/资源索引.json', json.dumps({'aliases': {'旧素材.mp4': old_resource}, 'files': {}, 'outputs': {}}))
            write(work + '/07-返修交接/剪映.jianying.json', json.dumps({'media': [{'file': old_resource}]}))
            write(work + '/作品状态.md', f'[成片](07-返修交接/成片/成片.mp4)\n| 文件 | {old_export} |\n')
            write(work + '/05-资产/资产清单.md', f'资源文件：../../../{old_resource}\n')
            evidence = work + '/06-视频生产/执行记录/原请求.json'
            original = json.dumps({'record_dir': evidence, 'file': old_resource})
            write(evidence, original)

            self.assertEqual(layout.migrate(project)['works'], 1)
            self.assertTrue((project / old_export).is_file())
            result = layout.migrate(project, apply=True)
            new_work = '03-' + work
            new_resource = '02-' + old_resource
            state = (project / new_work / '作品状态.md').read_text()
            self.assertIn('[成片](08-成片/成片.mp4)', state)
            self.assertIn(new_work + '/08-成片/成片.mp4', state)
            self.assertIn('../../../' + new_resource, (project / new_work / '05-资产/资产清单.md').read_text())
            self.assertEqual((project / new_work / '08-成片/成片.mp4').read_text(), 'final')
            self.assertEqual((project / ('03-' + evidence)).read_text(), original)
            self.assertFalse((project / new_work / '99-综合资料').exists())
            manifest = json.loads((project / new_work / '07-返修交接/剪映.jianying.json').read_text())
            self.assertEqual(manifest['media'][0]['file'], new_resource)
            with zipfile.ZipFile(project / result['backup']) as archive:
                self.assertIn(old_export, archive.read(work + '/作品状态.md').decode())
