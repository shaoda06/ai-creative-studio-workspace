"""Model and look documents accept only their established image categories."""
from pathlib import Path
import unittest
from chloe_documents import check_relations


class ImagePurposesTest(unittest.TestCase):
    def test_allowed_categories_and_unknown_category_rejection(self):
        root = Path('/isolated-chloe')
        for filename, purposes, retired in (
            ('模特说明.md', ['正面面部', '全身三视图原图'], ['面部三视图', '造型面部三视图', '全身三视图遮面版']),
            ('造型说明.md', ['造型面部三视图', '全身三视图原图', '全身三视图遮面版'], ['面部三视图', '正面面部']),
        ):
            for heading in ('参考版本', '当前采用'):
                rejected = retired + ['未定义图种']
                for purpose in purposes + [purposes[0]+'/对照'] + rejected:
                    with self.subTest(file=filename, heading=heading, purpose=purpose):
                        columns = ['用途', '资源引用', '采用依据', '采用时间', '执行编号']
                        row = [purpose, '准确引用', '用户批准', '2026-11-07T12:00:00+08:00', '不适用']
                        doc = {'sections': [{'heading': heading, 'tables': [{'columns': columns, 'rows': [row]}]}]}
                        path = root/'综合资料'/filename
                        if purpose in rejected:
                            with self.assertRaisesRegex(ValueError, '图片用途不在固定图种内'):
                                check_relations(root, path, doc)
                        else:
                            check_relations(root, path, doc)


if __name__ == '__main__':
    unittest.main()
