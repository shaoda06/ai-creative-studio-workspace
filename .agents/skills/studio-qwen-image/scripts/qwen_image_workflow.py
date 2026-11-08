"""Prepare Qwen requests from explicit content and parameters; never generates content."""
import argparse
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / 'references/workflows'


def assemble(*, prompt, size, seed, mode, references=(), parameters=None,
             prefix, remote_output=None):
    """Return canvas, API, upload bindings and output node without any network call."""
    if mode not in ('t2i', 'edit') or bool(references) != (mode == 'edit'):
        raise ValueError('Qwen模式与参考输入不一致：t2i不带图，edit须带图')
    width, height = size
    if any(type(n) is not int or n <= 0 or n % 32 for n in size):
        raise ValueError('Qwen宽高须为32倍数的正整数像素')
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError('种子必须为有效非负整数')
    if (set(prompt) not in ({'rewritten_prompt', 'wh_ratio'},
                           {'rewritten_prompt', 'wh_ratio', 'ratio_follow'})
            or not prompt['rewritten_prompt'] or not prompt['wh_ratio'] or prompt.get('ratio_follow')):
        raise ValueError('任务清单须提供最终正文和明确画幅，不能同时跟随输入画幅')
    if Fraction(prompt['wh_ratio'].replace(':', '/')) != Fraction(width, height):
        raise ValueError('提示词画幅元数据与目标宽高不一致')
    if len(references) > 10:
        raise ValueError('参考图数量超过现行10图入口')
    base = 'Qwen2.1-' + ('图生图' if mode == 'edit' else '文生图') + '-普通版'
    api = json.loads((WORKFLOWS / (base + '.api.json')).read_text('utf-8-sig'))
    text, latent, sampler, encoder, output = (('680', '479', '481', '497', '487')
                                               if mode == 'edit' else ('672', '514', '515', '522', '508'))
    api[text]['inputs']['value'] = prompt['rewritten_prompt']
    api[latent]['inputs'].update(width=width, height=height)
    api[sampler]['inputs']['seed'] = seed
    for name, content in (parameters or {}).items():
        if name != 'negative_prompt':
            raise ValueError('图片任务不能覆盖固定配置：' + name)
        api[encoder]['inputs'][name] = content
    api[output]['inputs']['filename_prefix'] = prefix if remote_output is None else remote_output
    uploads = []
    for index, file in enumerate(map(Path, references)):
        loader = '475' if index == 0 else str(700 + (index - 1) * 2)
        scale = '532' if index == 0 else str(701 + (index - 1) * 2)
        if index:
            api[loader] = deepcopy(api['475'])
            api[scale] = deepcopy(api['532'])
        api[loader]['inputs']['image'] = file.name
        api[scale]['inputs']['image'] = [loader, 0]
        api[encoder]['inputs'][f'images.image_{index + 1}'] = [scale, 0]
        uploads.append(dict(file=str(file), node=loader, input='image', subfolder=prefix,
                            **{'response-name': prefix + f'-上传响应-{index + 1:03d}.json'}))
    return None, api, uploads, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, help='UTF-8 JSON: prompt/size/seed/mode/prefix及可选references/parameters/remote_output；文件路径相对当前目录')
    parser.add_argument('--output', required=True, help='新建装配结果JSON，不覆盖已有文件；只准备，不上传或提交')
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text('utf-8-sig'))
    canvas, api, uploads, output = assemble(**request)
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(dict(canvas=canvas, workflow=api, uploads=uploads, output_node=output),
                  stream, ensure_ascii=False, indent=2)


def execution_facts(api, *, size, has_references):
    """Describe actual Qwen parameters for callers, without a business record format."""
    sampler = next(node['inputs'] for node in api.values() if node['class_type'] == 'KSampler')
    encoder = next(node['inputs'] for node in api.values() if node['class_type'] == 'TextEncodeQwenImage21')
    models = [node['inputs'][field] for node in api.values()
              for field in ('unet_name', 'clip_name', 'vae_name') if field in node['inputs']]
    parameters = '、'.join(str(sampler[name]) for name in ('seed', 'steps', 'cfg', 'sampler_name', 'scheduler'))
    caches = [node['inputs'] for node in api.values() if node['class_type'] == 'QwenImage21Cache']
    cache_text = '；'.join(f"缓存device={cache['device']}、dtype={cache['dtype']}" for cache in caches) or '无缓存节点'
    acceleration = [node['inputs'] for node in api.values() if node['class_type'] == 'TESpeedQwenImage21']
    if acceleration:
        cache_text += '；TE加速：' + json.dumps({key: value for key, value in acceleration[0].items() if key != 'model'}, ensure_ascii=False)
    width, height = size
    preprocessing = (f"每张参考图lanczos缩放至1.5MP、32对齐；编码器resolution={encoder['resolution']}；API节点479直接设置宽高"
                     if has_references else '无输入参考；API节点514直接设置宽高')
    return dict(sampler=sampler, encoder=encoder, models=models, parameters=parameters,
                cache_text=cache_text, preprocessing=f'明确{width}×{height}；' + preprocessing)


if __name__ == '__main__':
    main()
