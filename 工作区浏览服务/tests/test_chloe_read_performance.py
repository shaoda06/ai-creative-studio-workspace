"""Read projections stay scoped, invalidate correctly and avoid repeated validation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.chloe_overview import fields
from backend import chloe_read_cache as cache
from backend.chloe_models import model_detail, model_file, model_sources
from backend.services.read_views import ReadViews, snapshot
from tests import test_chloe_models as model_fixtures
from chloe_init import initialize_asset
from chloe_documents import template
import project_resources as resources


class ChloeReadPerformanceTests(unittest.TestCase):
    setUp = model_fixtures.ChloeModelsTests.setUp
    add_image = model_fixtures.ChloeModelsTests.add_image
    append = model_fixtures.ChloeModelsTests.append

    def read_model(self):
        return cache.read_document(self.root, self.path, template('chloe-assets', '模特说明模板.md'),
                                   {'identity': 'M001', 'title': '示例模特甲'})

    def test_validated_document_reuses_only_its_actual_versions(self):
        ref, label = self.add_image('red', 'first')
        self.append('参考版本', ['正面面部', label, '用户提供', '不适用'])
        with patch.object(cache, 'validate_document', wraps=cache.validate_document) as validate:
            self.read_model()
            self.read_model()
            self.add_image('blue', 'unrelated')
            self.read_model()
            self.assertEqual(validate.call_count, 1)
            self.path.write_text(self.path.read_text().replace('| 面部特征 | 待确定 |', '| 面部特征 | 新特征 |'))
            self.assertEqual(fields(self.read_model(), '人物特征')['面部特征'], '新特征')
            self.assertEqual(validate.call_count, 2)
            metadata = Path(ref['absolute_file']).with_name('版本信息.json')
            metadata.unlink()
            with self.assertRaises(ValueError):
                self.read_model()

    def test_changed_resource_index_mapping_is_not_hidden_by_cache(self):
        ref, label = self.add_image('red', 'first')
        self.append('参考版本', ['正面面部', label, '用户提供', '不适用'])
        self.read_model()
        with resources.edit_index(self.root / '综合资料') as index:
            index['files'][ref['file']]['version'] = 'V999'
        with self.assertRaises(FileNotFoundError):
            self.read_model()

    def test_model_view_and_media_do_not_visit_unrelated_looks(self):
        ref, label = self.add_image('red', 'first')
        self.append('参考版本', ['正面面部', label, '用户提供', '不适用'])
        before = model_sources(self.root, 'M001', 'base')
        initialize_asset(self.root, '造型', 'L001', '无关造型')
        self.assertEqual(before, model_sources(self.root, 'M001', 'base'))
        with patch('backend.chloe_models.model_looks', side_effect=AssertionError('unrelated looks read')):
            detail = model_detail(self.root, 'M001', self.api, 'base')
            self.assertEqual(detail['looks'], [])
            self.assertFalse(any(section['heading'] == '执行记录' for section in detail['sections']))
            self.assertEqual(model_file(self.root, 'M001', '综合资料/' + ref['file']), Path(ref['absolute_file']))

    def test_file_roots_invalidate_on_atomic_replacement_and_missing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.json'
            path.write_text('one')
            views = ReadViews()
            build = lambda: path.read_text()
            self.assertEqual(views.read('file', [path], build)[0], 'one')
            temporary = path.with_suffix('.tmp')
            temporary.write_text('two')
            temporary.replace(path)
            self.assertEqual(views.read('file', [path], build)[0], 'two')
            path.unlink()
            self.assertEqual(snapshot([path]), {path: None})

    def test_catalog_validates_files_for_the_current_page_not_every_history(self):
        from backend.chloe_reference_assets import asset_rows, ACCESSORIES
        from backend.chloe_asset_pages import asset_page, AssetPage
        for number in range(1, 15):
            directory = initialize_asset(self.root, '配饰', f'C{number:03d}', f'隔离配饰{number}')
        path = directory / '配饰说明.md'
        text = path.read_text()
        header = '| 用途 | 资源引用 | 来源或原图引用 | 执行编号 |\n| --- | --- | --- | --- |'
        path.write_text(text.replace(header, header+'\n| 配饰参考图 | [共用:IMG-missing@V001](<missing.png>) | 用户提供 | 不适用 |'))
        with patch.object(cache, 'validate_document', wraps=cache.validate_document) as validate:
            rows = asset_rows(self.root, self.api, ACCESSORIES)
            result = asset_page(rows, AssetPage(page=1))
            self.assertEqual(len(result['items']), 12)
            full = [call for call in validate.call_args_list if call.kwargs.get('check_references', True)]
            self.assertEqual(len(full), 12)
            with self.assertRaises((ValueError, FileNotFoundError)):
                asset_page(rows, AssetPage(page=2))

    def test_persistent_read_view_restarts_without_rebuilding_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.md'
            source.write_text('one')
            cache_file = Path(folder) / 'runtime/cache.json'
            data, revision = ReadViews().read('catalog', [source], lambda: {'value': 'one'}, cache_file=cache_file)
            restored, restored_revision = ReadViews().read('catalog', [source],
                lambda: self.fail('rebuilt unchanged sources after restart'), cache_file=cache_file)
            self.assertEqual((restored, restored_revision), (data, revision))
            source.write_text('changed')
            changed, _ = ReadViews().read('catalog', [source], lambda: {'value': 'changed'}, cache_file=cache_file)
            self.assertEqual(changed['value'], 'changed')


if __name__ == '__main__':
    unittest.main()
