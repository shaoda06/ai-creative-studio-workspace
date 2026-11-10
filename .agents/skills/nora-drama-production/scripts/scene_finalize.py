#!/usr/bin/env python3
"""汇总已批准的整场一采或二采，保存场次画布、API和来源记录。"""
import argparse
import copy
import json
import os
from pathlib import Path

import sys
_SKILLS = Path(__file__).resolve().parents[2]
for _skill in ("studio-comfyui", "studio-h3", "studio-video-processing", "nora-video-prompts", "nora-drama-production", "nora-drama-handoff"):
    sys.path.insert(0, str(_SKILLS / _skill / "scripts"))
import re
import sys
import tempfile
from urllib.parse import unquote

import video_adopt as adopt
import workflow_baselines as pairs
import project_progress

client = adopt.client
MEDIA = ('imageFile', 'audioFile', 'videoFile', 'pairedAudioFile')
FINALIZATION_STAGES = ('一采', '二采')
WIDGETS = ('steps', 'sampler', 'scheduler', 'cfg', 'shift_video', 'shift_audio', 'seed', 'task_type')


def replace_file(path, text):
    if path.exists() and path.read_text(encoding='utf-8-sig') == text:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=path.parent,
                                         prefix='.' + path.name, delete=False) as out:
            temporary = Path(out.name)
            out.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_json(path, value):
    replace_file(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def indexed_parts(root, episode):
    path = root / '09-剧集制作' / episode / '03-分镜脚本' / (episode + '-分镜索引.md')
    return re.findall(r'^\| (' + re.escape(episode) + r'-C\d{3}) \|[^\n]*?\| ('
                      + re.escape(episode) + r'-C\d{3}-P\d{3}) \|', path.read_text('utf-8-sig'), re.M)


def selected(root, part, stage):
    draft = root / '09-剧集制作' / part.split('-')[0] / '其他资料/工作稿' / (part + '-视频制作-工作稿.md')
    if not draft.is_file():
        return None
    text = draft.read_text('utf-8-sig')
    output = adopt.selected_output(root, draft, text, part, stage)
    return output['identity'] if output else None


def episode_missing(root, episode):
    """Completion requires adopted stage outputs."""
    missing = []
    for scene, part in indexed_parts(root, episode):
        for stage in adopt.STAGES:
            if selected(root, part, stage) is None:
                missing.append(part + ' ' + stage + '未采用')
    return missing


def retrospective_status(summary):
    """Use a current explicit decision, never infer completion from a history heading."""
    text = summary.read_text('utf-8-sig')
    text = re.split(r'^#{2,6}[ \t]+', text, maxsplit=1, flags=re.M)[0]
    explicit = re.search(r'^- 完集复盘状态：([^\n]*)', text, re.M)
    current = re.search(r'^- 当前状态及待办：([^\n]*)', text, re.M)
    completed = (explicit[1].strip() == '已完成' if explicit else
                 bool(current and '完集复盘与经验归并已完成' in current[1]))
    return {'status': 'completed' if completed else 'pending', 'record': str(summary)}


def update_progress(root, episode, scene, stage, summary):
    path = root / '项目进度.md'
    pending, next_steps = [], []
    indexed = indexed_parts(root, episode)
    missing = episode_missing(root, episode)
    for current_scene, part in indexed:
        if current_scene == scene and selected(root, part, stage) is None:
            draft = root / '09-剧集制作' / episode / '其他资料/工作稿' / (part + '-视频制作-工作稿.md')
            pending.append('[' + part + '](' + adopt.link(path, draft) + ')的' + stage + '尚未采用')
    complete = not missing
    if complete and retrospective_status(summary)['status'] == 'pending':
        next_steps.append('完成本集复盘与经验归并，记录于[生成说明工作稿](' + adopt.link(path, summary) + ')')
    folder = root / '09-剧集制作' / episode / '06-阶段采用视频' / adopt.STAGES[stage] / (scene.split('-')[-1] + '-场次')
    outputs = '[' + scene + stage + '采用视频](' + adopt.link(path, folder) + ')、[制作与留档记录](' + adopt.link(path, summary) + ')'
    text = path.read_text('utf-8-sig')
    replace_file(path, project_progress.update(text, episode, status='已完成' if complete else '进行中',
                                             outputs=outputs, pending=pending, next_steps=next_steps))
    return complete


def source(root, item):
    mapping_path = adopt.local_path(root, item['mapping'])
    mapping = adopt.execution_metadata(root, mapping_path, adopt.load(mapping_path))
    contexts = [c for c in mapping['generation_contexts'] if c['identity'] == item['identity']]
    if len(contexts) != 1:
        raise ValueError('来源映射身份不唯一：' + item['identity'])
    api_path = adopt.local_path(root, item['api'])
    canvas_path = adopt.local_path(root, item['canvas'])
    workflow, canvas = adopt.load(api_path), adopt.load(canvas_path)
    request = adopt.load(mapping_path.parent / '请求.json')
    response = adopt.load(mapping_path.parent / '提交响应.json')
    accepted = response.get('data', response)
    restoration = []
    # Populate the export copy from the actual API; source canvas bytes stay untouched.
    for stored in canvas['nodes']:
        named = stored.get('widgets_values_named', {})
        key = str(stored['id'])
        if named and key in workflow:
            named.update({k: v for k, v in workflow[key]['inputs'].items() if k in named and not pairs.is_link(v)})
            stored['widgets_values'] = list(named.values())
    if (not mapping.get('prompt_id') or accepted.get('prompt_id') != mapping['prompt_id']
            or pairs.semantic(request['prompt']) != pairs.semantic(workflow)):
        raise ValueError('来源 API／提交响应与实际获批任务不一致：' + item['identity'])
    return {'identity': item['identity'], 'mapping_path': mapping_path, 'mapping': mapping,
            'context': contexts[0], 'api_path': api_path, 'canvas_path': canvas_path,
            'api': workflow, 'canvas': canvas, 'restoration': restoration}


def lift_common(common, group):
    """公共区差异移入各组；保留绝对素材槽位，本组覆盖公共同槽。"""
    group = copy.deepcopy(group)
    if common['commonEnabled']:
        group['prompt'] = '\n\n'.join(p.strip() for p in (common['prompt'], group['prompt']) if p.strip())
        for field in ('refs', 'refAudios', 'refVideos'):
            local = {r['index']: r for r in group[field]}
            group[field] = sorted({**{r['index']: copy.deepcopy(r) for r in common[field]}, **local}.values(),
                                  key=lambda r: r['index'])
    return group


def director(source_item, part):
    nodes = [(k, n) for k, n in source_item['api'].items() if n['class_type'] == 'MiniMaxH3Director']
    if len(nodes) != 1:
        raise ValueError('来源需要唯一原生导演台：' + source_item['identity'])
    key, node = nodes[0]
    timeline = client.strict_json(node['inputs']['timeline_data'])
    if timeline['editMode'] != 'segment' or not timeline['global']['taskType'].startswith('r2v'):
        raise ValueError('场次留档目前支持原生 r2v 分组导演台')
    mapping = source_item['mapping']
    stage = source_item['identity'].rsplit('-', 1)[1]
    indices = [i for i, s in enumerate(mapping['segments'])
               if s['segment'] == part and s['segment'] + '-' + s['round'] + '-' + stage == source_item['identity']]
    if len(mapping['segments']) != len(timeline['segments']) or len(indices) != 1:
        raise ValueError('输入映射原组序无法唯一对应实际时间线分段：' + part)
    index = indices[0]
    group = timeline['segments'][index]
    if index not in mapping['selected_indices']:
        raise ValueError('该分段不在输入映射实际执行范围：' + part)
    if timeline.get('runSelectEnabled') and index not in timeline['runSelection']:
        raise ValueError('该分段不在来源任务实际执行范围：' + part)
    editor = timeline['batchWorkspaces']['r2v']
    stale_editor = (pairs.director_editor_state(editor['globalCommon'], True) != pairs.director_editor_state(timeline['global'], True)
                    or [pairs.director_editor_state(g) for g in editor['segments']]
                    != [pairs.director_editor_state(g) for g in timeline['segments']])
    if timeline['keyframes'] or timeline['videoClips'] or timeline['video'].get('fileName'):
        raise ValueError('分组汇总不改写带源视频／关键帧时间轴的工程：' + part)
    prompt = '\n\n'.join(p.strip() for p in
                         ([timeline['global']['prompt'], group['prompt']] if timeline['global']['commonEnabled']
                          else [group['prompt']]) if p.strip())
    frozen = adopt.local_path(source_item['root'], source_item['context']['prompts']['english'])
    if frozen.read_text(encoding='utf-8-sig').strip() != prompt:
        raise ValueError('实际正文与冻结提示词不同：' + part)
    if stale_editor:
        # source() has verified the API against the actual submitted request.
        # Restore only the parsed export copy; never alter submitted API/canvas evidence.
        editor['globalCommon'] = copy.deepcopy(timeline['global'])
        editor['segments'] = copy.deepcopy(timeline['segments'])
        source_item['restoration'].append('按实际提交及冻结正文同步留档副本编辑区：' + part)
    return key, node, timeline, group




def prepare(root, plan, batch_parts=None, batch_name=None):
    episode, scene, stage = plan['episode'], plan['scene'], plan['stage']
    if not re.fullmatch(r'(?:EP\d{3}|片头|片尾)', episode) or not re.fullmatch(r'C\d{3}', scene) or stage not in FINALIZATION_STAGES:
        raise ValueError('需要明确 EP编号或片头／片尾、C编号以及一采或二采；后处理不使用场次画布留档')
    ep = root / '09-剧集制作' / episode
    index_file = ep / '03-分镜脚本' / f'{episode}-分镜索引.md'
    expected = re.findall(r'^\| ' + episode + '-' + scene + r' \|[^\n]*?\| (' + episode + '-' + scene + r'-P\d{3}) \|',
                          index_file.read_text(encoding='utf-8-sig'), re.M)
    if batch_parts is not None:
        expected = [p for p in expected if p in batch_parts]
    identities = [item['identity'] for item in plan['items']]
    parts = [adopt.IDENTITY.fullmatch(i).groups() if adopt.IDENTITY.fullmatch(i) else () for i in identities]
    if (not expected or len(expected) != len(set(expected)) or len(identities) != len(set(identities))
            or any(not p or p[0] != episode or p[1] != scene or p[4] != stage for p in parts)
            or {f'{p[0]}-{p[1]}-{p[2]}' for p in parts} != set(expected)):
        raise ValueError('留档范围必须完整、唯一覆盖正式分镜索引中的当前场次该阶段全部P段')
    items = sorted(plan['items'], key=lambda item: expected.index(item['identity'].rsplit('-', 2)[0]))
    sources, drafts, evidence, media = [], [], [], {}
    for item in items:
        part = item['identity'].rsplit('-', 2)[0]
        draft = ep / '其他资料' / '工作稿' / f'{part}-视频制作-工作稿.md'
        text = draft.read_text(encoding='utf-8-sig')
        _, _, row = adopt.selected_row(text, stage)
        links = [unquote(u) for u in re.findall(r'\]\(([^)#]+)\)', row) if Path(unquote(u)).stem == item['identity']]
        reviews = set(re.findall(r'\]\(#([^)]*)\)', row.strip().strip('|').split('|')[-1]))
        if len(links) != 1 or len(reviews) != 1:
            raise ValueError('当前采用入口／人工审核依据不唯一：' + part)
        selected = adopt.local_path(root, draft.parent / links[0])
        import project_resources as resources
        if not resources.reference(root, selected) and not selected.is_relative_to(ep / '06-阶段采用视频' / adopt.STAGES[stage] / f'{scene}-场次'):
            raise ValueError('当前采用文件未归位对应阶段定稿目录：' + part)
        review = next(iter(reviews))
        if not adopt.approved_row(text, selected.name + f' [审核](#{review})', selected.name):
            raise ValueError('当前具体版本尚未批准采用：' + item['identity'])
        mapping_path = adopt.local_path(root, item['mapping'])
        mapped = adopt.load(mapping_path)
        local_edit = mapped.get('local_edit')
        if local_edit is not None:
            # The approved silent MP4 has no model execution of its own.
            if mapped.get('prompt_id') or mapped.get('operation') != 'local-video-audio-removal':
                raise ValueError('本地衍生留档仅支持无新模型任务的整段静音视频')
            content = source(root, item['generation_source'])
            contexts = [c for c in mapped['generation_contexts'] if c['identity'] == item['identity']]
            if (len(contexts) != 1 or contexts[0].get('source') != content['identity']
                    or local_edit['source'] != content['identity']
                    or content['identity'].rsplit('-', 2)[0] != part
                    or content['identity'].rsplit('-', 1)[1] != stage):
                raise ValueError('静音衍生与明确指定的原生成来源不一致')
            parameters = local_edit['parameters']
            if '-an' not in parameters or parameters[parameters.index('-c:v') + 1] != 'copy':
                raise ValueError('静音衍生须保留原视频流，不把画面修改当作原生成缓存')
            original_receipt = adopt.load(adopt.local_path(root, item['generation_source']['receipt']))
            adopt.check_file(adopt.local_path(root, local_edit['source_file']),
                             original_receipt.get('data', original_receipt))
            actual = {'identity': item['identity'], 'mapping_path': mapping_path, 'mapping': mapped,
                      'context': contexts[0], 'api_path': None, 'canvas_path': None, 'restoration': []}
        else:
            actual = source(root, item)
            content = actual
        receipt_path = adopt.local_path(root, item['receipt'])
        if local_edit is not None:
            receipt_document = adopt.load(receipt_path)
            receipt = mapped['output'] if receipt_path == mapping_path else receipt_document.get('data', receipt_document)
            if (not isinstance(receipt.get('bytes'), int) or receipt['bytes'] <= 0
                    or adopt.local_path(root, receipt['path']).name != selected.name):
                raise ValueError('静音衍生缺少本次采用文件的实际输出凭据')
        elif not receipt_path.is_relative_to(actual['mapping_path'].parent):
            paths = [s.get(field) for s in actual['mapping']['segments']
                     for field in ('download_response', 'download_receipt', 'final_download_receipt') if s.get(field)]
            if receipt_path not in [adopt.local_path(root, p) for p in paths]:
                raise ValueError('共同任务外的取回凭据须已在输入映射中明确关联')
        if local_edit is None:
            receipt_document = adopt.load(receipt_path)
            receipt = receipt_document.get('data', receipt_document)
        mapped_parts = [s for i, s in enumerate(actual['mapping']['segments'])
                        if local_edit is None
                        if i in actual['mapping']['selected_indices']
                        and s['segment'] + '-' + s['round'] + '-' + stage == item['identity']]
        if local_edit is None and len(mapped_parts) != 1:
            raise ValueError('来源映射的实际执行范围与采用身份不符')
        if local_edit is None:
            mapped_part = mapped_parts[0]
            remote = mapped_part.get('remote', mapped_part.get('remote_output', actual['mapping'].get('remote_output')))
            if remote is None and mapped_part.get('final_output'):
                remote = mapped_part['final_output']['remote']
            if remote is None:
                outputs = [o for o in actual['mapping'].get('outputs', []) if o.get('identity') == item['identity']]
                if len(outputs) != 1 or adopt.local_path(root, outputs[0]['receipt']) != receipt_path:
                    raise ValueError('后台输出未唯一关联本段及指定取回凭据')
                remote = outputs[0]['remote']
            if remote != receipt['remote']:
                raise ValueError('取回凭据的远端输出与本段映射不对应')
        adopt.check_file(selected, receipt)
        content['root'] = root
        content['director'] = director(content, part)
        sources.append((actual, content))
        drafts.append(draft)
        refs = content['context']['references']
        for scope_name, scope in refs.items():
            for ref in scope:
                local = adopt.local_path(root, ref['file'])
                if not local.is_file():
                    raise ValueError('冻结素材缺失：' + str(local))
                block = content['director'][2]['global'] if scope_name == 'common' else content['director'][3]
                paths = [r[file_field] for field, file_field, label in
                         (('refs', 'imageFile', 'Picture'), ('refAudios', 'audioFile', 'Audio'), ('refVideos', 'videoFile', 'Video'))
                         for r in block[field] if ref['label'] == f'<{label} {r["index"] + 1}>']
                if len(paths) != 1:
                    raise ValueError('冻结素材标签与实际时间线不对应：' + ref['label'])
                remote_path = paths[0]
                if remote_path in media and media[remote_path].read_bytes() != local.read_bytes():
                    raise ValueError('不同来源同一远端素材路径字节冲突：' + remote_path)
                media[remote_path] = local
        for upload in content['mapping']['uploads']:
            local = adopt.local_path(root, upload['file'])
            if local.is_file():
                if upload['input_path'] in media and media[upload['input_path']].read_bytes() != local.read_bytes():
                    raise ValueError('不同来源同一远端素材路径字节冲突：' + upload['input_path'])
                media.setdefault(upload['input_path'], local)
        evidence.append({'identity': item['identity'], 'selected_path': str(selected), 'review': review,
                         'mapping': str(actual['mapping_path']),
                         'api': str(actual['api_path']) if actual['api_path'] else None,
                         'canvas': str(actual['canvas_path']) if actual['canvas_path'] else None,
                         'prompt_id': actual['mapping'].get('prompt_id'),
                         'content_identity': content['identity'], 'content_mapping': str(content['mapping_path']),
                         'content_api': str(content['api_path']), 'content_canvas': str(content['canvas_path']),
                         'seed': content['director'][1]['inputs']['seed'], 'receipt': item['receipt'],
                         'restoration': actual['restoration'], 'content_restoration': content['restoration']})
        if local_edit is not None:
            evidence[-1].update(local_edit=local_edit, generation_source=item['generation_source'])
    first = sources[0][1]
    key, node, timeline, _ = first['director']
    workflow, canvas, timeline = copy.deepcopy(first['api']), copy.deepcopy(first['canvas']), copy.deepcopy(timeline)
    # Compare full active model/SIGMAS/Refine graph by class and dependency structure, independent of IDs.
    def graph_signature(api, director_key):
        def walk(node_key):
            n = api[node_key]
            values = {k: walk(v[0]) + [v[1]] if pairs.is_link(v) else v for k, v in n['inputs'].items()
                      if not (node_key == director_key and k in ('timeline_data', 'global_prompt', 'total_frames'))}
            return [n['class_type'], values]
        return walk(director_key)
    for _, content in sources[1:]:
        other_key, _, other_t, _ = content['director']
        if (graph_signature(first['api'], key) != graph_signature(content['api'], other_key)
                or any(timeline[f] != other_t[f] for f in ('frameRate', 'width', 'height', 'refMaxSize', 'output'))):
            raise ValueError(f'无法合并必要配置（模型链／SIGMAS／Refine／种子／尺寸）：{first["identity"]} 与 {content["identity"]}')
    globals_ = [content['director'][2]['global'] for _, content in sources]
    common_same = all(g == globals_[0] for g in globals_)
    if not common_same:
        ignored = {'prompt', 'refs', 'refAudios', 'refVideos', 'commonEnabled', 'commonCollapsed'}
        if any({k: v for k, v in g.items() if k not in ignored} != {k: v for k, v in globals_[0].items() if k not in ignored}
               for g in globals_):
            raise ValueError('公共区模式配置冲突，无法只移入各组正文／引用素材')
        if any(g.get('referenceVideo', {}).get('videoFile') for g in globals_):
            raise ValueError('公共旧版referenceVideo差异需要先规范化，不能丢失引用')
        timeline['global'].update(commonEnabled=False, prompt='', refs=[], refAudios=[], refVideos=[])
    groups, frame = [], 0
    for _, content in sources:
        _, _, t, group = content['director']
        group = copy.deepcopy(group) if common_same else lift_common(t['global'], group)
        group['start'] = frame
        frame += group['frameCount']
        groups.append(group)
    timeline.update(segments=groups, totalFrames=frame, durationSec=sum(g['durationSec'] for g in groups),
                    runSelectEnabled=True, runSelection=list(range(len(groups))), selectedIndex=0)
    timeline['video']['sourceFrameCount'] = frame
    timeline['batchWorkspaces'] = {'r2v': {'globalCommon': copy.deepcopy(timeline['global']), 'segments': copy.deepcopy(groups),
                                         'selectedIndex': 0, 'editMode': 'segment', 'runSelectEnabled': True,
                                         'runSelection': list(range(len(groups)))}}
    workflow[key]['inputs'].update(timeline_data=json.dumps(timeline, ensure_ascii=False), total_frames=frame,
                                  global_prompt=timeline['global']['prompt'])
    graph, node_id = pairs.Canvas(canvas).find(key)
    stored = graph.nodes[node_id]
    for field in ('timeline_data', 'total_frames', 'global_prompt'):
        stored['widgets_values_named'][field] = workflow[key]['inputs'][field]
    stored['widgets_values'] = list(stored['widgets_values_named'].values())
    canvas.setdefault('extra', {})['nora_scene_finalization'] = {'stage': stage, 'sources': evidence,
                                                              'purpose': '整场汇总工程；不是单次执行原始画布；不恢复一采缓存'}
    urls = {content['mapping']['url'].rstrip('/') for _, content in sources}
    if len(urls) != 1:
        raise ValueError('引用媒体分属不同服务，无法汇总为一份使用原素材路径的场次画布')
    edition = plan.get('edition', '')
    if edition and not re.fullmatch(r'\d{3}', edition):
        raise ValueError('edition 须为三位留档序号，不是生成R编号')
    base = f'{episode}-{scene}-{stage}定稿' + ('-' + batch_name if batch_name else '')
    final = adopt.local_path(root, ep / '06-阶段采用视频' / adopt.STAGES[stage] / f'{scene}-场次' / '导演包')
    record = sources[0][0]['mapping_path'].parent
    if not edition:
        versions = set()
        for directory in (final, record):
            for path in directory.glob(base + '*'):
                match = re.fullmatch(re.escape(base) + r'(?:-(\d{3}))?(?:-导演包\.mmxpack\.zip|\.workflow\.json|-留档记录\.json|\.api\.json|-导出响应\.json)', path.name)
                if match:
                    versions.add(match[1] or '')
        for version in sorted(versions, key=lambda v: int(v or '1'), reverse=True):
            previous_path = record / (base + ('-' + version if version else '') + '-留档记录.json')
            if previous_path.is_file():
                previous = adopt.load(previous_path)
                if (previous.get('canvas') and previous['sources'] == evidence and previous['stage'] == stage
                        and previous.get('configuration_batch_authorization') == plan.get('configuration_batch_authorization')):
                    edition = version
                    break
        else:
            if versions:
                number = max(int(v or '1') for v in versions) + 1
                if number > 999:
                    raise ValueError('本场该阶段留档序号已用至999，不能覆盖已有版本')
                edition = f'{number:03d}'
    stem = base + ('-' + edition if edition else '')
    return {'workflow': workflow, 'canvas': canvas, 'node': key,
            'url': next(iter(urls)), 'sources': sources, 'evidence': evidence,
            'canvas_path': final / (stem + '.workflow.json'),
            'api_path': record / (stem + '.api.json'),
            'record': record / (stem + '-留档记录.json'), 'drafts': drafts,
            'summary': adopt.local_path(root, plan.get('summary', ep / '其他资料' / '工作稿' / f'{episode}-生成说明-工作稿.md')),
            'progress': adopt.local_path(root, root / '项目进度.md'),
            'heading': f'定稿留档-{episode}-{scene}-{stage}' + ('-' + batch_name if batch_name else ''),
            'scope': '该配置批次' if batch_name else '整场该阶段'}




def finalize_one(root, plan, p, apply):
    for path in [*p['drafts'], p['summary'], p['progress']]:
        path.read_text(encoding='utf-8-sig')
    project_progress.phase_row(p['progress'].read_text('utf-8-sig'), plan['episode'])
    record = {'stage': plan['stage'], 'sources': p['evidence'], 'url': p['url'], 'node_id': p['node'],
              'canvas': str(p['canvas_path']), 'api': str(p['api_path']),
              'configuration_batch_authorization': plan.get('configuration_batch_authorization')}
    old = adopt.load(p['record']) if p['record'].exists() else None
    if old is not None and any(old.get(k) != v for k, v in record.items()):
        raise ValueError('已有留档来源不同，保留原附件；使用新的 edition 明确另存版本')
    for path, value in ((p['api_path'], p['workflow']), (p['canvas_path'], p['canvas'])):
        if path.exists() and adopt.load(path) != value:
            raise ValueError('已有汇总工程不同，不能覆盖：' + str(path))
    result = {'state': 'ready', 'mode': 'apply' if apply else 'dry_run', **record,
              'record': str(p['record']), 'browser_sync': 'not_checked'}
    if not apply:
        return result
    if old is None:
        client.write_new(p['record'], {**record, 'state': 'prepared'})
    for path, value in ((p['api_path'], p['workflow']), (p['canvas_path'], p['canvas'])):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            client.write_new(path, value)
    if old and old.get('delivery') == 'on-demand' and old['state'] == 'completed':
        # Legacy finalization wrote the archive record before updating project progress.
        progress_path = str(p['progress'])
        if progress_path not in old['records']:
            update_progress(root, plan['episode'], plan['episode'] + '-' + plan['scene'], plan['stage'], p['summary'])
            save_json(p['record'], {**old, 'records': [*old['records'], progress_path]})
        return {**result, 'state': 'completed'}
    stamp = adopt.load(p['record']).get('verified_at', client.now())
    for path in [*p['drafts'], p['summary']]:
        text = path.read_text(encoding='utf-8-sig')
        body = (f'\n- 状态：{p["scope"]}定稿留档完成，已保存场次画布。\n'
                f'- 场次画布：[下载]({adopt.link(path, p["canvas_path"])})\n'
                f'- 来源核对：[留档记录]({adopt.link(path, p["record"])})\n')
        if re.search(r'^### ' + re.escape(p['heading']) + r'\s*$', text, re.M):
            a, b = adopt.section(text, p['heading'])
            text = text[:a] + body + '\n' + text[b:]
        else:
            text = text.rstrip() + '\n\n### ' + p['heading'] + '\n' + body + '\n'
        replace_file(path, text)
    for actual, _ in p['sources']:
        mapped = adopt.load(actual['mapping_path'])
        mapped.setdefault('scene_finalizations', {})[plan['stage']] = str(p['record'])
        save_json(actual['mapping_path'], mapped)
    save_json(p['record'], {**record, 'state': 'completed', 'verified_at': stamp,
                           'checks': '全部P段实际批准／实际提交来源／本地冻结素材／场次画布与API',
                           'records': [str(path) for path in [*p['drafts'], p['summary']]]})
    update_progress(root, plan['episode'], plan['episode'] + '-' + plan['scene'], plan['stage'], p['summary'])
    saved = adopt.load(p['record'])
    save_json(p['record'], {**saved, 'records': saved['records'] + [str(p['progress'])]})
    result['state'] = 'completed'
    return result


def finalize(args, *, plan=None):
    root = Path(args.project).resolve(strict=True)
    if plan is None:
        plan_path = Path(args.plan)
        plan = adopt.load(plan_path if plan_path.is_absolute() else root / plan_path)
    if not plan.get('configuration_batches'):
        return finalize_one(root, plan, prepare(root, plan), args.apply)
    if not plan.get('configuration_batch_authorization'):
        raise ValueError('按配置分批留档须填写用户本次明确授权依据')
    batches = plan['configuration_batches']
    names = [b['name'] for b in batches]
    parts = [p for b in batches for p in b['parts']]
    expected = re.findall(r'^\| ' + re.escape(plan['episode'] + '-' + plan['scene']) + r' \|[^\n]*?\| ('
                          + re.escape(plan['episode'] + '-' + plan['scene']) + r'-P\d{3}) \|',
                          (root / '09-剧集制作' / plan['episode'] / '03-分镜脚本'
                           / (plan['episode'] + '-分镜索引.md')).read_text(encoding='utf-8-sig'), re.M)
    item_parts = [i['identity'].rsplit('-', 2)[0] for i in plan['items']]
    if (not expected or len(expected) != len(set(expected)) or len(names) != len(set(names))
            or any(not re.fullmatch(r'[\w-]+', n) for n in names)
            or len(parts) != len(set(parts)) or len(item_parts) != len(set(item_parts))
            or set(parts) != set(expected) or set(item_parts) != set(expected)
            or any(not b['parts'] for b in batches)):
        raise ValueError('授权分批必须各段唯一归属，并完整覆盖正式索引及本次留档清单')
    prepared = []
    for batch in batches:
        sub = {**plan, 'items': [i for i in plan['items'] if i['identity'].rsplit('-', 2)[0] in batch['parts']]}
        prepared.append((sub, prepare(root, sub, batch['parts'], batch['name'])))
    # Validate every source and configuration before writing any archive.
    results = [finalize_one(root, sub, p, args.apply) for sub, p in prepared]
    return {'state': 'completed' if args.apply else 'ready', 'mode': 'apply' if args.apply else 'dry_run',
            'authorization': plan['configuration_batch_authorization'], 'batches': results,
            'browser_sync': 'not_checked'}


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog='Python 3.11+，标准库。预览离线；--apply 仅保存场次画布、API和来源记录。路径及请求格式见 nora-drama-production/references/固定脚本接口规范.md。')
    parser.add_argument('--project', required=True, help='项目根；相对当前工作目录解析')
    parser.add_argument('--plan', required=True, help='阶段留档请求JSON；相对项目根解析')
    parser.add_argument('--apply', action='store_true', help='保存到阶段定稿目录并补齐现有记录；默认只读预览')
    args = parser.parse_args()
    try:
        print(json.dumps(finalize(args), ensure_ascii=False))
    except (ValueError, KeyError, OSError, AssertionError, client.ClientError) as error:
        print(json.dumps({'ok': False, 'error': str(error), 'type': type(error).__name__}, ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
