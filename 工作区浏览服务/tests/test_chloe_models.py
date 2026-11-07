import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from PIL import Image

from backend.chloe_models import model_cards, portrait_file
from chloe_init import initialize_workspace, initialize_asset, SKILLS
sys.path.insert(0, str(SKILLS/'chloe-assets/scripts'))
from chloe_resources import import_media


class ChloeModelsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.root = initialize_workspace(self.base/'Chloe Workspace')
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
