"""Image technical checks and prepared document associations; no visual judgement."""
import hashlib
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote

import sys
SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / 'nora-workspace-browser/scripts'))
from document_fields import fields, link
sys.path.insert(0, str(SKILLS / "nora-image-processing/scripts"))
import image_files
from image_files import inspect_remote
from image_processing import validate_processing

def png(raw):
    return image_files.png(raw)
from project_paths import project_file
import project_progress
from prepared_documents import write_json


TEMPLATES = {'人物': '人物参考图工作稿模板.md', '场景': '场景参考图工作稿模板.md',
             '道具': '道具参考图工作稿模板.md', '剧集素材': '剧集素材工作稿模板.md',
             '封面': '封面制作工作稿模板.md'}


def template_path(skill, kind):
    folder = (SKILLS / 'nora-cover-images/templates'
              if kind == '封面' else Path(__file__).resolve().parents[1] / 'references/模板')
    return folder / TEMPLATES[kind]


def progress_phases(root, drafts):
    phases = set()
    for draft in drafts:
        parts = project_file(root, draft).relative_to(root).parts
        if parts[0] == '09-剧集制作':
            phases.add(parts[1] + '制作')
        else:
            phases.update({'03-人物资料': ('人物资料卡', '人物参考图'),
                           '04-场景资料': ('场景资料卡', '场景参考图'),
                           '05-道具资料': ('道具资料卡', '道具参考图'),
                           '10-社交媒体资料': ('封面制作',)}[parts[0]])
    return phases


def validate_record_updates(root, drafts, updates, *, tokens=(), contents=None):
    """Preview exact association edits without publishing them or rendering future outputs."""
    edits = {}
    for update in updates:
        if (set(update) != {'path', 'old', 'new'}
                or any(not isinstance(update[name], str) or not update[name] for name in update)):
            raise ValueError('图片关联更新须为非空path/old/new文字')
        path = project_file(root, update['path'])
        if path.suffix != '.md':
            raise ValueError('图片关联更新只允许项目Markdown')
        if set(re.findall(r'\{\{[^{}]+\}\}', update['new'])) - set(tokens):
            raise ValueError('图片关联更新有未知占位符')
        if path not in edits:
            text = contents[path] if contents is not None and path in contents else path.read_text('utf-8-sig')
            edits[path] = text, text
        before, text = edits[path]
        if update['old'] == update['new'] or text.count(update['new']) == 1:
            continue
        if text.count(update['old']) != 1:
            raise ValueError('图片关联更新源文字变化或不唯一：' + str(path))
        edits[path] = before, text.replace(update['old'], update['new'], 1)
    progress = root / '项目进度.md'
    if progress in edits:
        project_progress.validate_update(*edits[progress], phases=progress_phases(root, drafts))
    return edits


def record_updates(plan):
    return [*plan.get('record_updates', []), *plan.get('upscale', {}).get('record_updates', [])]


def with_record_updates(plan, updates):
    plan = deepcopy(plan)
    plan['record_updates'] = [] if plan.get('upscale') else updates
    if plan.get('upscale'):
        plan['upscale']['record_updates'] = updates
    return plan


