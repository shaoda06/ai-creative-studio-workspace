import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from backend.chloe_publication import publication, router
from chloe_init import initialize_workspace, initialize_video, write_template, SKILLS
from chloe_documents import check_workspace, read_document, template
from tests.http_case import HttpTestCase
sys.path.insert(0, str(SKILLS/'chloe-assets/scripts'))
from chloe_resources import import_media
sys.path.insert(0, str(SKILLS/'studio-workspace-browser/scripts'))
from media_files import store_media


class ChloePublicationTests(HttpTestCase):
    def setUp(self):
        super().setUp()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = initialize_workspace(self.base/'Chloe Workspace')
        self.project = initialize_video(self.root, 'V001', '隔离发布')
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
        self.url = self.api+'/publication-videos/'+self.project.name

    def append(self, path, section, values):
        text = path.read_text()
        start = text.index('## '+section+'\n')
        end = text.find('\n\n', text.index('| ---', start))
        if end < 0:
            end = len(text.rstrip('\n'))
        path.write_text(text[:end]+'\n| '+' | '.join(values)+' |'+text[end:])

    def prepare(self):
        film = self.project/'成片/最终成片.webm'
        store_media(self.project, film, source=Path(__file__).parents[1]/'frontend/public/component-samples/video.webm')
        image = self.base/'横版封面.png'
        Image.new('RGB', (160, 120), 'teal').save(image)
        cover = import_media(self.root, image, 'shared-cover')
        label = f'[共用:{cover["resource_id"]}@{cover["version"]}](<{Path(os.path.relpath(cover["absolute_file"],self.project)).as_posix()}>)'
        portrait = self.base/'竖版封面.png'
        Image.new('RGB', (120, 160), 'purple').save(portrait)
        self.portrait = import_media(self.root, portrait, 'portrait-cover', project=self.project.name)
        portrait_label = f'[本视频:{self.portrait["resource_id"]}@{self.portrait["version"]}](<{Path(self.portrait["absolute_file"]).relative_to(self.project).as_posix()}>)'
        path = self.project/'发布资料.md'
        write_template(path, 'chloe-handoff', '发布资料模板.md', identity='V001', title='隔离发布')
        self.row = ['Q001','抖音','示例账号','[成片](<成片/最终成片.webm>)',label,portrait_label,'一件上衣的日常搭配',
                    '领口和面料细节。<br>第二行保留换行与竖线&#124;。','#日常穿搭 #上衣','示例上衣','蓝色 M码',
                    'https://example.com/product?id=1&sku=blue','未取得','待选择','实际成片与商品资料']
        self.append(path, '发布资料', self.row)
        return film, cover, path

    def test_empty_and_read_only_original_media(self):
        self.assertEqual(publication.detail(self.root,self.project.name,self.api)['materials'],[])
        self.assertEqual(publication.listing(self.root,self.api)[0]['finalCount'],0)
        film, cover, path = self.prepare()
        before = {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        response = self.client.get(self.url)
        self.assertEqual(response.status_code,200,response.text)
        data = response.json(); material = data['materials'][0]
        self.assertEqual(material['fields']['正文'],'领口和面料细节。\n第二行保留换行与竖线|。')
        self.assertEqual(data['history'],[])
        self.assertEqual(publication.listing(self.root,self.api)[0]['finalCount'],1)
        for media, original in [(material['film'],film),(material['covers'][0]['media'],Path(cover['absolute_file'])), (material['covers'][1]['media'],Path(self.portrait['absolute_file']))]:
            downloaded = self.client.get(media['url']+'?download=true')
            self.assertEqual(downloaded.content, original.read_bytes())
            self.assertIn('attachment', downloaded.headers['content-disposition'])
            self.assertEqual(self.client.get(media['url'],headers={'Range':'bytes=0-19'}).status_code,206)
        self.assertEqual(before,{p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(check_workspace(self.root, path)['errors'],[])
        self.assertEqual(self.client.post(self.url).status_code,405)

    def test_scoped_files_and_symlink_rejection(self):
        film, cover, path = self.prepare()
        for key in ['README.md', (self.project/'README.md').relative_to(self.root).as_posix(), '../secret.txt']:
            with self.assertRaises((ValueError,FileNotFoundError)):
                publication.media_file(self.root,self.project.name,key)
        image = self.base/'unlinked.png';Image.new('RGB',(32,32),'red').save(image)
        other = import_media(self.root,image,'unlinked')
        with self.assertRaises(FileNotFoundError):
            publication.media_file(self.root,self.project.name,other['file'])
        outside=self.base/'private.webm';outside.write_bytes(b'private')
        (self.project/'成片/越界.webm').symlink_to(outside)
        self.assertEqual(self.client.get(self.url).status_code,409)
        self.assertEqual(self.client.get(self.url+'/files/'+str(outside)).status_code,404)
        self.space.view='files'
        self.assertEqual(self.client.get(self.url).status_code,404)

    def test_bound_publication_history_and_material_edits(self):
        film, cover, path = self.prepare()
        self.row[0]='Q002';self.row[1]='小红书';self.row[6]='另一平台标题'
        self.append(path,'发布资料',self.row)
        readme=self.project/'README.md'
        self.append(readme,'发布记录',['P001',self.row[3],self.row[4],self.row[5],'[Q001](<发布资料.md>)',self.row[8],self.row[10],self.row[11],
                                      '未取得','未取得','立即发布','待提交','未取得','未取得','示例安排','未取得'])
        data=publication.detail(self.root,self.project.name,self.api)
        self.assertEqual([m['id'] for m in data['materials']],['Q001','Q002'])
        self.assertEqual(data['history'][0]['materialId'],'Q001')
        self.assertEqual(data['materials'][0]['fields']['标题'],'一件上衣的日常搭配')
        path.write_text(path.read_text().replace('#日常穿搭 #上衣','#改过的话题',1))
        self.assertEqual(self.client.get(self.url).status_code,409)
        path.write_text(path.read_text().replace('#改过的话题','#日常穿搭 #上衣',1).replace('| 待选择 |','| 不合法执行方式 |',1))
        self.assertEqual(self.client.get(self.url).status_code,409)

    def test_manual_and_agent_flow_preserves_materials_and_partial_public_facts(self):
        film, cover, path = self.prepare()
        self.assertEqual(self.client.get(self.url).json()['history'], [])
        self.assertEqual(self.row[13], '待选择')
        readme = self.project/'README.md'
        time = '2026-11-08T10:00:00+08:00'
        evidence = self.project/'执行记录/发布核对.md'
        evidence.write_text('隔离测试证据：对应账号与作品已公开，商品入口待核实；时间、作品ID和链接未取得。')
        account = self.root/'综合资料/账号定位.md'
        self.append(account, '决定与变更', ['B001', time, '发布设置/抖音/示例账号/可见范围',
                    '无', '公开', '隔离用户决定'])
        for slot, ref in [('横版', self.row[4]), ('竖版', self.row[5])]:
            self.append(readme, '当前采用', ['封面/抖音/'+slot, ref, '隔离封面采用决定', time])
        record = self.project/'制作记录.md'
        initial_record = record.read_text()
        initial_readme, initial_material = readme.read_text(), path.read_text()
        for executor, method, planned in [('用户手动', '立即发布', '未取得'), ('Agent代发', '定时发布', time)]:
            with self.subTest(executor=executor):
                readme.write_text(initial_readme.replace('| 视频状态 | 制作中 |', '| 视频状态 | 待发布 |'))
                record.write_text(initial_record)
                path.write_text(initial_material.replace('| 待选择 |', '| '+executor+' |'))
                frozen = path.read_text()
                row = ['P001', self.row[3], self.row[4], self.row[5], '[Q001](<发布资料.md>)',
                       self.row[8], self.row[10], self.row[11], planned, '未取得', method, '待提交',
                       '未取得', '未取得', '隔离授权或用户发布反馈', '未取得']
                self.append(readme, '发布记录', row)
                revised = self.row.copy()
                revised[0], revised[6], revised[8], revised[13] = 'Q002', '适配后的标题', '#上衣', executor
                revised[14] = '[Q001](<发布资料.md>)；隔离长度调整决定'
                self.append(path, '发布资料', revised)
                self.assertIn(frozen.strip(), path.read_text())
                readme.write_text(readme.read_text().replace('[Q001](<发布资料.md>)', '[Q002](<发布资料.md>)')
                                 .replace(self.row[8], revised[8]))
                self.append(readme, '阶段变更', ['B001', time, 'P001/发布资料', '[Q001](<发布资料.md>)',
                            '[Q002](<发布资料.md>)', '隔离调整决定'])
                self.assertEqual(check_workspace(self.root)['errors'], [])
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(len(response.json()['history']), 1)
                self.assertEqual(response.json()['history'][0]['materialId'], 'Q002')
                if executor == 'Agent代发':
                    readme.write_text(readme.read_text().replace('| 待提交 |', '| 已提交 |'))
                    self.assertEqual(check_workspace(self.root)['errors'], [])
                    self.assertIn('| 视频状态 | 待发布 |', readme.read_text())
                readme.write_text(readme.read_text().replace('| 视频状态 | 待发布 |', '| 视频状态 | 已发布 |')
                                 .replace('| 待提交 |', '| 已发布 |').replace('| 已提交 |', '| 已发布 |')
                                 .replace('隔离授权或用户发布反馈 | 未取得',
                                          '隔离授权或用户发布反馈 | [发布证据](<执行记录/发布核对.md>)'))
                self.append(record, '交接与成片核对', ['K001', time, '[P001](<README.md>)',
                            '公开事实已核实；商品入口待核实', '待核实', '[原证据](<执行记录/发布核对.md>)'])
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200, response.text)
                history = response.json()['history'][0]['fields']
                self.assertEqual(history['发布进展'], '已发布')
                self.assertEqual(history['实际发布时间'], '未取得')
                self.assertEqual(history['平台作品ID'], '未取得')
                self.assertEqual(check_workspace(self.root)['errors'], [])
                readme.write_text(readme.read_text().replace('[发布证据](<执行记录/发布核对.md>)', '已公开'))
                self.assertEqual(self.client.get(self.url).status_code, 409)

    def test_draft_missing_fields_and_project_cover(self):
        film, cover, path=self.prepare()
        image=self.base/'local.png';Image.new('RGB',(64,48),'blue').save(image)
        local=import_media(self.root,image,'local-cover',project=self.project.name)
        self.row[0]='Q002';self.row[3]='未取得'
        self.row[4]=f'[本视频:{local["resource_id"]}@{local["version"]}](<{Path(local["absolute_file"]).relative_to(self.project).as_posix()}>)'
        self.append(path,'发布资料',self.row)
        data=publication.detail(self.root,self.project.name,self.api)
        self.assertIsNone(data['materials'][1]['film'])
        self.assertEqual(self.client.get(data['materials'][1]['covers'][0]['media']['url']).content,image.read_bytes())
        path.write_text(path.read_text().replace('https://example.com/product?id=1&sku=blue','javascript:alert(1)',1))
        self.assertEqual(self.client.get(self.url).status_code,409)

    def test_missing_orientation_and_actual_upload_selection(self):
        film, cover, path = self.prepare()
        original = path.read_text()
        path.write_text(original.replace(self.row[5], '未取得'))
        data = publication.detail(self.root, self.project.name, self.api)
        self.assertIsNotNone(data['materials'][0]['covers'][0]['media'])
        self.assertIsNone(data['materials'][0]['covers'][1]['media'])
        path.write_text(original)
        readme = self.project/'README.md'
        # Only the portrait is uploaded; the prepared landscape stays available.
        self.append(readme, '发布记录', ['P001', self.row[3], '不适用', self.row[5], '[Q001](<发布资料.md>)',
                    self.row[8], self.row[10], self.row[11], '未取得', '未取得', '立即发布', '待提交',
                    '未取得', '未取得', '示例安排', '未取得'])
        self.assertEqual(self.client.get(self.url).status_code, 200)
        readme.write_text(readme.read_text().replace(self.row[5], self.row[4]))
        self.assertEqual(self.client.get(self.url).status_code, 409)


if __name__=='__main__':unittest.main()
