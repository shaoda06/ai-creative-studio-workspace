from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.chloe_overview import TOOL, account_overview, example_overview, router


class ChloeOverviewTests(unittest.TestCase):
    def test_direction_and_video_progress_without_operational_dependencies(self):
        for scenario in ('new', 'working'):
            data = example_overview(scenario)
            self.assertEqual(list(data), ['direction', 'videos'])
            self.assertEqual(list(data['direction']), ['发布平台', '目标人群', '内容风格'])
            self.assertFalse((TOOL/'examples/chloe-overview'/scenario/'综合资料/账号运营配置.md').exists())
        self.assertEqual(example_overview('new')['direction']['目标人群'], '待确定')
        self.assertEqual(example_overview('new')['videos'], [])
        videos = example_overview('working')['videos']
        self.assertEqual(len(videos), 3)
        self.assertEqual(sum(v['progress']['处理状态'] == '待用户决定' for v in videos), 1)
        self.assertEqual(sum(v['progress']['当前阶段'] == '人工后期' for v in videos), 1)
        self.assertEqual([v['progress']['视频状态'] for v in videos], ['制作中','制作中','待发布'])

    def test_document_updates_multiple_platforms_and_format_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'example'
            shutil.copytree(TOOL/'examples/chloe-overview/new', root)
            path = root/'综合资料/账号定位.md'
            path.write_text(path.read_text().replace('| 发布平台 | 抖音 |', '| 发布平台 | 抖音、小红书 |'))
            self.assertEqual(account_overview(root)['direction']['发布平台'], '抖音、小红书')
            path.write_text(path.read_text().replace('## 账号方向', '## 自拟章节'))
            with self.assertRaisesRegex(ValueError, '章节名称'):
                account_overview(root)

    def test_video_progress_updates_from_its_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'example'
            shutil.copytree(TOOL/'examples/chloe-overview/working', root)
            path = next((root/'projects').glob('V001-*/README.md'))
            text = path.read_text().replace('| 处理状态 | 待用户决定 |', '| 处理状态 | 正常 |')
            path.write_text(text)
            videos = account_overview(root)['videos']
            self.assertEqual(videos[0]['progress']['处理状态'], '正常')
            self.assertEqual(sum(v['progress']['处理状态'] == '待用户决定' for v in videos), 0)
            path.write_text(text.replace('## 定位与当前进度', '## 临时章节'))
            with self.assertRaisesRegex(ValueError, '章节名称'):
                account_overview(root)

    def test_readonly_fixed_scenarios(self):
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/examples/chloe/overview').status_code, 200)
            self.assertEqual(list(client.get('/api/examples/chloe/overview?scenario=new').json()), ['direction', 'videos'])
            self.assertEqual(client.get('/api/examples/chloe/overview?scenario=../../workspaces').status_code, 422)
            self.assertEqual(client.post('/api/examples/chloe/overview').status_code, 405)


if __name__ == '__main__':
    unittest.main()