def repair_record_updates(root, drafts, current, repair, report_file, *, identity=None):
    """Repair only exact record edits; retain immutable task/approval evidence and an audit copy."""
    previous = json.loads(report_file.read_text('utf-8-sig')) if report_file.exists() else None
    if previous and identity and any(previous.get(name) != value for name, value in identity.items()):
        raise ValueError('登记修复报告不属于原任务或成果，不覆盖')
    if previous and previous.get('record_repair') == repair:
        return repair['updates']
    if (set(repair) != {'reason', 'expected_updates', 'updates'}
            or not isinstance(repair['reason'], str) or not repair['reason'].strip()
            or repair['expected_updates'] != current):
        raise ValueError('登记修复须说明原因并匹配当前关联更新，不覆盖其他修复')
    if previous and previous['status'] in ('registered', 'completed'):
        raise ValueError('图片已登记，不再改写登记计划；网页失败只接续核验')
    allowed = {project_file(root, item['path']) for item in current}
    if any(project_file(root, item['path']) not in allowed for item in repair['updates']):
        raise ValueError('登记修复不能新增写入文件')
    edits = validate_record_updates(root, drafts, repair['updates'])
    for before, after in edits.values():
        confirmations = re.findall(r'^#### 4\. 用户确认\s*\n.*?(?=^#### |^### |^## |\Z)', before, re.M | re.S)
        if any(block not in after for block in confirmations):
            raise ValueError('登记修复不能改写已有用户确认或批准依据')
    if previous:
        count = len(current)
        prefix = previous['updates'][:-count] if count else previous['updates']
        tail = previous['updates'][-count:] if count else []
        if [(u['path'], u['old']) for u in tail] != [(u['path'], u['old']) for u in current]:
            raise ValueError('收尾报告与关联更新不符，不猜测或改写系统登记项')
        # Keep system-generated edits intact; they still undergo the final source/approval checks.
        revised = {**previous, 'updates': [*prefix, *repair['updates']],
                   'record_repair': repair, 'registration_updates': repair['updates']}
    index = 1
    archive = report_file.with_name(report_file.stem + f'-登记修复前-{index:03d}.json')
    while archive.exists():
        index += 1
        archive = report_file.with_name(report_file.stem + f'-登记修复前-{index:03d}.json')
    write_json(archive, {'report': previous, 'record_updates': current, 'repair': repair})
    if previous:
        if json.loads(report_file.read_text('utf-8-sig')) != previous:
            raise ValueError('收尾报告并发变化，不覆盖')
        write_json(report_file, revised)
    return repair['updates']


def section(text, heading):
    found = list(re.finditer(r'^### ' + re.escape(heading) + r'\s*\n.*?(?=^#{1,3} |\Z)', text, re.M | re.S))
    if len(found) != 1:
        raise ValueError('记录章节缺失或重复：' + heading)
    return found[0]


def value(text, name):
    match = re.search(r'^- ' + re.escape(name) + r'：([^\n]*)', text, re.M)
    return match[1].strip() if match else ''








def validate_names(root, plan, *, required=False):
    """Bind new candidate destinations to their declared formal image identity."""
    up = plan.get('upscale')
    formal_name = plan.get('formal') or (up.get('formal') if up and required else None)
    if formal_name is None:
        if required and plan.get('image_type') != '画风样例':
            raise ValueError('新图片任务须填写formal正式图片路径，再确定候选名称')
        if not required:
            return  # Historical execution plans retain their submitted destinations.
    formal = project_file(root, formal_name) if formal_name else Path('项目基本定位-画风验证.png')
    draft = project_file(root, plan['draft'])
    if up and formal != project_file(root, up['formal']):
        raise ValueError('处理结果的formal与正式保存路径不一致')
    for item in plan['images']:
        candidate = project_file(root, item['path'])
        if candidate.parent != draft.parent / '素材':
            raise ValueError('新图片候选须保存到工作稿/素材/')
        base = re.escape(formal.stem) + r'-候选-v[0-9]{2,}'
        board = re.fullmatch(r'(.+-手绘导演分镜表)-第([0-9]{2,})页', formal.stem)
        if up:
            source = project_file(root, up['source'])
            if not re.fullmatch(base, source.stem):
                raise ValueError('批准原候选与正式图片名称不一致；先按授权整理来源，不改写原批准')
            valid = candidate.name == source.stem + '-' + up['number'] + '.png'
        elif plan.get('kind') == '社交媒体':
            valid = bool(candidate.suffix and re.fullmatch(base + r'-(?:原生|[1-9][0-9]*x[1-9][0-9]*)', candidate.stem))
        elif board:
            valid = bool(re.fullmatch(re.escape(board[1]) + r'-v[0-9]{2,}-第' + board[2] + r'页\.png', candidate.name))
        else:
            valid = bool(re.fullmatch(base + r'\.png', candidate.name))
        if not valid:
            raise ValueError('新图片候选须按对应正式图片名及规定处理编号命名，不追加工具、比例等后缀：' + candidate.name)


