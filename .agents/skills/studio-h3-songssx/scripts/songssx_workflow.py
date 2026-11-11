"""Offline assembly of the registered Songssx SelfLift scene workflow."""
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import sys

SKILLS = Path(__file__).resolve().parents[2]
for skill in ('studio-comfyui', 'studio-h3'):
    sys.path.insert(0, str(SKILLS / skill / 'scripts'))
from project_paths import input_file, project_file
from workflow_graph import Canvas
from workflow_paths import workflow_file
from h3_prompt_format import PROMPT_CHARACTER_LIMIT, format_findings

WORKFLOW = 'songssx-selflift'
TASK_TYPE = 'video-scene-generation'
FPS = 24
MAX_GEN_FRAMES = 3592  # Songssx finite timeline segment limit.
LOW_STEPS = 6
LOWRES_SCALE = 0.6
MAX_SCHEDULER_STEPS = 1_000  # H3's simple scheduler draws from 1,000 distinct sigmas.
PLANNER, SAMPLER, SAVE = '402', '403', '404'
OUTPUT_KEY = 'images'  # ComfyUI PreviewVideo uses this history key.
STEM = 'MiniMax-H3-Songssx导演台-Selflift-标准版'
PLANNER_WIDGETS = ('width', 'height', 'generation_seconds', 'timeline_data', 'material_planner_ui')
WIDGETS = {
    332: ('selection', 'selection.tau', 'start_percent', 'end_percent',
          'dense_blocks', 'min_tokens', 'extra_tokens', 'sink_conditioning', 'verbose'),
    402: (*PLANNER_WIDGETS[:4], None),
    403: ('seed', None, 'continue_audio_latent', 'ref_image_size'),
    404: ('filename_prefix', 'format', 'format.codec', 'format.codec.encoding', None),
    407: ('lora_name', 'strength_model'),
}


def api_from_canvas(canvas):
    graph = deepcopy(canvas)
    for node in graph['nodes']:
        if node.get('mode', 0) in (2, 4) or node['id'] == 406:
            continue
        names = WIDGETS.get(node['id'])
        if names is None:
            names = [socket['widget']['name'] for socket in node.get('inputs', []) if 'widget' in socket]
        values = node.get('widgets_values', [])
        node['widgets_values_named'] = {name: value for name, value in zip(names, values, strict=True) if name}
        node['widgets_values'] = list(node['widgets_values_named'].values())
    return Canvas(graph).api(SAVE, optional=False)


def configure_sampling(canvas, api, nodes, timeline, options):
    choice = options['configuration']
    if not isinstance(choice, dict) or set(choice) != {'high_steps', 'scene_type', 'speed', 'loras'}:
        raise ValueError('Songssx 六步配置须提供 high_steps、scene_type、speed 和 loras')
    high_steps = choice['high_steps']
    if type(high_steps) is not int or not 1 <= high_steps <= MAX_SCHEDULER_STEPS - LOW_STEPS:
        raise ValueError(f'高清采样步数须为 1 至 {MAX_SCHEDULER_STEPS - LOW_STEPS} 的整数')
    scene = choice['scene_type']
    if scene not in ('dialogue', 'combat'):
        raise ValueError('scene_type 须为 dialogue 或 combat')
    speed = choice['speed']
    if speed is None:
        if scene != 'dialogue':
            raise ValueError('只有文戏默认关闭速度 LoRA 时可将 speed 设为 null')
    elif type(speed) not in (int, float) or not -10 <= speed <= 10:
        raise ValueError('动作速度须为 -10 至 10 的数值')
    loras = choice['loras']
    if (not isinstance(loras, list)
            or any(type(value) is not int or value not in (1, 2) for value in loras)
            or len(set(loras)) != len(loras)):
        raise ValueError('附加 LoRA 使用不重复的编号 1、2，两项都关时传空列表')
    if (options.get('reference_image_center_crop', False) is not False
            or options.get('lowres_scale', LOWRES_SCALE) != LOWRES_SCALE):
        raise ValueError('Songssx 六步配置固定关闭参考图居中裁切，低清缩放倍率固定为 0.60')

    timeline.update(secondPassLowresScale=LOWRES_SCALE, referenceImageCenterCrop=False,
                    secondPassHighSteps=high_steps)
    total_steps = LOW_STEPS + high_steps
    nodes['261']['widgets_values'][1] = total_steps
    nodes['261']['widgets_values_named']['steps'] = total_steps
    api['261']['inputs']['steps'] = total_steps
    if speed is not None:
        nodes['343']['widgets_values'][1] = speed
        nodes['343']['widgets_values_named']['strength_model'] = speed

    combat = scene == 'combat'
    enabled_loras = {'400': 1 in loras, '407': 2 in loras, '342': combat,
                     '344': combat, '345': combat, '343': speed is not None}
    for key, enabled in enabled_loras.items():
        nodes[key]['mode'] = 0 if enabled else 4
    # Resolve bypassed model links using the shared canvas converter.
    model_chain = api_from_canvas(canvas)
    for key, enabled in enabled_loras.items():
        if enabled:
            api[key] = model_chain[key]
        else:
            api.pop(key, None)
    api['331']['inputs']['model'] = model_chain['331']['inputs']['model']


