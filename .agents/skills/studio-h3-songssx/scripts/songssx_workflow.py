"""Offline assembly of the registered Songssx SelfLift scene workflow."""
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import subprocess
import sys

SKILLS = Path(__file__).resolve().parents[2]
for skill in ('studio-comfyui', 'studio-h3', 'studio-video-processing'):
    sys.path.insert(0, str(SKILLS / skill / 'scripts'))
from project_paths import input_file, project_file
from workflow_graph import Canvas
from workflow_paths import workflow_file
from h3_prompt_format import PROMPT_CHARACTER_LIMIT, format_findings, shot_blocks
from video_metadata import probe

WORKFLOW = 'songssx-selflift'
TASK_TYPE = 'video-scene-generation'
FPS = 24
MAX_GEN_FRAMES = 362  # 15 seconds at 24 fps, rounded up to the H3 frame grid.
MAX_SCENE_FRAMES = 150 * FPS  # Material Planner's scene duration limit.
MAX_DIMENSION = 16384
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
REFERENCE_EXTENSIONS = {
    'images': {'.png', '.jpg', '.jpeg', '.webp'},
    'audios': {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.wma'},
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
    if type(seconds) not in (int, float) or not 4 <= seconds <= 15:
        raise ValueError('GEN 的计划新增时长须在 4 至 15 秒之间')
    requested_frames = seconds * FPS + overlap
    frames = 5 + 17 * math.ceil((requested_frames - 5) / 17)
    if frames > MAX_GEN_FRAMES:
        raise ValueError(f'GEN 对齐后为 {frames} 帧（含 {overlap} 帧重叠），超过 {MAX_GEN_FRAMES} 帧上限')
    return frames


def validate_dimensions(width, height):
    if any(type(value) is not int or not 32 <= value <= MAX_DIMENSION or value % 32
           for value in (width, height)):
        raise ValueError(f'Songssx 宽高须为 32 至 {MAX_DIMENSION} 之间且对齐 32 的整数')


def validate_shots(prompt, gen, frames, overlap):
    shots = shot_blocks(prompt)
    if not shots or any(number != index or not body
                        for index, (number, body) in enumerate(shots, 1)):
        raise ValueError(f'GEN {gen} 须包含从 [Shot 1] 开始的连续镜号，每镜须有正文')
    overlap_end_ms = round(overlap * 1000 / FPS)
    previous_ms = 0
    for number, body in shots[1:]:
        match = re.match(r'At\s+(\d{2}):([0-5]\d)(?:\.(\d{1,3}))?(?=[\s,]|$)', body, re.IGNORECASE)
        if match is None:
            raise ValueError(f'GEN {gen} [Shot {number}] 须以 At MM:SS.mmm 标出切镜时码')
        minutes, seconds, fraction = match.groups()
        cut_ms = (60 * int(minutes) + int(seconds)) * 1000 + int((fraction or '').ljust(3, '0'))
        if cut_ms <= previous_ms or cut_ms * FPS >= frames * 1000:
            raise ValueError(f'GEN {gen} [Shot {number}] 的切镜时码须严格递增且位于采样区间内')
        if cut_ms < overlap_end_ms:
            raise ValueError(f'GEN {gen} [Shot {number}] 的切镜时码落在开头 {overlap} 帧重叠区内')
        previous_ms = cut_ms


def gap_boundaries(before_frame, generated_frames):
    # The first GEN must start at zero. Put the two visual samples just
    # outside that window so the planner uses its native gap guides.
    return [
        dict(id='gap-before', start=-1 / FPS, duration=1 / FPS,
             trimStart=before_frame / FPS, hasAudio=False),
        dict(id='gap-after', start=generated_frames / FPS, duration=1 / FPS,
             trimStart=0, hasAudio=False),
    ]


def validate(workflow, video_plan, outputs, uploads):
    planner, sampler, save = (workflow[key] for key in (PLANNER, SAMPLER, SAVE))
    if ([node['class_type'] for node in (planner, sampler, save)] !=
            ['MiniMaxH3TimelinePlanner', 'MiniMaxH3FiniteSegmentVideoSampler', 'SaveVideo']
            or sampler['inputs']['finite_plan'] != [PLANNER, 2]
            or save['inputs']['video'] != [SAMPLER, 1] or save['inputs']['format'] != 'mp4'
            or any(name in planner['inputs'] for name in ('import_preset', 'prompt_index'))):
        raise ValueError('Songssx 须连接完整的生成计划并保存一个 MP4')
    if (len(outputs) != 1 or (outputs[0].node_id, outputs[0].output_key, outputs[0].index) != (SAVE, OUTPUT_KEY, 0)
            or Path(outputs[0].path).suffix.lower() != '.mp4'):
        raise ValueError('Songssx 须登记 SaveVideo 的一个 MP4 取回目标')
    inputs = planner['inputs']
    validate_dimensions(inputs['width'], inputs['height'])
    timeline = json.loads(inputs['timeline_data'])
    config = timeline['segmentConfig']
    segments, mapping = config['segments'], video_plan['segments']
    if (timeline['fps'] != FPS or not 1 <= len(segments) <= 64 or config['mode'] != 'timeline'
            or config['count'] != len(segments) or len(mapping) != len(segments)):
        raise ValueError('Songssx 的 GEN 数量或帧率不符合装配记录')
    gap = 'gap_repair' in video_plan
    clips = timeline['videoClips']
    if not gap and clips:
        raise ValueError('Songssx 仅在 gap_repair 任务中接收两段边界视频')
    if gap and timeline['audios']:
        raise ValueError('Songssx 双边界补生成只接收边界画面及独立参考图')
    if any(item.get('audioMode') != 'reference' for item in timeline['audios']):
        raise ValueError('Songssx 独立参考音频须使用参考音色模式')
    asset_ids = {kind: {item['id'] for item in timeline[kind]} for kind in REFERENCE_EXTENSIONS}
    expected_paths = {(PLANNER, 'timeline_data', (kind, index, 'file'))
                      for kind in asset_ids for index in range(len(timeline[kind]))}
    if gap:
        expected_paths.update((PLANNER, 'timeline_data', ('videoClips', i, 'file')) for i in range(2))
    paths = {(item['node'], item['input'], tuple(item.get('json-path', ()))) for item in uploads}
    if (any(len(ids) != len(timeline[kind]) for kind, ids in asset_ids.items())
            or len(uploads) != len(expected_paths) or paths != expected_paths):
        raise ValueError('Songssx 参考素材须逐一绑定实际上传目标')
    if gap:
        repair = video_plan['gap_repair']
        if (not isinstance(repair, dict) or len(segments) != 1 or len(clips) != 2
                or timeline.get('videoAudioEnabled') is not True
                or type(repair.get('before_source_frame')) is not int or repair['before_source_frame'] < 0
                or type(repair.get('replacement_frames')) is not int
                or repair['replacement_frames'] != mapping[0]['planned_seconds'] * FPS):
            raise ValueError('Songssx 局部返修须有一个补生成 GEN、两个画面边界和准确的替换帧数')
        boundaries = gap_boundaries(repair['before_source_frame'], segments[0]['endFrame'])
        if any(not clip.get('file') or clip.get('hasAudio') is not False
               or any(clip.get(key) != value for key, value in expected.items())
               for clip, expected in zip(clips, boundaries, strict=True)):
            raise ValueError('Songssx 局部返修的视频边界须紧贴补生成区间，且仅提供画面')
    minimum_images = 0 if gap else 1
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
        prompt = item['prompt']
        findings = format_findings(prompt, mode='r2v', duration=(end - start) / FPS)
        if findings:
            raise ValueError(f'GEN {index} 的提示词格式错误：{findings[0]["detail"]}')
        if len(prompt) > PROMPT_CHARACTER_LIMIT:
            raise ValueError(f'GEN {index} 的提示词有 {len(prompt)} 字符，超过 {PROMPT_CHARACTER_LIMIT}')
        for kind, label, minimum, maximum in (('images', 'Picture', minimum_images, 9), ('audios', 'Audio', 0, 3)):
            refs = item[kind]
            if not minimum <= len(refs) <= maximum or len(set(refs)) != len(refs) or not set(refs) <= asset_ids[kind]:
                raise ValueError(f'GEN {index} 的 {label} 参考素材分配无效')
            labels = {int(number) for number in re.findall(rf'<{label} (\d+)>', prompt)}
            if labels != set(range(1, len(refs) + 1)):
                raise ValueError(f'GEN {index} 的 {label} 提示词标签与实际参考素材不符')
        if re.search(r'<Video \d+>', prompt):
            raise ValueError(f'GEN {index} 的提示词标签与实际参考素材不符')
        validate_shots(prompt, index, end - start, overlap)
        identities.add(row['p'])
        previous_length, previous = end - start, end
    if previous > MAX_SCENE_FRAMES:
        raise ValueError(f'Songssx 整场输出为 {previous} 帧，超过 {MAX_SCENE_FRAMES} 帧上限')
    if (timeline['selection'] != {'start': 0, 'duration': previous / FPS}
            or inputs['generation_seconds'] != previous / FPS):
        raise ValueError('Songssx 的场次总时长与 GEN 时间线不一致')


def reference_audio_duration(path):
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                                 '-show_entries', 'stream=duration:format=duration',
                                 '-of', 'json', str(path)], capture_output=True, timeout=30)
    except FileNotFoundError as error:
        raise ValueError('Songssx 参考音频时长检查需要 ffprobe') from error
    except subprocess.TimeoutExpired as error:
        raise ValueError(f'Songssx 读取参考音频时长超时：{path.name}') from error
    if result.returncode:
        raise ValueError(f'Songssx 无法读取参考音频：{path.name}')
    metadata = json.loads(result.stdout)
    if not metadata['streams']:
        raise ValueError(f'Songssx 参考音频没有音轨：{path.name}')
    seconds = metadata['streams'][0].get('duration')
    if seconds in (None, 'N/A'):
        seconds = metadata['format'].get('duration')
    if seconds in (None, 'N/A') or not 2 <= float(seconds) <= 15:
        raise ValueError(f'Songssx 单条参考音频须为 2 至 15 秒：{path.name}')
    return float(seconds)


