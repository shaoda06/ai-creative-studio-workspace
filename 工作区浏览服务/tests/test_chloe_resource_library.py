from pathlib import Path
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from backend.chloe_resource_library import catalog, detail_data, library_file, router
from chloe_init import initialize_workspace, initialize_project, initialize_video, initialize_asset, SKILLS
sys.path.insert(0, str(SKILLS/'chloe-assets/scripts'))
from chloe_resources import import_media, bind_reference
import project_resources as resources


class ChloeResourceLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = initialize_project(initialize_workspace(self.base/'Chloe Workspace'), '隔离甲项目')
        self.video = initialize_video(self.root, 'V001', '隔离穿搭展示')
        self.asset = initialize_asset(self.root, '模特', 'M001', '隔离模特')
        self.api = '/api/workspaces/test/contexts/'+self.root.name
        first = self.base/'portrait.png'; Image.new('RGB', (30, 40), 'red').save(first)
        second = self.base/'portrait-upscaled.png'; Image.new('RGB', (60, 80), 'blue').save(second)
        self.first = import_media(self.root, first, 'original')
        self.second = import_media(self.root, second, 'process', resource_id=self.first['resource_id'], origin='process',
            record='共用素材/AI模特/M001-隔离模特/模特说明.md', parent=self.first['file'])
        self.local = import_media(self.root, first, 'local-shot', project=self.video.name)
        for key in ('shot/Picture1', 'other/Picture1'):
            bind_reference(self.root, self.video.name, key, self.first['resource_id'], self.first['version'])
        target = Path(self.first['absolute_file'])
        with (self.asset/'模特说明.md').open('a') as f:
            f.write('\n## 隔离引用\n[原图](<'+os.path.relpath(target,self.asset)+'>)\n')
        with (self.video/'脚本.md').open('a') as f:
            f.write('\n## 隔离引用\n[原图](<'+os.path.relpath(target,self.video)+'>)\n')
        samples = Path(__file__).parents[1]/'frontend/public/component-samples'
        for name in ('tone.wav', 'video.webm'):
            source = self.base/name; shutil.copyfile(samples/name,source)
            ref = import_media(self.root, source, name, project=None if name=='tone.wav' else self.video.name)
            if name=='tone.wav': self.audio=ref
            else: self.clip=ref
        self.voice=initialize_asset(self.root,'声音','A001','隔离声音')
        voice_doc=self.voice/'声音说明.md'
        ref=f"[共用:{self.audio['resource_id']}@{self.audio['version']}](<{os.path.relpath(self.audio['absolute_file'],self.voice)}>)"
        header='| 用途 | 资源引用 | 来源或原图引用 | 执行编号 |\n| --- | --- | --- | --- |'
        voice_doc.write_text(voice_doc.read_text().replace(header,header+f'\n| 声音参考 | {ref} | 原件 | 无 |\n| 声音原始参考 | {ref} | 用户上传 | 无 |'))
        shutil.copyfile(samples/'video.webm',self.video/'成片/人工成片.webm')
        (self.video/'剪辑交接/示例包.zip').write_bytes(b'not a media resource')
        self.space = SimpleNamespace(root=self.root,api=self.api,view='chloe-commerce')
        app = FastAPI()
        @app.middleware('http')
        async def scope(request, call_next):
            request.state.workspace_space = self.space
            return await call_next(request)
        app.include_router(router, prefix=self.api)
        self.client = TestClient(app)

    def label_visuals(self):
        doc=self.asset/'模特说明.md'
        header='| 用途 | 资源引用 | 来源或原图引用 | 执行编号 |\n| --- | --- | --- | --- |'
        rows=''.join(f"\n| 正面面部 | [共用:{ref['resource_id']}@{ref['version']}](<{os.path.relpath(ref['absolute_file'],self.asset)}>) | 用户上传 | 无 |" for ref in (self.first,self.second))
        doc.write_text(doc.read_text().replace(header,header+rows))
        self.label_clip(self.clip,'E001','一采')

    def label_clip(self, ref, execution, stage):
        doc=self.video/'制作记录.md'
        stages='| 分段编号 | 制作阶段 | 候选版本 | 执行编号 | 输出槽位 | 模型分段序号 |\n| --- | --- | --- | --- | --- | --- |'
        outputs='| 执行编号 | 输出槽位 | 资源引用 |\n| --- | --- | --- |'
        link=f"[本视频:{ref['resource_id']}@{ref['version']}](<{os.path.relpath(ref['absolute_file'],self.video)}>)"
        doc.write_text(doc.read_text().replace(stages,stages+f'\n| P001 | {stage} | R001 | {execution} | P001视频 | 0 |')
            .replace(outputs,outputs+f'\n| {execution} | P001视频 | {link} |'))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_catalog_is_readonly_unique_versions_and_excludes_deliverables(self):
        before = self.snapshot()
        response = self.client.get(self.api+'/resource-library')
        self.assertEqual(response.status_code,200)
        listing = response.json()
        self.assertEqual(listing['total'],5)
        self.assertEqual(len({v['key'] for v in listing['items']}),5)
        self.assertNotIn('人工成片',json.dumps(listing,ensure_ascii=False))
        for entry in listing['items']:
            detail = self.client.get(self.api+'/resource-library/detail',params={k:entry[k] for k in ('owner','resource_id','version')})
            self.assertEqual(detail.status_code,200)
        self.assertEqual(self.snapshot(),before)

    def test_filters_pagination_and_registered_order(self):
        for index, ref in enumerate((self.first,self.second,self.local)):
            path = Path(ref['absolute_file']).with_name('版本信息.json');data=json.loads(path.read_text())
            data['registered_at']=f'2030-01-0{index+1}T10:00:00+08:00';resources.write_json(path,data)
        listing = self.client.get(self.api+'/resource-library',params={'kind':'图片','page_size':2}).json()
        self.assertEqual(listing['total'],3)
        self.assertEqual([v['file'] for v in listing['items']],[str(Path(self.local['absolute_file']).relative_to(self.root)),str(Path(self.second['absolute_file']).relative_to(self.root))])
        last = self.client.get(self.api+'/resource-library',params={'kind':'图片','page_size':2,'page':99}).json()
        self.assertEqual(last['page'],2);self.assertEqual(len(last['items']),1)
        filtered=self.client.get(self.api+'/resource-library',params={'owner':'综合资料','q':'UPSCALED'}).json()
        self.assertEqual(filtered['total'],1);self.assertEqual(filtered['items'][0]['facts']['width'],60)
        self.assertEqual(self.client.get(self.api+'/resource-library',params={'q':'no matches'}).json()['total'],0)

    def test_exact_lineage_and_shared_references(self):
        data=detail_data(self.root,self.api,'综合资料',self.second['resource_id'],self.second['version'])
        self.assertEqual([v['version'] for v in data['versions']],['V002','V001'])
        self.assertEqual(data['parent_entry']['version'],'V001')
        self.assertEqual(data['producer_file'],'综合资料/共用素材/AI模特/M001-隔离模特/模特说明.md')
        first=detail_data(self.root,self.api,'综合资料',self.first['resource_id'],'V001')
        self.assertEqual(len(first['uses']),4)
        self.assertTrue(any('model=M001' in (u['to'] or '') for u in first['uses']))
        self.assertTrue(any('video=' in (u['to'] or '') for u in first['uses']))
        for use in first['uses']:
            self.assertEqual(self.client.get(self.api+'/resource-library/document',params={'path':use['path']}).status_code,200)

    def test_file_scope_missing_and_other_workspace(self):
        listing = self.client.get(self.api+'/resource-library').json()
        entry=next(v for v in listing['items'] if v['owner']=='综合资料')
        response=self.client.get(entry['media']['url'],params={'download':'true'})
        self.assertEqual(response.status_code,200)
        self.assertIn('attachment',response.headers['content-disposition'])
        self.assertEqual(response.content,(self.root/entry['file']).read_bytes())
        for key in ('../别的项目/README.md','/etc/passwd','.private.md',self.video.relative_to(self.root).as_posix()+'/成片/人工成片.webm'):
            self.assertEqual(self.client.get(self.api+'/resource-library/document',params={'path':key}).status_code,404)
        external=self.base/'secret.md';external.write_text('private')
        link=self.asset/'外部.md';link.symlink_to(external)
        with self.assertRaises(HTTPException) as caught:
            library_file(self.root,link.relative_to(self.root).as_posix())
        self.assertEqual(caught.exception.status_code,404)
        self.assertEqual(self.client.get(entry['media']['url']).status_code,200)

    def test_execution_directory_opens_original_archive_and_missing_is_explicit(self):
        record=self.asset/'E001';record.mkdir()
        archive=record/'执行档案.json';archive.write_text('{"execution":"E001"}')
        meta=Path(self.second['absolute_file']).with_name('版本信息.json')
        data=json.loads(meta.read_text());data['producer']=record.relative_to(self.root/'综合资料').as_posix()
        resources.write_json(meta,data)
        detail=detail_data(self.root,self.api,'综合资料',self.second['resource_id'],self.second['version'])
        self.assertEqual(detail['producer_path'],record.relative_to(self.root).as_posix())
        self.assertEqual(detail['producer_file'],archive.relative_to(self.root).as_posix())
        self.assertEqual(self.client.get(self.api+'/resource-library/document',params={'path':detail['producer_file']}).status_code,200)
        archive.unlink()
        detail=detail_data(self.root,self.api,'综合资料',self.second['resource_id'],self.second['version'])
        self.assertIsNone(detail['producer_file'])
        self.assertIsNotNone(detail['producer_path'])

    def test_unknown_version_and_workspace_rejected(self):
        params={'owner':'../别的项目','resource_id':self.first['resource_id'],'version':'V001'}
        self.assertEqual(self.client.get(self.api+'/resource-library/detail',params=params).status_code,404)
        self.assertEqual(self.client.post(self.api+'/resource-library',json={}).status_code,405)
        self.space.view='serial-drama'
        self.assertEqual(self.client.get(self.api+'/resource-library').status_code,404)

    def test_audio_title_uses_exact_voice_role_without_renaming_file(self):
        before=self.snapshot()
        entry=next(v for v in catalog(self.root,self.api)[0] if v['kind']=='音频')
        self.assertEqual(entry['display_name'],'隔离声音 · 原始参考')
        self.assertEqual(entry['name'],'tone.wav')
        self.assertEqual(entry['media']['name'],'tone.wav')
        self.assertEqual(self.snapshot(),before)
        doc=self.voice/'声音说明.md'
        doc.write_text(doc.read_text().replace('声音原始参考','声音参考'))
        entry=next(v for v in catalog(self.root,self.api)[0] if v['kind']=='音频')
        self.assertEqual(entry['display_name'],'隔离声音 · 声音参考')
        newer=import_media(self.root,self.base/'tone.wav','tone-version-2',resource_id=self.audio['resource_id'])
        doc.write_text(doc.read_text().replace('@V001','@V002').replace(
            os.path.relpath(self.audio['absolute_file'],self.voice),os.path.relpath(newer['absolute_file'],self.voice)))
        entry=next(v for v in catalog(self.root,self.api)[0] if v['kind']=='音频' and v['version']=='V001')
        self.assertEqual(entry['display_name'],entry['title'])

    def test_missing_file_remains_recorded(self):
        path=Path(self.first['absolute_file']);path.unlink()
        entry=next(v for v in catalog(self.root,self.api)[0] if v['owner']=='综合资料' and v['resource_id']==self.first['resource_id'] and v['version']=='V001')
        self.assertIsNone(entry['media'])

    def test_visual_titles_follow_assets_and_exact_output_stage(self):
        self.label_visuals()
        newer=import_media(self.root,self.base/'video.webm','processed-clip',resource_id=self.clip['resource_id'],project=self.video.name)
        self.label_clip(newer,'E002','后处理')
        before=self.snapshot()
        items=catalog(self.root,self.api)[0]
        pictures=[v for v in items if v['resource_id']==self.first['resource_id']]
        self.assertEqual([v['display_name'] for v in pictures],['隔离模特 · 正面面部']*2)
        clips={v['version']:v for v in items if v['resource_id']==self.clip['resource_id']}
        self.assertEqual(clips['V001']['display_name'],'隔离穿搭展示 · P001 · 一采')
        self.assertEqual(clips['V002']['display_name'],'隔离穿搭展示 · P001 · 后处理')
        self.assertEqual(clips['V001']['name'],'video.webm')
        self.assertEqual(self.snapshot(),before)

    def test_dedicated_picture_title_reads_existing_generation_purpose(self):
        producer=self.video/'执行记录/图片参数.json'
        producer.write_text(json.dumps({'purpose':'P001全身开场参考图'}))
        meta=Path(self.local['absolute_file']).with_name('版本信息.json')
        data=json.loads(meta.read_text());data['producer']=producer.relative_to(self.video).as_posix()
        resources.write_json(meta,data)
        entry=next(v for v in catalog(self.root,self.api)[0] if v['resource_id']==self.local['resource_id'])
        self.assertEqual(entry['display_name'],'隔离穿搭展示 · P001全身开场参考图')
        self.assertEqual(entry['name'],'portrait.png')
