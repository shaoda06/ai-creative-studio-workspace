"""Chloe production records: references only; never submit, copy media or infer approval."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import math
import sys

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS/'chloe-positioning/scripts'))
from chloe_documents import records, media_reference, MISSING, read_document, template, check_manifest
from chloe_init import resources

STAGES = ('一采', '二采', '后处理')


def local(project, value):
    return resources.local(project, value)


def link_path(project, value):
    match = re.fullmatch(r'\[[^\]]+\]\(<([^>]+)>\)', value)
    return local(project, match[1] if match else value)


def document(project, name):
    filename=Path(name).name
    kind='视频README模板.md' if filename=='README.md' else '制作记录模板.md' if filename=='制作记录.md' else '脚本模板.md'
    identity,title=project.name.split('-',1)
    return read_document(project.parent.parent,project/name,template('chloe-creative',kind),{'identity':identity,'title':title})


def fields(doc, heading):
    return {row['字段']: row['内容'] for row in records(doc, heading)}


def plan(project, source='脚本.md'):
    doc = document(project, source)
    result = {}
    body=(project/source).read_text('utf-8-sig')
    available=set(re.findall(r'^#{3,4} (SH\d{3,})(?:｜|\s)',body,re.M))
    for row in records(doc, '分段计划'):
        identity = row['分段编号']
        if not re.fullmatch(r'P\d{3,}', identity) or identity in result:
            raise ValueError('分段编号无效或重复：'+identity)
        shots = row['镜头编号'].split('、')
        if any(not re.fullmatch(r'SH\d{3,}', shot) for shot in shots) or len(shots) != len(set(shots)):
            raise ValueError('镜头编号须用顿号分隔且不重复')
        if not set(shots)<=available:
            raise ValueError('分段计划引用了不存在的镜头')
        duration = float(row['时长秒'])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('分段时长必须大于零')
        result[identity] = {'id': identity, 'duration': duration, 'shotIds': shots}
    return doc, result


def director_slot(value):
    if not value.startswith('导演表/'):
        return None
    match = re.fullmatch(r'导演表/脚本(v\d+)/图表(v\d+)/候选([1-9]\d*)/第([1-9]\d*)页', value)
    if match:
        return {'sourceVersion':match[1], 'version':match[2], 'candidateNumber':int(match[3]), 'page':int(match[4])}
    legacy = re.fullmatch(r'导演表/(v\d+)/第([1-9]\d*)页', value)
    if legacy:
        return {'sourceVersion':'', 'version':legacy[1], 'page':int(legacy[2])}
    raise ValueError('导演表输出槽位须明确脚本版本、图表版本、候选编号和页码')


def state(project):
    project = Path(project).resolve()
    root = project.parent.parent
    script, planned = plan(project)
    doc = document(project, '制作记录.md')
    executions = {row['执行编号']: row for row in records(doc, '执行记录')}
    outputs = {(row['执行编号'], row['输出槽位']): row for row in records(doc, '输出记录')}
    director_versions = {}; director_pages = set()
    for row in records(doc, '输出记录'):
        sheet = director_slot(row['输出槽位'])
        if sheet is None:
            continue
        reference = media_reference(root, project/'制作记录.md', row['资源引用'])
        if row['执行编号'] not in executions or reference['owner'] != project.relative_to(root).as_posix() or not reference['resource_id'].startswith('IMG-'):
            raise ValueError('导演表须关联原执行及本视频准确图片版本')
        version = sheet['version']; page = (version, sheet['page'])
        origin = (sheet['sourceVersion'], sheet.get('candidateNumber'))
        if version in director_versions and director_versions[version] != origin:
            raise ValueError('同一图表版本不能混用来源脚本版本或候选编号')
        if page in director_pages:
            raise ValueError('同一图表版本的页码重复')
        director_versions[version] = origin; director_pages.add(page)
    candidates = {}
    for row in records(doc, '视频分段执行'):
        identity, stage, run, execution, slot = (row[key] for key in ('分段编号','制作阶段','候选版本','执行编号','输出槽位'))
        if not re.fullmatch(r'P\d{3,}', identity) or stage not in STAGES or not re.fullmatch(r'R\d{3,}', run):
            raise ValueError('视频分段执行的分段、阶段或候选版本无效')
        key = (identity, execution, slot)
        if key in candidates or any((identity, stage, run) == (v['id'],v['stage'],v['run']) for v in candidates.values()):
            raise ValueError('视频分段执行重复')
        if execution not in executions or int(row['模型分段序号']) < 0:
            raise ValueError('视频分段执行缺少原执行或模型分段序号无效')
        output = outputs.get((execution, slot))
        ref = media_reference(root, project/'制作记录.md', output['资源引用']) if output else None
        if ref and (ref['owner'] != project.relative_to(root).as_posix() or not ref['resource_id'].startswith('VID-')):
            raise ValueError('视频产出须引用本视频资源区准确视频版本')
        candidates[key] = {'id':identity,'stage':stage,'run':run,'execution':execution,'slot':slot,
                           'index':int(row['模型分段序号']),'ref':ref,'record':executions[execution]}
    spec = json.loads((project/'制作轮次.json').read_text('utf-8'))
    if set(spec) != {'format','rounds'} or spec['format'] != 1:
        raise ValueError('制作轮次必须使用 format 1 和 rounds')
    rounds = {}; seen = set()
    for item in spec['rounds']:
        required = {'number','created_at','note','script','segments'}
        if not required <= item.keys() or set(item)-required-{'base_round','changed_segments','review_outputs'}:
            raise ValueError('制作轮次字段不符合规范')
        number = item['number']
        if type(number) is not int or number != len(rounds)+1:
            raise ValueError('整片轮次从1起连续递增且不可重复')
        if datetime.fromisoformat(item['created_at']).tzinfo is None:
            raise ValueError('轮次时间须包含时区')
        source = local(project, item['script'])
        if source.parent != project/'历史版本' or not source.is_file():
            raise ValueError('轮次脚本须引用历史版本中的准确稿件')
        _, row_plan = plan(project, item['script'])
        ids = []; values = []
        for segment in item['segments']:
            if set(segment) != {'id','execution','slot'}:
                raise ValueError('轮次分段仅保存 id、execution、slot 引用')
            key = (segment['id'], segment['execution'], segment['slot'])
            if key not in candidates:
                raise ValueError('轮次引用不存在的分段执行：'+str(key))
            ids.append(segment['id']); values.append({**candidates[key], **row_plan[segment['id']], 'carried':key in seen})
        if not ids or ids != list(row_plan):
            raise ValueError('轮次必须按脚本计划保存完整且唯一的分段顺序')
        base = item.get('base_round')
        if base is not None:
            if base not in rounds:
                raise ValueError('来源轮次不存在')
            previous = {v['id']:(v['execution'],v['slot']) for v in rounds[base]['values']}
            changed = {v['id'] for v in values if previous.get(v['id']) != (v['execution'],v['slot'])} | (previous.keys()-set(ids))
            if set(item.get('changed_segments', [])) != changed:
                raise ValueError('changed_segments 必须对应实际变化的分段')
        elif 'changed_segments' in item:
            raise ValueError('changed_segments 必须有 base_round')
        for output in item.get('review_outputs', []):
            if set(output) != {'label','resource'}:
                raise ValueError('审阅附加输出须为 label 和准确 resource 引用')
            media_reference(root, project/'制作记录.md', output['resource'])
        seen.update((v['id'],v['execution'],v['slot']) for v in values)
        rounds[number] = {**item, 'values':values}
    for value in candidates.values():
        execution=value['record']
        if execution['执行状态']=='已完成' and not value['ref']:
            raise ValueError('已完成的视频分段缺少准确输出引用')
        if value['stage'] in ('二采','后处理'):
            source=next((v for v in candidates.values() if v['execution']==execution['上游执行'] and v['id']==value['id']),None)
            expected='一采' if value['stage']=='二采' else '二采'
            if not source or source['stage']!=expected:
                raise ValueError(value['stage']+'须关联同一分段的'+expected+'执行')
    for row in records(document(project,'README.md'),'当前采用'):
        match=re.fullmatch(r'(P\d{3,})/(一采|二采|后处理)',row['用途'])
        if match:
            reference=media_reference(root,project/'README.md',row['资源引用'])
            if not any(v['id']==match[1] and v['stage']==match[2] and v['ref']==reference for v in candidates.values()):
                raise ValueError('当前采用未对应同一分段和阶段的真实输出')
    notes = json.loads((project/'视频修改意见.json').read_text('utf-8'))
    if set(notes) != {'notes','rounds'}:
        raise ValueError('视频修改意见须使用公共 notes、rounds 结构')
    return {'project':project,'root':root,'script':script,'plan':planned,'doc':doc,
            'executions':executions,'candidates':candidates,'rounds':rounds}


def prompt_sections(value, row):
    """Read both languages by P identity from the single execution prompt file."""
    execution=row['执行编号']
    prompt=row['提示词或正文']
    if not re.fullmatch(r'\[[^\]]+\]\(<[^>]+>\)', prompt):
        raise ValueError(execution+' 视频生成提示词须使用Markdown文件链接，不直接填写正文')
    path=link_path(value['project'],prompt)
    if path.suffix!='.md' or not path.is_file():
        raise ValueError(execution+' 提示词须引用存在的Markdown文件')
    text=path.read_text('utf-8-sig')
    segments=sorted((v for v in value['candidates'].values() if v['execution']==execution),key=lambda v:v['index'])
    ids=[v['id'] for v in segments]
    result={}
    for heading in ('模型提示词正文','中文提示词参考版'):
        sections=re.findall(r'^## '+heading+r'[^\S\n]*\n(.*?)(?=^## |\Z)',text,re.M|re.S)
        if len(sections)!=1 or not sections[0].strip() or '{{' in sections[0]:
            raise ValueError(execution+' 提示词缺少唯一且已填写的章节：'+heading)
        body=sections[0].strip()
        blocks=list(re.finditer(r'^### (共用|P\d{3,})[^\S\n]*\n',body,re.M))
        if not blocks and len(ids)<=1:
            result[heading]={identity:body for identity in ids}
            continue
        names=[m[1] for m in blocks]
        if names not in (ids,['共用',*ids]) or body[:blocks[0].start()].strip():
            raise ValueError(execution+' '+heading+' 分段标题须按模型分段序号对应：'+','.join(ids))
        parts={m[1]:body[m.end():blocks[i+1].start() if i+1<len(blocks) else len(body)].strip() for i,m in enumerate(blocks)}
        if any(not part for part in parts.values()):
            raise ValueError(execution+' '+heading+' 分段正文不能为空')
        result[heading]={identity:'\n\n'.join(p for p in (parts.get('共用',''),parts[identity]) if p) for identity in ids}
    return result


def check_handoffs(value):
    project, root = value['project'], value['root']
    readme = document(project, 'README.md')
    manifests = list((project/'剪辑交接').glob('*.jianying.json'))
    if not manifests and not records(readme, '剪映交接'):
        return
    handoffs = {}
    for row in records(readme, '剪映交接'):
        if row['清单文件'] in MISSING and row['交接状态'] == '待核对':
            continue
        path = link_path(project, row['清单文件'])
        if path.parent != project/'剪辑交接' or not path.name.endswith('.jianying.json') or not path.is_file():
            raise ValueError('剪映交接须引用剪辑交接目录内的实际清单')
        if path in handoffs:
            raise ValueError('同一剪映清单不能重复登记交接')
        if row['记录时间'] in MISSING or row['依据'] in MISSING:
            raise ValueError('剪映交接须填写交接时间与采用依据')
        handoffs[path] = row
    # Existing adoption events preserve the exact choices at each handoff time.
    adoptions = {}
    for row in records(readme, '采用变更'):
        purpose = row['变更范围']
        if re.fullmatch(r'P\d{3,}/(一采|二采|后处理)', purpose):
            if row['记录时间'] in MISSING or row['依据'] in MISSING:
                raise ValueError('片段采用变更须填写时间和依据')
            ref = None if row['新值或新版本'] in MISSING else media_reference(root, project/'README.md', row['新值或新版本'])
            adoptions.setdefault(purpose, []).append((datetime.fromisoformat(row['记录时间']), ref))
    for row in records(readme, '当前采用'):
        if re.fullmatch(r'P\d{3,}/(一采|二采|后处理)', row['用途']):
            ref = media_reference(root, project/'README.md', row['资源引用'])
            adoptions.setdefault(row['用途'], []).append((datetime.fromisoformat(row['采用时间']), ref))
    for path in manifests:
        check_manifest(project, path)
        if path not in handoffs:
            raise ValueError('剪映清单缺少README交接记录：'+path.name)
        when = datetime.fromisoformat(handoffs[path]['记录时间'])
        media = json.loads(path.read_text('utf-8'))['media']
        timeline = [local(project, item['file']) for item in media if item['timeline']]
        matching = [row for row in value['rounds'].values()
                    if all(v['ref'] for v in row['values']) and
                    [root/v['ref']['file'] for v in row['values']] == timeline and
                    datetime.fromisoformat(row['created_at']) <= when]
        if not matching:
            raise ValueError('剪映时间线须按交接轮次完整匹配片段版本与顺序，不得遗漏、重复或乱序')
        for round_row in matching:
            for segment in round_row['values']:
                events = [(date, ref) for date, ref in adoptions.get(segment['id']+'/'+segment['stage'], []) if date <= when]
                if not events or sorted(events, key=lambda event: event[0])[-1][1] != segment['ref']:
                    break
            else:
                break
        else:
            raise ValueError('剪映时间线含交接时尚未采用或已取消采用的片段版本')


def check(project):
    value = state(project)
    check_handoffs(value)
    for execution, row in value['executions'].items():
        if row['执行类型'] != '视频生成':
            continue
        prompt = row['提示词或正文']
        if prompt in MISSING:
            if row['执行状态'] in ('已提交', '执行中', '已完成') or row['任务ID'] not in MISSING:
                raise ValueError(execution+' 视频生成缺少中英文提示词文件')
            continue
        prompt_sections(value,row)
    sys.path.insert(0,str(SKILLS.parent.parent/'工作区浏览服务'))
    from backend.services.review_notes import ProjectReviewNotes
    notes=ProjectReviewNotes().read(value['project']/'视频修改意见.json')
    identities={(v['id'],v['stage'],v['run']) for v in value['candidates'].values()}
    rounds={n:{(v['id'],v['stage'],v['run']) for v in row['values']} for n,row in value['rounds'].items()}
    if any(note.number not in rounds for note in notes.rounds.values()) or any(
            (note.segment,note.stage,note.run) not in identities or note.roundNumber is not None and
            (note.segment,note.stage,note.run) not in rounds.get(note.roundNumber,set()) for note in notes.notes.values()):
        raise ValueError('修改意见引用了不存在的候选或轮次')
    return {'project':str(value['project']),'rounds':len(value['rounds']),'candidates':len(value['candidates'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check'])
    parser.add_argument('--project', required=True, type=Path, help='单条 V 视频项目的绝对目录；只读校验，不生成或写入资料')
    args=parser.parse_args()
    print(json.dumps(check(args.project), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
