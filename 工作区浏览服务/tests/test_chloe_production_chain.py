"""Isolated Chloe chain with mocked remote sampling and downloads."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import AsyncMock, patch
from backend import main
from backend.services import comfy_tasks as tasks, submission_plans, result_registration
from tests import test_chloe_production as fixtures
from tests.test_submission_lifecycle import ENGLISH
from tests.test_songssx import PROMPT
from backend.services.episode_downloads import songssx_round_videos
from backend.services.review_notes import ExportChanges
from workflow_paths import workflow_file
from chloe_production import prompt_sections
import execution_records as recordio


class ChloeChainTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.f=fixtures.ChloeProductionTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.plan(); self.root=self.f.root; self.project=self.f.project
        (self.root/'comfyui-config.json').write_text(json.dumps({'remote-urls':['http://comfy.invalid:8188']}))
        self.store=tasks.TaskStore(self.root/'runtime',self.root); self.store.queue_notifications=False
        self.addAsyncCleanup(self.store.close)
        self.enterContext(patch.object(tasks,'read_thread_name',AsyncMock(return_value='隔离链路')))
        self.source,self.source_link,_=self.f.resource(kind='image',shared=True)
        self.reference=fixtures.input_key(self.project,self.source)
        from chloe_documents import media_reference
        binding=media_reference(self.root,self.f.record,self.source_link)
        (self.project/'资源/共用引用.json').write_text(json.dumps({'format':1,'references':{'portrait':binding}}))
        self.api=self.f.api+'/projects/'+self.project.name

    def entry(self, execution, ids, upstream=None):
        folder=self.project/'执行记录'/execution; folder.mkdir()
        stage='二采' if upstream else '一采'
        for i,identity in enumerate(ids):
            fixtures.add_row(self.f.record,'视频分段执行',[identity,stage,'R001',execution,identity+'视频',str(i)])
        text=''
        for language,body in [('模型提示词正文',ENGLISH),('中文提示词参考版','此段中文')]:
            text+='## '+language+'\n\n### 共用\n\n'+('Common.' if language=='模型提示词正文' else '共用说明。')+'\n\n'
            text+='\n\n'.join('### '+p+'\n\n'+body+' '+p for p in ids)+'\n\n'
        (folder/'提示词.md').write_text(text)
        fixtures.add_row(self.f.record,'执行记录',[execution,'视频生成',upstream or '不适用','H3',
            f'[提示词](<执行记录/{execution}/提示词.md>)',f'[参数](<执行记录/{stage}任务清单.json>)',
            '[审阅](<制作记录.md#审阅记录>)' if upstream else '隔离测试授权','未取得','未取得','未取得','准备中','无'])
        fixtures.add_row(self.f.record,'输入记录',[execution,'Picture 1','portrait',self.source_link])
        if upstream:
            canvas=self.project/'执行记录'/upstream/'任务.workflow.json'
        else:
            graph=json.loads(workflow_file('Minimax-H3-导演台-视频生成-标准版','workflow').read_text())
            node=next(n for n in graph['nodes'] if n['id']==502); inputs=node['widgets_values_named']
            timeline=json.loads(inputs['timeline_data']);common=timeline['global']
            common.update(prompt='Common.',commonEnabled=True,taskType='r2v',refs=[{'index':0,'imageFile':'planned/ref.png'}],refVideos=[],refAudios=[],referenceVideo=None)
            segments=[]
            for p in ids:
                item=deepcopy(timeline['segments'][0]);item.update(prompt=ENGLISH+' '+p,durationSec=5 if p=='P001' else 4,
                    refs=[],refVideos=[],refAudios=[],referenceVideo=None,continuityFromPrev=False);segments.append(item)
            timeline.update(segments=segments,runSelectEnabled=True,runSelection=list(range(len(ids))),editMode='segment')
            timeline['output']['exportMode']='segments'
            timeline['batchWorkspaces']['r2v'].update(globalCommon=deepcopy(common),segments=deepcopy(segments))
            inputs.update(timeline_data=json.dumps(timeline),global_prompt='');node['widgets_values']=list(inputs.values())
            canvas=folder/'内容.workflow.json';canvas.write_text(json.dumps(graph))
        spec=dict(task_type='video-second-pass' if upstream else 'video-first-pass',title=execution,authorization='隔离授权',
            record_dir=f'执行记录/{execution}',canvas=canvas.relative_to(self.project).as_posix(),output_nodes=[403],
            references=[{'placeholder':'inputs/reference.png' if upstream else 'planned/ref.png','file':self.reference}],
            video_plan={'adapter':'technical','metadata':'ffprobe'},segment_plan={'director_node':'502','report_node':'403',
            'output_root':'/remote/output','targets':[{'index':i,'path':f'候选/{execution}-{p}.mp4','response_name':p+'取回.json'} for i,p in enumerate(ids)]})
        if upstream:spec['h3_second_pass']={'width':1920,'height':1088}
        else:spec['h3_first_pass']=dict(aspect_ratio='16:9',width=1024,height=576,steps=8,refine_steps=4,scene_type='dialogue',speed=None,loras=[])
        return spec

    async def enqueue(self, entries, stage):
        path=self.project/'执行记录'/f'{stage}任务清单.json';path.write_text(json.dumps({'tasks':entries,'group_title':'隔离整片'}))
        payload=main.SubmissionPlanInput(project=self.project.name,plan_file=path.relative_to(self.project).as_posix(),
            thread_id='isolated-thread',desktop=dict(node='node',server='server.mjs',pipe='private-pipe',caller_thread='isolated-thread'),prepare_only=True,start_paused=True)
        with patch.object(self.store,'read_session_name',AsyncMock()):
            before=len(self.store.rows)
            prepared=await submission_plans.execute(self.store,payload)
            self.assertEqual(prepared['status'],'prepared');self.assertEqual(len(self.store.rows),before)
            accepted=payload.model_copy(update={'prepare_only':False})
            result=await submission_plans.execute(self.store,accepted)
            reused=await submission_plans.execute(self.store,accepted)
        self.assertEqual(result['tasks'],reused['tasks'])
        return result

    async def test_group_submit_collect_review_and_second_pass(self):
        entries=[self.entry('E001',['P001']),self.entry('E002',['P002'])]
        self.f.rounds([self.f.round(1,[('P001','E001'),('P002','E002')])])
        result=await self.enqueue(entries,'一采');fixtures.check(self.project)
        pending=fixtures.browser.production_data(self.project,self.api,'V001')
        self.assertEqual(len(pending['segments']),2)
        self.assertTrue(all(not s['videos'][0]['url'] for s in pending['segments']))
        sample=self.root/'fixture.mp4'
        subprocess.run([shutil.which('ffmpeg'),'-v','error','-f','lavfi','-i','color=s=64x48:r=24:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(sample)],check=True)
        media=sample.read_bytes()
        for item,identity in zip(result['tasks'],['P001','P002']):
            key=item['local_task_id'];data=self.store.rows[key]['input'];execution=Path(data.record_dir).name;info=self.source.stat()
            with patch.object(tasks.client,'upload',return_value={'input_path':'inputs/reference.png','sha256':'isolated','bytes':info.st_size,'mtime_ns':info.st_mtime_ns,'remote':{'name':'reference.png','subfolder':'inputs','type':'input'}}),\
                 patch.object(tasks,'connect',AsyncMock(return_value=AsyncMock())),\
                 patch.object(tasks.client.Client,'json',return_value={'prompt_id':'remote-'+execution}),\
                 patch.object(self.store,'check_target_cache',AsyncMock()),patch.object(self.store,'watch',AsyncMock()):
                workflow=await self.store.prepare(key)
                await self.store.submit(data,key=key,workflow=workflow)
            def download(remote,args):
                path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(media)
                return dict(path=str(path),bytes=len(media),sha256=None,remote={k:getattr(args,k) for k in ('filename','subfolder','type')})
            terminal={'history':{'outputs':{'403':{'text':['Segment 1: 一采 mp4 saved → /remote/output/minimax_seg_export/run/seg_0000_pre.mp4']}}}}
            with patch.object(tasks.client,'download',side_effect=download) as downloaded:
                self.assertEqual(await tasks.segments.finish(self.store,key,terminal),[])
                self.assertEqual(await tasks.segments.finish(self.store,key,terminal),[]);self.assertEqual(downloaded.call_count,1)
            row=self.store.rows[key];row['state'].update(status='completed',collected=1,expected=1);self.store.save(key)
            report=result_registration.register(self.store,key);self.assertEqual(result_registration.register(self.store,key),report)
            output=self.project/report['items'][0]['path'];ref=fixtures.resources.reference(self.project,output);self.assertIsNotNone(ref)
            fixtures.add_row(self.f.record,'输出记录',[execution,identity+'视频',f'[本视频:{ref["resource_id"]}@{ref["version"]}](<{output.relative_to(self.project)}>)'])
            self.f.record.write_text(self.f.record.read_text().replace('| 隔离测试授权 | 未取得 |','| 隔离测试授权 | '+key+' |',1))
            current=fixtures.browser.production_data(self.project,self.api,'V001')
            self.assertEqual(sum(bool(p['videos'][0]['url']) for p in current['segments']),1 if identity=='P001' else 2)
        value=fixtures.browser.production_data(self.project,self.api,'V001')
        for part in value['segments']:
            video=part['videos'][0];self.assertTrue(video['url']);self.assertFalse(video['approved'])
            self.assertTrue(video['context']['references']['common'],video['context'])
            self.assertIn('/production-files/',video['context']['references']['common'][0]['url'])
            self.assertIn(part['id'],video['context']['prompts']['chinese'])
        self.assertEqual(list((self.project/'资源/图片').glob('**/*.png')),[])
        self.assertEqual(len(list((self.project/'资源/视频').glob('**/*.mp4'))),2)
        fixtures.add_row(self.f.record,'审阅记录',['R001','2026-11-08T12:00:00+08:00','[第1轮](<制作轮次.json#round-1>)','通过','无','隔离用户批准'])
        first_canvas=(self.project/'执行记录/E001/任务.workflow.json').read_bytes()
        second=[self.entry('E003',['P001'],'E001'),self.entry('E004',['P002'],'E002')]
        self.f.rounds([self.f.round(1,[('P001','E001'),('P002','E002')]),self.f.round(2,[('P001','E003'),('P002','E004')])])
        await self.enqueue(second,'二采');fixtures.check(self.project)
        self.assertEqual((self.project/'执行记录/E001/任务.workflow.json').read_bytes(),first_canvas)
        data=fixtures.state(self.project)
        second_task,_=fixtures.browser.task_for(self.project,data['executions']['E003'])
        first_task,_=fixtures.browser.task_for(self.project,data['executions']['E001'])
        first_request=recordio.read(self.project/'执行记录/E001/请求.json')['prompt']
        self.assertNotIn('343', first_request)
        self.assertNotIn('343', second_task['workflow'])
        self.assertEqual(second_task['workflow']['502'],first_request['502'])
        self.assertEqual(second_task['workflow']['407']['inputs']['width'],1920)
        self.assertEqual(first_task['workflow']['261'],second_task['workflow']['261'])
        second_id=next(k for k,r in self.store.rows.items() if Path(r['input'].record_dir).name=='E003')
        with patch.object(tasks.client.Client,'json',return_value={'can_confirm_refine':False}),patch.object(tasks.client,'submit',side_effect=AssertionError('must not generate')):
            with self.assertRaisesRegex(ValueError,'一采缓存缺失或不匹配'):await self.store.check_target_cache(second_id,second_task['workflow'])
        with patch.object(tasks.client.Client,'json',return_value={'can_confirm_refine':True}):await self.store.check_target_cache(second_id,second_task['workflow'])
        self.assertEqual(len(list((self.project/'资源/视频').glob('**/*.mp4'))),2)
        self.assertEqual(len(list((self.project/'执行记录').glob('*-装配结果.json'))),2)

    async def test_multi_segment_prompt_mapping_and_invalid_sections(self):
        entry=self.entry('E001',['P001','P002']);path=self.project/'执行记录/E001/提示词.md'
        result=await self.enqueue([entry],'一采')
        task,folder=fixtures.browser.task_for(self.project,fixtures.state(self.project)['executions']['E001'])
        key=result['tasks'][0]['local_task_id'];self.store.record(key,'submit','accepted',_changes={'prompt_id':'isolated','status':'queued'})
        recordio.write(folder/'请求.json',{'prompt':task['workflow']})
        self.assertTrue(recordio.read(folder/'后台任务状态.json').get('prompt_id'),recordio.read(folder/'后台任务状态.json'))
        self.assertTrue(recordio.exists(folder/'请求.json'))
        page=fixtures.browser.production_data(self.project,self.api,'V001')
        for part in page['segments']:
            context=part['videos'][0]['context']
            self.assertIn(part['id'],context['prompts']['english'],context)
            self.assertIn(part['id'],context['prompts']['chinese'])
            self.assertNotIn('P002' if part['id']=='P001' else 'P001',context['prompts']['chinese'])
        value=fixtures.state(self.project);row=value['executions']['E001'];mapping=prompt_sections(value,row)['中文提示词参考版']
        self.assertIn('共用说明',mapping['P001']);self.assertNotIn('P002',mapping['P001'])
        self.assertIn('P002',mapping['P002']);self.assertNotIn('P001',mapping['P002'])
        original=path.read_text()
        for malformed in [original.replace('### P002','### P001'),original.replace('### P002','### P003'),original.replace('### P001','### P002',1),original.replace('### P002\n\n此段中文 P002','### P002\n\n')]:
            path.write_text(malformed)
            with self.assertRaises(ValueError):fixtures.check(self.project)
        path.write_text(original);fixtures.check(self.project)

    async def test_manifest_selects_execution_directory_and_rejects_ambiguity(self):
        self.f.candidate('P001','E001',output=False)
        path=self.project/'执行记录/任务清单.json'
        row={**fixtures.state(self.project)['executions']['E001'],'参数记录':'[参数](<执行记录/任务清单.json>)'}
        first={'record_dir':'执行记录/E001','project':str(self.project),'uploads':[]}
        second={**first,'record_dir':'执行记录/E002'}
        path.write_text(json.dumps({'tasks':[second,first]}))
        self.assertEqual(fixtures.browser.task_for(self.project,row)[0],first)
        for entries in ([second],[first,first]):
            path.write_text(json.dumps({'tasks':entries}))
            with self.assertRaisesRegex(ValueError,'对应唯一任务'):fixtures.browser.task_for(self.project,row)

    async def test_songssx_whole_video_review_postprocess_and_handoff(self):
        project, fixture = self.project, self.f
        ids = ('P001', 'P002')
        slot = '整片视频'
        def declare(execution, stage, number, upstream='不适用', run='R001', *, local_result=False):
            folder = project / '执行记录' / execution
            folder.mkdir()
            prompt_link = '不适用'
            if stage == '场次生成':
                prompt = '\n\n'.join('## '+title+'\n\n'+'\n\n'.join(f'### {p}\n\n{body}' for p in ids)
                                     for title, body in [('模型提示词正文', PROMPT), ('中文提示词参考版', '隔离中文')])
                (folder / '提示词.md').write_text(prompt+'\n', encoding='utf-8')
                prompt_link = f'[提示词](<执行记录/{execution}/提示词.md>)'
            fixtures.add_row(fixture.record,'执行记录',[execution,'视频生成' if stage=='场次生成' else '视频处理',
                upstream,'隔离工作流',prompt_link,'不适用' if local_result else f'[参数](<执行记录/{stage}任务清单.json>)','隔离授权',
                '未取得','未取得','未取得','准备中','无'])
            for index, p in enumerate(ids):
                fixtures.add_row(fixture.record,'视频分段执行',[p,stage,run,execution,slot,str(index)])
            round_row = fixture.round(number, [(p, execution) for p in ids])
            for segment in round_row['segments']:
                segment['slot'] = slot
            return round_row, {'adapter':'chloe-video','document':'制作记录.md','execution':execution,
                               'round':number,'outputs':[{'slot':slot}]}

        async def collect(result, media):
            key = result['tasks'][0]['local_task_id']
            data = self.store.rows[key]['input']
            target, = data.outputs
            remote = {'filename':'isolated.mp4','subfolder':'video/test','type':'output'}
            def download(_, args):
                path = Path(args.output)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(media)
                return {'path':str(path),'bytes':len(media),'remote':remote}

            self.store.save(key, prompt_id='remote-'+Path(data.record_dir).name)
            recordio.write(Path(data.record_dir)/'请求.json', {'prompt':data.workflow})
            with patch.object(tasks.client,'download',side_effect=download):
                await self.store.finish_collection(key, {'state':'success','files':[{
                    'node_id':target.node_id,'output_key':target.output_key,'index':target.index,'file':remote}]})
            report = result_registration.register(self.store, key)
            self.assertEqual(report, result_registration.register(self.store, key))
            return report, Path(target.path)

        def media(name, size, duration):
            path = self.root / name
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=s={size}:r=24:d={duration}',
                            '-c:v','libx264','-pix_fmt','yuv420p',str(path)], check=True)
            return path.read_bytes()

        first, association = declare('E001','场次生成',1)
        fixture.rounds([first])
        scene_task = dict(task_type='video-scene-generation',title='隔离整片',authorization='隔离授权',
                          record_dir='执行记录/E001',output='候选/整片.mp4',video_plan={'business_result':association},
                          songssx={'width':736,'height':1280,'seed':7,'remote_prefix':'video/test/chloe',
                                   'configuration':{'high_steps':4,'scene_type':'dialogue','speed':None,'loras':[]},
                                   'segments':[{'p':p,'duration':duration,'overlap_frames':0,'images':[self.reference],
                                                'prompt':PROMPT,'prompt_zh':p+' 中文'} for p,duration in zip(ids,(5,4))]})
        accepted = await self.enqueue([scene_task], '场次生成')
        detail = lambda: fixtures.browser.detail(fixture.projects,project.name,fixture.api,'V001')
        self.assertFalse(detail()['sceneRounds']['whole'][0]['songssx']['video']['url'])
        duration = detail()['sceneRounds']['whole'][0]['songssx']['segments'][-1]['end']
        report, source = await collect(accepted, media('source.mp4','64x48',duration))
        self.assertTrue(report['business_sync']['round_ready'])
        self.assertFalse(report['business_sync']['adopted'])
        page = detail()
        self.assertEqual(page['productionWorkflows'], ['songssx'])
        scene = page['sceneRounds']['whole'][0]['songssx']
        self.assertTrue(scene['video']['url'])
        self.assertFalse(scene['video']['approved'])
        self.assertEqual([part['id'] for part in scene['segments']], list(ids))
        self.assertEqual(scene['segments'][1]['start'], scene['segments'][0]['end'])
        self.assertEqual(scene['segments'][1]['context']['prompts']['chinese'], 'P002 中文')
        self.assertIn('/production-files/',scene['segments'][0]['context']['references']['segment'][0]['url'])
        self.assertEqual([path for path,_ in songssx_round_videos(fixture.projects,project.name,page,1)], [source])
        note = ExportChanges.model_validate({'notes':[{'segment':'P002','stage':'场次生成','run':'R001',
            'roundNumber':1,'text':'第二段回看','fileRevision':scene['video']['fileRevision'],'expectedText':''}],
            'rounds':[]})
        fixtures.browser.validate_notes(project,'V001',{(1,'P002','场次生成','R001')},note)

        preview, _ = declare('E002','后处理',2,'E001',local_result=True)
        derived_path = self.root/'silent.mp4'
        derived_path.write_bytes(source.read_bytes())
        original_ref = fixtures.resources.reference(project, source)
        derived_ref = fixtures.resources.register(project, derived_path, key='silent',
            resource_id=original_ref['resource_id'], parent=source)
        derived = derived_ref['file']
        fixtures.add_row(fixture.record,'输出记录',['E002',slot,
            f'[本视频:{derived_ref["resource_id"]}@{derived_ref["version"]}](<{derived}>)'])
        preview['review_outputs'] = [{'label':'静音审阅版','file':derived,
            'playback':{'scene':'whole','run':'R001','stage':'后处理'}}]
        fixture.rounds([first,preview])
        self.assertEqual(detail()['sceneRounds']['whole'][1]['songssx']['video']['key'],derived)
        self.assertEqual([path for path,_ in songssx_round_videos(fixture.projects,project.name,detail(),2)],
                         [project/derived])

        second, processing = declare('E003','后处理',3,'E002','R002')
        fixture.rounds([first,preview,second])
        processing['adopt'] = {'document':'制作记录.md','review':'R001'}
        processing['outputs'][0].update(previous='无',expected={'width':128,'height':96,'frame_rate':24,
                                                                'duration':duration,'audio_tracks':0})
        post_task = dict(task_type='video-postprocess',title='隔离整片后处理',authorization='隔离授权',
                         record_dir='执行记录/E003',output_nodes=['16'],references=[{'file':derived,'placeholder':'planned/video.mp4'}],
                         video_postprocess={'source':derived,'resolution':[128,96],'fps':'original'},
                         outputs=[{'path':'候选/处理版.mp4','node_id':'16','output_key':'images','index':0,'response_name':'取回.json'}],
                         video_plan={'adapter':'technical','metadata':'ffprobe','business_result':processing})
        with self.assertRaisesRegex(ValueError,'审阅|批准'):
            await self.enqueue([post_task],'后处理')
        fixtures.add_row(fixture.record,'审阅记录',['R001','2026-11-08T12:00:00+08:00',
            '[第2轮](<制作轮次.json#round-2>)','通过','无','隔离用户批准'])
        accepted = await self.enqueue([post_task], '后处理')
        report, processed = await collect(accepted, media('processed.mp4','128x96',duration))
        self.assertTrue(report['business_sync']['adopted'])
        handoff = json.loads(Path(report['business_sync']['handoff']).read_text('utf-8'))
        self.assertEqual([project/item['file'] for item in handoff['media']], [processed])
        page = detail()
        after = page['sceneRounds']['whole'][2]['songssx']
        self.assertTrue(after['video']['approved'])
        self.assertEqual(after['video']['stage'], '后处理')
        self.assertEqual(after['segments'][1]['start'],scene['segments'][1]['start'])
        self.assertEqual([path for path,_ in songssx_round_videos(fixture.projects,project.name,page,3)], [processed])
        fixtures.check(project)
