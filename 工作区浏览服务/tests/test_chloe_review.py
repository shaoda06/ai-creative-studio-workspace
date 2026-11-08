from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.chloe_review import overview, review, router
from chloe_init import initialize_workspace, initialize_project, initialize_video
from tests import test_chloe_publication as publication_tests


class ChloeReviewTests(unittest.TestCase):
    append = publication_tests.ChloePublicationTests.append

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = initialize_project(initialize_workspace(self.base/'Chloe Workspace'), '隔离复盘')
        self.project = initialize_video(self.root, 'V001', '开场展示')
        self.api = '/api/workspaces/chloe'
        self.space = SimpleNamespace(root=self.root, api=self.api, view='chloe-commerce')
        app = FastAPI()
        @app.middleware('http')
        async def workspace(request, call_next):
            request.state.workspace_space = self.space
            return await call_next(request)
        app.include_router(router, prefix=self.api)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def prepare(self):
        from media_files import store_media
        film = self.project/'成片/分析版本.webm'
        store_media(self.project, film, source=Path(__file__).parents[1]/'frontend/public/component-samples/video.webm')
        evidence = self.project/'执行记录/原始数据.txt'
        evidence.write_text('平台原始证据')
        from PIL import Image
        from chloe_resources import import_media
        cover_path=self.base/'封面.png';Image.new('RGB',(90,120),'teal').save(cover_path)
        cover=import_media(self.root,cover_path,'review-cover',project=self.project.name)
        readme = self.project/'README.md'
        self.append(readme,'当前采用',['封面/抖音/竖版',f'[本视频:{cover["resource_id"]}@{cover["version"]}](<{Path(cover["absolute_file"]).relative_to(self.project).as_posix()}>)','用户采用','2026-11-01T09:00:00+08:00'])
        readme.write_text(readme.read_text().replace('| 视频状态 | 制作中 |', '| 视频状态 | 已发布 |'))
        self.append(readme, '发布记录', ['P001','[成片](<成片/分析版本.webm>)','未取得','未取得','未取得','未取得','不适用','不适用','未取得','2026-11-01T10:00:00+08:00','立即发布','已发布','example1','https://example.com/post','用户已发布','[证据](<执行记录/原始数据.txt>)'])
        for batch, date, metric, value in [('D001','02','播放量','100'),('D001','02','商品点击','6'),('D002','03','播放量','250')]:
            self.append(readme,'效果数据',[batch,'P001',f'2026-11-{date}T10:00:00+08:00','2026-11-01T10:00:00+08:00',f'2026-11-{date}T10:00:00+08:00',metric,value,'次','平台原口径','[原数据](<执行记录/原始数据.txt>)'])
        self.append(readme,'单条复盘',['R001','D001','[成片](<成片/分析版本.webm>)开场展示偏晚','暂不能判断收益','样本有限','将产品展示提前到开场，参见[调整目标](<脚本.md>)'])
        self.append(readme,'单条复盘',['R002','不适用','[成片](<成片/分析版本.webm>)仅核对画面','不适用','没有效果判断','保留细节展示'])
        report = self.root/'综合资料/运营复盘.md'
        self.append(report,'跨视频结论',['R001','2026-11-04T10:00:00+08:00','2026-11-01T10:00:00+08:00','2026-11-03T10:00:00+08:00','[R001](<../projects/V001-开场展示/README.md#单条复盘>)、[D002](<../projects/V001-开场展示/README.md#效果数据>)','相同观察口径','开场需要更直接','样本有限','对下一条验证开场，参见[说明](<../projects/V001-开场展示/执行记录/原始数据.txt>)'])
        self.append(report,'建议验证',['T001','[R001](<../projects/V001-开场展示/README.md#单条复盘>)','采用','本次决定','[成片](<../projects/V001-开场展示/成片/分析版本.webm>)','核对开场','内容调整已落实，效果未取得','[核对原文](<../projects/V001-开场展示/执行记录/原始数据.txt>)'])
        self.append(report,'建议验证',['T002','R001','待决定','未取得','未取得','未取得','未取得','未取得'])
        content_video=initialize_video(self.root,'V002','内容分析')
        content_film=content_video/'成片/内容.webm';store_media(content_video,content_film,source=film)
        self.append(content_video/'README.md','单条复盘',['R001','不适用','[成片](<成片/内容.webm>)核对展示动作','不适用','尚无运营数据','保留动作'])
        return film, evidence

    def test_empty_and_read_only(self):
        response = self.client.get(self.api+'/reviews')
        self.assertEqual(response.status_code,200,response.text)
        data = response.json()
        self.assertEqual(data['conclusions'],[])
        self.assertEqual(data['videos'][0]['samples'],[])
        self.assertEqual(self.client.post(self.api+'/reviews').status_code,405)

    def test_batches_sources_and_originals(self):
        film, evidence = self.prepare()
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        data = overview(self.root,self.api)
        video = data['videos'][0]
        self.assertIsNotNone(video['cover'])
        self.assertEqual(self.client.get(video['cover']).status_code,200)
        self.assertEqual(data['videos'][1]['samples'],[])
        self.assertIn('href="https://example.com/post"',video['publications'][0]['html']['发布链接'])
        self.assertEqual([len(s['rows']) for s in video['samples']],[2,1])
        self.assertTrue(data['trials'][0]['origin']['fields']['调整建议'].startswith('将产品展示提前到开场'))
        self.assertTrue(data['trials'][1]['origin']['fields']['调整建议'].startswith('对下一条验证开场'))
        self.assertEqual([r['label'] for r in video['reviews'][0]['references'] if r['field'] in ('内容判断','局限')],['成片'])
        self.assertEqual([r['label'] for r in data['conclusions'][0]['references'] if r['field']=='视频与证据'],['R001','D002'])
        self.assertIn('data-doc="projects/',video['reviews'][0]['html']['内容判断'])
        for file in (film,evidence):
            url = self.api+'/reviews/files/'+file.relative_to(self.root).as_posix()
            self.assertEqual(self.client.get(url).content,file.read_bytes())
        document = self.client.get(self.api+'/reviews/document',params={'path':evidence.relative_to(self.root).as_posix()})
        self.assertEqual(document.json()['text'],'平台原始证据')
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_files_do_not_escape_context_or_expand_to_unreferenced_files(self):
        self.prepare()
        secret = self.root/'private.txt'; secret.write_text('private')
        for key in ['private.txt','../outside.txt','综合资料/账号定位.md']:
            self.assertEqual(self.client.get(self.api+'/reviews/files/'+key).status_code,404)
        outside = self.base/'outside.txt';outside.write_text('outside')
        evidence = self.project/'执行记录/原始数据.txt';evidence.unlink();evidence.symlink_to(outside)
        self.assertEqual(self.client.get(self.api+'/reviews/files/'+evidence.relative_to(self.root).as_posix()).status_code,404)
        self.space.view='serial-drama'
        self.assertEqual(self.client.get(self.api+'/reviews').status_code,404)

    def test_bad_record_is_visible_error_and_archived_videos_are_omitted(self):
        (self.project/'.archived').touch()
        self.assertEqual(overview(self.root,self.api)['videos'],[])
        (self.project/'.archived').unlink()
        path=self.project/'README.md';path.write_text(path.read_text().replace('## 单条复盘','## 非法改名'))
        self.assertEqual(self.client.get(self.api+'/reviews').status_code,409)

if __name__ == '__main__':
    unittest.main()
