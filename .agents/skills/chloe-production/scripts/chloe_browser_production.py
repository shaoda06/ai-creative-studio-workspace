"""Chloe's reference projection into the complete public ProductionWorkbench."""
import json
from math import isclose
from pathlib import Path
import re
from urllib.parse import quote

from chloe_production import state, local, link_path, fields, document, plan, director_slot, STAGES, prompt_sections, check_handoffs
from chloe_documents import records, media_reference, MISSING
from backend.parsers import documents
from backend.services.workspaces import jianying_links
import execution_records as recordio
from project_paths import input_file, input_key
from director_export import submitted_media
from h3_browser_context import request_context, empty_context
from prepared_documents import read_journal


def review_page(space, project):
    page = '/#/spaces/' + quote(space.id, safe='')
    context = space.context
    if '::' in project:
        context, project = project.split('::', 1)
    if context:
        page += '/contexts/' + quote(context, safe='')
    if project == '@shared':
        return page + '?section=assets'
    return page + '?section=production&video=' + quote(project, safe='')


def check_work(project, work):
    if work is not None and work != project.name.split('-',1)[0]:
        raise FileNotFoundError('视频编号不属于本项目')


def production_section(project, work=None):
    check_work(project,work)
    return '.'


def notes_path(project, work=None):
    check_work(project, work)
    return project/'视频修改意见.json'


def file_url(api, key):
    return api+'/files/'+quote(key, safe='/')


def ref(project, api, path):
    key=path.relative_to(project).as_posix()
    return {'kind':'json' if path.suffix=='.json' else 'markdown' if path.suffix=='.md' else 'file','name':path.name,'key':key,'url':file_url(api,key)}


def resource_file(data, api, reference):
    path=data['root']/reference['file']
    if path.is_relative_to(data['project']):
        return file_url(api,path.relative_to(data['project']).as_posix())
    return api.split('/projects/')[0]+'/production-files/'+quote(reference['file'],safe='/')


def task_for(project, row):
    if row['参数记录'] in MISSING:
        return None
    path=link_path(project,row['参数记录'])
    journal=path.with_name(path.stem+'-装配结果.json')
    manifest=read_journal(journal) if journal.is_file() else json.loads(path.read_text('utf-8-sig'))
    record=local(project,'执行记录/'+row['执行编号'])
    matches=[task for task in manifest['tasks'] if local(project,task['record_dir'])==record]
    if len(matches) != 1:
        raise ValueError(row['执行编号']+' 参数清单须按执行目录对应唯一任务')
    task=matches[0]
    return task,record


def read_record(path):
    return recordio.read(path) if recordio.exists(path) else {}


def context_for(data, api, candidate, active=None, bindings=None):
    active=set() if active is None else active
    bindings={} if bindings is None else bindings
    execution=candidate['execution']
    if execution in active:
        raise ValueError('上游执行循环引用')
    active.add(execution)
    row=candidate['record']; task_record=task_for(data['project'],row)
    if candidate['stage'] in ('二采','后处理') and row['上游执行'] not in MISSING:
        source=next((v for v in data['candidates'].values() if v['execution']==row['上游执行'] and v['id']==candidate['id']),None)
        if source:
            # The shared projection collects bindings by actual remote filename,
            # including the original upload's source stamp. No new upload is implied.
            upstream=context_for(data,api,source,active,bindings)
            if candidate['stage']=='后处理':
                return upstream
    if not task_record:
        return empty_context('尚未登记实际任务参数。')
    task,record=task_record
    request=read_record(record/task.get('request_name','请求.json'))
    task_state=read_record(record/'后台任务状态.json')
    if not request or not task_state.get('prompt_id'):
        return empty_context('尚未取得实际提交请求及凭据；不以准备稿替代。')
    root=data['root']
    def key(_, value, original):
        path=input_file(data['project'],value,recorded=True)
        if not path.is_relative_to(data['project']) and not path.is_relative_to(root/'综合资料/资源'):
            raise ValueError('实际输入越出本视频与共用资源区')
        return path.relative_to(root).as_posix()
    workspace_api=api.split('/projects/')[0]
    result=request_context(root,task,candidate['index'],request,workspace_api,
        read_record(record/'执行检查报告.json').get('sources',{}),bindings,resolve_key=key,
        file_link=lambda _, path:workspace_api+'/production-files/'+quote(path,safe='/'))
    result['prompts']['englishUrl']=file_url(api,(record/task.get('request_name','请求.json')).relative_to(data['project']).as_posix())
    if row['提示词或正文'] not in MISSING:
        prompt=link_path(data['project'],row['提示词或正文'])
        sections=prompt_sections(data,row)
        result['prompts'].update(chinese=sections['中文提示词参考版'][candidate['id']],
                                chineseUrl=file_url(api,prompt.relative_to(data['project']).as_posix()))
    return result


