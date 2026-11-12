import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from PIL import Image

from backend.chloe_models import model_cards, portrait_file, model_detail, model_file, router
from chloe_init import initialize_workspace, initialize_project, initialize_asset, SKILLS
sys.path.insert(0, str(SKILLS/'chloe-assets/scripts'))
from chloe_resources import import_media


class ChloeModelsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.root = initialize_project(initialize_workspace(self.base/'Chloe Workspace'), '隔离样例')
        self.model = initialize_asset(self.root, '模特', 'M001', '示例模特甲')
        self.path = self.model/'模特说明.md'
        self.api = '/api/workspaces/test'

    def add_image(self, color, key, resource_id=None):
        path = self.base/(key+'.png')
        Image.new('RGB', (32, 48), color).save(path)
        ref = import_media(self.root, path, key, resource_id=resource_id)
        relative = Path(os.path.relpath(ref['absolute_file'], self.model)).as_posix()
        label = f'[共用:{ref["resource_id"]}@{ref["version"]}](<{relative}>)'
        return ref, label

    def append(self, section, row):
        text = self.path.read_text()
        start = text.index('## '+section+'\n')
        end = text.index('\n\n', text.index('| ---', start))
        self.path.write_text(text[:end]+'\n| '+' | '.join(row)+' |'+text[end:])

    def test_models_are_objects_not_candidate_images(self):
        _, first = self.add_image('red', 'first')
        _, second = self.add_image('blue', 'second')
        self.append('参考版本', ['正面面部', first, '用户提供', '不适用'])
        self.append('参考版本', ['正面面部', second, '用户提供', '不适用'])
        initialize_asset(self.root, '模特', 'M002', '示例模特乙')
        cards = model_cards(self.root, self.api)
        self.assertEqual([c['id'] for c in cards], ['M001', 'M002'])
        self.assertTrue(all(c['media'] is None for c in cards))
        self.assertEqual(cards[0]['features']['面部特征'], '待确定')

    def test_adopted_portrait_uses_exact_original_without_copy(self):
        first, label = self.add_image('red', 'first')
        second, _ = self.add_image('blue', 'second', first['resource_id'])
        self.append('当前采用', ['正面面部', label, '隔离示例采用', '2026-11-07T12:00:00+08:00'])
        before = sorted(str(p) for p in self.root.rglob('*'))
        card = model_cards(self.root, self.api)[0]
        self.assertTrue(card['media']['url'].endswith('/'+first['resource_id']+'/'+first['version']))
        self.assertEqual(portrait_file(self.root, 'M001', first['resource_id'], first['version']), Path(first['absolute_file']))
        with self.assertRaises(FileNotFoundError):
            portrait_file(self.root, 'M001', second['resource_id'], second['version'])
        self.assertEqual(sorted(str(p) for p in self.root.rglob('*')), before)

    def test_detail_keeps_candidates_and_exact_originals(self):
        first, first_label = self.add_image('red', 'first')
        second, second_label = self.add_image('blue', 'second', first['resource_id'])
        original, original_label = self.add_image('green', 'original')
        for purpose, label, parent in [('正面面部', first_label, '用户提供'), ('正面面部', second_label, first_label),
                                      ('全身三视图原图', original_label, first_label)]:
            self.append('参考版本', [purpose, label, parent, '不适用'])
        self.append('当前采用', ['正面面部', first_label, '用户选定', '2026-11-07T12:00:00+08:00'])
        self.append('当前采用', ['全身三视图原图', original_label, '用户选定', '2026-11-07T12:00:00+08:00'])
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        value = model_detail(self.root, 'M001', self.api)
        self.assertEqual(len(value['images']), 3)
        self.assertEqual(sum(i['adopted'] for i in value['images']), 2)
        card = model_cards(self.root, self.api)[0]
        for image in value['images']:
            media = image['media']
            if image['purpose'] == '正面面部' and image['adopted']:
                self.assertEqual(media['thumbnailUrl'], card['media']['thumbnailUrl'])
                self.assertNotEqual(media['url'], card['media']['url'])
            else:
                self.assertEqual(media['thumbnailUrl'].split('?')[0], media['url'])
            if image['adopted']:
                self.assertEqual(media['originalDimensions'], [32, 48])
        candidate = next(i for i in value['images'] if i['purpose'] == '正面面部' and i['version'] == second['version'])
        self.assertFalse(candidate['adopted'])
        self.assertIn('/shared-models/M001/files/', candidate['sourceHtml'])
        self.assertEqual(card['version'], first['version'])
        self.assertEqual(model_file(self.root, 'M001', Path(second['absolute_file']).relative_to(self.root).as_posix()), Path(second['absolute_file']))
        self.assertEqual({str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, before)
        unlinked, _ = self.add_image('yellow', 'unlinked')
        with self.assertRaises(FileNotFoundError):
            model_file(self.root, 'M001', unlinked['file'])
        with self.assertRaises(FileNotFoundError):
            model_detail(self.root, 'M999', self.api)

    def test_linked_files_do_not_expose_external_documents(self):
        outside = self.base/'private.md'
        outside.write_text('private')
        linked = self.model/'outside.md'
        linked.symlink_to(outside)
        self.path.write_text(self.path.read_text().replace('| 来源说明 | 待核实 |', '| 来源说明 | [外部](<outside.md>) |'))
        value = model_detail(self.root, 'M001', self.api)
        self.assertNotIn('/outside.md', str(value))
        with self.assertRaises(FileNotFoundError):
            model_file(self.root, 'M001', linked.relative_to(self.root).as_posix())

    def test_model_looks_are_scoped_without_copying_or_showing_identity(self):
        initialize_asset(self.root, '模特', 'M002', '另一模特')
        for model_id, model_name, look_id in [('M001', '示例模特甲', 'L001'), ('M002', '另一模特', 'L002')]:
            folder = initialize_asset(self.root, '造型', look_id, '测试造型')
            path = folder/'造型说明.md'
            text = path.read_text().replace('| 模特编号 | 待确定 |', f'| 模特编号 | {model_id} |')
            start = text.index('## 关联资料')
            end = text.index('\n\n', text.index('| ---', start))
            row = f'\n| 模特 | {model_id} | [说明](<../../AI模特/{model_id}-{model_name}/模特说明.md>) | 造型人物 |'
            path.write_text(text[:end]+row+text[end:])
        look_path = self.root/'综合资料/共用素材/造型/L001-测试造型/造型说明.md'
        first, _ = self.add_image('red', 'look-original')
        second, _ = self.add_image('black', 'look-masked')
        face, _ = self.add_image('white', 'look-face')
        self.path = look_path
        for purpose, ref in [('全身三视图原图', first), ('全身三视图遮面版', second), ('造型面部三视图', face)]:
            label = f'[共用:{ref["resource_id"]}@{ref["version"]}](<{os.path.relpath(ref["absolute_file"], look_path.parent)}>)'
            self.append('当前采用', [purpose, label, '隔离采用', '2026-11-07T12:00:00+08:00'])
        before = {str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        detail = model_detail(self.root, 'M001', self.api)
        self.assertEqual([x['id'] for x in detail['looks']], ['L001'])
        look = detail['looks'][0]
        self.assertEqual(look['status'], '制作中')
        self.assertEqual(len(look['images']), 3)
        face_image = next(image for image in look['images'] if image['purpose'] == '造型面部三视图')
        self.assertTrue(face_image['adopted'])
        self.assertEqual((face_image['resource'], face_image['version']), (face['resource_id'], face['version']))
        self.assertEqual(model_file(self.root, 'M001', face_image['media']['key']), Path(face['absolute_file']))
        self.assertEqual(look['media']['key'], Path(first['absolute_file']).relative_to(self.root).as_posix())
        full_body = next(image for image in look['images'] if image['purpose'] == '全身三视图原图')
        self.assertEqual(look['media']['thumbnailUrl'], full_body['media']['thumbnailUrl'])
        self.assertEqual(detail['images'], [])
        self.assertIn('造型信息', [x['heading'] for x in look['sections']])
        self.assertNotIn('资产身份', [x['heading'] for x in look['sections']])
        self.assertEqual(model_file(self.root, 'M001', look['media']['key']), Path(first['absolute_file']))
        self.assertNotIn('资产身份', [x['heading'] for x in detail['sections']])
        self.assertEqual(model_file(self.root,'M001','综合资料/共用素材/造型/L001-测试造型/造型说明.md').name,'造型说明.md')
        with self.assertRaises(FileNotFoundError):
            model_file(self.root,'M001','综合资料/共用素材/造型/L002-测试造型/造型说明.md')
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        text=look_path.read_text()
        look_path.write_text('\n'.join(line for line in text.splitlines() if not line.startswith('| 全身三视图原图 |'))+'\n')
        self.assertIsNone(model_detail(self.root,'M001',self.api)['looks'][0]['media'])

    def test_look_clothing_inputs_keep_exact_versions_and_multiple_references(self):
        folder = initialize_asset(self.root, '造型', 'L001', '测试造型')
        self.path = folder/'造型说明.md'
        self.path.write_text(self.path.read_text().replace('| 模特编号 | 待确定 |','| 模特编号 | M001 |'))
        self.append('关联资料',['模特','M001','[模特](<../../AI模特/M001-示例模特甲/模特说明.md>)','所属模特'])
        first, _ = self.add_image('yellow', 'clothing-first')
        second, _ = self.add_image('orange', 'clothing-second', first['resource_id'])
        for execution in ['E001','E002']:
            self.append('执行记录',[execution,'图片生成','不适用','隔离测试','测试','不适用','隔离测试','未取得','未取得','未取得','准备中','未取得'])
        for slot, ref, execution, purpose in [('1',first,'E001','服装参考'),('2',second,'E001','配饰参考'),('1',first,'E002','服装参考'),('3',second,'E002','模特参考')]:
            label = f'[共用:{ref["resource_id"]}@{ref["version"]}](<{os.path.relpath(ref["absolute_file"], folder)}>)'
            self.append('输入记录',[execution,slot,purpose,'不适用',label])
        before = {str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        clothing = model_detail(self.root,'M001',self.api)['looks'][0]['clothing']
        self.assertEqual(len(clothing),2)
        self.assertEqual(clothing[0]['reference'],first['resource_id']+'@V001')
        self.assertEqual(clothing[1]['reference'],second['resource_id']+'@V002')
        self.assertTrue(clothing[1]['media']['name'].startswith('配饰参考'))
        self.assertEqual(clothing[0]['executions'],['E001','E002'])
        self.assertEqual(model_file(self.root,'M001',clothing[0]['media']['key']),Path(first['absolute_file']))
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        space = SimpleNamespace(root=self.root, api=self.api, runtime=self.base/'runtime', view='chloe-commerce')

        def select(request: Request):
            request.state.workspace_space = space

        app = FastAPI()
        app.include_router(router, prefix=self.api, dependencies=[Depends(select)])
        with TestClient(app) as client:
            for item, ref in zip(clothing, (first, second)):
                media = item['media']
                thumbnail = client.get(media['thumbnailUrl'])
                self.assertEqual(thumbnail.status_code, 200)
                self.assertEqual(thumbnail.headers['content-type'], 'image/webp')
                download = client.get(media['url'], params={'download': True})
                self.assertEqual(download.content, Path(ref['absolute_file']).read_bytes())
            self.assertNotEqual(clothing[0]['media']['thumbnailUrl'], clothing[1]['media']['thumbnailUrl'])
            self.assertEqual(client.get(clothing[0]['media']['thumbnailUrl'].replace('/M001/', '/M002/')).status_code, 404)
        good = self.path.read_text()
        self.path.write_text(good.replace('| 服装参考 |','| 猜测用途 |'))
        with self.assertRaisesRegex(ValueError,'输入用途'):
            model_detail(self.root,'M001',self.api)
        self.path.write_text(good)
        self.append('输入记录',['E002','4','服装参考','不适用','未取得'])
        with self.assertRaisesRegex(ValueError,'服装参考须引用'):
            model_detail(self.root,'M001',self.api)

    def test_empty_and_invalid_document(self):
        self.path.unlink()
        self.assertEqual(model_cards(self.root, self.api), [])
        initialize_asset(self.root, '模特', 'M001', '示例模特甲')
        self.path.write_text(self.path.read_text().replace('## 人物特征', '## 临时字段'))
        with self.assertRaisesRegex(ValueError, '章节名称'):
            model_cards(self.root, self.api)

    def test_duplicate_identity_and_external_document_are_rejected(self):
        duplicate = self.model.with_name('M001-重复')
        shutil.copytree(self.model, duplicate)
        with self.assertRaisesRegex(ValueError, '编号重复'):
            model_cards(self.root, self.api)
        shutil.rmtree(duplicate)
        external = self.base/'private.md'
        self.path.rename(external)
        self.path.symlink_to(external)
        with self.assertRaisesRegex(ValueError, '越出'):
            model_cards(self.root, self.api)


if __name__ == '__main__':
    unittest.main()
