from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from backend.chloe_asset_search import router
from chloe_init import initialize_asset, initialize_project, initialize_workspace


class ChloeAssetSearchTests(TestCase):
    def test_search_number_and_detail_destinations_in_current_scope(self):
        with TemporaryDirectory() as directory:
            workspace = initialize_workspace(Path(directory)/'Chloe Workspace')
            root = initialize_project(workspace, '隔离搜索')
            other = initialize_project(workspace, '另一个项目')
            for kind, identity, name in (
                ('模特', 'M001', '示例模特'), ('发型', 'H001', '示例发型'), ('配饰', 'C001', '示例配饰'),
                ('场景', 'S001', '示例场景'), ('声音', 'A001', '示例声音'), ('参考视频', 'RV001', '未登记视频'),
                ('服装', 'O002', '旧服装'),
            ):
                initialize_asset(root, kind, identity, name)
            outfit = initialize_asset(root, '服装', 'O001', '示例套装')/'服装说明.md'
            outfit.write_text(outfit.read_text('utf-8').replace('服装形态 | 待确定', '服装形态 | 套装')
                              .replace('套装来源 | 不适用', '套装来源 | 提取')
                              .replace('组成与穿法 | 不适用', '组成与穿法 | 示例搭配'), 'utf-8')
            look = initialize_asset(root, '造型', 'L001', '示例造型')/'造型说明.md'
            text = look.read_text('utf-8').replace('模特编号 | 待确定', '模特编号 | M001')
            start = text.index('## 关联资料')
            end = text.index('\n\n', text.index('| ---', start))
            row = '\n| 模特 | M001 | [说明](<../../AI模特/M001-示例模特/模特说明.md>) | 造型人物 |'
            look.write_text(text[:end]+row+text[end:], 'utf-8')

            def select(scope: str, request: Request):
                owner, view = {'first': (root, 'chloe-commerce'), 'second': (other, 'chloe-commerce'),
                               'unrelated': (root, 'files')}[scope]
                request.state.workspace_space = SimpleNamespace(root=owner, view=view)

            app = FastAPI()
            app.include_router(router, prefix='/{scope}', dependencies=[Depends(select)])
            poses = {'站姿-016': SimpleNamespace(id='站姿-016', name='隔离姿态')}
            with TestClient(app) as client, patch('backend.chloe_asset_search.catalog', return_value=(poses, 'test')):
                url = '/first/shared-asset-search'
                for query, asset, field in (
                    ('m001', 'models', 'model'), ('h001', 'hair', 'hair'), ('c001', 'accessories', 'accessory'),
                    ('s001', 'scenes', 'scene'), ('a001', 'voices', 'voice'), ('站姿-016', 'poses', 'pose'),
                ):
                    with self.subTest(query=query):
                        self.assertEqual(client.get(url, params={'q': query}).json()[0]['params'],
                                         {'asset': asset, field: query.upper()})
                clothes = client.get(url, params={'q': ' o00 '}).json()
                self.assertEqual([(item['id'], item['params']['clothingTab']) for item in clothes],
                                 [('O001', 'outfits'), ('O002', 'garments')])
                look_result = client.get(url, params={'q': 'L001'})
                self.assertEqual(look_result.status_code, 200, look_result.text)
                self.assertEqual(look_result.json()[0]['params'],
                                 {'asset': 'models', 'model': 'M001', 'modelTab': 'looks', 'look': 'L001'})
                for query in ('', '示例套装', 'RV001', '001'):
                    self.assertEqual(client.get(url, params={'q': query}).json(), [])
                self.assertEqual(client.get('/second/shared-asset-search', params={'q': 'O001'}).json(), [])
                self.assertEqual(client.get('/unrelated/shared-asset-search', params={'q': 'O001'}).status_code, 404)
