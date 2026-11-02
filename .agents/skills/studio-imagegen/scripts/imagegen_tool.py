"""Native Imagegen call preparation and original-file preservation, without business records."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-image-processing/scripts'))
from image_files import png

EXECUTOR = {'model': 'gpt-6-luna', 'reasoning_effort': 'medium', 'fork_turns': 'none'}


def validate_inputs(prompt, references):
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError('Imagegen需要完整实际提示词')
    if len(references) > 5:
        raise ValueError('内置Imagegen最多接收5张参考图，请先按实际用途精简输入')


def generation_call(prompt, references, result_store_key):
    validate_inputs(prompt, references)
    arguments = {'prompt': prompt}
    if references:
        arguments['referenced_image_paths'] = [str(file) for file in references]
    return ('// @exec: {"yield_time_ms": 120000, "max_output_tokens": 1000}\n'
            'const imagegenResult = await tools.image_gen__imagegen(' + json.dumps(arguments, ensure_ascii=False) + ');\n'
            'store(' + json.dumps(result_store_key, ensure_ascii=False) + ', imagegenResult);\n'
            'generatedImage(imagegenResult);\n')


def preserve_original(source, destination):
    """Copy the actual native PNG unchanged and return its measured facts."""
    source, destination = Path(source), Path(destination)
    raw = source.read_bytes()
    width, height = png(raw)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != raw:
            raise ValueError('候选文件已有不同内容，不覆盖')
    else:
        with destination.open('xb') as stream:
            stream.write(raw)
    return dict(width=width, height=height, bytes=len(raw), format='PNG', decoded=True)