def video(data,api,value):
    reference=value['ref']; project=data['project']
    path=data['root']/reference['file'] if reference else None
    key=path.relative_to(project).as_posix() if path else 'pending/'+value['execution']+'/'+value['slot']
    info=path.stat() if path else None
    adopted=records(document(project,'README.md'),'当前采用')
    approved=any(row['用途']==value['id']+'/'+value['stage'] and reference and
                 media_reference(data['root'],project/'README.md',row['资源引用'])==reference for row in adopted)
    task_record=task_for(project,value['record'])
    task_state=read_record(task_record[1]/'后台任务状态.json') if task_record else {}
    return {'key':key,'url':file_url(api,key) if path else '', 'stage':value['stage'],'run':value['run'],
            'approved':approved,'adoptionKnown':True,'candidateNumber':int(value['run'][1:]),
            'fileRevision':f'{info.st_size}:{info.st_mtime_ns}' if info else '',
            'context':context_for(data,api,value),'deliveryStatus':'已取回' if path else '未取回',
            'taskStatus':task_state.get('status',value['record']['执行状态']),
            'taskStateUrl':file_url(api,(task_record[1]/'后台任务状态.json').relative_to(project).as_posix()) if task_state else '',
            'checkedAt':task_state.get('updated_at','')}


def script_part(project,source,ids):
    text=local(project,source).read_text('utf-8-sig')
    sections=list(re.finditer(r'^### (SH\d{3,})(?:｜|\s)[^\n]*',text,re.M))
    pieces=[]
    for i,match in enumerate(sections):
        if match[1] in ids:
            end=sections[i+1].start() if i+1<len(sections) else len(text)
            pieces.append(re.split(r'^## ',text[match.start():end],maxsplit=1,flags=re.M)[0])
    return documents.markdown('\n'.join(pieces),source)



def script_document(project,api,source):
    path=local(project,source)
    result=ref(project,api,path)
    result['version']=fields(document(project,source),'脚本信息')['脚本版本']
    chapter=re.search(r'^## 镜头与分镜\s*\n(.*?)(?=^## |\Z)',path.read_text('utf-8-sig'),re.M|re.S)[1]
    result['doc']={'title':'分镜脚本','html':documents.markdown(chapter,source),'url':result['url']}
    return result


def production_data(project,api,work=None,**kwargs):
    check_work(project,work); data=state(project)
    segments={key:{**item,'scriptHtml':script_part(project,'脚本.md',item['shotIds']),
                   'scriptUrl':file_url(api,'脚本.md'),'videos':[]} for key,item in data['plan'].items()}
    for value in data['candidates'].values():
        item=segments.setdefault(value['id'],{'id':value['id'],'duration':0,'scriptHtml':'','videos':[]})
        item['videos'].append(video(data,api,value))
    for item in segments.values():
        item['planned']=not item['videos']
    return {'segments':list(segments.values()),'batches':[],'issues':[]}


