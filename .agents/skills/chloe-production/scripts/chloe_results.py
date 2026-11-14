"""Chloe video completion: exact outputs, whole-round review, technical adoption and handoff."""
from pathlib import Path
import json
import math
import sys

SKILLS=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(SKILLS/'chloe-assets/scripts'))
import chloe_result_records as records
import chloe_production as production
resources=records.resources


def validate(owner, plan, count):
    document,body,execution=records.validate(owner,plan,count)
    if document!=owner/'制作记录.md':
        raise ValueError('视频结果须写本视频制作记录')
    value=production.state(owner)
    current=value['rounds'][plan['round']]
    slots={v['slot'] for v in current['values'] if v['execution']==plan['execution']}
    if slots!={o['slot'] for o in plan['outputs']}:
        raise ValueError('结果槽位未完整绑定指定轮次与执行')
    stages={v['stage'] for v in current['values'] if v['execution']==plan['execution']}
    if len(stages)!=1:
        raise ValueError('同一执行不能混合制作阶段')
    stage=next(iter(stages))
    if stage=='后处理':
        review_doc,review=records.approval(owner,plan,body)
        if review_doc!=document:
            raise ValueError('视频批准须来自本视频制作记录')
        # Match each upstream output to the actual approved round, including partial reuse.
        approved=next((r for r in value['rounds'].values() if review['对象引用']==f"[第{r['number']}轮](<制作轮次.json#round-{r['number']}>)"),None)
        if approved is None:
            raise ValueError('后处理须关联准确的已批准轮次')
        for v in current['values']:
            if v['execution']==plan['execution'] and not any(
                    a['id']==v['id'] and a['execution']==execution['上游执行'] and a['ref']
                    and (not current['scene_source'] or a['duration']==v['duration']) for a in approved['values']):
                raise ValueError('后处理上游不在批准的轮次组合内')
        for output in plan['outputs']:
            expected=output['expected']
            if not isinstance(output['previous'],str):
                raise ValueError('后处理须记录提交时本用途采用值，空值为无')
            for key in ('width','height','frame_rate','duration'):
                if not isinstance(expected[key],(int,float)) or not math.isfinite(expected[key]) or expected[key]<=0:
                    raise ValueError('后处理目标须为有效正数：'+key)
            if type(expected['audio_tracks']) is not int or expected['audio_tracks']<0:
                raise ValueError('音轨数须为非负整数')
    elif plan.get('adopt'):
        raise ValueError('生成结果返回后仅登记待审，不自动采用')
    return document,body,execution,value,stage


def validate_task(data, plan, checked):
    from project_paths import input_file
    from backend.services.scene_postprocess import output_for_source

    stages = {'video-first-pass': '一采', 'video-second-pass': '二采',
              'video-scene-generation': '场次生成', 'video-postprocess': '后处理'}
    _, _, execution, value, stage = checked
    if stages.get(data.task_type) != stage:
        raise ValueError('任务类型与原分段阶段不一致')
    owner = value['project']
    if Path(data.record_dir).resolve() != owner / '执行记录' / plan['execution']:
        raise ValueError('任务目录与原执行不一致')
    round_row = value['rounds'][plan['round']]
    if stage == '场次生成':
        timeline = data.video_plan
        if ('gap_repair' in timeline or
                [(row['p'], row['planned_seconds']) for row in timeline['segments']]
                != [(item['id'], item['duration']) for item in round_row['values']]):
            raise ValueError('整场生成须匹配完整轮次及分段时长')
        if plan.get('automatic_round'):
            from songssx_workflow import PLANNER, shot_blocks

            request = json.loads(data.workflow[PLANNER]['inputs']['timeline_data'])
            prompts = production.prompt_sections(value, execution)
            for entry, row, gen in zip(round_row['values'], timeline['segments'],
                                       request['segmentConfig']['segments'], strict=True):
                identity = entry['id']
                if (len(shot_blocks(gen['prompt'])) != len(entry['shotIds'])
                        or prompts['模型提示词正文'][identity] != gen['prompt'].strip()
                        or prompts['中文提示词参考版'][identity] != row['prompt_zh'].strip()):
                    raise ValueError(identity + ' 的实际提示词与已登记轮次不一致')
    elif stage == '后处理':
        sources = [production.upstream_candidate(value['candidates'], item) for item in round_row['values']
                   if item['execution'] == execution['执行编号']]
        expected = {value['root'] / item['ref']['file'] for item in sources}
        if round_row['scene_source']:
            source, = expected
            output_for_source(owner, data.model_dump(), source)
            duration = production.video_version(value['root'], sources[0]['ref'])['facts']['duration_seconds']
            target = plan['outputs'][0]['expected']
            if abs(duration-target['duration']) > 1/target['frame_rate']+0.001:
                raise ValueError('整场后处理须保留原片时长及分段时间轴')
        elif not expected <= {input_file(owner, item['file']) for item in data.uploads}:
            raise ValueError('后处理任务须使用已批准的准确源片')


def technical(item, expected):
    actual=item['metadata']
    for key in ('width','height'):
        if actual[key]!=expected[key]:
            raise ValueError('后处理'+key+'与确认目标不符')
    if actual['frame_rate'] is None or abs(actual['frame_rate']-expected['frame_rate'])>0.001:
        raise ValueError('后处理帧率与确认目标不符')
    # Frame-grid rounding may change duration by at most one output frame.
    if actual['duration'] is None or abs(actual['duration']-expected['duration'])>1/expected['frame_rate']+0.001:
        raise ValueError('后处理时长变化超过一帧')
    if len(actual['audio'])!=expected['audio_tracks']:
        raise ValueError('后处理音轨数与确认目标不符')


