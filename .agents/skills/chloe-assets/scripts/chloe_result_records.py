"""Chloe result rows; update existing documents without copying media or inventing review."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS/'studio-workspace-browser/scripts'))
sys.path.insert(0, str(SKILLS/'chloe-positioning/scripts'))
sys.path.insert(0, str(SKILLS/'studio-comfyui/scripts'))
import project_resources as resources
import chloe_documents as docs
import execution_records as recordio


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def link(document, path, label):
    return f'[{label}](<{os.path.relpath(path, document.parent)}>)'


def report_link(document, report_path, label):
    return link(document,recordio.backing_file(report_path),label)


def table(text, heading):
    section = re.search(r'^## '+re.escape(heading)+r'\s*\n(.*?)(?=^## |\Z)', text, re.M|re.S)
    if not section:
        raise ValueError('缺少固定章节：'+heading)
    match = re.search(r'^\|.*\n\|[ :|\-]+\|\n(?:\|.*\n)*', section[1], re.M)
    if not match:
        raise ValueError('缺少固定表格：'+heading)
    lines = match[0].splitlines()
    cells = lambda line: [x.strip() for x in line.strip().strip('|').split('|')]
    columns = cells(lines[0])
    rows = [dict(zip(columns, cells(line), strict=True)) for line in lines[2:]]
    return section.start(1)+match.start(), section.start(1)+match.end(), columns, rows


def rows(text, heading):
    return table(text, heading)[3]


def put(text, heading, key, values, *, replace=False):
    start, end, columns, entries = table(text, heading)
    found = [r for r in entries if all(r[k] == values[k] for k in key)]
    if len(found)>1:
        raise ValueError('重复行身份：'+heading)
    if found:
        if not replace and any(found[0][k] != str(v) for k,v in values.items()):
            raise ValueError('原记录与返回结果不一致：'+heading)
        found[0].update({k:str(v) for k,v in values.items()})
    else:
        if set(values)!=set(columns):
            raise ValueError('新增行须填写固定字段：'+heading)
        entries.append({k:str(v) for k,v in values.items()})
    if any('\n' in v or '|' in v for r in entries for v in r.values()):
        raise ValueError('表格字段不能包含换行或竖线')
    rendered = '\n'.join('| '+' | '.join(r)+' |' for r in [columns,['---']*len(columns), *[[r[c] for c in columns] for r in entries]])+'\n'
    return text[:start]+rendered+text[end:]


def save(path, text):
    if path.read_text('utf-8') == text:
        return
    temp = path.with_name(path.name+'.result-tmp')
    temp.write_text(text, encoding='utf-8')
    temp.replace(path)


def resource(owner, document, filename):
    ref = resources.reference(owner, filename)
    if ref is None or not resources.local(owner, ref['file']).is_file():
        raise ValueError('结果必须已保存为本归属中的准确资源版本')
    prefix = '共用' if owner.name == '综合资料' else '本视频'
    return link(document, resources.local(owner, ref['file']), f"{prefix}:{ref['resource_id']}@{ref['version']}")


def validate(owner, plan, count):
    document = resources.local(owner, plan['document'])
    body = document.read_text('utf-8')
    execution = [r for r in rows(body,'执行记录') if r['执行编号']==plan['execution']]
    if len(execution)!=1:
        raise ValueError('须先建立唯一执行行')
    if len(plan['outputs'])!=count or len({r['slot'] for r in plan['outputs']})!=count:
        raise ValueError('业务输出槽位须与技术输出逐项对应且不重复')
    if plan['adapter']=='chloe-image':
        if execution[0]['执行类型'] not in ('图片生成','图片处理'):
            raise ValueError('图片收尾只能关联图片执行')
        for item in plan['outputs']:
            if not item['purpose']:
                raise ValueError('图片必须明确用途')
            if item.get('source'):
                resource(owner,document,item['source'])
        if plan.get('adopt'):
            approval(owner, plan, body)
    return document, body, execution[0]


def approval(owner, plan, body):
    decision = plan['adopt']
    review_doc = resources.local(owner,decision['document'])
    reviews = rows(review_doc.read_text('utf-8'),'审阅记录')
    match = next((r for r in reviews if r['审阅编号']==decision['review']),None)
    if not match or match['审阅结论']!='通过':
        raise ValueError('自动采用须引用已通过的原审阅')
    return review_doc, match


def adopt(body, purpose, reference, basis, time, *, expected=None):
    old = next((r['资源引用'] for r in rows(body,'当前采用') if r['用途']==purpose),'无')
    if old == reference:
        return body
    if expected is not None and old!=expected:
        raise ValueError('当前采用已改变，不覆盖后续决定')
    events=rows(body,'采用变更')
    number=max([int(r['记录编号'][1:]) for r in events]+[0])+1
    body=put(body,'采用变更',['记录编号'],dict(zip(
        ['记录编号','记录时间','变更范围','原值或原版本','新值或新版本','依据'],
        [f'B{number:03}',time,purpose,old,reference,basis])))
    return put(body,'当前采用',['用途'],{'用途':purpose,'资源引用':reference,'采用依据':basis,'采用时间':time},replace=True)


def complete_execution(body, execution, task_id, time, proof, started_at=None):
    row=next(r for r in rows(body,'执行记录') if r['执行编号']==execution)
    if row['任务ID'] not in docs.MISSING and row['任务ID'].split('；')[0]!=task_id:
        raise ValueError('返回任务与原执行的任务ID不同')
    return put(body,'执行记录',['执行编号'],{'执行编号':execution,'任务ID':row['任务ID'] if row['任务ID'] not in docs.MISSING else task_id,
        '开始时间':started_at or row['开始时间'],
        '结束时间':time,'执行状态':'已完成','结果说明':proof if row['结果说明'] in docs.MISSING else row['结果说明'] if proof in row['结果说明'] else row['结果说明']+'；'+proof},replace=True)


def finish(owner, plan, report, report_path):
    owner=Path(owner).resolve()
    with resources.index_lock(owner):
        document, body, execution = validate(owner,plan,len(report['items']))
        time=now()
        proof=report_link(document,report_path,'结果收尾报告')
        adopt_doc = resources.local(owner, plan.get('adoption_document',plan['document']))
        adopted_body=body if adopt_doc==document else adopt_doc.read_text('utf-8')
        for spec,item in zip(plan['outputs'],report['items'],strict=True):
            reference=resource(owner,document,item['path'])
            body=put(body,'输出记录',['执行编号','输出槽位'],{'执行编号':plan['execution'],'输出槽位':spec['slot'],'资源引用':reference})
            # Video image records intentionally have no reference-version table.
            if re.search(r'^## 参考版本\s*$',body,re.M):
                body=put(body,'参考版本',['用途','资源引用'],{'用途':spec['purpose'],'资源引用':reference,
                    '来源或原图引用':resource(owner,document,spec['source']) if spec.get('source') else '无','执行编号':plan['execution']})
            if plan.get('adopt'):
                review_doc, review=approval(owner,plan,body)
                if execution['执行类型']!='图片处理' or not spec.get('source'):
                    raise ValueError('自动采用仅用于已批准原图的技术处理')
                source=resource(owner,review_doc,spec['source'])
                if review['对象引用']!=source:
                    raise ValueError('批准对象必须是本次处理的准确来源版本')
                inputs=rows(body,'输入记录')
                if not any(r['执行编号']==plan['execution'] and r['资源引用']==resource(owner,document,spec['source']) for r in inputs):
                    raise ValueError('处理来源未登记在原输入记录')
                if adopt_doc==document:
                    adopted_body=body
                adopted_body=adopt(adopted_body,spec['purpose'],resource(owner,adopt_doc,item['path']),
                    link(adopt_doc,review_doc,plan['adopt']['review'])+'；'+report_link(adopt_doc,report_path,'尺寸核对'),time,
                    expected=spec['previous'])
                if adopt_doc==document:
                    body=adopted_body
        body=complete_execution(body,plan['execution'],report['task_id'],report.get('ended_at') or report['recorded_at'],proof,report.get('started_at'))
        save(document,body)
        if adopt_doc!=document and plan.get('adopt'):
            save(adopt_doc,adopted_body)
        # Fixed-document validation is scoped to the documents written in this operation.
        root=owner.parent if owner.name=='综合资料' else owner.parent.parent
        for path in {document,adopt_doc} if plan.get('adopt') else {document}:
            result=docs.check_workspace(root,only=path)
            if result['errors']:
                raise ValueError(str(result['errors']))
        return {'status':'updated','execution':plan['execution'],'adopted':bool(plan.get('adopt')),
                'paths':[str(document)],'next_action':'完成' if plan.get('adopt') else '用户审阅图片'}


def native(project, manifest, source):
    """The manifest is the existing generation parameter record, not a second ledger."""
    from chloe_resources import import_media
    spec=json.loads(manifest.read_text('utf-8'))
    plan=spec['business_result']
    video=spec.get('video_project')
    owner=project/'projects'/video if video else project/'综合资料'
    if plan.get('adopt'):
        raise ValueError('原生生图只登记候选；用户审阅后单独处理')
    validate(owner,plan,1)
    if len(plan['outputs'])!=1:
        raise ValueError('一次原生结果对应一个明确输出槽位')
    result=import_media(project,source,plan['execution']+'/'+plan['document']+'/'+plan['outputs'][0]['slot'],
        project=video,resource_id=spec.get('resource_id'),origin='generated',
        record=str(manifest.relative_to(owner)),parent=plan['outputs'][0].get('source'))
    facts=json.loads((Path(result['absolute_file']).parent/'版本信息.json').read_text('utf-8'))['facts']
    report=spec.get('actual_result') or {'task_id':spec['task_id'],'recorded_at':now(),
        'items':[{'path':result['file'],**facts}]}
    if report['items'][0]['path']!=result['file']:
        raise ValueError('原生结果与已有登记不同')
    spec['actual_result']=report
    resources.write_json(manifest,spec)
    result=finish(owner,plan,report,manifest)
    return {**result,'images':[{'file':str(resources.local(owner,report['items'][0]['path'])),'width':facts['width'],'height':facts['height']}]}


def register_available(project, file, basis):
    root = docs.project_path(project)
    path = (root / file).resolve()
    if not basis.strip() or basis.strip() in docs.MISSING:
        raise ValueError('须提供用户明确批准该资产登记为可用的依据')
    with resources.index_lock(root/'综合资料'):
        entry = next((e for e in docs.documents(root) if e[0] == path and e[0].name in docs.REQUIRED_ASSET_IMAGES), None)
        if entry is None:
            raise ValueError('不是已登记的Chloe共用图片资产说明')
        body = path.read_text('utf-8')
        state = docs.asset_status(path, docs.read_document(root, *entry, body=body))
        if state['missing_images']:
            raise ValueError('资产登记为可用前须采用：'+'、'.join(state['missing_images']))
        if state['status'] == '可用':
            return state
        number = max((int(r['记录编号'][1:]) for r in rows(body, '采用变更')), default=0)+1
        body = put(body, '采用变更', ['记录编号'], {
            '记录编号': f'B{number:03}', '记录时间': now(), '变更范围': '资产状态',
            '原值或原版本': '制作中', '新值或新版本': '可用', '依据': basis.strip(),
        })
        body = put(body, '资产身份', ['字段'], {'字段': '资产状态', '内容': '可用'}, replace=True)
        updated = docs.asset_status(path, docs.read_document(root, *entry, body=body))
        save(path, body)
        return updated


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='action',required=True)
    native_cmd=commands.add_parser('native',help='原生图片候选：导入一次并登记，不采用、不删除工具原图')
    native_cmd.add_argument('--project-root',required=True,type=Path,help='Chloe具名项目根目录')
    native_cmd.add_argument('--manifest',required=True,type=Path,help='现有生图参数JSON，含business_result、task_id')
    native_cmd.add_argument('--source',required=True,type=Path,help='工具实际返回图片的绝对路径')
    resume=commands.add_parser('finish',help='从已有技术报告恢复业务登记，不取回或重新检测媒体')
    resume.add_argument('--owner',required=True,type=Path,help='任务实际资源归属：综合资料或单条视频绝对目录')
    resume.add_argument('--manifest',required=True,type=Path,help='原任务清单JSON；business_result位于所选任务的image_plan或video_plan')
    resume.add_argument('--task-index',required=True,type=int,help='任务清单tasks中的零基序号')
    resume.add_argument('--report',required=True,type=Path,help='该任务已有的结果收尾报告，兼容执行档案内紧凑记录')
    available=commands.add_parser('register-available',help='用户明确批准后，将一项图片资产登记为可用')
    available.add_argument('--project-root',required=True,type=Path)
    available.add_argument('--file',required=True,type=Path,help='固定资产说明路径，相对项目根目录或绝对路径')
    available.add_argument('--basis',required=True,help='用户明确批准该对象登记为可用的实际依据')
    args=parser.parse_args()
    if args.action=='native':
        result=native(args.project_root.resolve(),args.manifest.resolve(),args.source.resolve())
    elif args.action=='register-available':
        result=register_available(args.project_root,args.file,args.basis)
    else:
        import execution_records as recordio
        task=json.loads(args.manifest.read_text('utf-8'))['tasks'][args.task_index]
        plan=(task.get('image_plan') or task['video_plan'])['business_result']
        record_dir=resources.local(args.owner.resolve(),task['record_dir'])
        if args.report.resolve().parent!=record_dir:
            raise ValueError('报告目录与原任务执行目录不同')
        report=recordio.read(args.report)
        if report.get('status')!='registered':
            raise ValueError('须使用已经完成技术核对的原报告')
        if plan['adapter']=='chloe-video':
            sys.path.insert(0,str(SKILLS/'chloe-production/scripts'))
            from chloe_results import finish as complete
        elif plan['adapter']=='chloe-image':
            complete=finish
        else:
            raise ValueError('未登记的Chloe结果适配')
        result=complete(args.owner.resolve(),plan,report,args.report.resolve())
    print(json.dumps(result,ensure_ascii=True,indent=2))

if __name__=='__main__':
    main()
