"""Result completion uses isolated records and media; no live tasks or generation."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image
from tests import test_chloe_production as fixtures
from chloe_init import initialize_asset
from backend.services import business_results
import sys
sys.path.insert(0,str(business_results.SKILLS/'chloe-assets/scripts'))
import chloe_result_records as records
sys.path.insert(0,str(business_results.SKILLS/'chloe-production/scripts'))
import chloe_results
sys.path.insert(0,str(business_results.SKILLS/'chloe-creative/scripts'))
from chloe_director_sheet import prepare
from chloe_resources import bind_reference
import chloe_browser_production as browser
from chloe_production import state

TIME='2026-11-08T20:00:00+08:00'

class ResultCompletionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ChloeProductionTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.owner=self.f.root/'综合资料'
        self.asset=initialize_asset(self.f.root,'模特','M001','隔离模特')

    def image_execution(self,execution='E001',process=False):
        document=self.asset/'模特说明.md'
        fixtures.add_row(document,'执行记录',[execution,'图片处理' if process else '图片生成',
            'E001' if process else '不适用','RTX' if process else 'Imagegen','不适用','不适用','用户授权',
            '未取得','未取得','未取得','准备中','无'])
        return document

    def image(self,key,size=(12,16),resource_id=None):
        source=Path(self.f.temp.name)/(key+'.png');Image.new('RGB',size,'white').save(source)
        ref=records.resources.register(self.owner,source,key=key,resource_id=resource_id)
        return source,ref

    def image_plan(self,doc,execution):
        return {'adapter':'chloe-image','document':str(doc.relative_to(self.owner)),
                'execution':execution,'outputs':[{'slot':'正面面部','purpose':'正面面部','source':None}]}

    def report(self,owner,ref,execution):
        path=owner/(execution+'-报告.json')
        report={'task_id':'task-'+execution,'recorded_at':TIME,'items':[{'path':ref['file'],'width':12,'height':16}]}
        path.write_text(json.dumps(report));return report,path

    def test_native_candidate_and_retry_do_not_adopt_or_copy_again(self):
        doc=self.image_execution(); plan=self.image_plan(doc,'E001')
        source=Path(self.f.temp.name)/'native.png';Image.new('RGB',(12,16),'white').save(source)
        manifest=self.asset/'E001-参数.json'
        manifest.write_text(json.dumps({'task_id':'native-E001','business_result':plan}))
        result=records.native(self.f.root,manifest,source)
        self.assertFalse(result['adopted'])
        before=doc.read_bytes(); index=(self.owner/'资源/索引.json')
        files=list((self.owner/'资源/图片').rglob('*.png'))
        records.native(self.f.root,manifest,source)
        self.assertEqual(before,doc.read_bytes());self.assertEqual(files,list((self.owner/'资源/图片').rglob('*.png')))
        self.assertEqual(records.rows(doc.read_text(),'当前采用'),[])
        self.assertTrue(source.exists())

    def director_brief(self):
        self.f.plan()
        script = self.f.project/'脚本.md'
        script.write_text(script.read_text('utf-8').replace('| 画幅 | 待确定 |','| 画幅 | 9:16 |'), encoding='utf-8')
        _, _, ref = self.f.resource(kind='image', shared=True, key='look')
        bind_reference(self.f.root, self.f.project.name, 'look', ref['resource_id'], ref['version'])
        return {'shots': [{'shot': shot, 'sketch': '人物转身', 'action': '面向镜头'}
                          for shot in ('SH001', 'SH002')],
                'references': [{'slot': '造型', 'key': 'look'}]}

    def test_prepare_director_sheet_rejects_used_and_pending_versions(self):
        brief = self.director_brief()
        project = self.f.project
        script = project/'脚本.md'
        script.write_text(script.read_text('utf-8').replace('| 脚本版本 | v01 |', '| 脚本版本 | v09 |'), encoding='utf-8')
        fixtures.add_row(self.f.record, '执行记录', ['E001','图片生成','不适用','Imagegen','不适用',
            '不适用','用户授权','未取得','未取得','未取得','已完成','无'])
        _, reference, _ = self.f.resource(kind='image')
        fixtures.add_row(self.f.record, '输出记录', ['E001','导演表/脚本v08/图表v01/候选1/第1页',reference])
        before = self.f.record.read_bytes()
        with self.assertRaisesRegex(ValueError, '已使用或已预留：v01'):
            prepare(project, '脚本.md', brief, '用户授权', chart_version='v01')
        self.assertEqual(self.f.record.read_bytes(), before)
        self.assertEqual(list((project/'执行记录').iterdir()), [])
        first = prepare(project, '脚本.md', brief, '用户授权')
        self.assertEqual((first['source_version'], first['chart_version'], first['candidate']), ('v09','v02',1))
        with self.assertRaisesRegex(ValueError, '已使用或已预留：v02'):
            prepare(project, '脚本.md', brief, '用户授权', chart_version='v02')
        second = prepare(project, '脚本.md', brief, '用户授权')
        self.assertEqual((second['chart_version'], second['candidate']), ('v03',2))

    def test_prepare_director_pages_match_registered_output(self):
        brief = self.director_brief()
        project = self.f.project
        result = prepare(project, '脚本.md', brief, '用户授权', page_size=1)
        self.assertEqual((result['source_version'],result['chart_version'],result['candidate']), ('v01','v01',1))
        plan = json.loads(Path(result['plan']).read_text('utf-8'))
        self.assertEqual(plan['shot_ids'], ['SH001','SH002'])
        before = (project/'README.md').read_bytes()
        for n, page in enumerate(result['pages'], 1):
            manifest = Path(page['manifest'])
            params = json.loads(manifest.read_text('utf-8'))
            slot = f'导演表/脚本v01/图表v01/候选1/第{n}页'
            self.assertEqual(params['business_result']['outputs'][0]['slot'], slot)
            self.assertEqual((manifest.parent/params['plan']).resolve(), Path(result['plan']))
            prompt = (manifest.parent/params['prompt_file']).read_text('utf-8')
            self.assertIn(f'来源分镜版本：v01｜图表 v01｜第{n}／2张｜镜号范围：SH{n:03d}', prompt)
            self.assertIn('手绘导演分镜表', prompt)
            self.assertIn('每格画幅 9:16', prompt)
            self.assertEqual(len(params['references']), 1)
            self.assertIn('referenced_image_paths', page['call'])
            source = Path(self.f.temp.name)/f'native-page{n}.png'
            Image.new('RGB',(12,16),'white').save(source)
            saved = records.native(self.f.root, manifest, source)
            self.assertEqual(Path(saved['images'][0]['file']).read_bytes(), source.read_bytes())
            records.native(self.f.root, manifest, source)
        sheets = browser.director_sheets(state(project), self.f.api)
        self.assertEqual([(row['version'],row['page'],row['adopted']) for row in sheets['candidates']],
                         [('v01',1,False),('v01',2,False)])
        self.assertEqual((project/'README.md').read_bytes(), before)

    def test_native_rejects_director_slot_collision_before_import(self):
        brief = self.director_brief()
        project = self.f.project
        result = prepare(project, '脚本.md', brief, '用户授权')
        manifest = Path(result['pages'][0]['manifest'])
        fixtures.add_row(self.f.record, '执行记录', ['E002','图片生成','不适用','Imagegen','不适用',
            '不适用','用户授权','未取得','未取得','未取得','已完成','无'])
        _, reference, _ = self.f.resource(kind='image')
        fixtures.add_row(self.f.record, '输出记录', ['E002','导演表/脚本v08/图表v01/候选1/第1页',reference])
        source = Path(self.f.temp.name)/'native-page.png'
        Image.new('RGB',(12,16),'white').save(source)
        before = self.f.record.read_bytes()
        images = list((project/'资源/图片').rglob('*.png'))
        with self.assertRaisesRegex(ValueError, '同一图表版本不能混用'):
            records.native(self.f.root, manifest, source)
        self.assertEqual(self.f.record.read_bytes(), before)
        self.assertEqual(list((project/'资源/图片').rglob('*.png')), images)

    def test_prepared_director_rejects_missing_frame_and_wrong_execution_page(self):
        brief = self.director_brief()
        project = self.f.project
        script = project/'脚本.md'
        ready = script.read_text('utf-8')
        script.write_text(ready.replace('| 画幅 | 9:16 |','| 画幅 | 待确定 |'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '须填写实际画幅'):
            prepare(project, '脚本.md', brief, '用户授权')
        self.assertFalse(list((project/'执行记录').iterdir()))
        script.write_text(ready, encoding='utf-8')
        result = prepare(project, '脚本.md', brief, '用户授权', page_size=1)
        manifest = Path(result['pages'][0]['manifest'])
        params = json.loads(manifest.read_text('utf-8'))
        output = params['business_result']['outputs'][0]
        slot = output['slot']
        source = Path(self.f.temp.name)/'wrong-page.png'
        Image.new('RGB',(12,16),'white').save(source)
        before = self.f.record.read_bytes()
        for changed in (slot.replace('图表v01','图表v02'), slot.replace('第1页','第2页'), '普通图片'):
            with self.subTest(slot=changed):
                output['slot'] = changed
                manifest.write_text(json.dumps(params), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, '计划页不一致'):
                    records.native(self.f.root, manifest, source)
        self.assertEqual(self.f.record.read_bytes(), before)
        self.assertFalse(list((project/'资源/图片').rglob('*.png')))

    def test_upscale_adopts_once_and_preserves_prior_versions(self):
        doc=self.image_execution();_,first=self.image('first')
        report,path=self.report(self.owner,first,'E001');records.finish(self.owner,self.image_plan(doc,'E001'),report,path)
        old=records.resource(self.owner,doc,first['file'])
        forward=old.replace('\\','/')
        backward=forward.replace('/','\\')
        fixtures.add_row(doc,'审阅记录',['R001',TIME,forward,'通过','无','用户批准'])
        self.image_execution('E002',True)
        fixtures.add_row(doc,'输入记录',['E002','原图','不适用',backward])
        _,second=self.image('second',(24,32),first['resource_id'])
        plan=self.image_plan(doc,'E002');plan['outputs'][0].update(source=first['file'],previous='无')
        plan['adopt']={'document':str(doc.relative_to(self.owner)),'review':'R001'}
        report,path=self.report(self.owner,second,'E002')
        result=records.finish(self.owner,plan,report,path);self.assertTrue(result['adopted'])
        before=doc.read_bytes();records.finish(self.owner,plan,report,path);self.assertEqual(before,doc.read_bytes())
        self.assertEqual(len(records.rows(doc.read_text(),'采用变更')),1)
        self.assertEqual(len(list((self.owner/'资源/图片').rglob('*.png'))),2)
        doc.write_text(doc.read_text().replace('| 通过 |','| 需修改 |'))
        with self.assertRaisesRegex(ValueError,'已通过'): records.finish(self.owner,plan,report,path)

    def test_upscale_rejects_wrong_version_before_submission(self):
        doc = self.image_execution('E002', True)
        _, wrong = self.image('prior')
        _, approved = self.image('approved', resource_id=wrong['resource_id'])
        reviewed = records.resource(self.owner, doc, approved['file'])
        fixtures.add_row(doc, '审阅记录', ['R001', TIME, reviewed, '通过', '无', '用户批准'])
        fixtures.add_row(doc, '输入记录', ['E002', '2/image', '不适用', reviewed])
        plan = self.image_plan(doc, 'E002')
        plan['outputs'][0].update(source=approved['file'], previous='无')
        plan['adopt'] = {'document': str(doc.relative_to(self.owner)), 'review': 'R001'}
        upload = {'node': '2', 'input': 'image', 'file': str(self.owner/approved['file'])}
        target = SimpleNamespace(base_file=approved['file'])
        data = SimpleNamespace(task_type='image-upscale', project=str(self.owner), segment_plan=None,
                               image_plan={'adapter': 'technical', 'business_result': plan},
                               outputs=[target], uploads=[upload])
        before = doc.read_bytes()
        business_results.validate(data)
        self.assertEqual(doc.read_bytes(), before)
        plan['outputs'][0]['source'] = wrong['file']
        with self.assertRaisesRegex(ValueError, '批准对象必须'):
            business_results.validate(data)
        plan['outputs'][0]['source'] = approved['file']
        upload['file'] = str(self.owner/wrong['file'])
        with self.assertRaisesRegex(ValueError, '实际上传必须'):
            business_results.validate(data)
        upload['file'] = str(self.owner/approved['file'])
        target.base_file = wrong['file']
        with self.assertRaisesRegex(ValueError, '结果的来源版本必须'):
            business_results.validate(data)
        target.base_file = approved['file']
        from backend.services import execution_checks
        document = doc.read_text('utf-8')
        data.record_dir = str(doc.parent)
        data.record_format = 'legacy'
        data.title = '隔离超分'
        store = SimpleNamespace(client=SimpleNamespace(now=lambda: TIME, ClientError=RuntimeError),
                                portable_input=lambda task: {'title': task.title})
        prepared = {'ok': True, 'prepared_input': execution_checks.basis(store, data),
                    'sources': execution_checks.sources(data), 'new_task_ready': True, 'segments': {}}
        self.assertTrue(execution_checks.prepare_report(store, data, previous=prepared)['reused'])
        other = records.resource(self.owner, doc, wrong['file'])
        doc.write_text(document.replace(f'| 2/image | 不适用 | {reviewed} |',
                                        f'| 2/image | 不适用 | {other} |'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '处理来源未登记'):
            execution_checks.prepare_report(store, data, previous=prepared)
        self.assertFalse(records.rows(doc.read_text('utf-8'), '当前采用'))

    def video_entry(self,identity,execution,stage,upstream=None):
        self.f.candidate(identity,execution,stage=stage,output=False)
        folder=self.f.project/'执行记录'/execution;folder.mkdir()
        (folder/'提示词.md').write_text('## 模型提示词正文\n\nShow the outfit.\n\n## 中文提示词参考版\n\n展示搭配。\n')
        body=self.f.record.read_text()
        body=records.put(body,'执行记录',['执行编号'],{'执行编号':execution,'上游执行':upstream or '不适用',
            '提示词或正文':f'[提示词](<执行记录/{execution}/提示词.md>)'},replace=True)
        records.save(self.f.record,body)
        _,_,ref=self.f.resource(key=execution)
        return ref

    def video_plan(self,execution,identity,number):
        return {'adapter':'chloe-video','document':'制作记录.md','execution':execution,'round':number,'outputs':[{'slot':identity+'视频'}]}

    def video_finish(self,plan,ref,metadata=None):
        report,path=self.report(self.f.project,ref,plan['execution'])
        if metadata is not None: report['items'][0]['metadata']=metadata
        path.write_text(json.dumps(report))
        return chloe_results.finish(self.f.project,plan,report,path)

    def test_whole_round_waits_and_postprocess_handoff_is_idempotent(self):
        f=self.f;f.plan()
        first=[self.video_entry(p,e,'一采') for p,e in [('P001','E001'),('P002','E002')]]
        f.rounds([f.round(1,[('P001','E001'),('P002','E002')])])
        self.assertFalse(self.video_finish(self.video_plan('E001','P001',1),first[0])['round_ready'])
        self.assertTrue(self.video_finish(self.video_plan('E002','P002',1),first[1])['round_ready'])
        self.assertEqual(records.rows((f.project/'README.md').read_text(),'当前采用'),[])
        second=[self.video_entry(p,e,'二采',up) for p,e,up in [('P001','E003','E001'),('P002','E004','E002')]]
        rounds=json.loads((f.project/'制作轮次.json').read_text())['rounds'];rounds.append(f.round(2,[('P001','E003'),('P002','E004')]))
        f.rounds(rounds)
        for p,e,ref in zip(['P001','P002'],['E003','E004'],second):self.video_finish(self.video_plan(e,p,2),ref)
        fixtures.add_row(f.record,'审阅记录',['R001',TIME,'[第2轮](<制作轮次.json#round-2>)','通过','无','用户批准'])
        post=[self.video_entry(p,e,'后处理',up) for p,e,up in [('P001','E005','E003'),('P002','E006','E004')]]
        rounds.append(f.round(3,[('P001','E005'),('P002','E006')]))
        f.rounds(rounds)
        plans=[]
        for p,e,ref in zip(['P001','P002'],['E005','E006'],post):
            plan=self.video_plan(e,p,3);plan['adopt']={'document':'制作记录.md','review':'R001'}
            plan['outputs'][0]['previous']='无'
            plan['outputs'][0]['expected']={'width':1080,'height':1920,'frame_rate':30,'duration':5,'audio_tracks':0}
            actual={'width':1080,'height':1920,'frame_rate':30,'duration':5,'audio':[]}
            for change in ({'width':999},{'frame_rate':24},{'duration':8},{'audio':[{}]}):
                with self.assertRaises(ValueError):self.video_finish(plan,ref,{**actual,**change})
            result=self.video_finish(plan,ref,actual);plans.append((plan,ref))
        self.assertTrue(result['adopted']);self.assertIsNotNone(result['handoff'])
        readme=f.project/'README.md'
        progress={row['字段']:row['内容'] for row in records.rows(readme.read_text('utf-8'),'定位与当前进度')}
        self.assertEqual(progress['当前阶段'],'视频制作')
        self.assertEqual(progress['下一步'],'交付已采用视频')
        self.assertEqual(result['next_action'],progress['下一步'])
        before=readme.read_bytes()
        self.video_finish(*plans[-1],actual)
        self.assertEqual(before,readme.read_bytes())
        self.assertEqual(len(records.rows((f.project/'README.md').read_text('utf-8'),'剪映交接')),1)
        self.assertEqual(len(json.loads(Path(result['handoff']).read_text())['media']),2)
        self.assertEqual(len(list((f.project/'资源/视频').rglob('*.mp4'))),6)
        # Late historical completion cannot turn the latest progress back to review.
        result=self.video_finish(self.video_plan('E001','P001',1),first[0]);self.assertTrue(result['historical'])
        self.assertEqual(before,readme.read_bytes())

        # A later retry must preserve an actual manual editing stage.
        body=readme.read_text('utf-8')
        for key, value in {'当前阶段':'人工后期','下一步':'用户剪辑'}.items():
            body=records.put(body,'定位与当前进度',['字段'],{'字段':key,'内容':value},replace=True)
        records.save(readme,body)
        before=readme.read_bytes()
        self.assertEqual(self.video_finish(*plans[-1],actual)['next_action'],'用户剪辑')
        self.assertEqual(before,readme.read_bytes())

    def test_common_dispatch_is_opt_in_and_report_is_reused(self):
        for adapter in ('technical','serial-drama'):
            data=SimpleNamespace(task_type='video-first-pass',video_plan={'adapter':adapter})
            self.assertEqual(business_results.selected(data),(None,None))
        doc=self.image_execution();_,ref=self.image('shared')
        plan=self.image_plan(doc,'E001');report,path=self.report(self.owner,ref,'E001')
        path=path.rename(path.parent/'结果收尾报告.json')
        report['items'][0]['image']=True
        data=SimpleNamespace(task_type='image',image_plan={'adapter':'technical','business_result':plan},project=str(self.owner),segment_plan=None,outputs=[SimpleNamespace(path=str(self.owner/ref['file']))])
        business_results.finish(data,report,path)
        with patch.object(records,'finish',side_effect=AssertionError('must reuse')):
            business_results.finish(data,report,path)

    def test_interrupted_image_adoption_resumes_without_duplicate_output(self):
        doc=self.image_execution();_,ref=self.image('resume')
        plan=self.image_plan(doc,'E001');report,path=self.report(self.owner,ref,'E001')
        original=records.docs.check_workspace
        with patch.object(records.docs,'check_workspace',side_effect=OSError('interrupted validation')):
            with self.assertRaises(OSError):records.finish(self.owner,plan,report,path)
        with patch.object(records.docs,'check_workspace',wraps=original):
            records.finish(self.owner,plan,report,path)
        self.assertEqual(len(records.rows(doc.read_text(),'输出记录')),1)
        self.assertEqual(len(records.rows(doc.read_text(),'参考版本')),1)

    def test_out_of_order_results_are_bound_to_declared_targets(self):
        doc=self.image_execution();_,a=self.image('a');_,b=self.image('b')
        plan=self.image_plan(doc,'E001')
        plan['outputs'].append({'slot':'全身三视图','purpose':'全身三视图原图','source':None})
        report,path=self.report(self.owner,a,'E001')
        report['items'].insert(0,{'path':b['file'],'width':12,'height':16})
        data=SimpleNamespace(task_type='image',image_plan={'adapter':'technical','business_result':plan},project=str(self.owner),
            segment_plan=None,outputs=[SimpleNamespace(path=str(self.owner/r['file'])) for r in (a,b)])
        business_results.finish(data,report,path)
        output=records.rows(doc.read_text(),'输出记录')
        self.assertIn(a['resource_id'],output[0]['资源引用'])
        self.assertIn(b['resource_id'],output[1]['资源引用'])

    def test_backend_closeout_persists_business_summary_and_reuses_it(self):
        import asyncio
        from backend.services import result_registration, image_tasks, result_summary
        from unittest.mock import Mock
        doc=self.image_execution();_,ref=self.image('backend')
        plan=self.image_plan(doc,'E001');report,path=self.report(self.owner,ref,'E001')
        path=path.rename(path.parent/'结果收尾报告.json')
        report['items'][0]['image']=True
        data=SimpleNamespace(task_type='image',image_plan={'adapter':'technical','business_result':plan},
            project=str(self.owner),record_dir=str(path.parent),segment_plan=None,
            outputs=[SimpleNamespace(path=str(self.owner/ref['file']))])
        state={'id':report['task_id'],'project':'isolated::@shared','status':'completed','collected':1,'expected':1}
        store=SimpleNamespace(rows={report['task_id']:{'input':data,'state':state}},
            client=SimpleNamespace(now=lambda:TIME),refresh_reports=Mock(),wake_group=Mock())
        def record(key,*args,_changes,**kwargs):state.update(_changes)
        store.record=record
        with patch.object(image_tasks,'register',return_value=report),patch.object(result_registration,'collected_outputs',return_value=[]):
            first=asyncio.run(result_registration.closeout_tasks(store,None,[report['task_id']]))
            self.assertTrue(first['user_message_ready'],first)
            with patch.object(records,'finish',side_effect=AssertionError('duplicate write')):
                second=asyncio.run(result_registration.closeout_tasks(store,None,[report['task_id']]))
        self.assertTrue(first['user_message_ready']);self.assertTrue(second['user_message_ready'])
        self.assertEqual(state['closeout']['business_sync']['next_action'],'用户审阅图片')
        self.assertEqual(len(records.rows(doc.read_text(),'输出记录')),1)

    def test_compact_report_links_original_archive_without_materializing_report(self):
        import execution_records as recordio
        doc=self.image_execution();_,ref=self.image('compact')
        report,path=self.report(self.owner,ref,'E001')
        path.unlink();recordio.write(path,report,compact=True)
        self.assertFalse(path.exists())
        result=records.finish(self.owner,self.image_plan(doc,'E001'),report,path)
        self.assertEqual(result['status'],'updated')
        self.assertIn('执行档案.json',records.rows(doc.read_text(),'执行记录')[0]['结果说明'])
        self.assertFalse(path.exists())
        self.assertTrue((path.parent/'执行档案.json').is_file())