def prepare(root, spec, documents):
    record = project_file(root, spec['record_dir'])
    canvas = json.loads(workflow_file(STEM).read_text('utf-8-sig'))
    api = json.loads(workflow_file(STEM, 'api').read_text('utf-8-sig'))
    nodes = {str(node['id']): node for node in canvas['nodes']}
    options = spec['songssx']
    if not isinstance(options, dict):
        raise ValueError('songssx 须为任务配置对象')
    legacy_fields = {'reference_image_center_crop', 'lowres_scale'}
    unknown = options.keys() - {'width', 'height', 'seed', 'remote_prefix', 'segments', 'configuration', 'gap_repair'} - legacy_fields
    if unknown:
        raise ValueError('未知 Songssx 配置字段：' + '、'.join(sorted(unknown)))
    if 'configuration' not in options and not legacy_fields <= options.keys():
        raise ValueError('Songssx 六步任务须提供 configuration，旧清单须保留原裁切与缩放字段')
    width, height = options['width'], options['height']
    validate_dimensions(width, height)
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
    segments, rows, uploads = [], [], []
    assets = {kind: {} for kind in REFERENCE_EXTENSIONS}
    for kind in assets:
        timeline[kind] = []
    audio_durations = {}
    end = 0
    for index, entry in enumerate(options['segments'], 1):
        overlap = entry['overlap_frames']
        if type(overlap) is not int or overlap < 0:
            raise ValueError('GEN 重叠必须是非负整数帧')
        begin = end - overlap
        stop = begin + aligned_frames(entry['duration'], overlap)
        assigned = {'images': [], 'audios': []}
        for kind, values in (('images', entry['images']), ('audios', entry.get('audios', []))):
            if not isinstance(values, list):
                raise ValueError(f'GEN {index} 的 {kind} 须为素材路径数组')
            for value in values:
                path = input_file(root, value)
                if path not in assets[kind]:
                    slot = len(timeline[kind])
                    asset_id = f'{kind[:-1]}-{slot + 1}'
                    suffix = path.suffix.lower()
                    if suffix not in REFERENCE_EXTENSIONS[kind]:
                        raise ValueError(f'Songssx 不支持 {kind} 素材格式：{path.name}')
                    material = {'id': asset_id, 'file': f'待上传/{asset_id}{suffix}', 'name': path.name}
                    if kind == 'audios':
                        material['audioMode'] = 'reference'
                        audio_durations[asset_id] = reference_audio_duration(path)
                    timeline[kind].append(material)
                    assets[kind][path] = asset_id
                    uploads.append({'file': str(path), 'node': PLANNER, 'input': 'timeline_data',
                                    'subfolder': record.name, 'response-name': f'上传响应-{len(uploads) + 1:03d}.json',
                                    'json-path': [kind, slot, 'file']})
                assigned[kind].append(assets[kind][path])
        if sum(audio_durations[asset] for asset in assigned['audios']) > 15:
            raise ValueError(f'GEN {index} 的参考音频总时长不能超过 15 秒')
        segments.append({**assigned, 'prompt': entry['prompt'],
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
    plan = {'adapter': 'technical', 'metadata': 'receipt', 'workflow_id': WORKFLOW, 'segments': rows}
    if 'gap_repair' in options:
        gap = options['gap_repair']
        if not isinstance(gap, dict) or gap.keys() != {'before', 'after'} or len(rows) != 1:
            raise ValueError('Songssx gap_repair 须提供 before、after 两个本地截好的视频和一个补生成 GEN')
        replacement_frames = rows[0]['planned_seconds'] * FPS
        if replacement_frames != int(replacement_frames):
            raise ValueError('Songssx 局部返修请求时长须对应 24 fps 的整数帧')
        paths = [input_file(root, gap[side]) for side in ('before', 'after')]
        facts = [probe(path) for path in paths]
        if any(fact['frame_rate'] != FPS or not fact['frames'] for fact in facts):
            raise ValueError('Songssx 返修边界须是可读取帧数的 24 fps 视频')
        before_frame = int(facts[0]['frames']) - 1
        plan['gap_repair'] = dict(before_source_frame=before_frame, replacement_frames=int(replacement_frames))
        clips = gap_boundaries(before_frame, end)
        for index, (clip, path) in enumerate(zip(clips, paths, strict=True)):
            clip.update(file=f'待上传/{clip["id"]}{path.suffix.lower()}', name=path.name)
            uploads.append({'file': str(path), 'node': PLANNER, 'input': 'timeline_data',
                            'subfolder': record.name, 'response-name': f'上传响应-{clip["id"]}.json',
                            'json-path': ['videoClips', index, 'file']})
        timeline.update(videoClips=clips, videoAudioEnabled=True)
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
    return dict(project=str(root), task_type=TASK_TYPE, title=spec['title'], workflow=api,
                record_dir=str(record), video_plan=plan, submission_plan=spec.get('submission_plan'),
                uploads=uploads, outputs=[dict(node_id=SAVE, output_key=OUTPUT_KEY, index=0,
                                               path=str(project_file(root, spec['output'])),
                                               response_name='场次视频-取回响应.json')],
                attempt_name='提交尝试.json', request_name='请求.json', response_name='提交响应.json')