def validate_plan(data, *, check_records=True):
    plan = data.image_plan
    if plan is None:
        raise ValueError('图片缺少image_plan收尾关联；旧任务需显式补充原记录关联，不自动猜测')
    if data.task_type not in ('image', 'image-upscale') or plan['kind'] not in TEMPLATES:
        raise ValueError('图片收尾类型错误')
    root = Path(data.project)
    validate_names(root, plan)
    draft = project_file(root, plan['draft'])
    text = draft.read_text('utf-8-sig')
    generation = section(text, plan['generation'])[0]
    for choices in (('输出候选文件', '候选文件入口'), ('执行状态', '真实执行状态'), ('实际尺寸、格式及数量',),
                    ('文件核对结论',), ('审阅记录入口',)):
        if not any(re.search(r'^- ' + re.escape(name) + '：', generation, re.M) for name in choices):
            raise ValueError('图片生成条目缺少模板字段：' + '／'.join(choices))
    if not re.search(r'^## 4\. 审阅区\s*$', text, re.M):
        raise ValueError('图片工作稿缺少模板审阅区')
    if not re.fullmatch(r'审阅-生成记录-\d{3,}-\d{3,}', plan['review']):
        raise ValueError('图片审阅章节编号错误')
    planned = {project_file(root, item['path']): item for item in plan['images']}
    if not planned or len(planned) != len(plan['images']) or set(planned) != {Path(item.path) for item in data.outputs}:
        raise ValueError('图片收尾范围与输出映射不符')
    if any(type(item[k]) is not int or item[k] <= 0 for item in planned.values() for k in ('width', 'height')):
        raise ValueError('图片目标尺寸必须为正整数')
    up = plan.get('upscale')
    if data.task_type == 'image-upscale':
        if not up or len(planned) != 1:
            raise ValueError('超分必须关联一个获批输入和一个输出')
        if up.get('review_required'):
            raise ValueError('用户要求超分后再审，不能使用自动正式采用计划')
        local = plan.get('local_processing')
        if not re.fullmatch(('规格处理' if local else '超分') + r'-\d{3,}', up['number']):
            raise ValueError('超分子记录编号错误')
        source = project_file(root, up['source'])
        approval_file, heading = up['approval'].split('#', 1)
        approval_path = project_file(root, approval_file)
        if approval_path != draft or heading != plan['review']:
            raise ValueError('超分必须关联原生成条目的原批准章节')
        approved = section(approval_path.read_text('utf-8-sig'), heading)[0]
        confirmation = re.search(r'^#### 4\. 用户确认\s*\n(.*?)(?=^#### |\Z)', approved, re.M | re.S)
        if not confirmation or (value(confirmation[1], '结论') or value(confirmation[1], '决定')) != '批准采用':
            raise ValueError('超分原图没有明确批准')
        candidates = re.findall(r'\[[^\]]*\]\(([^)]+)\)', value(confirmation[1], '批准的具体候选') or value(confirmation[1], '对应具体候选'))
        if not any(project_file(root, (approval_path.parent / unquote(path)).resolve(), recorded=True) == source for path in candidates):
            raise ValueError('超分输入不是批准的具体候选')
        output = next(iter(planned.values()))
        target = (output['width'], output['height'])
        source_size = png(source.read_bytes())
        validate_processing(data, source, source_size, target, local)
        formal = project_file(root, up['formal'])
        if formal == source or formal in planned or formal.is_relative_to(Path(data.record_dir)):
            raise ValueError('超分正式文件必须与审批原图、候选及执行附件分开')
        if up.get('archive') and project_file(root, up['archive']) in (formal, source, *planned):
            raise ValueError('归档入口不得指向正式文件、审批原图或候选')
        if not up['record_updates']:
            raise ValueError('超分须预先提供正式资产表及关联入口的采用更新')
    elif up:
        raise ValueError('普通图片不能带超分采用计划')
    tokens = ['{{outputs}}', '{{specs}}', '{{time}}', '{{evidence}}'] + (['{{file}}'] if up else [])
    if check_records:
        validate_record_updates(root, [plan['draft']], record_updates(plan), tokens=tokens)
    return draft, text, planned


