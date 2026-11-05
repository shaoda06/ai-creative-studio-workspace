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
