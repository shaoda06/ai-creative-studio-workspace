"""Serial-drama image preparation: types, approval, naming and business records."""
from copy import deepcopy
import json
from pathlib import Path
import re
import secrets
import sys
from urllib.parse import unquote
SKILLS = Path(__file__).resolve().parents[2]
for folder in ['nora-qwen-image', 'nora-image-processing']:
    sys.path.insert(0, str(SKILLS / folder / 'scripts'))
from qwen_image_workflow import assemble as assemble_qwen, execution_facts
from image_processing import assemble_rtx
from project_paths import project_file
from backend.services import image_closeout as images

SEEDS = {'人物上半身正面肖像图': '人物上半身正面肖像', '人物多视角参考图': '人物六视图',
         '服装参考图': '服装正背面图', '角色多视角参考图': '角色六视图', '道具三视图': '道具三视图',
         '场景参考图': '场景参考图', '首帧参考图': '首帧参考图'}
SIZES = {'人物上半身正面肖像图': (1024, 1024), '人物多视角参考图': (2048, 2048),
         '服装参考图': (1152, 864), '角色多视角参考图': (2048, 2048)}

def image_workflow(skill, spec, refs, width, height, seed, prefix, remote_output=None):
    files = [ref['file'] for ref in refs]
    if spec['task_type'] == 'image-upscale':
        return assemble_rtx(files[0], prefix=prefix, remote_output=remote_output,
                            size=[width, height] if 'size' in spec else None)
    return assemble_qwen(prompt=spec['prompt'], size=[width, height], seed=seed,
                         mode='edit' if files else 't2i', references=files,
                         parameters=spec.get('parameters', {}), prefix=prefix,
                         remote_output=remote_output)

def remote_prefix(root, *parts):
    """Build output-relative paths; each supplied identity is one path component."""
    names = (root.name, *parts)
    if any(not name or name in ('.', '..') or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name.endswith(('.', ' ')) for name in names):
        raise ValueError('远端输出名称须为合法的单个目录名或文件前缀')
    return '/'.join(names)


