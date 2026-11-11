import os
from io import BytesIO
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from PIL import Image

from functools import partial
from backend.chloe_reference_assets import CLOTHING, HAIR, SCENES, asset_cards, asset_detail, asset_file, asset_router
from chloe_init import initialize_workspace, initialize_project, initialize_asset, SKILLS
sys.path.insert(0, str(SKILLS/'chloe-assets/scripts'))
from chloe_resources import import_media
from chloe_documents import check_workspace


class ChloeClothingTests(unittest.TestCase):
    kind = CLOTHING
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = initialize_project(initialize_workspace(self.base/'Chloe Workspace'), '隔离样例')
        self.identity = self.kind.prefix+'001'
        self.folder = initialize_asset(self.root, self.kind.label, self.identity, '示例资产')
        self.cards = partial(asset_cards, kind=self.kind)
        self.detail = partial(asset_detail, kind=self.kind)
        self.file = partial(asset_file, kind=self.kind)
        self.path = self.folder/(self.kind.label+'说明.md')
        self.api = '/api/workspaces/test'

    def append(self, section, row):
        text = self.path.read_text()
        start = text.index('## '+section+'\n')
        end = text.index('\n\n', text.index('| ---', start))
        self.path.write_text(text[:end]+'\n| '+' | '.join(row)+' |'+text[end:])

    def image(self, color, key, resource=None, size=(40, 60)):
        path = self.base/(key+'.png')
        Image.new('RGB', size, color).save(path)
        ref = import_media(self.root, path, key, resource_id=resource)
        return ref, f'[共用:{ref["resource_id"]}@{ref["version"]}](<{os.path.relpath(ref["absolute_file"], self.folder)}>)'

    def test_empty_clothing_and_exact_adopted_cover_without_copies(self):
        self.assertIsNone(self.cards(self.root,self.api)[0]['media'])
        first, label = self.image('red','first')
        second, other = self.image('blue','second',first['resource_id'])
        self.append('参考版本',[self.kind.label+'展示图',label,'用户提供','不适用'])
        self.append('参考版本',[self.kind.label+'展示图',other,label,'不适用'])
        self.assertIsNone(self.cards(self.root,self.api)[0]['media'])
        self.append('当前采用',[self.kind.label+'展示图',label,'隔离采用','2026-11-07T12:00:00+08:00'])
        before = {str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        detail = self.detail(self.root,self.identity,self.api)
        card = self.cards(self.root,self.api)[0]
        self.assertEqual(card['media']['key'],Path(first['absolute_file']).relative_to(self.root).as_posix())
        self.assertEqual(self.file(self.root,self.identity,card['media']['key']),Path(first['absolute_file']))
        self.assertEqual(detail['description'],'无')
        self.assertEqual([s['heading'] for s in detail['sections']][:1],[self.kind.label+'信息'])
        self.assertEqual(len(detail['images']),2)
        self.assertEqual(sum(image['adopted'] for image in detail['images']),1)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_thumbnail_uses_exact_version_and_original_download(self):
        first, label = self.image('red', 'large', size=(1200, 1800))
        second, other = self.image('blue', 'small', first['resource_id'])
        purpose = self.kind.label+'展示图'
        self.append('参考版本', [purpose, label, '用户提供', '不适用'])
        self.append('参考版本', [purpose, other, label, '不适用'])
        self.append('当前采用', [purpose, label, '隔离采用', '2026-11-07T12:00:00+08:00'])
        space = SimpleNamespace(root=self.root, api=self.api, runtime=self.base/'runtime', view='chloe-commerce')

        def select(request: Request):
            request.state.workspace_space = space

        app = FastAPI()
        app.include_router(asset_router(self.kind), prefix=self.api, dependencies=[Depends(select)])
        endpoint = f'{self.api}/{self.kind.endpoint}'
        with TestClient(app) as client:
            media = client.get(endpoint).json()[0]['media']
            detail_media = client.get(f'{endpoint}/{self.identity}').json()['images'][0]['media']
            self.assertEqual(detail_media['thumbnailUrl'], media['thumbnailUrl'])
            self.assertEqual(detail_media['originalDimensions'], [1200, 1800])
            self.assertFalse(space.runtime.exists())
            original = Path(first['absolute_file']).read_bytes()
            preview = client.get(media['thumbnailUrl'])
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.headers['content-type'], 'image/webp')
            self.assertEqual(preview.headers['cache-control'], 'private, max-age=86400')
            with Image.open(BytesIO(preview.content)) as image:
                self.assertEqual((image.format, image.size), ('WEBP', (512, 768)))
            with patch('backend.chloe_thumbnails.Image.open', side_effect=AssertionError('re-encoded cached version')):
                self.assertEqual(client.get(media['thumbnailUrl']).content, preview.content)
            self.assertEqual(client.get(media['url']).content, original)
            download = client.get(media['url'], params={'download': True})
            self.assertEqual(download.content, original)
            self.assertIn('attachment', download.headers['content-disposition'])

            self.path.write_text(self.path.read_text().replace(f'| {label} | 隔离采用', f'| {other} | 隔离采用'))
            updated = client.get(endpoint).json()[0]['media']
            self.assertNotEqual(updated['thumbnailUrl'], media['thumbnailUrl'])
            with Image.open(BytesIO(client.get(updated['thumbnailUrl']).content)) as image:
                self.assertEqual(image.size, (40, 60))
            self.assertEqual(client.get(updated['url']).content, Path(second['absolute_file']).read_bytes())

    def test_access_scoped_to_referenced_files_and_clothing_identity(self):
        ref, _ = self.image('red','unlinked')
        with self.assertRaises(FileNotFoundError):
            self.file(self.root,self.identity,Path(ref['absolute_file']).relative_to(self.root).as_posix())
        with self.assertRaises(FileNotFoundError):
            self.detail(self.root,self.kind.prefix+'999',self.api)
        outside = self.base/'private.md'
        outside.write_text('private')
        (self.folder/'outside.md').symlink_to(outside)
        self.path.write_text(self.path.read_text().replace('| 来源说明 | 待核实 |','| 来源说明 | [外部](<outside.md>) |'))
        with self.assertRaises(FileNotFoundError):
            self.file(self.root,self.identity,(self.folder/'outside.md').relative_to(self.root).as_posix())
        self.assertNotIn('/outside.md',str(self.detail(self.root,self.identity,self.api)))

    def test_invalid_template_and_duplicate_identity_are_reported(self):
        text = self.path.read_text()
        self.path.write_text(text.replace('## '+self.kind.label+'信息','## 自创字段'))
        with self.assertRaisesRegex(ValueError,'章节名称'):
            self.cards(self.root,self.api)
        self.path.write_text(text)
        shutil.copytree(self.folder,self.folder.with_name(self.identity+'-重复'))
        with self.assertRaisesRegex(ValueError,'编号重复'):
            self.cards(self.root,self.api)

    def test_clothing_purpose_options_and_reference_not_adoptable(self):
        _, ref = self.image('green', 'reference')
        self.append('参考版本', [self.kind.label+'参考图', ref, '用户提供', '不适用'])
        self.assertIsNone(self.cards(self.root, self.api)[0]['media'])
        text = self.path.read_text()
        self.path.write_text(text.replace('| '+self.kind.label+'参考图 |', '| 正面 |'))
        with self.assertRaisesRegex(ValueError, self.kind.label+'用途'):
            self.detail(self.root, self.identity, self.api)
        self.path.write_text(text)
        self.append('当前采用', [self.kind.label+'参考图', ref, '错误采用', '2026-11-07T12:00:00+08:00'])
        with self.assertRaisesRegex(ValueError, '当前采用只登记'):
            self.detail(self.root, self.identity, self.api)