def items(projects,name,space_api):
    project=projects.project(name)
    progress=fields(document(project,'README.md'),'定位与当前进度')
    status=progress['视频状态']
    color={'制作中':'blue','待发布':'orange','已发布':'green'}[status]
    return [{'kind':'group','name':name,'title':progress['视频名称'],'key':'README.md',
             'statusHtml':f'<span class="status-badge status-{color}">{status}</span>',
             'workStatusLabel':status,'hasArchive':False}]


def apply_script_timing(context, script_shots, entry):
    """Project this round's explicit script times into segment-local planned times."""
    shots = context['shots']
    if context.get('shotTimingSource') == 'recorded' or not shots or len(shots) != len(entry['shotIds']):
        return
    fields_by_id = {shot['fields']['镜号']: shot['fields'] for shot in script_shots}
    spans = []
    for identity in entry['shotIds']:
        fields = fields_by_id[identity]
        interval = re.fullmatch(r'\s*((?:\d+:){1,2}\d+(?:\.\d+)?)\s*[-–—]\s*((?:\d+:){1,2}\d+(?:\.\d+)?)\s*秒?\s*', fields['时间'])
        if not interval:
            return
        start, end = (sum(float(part) * 60 ** power for power, part in enumerate(value.split(':')[::-1]))
                      for value in interval.groups())
        duration = float(fields['时长'].removesuffix('秒').strip())
        if end <= start or not isclose(end - start, duration, abs_tol=1e-6) or (spans and not isclose(start, spans[-1][1], abs_tol=1e-6)):
            return
        spans.append((start, end))
    origin = spans[0][0]
    if not isclose(spans[-1][1] - origin, entry['duration'], abs_tol=1e-6):
        return
    for shot, (start, end) in zip(shots, spans):
        if shot['duration'] is not None and (not isclose(shot['duration'], end - start, abs_tol=1e-6)
                or not isclose(shot['start'], start - origin, abs_tol=1e-6)):
            return
    for shot, (start, end) in zip(shots, spans):
        shot.update(start=start - origin, duration=end - start)
    context['shotTimingSource'] = 'plan'


