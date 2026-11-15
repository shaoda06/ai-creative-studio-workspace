import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from backend.chloe_asset_pages import AssetPage, AssetRow, asset_page, respond_asset_page


class ChloeAssetPagesTests(unittest.TestCase):
    def test_etag_only_revalidates_the_requested_page_and_filters(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            space = SimpleNamespace(api='/example')
            app = FastAPI()
            rows = [
                AssetRow('C001', lambda: {'id': 'C001'}, '制作中'),
                AssetRow('C002', lambda: {'id': 'C002'}, '可用'),
            ]

            @app.get('/assets')
            def listing(request: Request, options: AssetPage = Depends()):
                return respond_asset_page(request, space, 'assets', options, lambda: rows, folders=[root])

            with TestClient(app) as client:
                url = '/assets?page=1&page_size=1'
                first = client.get(url)
                self.assertEqual(first.json()['items'], [{'id': 'C001'}])
                headers = {'If-None-Match': first.headers['etag']}
                self.assertEqual(client.get(url, headers=headers).status_code, 304)
                for other in ('/assets?page=2&page_size=1', url + '&available=true'):
                    response = client.get(other, headers=headers)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()['items'], [{'id': 'C002'}])
                self.assertEqual(client.get('/assets?ids=C002', headers=headers).json(), [{'id': 'C002'}])

    def test_filters_count_the_whole_catalog_and_only_build_the_current_page(self):
        built = []

        def card(identity):
            built.append(identity)
            return {'id': identity}

        rows = [
            AssetRow(str(index), lambda index=index: card(str(index)),
                     '制作中' if index == 4 else '可用', index != 6,
                     '套装' if index == 8 else '单件',
                     '外套' if index in (25, 26) else '上装')
            for index in range(1, 27)
        ]
        result = asset_page(rows, AssetPage(page=2, available=True, require_media=True, form='单件', types=['上装']))
        self.assertEqual((result['page'], result['total'], result['page_size']), (2, 21, 12))
        self.assertCountEqual(result['types'], ['上装', '外套'])
        self.assertEqual(built, [str(index) for index in range(16, 25)])
        self.assertEqual(result['items'], [{'id': identity} for identity in built])

        built.clear()
        selected = asset_page(rows, AssetPage(available=True, require_media=True, form='单件', ids=['26', '4', '1', '6']))
        self.assertEqual(selected, [{'id': '26'}, {'id': '1'}])
        self.assertEqual(built, ['26', '1'])

        last = asset_page(rows, AssetPage(page=100, types=['外套']))
        self.assertEqual((last['page'], last['total']), (1, 2))
        self.assertEqual(last['items'], [{'id': '25'}, {'id': '26'}])