def review_text(skill, plan, generation, links, specs, evidence, stamp):
    template = template_path(skill, plan['kind']).read_text('utf-8-sig')
    template = re.search(r'````markdown\n(.*?)\n````', template, re.S)[1]
    review = section(template, '审阅-生成记录-001-001')[0]
    review = review.replace('### 审阅-生成记录-001-001', '### ' + plan['review'], 1)
    # Only fill fixed template fields; creative identity comes from the prepared generation entry.
    common = {'文件核对结论': '通过', '实际尺寸、格式、数量及可解码性': specs,
              '文件完整性、来源版本与请求核对证据': evidence,
              '图片身份、用途及适用状态的记录依据': '[生成记录](#' + plan['generation'] + ')；技术核验不代表画面符合目标',
              '看图调用状态': '未调用（默认）', '看图授权及限定范围': '不适用', '授权查看的发现': '不适用',
              '本次展示候选及原图入口': links + '；审核入口已登记，同步结果见收尾报告；登记时间：' + stamp,
              '文件或记录异常及处理': '无', '用户反馈的问题、位置与依据': '尚无反馈',
              '用户要求的修改及保留范围': '尚无', '修改／重试授权与次数': '不追加生成',
              '关联的上一轮候选及记录入口': value(generation, '关联的上一轮生成或审阅记录') or '不适用',
              '结论': '待确认', '决定': '待确认', '决定原因': '尚未决定', '批准的具体候选': '未批准',
              '对应具体候选': links, '确认范围': '尚未批准', '确认时间与依据': '尚未确认',
              '留存用途': '待审候选及真实生成记录', '当前制作适用性': '待核对；等待用户审核',
              '对应生成记录': '[生成记录](#' + plan['generation'] + ')', '来源生成记录': '[生成记录](#' + plan['generation'] + ')',
              '本轮候选文件及版本': links, '候选文件及版本': links, '具体候选文件及版本': links,
              '人物状态、服装状态': value(generation, '人物状态') + '；' + value(generation, '服装状态'),
              '批准后超分状态与关联': value(generation, '批准后超分') or '不适用',
              '超分文件核对与交付': '尚未执行', '正式保存位置': '尚未正式保存'}
    names = re.findall(r'^- ([^：\n]+)：', review, re.M)
    for name in names:
        common.setdefault(name, value(generation, name) or '不适用；尚未采用')
    return fields(review, common).rstrip() + '\n\n'


