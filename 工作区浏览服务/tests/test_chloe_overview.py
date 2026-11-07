from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.chloe_overview import TOOL, account_overview, example_overview, router


class ChloeOverviewTests(unittest.TestCase):
    def test_templates_and_distinct_permissions(self):
        new = example_overview('new')
        working = example_overview('working')
        self.assertEqual(new['videos'], [])
        self.assertEqual(new['connection']['连接状态'], '未核实')
        self.assertEqual(working['connection']['连接状态'], '已连接')
        self.assertEqual(working['connection']['挂品资格'], '待核实')
        self.assertEqual(len(working['videos']), 3)
        self.assertFalse(any(v['published'] for v in working['videos']))

    def test_progress_is_read_from_markdown_and_format_errors_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'example'
            shutil.copytree(TOOL/'examples/chloe-overview/working', root)
            path = next((root/'projects').glob('V001-*/README.md'))
            path.write_text(path.read_text().replace('| 制作状态 | 待用户决定 |', '| 制作状态 | 进行中 |'))
            self.assertEqual(account_overview(root)['videos'][0]['progress']['制作状态'], '进行中')
            path.write_text(path.read_text().replace('## 定位与当前进度', '## 自拟章节'))
            with self.assertRaisesRegex(ValueError, '章节名称'):
                account_overview(root)

    def test_readonly_fixed_scenarios(self):
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/examples/chloe/overview').status_code, 200)
            self.assertEqual(client.get('/api/examples/chloe/overview?scenario=new').json()['videos'], [])
            self.assertEqual(client.get('/api/examples/chloe/overview?scenario=../../workspaces').status_code, 422)
            self.assertEqual(client.post('/api/examples/chloe/overview').status_code, 405)


if __name__ == '__main__':
    unittest.main()