class ChloeHairTests(ChloeClothingTests):
    kind = HAIR

    def test_existing_project_without_hair_directory_can_be_read_and_initialized(self):
        self.path.unlink()
        self.folder.rmdir()
        self.folder.parent.rmdir()
        self.assertEqual(self.cards(self.root, self.api), [])
        self.assertEqual(check_workspace(self.root)['errors'], [])
        folder = initialize_asset(self.root, '发型', 'H001', '新增发型')
        self.assertTrue((folder/'发型说明.md').is_file())
        self.assertEqual(self.cards(self.root, self.api)[0]['id'], 'H001')


class ChloeSceneTests(ChloeClothingTests):
    kind = SCENES

    def test_non_image_scene_references_fail_document_check_and_page(self):
        original = self.path.read_text()
        samples = Path(__file__).resolve().parents[1]/'frontend/public/component-samples'
        for name in ('tone.wav', 'video.webm'):
            ref = import_media(self.root, samples/name, 'wrong-scene-'+name)
            link = f'[共用:{ref["resource_id"]}@{ref["version"]}](<{os.path.relpath(ref["absolute_file"], self.folder)}>)'
            for heading, purpose in (('参考版本', '场景参考图'), ('参考版本', '场景展示图'), ('当前采用', '场景展示图')):
                with self.subTest(media=name, heading=heading, purpose=purpose):
                    self.path.write_text(original)
                    tail = ['用户提供', '不适用'] if heading == '参考版本' else ['隔离采用', '2026-11-08T10:00:00+08:00']
                    self.append(heading, [purpose, link, *tail])
                    result = check_workspace(self.root, self.path)
                    self.assertEqual(len(result['errors']), 1)
                    self.assertIn('须引用PNG、JPEG或WebP图片', str(result['errors']))
                    with self.assertRaisesRegex(ValueError, '须引用PNG、JPEG或WebP图片'):
                        self.detail(self.root, self.identity, self.api)

    def test_scene_upstream_execution_must_exist(self):
        self.append('执行记录', ['E001', '图片生成', '不适用', 'Imagegen', '不适用', '不适用', '隔离测试', '不适用', '2026-11-08T10:00:00+08:00', '不适用', '准备中', '无'])
        self.append('执行记录', ['E002', '图片处理', 'E001', 'RTX2倍', '不适用', '不适用', '隔离测试', '不适用', '2026-11-08T10:00:00+08:00', '不适用', '准备中', '无'])
        _, link = self.image('green', 'scene')
        self.append('参考版本', ['场景展示图', link, '用户提供', 'E001'])
        self.append('当前采用', ['场景展示图', link, '隔离采用', '2026-11-08T10:00:00+08:00'])
        self.assertEqual(check_workspace(self.root, self.path)['errors'], [])
        self.assertIsNotNone(self.cards(self.root, self.api)[0]['media'])
        self.path.write_text(self.path.read_text().replace('| E002 | 图片处理 | E001 |', '| E002 | 图片处理 | E999 |'))
        result = check_workspace(self.root, self.path)
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('E002引用不存在的上游执行：E999', str(result['errors']))
        with self.assertRaisesRegex(ValueError, 'E002引用不存在的上游执行：E999'):
            self.detail(self.root, self.identity, self.api)