def reference(root, draft, ref, documents, *, require_seed=True):
    file = project_file(root, ref['file'])
    if file not in documents.image_sizes:
        documents.image_sizes[file] = images.png(file.read_bytes())
    size = documents.image_sizes[file]
    if ref.get('user_reference'):
        if not ref.get('basis'):
            raise ValueError('用户参考图须写明本次指定依据与用途')
        source_seed = ref.get('source_seed')
        if require_seed and source_seed is None and not (ref.get('source_kind') == '非生成' or ref.get('unknown_seed_basis')):
            raise ValueError('来源种子未知，须记录用户对未知来源的处理决定')
        basis = ref['basis']
    else:
        approval_file, heading = ref['approval'].split('#', 1)
        approval_path = project_file(root, approval_file)
        text = documents.read(approval_file)
        review = images.section(text, heading)[0]
        confirmation = re.search(r'^#### 4\. 用户确认\s*\n(.*?)(?=^#### |\Z)', review, re.M | re.S)
        if not confirmation or (images.value(confirmation[1], '结论') or images.value(confirmation[1], '决定')) != '批准采用':
            raise ValueError('输入参考图未批准：' + ref['file'])
        candidate_links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', images.value(confirmation[1], '批准的具体候选') or images.value(confirmation[1], '对应具体候选'))
        candidates = [project_file(root, approval_path.parent / unquote(link)) for link in candidate_links]
        formal = False
        for line in text.splitlines():
            if not line.startswith('|'):
                continue
            links = [unquote(link) for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', line)]
            if ('#' + heading) in links and any('#' not in link and project_file(root, approval_path.parent / link) == file for link in links):
                formal = True
        if file not in candidates and not formal:
            raise ValueError('输入不是该批准的具体候选或已登记正式文件：' + ref['file'])
        generation = re.search(r'生成记录-\d+', heading)[0]
        body = images.section(text, generation)[0]
        token = images.value(body, '种子、步数、CFG、采样器及调度器') or images.value(body, '种子、步数、CFG、采样器、调度器及其他实际参数')
        matched = re.match(r'(\d+)\b', token)
        source_seed = int(matched[1]) if matched else None
        if require_seed and source_seed is None and not ref.get('unknown_seed_basis'):
            raise ValueError('批准输入缺少原始种子依据：' + ref['file'])
        basis = images.link(draft, approval_path, '批准记录')[:-1] + '#' + heading + ')'
    return dict(file=file, size=size, seed=source_seed, purpose=ref['purpose'], basis=basis,
                unknown_seed_basis=ref.get('unknown_seed_basis', ''), non_generated=ref.get('source_kind') == '非生成')


def choose_seed(root, spec, refs, documents, generation_link):
    kind = SEEDS.get(spec['image_type']) if not spec.get('supplementary') else None
    position = root / '00-项目定位/项目基本定位.md'
    text = documents.read(position)
    rows = list(re.finditer(r'^\| ([^|\n]+) \| (\d+|首次生成时确定) \|[^\n]*', text or '', re.M))
    values = {row[1]: int(row[2]) for row in rows if row[2].isdigit()}
    if len(values.values()) != len(set(values.values())):
        raise ValueError('项目类别种子存在重复，请先解决原登记冲突')
    prior = set()
    if spec.get('supplementary'):
        previous = documents.read(spec['draft']) or ''
        prior = {int(n) for n in re.findall(r'^- 种子、[^：\n]*：([0-9]+)\b', previous, re.M)}
    selected = spec.get('seed', values.get(kind))
    if kind and kind not in [row[1] for row in rows]:
        raise ValueError('缺少项目七类种子表的目标类别：' + kind)
    if selected is None:
        selected = secrets.randbelow(2**53)
        while selected in values.values() or selected in prior or selected in [ref['seed'] for ref in refs]:
            selected = secrets.randbelow(2**53)
    if type(selected) is not int or selected < 0 or selected >= 2**64:
        raise ValueError('种子必须为有效非负整数')
    if selected in prior:
        raise ValueError('补充图须使用未在该工作稿历史使用过的新种子')
    if kind in values and selected != values[kind]:
        raise ValueError('任务种子与已登记类别不同；变更须先按原规则确认并更新登记')
    if any(value == selected for name, value in values.items() if name != kind) or any(ref['seed'] == selected for ref in refs):
        raise ValueError('种子与其他类别或实际输入冲突，不自动换值')
    if kind and kind not in values:
        row = next(row for row in rows if row[1] == kind)
        replacement = f'| {kind} | {selected} | {generation_link}；首次生成所选值，实际提交状态见后台记录 |'
        documents.put(position, text[:row.start()] + replacement + text[row.end():])
    return selected


def generation_record(skill, spec, generation, refs, seed, width, height, record, draft, candidate, api):
    template = images.template_path(skill, spec['kind']).read_text('utf-8-sig')
    template = re.search(r'````markdown\n(.*?)\n````', template, re.S)[1]
    body = images.section(template, '生成记录-001')[0].replace('### 生成记录-001', '### ' + generation, 1)
    names = re.findall(r'^- ([^：\n]+)：', body, re.M)
    values = {name: '不适用' for name in names}
    values.update(spec.get('fields', {}))
    native = spec['image_type'] in ('人物多视角参考图', '角色多视角参考图')
    facts = execution_facts(api, size=[width, height], has_references=bool(refs))
    sampler, encoder, model_names = facts['sampler'], facts['encoder'], facts['models']
    parameters, cache_text = facts['parameters'], facts['cache_text']
    api_link = images.link(draft, record / (record.name + '.api.json'), '实际API副本')
    workflow_entry = images.link(draft, record / (record.name + '.api.json'), 'API')
    workflow_entry += '；原始' + ('图生图' if refs else '文生图') + '画布仅保存在技能工作流目录'
    values.update({'创建时间': spec['created_at'], '生成／修改授权与计数': spec['authorization'] + '；本次目标1张；实际提交次数及状态见后台记录',
        '图片类型': spec['image_type'], '生成方式与任务用途': ('图生图' if refs else '文生图') + '；' + spec.get('purpose', '基础参考图'),
        '人物状态': spec.get('state', '不适用'), '服装状态': spec.get('costume', '不适用'),
        '本次目标': spec.get('description', spec['title']), '本次目标、保留与变化': spec.get('description', spec['title']),
        '依据的资料卡及版本': spec.get('basis', '任务清单所列当前需求及已批准输入'),
        '本次工作流副本入口': workflow_entry,
        '本次任务副本入口': workflow_entry,
        '目标尺寸、格式及数量': f'{width}×{height}、PNG、1张',
        '实际反向提示词': encoder['negative_prompt'] or '空',
        '模型及工作流': '；'.join(model_names) + '；' + api_link,
        '模型与工作流基准': '；'.join(model_names) + '；' + api_link,
        '种子、步数、CFG、采样器及调度器': parameters,
        '种子、步数、CFG、采样器、调度器及其他实际参数': parameters + '；denoise=' + str(sampler['denoise']) + '；' + api_link,
        '其他实际参数（如降噪、缓存设置）': f"denoise={sampler['denoise']}；" + cache_text,
        '参考图预处理与画布设置': facts['preprocessing'] + ('；输入顺序见第2节' if refs else ''),
        '请求响应与执行结果入口': '实际通信证据与状态见' + images.link(draft, record / '后台任务状态.json', '后台状态'),
        '请求、上传／提交响应及执行结果入口': '实际通信证据与状态见' + images.link(draft, record / '后台任务状态.json', '后台状态'),
        '种子选择与输入避重依据': '按项目类别登记；' + '；'.join(f'输入{i+1}原始种子：{r["seed"] if r["seed"] is not None else ("不适用" if r["non_generated"] else "未知；" + r["unknown_seed_basis"])}' for i, r in enumerate(refs)),
        '执行状态': '技术状态见' + images.link(draft, record / '后台任务状态.json', '后台状态'),
        '真实执行状态': '技术状态见' + images.link(draft, record / '后台任务状态.json', '后台状态'),
        '输出候选文件': '尚未取得实际输出；计划保存：' + images.link(draft, candidate, '计划候选'),
        '候选文件入口': '尚未取得实际输出；计划保存：' + images.link(draft, candidate, '计划候选'),
        '实际尺寸、格式及数量': '待核对', '失败或异常说明': '具体状态及问题见后台记录',
        '批准后超分': '不适用，原生图直接保存' if native else '待批准',
        '文件核对结论': '待核对', '文件核对证据与异常': '结果由后台收尾；尚无实际输出',
        '看图调用状态': '未调用（默认）', '审阅记录入口': '实际候选取回后由后台登记',
        '用户采用状态': '未送审', '用户决定原因与依据': '尚无本轮候选与采用决定', '正式文件入口': '尚未采用',
        '用户决定及具体候选、批准依据': '未送审；尚无本轮候选与采用决定',
        'client_id、prompt_id': '见' + images.link(draft, record / '后台任务状态.json', '后台任务状态')})
    body = images.fields(body, values)
    body = re.sub(r'```json\n\{\}\n```', lambda _: '```json\n' + json.dumps(spec['prompt'], ensure_ascii=False, indent=2) + '\n```', body, count=1)
    start = body.index('#### 2. 输入参考')
    end = body.index('#### 3.', start)
    inputs = '\n'.join(f'- 输入{i+1}：{images.link(draft,r["file"])}；用途：{r["purpose"]}；{r["size"][0]}×{r["size"][1]}；来源／批准：{r["basis"]}；原始种子：{r["seed"] if r["seed"] is not None else "未知或不适用，见来源依据"}' for i, r in enumerate(refs)) or '- 无输入参考图。'
    return body[:start] + '#### 2. 输入参考\n\n' + inputs + '\n\n' + body[end:]


def adoption_updates(root, draft, text, generation, heading, source, spec):
    """Fill the existing formal-assets table; optional extra associations remain explicit."""
    area = re.search(r'^## 1\. 当前正式资产\s*\n(.*?)(?=^## |\Z)', text, re.M | re.S)[1]
    rows = [line for line in area.splitlines() if line.startswith('|')]
    columns = [name.strip() for name in rows[0].strip('|').split('|')]
    body = images.section(text, generation)[0]
    version = re.search(r'-v(\d+)', source.stem)
    values = {name: images.value(body, name) for name in columns}
    values.update({'正式文件': '{{file}}', '审阅记录': '[批准](#' + heading + ')',
        '采用的候选版本': ('v' + version[1] if version else source.stem) + '／' + spec['upscale_number'],
        '采用候选版本': ('v' + version[1] if version else source.stem) + '／' + spec['upscale_number']})
    values.update(spec.get('adoption_fields', {}))
    formal = project_file(root, spec['formal'])
    previous = []
    for row in rows[2:]:
        links = re.findall(r'\]\(([^)]+)\)', row)
        if any('#' not in link and project_file(root, draft.parent / unquote(link)) == formal for link in links):
            previous.append(row)
    if len(previous) > 1:
        raise ValueError('正式资产表中同一正式文件重复')
    if '封面编号' in columns and not values.get('封面编号') and previous:
        values['封面编号'] = previous[0].strip('|').split('|')[columns.index('封面编号')].strip()
    missing = [name for name in columns if not values.get(name) or values[name] == '不适用']
    # 不适用 is a valid explicit state for portraits/base bodies, but not a missing scope or view.
    missing = [name for name in missing if name not in ('人物状态', '服装状态', '列表封面')]
    if missing:
        raise ValueError('正式资产表缺少已确认内容，请在adoption_fields填写：' + '、'.join(missing))
    if '列表封面' in columns and '列表封面' not in spec.get('adoption_fields', {}):
        values['列表封面'] = (previous[0].strip('|').split('|')[columns.index('列表封面')].strip()
                            if previous else '')
    replacement = '| ' + ' | '.join(values[name] for name in columns) + ' |'
    old = previous[0] if previous else '\n'.join(rows[:2])
    new = replacement if previous else old + '\n' + replacement
    return [dict(path=draft.relative_to(root).as_posix(), old=old, new=new), *spec.get('adoption_updates', [])]


def build_image(root, skill, spec, documents, now):
    if spec['kind'] == '封面' and spec['task_type'] == 'image':
        from backend.parsers.covers import cover_fields
        spec = {**spec, 'fields': cover_fields(spec.get('fields', {}), documents.read)}
    draft = project_file(root, spec['draft'])
    text = documents.read(draft)
    if text is None:
        template = images.template_path(skill, spec['kind']).read_text('utf-8-sig')
        text = re.search(r'````markdown\n(.*?)\n````', template, re.S)[1]
        text = '# ' + draft.stem + '\n' + text.split('\n', 1)[1]
        text = text[:text.index('### 生成记录-001')] + text[text.index('## 3. 讨论与修改'):text.index('### 审阅-生成记录-001-001')]
    refs = [reference(root, draft, ref, documents, require_seed=spec['task_type'] != 'image-upscale') for ref in spec.get('references', [])]
    if spec['task_type'] == 'image-upscale':
        if len(refs) != 1:
            raise ValueError('超分必须选择一个获批输入')
        approval = spec['references'][0]['approval']
        approval_file, heading = approval.split('#', 1)
        if project_file(root, approval_file) != draft:
            raise ValueError('超分必须在原生成工作稿留档')
        generation = re.search(r'生成记录-\d+', heading)[0]
        target = spec.get('size', [n * 2 for n in refs[0]['size']])
        if not isinstance(target, (list, tuple)) or len(target) != 2 or any(type(n) is not int or n <= 0 for n in target):
            raise ValueError('超分size须为两个正整数像素宽高')
        width, height = target
        local = tuple(target) == tuple(refs[0]['size']) or any(n < old for n, old in zip(target, refs[0]['size']))
        label = '规格处理' if local else '超分'
        numbers = [int(n) for n in re.findall(label + r'-(\d+)', images.section(text, generation)[0])]
        number = spec.get('processing_number' if local else 'upscale_number', f'{label}-{max(numbers, default=0)+1:03d}')
        prefix = spec['object'] + '-' + generation + '-' + number
        processing = f'RTX指定尺寸{width}×{height}' if 'size' in spec else '固定RTX2倍'
        if local:
            processing = f'本地等比缩放与裁切{width}×{height}'
        candidate = project_file(root, spec.get('output', str(refs[0]['file'].with_name(refs[0]['file'].stem + '-' + number + '.png'))))
        record = project_file(root, spec.get('record_dir', str(draft.parent.parent / '执行附件' / prefix)))
        plan = dict(draft=draft.relative_to(root).as_posix(), kind=spec['kind'], generation=generation, review=heading,
            images=[dict(path=candidate.relative_to(root).as_posix(), width=width, height=height)],
            upscale=dict(number=number, source=refs[0]['file'].relative_to(root).as_posix(), approval=approval,
                         formal=spec['formal'], record_updates=adoption_updates(root, draft, text, generation, heading, refs[0]['file'], {**spec, 'upscale_number': number})))
        if spec.get('archive'):
            plan['upscale']['archive'] = spec['archive']
        if local:
            plan['local_processing'] = dict(source_size=list(refs[0]['size']), crop_anchor=spec.get('crop_anchor', [0.5, 0.5]))
        body = images.section(text, generation)[0]
        changed = images.fields(body, {'批准后超分': '已批准待本地规格处理' if local else '已批准待超分；进度见后台状态',
            '超分编号及批准输入': number + '；' + images.link(draft, refs[0]['file']) + '；[原批准](#' + heading + ')',
            '超分工作流、参数与任务ID': processing + '；' + images.link(draft, record / ('结果收尾报告.json' if local else '后台任务状态.json'), '处理记录' if local else '后台状态')})
        text = text.replace(body, changed, 1)
        seed = None
    else:
        number = max((int(n) for n in re.findall(r'^### 生成记录-(\d+)', text, re.M)), default=0) + 1
        generation = spec.get('generation', f'生成记录-{number:03d}')
        prefix = spec['object'] + '-' + generation
        if re.search(r'^### ' + re.escape(generation) + r'\s*$', text, re.M):
            raise ValueError('新生成编号已存在，不能覆盖：' + generation)
        width, height = spec.get('size', SIZES.get(spec['image_type'], (None, None)))
        if not width or not height or width % 32 or height % 32:
            raise ValueError('明确图片尺寸须为有效32倍数；其他类型请在size指定既定尺寸')
        if not spec.get('formal') and spec['image_type'] != '画风样例':
            raise ValueError('新图片任务须填写formal正式图片路径，再确定候选名称')
        stem = project_file(root, spec['formal']).stem if spec.get('formal') else '项目基本定位-画风验证'
        board = re.fullmatch(r'(.+-手绘导演分镜表)-第([0-9]{2,})页', stem)
        pattern = (re.escape(board[1]) + r'-v([0-9]{2,})-第' + board[2] + r'页\.png') if board else re.escape(stem) + r'-候选-v([0-9]{2,})\.png'
        versions = []
        for area in re.finditer(r'^### 生成记录-\d+\s*\n.*?(?=^#{1,3} |\Z)', text, re.M | re.S):
            for path in re.findall(r'\]\(([^)]+\.png)\)', images.value(area[0], '输出候选文件') or images.value(area[0], '候选文件入口')):
                version = re.fullmatch(pattern, Path(unquote(path)).name)
                if version: versions.append(int(version[1]))
        version = max(versions, default=0) + 1
        filename = f'{board[1]}-v{version:02d}-第{board[2]}页.png' if board else f'{stem}-候选-v{version:02d}.png'
        candidate = project_file(root, spec.get('output', str(draft.parent / '素材' / filename)))
        record = project_file(root, spec.get('record_dir', str(draft.parent.parent / '执行附件' / prefix)))
        seed = choose_seed(root, spec, refs, documents, images.link(root / '00-项目定位/项目基本定位.md', draft, generation)[:-1] + '#' + generation + ')')
        plan = dict(draft=draft.relative_to(root).as_posix(), kind=spec['kind'], generation=generation,
                    review='审阅-' + generation + '-001', images=[dict(path=candidate.relative_to(root).as_posix(), width=width, height=height)])
    if spec.get('formal'):
        plan['formal'] = project_file(root, spec['formal']).relative_to(root).as_posix()
    plan['image_type'] = spec['image_type'] if 'image_type' in spec else images.value(images.section(text, generation)[0], '图片类型')
    images.validate_names(root, plan, required=True)
    if candidate.exists():
        raise ValueError('候选文件已存在，不能覆盖：' + str(candidate))
    if plan.get('local_processing'):
        documents.new_json(record / (prefix + '-本地处理计划.json'), plan)
        documents.put(draft, text)
        return dict(project=str(root), task_type=spec['task_type'], title=spec['title'], workflow={}, uploads=[], image_plan=plan,
            record_dir=str(record), outputs=[dict(node_id='local', output_key='images', index=0, path=str(candidate), response_name=prefix+'-处理结果.json')],
            attempt_name=prefix+'-执行尝试.json', request_name=prefix+'-本地请求.json', response_name=prefix+'-本地响应.json', history_name=prefix+'-执行结果.json')
    image_type = spec.get('image_type') or images.value(images.section(text, generation)[0], '图片类型')
    remote_name = spec['object'] + '-' + image_type + '-' + prefix[len(spec['object']) + 1:]
    category = '剧集专用' if spec['kind'] == '剧集素材' else spec['kind']
    if image_type == '画风样例':
        remote_output = remote_prefix(root, '图片生成', '画风样例', prefix)
    elif category == '剧集专用':
        episode = re.search(r'(?:EP\d+|片头|片尾)', spec['object'])[0]
        remote_output = remote_prefix(root, '图片生成', category, episode, remote_name)
    else:
        remote_output = remote_prefix(root, '图片生成', category, spec['object'], remote_name)
    canvas, api, uploads, output_node = image_workflow(skill, spec, refs, width, height, seed, prefix, remote_output)
    if spec['task_type'] == 'image':
        body = generation_record(skill, {**spec, 'created_at': now}, generation, refs, seed, width, height, record, draft, candidate, api)
        marker = re.search(r'^## 3\. 讨论与修改\s*$', text, re.M)
        if not marker:
            raise ValueError('图片工作稿不符合既有模板：' + spec['draft'])
        text = text[:marker.start()] + body.rstrip() + '\n\n' + text[marker.start():]
    for suffix, content in [('.workflow.json', canvas), ('.api.json', api), ('-上传映射.json', uploads), ('-成果取回映射.json', [dict(node_id=output_node, output_key='images', index=0, path=candidate.relative_to(root).as_posix(), response_name=prefix+'-取回响应.json')]), ('-图片收尾计划.json', plan)]:
        if content is not None:
            documents.new_json(record / (prefix + suffix), content)
    documents.put(draft, text)
    return dict(project=str(root), task_type=spec['task_type'], title=spec['title'], workflow=api, uploads=uploads, image_plan=plan,
        record_dir=str(record), outputs=[dict(node_id=output_node, output_key='images', index=0, path=str(candidate), response_name=prefix+'-取回响应.json')],
        attempt_name=prefix+'-提交尝试.json', request_name=prefix+'-请求.json', response_name=prefix+'-提交响应.json', history_name=prefix+'-执行结果.json')
