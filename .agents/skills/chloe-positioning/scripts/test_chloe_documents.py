"""Template, initializer and populated-record checks in isolated Chloe workspaces."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

from chloe_init import initialize_workspace, initialize_video, initialize_asset, ASSETS, SKILLS
import chloe_documents as docs
sys.path.insert(0,str(SKILLS/'chloe-assets/scripts'))
from chloe_resources import import_media, bind_reference


class ChloeDocumentsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = initialize_workspace(self.base/'Chloe Workspace')
        self.video = initialize_video(self.root,'V001','商品-展示')
        self.assets = {kind:initialize_asset(self.root,kind,data[1]+'001','测试') for kind,data in ASSETS.items()}

    def check(self):
        return docs.check_workspace(self.root)

    def append(self,path,section,row):
        body=path.read_text(); start=body.index('## '+section+'\n')
        end=body.index('\n\n',body.index('| ---',start))
        path.write_text(body[:end]+'\n| '+' | '.join(row)+' |'+body[end:])

    def test_all_fourteen_types_and_reinitialization(self):
        result=self.check()
        self.assertEqual(result,{'checked_documents':14,'errors':[]})
        self.assertEqual(len({source for _,source,_ in docs.documents(self.root)}),14)
        self.assertFalse((self.root/'综合资料/账号运营配置.md').exists())
        direction = next(e for e in docs.documents(self.root) if e[0].name == '账号定位.md')
        parsed = docs.read_document(self.root, *direction)
        self.assertEqual([r['字段'] for r in docs.records(parsed, '账号方向')], ['发布平台', '目标人群', '内容风格'])
        with self.assertRaises(ValueError):
            initialize_video(self.root,'V002','商品|主题')
        p=self.root/'综合资料/账号定位.md'
        p.write_text(p.read_text().replace('| 目标人群 | 待确定 |','| 目标人群 | 通勤人群 |'))
        initialize_workspace(self.root)
        self.assertIn('| 目标人群 | 通勤人群 |',p.read_text())
        self.assertEqual(self.check()['errors'],[])
        for kind,path in self.assets.items():
            self.assertTrue((path/ASSETS[kind][2]).is_file())

    def test_format_drift_and_nonstandard_values_rejected(self):
        p=self.root/'综合资料/账号定位.md'; original=p.read_text()
        changes=[('## 账号方向','## 基本信息'),('| 目标人群 | 待确定 |\n',''),
                 ('| 发布平台 | 抖音 |','| 发布平台 | 抖音 |\n| 发布平台 | 抖音 |'),
                 ('| 内容风格 | 待确定 |','| 内容风格 |  |'),
                 ('| 内容风格 | 待确定 |','| 内容风格 | 甲|乙 |')]
        for before,after in changes:
            with self.subTest(change=before):
                p.write_text(original.replace(before,after))
                self.assertTrue(self.check()['errors'])
        p.write_text(original)
        self.assertFalse(self.check()['errors'])

    def test_model_identity_is_minimal_and_old_fields_are_rejected(self):
        path = self.assets['模特']/'模特说明.md'
        original = path.read_text()
        entry = next(e for e in docs.documents(self.root) if e[0] == path)
        parsed = docs.read_document(self.root, *entry)
        self.assertEqual([r['字段'] for r in docs.records(parsed, '资产身份')],
                         ['资产编号', '资产名称', '来源说明'])
        for field in ('资产类型', '资产用途', '使用限制'):
            path.write_text(original.replace('## 人物特征', f'| {field} | 待核实 |\n\n## 人物特征'))
            self.assertTrue(self.check()['errors'])
        path.write_text(original)
        self.assertFalse(self.check()['errors'])

    def test_parsed_values_keep_long_content_and_template_fields(self):
        path=self.video/'脚本.md'
        path.write_text(path.read_text().replace('| 开头 | 待确定 |','| 开头 | 第一行<br>第二行&#124;示意 |').replace('| 计划时长秒 | 待确定 |','| 计划时长秒 | 15.5 |'))
        entry=next(e for e in docs.documents(self.root) if e[0]==path)
        data=docs.read_document(self.root,*entry)
        values={r['字段']:r['内容'] for r in docs.records(data,'内容与声音')}
        self.assertEqual(values['开头'],'第一行<br>第二行&#124;示意')
        path.write_text(path.read_text().replace('| 计划时长秒 | 15.5 |','| 计划时长秒 | 十五秒 |'))
        self.assertTrue(self.check()['errors'])

    def test_shared_shot_blocks_and_legacy_table_are_readable(self):
        from storyboard_fields import FIELDS
        path = self.video / '脚本.md'
        original = path.read_text()
        values = {field: '保持当前画面' for field in FIELDS}
        values.update({'镜号': 'SH001', '时间': '00:00–00:03秒', '时长': '3秒'})
        pairs = list(values.items()) + [('商品可见细节', '包装上的规格'), ('字幕', '后期添加'), ('参考需求', '待确定')]
        block = '### SH001｜展示规格\n\n' + '\n\n'.join('**' + key + '**：' + value for key, value in pairs)
        prefix = original[:original.index('## 镜头与分镜')]
        suffix = original[original.index('## 修订记录'):]
        path.write_text(prefix + '## 镜头与分镜\n\n' + block + '\n\n' + suffix)
        entry = next(e for e in docs.documents(self.root) if e[0] == path)
        parsed = docs.read_document(self.root, *entry)
        shots = next(section for section in parsed['sections'] if section['heading'] == '镜头与分镜')['shots']
        self.assertEqual(shots[0]['fields']['镜号'], 'SH001')
        good = path.read_text()
        path.write_text(good.replace('**结束画面**：保持当前画面\n\n', ''))
        self.assertTrue(self.check()['errors'])
        path.write_text(good.replace(block, block + '\n\n' + block))
        self.assertTrue(self.check()['errors'])
        columns = '镜头编号 | 时长秒 | 景别与构图 | 主体与商品动作 | 商品可见细节 | 场景与机位 | 对白或旁白 | 字幕 | 音乐与环境声 | 参考需求'
        legacy = '| ' + columns + ' |\n| ' + ' | '.join(['---'] * 10) + ' |\n| SH001 | 3 | 中景 | 递出包装 | 规格文字 | 正面 | 无 | 后期 | 无 | 待确定 |'
        path.write_text(prefix + '## 镜头与分镜\n\n' + legacy + '\n\n' + suffix)
        self.assertEqual(self.check()['errors'], [])

    def test_populated_input_and_output_resolve_same_shared_version(self):
        source=self.base/'source.png'; Image.new('RGB',(12,16),'red').save(source)
        common=import_media(self.root,source,'external/reference')
        own=import_media(self.root,source,'task/output',project=self.video.name)
        bind_reference(self.root,self.video.name,'E001/reference',common['resource_id'],common['version'])
        import os
        common_link=f"[共用:{common['resource_id']}@{common['version']}](<{Path(os.path.relpath(common['absolute_file'],self.video)).as_posix()}>)"
        own_link=f"[本视频:{own['resource_id']}@{own['version']}](<{Path(os.path.relpath(own['absolute_file'],self.video)).as_posix()}>)"
        p=self.video/'制作记录.md'
        self.append(p,'执行记录',['E001','素材导入','不适用','本地导入','不适用','不适用','隔离测试','不适用','2026-11-07T09:00:00+08:00','2026-11-07T09:01:00+08:00','已完成','导入完成'])
        self.append(p,'输入记录',['E001','reference','E001/reference',common_link])
        self.append(p,'输出记录',['E001','output',own_link])
        self.assertEqual(self.check()['errors'],[])
        good=p.read_text()
        p.write_text(good.replace('E001/reference','E002/reference'))
        self.assertTrue(any('共用输入' in e['error'] for e in self.check()['errors']))
        p.write_text(good.replace('@V001','@latest'))
        self.assertTrue(self.check()['errors'])
        p.write_text(good.replace('| E001 | output |','| E002 | output |'))
        self.assertTrue(any('不存在的执行' in e['error'] for e in self.check()['errors']))
        p.write_text(good)
        self.assertEqual(self.check()['errors'],[])
        self.assertEqual(len(list((self.video/'资源').rglob('*.png'))),1)

    def test_duplicate_record_and_wrong_identity(self):
        p=self.root/'综合资料/选品记录.md'
        row=['G001','[商品](<商品资料/G001-测试/商品说明.md>)','候选','测试依据','待核实','未取得','未取得']
        self.append(p,'选品列表',row);self.append(p,'选品列表',row)
        self.assertTrue(any('重复' in e['error'] for e in self.check()['errors']))
        p=self.assets['模特']/'模特说明.md'
        p.write_text(p.read_text().replace('| 资产编号 | M001 |','| 资产编号 | M002 |'))
        self.assertTrue(any('目录不符' in e['error'] for e in self.check()['errors']))

    def test_json_and_manifest_integrity(self):
        refpath=self.video/'资源/共用引用.json'
        refpath.write_text('{"format":1,"references":[]}')
        self.assertTrue(any('共用引用格式' in e['error'] for e in self.check()['errors']))
        refpath.write_text('{"format":1,"references":{}}')
        media=self.video/'成片/fixture.mp4';media.write_bytes(b'isolated path fixture, not a decoded video')
        manifest=self.video/'剪辑交接/test.jianying.json'
        spec={'name':'隔离清单','media':[{'file':'成片/fixture.mp4','member':'01.mp4','timeline':True}]}
        manifest.write_text(json.dumps(spec))
        self.assertEqual(self.check()['errors'],[])
        spec['media'][0]['timeline']=False;manifest.write_text(json.dumps(spec))
        self.assertTrue(any('时间线' in e['error'] for e in self.check()['errors']))
        del spec['media'][0]['timeline'];manifest.write_text(json.dumps(spec))
        self.assertTrue(any('timeline' in e['error'] for e in self.check()['errors']))
        spec['media'][0].update(timeline=True,file='../../outside.mp4');manifest.write_text(json.dumps(spec))
        self.assertTrue(self.check()['errors'])

    def test_look_associations_and_adoption_evidence(self):
        p=self.assets['造型']/'造型说明.md'
        p.write_text(p.read_text().replace('| 模特编号 | 待确定 |','| 模特编号 | M001 |')
                     .replace('| 服装来源类型 | 待确定 |','| 服装来源类型 | 商品 |')
                     .replace('| 服装或商品编号 | 待确定 |','| 服装或商品编号 | G001 |'))
        self.append(p,'关联资料',['模特','M001','[模特](<../../AI模特/M001-测试/模特说明.md>)','人物'])
        self.append(p,'关联资料',['商品','G001','[商品](<../../../商品资料/G001-测试/商品说明.md>)','穿着'])
        self.assertEqual(self.check()['errors'],[])
        good=p.read_text()
        p.write_text(good.replace('| 服装或商品编号 | G001 |','| 服装或商品编号 | O001 |'))
        self.assertTrue(any('造型组合' in e['error'] for e in self.check()['errors']))
        p.write_text(good)
        self.append(p,'当前采用',['全身三视图原图','未取得','未取得','未取得'])
        self.assertTrue(any('当前采用必须' in e['error'] for e in self.check()['errors']))

    def test_completed_publication_and_metrics_use_existing_records(self):
        p=self.video/'README.md'
        p.write_text(p.read_text().replace('| 商品编号 | 待确定 |','| 商品编号 | G001 |')
                     .replace('| 商品资料 | 待确定 |','| 商品资料 | [商品](<../../综合资料/商品资料/G001-测试/商品说明.md>) |'))
        (self.video/'成片/test.mp4').write_bytes(b'path-only fixture')
        time='2026-11-07T10:00:00+08:00'
        p.write_text(p.read_text().replace('| 视频状态 | 制作中 |','| 视频状态 | 已发布 |'))
        self.append(p,'发布记录',['P001','[成片](<成片/test.mp4>)','不适用','测试文案','不适用','不适用','不适用','不适用',time,'立即发布','已发布','test-platform-id','https://example.com/post','隔离授权示例','隔离结果示例'])
        self.append(p,'效果数据',['D001','P001',time,time,time,'播放量','10','次','平台显示','https://example.com/metrics'])
        self.append(p,'效果数据',['D001','P001',time,time,time,'净增粉丝','-2','人','平台显示','https://example.com/metrics'])
        self.append(p,'单条复盘',['R001','D001','样本不足','未取得','隔离示例','继续观察'])
        self.assertEqual(self.check()['errors'],[])
        good=p.read_text()
        p.write_text(good.replace('[成片](<成片/test.mp4>)','[其他文件](<README.md>)'))
        self.assertTrue(any('发布文件' in e['error'] for e in self.check()['errors']))
        p.write_text(good.replace('| 已发布 | test-platform-id |','| 已发布 | 未取得 |'))
        self.assertTrue(any('实际发布字段' in e['error'] for e in self.check()['errors']))
        withdrawn=good.replace('| 立即发布 | 已发布 |','| 立即发布 | 已撤回 |')
        p.write_text(withdrawn)
        self.assertTrue(any('视频状态' in e['error'] for e in self.check()['errors']))
        p.write_text(withdrawn.replace('| 视频状态 | 已发布 |','| 视频状态 | 待发布 |'))
        self.assertEqual(self.check()['errors'],[])
        p.write_text(good)
        self.append(p,'发布记录',['P002','[成片](<成片/test.mp4>)','不适用','重发文案','不适用','不适用','不适用',time,'未取得','定时发布','已提交','未取得','未取得','隔离授权','未取得'])
        self.assertEqual(self.check()['errors'],[])

    def test_pending_video_needs_no_final_registry_or_publication(self):
        p=self.video/'README.md'
        original=p.read_text()
        self.assertNotIn('## 人工成片',original)
        (self.video/'成片/未发布.mp4').write_bytes(b'path-only fixture')
        for status in ('制作中','待发布'):
            p.write_text(original.replace('| 视频状态 | 制作中 |','| 视频状态 | '+status+' |'))
            self.assertEqual(self.check()['errors'],[])
        for status in ('完成','已完成','已发布','已定时','审核中'):
            p.write_text(original.replace('| 视频状态 | 制作中 |','| 视频状态 | '+status+' |'))
            self.assertTrue(self.check()['errors'])
        p.write_text(original.replace('| 处理状态 | 正常 |','| 处理状态 | 进行中 |'))
        self.assertTrue(self.check()['errors'])

    def test_publication_process_keeps_pending_and_checks_exact_file(self):
        p=self.video/'README.md'
        p.write_text(p.read_text().replace('| 视频状态 | 制作中 |','| 视频状态 | 待发布 |'))
        (self.video/'成片/test.mp4').write_bytes(b'path-only fixture')
        time='2026-11-07T10:00:00+08:00'
        self.append(p,'发布记录',['P001','[成片](<成片/test.mp4>)','不适用','文案','不适用','不适用','不适用',time,'未取得','定时发布','待提交','未取得','未取得','隔离授权','未取得'])
        good=p.read_text()
        for progress in ('待提交','已提交','审核中','失败','已撤回','待核实'):
            p.write_text(good.replace('| 待提交 |','| '+progress+' |'))
            self.assertEqual(self.check()['errors'],[])
        for old,new in [('[成片](<成片/test.mp4>)','C001'),
                        ('[成片](<成片/test.mp4>)','[目录](<成片>)'),
                        ('[成片](<成片/test.mp4>)','[缺失](<成片/missing.mp4>)'),
                        (time,'未取得'),('| 定时发布 |','| 已定时 |')]:
            p.write_text(good.replace(old,new))
            self.assertTrue(self.check()['errors'])
        outside=self.root/'综合资料/outside.mp4'; outside.write_bytes(b'outside')
        (self.video/'成片/link.mp4').symlink_to(outside)
        p.write_text(good.replace('成片/test.mp4','成片/link.mp4'))
        self.assertTrue(any('发布文件' in e['error'] for e in self.check()['errors']))


if __name__=='__main__':
    unittest.main()
