import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from PIL import Image

from backend.chloe_clothing import clothing_cards, clothing_detail, clothing_file
from chloe_init import initialize_workspace, initialize_asset, SKILLS
sys.path.insert(0, str(SKILLS/'chloe-assets/scripts'))
from chloe_resources import import_media


class ChloeClothingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = initialize_workspace(self.base/'Chloe Workspace')
        self.folder = initialize_asset(self.root, '服装', 'O001', '测试服装')
        self.path = self.folder/'服装说明.md'
        self.api = '/api/workspaces/test'

    def append(self, section, row):
        text = self.path.read_text()
        start = text.index('## '+section+'\n')
        end = text.index('\n\n', text.index('| ---', start))
        self.path.write_text(text[:end]+'\n| '+' | '.join(row)+' |'+text[end:])

    def image(self, color, key, resource=None):
        path = self.base/(key+'.png')
        Image.new('RGB', (40, 60), color).save(path)
        ref = import_media(self.root, path, key, resource_id=resource)
        return ref, f'[共用:{ref["resource_id"]}@{ref["version"]}](<{os.path.relpath(ref["absolute_file"], self.folder)}>)'

    def test_empty_clothing_and_exact_adopted_cover_without_copies(self):
        self.assertIsNone(clothing_cards(self.root,self.api)[0]['media'])
        first, label = self.image('red','first')
        second, other = self.image('blue','second',first['resource_id'])
        self.append('参考版本',['正面',label,'用户提供','不适用'])
        self.append('参考版本',['正面',other,label,'不适用'])
        self.assertIsNone(clothing_cards(self.root,self.api)[0]['media'])
        self.append('当前采用',['正面',label,'隔离采用','2026-11-07T12:00:00+08:00'])
        before = {str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        detail = clothing_detail(self.root,'O001',self.api)
        card = clothing_cards(self.root,self.api)[0]
        self.assertEqual(card['media']['key'],Path(first['absolute_file']).relative_to(self.root).as_posix())
        self.assertEqual(clothing_file(self.root,'O001',card['media']['key']),Path(first['absolute_file']))
        self.assertEqual(detail['description'],'无')
        self.assertEqual([s['heading'] for s in detail['sections']][:1],['服装信息'])
        self.assertEqual(len(detail['images']),2)
        self.assertEqual(sum(image['adopted'] for image in detail['images']),1)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_access_scoped_to_referenced_files_and_clothing_identity(self):
        ref, _ = self.image('red','unlinked')
        with self.assertRaises(FileNotFoundError):
            clothing_file(self.root,'O001',Path(ref['absolute_file']).relative_to(self.root).as_posix())
        with self.assertRaises(FileNotFoundError):
            clothing_detail(self.root,'O999',self.api)
        outside = self.base/'private.md'
        outside.write_text('private')
        (self.folder/'outside.md').symlink_to(outside)
        self.path.write_text(self.path.read_text().replace('| 来源说明 | 待核实 |','| 来源说明 | [外部](<outside.md>) |'))
        with self.assertRaises(FileNotFoundError):
            clothing_file(self.root,'O001',(self.folder/'outside.md').relative_to(self.root).as_posix())
        self.assertNotIn('/outside.md',str(clothing_detail(self.root,'O001',self.api)))

    def test_invalid_template_and_duplicate_identity_are_reported(self):
        text = self.path.read_text()
        self.path.write_text(text.replace('## 服装信息','## 自创字段'))
        with self.assertRaisesRegex(ValueError,'章节名称'):
            clothing_cards(self.root,self.api)
        self.path.write_text(text)
        shutil.copytree(self.folder,self.folder.with_name('O001-重复'))
        with self.assertRaisesRegex(ValueError,'编号重复'):
            clothing_cards(self.root,self.api)
