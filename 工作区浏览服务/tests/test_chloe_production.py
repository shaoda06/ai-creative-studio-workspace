"""Isolated Chloe workflow, exact resources, review and public workbench projection."""
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from backend.services import production
from backend.services.project_files import ProjectFiles
from backend.services.review_notes import ExportChanges, NoteChange, OverallChange, ProjectReviewNotes, NotesChangedError
from chloe_init import initialize_workspace, initialize_project, initialize_video, resources, SKILLS
from chloe_documents import check_workspace
from chloe_production import state, check
import chloe_browser_production as browser
from project_paths import input_file, input_key, RecordPaths, PreparationPaths, project_file
from backend.services import execution_checks
from types import SimpleNamespace


def add_row(path, heading, values):
    text=path.read_text();start=text.index('## '+heading+'\n');end=text.find('\n## ',start+3)
    if end<0:end=len(text)
    chunk=text[start:end].rstrip()+'\n| '+' | '.join(values)+' |\n\n'
    path.write_text(text[:start]+chunk+text[end:])


class ChloeProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()/'Chloe Workspace'
        self.root = initialize_project(initialize_workspace(self.root), '隔离样例')
        self.project=initialize_video(self.root,'V001','隔离演示')
        self.projects=ProjectFiles(self.root/'projects');self.api='/api/workspaces/chloe'
        self.record=self.project/'制作记录.md'

    def resource(self,kind='video',shared=False,key='first'):
        path=Path(self.temp.name)/ (key+('.mp4' if kind=='video' else '.png'))
        if kind=='image':Image.new('RGB',(16,12),'white').save(path)
        else:path.write_bytes(b'isolated-video-fixture-'+key.encode())
        owner=self.root/'综合资料' if shared else self.project
        ref=resources.register(owner,path,key=key,info=None if kind=='image' else {'bytes':path.stat().st_size,'width':16,'height':12,'duration':5,'fps':24})
        actual=resources.version_file(owner,ref['resource_id'],ref['version'])
        label=('共用' if shared else '本视频')+':'+ref['resource_id']+'@'+ref['version']
        return actual,f'[{label}](<{os.path.relpath(actual,self.project)}>)',ref

    def plan(self):
        add_row(self.project/'脚本.md','分段计划',['P001','SH001','5'])
        add_row(self.project/'脚本.md','分段计划',['P002','SH002','4'])
        path=self.project/'脚本.md'
        body=''
        for identity,duration in [('SH001','5'),('SH002','4')]:
            body+='\n### '+identity+'｜隔离镜头\n\n'
            fields=[('镜号',identity),('时间','00:00-00:0'+duration+'秒'),('时长',duration+'秒'),('景别','中景'),('机位/构图','正面'),('运镜','固定镜头'),('起始画面','站立'),('情绪/动作','展示商品'),('结束画面','站立'),('台词','无'),('音效','无'),('转场方式','直接切'),('商品可见细节','无'),('字幕','无'),('参考需求','无')]
            body+='\n\n'.join('**'+k+'**：'+v for k,v in fields)+'\n'
        path.write_text(path.read_text().replace('## 修订记录',body+'\n## 修订记录'))
        (self.project/'历史版本/脚本-v01.md').write_text((self.project/'脚本.md').read_text())

    def candidate(self,identity,execution,run='R001',stage='一采',output=True):
        add_row(self.record,'执行记录',[execution,'视频生成' if stage!='后处理' else '视频处理','不适用','H3','不适用','不适用','隔离授权','未取得','未取得','未取得','准备中','无'])
        add_row(self.record,'视频分段执行',[identity,stage,run,execution,identity+'视频','0'])
        if output:
            actual,reference,ref=self.resource(key=execution)
            add_row(self.record,'输出记录',[execution,identity+'视频',reference])
            return actual,reference,ref

    def rounds(self,values):
        (self.project/'制作轮次.json').write_text(json.dumps({'format':1,'rounds':values},ensure_ascii=False))

    def round(self,n,segments,**extra):
        return {'number':n,'created_at':'2026-11-07T12:00:00+08:00','note':'隔离审阅','script':'历史版本/脚本-v01.md',
                'segments':[{'id':identity,'execution':execution,'slot':identity+'视频'} for identity,execution in segments],**extra}

    def test_empty_initialization_and_independent_adapter(self):
        self.assertEqual(check_workspace(self.root)['errors'],[])
        self.assertEqual(browser.items(self.projects,self.project.name,self.api)[0]['name'],self.project.name)
        detail=browser.detail(self.projects,self.project.name,self.api,'V001')
        self.assertEqual(detail['segments'],{'whole':[]})
        self.assertEqual(detail['episodeRounds'],[])
        self.assertIn('directorSheets',detail)
        initialize_video(self.root,'V001','隔离演示')
        self.assertEqual(state(self.project)['rounds'],{})

    def published_record(self):
        (self.project/'成片/隔离成片.webm').write_bytes((Path(__file__).parents[1]/'frontend/public/component-samples/video.webm').read_bytes())
        add_row(self.project/'README.md','发布记录',['P001','[成片](<成片/隔离成片.webm>)','不适用','不适用','隔离发布文案','无','不适用','不适用',
            '未取得','2026-11-08T12:00:00+08:00','立即发布','已发布','isolated-work','https://example.com/video/1','隔离手动发布反馈','https://example.com/video/1'])

    def test_list_video_status_reads_readme_without_writing_records(self):
        path=self.project/'README.md'
        original=path.read_text()
        for status,color in [('制作中','blue'),('待发布','orange'),('已发布','green')]:
            with self.subTest(status=status):
                path.write_text(original.replace('| 视频状态 | 制作中 |',f'| 视频状态 | {status} |'))
                if status=='已发布':self.published_record()
                before={p.relative_to(self.project):p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
                item=browser.items(self.projects,self.project.name,self.api)[0]
                self.assertEqual(item['statusHtml'],f'<span class="status-badge status-{color}">{status}</span>')
                self.assertEqual(browser.detail(self.projects,self.project.name,self.api,'V001')['statusHtml'],item['statusHtml'])
                self.assertEqual(item['workStatusLabel'],status)
                self.assertEqual(before,{p.relative_to(self.project):p.read_bytes() for p in self.project.rglob('*') if p.is_file()})

    def test_director_sheet_separate_source_chart_and_candidate(self):
        add_row(self.record,'执行记录',['E001','图片生成','不适用','Imagegen','不适用','不适用','隔离授权','未取得','未取得','未取得','准备中','无'])
        actual,_,resource=self.resource(kind='image')
        template=(SKILLS/'chloe-creative/templates/导演表登记接入模板.md').read_text()
        sample=re.search(r'资源引用为实际`([^`]+)`',template)[1]
        reference=sample.replace('IMG-编号',resource['resource_id']).replace('@V001','@'+resource['version']).replace('相对原文件路径',os.path.relpath(actual,self.project))
        add_row(self.record,'输出记录',['E001','导演表/脚本v02/图表v04/候选3/第1页',reference])
        add_row(self.project/'README.md','当前采用',['导演表/第1页',reference,'隔离批准','2026-11-07T12:00:00+08:00'])
        before={p.relative_to(self.project):p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        sheets=browser.director_sheets(state(self.project),self.api)
        item=sheets['candidates'][0]
        self.assertEqual((item['sourceVersion'],item['version'],item['candidateNumber'],item['page']),('v02','v04',3,1))
        self.assertEqual(sheets['formal'],[item])
        self.assertEqual(before,{p.relative_to(self.project):p.read_bytes() for p in self.project.rglob('*') if p.is_file()})

    def test_legacy_director_sheet_does_not_infer_source_or_candidate(self):
        add_row(self.record,'执行记录',['E001','图片生成','不适用','Imagegen','不适用','不适用','隔离授权','未取得','未取得','未取得','准备中','无'])
        _,reference,_=self.resource(kind='image')
        add_row(self.record,'输出记录',['E001','导演表/v01/第1页',reference])
        item=browser.director_sheets(state(self.project),self.api)['candidates'][0]
        self.assertEqual(item['sourceVersion'],'')
        self.assertEqual(item['version'],'v01')
        self.assertNotIn('candidateNumber',item)

    def test_director_sheet_rejects_ambiguous_versions_and_duplicate_pages(self):
        add_row(self.record,'执行记录',['E001','图片生成','不适用','Imagegen','不适用','不适用','隔离授权','未取得','未取得','未取得','准备中','无'])
        _,reference,_=self.resource(kind='image')
        add_row(self.record,'输出记录',['E001','导演表/脚本v02/图表v01/候选1/第1页',reference])
        original=self.record.read_text()
        for slot in ['导演表/脚本v03/图表v01/候选1/第2页','导演表/脚本v02/图表v01/候选2/第2页',
                     '导演表/脚本v02/图表v01/候选1/第1页','导演表/脚本v02/图表v01/候选0/第2页']:
            with self.subTest(slot=slot):
                self.record.write_text(original)
                add_row(self.record,'输出记录',['E001',slot,reference])
                with self.assertRaises(ValueError):state(self.project)

    def test_segment_plan_rejects_missing_duplicate_order_and_duration_errors(self):
        self.plan()
        script=self.project/'脚本.md';original=script.read_text()
        changes=[
            ('| P002 | SH002 | 4 |','| P002 | SH001 | 5 |'),
            ('| P002 | SH002 | 4 |',''),
            ('| P001 | SH001 | 5 |\n| P002 | SH002 | 4 |','| P002 | SH002 | 4 |\n| P001 | SH001 | 5 |'),
            ('| P002 | SH002 | 4 |','| P002 | SH002 | 99 |'),
            ('| 计划时长秒 | 待确定 |','| 计划时长秒 | 8 |'),
            ('| P002 | SH002 | 4 |','| P001 | SH002 | 4 |'),
            ('| P002 | SH002 | 4 |','| P002 | SH999 | 4 |'),
        ]
        for old,new in changes:
            with self.subTest(change=(old,new)):
                self.assertIn(old,original)
                script.write_text(original.replace(old,new))
                self.assertTrue(check_workspace(self.root,only=script)['errors'])
                with self.assertRaises(ValueError):state(self.project)

    def test_multi_shot_segment_accepts_exact_decimal_planned_duration(self):
        self.plan()
        script=self.project/'脚本.md'
        text=script.read_text().replace('| P001 | SH001 | 5 |\n| P002 | SH002 | 4 |','| P001 | SH001、SH002 | 0.3 |')
        text=text.replace('**时长**：5秒','**时长**：0.1秒').replace('**时长**：4秒','**时长**：0.2秒')
        script.write_text(text.replace('| 计划时长秒 | 待确定 |','| 计划时长秒 | 0.3 |'))
        self.assertEqual(check_workspace(self.root,only=script)['errors'],[])
        self.assertEqual(state(self.project)['plan']['P001']['duration'],0.3)

    def test_script_document_before_generation_and_round_source(self):
        self.plan()
        script=self.project/'脚本.md'
        script.write_text(script.read_text().replace('| 脚本版本 | v01 |','| 脚本版本 | v02 |').replace('## 内容与声音','当前稿专属说明\n\n## 内容与声音').replace('隔离镜头','当前镜头'))
        before=set(self.project.rglob('*'))
        detail=browser.detail(self.projects,self.project.name,self.api,'V001')
        current=detail['storyboards']['whole']
        self.assertEqual(current['version'],'v02')
        self.assertEqual(current['key'],'脚本.md')
        self.assertNotIn('当前稿专属说明',current['doc']['html'])
        self.assertNotIn('内容与声音',current['doc']['html'])
        self.assertNotIn('脚本信息',current['doc']['html'])
        self.assertNotIn('修订记录',current['doc']['html'])
        self.assertNotIn('填写说明',current['doc']['html'])
        self.assertIn('SH001',current['doc']['html'])
        self.assertIn('SH002',current['doc']['html'])
        self.assertIn('当前镜头',current['doc']['html'])
        self.assertEqual(current['doc']['url'],detail['script']['url'])
        self.assertEqual(detail['episodeRounds'],[])
        self.assertTrue(all(not item['videos'] for item in detail['segments']['whole']))
        self.assertEqual(set(self.project.rglob('*')),before)
        self.candidate('P001','E001');self.candidate('P002','E002')
        self.rounds([self.round(1,[('P001','E001'),('P002','E002')])])
        detail=browser.detail(self.projects,self.project.name,self.api,'V001')
        recorded=detail['sceneRounds']['whole'][0]['storyboard']
        self.assertEqual(recorded['version'],'v01')
        self.assertEqual(recorded['key'],'历史版本/脚本-v01.md')
        self.assertNotIn('当前镜头',recorded['doc']['html'])
        self.assertIn('SH001',recorded['doc']['html'])

    def test_round_script_drives_local_timing_not_current_script(self):
        self.plan()
        script=self.project/'脚本.md'
        body=script.read_text().replace('| P001 | SH001 | 5 |\n| P002 | SH002 | 4 |','| P001 | SH001、SH002 | 9 |')
        body=body.replace('00:00-00:05秒','00:10-00:15秒').replace('00:00-00:04秒','00:15-00:19秒')
        (self.project/'历史版本/脚本-v01.md').write_text(body)
        script.write_text(body.replace('00:10-00:15秒','00:10-00:16秒').replace('00:15-00:19秒','00:16-00:19秒').replace('**时长**：5秒','**时长**：6秒').replace('**时长**：4秒','**时长**：3秒'))
        self.candidate('P001','E001')
        self.rounds([self.round(1,[('P001','E001')])])
        context={'shots':[{'id':'SH001','duration':None},{'id':'SH002','duration':None}],
                 'issues':[], 'prompts':{}, 'references':{}}
        with patch.object(browser,'context_for',side_effect=lambda *args:json.loads(json.dumps(context))):
            detail=browser.detail(self.projects,self.project.name,self.api,'V001')
        result=detail['segments']['whole'][0]['videos'][0]['context']
        self.assertEqual([(s['start'],s['duration']) for s in result['shots']],[(0,5),(5,4)])
        self.assertEqual(result['shotTimingSource'],'plan')

    def test_unreliable_script_timing_stays_disabled_and_recorded_times_win(self):
        context={'shots':[{'id':'SH003','duration':None},{'id':'SH004','duration':None}]}
        entry={'shotIds':['SH003','SH004'],'duration':10}
        shots=[{'fields':{'镜号':'SH003','时间':'00:10-00:14秒','时长':'4'}},
               {'fields':{'镜号':'SH004','时间':'00:14-00:20秒','时长':'6'}}]
        for bad in ['待确定','00:13-00:19秒','00:15-00:21秒','00:14-00:19秒']:
            changed=json.loads(json.dumps(shots));changed[1]['fields']['时间']=bad
            result=json.loads(json.dumps(context));browser.apply_script_timing(result,changed,entry)
            self.assertEqual(result,context)
        result=json.loads(json.dumps(context));browser.apply_script_timing(result,shots,entry)
        self.assertEqual([(s['start'],s['duration']) for s in result['shots']],[(0,4),(4,6)])
        result['shotTimingSource']='recorded';result['shots'][0]['duration']=3.5
        before=json.loads(json.dumps(result));browser.apply_script_timing(result,shots,entry)
        self.assertEqual(result,before)
        mismatch={'shots':[{'id':'SH003','duration':None}]}
        browser.apply_script_timing(mismatch,shots,entry)
        self.assertNotIn('shotTimingSource',mismatch)

    def test_complete_round_partial_revision_and_approval_not_inferred(self):
        self.plan();self.candidate('P001','E001');self.candidate('P002','E002')
        self.candidate('P001','E003','R002')
        self.rounds([self.round(1,[('P001','E001'),('P002','E002')]),
                     self.round(2,[('P001','E003'),('P002','E002')],base_round=1,changed_segments=['P001'])])
        data=browser.detail(self.projects,self.project.name,self.api,'V001')
        self.assertEqual([v['carried'] for v in data['sceneRounds']['whole'][1]['segments']],[False,True])
        self.assertFalse(any(v['approved'] for p in data['segments']['whole'] for v in p['videos']))
        # No media copy is created by repeated reads.
        files=list(self.project.rglob('*.mp4'));browser.detail(self.projects,self.project.name,self.api,'V001')
        self.assertEqual(list(self.project.rglob('*.mp4')),files)
        spec=json.loads((self.project/'制作轮次.json').read_text());spec['rounds'][1]['changed_segments']=[]
        self.rounds(spec['rounds'])
        with self.assertRaisesRegex(ValueError,'changed_segments'):state(self.project)

    def test_pending_candidate_and_whole_round_requirements(self):
        self.plan();self.candidate('P001','E001',output=False);self.candidate('P002','E002',output=False)
        self.rounds([self.round(1,[('P001','E001'),('P002','E002')])])
        data=browser.detail(self.projects,self.project.name,self.api,'V001')
        self.assertEqual(data['segments']['whole'][0]['videos'][0]['url'],'')
        self.rounds([self.round(1,[('P001','E001')])])
        with self.assertRaisesRegex(ValueError,'完整'):state(self.project)

    def test_exact_shared_input_and_output_boundary(self):
        actual,reference,ref=self.resource(kind='image',shared=True)
        key='@shared/'+actual.relative_to(self.root/'综合资料').as_posix()
        self.assertEqual(input_file(self.project,key),actual)
        self.assertEqual(input_key(self.project,actual),key)
        paths=RecordPaths.from_resolved(self.project,[str(actual),str(self.project/'执行记录')])
        self.assertEqual(paths.file(key),actual)
        prep=PreparationPaths.from_resolved(self.project,[str(actual)])
        self.assertEqual(prep.io_file(key),actual)
        with self.assertRaisesRegex(ValueError,'越出项目'):project_file(self.project,key)
        with self.assertRaises(ValueError):input_file(self.project,'@shared/账号定位.md')
        with self.assertRaises(ValueError):input_file(self.project,'../V002-其他/secret.png')
        payload={'task_type':'video-first-pass','record_dir':'执行记录/E001','uploads':[{'file':key}], 'outputs':[]}
        routed=resources.route_task(self.project,payload)
        self.assertEqual(routed['uploads'][0]['file'],str(actual))
        self.assertEqual(routed['uploads'][0]['resource']['version'],ref['version'])
        self.assertEqual(list((self.project/'资源/图片').iterdir()),[])
        fake=SimpleNamespace(project=str(self.project),record_dir=str(self.project/'执行记录'),uploads=[{'file':str(actual)}])
        with patch.object(execution_checks,'associated_sources',return_value=[]):
            report=execution_checks.sources(fake,mapping={})
        self.assertIn(key,report)

    def test_notes_round_identity_and_concurrency(self):
        self.plan();first,_,_=self.candidate('P001','E001');self.candidate('P002','E002')
        self.rounds([self.round(1,[('P001','E001'),('P002','E002')])])
        identities={('P001','一采','R001'),('P002','一采','R001')}
        note=NoteChange(segment='P001',stage='一采',run='R001',text='修改动作',expectedText='',fileRevision='stamp',roundNumber=1)
        changes=ExportChanges(notes=[note],rounds=[OverallChange(number=1,text='总体意见',expectedText='')])
        browser.validate_notes(self.project,'V001',identities,changes)
        store=ProjectReviewNotes();store.save(browser.notes_path(self.project),changes)
        with self.assertRaises(NotesChangedError):store.save(browser.notes_path(self.project),changes)
        note.roundNumber=2
        with self.assertRaisesRegex(ValueError,'意见必须'):browser.validate_notes(self.project,'V001',identities,changes)
        self.assertTrue(first.exists())

    def test_video_prompt_file_validation(self):
        self.plan();self.candidate('P001','E001')
        original=self.record.read_text()
        check(self.project)  # A draft may be awaiting its prompt, but cannot be submitted yet.
        self.record.write_text(original.replace('| 准备中 |', '| 已取消 |'))
        check(self.project)  # Cancellation before submission does not invent a prompt.
        self.record.write_text(original.replace('| 准备中 |', '| 已提交 |'))
        with self.assertRaisesRegex(ValueError,'缺少中英文提示词文件'):
            check(self.project)
        def set_prompt(value):
            self.record.write_text(original.replace('| H3 | 不适用 |', '| H3 | '+value+' |'))
        set_prompt('Action in English')
        with self.assertRaisesRegex(ValueError,'Markdown文件链接'):
            check(self.project)
        folder=self.project/'执行记录/E001';folder.mkdir()
        prompt=folder/'提示词.md'
        set_prompt('[提示词](<执行记录/E001/提示词.md>)')
        with self.assertRaisesRegex(ValueError,'文件链接不存在'):
            check(self.project)
        prompt.write_text('## 模型提示词正文\nAction.\n')
        with self.assertRaisesRegex(ValueError,'中文提示词参考版'):
            check(self.project)
        prompt.write_text('## 模型提示词正文\nAction.\n## 中文提示词参考版\n\n')
        with self.assertRaisesRegex(ValueError,'中文提示词参考版'):
            check(self.project)
        body='## 模型提示词正文\nAction.\n## 中文提示词参考版\n动作。\n'
        prompt.write_text(body+'## 中文提示词参考版\n重复内容。\n')
        with self.assertRaisesRegex(ValueError,'唯一'):
            check(self.project)
        template=(SKILLS/'chloe-production/templates/视频提示词模板.md').read_text()
        prompt.write_text(template)
        with self.assertRaisesRegex(ValueError,'已填写'):
            check(self.project)
        prompt.write_text(body)
        self.record.write_text(self.record.read_text().replace('| 准备中 |', '| 已提交 |'))
        self.assertEqual(check(self.project)['candidates'],1)

    def test_shared_request_context_refers_to_original(self):
        self.plan();self.candidate('P001','E001');self.candidate('P002','E002')
        actual,reference,ref=self.resource(kind='image',shared=True)
        key=input_key(self.project,actual)
        folder=self.project/'执行记录/E001';folder.mkdir()
        timeline={'global':{'commonEnabled':False},'segments':[{'prompt':'detailed_description:\n[Shot 1]\ntime: 0-5\nAction.', 'refs':[{'imageFile':'remote.png','index':0}]}]}
        workflow={'1':{'class_type':'MiniMaxH3Director','inputs':{'timeline_data':json.dumps(timeline)}}}
        task={'project':str(self.project),'record_dir':'执行记录/E001','uploads':[{'file':key,'node':'1','input':'timeline_data','json-path':['segments',0,'refs',0,'imageFile']}]}
        (folder/'提交任务清单.json').write_text(json.dumps({'tasks':[task]}))
        (folder/'请求.json').write_text(json.dumps({'prompt':workflow}))
        (folder/'后台任务状态.json').write_text(json.dumps({'prompt_id':'isolated','status':'completed','remote_url':'http://localhost:8188'}))
        info=actual.stat();(folder/'执行检查报告.json').write_text(json.dumps({'sources':{key:[info.st_size,info.st_mtime_ns]}}))
        self.record.write_text(self.record.read_text().replace('| E001 | 视频生成 | 不适用 | H3 | 不适用 | 不适用 |','| E001 | 视频生成 | 不适用 | H3 | 不适用 | [参数](<执行记录/E001/提交任务清单.json>) |'))
        value=browser.production_data(self.project,self.api+'/projects/'+self.project.name,'V001')
        context=value['segments'][0]['videos'][0]['context']
        self.assertIn('/production-files/',context['references']['segment'][0]['url'])
        prompt=folder/'提示词.md'
        template=(SKILLS/'chloe-production/templates/视频提示词模板.md').read_text()
        prompt.write_text(template.replace('{{execution}}','E001').replace('{{segment}}','P001')
            .replace('{{按实际H3模式及真实输入角色填写完整模型正文}}','Prepared wording, not request evidence.')
            .replace('{{填写同版完整中文参考}}','[Shot 1]\ntime: 0-5\n动作。'))
        self.record.write_text(self.record.read_text().replace('| H3 | 不适用 |','| H3 | [提示词](<执行记录/E001/提示词.md>) |',1))
        check(self.project)
        context=browser.production_data(self.project,self.api+'/projects/'+self.project.name,'V001')['segments'][0]['videos'][0]['context']
        self.assertEqual(context['prompts']['chinese'],'[Shot 1]\ntime: 0-5\n动作。')
        self.assertIn('Action.',context['prompts']['english'])
        self.assertNotIn('Prepared wording',context['prompts']['english'])
        self.assertIn('E001/',context['prompts']['chineseUrl'])
        self.assertEqual(list(folder.glob('*.md')),[prompt])
        self.assertIn('Action.',context['prompts']['english'])
        self.assertEqual(list((self.project/'资源/图片').iterdir()),[])

    def test_second_pass_reuses_upstream_bindings_without_writes(self):
        self.plan();self.candidate('P001','E001');self.candidate('P001','E002',stage='二采')
        shared,_,_=self.resource(kind='image',shared=True,key='portrait')
        local_image,_,_=self.resource(kind='image',key='opening')
        timeline={'global':{'commonEnabled':True,'refs':[{'imageFile':'remote-face.png','index':0}]},
                  'segments':[{'prompt':'First pass.', 'refs':[{'imageFile':'remote-opening.png','index':1}]}]}
        sources={input_key(self.project,p):[p.stat().st_size,p.stat().st_mtime_ns] for p in (shared,local_image)}
        for execution in ('E001','E002'):
            folder=self.project/'执行记录'/execution;folder.mkdir()
            uploads=[]
            if execution=='E001':
                uploads=[{'file':input_key(self.project,p),'node':'1','input':'timeline_data','json-path':slot}
                         for p,slot in [(shared,['global','refs',0,'imageFile']),
                                        (local_image,['segments',0,'refs',0,'imageFile'])]]
            else:
                timeline['segments'][0]['prompt']='Actual second pass.'
            task={'project':str(self.project),'record_dir':'执行记录/'+execution,'uploads':uploads}
            (folder/'提交任务清单.json').write_text(json.dumps({'tasks':[task]}))
            request={'prompt':{'1':{'class_type':'MiniMaxH3Director','inputs':{'timeline_data':json.dumps(timeline)}}}}
            (folder/'请求.json').write_text(json.dumps(request))
            (folder/'后台任务状态.json').write_text(json.dumps({'prompt_id':execution,'status':'completed'}))
            (folder/'执行检查报告.json').write_text(json.dumps({'sources':sources if execution=='E001' else {}}))
            self.record.write_text(self.record.read_text().replace(
                f'| {execution} | 视频生成 | 不适用 | H3 | 不适用 | 不适用 |',
                f'| {execution} | 视频生成 | '+('E001' if execution=='E002' else '不适用')+
                f' | H3 | 不适用 | [参数](<执行记录/{execution}/提交任务清单.json>) |'))
        data=state(self.project)
        candidate=next(v for v in data['candidates'].values() if v['execution']=='E002')
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        context=browser.context_for(data,self.api+'/projects/'+self.project.name,candidate)
        self.assertEqual(context['prompts']['english'],'Actual second pass.')
        self.assertIn('E002/',context['prompts']['englishUrl'])
        for group,path in [('common',shared),('segment',local_image)]:
            item=context['references'][group][0]
            self.assertNotIn('missing',item)
            self.assertTrue(item['url'].endswith(browser.quote(path.relative_to(self.root).as_posix(),safe='/')))
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        # A new remote reference cannot be substituted with the current asset or an old slot.
        request_path=self.project/'执行记录/E002/请求.json'
        timeline['segments'][0]['refs'][0]['imageFile']='unrecorded.png'
        request['prompt']['1']['inputs']['timeline_data']=json.dumps(timeline)
        request_path.write_text(json.dumps(request))
        context=browser.context_for(data,self.api,candidate)
        self.assertTrue(context['references']['segment'][0]['missing'])
        self.assertNotIn('missing',context['references']['common'][0])
        info=shared.stat()
        os.utime(shared,ns=(info.st_atime_ns,info.st_mtime_ns+1_000_000))
        context=browser.context_for(data,self.api,candidate)
        self.assertTrue(context['references']['common'][0]['missing'])
        self.assertTrue(any('执行后变化' in issue for issue in context['issues']))
        shared.chmod(info.st_mode | 0o200)
        shared.unlink()
        with self.assertRaisesRegex(ValueError,'共用输入尚未完整保存'):
            browser.context_for(data,self.api,candidate)

    def test_registered_http_routes_and_shared_media_boundaries(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend import main
        from backend.services.workspaces import Workspace
        app=FastAPI();app.include_router(main.spaces_router, prefix='/api/workspaces/{workspace_id}')
        space=Workspace('chloe','Chloe',self.root,self.root/'runtime','chloe-commerce',self.projects,production_adapter='chloe-production')
        app.state.workspaces=SimpleNamespace(get=lambda identity:space)
        with TestClient(app) as client:
            listing=client.get(self.api+'/production-videos')
            self.assertEqual(listing.status_code,200,listing.text)
            base=self.api+'/projects/'+self.project.name
            self.assertEqual(client.get(base).status_code,200)
            detail=client.get(base+'/works/V001/production-detail')
            self.assertEqual(detail.status_code,200,detail.text)
            self.assertEqual(client.get(base+'/works/V002/production-detail').status_code,404)
            self.assertEqual(client.get(base+'/works/V001/production-downloads').status_code,200)
            self.assertEqual(client.get(base+'/works/V001/production-notes').json(),{'notes':{},'rounds':{}})
            actual,_,_=self.resource(kind='image',shared=True)
            self.assertEqual(client.get(self.api+'/production-files/'+actual.relative_to(self.root).as_posix()).status_code,200)
            self.assertEqual(client.get(self.api+'/production-files/综合资料/账号定位.md').status_code,404)
            self.assertEqual(client.get(self.api+'/production-files/%2e%2e/secret.png').status_code,404)

    def test_whole_postprocess_review_beside_segment_round(self):
        self.plan()
        self.candidate('P001','E001')
        self.candidate('P002','E002')
        record='执行记录/E003'
        source='整片原片.mp4'
        output='整片后处理.mp4'
        (self.project/source).write_text('原片')
        (self.project/output).write_text('整片后处理')
        from execution_records import write_entries
        write_entries(self.project/record,{
            '执行检查报告.json':{'prepared_input':{'task_type':'video-postprocess',
                'record_dir':record,'uploads':[{'file':source}],
                'outputs':[{'path':output,'response_name':'取回.json'}]}},
            '后台任务状态.json':{'id':'test','task_type':'video-postprocess','record_dir':record},
            '取回.json':{},
        })
        round_=self.round(1,[('P001','E001'),('P002','E002')])
        round_['review_outputs']=[{'label':'整片后处理','source':source,'postprocess':record}]
        self.rounds([round_])
        detail=browser.detail(self.projects,self.project.name,self.api,'V001')
        review,=detail['sceneRounds']['whole'][0]['reviewOutputs']
        self.assertEqual(review['key'],output)
        self.assertEqual([len(item['videos']) for item in detail['segments']['whole']],[1,1])

    def prepare_handoff(self):
        self.plan()
        self.candidate('P001','E001');self.candidate('P002','E002')
        self.candidate('P001','E003',stage='二采');self.candidate('P002','E004',stage='二采')
        first,ref1,_=self.candidate('P001','E005',stage='后处理')
        second,ref2,_=self.candidate('P002','E006',stage='后处理')
        body=self.record.read_text()
        for identity,source in [('E003','E001'),('E004','E002'),('E005','E003'),('E006','E004')]:
            kind='视频处理' if identity in ('E005','E006') else '视频生成'
            body=body.replace('| '+identity+' | '+kind+' | 不适用 |','| '+identity+' | '+kind+' | '+source+' |')
        self.record.write_text(body)
        self.rounds([self.round(1,[('P001','E001'),('P002','E002')]),self.round(2,[('P001','E003'),('P002','E004')]),self.round(3,[('P001','E005'),('P002','E006')])])
        for identity,reference in [('P001',ref1),('P002',ref2)]:
            add_row(self.project/'README.md','当前采用',[identity+'/后处理',reference,'隔离的二采批准与技术核对','2026-11-07T12:00:00+08:00'])
        manifest={'name':'隔离剪映','media':[{'file':path.relative_to(self.project).as_posix(),'member':str(i)+'.mp4','timeline':True} for i,path in enumerate((first,second))]}
        (self.project/'剪辑交接/交接.jianying.json').write_text(json.dumps(manifest))
        add_row(self.project/'README.md','剪映交接',['J001','2026-11-07T12:10:00+08:00','[清单](<剪辑交接/交接.jianying.json>)','可下载','本次整片采用组合已确认'])
        return manifest

    def test_postprocess_provenance_adoption_and_handoff(self):
        self.prepare_handoff()
        detail=browser.detail(self.projects,self.project.name,self.api,'V001')
        self.assertTrue(all(p['videos'][-1]['approved'] for p in detail['segments']['whole']))
        download=browser.downloads(self.projects,self.project.name,self.api,'V001')
        self.assertEqual(download['workPackages'][0]['rounds'],[3])
        self.assertEqual(check_workspace(self.root)['errors'],[])
        body=self.record.read_text().replace('| E005 | 视频处理 | E003 |','| E005 | 视频处理 | E001 |')
        self.record.write_text(body)
        with self.assertRaisesRegex(ValueError,'二采执行'):state(self.project)

    def test_handoff_rejects_missing_duplicate_reordered_and_wrong_versions(self):
        manifest=self.prepare_handoff()
        path=self.project/'剪辑交接/交接.jianying.json'
        unused,_,_=self.resource(key='unused')
        for label,media in (
            ('missing',manifest['media'][:1]),
            ('duplicate',[manifest['media'][0],{**manifest['media'][0],'member':'duplicate.mp4'}]),
            ('reordered',list(reversed(manifest['media']))),
            ('wrong version',[{**manifest['media'][0],'file':unused.relative_to(self.project).as_posix()},manifest['media'][1]]),
        ):
            with self.subTest(case=label):
                path.write_text(json.dumps({**manifest,'media':media}))
                with self.assertRaisesRegex(ValueError,'完整匹配片段版本与顺序'):
                    check(self.project)
        path.write_text(json.dumps({**manifest,'media':manifest['media']+[{'file':unused.relative_to(self.project).as_posix(),'member':'candidate.mp4','timeline':False}]}))
        self.assertEqual(check_workspace(self.root)['errors'],[])

    def test_handoff_requires_record_and_adoption_at_handoff_time(self):
        self.prepare_handoff()
        path=self.project/'README.md';good=path.read_text()
        for label,bad,error in (
            ('no record','\n'.join(line for line in good.splitlines() if not line.startswith('| J001 |')),'缺少README交接记录'),
            ('no adoption','\n'.join(line for line in good.splitlines() if not line.startswith('| P00')),'尚未采用'),
            ('future adoption',good.replace('隔离的二采批准与技术核对 | 2026-11-07T12:00','隔离的二采批准与技术核对 | 2026-11-07T12:20'),'尚未采用'),
            ('no basis',good.replace('| 本次整片采用组合已确认 |','| 无 |'),'交接时间与采用依据'),
            ('missing manifest',good.replace('交接.jianying.json','不存在.jianying.json'),'文件链接不存在'),
        ):
            with self.subTest(case=label):
                path.write_text(bad)
                self.assertTrue(any(error in item['error'] for item in check_workspace(self.root)['errors']))
        path.write_text(good)

    def test_old_handoff_preserves_adoption_history_after_replacement_or_cancellation(self):
        self.prepare_handoff()
        path=self.project/'README.md'
        from chloe_documents import records
        from chloe_production import document
        adopted=records(document(self.project,'README.md'),'当前采用')
        for number,row in enumerate(adopted,1):
            add_row(path,'采用变更',['B00'+str(number),'2026-11-07T12:00:00+08:00',row['用途'],'无',row['资源引用'],'原采用依据'])
        body=path.read_text()
        path.write_text('\n'.join(line for line in body.splitlines() if not line.startswith('| P00'))+'\n')
        add_row(path,'采用变更',['B003','2026-11-07T12:20:00+08:00','P001/后处理',adopted[0]['资源引用'],'无','取消该采用'])
        self.assertEqual(check_workspace(self.root)['errors'],[])
        old=path.read_text()
        path.write_text(old.replace('| J001 | 2026-11-07T12:10','| J001 | 2026-11-07T12:30'))
        with self.assertRaisesRegex(ValueError,'已取消采用'):
            check(self.project)
        path.write_text(old)
        # A newer valid candidate and current adoption must not rewrite the old package.
        _,new_ref,_=self.candidate('P001','E007',run='R002',stage='后处理')
        self.record.write_text(self.record.read_text().replace('| E007 | 视频处理 | 不适用 |','| E007 | 视频处理 | E003 |'))
        add_row(path,'当前采用',['P001/后处理',new_ref,'新采用','2026-11-07T12:30:00+08:00'])
        self.assertEqual(check_workspace(self.root)['errors'],[])


from tests import test_comfy_tasks as task_fixtures
from tests import test_technical_video as technical_fixture
from unittest.mock import AsyncMock
from backend.services import comfy_tasks as tasks
import execution_records as recordio

class SharedVideoInputTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=task_fixtures.TaskTests.asyncSetUp
    asyncTearDown=task_fixtures.TaskTests.asyncTearDown
    configure=technical_fixture.TechnicalVideoTests.configure

    async def test_shared_reference_prepares_submits_and_reloads_without_copy(self):
        self.configure()
        common=self.root/'综合资料';common.mkdir();resources.initialize(common,managed=True)
        resources.initialize(self.project,managed=True)
        image=self.root/'portrait.png';Image.new('RGB',(16,12),'white').save(image)
        reference=resources.register(common,image,key='portrait')
        source=resources.version_file(common,reference['resource_id'],reference['version'])
        key=input_key(self.project,source)
        timeline=json.loads(self.data.workflow['director']['inputs']['timeline_data'])
        timeline['segments'][0]['refs']=[{'imageFile':'reference.png','index':0}]
        self.data.workflow['director']['inputs']['timeline_data']=json.dumps(timeline)
        self.data.uploads=[{'file':key,'node':'director','input':'timeline_data','subfolder':'inputs',
                           'response-name':'上传.json','json-path':['segments',0,'refs',0,'imageFile']}]
        result=await self.store.prepare_only(self.data)
        self.assertTrue(result['prepared'])
        info=source.stat()
        upload={'input_path':'inputs/reference.png','sha256':'fixture','bytes':info.st_size,'mtime_ns':info.st_mtime_ns}
        with patch.object(tasks.client,'upload',return_value=upload),patch.object(tasks,'connect',AsyncMock(return_value=AsyncMock())),\
             patch.object(tasks.client,'submit',return_value={'prompt_id':'shared-test','submission_state':'accepted'}),\
             patch.object(self.store,'check_target_cache',AsyncMock()),patch.object(self.store,'watch',AsyncMock()):
            accepted=await self.store.submit(self.data)
        row=self.store.rows[accepted['monitor_id']]
        self.assertEqual(Path(row['input'].uploads[0]['file']),source)
        saved=self.store.portable_input(row['input'])
        self.assertEqual(saved['uploads'][0]['file'],key)
        restored=tasks.TaskInput.model_validate(saved);self.store.resolve_input(restored,recorded=True)
        self.assertEqual(Path(restored.uploads[0]['file']),source)
        self.assertEqual(list((self.project/'资源/图片').glob('**/*.png')),[])
        self.assertIn(key,recordio.read(self.record/'执行检查报告.json')['sources'])
        association=recordio.read(self.record/'资源关联.json')
        self.assertEqual(association['inputs'][0]['file'],key)
        self.assertEqual(association['inputs'][0]['scope'],'@shared')