def register(store, key, outputs, report_file):
    data, state = store.rows[key]['input'], store.rows[key]['state']
    if data.image_plan is None and state.get('image_closeout_plan'):
        data = data.model_copy(update={'image_plan': state['image_closeout_plan']})
    if 'image_registration_updates' in state:
        data = data.model_copy(update={'image_plan': with_record_updates(data.image_plan, state['image_registration_updates'])})
    previous = json.loads(report_file.read_text('utf-8')) if report_file.exists() else None
    if previous:
        if previous['task_id'] != key or previous['prompt_id'] != state['prompt_id']:
            raise ValueError('图片收尾报告不属于本次执行')
        for proof in previous['checks']:
            current = project_file(data.project, proof['path']).stat()
            if [current.st_size, current.st_mtime_ns] != proof['stamp']:
                raise ValueError('图片收尾已核验证据发生变化：' + proof['path'])
        if previous.get('approval'):
            proof = previous['approval']
            current = project_file(data.project, proof['path']).read_text('utf-8-sig')
            if proof['text'] not in section(current, proof['heading'])[0]:
                raise ValueError('超分原批准依据已变化，请核对')
        if previous['status'] == 'registered':
            return previous
        return apply(store, key, previous, report_file)
    draft, original, planned = validate_plan(data)
    plan, root = data.image_plan, Path(data.project)
    if len(outputs) != len(planned):
        raise ValueError('图片取回摘要缺项')
    stamp = store.client.now()
    inspected, checked, upload_receipts, request = inspect_remote(data, state, outputs, planned)
    for item in inspected:
        item['draft'] = plan['draft']
    links = '；'.join(link(draft, project_file(root, item['path'])) for item in inspected)
    specs = '；'.join(f"{item['width']}×{item['height']}、PNG、{item['bytes']}字节、可解码" for item in inspected) + f'；数量{len(inspected)}'
    evidence = '；'.join(link(draft, project_file(root, item['receipt']), '取回凭据') for item in inspected)
    evidence += '；' + link(draft, Path(data.record_dir) / data.request_name, '实际请求') + '；远端任务：' + state['prompt_id']
    generation = section(original, plan['generation'])[0]
    original_generation = generation
    updates = []
    changes = {'实际尺寸、格式及数量': specs, '文件核对结论': '通过', '文件核对证据与异常': evidence,
               'client_id、prompt_id': state.get('client_id', '') + '；' + state['prompt_id'],
               'client ID／prompt ID': state.get('client_id', '') + '；' + state['prompt_id']}
    up = plan.get('upscale')
    if not up:
        for index, binding in enumerate(data.uploads, 1):
            receipt_path = Path(data.record_dir) / binding['response-name']
            uploaded = upload_receipts[receipt_path]
            generation = re.sub(r'^- 输入' + str(index) + r'：[^\n]*',
                lambda match: match[0] + '；实际上传：' + uploaded['input_path'] + '；槽位：' + binding['node'] + '.' + binding['input'] + '；' + link(draft, receipt_path, '上传凭据'), generation, flags=re.M)
        changes['请求响应与执行结果入口'] = evidence
        changes['请求、上传／提交响应及执行结果入口'] = evidence
    if up:
        source = project_file(root, up['source'])
        source_bytes = source.read_bytes()
        source_size = png(source_bytes)
        upload = upload_receipts[Path(data.record_dir) / data.uploads[0]['response-name']]
        checked.append(source)
        if upload['sha256'] != hashlib.sha256(source_bytes).hexdigest() or request['prompt']['2']['inputs']['image'] != upload['input_path']:
            raise ValueError('超分实际上传与批准原图不符')
        item = inspected[0]
        resize = data.workflow['1']['inputs']
        if resize['resize_type'] == 'scale by multiplier' and (item['width'], item['height']) != tuple(n * 2 for n in source_size):
            raise ValueError('超分实际尺寸不是批准原图的两倍')
        processing = f"指定尺寸{item['width']}×{item['height']}" if resize['resize_type'] == 'target dimensions' else '2倍'
        formal = project_file(root, up['formal'])
        changes = {'批准后超分': '成功', '超分输出文件及实际规格': links + '；' + specs,
                   '超分请求响应与执行结果入口': evidence, '超分工作流、参数与任务ID': 'RTXVideoSuperResolution；' + processing + '；' + state['prompt_id'],
                   '正式文件入口': link(draft, formal), '用户采用状态': '已采用'}
        changed = fields(generation, changes)
        subrecord = ('##### ' + up['number'] + '\n\n- 超分本地任务与远端任务：' + key + '；' + state['prompt_id']
                     + '\n- 批准输入与原批准：' + link(draft, source) + '；[批准记录](#' + plan['review'] + ')'
                     + f'\n- 尺寸处理方式与原图规格：{processing}；原图{source_size[0]}×{source_size[1]}'
                     + '\n- 超分成果与文件核对：' + links + '；' + specs + '\n- 执行证据：' + evidence + '\n\n')
        if re.search(r'^##### ' + re.escape(up['number']) + r'\s*$', changed, re.M):
            raise ValueError('超分子记录编号已使用')
        changed = changed.replace('#### 5. 检查与采用', subrecord + '#### 5. 检查与采用', 1)
        review = section(original, plan['review'])[0]
        new_review = fields(review, {'批准后超分状态与关联': '成功；批准后' + processing + '超分；' + links,
                  '超分文件核对与交付': specs + '；' + evidence, '正式保存位置': link(draft, formal),
                  '批准后超分状态及执行入口': '成功；' + evidence, '超分输出及实际规格': specs})
        updates.append({'path': plan['draft'], 'old': review, 'new': new_review})
    else:
        changes.update({'执行状态': 'completed；全部预期图片已保存', '真实执行状态': 'completed；全部预期图片已保存',
                        '输出候选文件': links, '候选文件入口': links,
                        '审阅记录入口': '[审阅记录](#' + plan['review'] + ')'})
        if value(generation, '用户采用状态') == '未送审':
            changes['用户采用状态'] = '待确认'
        changed = fields(generation, changes)
        if not re.search(r'^### ' + re.escape(plan['review']) + r'\s*$', original, re.M):
            # Insert within the existing review area, before optional supplements.
            area = re.search(r'^## 4\. 审阅区\s*\n.*?(?=^## |\Z)', original, re.M | re.S)
            if not area:
                raise ValueError('图片工作稿缺少审阅区')
            review = review_text(None, plan, generation, links, specs, evidence, stamp)
            updates.append({'path': plan['draft'], 'old': area[0], 'new': area[0].rstrip() + '\n\n' + review})
        else:
            review = section(original, plan['review'])[0]
            if not any(item['path'].split('/')[-1] in review for item in inspected):
                raise ValueError('审阅编号已用于其他候选')
    updates.insert(0, {'path': plan['draft'], 'old': original_generation, 'new': changed})
    for update in [*plan.get('record_updates', []), *(up['record_updates'] if up else [])]:
        update = dict(update)
        target = project_file(root, update['path'])
        replacements = {'{{specs}}': specs, '{{time}}': stamp,
                        '{{outputs}}': '；'.join(link(target, project_file(root, item['path'])) for item in inspected),
                        '{{evidence}}': '；'.join(link(target, project_file(root, item['receipt']), '取回凭据') for item in inspected)}
        if up:
            replacements['{{file}}'] = link(target, formal)
        for token, content in replacements.items():
            update['new'] = update['new'].replace(token, content)
        if re.search(r'\{\{[^{}]+\}\}', update['new']):
            raise ValueError('图片关联更新有未知占位符')
        updates.append(update)
    report = {'task_id': key, 'prompt_id': state['prompt_id'], 'status': 'registering', 'recorded_at': stamp,
              'items': inspected, 'updates': updates, 'checks': []}
    for path in checked:
        current = path.stat()
        report['checks'].append({'path': path.relative_to(root).as_posix(), 'stamp': [current.st_size, current.st_mtime_ns]})
    if up:
        formal = project_file(root, up['formal'])
        prior = formal.stat() if formal.exists() else None
        report['publication'] = {'source': inspected[0]['path'], 'formal': up['formal'], 'archive': up.get('archive'),
                                 'prior': [prior.st_size, prior.st_mtime_ns] if prior else None}
        confirmation = re.search(r'^#### 4\. 用户确认\s*\n(.*?)(?=^#### |\Z)', review, re.M | re.S)[0]
        report['approval'] = {'path': plan['draft'], 'heading': plan['review'], 'text': confirmation}
        inspected[0]['display_path'] = up['formal']
    write_json(report_file, report)
    return apply(store, key, report, report_file)


