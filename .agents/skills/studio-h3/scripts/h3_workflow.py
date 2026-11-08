"""H3 canvas conversion and explicit media-slot binding; no business paths."""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-comfyui/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-video-processing/scripts'))
from video_workflow import configure_postprocess
import workflow_graph as pairs
from project_paths import project_file, input_file

def configure_first_pass(canvas, spec):
    """Apply explicit six-step answers to a fresh standard H3 first-pass task."""
    choice = spec['h3_first_pass']
    if spec['task_type'] != 'video-first-pass':
        raise ValueError('h3_first_pass仅用于新一采；二采及后处理保留来源配置')
    required = {'aspect_ratio', 'width', 'height', 'steps', 'refine_steps', 'scene_type', 'speed', 'loras'}
    if set(choice) != required:
        raise ValueError('h3_first_pass须完整提供比例、宽高、一采steps、二采refine_steps、文戏/打戏、速度及附加LoRA')
    width, height, steps = choice['width'], choice['height'], choice['steps']
    tail = choice['refine_steps']
    if any(type(v) is not int or v <= 0 for v in (width, height, steps, tail)):
        raise ValueError('宽、高及一采、二采步数须为正整数')
    if width % 32 or height % 32:
        raise ValueError('一采宽高须为32的整数倍；请确认尺寸，不自动取整')
    ratio = choice['aspect_ratio']
    if not isinstance(ratio, str) or len(ratio.split(':')) != 2 or not all(v.isdigit() and int(v) > 0 for v in ratio.split(':')):
        raise ValueError('比例须为正整数之比，例如16:9')
    a, b = map(int, ratio.split(':'))
    if width * b != height * a:
        raise ValueError('分辨率与所选比例不符；请确认比例或尺寸')
    scene = choice['scene_type']
    if scene not in ('dialogue', 'combat'):
        raise ValueError('scene_type须为dialogue或combat')
    speed = choice['speed']
    if type(speed) not in (int, float) or not math.isfinite(speed) or not -10 <= speed <= 10:
        raise ValueError('动作速度须为-10～10之间的数值')
    loras = choice['loras']
    if not isinstance(loras, list) or any(type(v) is not int or v not in (1, 2) for v in loras) or len(set(loras)) != len(loras):
        raise ValueError('附加LoRA使用不重复的编号1、2；不启用时传空列表')
    nodes = {n['id']: n for n in canvas['nodes']}
    combat = scene == 'combat'
    widget(canvas, nodes[261], steps=steps + tail)
    widget(canvas, nodes[289], step=steps)
    # The external SIGMAS link remains authoritative; do not disconnect it.
    widget(canvas, nodes[502], steps=steps, width=width, height=height)
    widget(canvas, nodes[343], strength_model=speed)
    nodes[343]['mode'] = 0
    for node, enabled in ((128, 1 in loras), (507, 2 in loras), (342, combat), (344, combat), (345, combat)):
        nodes[node]['mode'] = 0 if enabled else 4
    for node, weight in ((128, .5), (507, .8), (342, .65), (344, .35), (345, .35)):
        widget(canvas, nodes[node], strength_model=weight)
    timeline = json.loads(nodes[502]['widgets_values_named']['timeline_data'])
    timeline.update(width=width, height=height)
    divisor = math.gcd(a, b)
    ratio = f'{a // divisor}:{b // divisor}'
    label = {'16:9': '16:9 (宽屏)', '9:16': '9:16 (竖屏)'}.get(ratio, ratio)
    timeline['output'].update(mode='fixed', width=width, height=height,
        aspectRatio=label, longEdge=max(width, height), megapixels=width * height / 1024 ** 2, multiple=32)
    widget(canvas, nodes[502], timeline_data=json.dumps(timeline, ensure_ascii=False))
    # Refine is a linked preset, not authorization to execute the second pass.
    mp = 1.9921875 if combat else 1.265625
    pixels = mp * 1024 ** 2
    refine_width = max(32, round(math.sqrt(pixels * width / height) / 32) * 32)
    refine_height = max(32, round(math.sqrt(pixels * height / width) / 32) * 32)
    widget(canvas, nodes[407], megapixels=mp, width=refine_width, height=refine_height, confirm_first_pass=True)
    return {**deepcopy(choice), 'aspect_ratio': ratio,
        'sampling': {'total_steps': steps + tail, 'split_step': steps,
                     'first_pass_with_zero': steps + 1, 'refine_tail_steps': tail}}

