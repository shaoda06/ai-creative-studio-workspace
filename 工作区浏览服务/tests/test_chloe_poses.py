"""Verify the live pose guide, page filters and registered image URLs."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from PIL import Image

from backend.chloe_poses import router


class ChloePosesTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.references = root / 'references'
        self.categories = self.references / '人物姿态'
        self.categories.mkdir(parents=True)
        self.guide = self.references / '人物姿态参考表.md'
        assets = root / 'assets'
        assets.mkdir()
        self.image = assets / '线稿.png'
        Image.new('RGB', (900, 1200), 'white').save(self.image)
        self.enterContext(patch('backend.chloe_poses.POSE_SKILL', root))
        space = SimpleNamespace(view='chloe-commerce', api='/test', runtime=root / 'runtime')

        def select(request: Request):
            request.state.workspace_space = space

        app = FastAPI()
        app.include_router(router, prefix=space.api, dependencies=[Depends(select)])
        self.client = self.enterContext(TestClient(app))
        self.url = space.api + '/shared-poses'

    def test_source_edits_update_categories_text_and_pages(self):
        guide = '# 人物姿态参考表\n\n## 分类与查用\n\n- [站姿](人物姿态/站姿.md)\n'
        self.guide.write_text(guide, 'utf-8')
        (self.categories / '站姿.md').write_text(
            '# 站姿\n\n## 站姿-001 正面站立\n\n两脚等重。\n\n![线稿](../../assets/线稿.png)\n\n*短标注。*\n', 'utf-8')
        (self.categories / '坐姿.md').write_text(
            '# 坐姿\n\n## 坐姿-001 椅边坐姿\n\n双脚平放。\n\n![线稿](../../assets/线稿.png)\n', 'utf-8')
        first = self.client.get(self.url, params={'page': 1, 'page_size': 1})
        self.assertEqual(first.json()['types'], ['站姿'])
        pose, = first.json()['items']
        self.assertEqual((pose['id'], pose['category'], pose['description']), ('站姿-001', '站姿', '两脚等重。'))
        self.assertEqual(self.client.get(pose['media']['url']).content, self.image.read_bytes())
        thumbnail = self.client.get(pose['media']['thumbnailUrl'])
        self.assertEqual((thumbnail.status_code, thumbnail.headers['content-type']), (200, 'image/webp'))
        self.assertEqual(self.client.get(self.url + '/坐姿-001/image').status_code, 404)
        headers = {'If-None-Match': first.headers['etag']}
        self.assertEqual(self.client.get(first.url, headers=headers).status_code, 304)

        self.guide.write_text(guide + '- [坐姿](人物姿态/坐姿.md)\n', 'utf-8')
        changed = self.client.get(first.url, headers=headers)
        self.assertCountEqual(changed.json()['types'], ['站姿', '坐姿'])
        self.assertEqual(changed.json()['total'], 2)
        next_page = self.client.get(self.url, params={'page': 2, 'page_size': 1}).json()
        self.assertEqual(next_page['items'][0]['id'], '坐姿-001')
        filtered = self.client.get(self.url, params={'page': 2, 'types': '坐姿'}).json()
        self.assertEqual((filtered['page'], filtered['total']), (1, 1))
        self.assertEqual(filtered['items'][0]['description'], '双脚平放。')
        entire_category = self.client.get(self.url, params={
            'types': '坐姿', 'available': True, 'require_media': True,
        }).json()
        self.assertEqual([pose['id'] for pose in entire_category], ['坐姿-001'])
