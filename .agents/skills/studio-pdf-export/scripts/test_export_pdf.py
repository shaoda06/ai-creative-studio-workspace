"""Real browser/PDF boundary checks; run with the export runtime and NODE_PATH set."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pypdf import PdfReader
from export_pdf import norm


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'source.md'
        self.output = self.root/'result.pdf'
        self.profile = self.root/'profile.json'
        self.profile.write_text(json.dumps({'font_pt': 10.5, 'watermark': {'text': '旧配置测试标记'}}, ensure_ascii=False))

    def run_export(self, *options):
        command = [sys.executable, str(Path(__file__).with_name('export_pdf.py')),
                   '--source', str(self.source), '--layout', 'text',
                   '--output', str(self.output), '--node', os.environ.get('PDF_NODE', 'node')]
        return subprocess.run([*command, *options], capture_output=True, text=True)

    def test_actual_chinese_pdf_text_roundtrip(self):
        self.source.write_text('# 中文提取回归\n\n检查长正文分页，保留真实内容。\n')
        result = self.run_export()
        self.assertEqual(result.returncode,0,result.stderr)
        text = norm(PdfReader(self.output).pages[0].extract_text())
        self.assertIn('检查长正文分页,保留真实内容。',text)
        self.assertIn('1/1',text)
        self.assertFalse(list(self.root.glob('.pdf-export-*')))
        self.assertFalse(list(self.root.rglob('*.html')))

    def test_legacy_watermark_profile_only_applies_layout(self):
        self.source.write_text('# 中文排版\n\n保留排版配置。\n')
        result = self.run_export('--profile', str(self.profile))
        self.assertEqual(result.returncode, 0, result.stderr)
        text = norm(PdfReader(self.output).pages[0].extract_text())
        self.assertNotIn('旧配置测试标记', text)
        report = json.loads(self.output.with_suffix('.检查.json').read_text())
        self.assertEqual(report['config']['font_pt'], 10.5)
        self.assertNotIn('watermark', report['config'])

    def test_missing_actual_image_cannot_succeed(self):
        content = '# 缺图测试\n\n![缺图](not-present.png)\n'
        self.source.write_text(content)
        result = self.run_export()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.source.read_text(),content)
        self.assertFalse(list(self.root.glob('.pdf-export-*')))
        self.assertFalse(list(self.root.rglob('*.html')))

    def test_existing_output_is_preserved(self):
        self.source.write_text('# 原版本保护\n')
        self.output.write_bytes(b'original-version')
        result = self.run_export()
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.output.read_bytes(),b'original-version')


if __name__ == '__main__':
    unittest.main()