def configure_second_pass(canvas, spec):
    """Change only Refine resolution on the supplied approved first-pass source."""
    if spec['task_type'] != 'video-second-pass':
        raise ValueError('h3_second_pass仅用于二采接续')
    choice = spec['h3_second_pass']
    if set(choice) != {'width', 'height'}:
        raise ValueError('h3_second_pass只接受二采width和height，不接受步数或LoRA覆盖')
    width, height = choice['width'], choice['height']
    if any(type(v) is not int or v <= 0 or v % 32 for v in (width, height)):
        raise ValueError('二采宽高须为正整数且为32的整数倍；不自动裁切或取整')
    nodes = {n['id']: n for n in canvas['nodes']}
    director = nodes[502]['widgets_values_named']
    refine = nodes[407]['widgets_values_named']
    if refine['mode'] != 'upscale' or refine['aspect_ratio'] != '跟随导演台' or not refine['confirm_first_pass']:
        raise ValueError('分辨率装配需要upscale、跟随导演台比例且开启一采确认的来源工作流')
    ratio = director['width'] / director['height']
    # Intersect the pixel-area intervals that round to both requested dimensions.
    # Width*height gives the standard MP values; small/custom targets may need
    # an interior area instead because Refine derives both sides from the ratio.
    lower = max(0 if width == 32 else (width - 16) ** 2 / ratio,
                0 if height == 32 else (height - 16) ** 2 * ratio)
    upper = min((width + 16) ** 2 / ratio, (height + 16) ** 2 * ratio)
    if lower >= upper:
        raise ValueError('二采尺寸无法按来源比例对齐32得到；请重新选择分辨率，不改一采比例')
    pixels = width * height
    if not lower < pixels < upper:
        pixels = (lower + upper) / 2
    mp = pixels / 1024 ** 2
    widget(canvas, nodes[407], width=width, height=height, megapixels=mp)
    return {'width': width, 'height': height, 'megapixels': mp}


def widget(graph, node, **values):
    named = node['widgets_values_named']
    for key, content in values.items():
        if key not in named:
            raise ValueError('基准不存在控件：' + key)
        slot = next((i for i in node.get('inputs', []) if i['name'] == key), None)
        if slot and slot.get('link') is not None:
            disconnect(graph, slot)
        named[key] = content
    if isinstance(node['widgets_values'], dict):
        node['widgets_values'].update(values)
    else:
        node['widgets_values'] = list(named.values())


def disconnect(graph, slot):
    key = slot['link']
    if key is None:
        return
    link = next(pairs.link_tuple(link) for link in graph['links'] if pairs.link_tuple(link)[0] == key)
    origin = next(n for n in graph['nodes'] if n['id'] == link[1])
    origin['outputs'][link[2]]['links'].remove(key)
    graph['links'] = [item for item in graph['links'] if pairs.link_tuple(item)[0] != key]
    slot['link'] = None


def reference_bindings(api, references, subfolder, existing=()):
    uploads = list(existing)
    timelines = {key: json.loads(node['inputs']['timeline_data']) for key,node in api.items() if node['class_type']=='MiniMaxH3Director'}
    for ref in {item['placeholder']: item for item in references}.values():
        file = Path(ref['file'])
        placeholder, matched = ref['placeholder'], False
        for key, node in api.items():
            for name, content in node['inputs'].items():
                slots = []
                if content == placeholder:
                    slots.append(None)
                elif node['class_type'] == 'MiniMaxH3Director' and name == 'timeline_data':
                    timeline = timelines[key]
                    for area, block in [(['global'], timeline['global']), *[(['segments', i], item) for i, item in enumerate(timeline['segments'])]]:
                        for array, field in [('refs', 'imageFile'), ('refVideos', 'videoFile'), ('refAudios', 'audioFile')]:
                            for index, item in enumerate(block.get(array, [])):
                                if item.get(field) == placeholder:
                                    slots.append(area + [array, index, field])
                for path in slots:
                    upload = dict(file=str(file), node=key, input=name, subfolder=subfolder,
                                  **{'response-name': f'上传响应-{len(uploads)+1:03d}.json'})
                    if path is not None:
                        upload['json-path'] = path
                    uploads.append(upload)
                    matched = True
        if not matched:
            raise ValueError('视频参考未对应实际画布槽位：' + placeholder)
    return uploads

def prepare_technical(root, spec, documents):
    record = project_file(root, spec['record_dir'])
    if 'video_postprocess' in spec:
        canvas, postprocess = configure_postprocess(root, spec)
    else:
        canvas = json.loads(project_file(root, spec['canvas']).read_text('utf-8-sig'))
    if 'h3_first_pass' in spec:
        configure_first_pass(canvas, spec)
    if 'h3_second_pass' in spec:
        configure_second_pass(canvas, spec)
    api = pairs.Canvas(canvas).api(spec['output_nodes'])
    refs = [{**item, 'file': str(input_file(root, item['file']))} for item in spec.get('references', [])]
    uploads = reference_bindings(api, refs, record.name, spec.get('uploads', []))
    documents.new_json(record / '任务.workflow.json', canvas)
    documents.new_json(record / '任务.api.json', api)
    return dict(project=str(root), task_type=spec['task_type'], title=spec['title'], workflow=api,
                record_dir=str(record), video_plan=spec['video_plan'], submission_plan=spec.get('submission_plan'),
                uploads=uploads, outputs=spec.get('outputs', []), segment_plan=spec.get('segment_plan'),
                attempt_name='提交尝试.json', request_name='请求.json', response_name='提交响应.json', history_name='执行结果.json')