def detail(projects,name,space_api,work,view=None,**kwargs):
    project=projects.project(name);check_work(project,work)
    if view=='archive':
        raise FileNotFoundError('本视频无独立归档入口')
    data=state(project);api=space_api+'/projects/'+quote(name,safe='')
    result=items(projects,name,space_api)[0]
    current=script_document(project,api,'脚本.md')
    segments=production_data(project,api,work)['segments']
    by_id={v['id']:v for v in segments};rounds=[]
    for item in data['rounds'].values():
        script=script_document(project,api,item['script'])
        values=[]
        for entry in item['values']:
            candidate=video(data,api,entry)
            html=script_part(project,item['script'],entry['shotIds'])
            values.append({**{key:entry[key] for key in ('id','duration','stage','run','carried','shotIds')},
                           'key':candidate['key'],'scriptHtml':html,'scriptUrl':script['url']})
            # Keep original execution context attached to its actual script, never the current draft.
            target=next(v for v in by_id[entry['id']]['videos'] if v['key']==candidate['key'] and v['run']==entry['run'])
            if not entry['carried']:
                context=target['context']
                context.update(scriptHtml=html,scriptUrl=script['url'])
                context['issues']=[issue for issue in context['issues'] if issue!='执行记录未关联分镜快照；这里展示当次实际提示词中的镜头描述。']
                if len(context['shots'])==len(entry['shotIds']):
                    for shot,identity in zip(context['shots'],entry['shotIds']):
                        shot.update(id=identity,html=script_part(project,item['script'],[identity]))
                script_doc=document(project,item['script'])
                script_shots=next(section['shots'] for section in script_doc['sections'] if section['heading']=='镜头与分镜')
                apply_script_timing(context, script_shots, entry)
                context['dialogues']=[]
                for shot in script_shots:
                    identity=shot['fields']['镜号']
                    if identity not in entry['shotIds']:continue
                    for line in shot['fields']['台词'].splitlines():
                        speaker,separator,original=line.partition('：')
                        if separator and original.strip():
                            context['dialogues'].append({'shot':identity,'index':len(context['dialogues']),'speaker':speaker.strip(),'original':original.strip()})
        review_outputs=[]
        for output in item.get('review_outputs',[]):
            reference=media_reference(data['root'],project/'制作记录.md',output['resource'])
            review_outputs.append({'kind':'video','name':output['label'],'url':resource_file(data,api,reference)})
        rounds.append({'number':item['number'],'created_at':item['created_at'],'note':item['note'],
                       'episodeRound':True,'script':script,'storyboard':script,'segments':values,
                       'record':ref(project,api,project/'制作记录.md'),'issues':[],'reviewOutputs':review_outputs})
    materials=[];seen=set()
    for row in records(data['doc'],'输入记录'):
        reference=media_reference(data['root'],project/'制作记录.md',row['资源引用'])
        identity=reference['file']
        if identity in seen or not reference['resource_id'].startswith('IMG-'):
            continue
        seen.add(identity)
        materials.append({'kind':'image','name':reference['resource_id']+'@'+reference['version'],
                          'url':resource_file(data,api,reference),'materialGroup':'unknown','materialStatus':'实际输入',
                          'materialNote':row['输入槽位'],'materialReview':ref(project,api,project/'制作记录.md')})
    progress=fields(document(project,'README.md'),'定位与当前进度')
    result.update(scenes=['whole'],segments={'whole':segments},sceneRounds={'whole':rounds},
        episodeRounds=[{'number':v['number'],'scenes':['whole']} for v in rounds],
        script=current,storyboards={'whole':current},materials=materials,materialRecord=ref(project,api,project/'制作记录.md'),
        productionTask=ref(project,api,project/'制作记录.md'),roundHistory=ref(project,api,project/'制作轮次.json'),
        directorSheets={'whole':director_sheets(data,api)},productionComplete=False,productionIssues=[],
        workStatus={'label':progress['当前阶段'],'summaryHtml':'','deliverySummary':'','record':ref(project,api,project/'README.md')})
    return result


def director_sheets(data,api):
    result={'formal':[],'candidates':[],'record':None}
    adopted={(row['用途'],row['资源引用']) for row in records(document(data['project'],'README.md'),'当前采用')}
    for row in records(data['doc'],'输出记录'):
        sheet=director_slot(row['输出槽位'])
        if sheet is None:
            continue
        reference=media_reference(data['root'],data['project']/'制作记录.md',row['资源引用'])
        item={'kind':'image','name':reference['resource_id'],'url':resource_file(data,api,reference),
              **sheet,'adopted':(f"导演表/第{sheet['page']}页",row['资源引用']) in adopted}
        result['candidates'].append(item)
        if item['adopted']:result['formal'].append(item)
    if result['candidates']:result['record']=ref(data['project'],api,data['project']/'制作记录.md')
    return result


def validate_notes(project,work,identities,changes,view=None):
    check_work(project,work);data=state(project)
    if view=='archive':raise ValueError('不可写入归档意见')
    rounds={n:{(v['id'],v['stage'],v['run']) for v in r['values']} for n,r in data['rounds'].items()}
    if any(r.number not in rounds for r in changes.rounds) or any((n.segment,n.stage,n.run) not in identities or
          n.roundNumber is not None and (n.segment,n.stage,n.run) not in rounds.get(n.roundNumber,set()) for n in changes.notes):
        raise ValueError('意见必须对应已有候选及其整片轮次')


def archive_episode(project,work):
    check_work(project,work)
    return None