def aligned_frames(seconds, overlap):
    if type(seconds) not in (int, float) or not 0 < seconds < math.inf:
        raise ValueError('GEN 的计划新增时长须为有限正数')
    requested_frames = seconds * FPS + overlap
    if requested_frames > MAX_GEN_FRAMES:
        raise ValueError(f'GEN 采样窗口超过 Songssx 节点的 {MAX_GEN_FRAMES} 帧上限')
    return 5 + 17 * math.ceil((requested_frames - 5) / 17)


def validate(workflow, video_plan, outputs, uploads):
    planner, sampler, save = (workflow[key] for key in (PLANNER, SAMPLER, SAVE))
    if ([node['class_type'] for node in (planner, sampler, save)] !=
            ['MiniMaxH3TimelinePlanner', 'MiniMaxH3FiniteSegmentVideoSampler', 'SaveVideo']
            or sampler['inputs']['finite_plan'] != [PLANNER, 2]
            or save['inputs']['video'] != [SAMPLER, 1] or save['inputs']['format'] != 'mp4'
            or any(name in planner['inputs'] for name in ('import_preset', 'prompt_index'))):
        raise ValueError('Songssx 须连接完整时间线并保存一个场次 MP4')
    if (len(outputs) != 1 or (outputs[0].node_id, outputs[0].output_key, outputs[0].index) != (SAVE, OUTPUT_KEY, 0)
            or Path(outputs[0].path).suffix.lower() != '.mp4'):
        raise ValueError('Songssx 须登记 SaveVideo 的一个整场 MP4 取回目标')
    inputs = planner['inputs']
    timeline = json.loads(inputs['timeline_data'])
    config = timeline['segmentConfig']
    segments, mapping = config['segments'], video_plan['segments']
    if (timeline['fps'] != FPS or not 1 <= len(segments) <= 64 or config['mode'] != 'timeline'
            or config['count'] != len(segments) or len(mapping) != len(segments)):
        raise ValueError('Songssx 的 GEN 数量或帧率不符合装配记录')
    if timeline['videoClips'] or timeline['audios']:
        raise ValueError('当前 Songssx 装配仅接入独立参考图与原生场内接续')
    asset_ids = [item['id'] for item in timeline['images']]
    paths = {(item['node'], item['input'], tuple(item.get('json-path', ()))) for item in uploads}
    if (len(set(asset_ids)) != len(asset_ids) or len(uploads) != len(asset_ids) or paths != {
        (PLANNER, 'timeline_data', ('images', index, 'file')) for index in range(len(asset_ids))
    }):
        raise ValueError('Songssx 参考图须逐一绑定实际上传目标')
    previous, previous_length = 0, 0
    identities = set()
    for index, (item, row) in enumerate(zip(segments, mapping, strict=True), 1):
        start, end = item['startFrame'], item['endFrame']
        overlap = previous - start
        if (row['gen'] != index or not re.fullmatch(r'P\d{3,}', row['p']) or row['p'] in identities
                or type(start) is not int or type(end) is not int or start < 0
                or overlap < 0 or (overlap not in (0, 1) and (overlap < 5 or (overlap - 5) % 17))
                or (index == 1 and start != 0) or (index > 1 and overlap >= previous_length)
                or end <= previous or end - start != aligned_frames(row['planned_seconds'], overlap)
                or row['overlap_frames'] != overlap or row['generation_frames'] != [start, end]
                or row['output_frames'] != [previous, end]):
            raise ValueError(f'GEN {index} 的 P 标识、时间线或接续帧与计划不一致')
        refs = item['images']
        if item['audios'] or not 1 <= len(refs) <= 9 or len(set(refs)) != len(refs) or not set(refs) <= set(asset_ids):
            raise ValueError(f'GEN {index} 的参考图分配无效')
        prompt = item['prompt']
        findings = format_findings(prompt, mode='r2v', duration=(end - start) / FPS)
        labels = {int(number) for number in re.findall(r'<Picture (\d+)>', prompt)}
        if findings:
            raise ValueError(f'GEN {index} 的提示词格式错误：{findings[0]["detail"]}')
        if len(prompt) > PROMPT_CHARACTER_LIMIT:
            raise ValueError(f'GEN {index} 的提示词有 {len(prompt)} 字符，超过 {PROMPT_CHARACTER_LIMIT}')
        if labels != set(range(1, len(refs) + 1)) or re.search(r'<(?:Audio|Video) \d+>', prompt):
            raise ValueError(f'GEN {index} 的提示词标签与实际参考素材不符')
        identities.add(row['p'])
        previous_length, previous = end - start, end
    if (timeline['selection'] != {'start': 0, 'duration': previous / FPS}
            or inputs['generation_seconds'] != previous / FPS or previous > 150 * FPS):
        raise ValueError('Songssx 的场次总时长与 GEN 时间线不一致')