def apply(store, key, report, report_file):
    """Resume only exact unfinished edits; preserve feedback and stop on concurrent changes."""
    return apply_updates(Path(store.rows[key]['input'].project), report, report_file)


def apply_updates(root, report, report_file):
    """Apply shared image record/publication updates for remote and native providers."""
    edits = {}
    for update in report['updates']:
        path = project_file(root, update['path'])
        if path not in edits:
            text = path.read_text('utf-8-sig')
            edits[path] = text, text
        before, text = edits[path]
        if update['old'] == update['new']:
            continue
        if text.count(update['new']) == 1:
            continue
        if text.count(update['old']) == 1:
            text = text.replace(update['old'], update['new'], 1)
        else:
            raise ValueError('图片收尾源文字变化或不唯一：' + str(path))
        edits[path] = before, text
    progress = root / '项目进度.md'
    if progress in edits:
        phases = progress_phases(root, [item['draft'] for item in report['items']])
        project_progress.validate_update(*edits[progress], phases=phases)
    if report.get('approval'):
        approval = report['approval']
        path = project_file(root, approval['path'])
        for text in edits[path]:
            review = section(text, approval['heading'])[0]
            if approval['text'] not in review:
                raise ValueError('原图批准依据发生变化，不自动正式采用')
    publication = report.get('publication')
    if publication:
        source, formal = (project_file(root, publication[name]) for name in ('source', 'formal'))
        raw = source.read_bytes()
        old = formal.read_bytes() if formal.exists() else None
        if old != raw:
            current = formal.stat() if formal.exists() else None
            stamp = [current.st_size, current.st_mtime_ns] if current else None
            if stamp != publication['prior']:
                raise ValueError('正式文件在收尾期间发生变化，不覆盖')
            if old is not None:
                if not publication['archive']:
                    raise ValueError('正式文件已存在，缺少替换归档入口')
                archive = project_file(root, publication['archive'])
                archive.parent.mkdir(parents=True, exist_ok=True)
                if archive.exists():
                    if archive.read_bytes() != old:
                        raise ValueError('归档入口已存在不同内容，不覆盖')
                else:
                    with archive.open('xb') as stream:
                        stream.write(old)
            formal.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=formal.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(raw)
                current = formal.stat() if formal.exists() else None
                if ([current.st_size, current.st_mtime_ns] if current else None) != publication['prior']:
                    raise ValueError('正式文件并发变化，不覆盖')
                temporary.replace(formal)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    for path, (before, after) in edits.items():
        if before == after:
            continue
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(after)
            if path.read_text('utf-8-sig') != before:
                raise ValueError('图片收尾源资料并发变化，未覆盖：' + str(path))
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    report['status'] = 'registered'
    report['registered_at'] = datetime.now().astimezone().isoformat()
    write_json(report_file, report)
    return report


