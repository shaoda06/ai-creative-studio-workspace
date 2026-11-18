import json
import os
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from backend.chloe_publication import publication, router, write_router
from chloe_init import initialize_workspace, initialize_project, initialize_video, write_template, SKILLS
from chloe_documents import check_workspace, read_document, template
from tests.http_case import HttpTestCase
from backend.main import queue_write
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
        self.root = initialize_project(initialize_workspace(self.base/'Chloe Workspace'), '隔离样例')
        self.project = initialize_video(self.root, 'V001', '隔离发布')
        self.api = '/api/workspaces/chloe'
        from backend.services.project_files import ProjectFiles
        self.space = SimpleNamespace(root=self.root, api=self.api, view='chloe-commerce',
                                     projects=ProjectFiles(self.root/'projects'), production_adapter='chloe-production')
        app = FastAPI()
        @app.middleware('http')
        async def workspace(request, call_next):
            request.state.workspace_space = self.space
            return await call_next(request)
        app.include_router(router, prefix=self.api)
        app.include_router(write_router, prefix=self.api, dependencies=[Depends(queue_write)])
        self.client = TestClient(app, base_url="http://127.0.0.1")
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

    def test_delete_unreferenced_final_and_preserve_other_files(self):
        film = self.project/'成片/子目录/待删.webm'
        other = self.project/'成片/保留.webm'
        store_media(self.project, film, source=Path(__file__).parents[1]/'frontend/public/component-samples/video.webm')
        store_media(self.project, other, source=film)
        film.chmod(0o644)  # Exercise ordinary deletion, not immutable-file permissions.
        before = other.read_bytes()
        key = film.relative_to(self.root).as_posix()
        url = self.url+'/files/'+key
        self.assertEqual(self.client.delete(url).status_code,403)
        self.assertEqual(self.client.delete(url,headers={'Origin':'https://outside.example'}).status_code,403)
        response = self.client.delete(url,headers={'Origin':'http://127.0.0.1'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(film.exists())
        self.assertEqual(other.read_bytes(),before)
        self.assertEqual(len(self.client.get(self.url).json()['finals']),1)
        self.assertEqual(self.client.delete(url,headers={'Origin':'http://127.0.0.1'}).status_code,404)

    def test_delete_rejects_referenced_and_out_of_scope_files(self):
        film, cover, material = self.prepare()
        url = self.url+'/files/'+film.relative_to(self.root).as_posix()
        headers={'Origin':'http://127.0.0.1'}
        response=self.client.delete(url,headers=headers)
        self.assertEqual(response.status_code,409,response.text)
        self.assertIn('发布资料.md',response.text)
        self.assertTrue(film.exists())
        material.unlink()
        evidence=self.project/'引用说明.md'
        evidence.write_text('[复盘依据](成片/%E6%9C%80%E7%BB%88%E6%88%90%E7%89%87.webm)')
        self.assertEqual(self.client.delete(url,headers=headers).status_code,409)
        evidence.unlink()
        other=initialize_video(self.root,'V002','其他作品')
        foreign=other/'成片/其他.webm';store_media(other,foreign,source=film)
        for key in [foreign.relative_to(self.root).as_posix(),(self.project/'README.md').relative_to(self.root).as_posix(),cover['file']]:
            self.assertEqual(self.client.delete(self.url+'/files/'+key,headers=headers).status_code,404)
        outside=self.base/'outside.webm';outside.write_bytes(b'preserve')
        (self.project/'成片/越界.webm').symlink_to(outside)
        self.assertEqual(self.client.delete(url,headers=headers).status_code,409)
        self.assertEqual(outside.read_bytes(),b'preserve')
        self.assertTrue(film.exists())

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
        self.assertEqual(material['film']['originalDimensions'], [320, 180])
        self.assertEqual([cover['media']['originalDimensions'] for cover in material['covers']], [[160, 120], [120, 160]])
        self.assertEqual(publication.listing(self.root,self.api)[0]['finalCount'],1)
        for media, original in [(material['film'],film),(material['covers'][0]['media'],Path(cover['absolute_file'])), (material['covers'][1]['media'],Path(self.portrait['absolute_file']))]:
            downloaded = self.client.get(media['url']+'?download=true')
            self.assertEqual(downloaded.content, original.read_bytes())
            self.assertIn('attachment', downloaded.headers['content-disposition'])
            self.assertEqual(self.client.get(media['url'],headers={'Range':'bytes=0-19'}).status_code,206)
        self.assertEqual(before,{p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(check_workspace(self.root, path)['errors'],[])
        self.assertEqual(self.client.post(self.url).status_code,405)

    def test_final_file_metadata_is_independent_and_follows_replacement(self):
        film, _, _ = self.prepare()
        incomplete = film.with_name('正在复制.mp4')
        incomplete.write_bytes(b'incomplete')
        def finals():
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200, response.text)
            return {item['name']: item for item in response.json()['finals']}
        items = finals()
        actual = items[film.name]
        stamp = film.stat()
        created = getattr(stamp, 'st_birthtime', None)
        self.assertAlmostEqual(datetime.fromisoformat(actual['fileTime']).timestamp(),
                               created if created is not None else stamp.st_mtime, places=5)
        self.assertEqual(actual['fileTimeSource'], 'created' if created is not None else 'modified')
        self.assertEqual(actual['videoMetadata'], {'width': 320, 'height': 180, 'duration': 2.0})
        self.assertIsNone(items[incomplete.name]['videoMetadata'])
        incomplete.write_bytes(film.read_bytes())
        self.assertEqual(finals()[incomplete.name]['videoMetadata'], actual['videoMetadata'])

    def test_upload_and_script_record_files_without_overwriting(self):
        first, _, _ = self.prepare()
        raw = first.read_bytes()
        target = self.url + '/files'
        headers = {'Origin': 'http://127.0.0.1'}
        upload = {'file': ('网页成片.webm', raw, 'video/webm')}
        self.assertEqual(self.client.post(target, files=upload).status_code, 403)
        self.assertEqual(self.client.post(target, files=upload, headers={'Origin': 'https://outside.example'}).status_code, 403)
        for name, data in [('假视频.mp4', b'bad video'), ('../越界.webm', raw), ('其他.txt', raw)]:
            with self.subTest(name=name):
                response = self.client.post(target, headers=headers, files={'file': (name, data, 'video/webm')})
                self.assertEqual(response.status_code, 422, response.text)
        response = self.client.post(target, files=upload, headers=headers)
        self.assertEqual(response.status_code, 201, response.text)
        added = response.json()
        self.assertEqual((self.root / added['key']).read_bytes(), raw)
        self.assertEqual(self.client.post(target, files=upload, headers=headers).status_code, 409)

        script_file = self.base / '脚本成片.webm'
        script_file.write_bytes(raw)
        script = Path(publication.__file__)
        argv = [sys.executable, '-X', 'utf8', '-B', str(script), '--project-root', str(self.root),
                '--video', self.project.name, str(script_file)]
        cli = subprocess.run(argv, check=True, capture_output=True, encoding='utf-8')
        self.assertEqual((self.root / json.loads(cli.stdout)['key']).read_bytes(), raw)
        self.assertNotEqual(subprocess.run(argv, capture_output=True).returncode, 0)

        items = self.client.get(self.url).json()['finals']
        self.assertEqual([item['name'] for item in items], [script_file.name, added['name'], first.name])
        self.assertTrue(all(item['videoMetadata']['duration'] == 2 for item in items))
        self.assertEqual(self.client.get(self.api+'/publication-videos').json()[0]['finalCount'], 3)
        self.assertEqual(self.client.delete(target + '/' + added['key'], headers=headers).status_code, 200)
        self.assertEqual(len(self.client.get(self.url).json()['finals']), 2)

    def test_rename_keeps_media_and_updates_local_document_links(self):
        film, _, material = self.prepare()
        raw = film.read_bytes()
        sibling = film.with_name('同名.webm')
        sibling.write_bytes(raw)
        self.append(self.project / 'README.md', '发布记录',
                    ['P001', self.row[3], self.row[4], self.row[5], '[Q001](<发布资料.md>)',
                     self.row[8], self.row[10], self.row[11], '未取得', '未取得', '立即发布',
                     '待提交', '未取得', '未取得', '隔离安排', '未取得'])
        record = self.project / '制作记录.md'
        self.append(record, '交接与成片核对', ['K001', '2026-11-16T12:00:00+08:00', self.row[3],
                    '测试原片引用', '通过', '文件读取通过'])
        related = self.project / '执行记录/补充核对.md'
        related.write_text('[原文件](../成片/%E6%9C%80%E7%BB%88%E6%88%90%E7%89%87.webm)\n'
                           '[外部](https://example.org/最终成片.webm)\n'
                           '`[命令示例](<../成片/最终成片.webm>)`\n'
                           '```md\n[文档示例](<../成片/最终成片.webm>)\n```\n', encoding='utf-8')
        url = self.url + '/files/' + film.relative_to(self.root).as_posix()
        headers = {'Origin': 'http://127.0.0.1'}
        self.assertEqual(self.client.patch(url, json={'name': '待改'}).status_code, 403)
        for invalid in ('同名', '  ', '../错误', 'CON'):
            self.assertEqual(self.client.patch(url, headers=headers, json={'name': invalid}).status_code, 409)
        self.assertTrue(film.exists())
        self.assertIn('最终成片.webm', material.read_text(encoding='utf-8'))
        response = self.client.patch(url, headers=headers, json={'name': '暖光 终版.WebM'})
        self.assertEqual(response.status_code, 200, response.text)
        expected = film.with_name('暖光 终版.webm')
        self.assertEqual((self.root / response.json()['key']), expected)
        self.assertEqual(expected.read_bytes(), raw)
        self.assertFalse(film.exists())
        self.assertIn('](<../成片/暖光 终版.webm>)', related.read_text(encoding='utf-8'))
        self.assertIn('https://example.org/最终成片.webm', related.read_text(encoding='utf-8'))
        self.assertIn('[命令示例](<../成片/最终成片.webm>)', related.read_text(encoding='utf-8'))
        self.assertIn('[文档示例](<../成片/最终成片.webm>)', related.read_text(encoding='utf-8'))
        self.assertIn('](<成片/暖光 终版.webm>)', record.read_text(encoding='utf-8'))
        data = self.client.get(self.url).json()
        self.assertEqual(data['materials'][0]['film']['name'], expected.name)
        self.assertIn(expected.name, data['history'][0]['fields']['发布文件'])
        self.assertEqual(self.client.get(data['materials'][0]['film']['url']).content, raw)
        self.assertEqual(sibling.read_bytes(), raw)

    def test_rename_rolls_back_when_a_link_cannot_be_written(self):
        film, _, material = self.prepare()
        readme = self.project / 'README.md'
        original = readme.read_text(encoding='utf-8')
        # Put a real link in a recognized field, so README is written before the failing publication file.
        edited = re.sub(r'(\| 下一步 \| )[^|]+', r'\1[成片](<成片/最终成片.webm>) ', original, count=1)
        self.assertNotEqual(edited, original)
        readme.write_text(edited, encoding='utf-8')
        before = readme.read_bytes()
        original_replace = Path.replace

        def fail_write(path, target):
            if target == material:
                raise PermissionError('模拟发布资料无法写入')
            return original_replace(path, target)

        url = self.url+'/files/'+film.relative_to(self.root).as_posix()
        with patch.object(Path, 'replace', fail_write):
            response = self.client.patch(url, headers={'Origin': 'http://127.0.0.1'}, json={'name': '待改'})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(readme.read_bytes(), before)
        self.assertTrue(film.exists())
        self.assertFalse(film.with_name('待改.webm').exists())
        self.assertEqual(self.client.get(self.url).status_code, 200)

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
                self.assertIn(next(line for line in frozen.splitlines() if line.startswith('| Q001 |')), path.read_text())
                self.assertIn(frozen.split('**本条发布设置**')[-1], path.read_text())
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