def downloads(projects,name,space_api,work,scene='whole',view=None):
    project=projects.project(name);check_work(project,work)
    if scene!='whole':raise FileNotFoundError('分段范围不存在')
    data=state(project);api=space_api+'/projects/'+quote(name,safe='')
    result={stage:{kind:{'count':0,'url':None,'files':[]} for kind in ('videos','director','canvas')} for stage in STAGES}
    result['workPackages']=[];seen=set()
    for candidate in data['candidates'].values():
        execution=candidate['execution']
        if execution in seen:continue
        seen.add(execution);task_record=task_for(project,candidate['record'])
        if not task_record:continue
        _,record=task_record
        for path in record.glob('*.workflow.json'):
            group=result[candidate['stage']]['canvas'];group['files'].append(ref(project,api,path));group['count']+=1
        request=read_record(record/task_record[0].get('request_name','请求.json'))
        task_state=read_record(record/'后台任务状态.json')
        if candidate['stage']!='后处理' and request and task_state.get('prompt_id'):
            group=result[candidate['stage']]['director']
            group['files'].append({'name':execution+' · 导演包','url':api+'/works/'+work+'/production-director?record='+execution})
            group['count']+=1
        else:
            for path in record.glob('*.director.json'):
                group=result[candidate['stage']]['director'];group['files'].append({'name':path.name,'url':api+'/works/'+work+'/production-director?path='+quote(path.relative_to(project).as_posix(),safe='')});group['count']+=1
    for package in check_handoffs(data):
        path, spec, numbers = package['path'], package['spec'], package['rounds']
        key=path.relative_to(project).as_posix();urls=jianying_links(space_api,name,key)
        result['workPackages'].append({'key':key,'label':spec['name'],'version':'','purpose':'剪映交接','rounds':numbers,'count':package['count'],**urls})
        stages={v['stage'] for v in data['rounds'][numbers[-1]]['values']}
        stage=max(stages, key=STAGES.index)
        group=result[stage]['videos'];group.setdefault('packages',[]).append({'name':spec['name'],'count':package['count'],'url':urls['zip']})
        group.update(count=package['count'],url=urls['zip'])
    return result


def director_spec(projects,name,work,path):
    project=projects.project(name);check_work(project,work)
    source=projects.file(name,path)
    if not source.name.endswith('.director.json'):raise ValueError('需要原生导演包清单')
    return json.loads(source.read_text('utf-8-sig'))


def execution_director_spec(projects,name,work,record):
    project=projects.project(name);check_work(project,work)
    data=state(project)
    row=data['executions'].get(record)
    if row is None:raise FileNotFoundError('执行编号不存在')
    task_record=task_for(project,row)
    if not task_record:raise ValueError('未登记实际任务')
    task,folder=task_record
    request=read_record(folder/task.get('request_name','请求.json'))
    task_state=read_record(folder/'后台任务状态.json')
    if not request or not task_state.get('prompt_id'):raise ValueError('缺少实际提交请求和凭据')
    workflow=request['prompt']
    nodes=[key for key,v in workflow.items() if v['class_type']=='MiniMaxH3Director']
    if len(nodes)!=1:raise ValueError('需要唯一的实际H3导演台')
    node=nodes[0];timeline=json.loads(workflow[node]['inputs']['timeline_data'])
    checks={input_key(project,key):stamp for key,stamp in read_record(folder/'执行检查报告.json').get('sources',{}).items()}
    def frozen_file(value):
        path=input_file(project,value,recorded=True);key=input_key(project,path)
        info=path.stat()
        if checks.get(key)!=[info.st_size,info.st_mtime_ns]:
            raise ValueError('原输入缺少核对记录或已改变：'+key)
        return key
    if not task_state.get('remote_url'):raise ValueError('缺少本次实际提交服务地址')
    return {'name':record+'.mmxpack.zip','node_id':node,'workflow':workflow,
            'media':submitted_media(timeline,node,task.get('uploads',[]),frozen_file),'url':task_state['remote_url']}
