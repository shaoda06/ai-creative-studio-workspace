import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from imagegen_tool import generation_call


class ImagegenHandoffTests(unittest.TestCase):
    def test_call_preserves_unicode_and_order_through_terminal_output(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            references = [root / '模特 (1).PNG', root / '参考图 𠮷.png']
            for reference in references:
                reference.touch()
            prompt = '沿用「参考图」\n第二行 𠮷'
            code = generation_call(prompt, references, '执行记录')

        # A terminal reading UTF-8 can receive this from a GBK Python process.
        transported = code.encode('gbk').decode('utf-8')
        call, storage = transported.splitlines()[1:3]
        arguments = json.loads(call.split('image_gen__imagegen(', 1)[1].removesuffix(');'))
        self.assertEqual(arguments, {'prompt': prompt, 'referenced_image_paths': list(map(str, references))})
        self.assertEqual(json.loads(storage.removeprefix('store(').removesuffix(', imagegenResult);')), '执行记录')

    def test_wrong_base_and_non_file_references_stop_before_call_is_prepared(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                generation_call('原提示词', ['资源/图片/参考图.png'], 'test')
            with self.assertRaises(FileNotFoundError):
                generation_call('原提示词', [root / '错误基准/参考图.png'], 'test')
            with self.assertRaises(FileNotFoundError):
                generation_call('原提示词', [root], 'test')