def verify_browser_entries(projects, name, images):
    """Verify native and downloaded images against their actual parsed review entries."""
    image_groups = {}
    for item in images:
        parts = Path(item['draft']).parts
        image_groups.setdefault((parts[0], parts[1] if parts[0] == '09-剧集制作' else None), []).append(item)
    for (scope, episode), members in image_groups.items():
        parsed = projects.section(name, scope, episode)
        found = set()
        def image_entries(value):
            if isinstance(value, dict):
                if value.get('key'):
                    found.add(unquote(value['key']))
                for child in value.values(): image_entries(child)
            elif isinstance(value, list):
                for child in value: image_entries(child)
        if scope in ('03-人物资料', '04-场景资料', '05-道具资料'):
            # A loose file in the directory is not a registered review/formal asset.
            for collection in ('people', 'scenes', 'props'):
                for asset in parsed.get(collection, []):
                    if any(asset.get('recordKey') == item['draft'] for item in members):
                        image_entries(asset.get('candidates', []))
                        image_entries(asset.get('formal', []))
                        image_entries(asset.get('auxiliary', []))
        else:
            image_entries(parsed)
        for item in members:
            if item.get('display_path', item['path']) not in found:
                raise ValueError('源资料已登记，网页缺少本批图片：' + item['path'])