def prepare(root, spec, documents):
    record = project_file(root, spec['record_dir'])
    canvas = json.loads(workflow_file(STEM).read_text('utf-8-sig'))
    api = json.loads(workflow_file(STEM, 'api').read_text('utf-8-sig'))
    nodes = {str(node['id']): node for node in canvas['nodes']}
    options = spec['songssx']
    if not isinstance(options, dict):
        raise ValueError('songssx 须为任务配置对象')
    legacy_fields = {'reference_image_center_crop', 'lowres_scale'}
    unknown = options.keys() - {'width', 'height', 'seed', 'remote_prefix', 'segments', 'configuration'} - legacy_fields
    if unknown:
        raise ValueError('未知 Songssx 配置字段：' + '、'.join(sorted(unknown)))
    if 'configuration' not in options and not legacy_fields <= options.keys():
        raise ValueError('Songssx 六步任务须提供 configuration，旧清单须保留原裁切与缩放字段')
    width, height = options['width'], options['height']
    if any(type(value) is not int or value <= 0 or value % 32 for value in (width, height)):
        raise ValueError('Songssx 的宽高必须为正且对齐 32')
    prefix = options['remote_prefix']
    if not re.fullmatch(r'video/[\w-]+(?:/[\w-]+)*', prefix):
        raise ValueError('场次输出前缀须位于远端 video 目录内')
    seed = options['seed']
    if type(seed) is not int or not 0 <= seed <= 2**53 - 1:
        raise ValueError('Songssx seed 须为可准确序列化的非负整数')

    planner = api[PLANNER]['inputs']
    timeline = json.loads(planner['timeline_data'])
    if 'configuration' in options:
        configure_sampling(canvas, api, nodes, timeline, options)
    else:
        crop, scale = options['reference_image_center_crop'], options['lowres_scale']
        if type(crop) is not bool:
            raise ValueError('参考图居中裁切须明确为开或关')
        if type(scale) not in (int, float) or not .25 <= scale <= 1:
            raise ValueError('一采缩放倍率须在 0.25 至 1 之间')
        timeline.update(secondPassLowresScale=scale, referenceImageCenterCrop=crop)
    timeline['images'], segments, rows, uploads = [], [], [], []
    images = {}
    end = 0
    for index, entry in enumerate(options['segments'], 1):
        overlap = entry['overlap_frames']
        if type(overlap) is not int or overlap < 0:
            raise ValueError('GEN 重叠必须是非负整数帧')
        begin = end - overlap
        stop = begin + aligned_frames(entry['duration'], overlap)
        assigned = []
        for value in entry['images']:
            path = input_file(root, value)
            if path not in images:
                asset = len(images) + 1
                images[path] = f'image-{asset}'
                suffix = path.suffix.lower()
                if suffix not in ('.png', '.jpg', '.jpeg', '.webp'):
                    raise ValueError('Songssx 参考图必须是 PNG、JPEG 或 WebP')
                timeline['images'].append({'id': images[path], 'file': f'待上传/{images[path]}{suffix}', 'name': path.name})
                uploads.append({'file': str(path), 'node': PLANNER, 'input': 'timeline_data',
                                'subfolder': record.name, 'response-name': f'上传响应-{asset:03d}.json',
                                'json-path': ['images', asset - 1, 'file']})
            assigned.append(images[path])
        segments.append({'images': assigned, 'audios': [], 'prompt': entry['prompt'],
                         'startFrame': begin, 'endFrame': stop})
        rows.append({'p': entry['p'], 'gen': index, 'planned_seconds': entry['duration'],
                     'generation_frames': [begin, stop], 'output_frames': [end, stop],
                     'overlap_frames': overlap})
        if 'prompt_zh' in entry:
            if not isinstance(entry['prompt_zh'], str):
                raise ValueError('GEN 的中文提示词参考版须为文本')
            rows[-1]['prompt_zh'] = entry['prompt_zh']
        end = stop
    timeline['segmentConfig'] = dict(count=len(segments), activeIndex=0, mode='timeline', segments=segments)
    timeline['selection'] = dict(start=0, duration=end / FPS)
    planner.update(width=width, height=height, generation_seconds=end / FPS,
                   timeline_data=json.dumps(timeline, ensure_ascii=False, allow_nan=False))
    api[SAMPLER]['inputs']['seed'] = seed
    api[SAVE]['inputs']['filename_prefix'] = prefix
    nodes[PLANNER]['widgets_values'][:4] = [width, height, end / FPS, planner['timeline_data']]
    nodes[PLANNER]['widgets_values_named'] = dict(zip(PLANNER_WIDGETS, nodes[PLANNER]['widgets_values'], strict=True))
    nodes[SAMPLER]['widgets_values'][0] = seed
    nodes[SAVE]['widgets_values'][0] = prefix
    documents.new_json(record / '任务.workflow.json', canvas)
    documents.new_json(record / '任务.api.json', api)
    plan = {'adapter': 'technical', 'metadata': 'receipt', 'workflow_id': WORKFLOW, 'segments': rows}
    return dict(project=str(root), task_type=TASK_TYPE, title=spec['title'], workflow=api,
                record_dir=str(record), video_plan=plan, submission_plan=spec.get('submission_plan'),
                uploads=uploads, outputs=[dict(node_id=SAVE, output_key=OUTPUT_KEY, index=0,
                                               path=str(project_file(root, spec['output'])),
                                               response_name='场次视频-取回响应.json')],
                attempt_name='提交尝试.json', request_name='请求.json', response_name='提交响应.json')