def handoff(owner, value, round_row, body, time):
    selected=round_row['values']
    adopted={r['用途']:r['资源引用'] for r in records.rows(body,'当前采用')}
    if not all(adopted.get(v['id']+'/'+v['stage'])==records.resource(owner,owner/'README.md',str(value['root']/v['ref']['file'])) for v in selected):
        return body, None
    number=round_row['number']
    path=owner/'剪辑交接'/f'第{number}轮.jianying.json'
    spec={'name':owner.name+f'-第{number}轮','media':[{'file':str((value['root']/v['ref']['file']).relative_to(owner)),
        'member':('整片' if round_row['scene_source'] else v['id'])+'.mp4','timeline':True}
        for v in production.timeline_values(round_row)]}
    if path.exists() and json.loads(path.read_text('utf-8'))!=spec:
        raise ValueError('既有交接组合不同，不覆盖历史清单')
    if not path.exists():
        resources.write_json(path,spec)
    reference=records.link(owner/'README.md',path,f'第{number}轮剪映清单')
    existing=next((r for r in records.rows(body,'剪映交接') if r['清单文件']==reference),None)
    if existing is None:
        number=max([int(r['交接编号'][1:]) for r in records.rows(body,'剪映交接')]+[0])+1
        body=records.put(body,'剪映交接',['交接编号'],{'交接编号':f'J{number:03}','记录时间':time,
            '清单文件':reference,'交接状态':'可下载','依据':f"第{round_row['number']}轮当前采用组合"})
    return body,str(path)


def finish(owner, plan, report, report_path):
    owner=Path(owner).resolve()
    with resources.index_lock(owner):
        document,body,execution,value,stage=validate(owner,plan,len(report['items']))
        if stage=='后处理':
            for spec,item in zip(plan['outputs'],report['items'],strict=True):
                technical(item,spec['expected'])
        proof=records.report_link(document,report_path,'结果收尾报告')
        for spec,item in zip(plan['outputs'],report['items'],strict=True):
            body=records.put(body,'输出记录',['执行编号','输出槽位'],{'执行编号':plan['execution'],
                '输出槽位':spec['slot'],'资源引用':records.resource(owner,document,item['path'])})
        body=records.complete_execution(body,plan['execution'],report['task_id'],report.get('ended_at') or report['recorded_at'],proof,report.get('started_at'))
        records.save(document,body)
        value=production.state(owner)
        round_row=value['rounds'][plan['round']]
        latest=plan['round']==max(value['rounds'])
        readme=owner/'README.md'; progress=readme.read_text('utf-8')
        adopted=False; manifest=None
        time=records.now()
        if stage=='后处理' and latest:
            results = {spec['slot']: (spec, item) for spec, item in zip(plan['outputs'],report['items'],strict=True)}
            for v in round_row['values']:
                if v['execution'] == plan['execution']:
                    spec,item = results[v['slot']]
                    progress=records.adopt(progress,v['id']+'/'+v['stage'],records.resource(owner,readme,item['path']),
                        records.link(readme,document,plan['adopt']['review'])+'；'+records.report_link(readme,report_path,'技术核对'),time,expected=spec['previous'])
            adopted=True
        ready=all(v['ref'] and v['record']['执行状态']=='已完成' for v in round_row['values'])
        next_action='等待本轮其余分段' if not ready else '整片审阅'
        phase=next(r['内容'] for r in records.rows(progress,'定位与当前进度') if r['字段']=='当前阶段')
        if latest and ready and phase not in ('发布阶段','复盘阶段'):
            if stage=='后处理':
                progress,manifest=handoff(owner,value,round_row,progress,time)
                next_action='剪映人工后期' if manifest else '确认本轮其余分段采用'
            else:
                next_action = (f"审阅第{plan['round']}轮整场视频" if stage == production.SCENE_STAGE
                               else f"审阅第{plan['round']}轮整片{stage}")
            for key,val in {'处理状态':'正常' if manifest else '待用户决定','当前问题':'无' if manifest else next_action,
                            '下一步':next_action,'当前阶段':'人工后期' if manifest else '视频制作'}.items():
                before=next(r['内容'] for r in records.rows(progress,'定位与当前进度') if r['字段']==key)
                if before!=val and key in ('处理状态','当前阶段','视频状态'):
                    changes=records.rows(progress,'阶段变更')
                    number=max([int(r['记录编号'][1:]) for r in changes]+[0])+1
                    progress=records.put(progress,'阶段变更',['记录编号'],{'记录编号':f'B{number:03}',
                        '记录时间':time,'变更范围':key,'原值或原版本':before,'新值或新版本':val,
                        '依据':records.report_link(readme,report_path,'本轮结果核对')})
                progress=records.put(progress,'定位与当前进度',['字段'],{'字段':key,'内容':val},replace=True)
        records.save(readme,progress)
        for path in (document,readme):
            checked=records.docs.check_workspace(value['root'],only=path)
            if checked['errors']:
                raise ValueError(str(checked['errors']))
        production.check(owner)
        return {'status':'updated','execution':plan['execution'],'round':plan['round'],'stage':stage,
                'round_ready':ready,'historical':not latest,'adopted':adopted,'handoff':manifest,
                'paths':[str(document),str(readme)],'next_action':next_action if latest else '历史轮次已登记'}
