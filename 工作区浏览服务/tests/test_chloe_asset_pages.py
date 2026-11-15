import unittest

from backend.chloe_asset_pages import AssetPage, AssetRow, asset_page


class ChloeAssetPagesTests(unittest.TestCase):
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
