"""Real temporary files exercise Iris's full-page projection and review writes."""
import json
from unittest.mock import patch
from fastapi.responses import Response

from tests import test_iris_works as fixtures
from backend.services import episode_downloads


class IrisWorkbenchTests(fixtures.IrisWorksTests):

    def register(self, identity='F001'):
        key = self.works[identity]
        board = key + '/04-分镜声音/分镜与声音制作稿-v01.md'
        self.write(board, '# 分镜v01\n### 分段P001｜3秒\n#### SH001\n原始动作和台词\n')
        self.write(key + '/04-分镜声音/分镜与声音制作稿-v02.md', '# 当前改稿\n### 分段P001｜4秒\n改后的动作')
        state = self.project / key / '作品状态.md'
        state.write_text(state.read_text() + '\n| 对象 | 当前版本/文件 |\n| --- | --- |\n| 分镜 | ' + board.replace('v01', 'v02') + ' |\n')
        spec = {'number': 1, 'created_at': '2026-11-06',
                'script': {'file': key + '/03-创意脚本/制作脚本-v01.md', 'version': 'v01'},
                'storyboard': {'file': board, 'version': 'v01'},
                'segments': [{'id': 'P001', 'duration': 3, 'stage': '一采', 'run': 'R001',
                              'file': key + '/06-视频生产/候选/P001-一采.mp4'}]}
        self.write(key + '/06-视频生产/制作轮次.json', json.dumps({'rounds': [spec]}, ensure_ascii=False))
        return spec

    def detail(self, identity='F001'):
        response = self.client.get(self.api + '/works/' + identity + '/production-detail')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_exact_round_sources_and_candidates_keep_work_identity(self):
        for identity in self.works:
            self.register(identity)
            data = self.detail(identity)
            self.assertEqual(data['name'], identity)
            self.assertEqual(data['scenes'], ['whole'])
            self.assertEqual(data['episodeRounds'], [{'number': 1, 'scenes': ['whole']}])
            round_, = data['sceneRounds']['whole']
            self.assertIn('原始动作和台词', round_['storyboard']['doc']['html'])
            self.assertNotIn('改后的动作', round_['segments'][0]['scriptHtml'])
            self.assertIn(self.works[identity], round_['segments'][0]['key'])
            video, = data['segments']['whole'][0]['videos']
            self.assertEqual(self.client.get(video['url']).text, identity + '候选')
            self.assertFalse(video['approved'])

    def test_missing_candidate_retains_round_and_recovery_uses_same_path(self):
        spec = self.register()
        path = self.project / spec['segments'][0]['file']
        value = path.read_bytes()
        path.unlink()
        data = self.detail()
        self.assertEqual(data['segments']['whole'][0]['videos'][0]['url'], '')
        self.assertEqual(data['sceneRounds']['whole'][0]['segments'][0]['key'], spec['segments'][0]['file'])
        path.write_bytes(value)
        self.assertTrue(self.detail()['segments']['whole'][0]['videos'][0]['url'])

    def test_legacy_single_shot_and_plan_timing_use_business_ids(self):
        spec = self.register()
        key = self.works['F001']
        self.write(key + '/06-视频生产/执行记录/R001-一采/请求.json', json.dumps({'prompt': {'1': {
            'class_type': 'MiniMaxH3Director', 'inputs': {'timeline_data': json.dumps({'segments': [
                {'prompt': 'detailed_description:\n[Shot 1]\nOne shot'}], 'global': {}})},
        }}}))
        spec['segments'][0]['duration'] = 5.125
        self.write(key + '/06-视频生产/制作轮次.json', json.dumps({'rounds': [spec]}))
        for plan, duration in [(
            '| 生产段 | 源摄影镜头 | 目标段长 |\n| --- | --- | --- |\n| P001 | SH002 | 5秒 |', 5.125,
        ), (
            '| 生成段 | 对应镜号 | 请求时长 | 段内Shot及时间 |\n| --- | --- | --- | --- |\n'
            '| P001 | SH002 | 5秒 | Shot 1：0–5秒 |', 5,
        )]:
            with self.subTest(plan=plan):
                self.write(spec['storyboard']['file'], plan)
                item, = self.detail()['segments']['whole']
                context = item['videos'][0]['context']
                shot, = context['shots']
                self.assertEqual((context['shotTimingSource'], shot['id'], shot['start'], shot['duration']),
                                 ('plan', 'SH002', 0, duration))
                self.assertIn('<h4>SH002</h4>', shot['html'])
                self.assertIn('[Shot 1]', context['prompts']['english'])

    def test_versioned_plan_groups_a_whole_film_and_aligns_only_evidenced_shots(self):
        spec = self.register()
        key = self.works['F001']
        plan = '''# 隔离分镜

| 生成段 | 场次 | 请求时长 | 所含原镜号 | 段内Shot及时间 |
| --- | --- | --- | --- | --- |
| P001 | S001 | 7秒 | SH001、SH002 | Shot 1：0–3秒；Shot 2：3–7秒 |
| P002 | S002 | 8秒 | SH003、SH004 | Shot 1：0–4秒；Shot 2：4–8秒 |

### 分段P001｜7秒

#### SH001｜外景

原有镜头内容

#### SH002｜开门

**台词与发声者**：甲：“进来”

### 分段P002｜8秒

#### SH003｜室内

室内动作

#### SH004｜收尾

原有结尾
'''
        self.write(spec['storyboard']['file'], plan)
        path = key + '/06-视频生产/候选/P002-一采.mp4'
        self.write(path, 'existing second candidate fixture')
        spec['segments'][0]['duration'] = 7
        spec['segments'].append({'id': 'P002', 'stage': '一采', 'run': 'R001', 'file': path, 'duration': 8})
        self.write(key + '/06-视频生产/制作轮次.json', json.dumps({'rounds': [spec]}))
        record = key + '/06-视频生产/执行记录/R001-一采'
        journal = self.project / record / '提交任务清单-装配结果.json'
        data = json.loads(journal.read_text())
        data['tasks'][0]['outputs'].append({'path': path, 'index': 1})
        journal.write_text(json.dumps(data))
        groups = [
            {'prompt': 'detailed_description:\n[Shot 1]\nExterior\n[Shot 2]\nDoor opens'},
            {'prompt': 'detailed_description:\n[Shot 1]\ntime: 1-5\nInterior\n[Shot 2]\ntime: 5-8\nEnd'},
        ]
        self.write(record + '/请求.json', json.dumps({'prompt': {'1': {
            'class_type': 'MiniMaxH3Director', 'inputs': {'timeline_data': json.dumps({'segments': groups, 'global': {}})},
        }}}))
        data = self.detail()
        self.assertEqual(data['episodeRounds'], [{'number': 1, 'scenes': ['S001', 'S002']}])
        for scene, segment, expected in [
            ('S001', 'P001', ('plan', [('SH001', 0, 3), ('SH002', 3, 4)])),
            ('S002', 'P002', ('recorded', [('SH003', 1, 4), ('SH004', 5, 3)])),
        ]:
            self.assertEqual([entry['id'] for entry in data['sceneRounds'][scene][0]['segments']], [segment])
            item, = data['segments'][scene]
            video, = item['videos']
            context = video['context']
            self.assertEqual((context['shotTimingSource'], [(shot['id'], shot['start'], shot['duration']) for shot in context['shots']]), expected)
        manifest = key + '/07-返修交接/草稿.jianying.json'
        media = [{'file': item['file'], 'member': item['id'] + '.mp4'} for item in spec['segments']]
        url = self.api + '/works/F001/production-downloads?scene=S001'
        self.write(manifest, json.dumps({'name': '隔离整片', 'media': media}))
        package, = self.client.get(url).json()['workPackages']
        self.assertEqual((package['rounds'], package['count']), ([1], 2))
        self.write(manifest, json.dumps({'name': '顺序不同', 'media': media[::-1]}))
        mismatched = self.client.get(url).json()
        self.assertEqual(mismatched['workPackages'], [])
        self.assertEqual(mismatched['一采']['videos']['count'], 2)
        self.write(spec['storyboard']['file'], plan.replace('Shot 2：3–7秒', 'Shot 2：4–7秒'))
        invalid = self.detail()['segments']['S001'][0]['videos'][0]['context']
        self.assertEqual([(shot['id'], shot['duration']) for shot in invalid['shots']], [('SH001', None), ('SH002', None)])
        self.assertNotIn('shotTimingSource', invalid)

    def test_archived_notes_are_read_from_the_original_file_and_cannot_be_saved(self):
        self.register()
        work = self.works['F001']
        archive = '归档/原制作'
        self.write(work + '/06-视频生产/历史执行入口.json', json.dumps({'archives': [archive]}))
        note = {'segment': 'P001', 'stage': '一采', 'run': 'R001', 'roundNumber': 2,
                'text': 'SH001：原镜头意见', 'fileRevision': 'original', 'updatedAt': '2026-11-05'}
        path = self.write(archive + '/09-剧集制作/EP001/其他资料/工作稿/EP001-视频修改意见.json',
                          json.dumps({'episode': 'EP001', 'notes': {'C001': {'round/2/P001/一采/R001': note}},
                                      'rounds': {'2': {'number': 2, 'text': '原总体意见', 'updatedAt': '2026-11-05'}}}, ensure_ascii=False))
        original = path.read_bytes()
        url = self.api + '/works/F001/production-notes'
        result = self.client.get(url + '/archive')
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['scenes']['C001']['notes']['round/2/P001/一采/R001']['text'], note['text'])
        self.assertEqual(result.json()['rounds']['2']['text'], '原总体意见')
        self.assertEqual(self.client.get(url.replace('F001', 'F002') + '/archive').status_code, 404)
        change = {key: value for key, value in note.items() if key != 'updatedAt'}
        self.assertEqual(self.client.put(url, json={**change, 'expectedText': ''}).status_code, 409)
        self.assertEqual(self.client.put(url + '/archive', json=change).status_code, 405)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse((self.project / work / '06-视频生产/视频修改意见.json').exists())

    def test_round_notes_are_separate_and_unknown_combinations_are_rejected(self):
        for identity in self.works:
            self.register(identity)
            url = self.api + '/works/' + identity + '/production-notes'
            note = {'roundNumber': 1, 'segment': 'P001', 'stage': '一采', 'run': 'R001',
                    'text': identity + '本轮意见', 'fileRevision': 'test', 'expectedText': ''}
            self.assertEqual(self.client.put(url, json=note).status_code, 200)
            self.assertEqual(self.client.put(url, json={**note, 'expectedText': '过期文字'}).status_code, 409)
            self.assertEqual(self.client.put(url, json={**note, 'roundNumber': 9}).status_code, 409)
            response = self.client.put(url + '/export', json={'notes': [], 'rounds': [
                {'number': 1, 'text': identity + '整片意见', 'expectedText': ''}]})
            self.assertEqual(response.status_code, 200, response.text)
        for identity in self.works:
            data = self.client.get(self.api + '/works/' + identity + '/production-notes').json()
            self.assertEqual(data['notes']['round/1/P001/一采/R001']['text'], identity + '本轮意见')
            self.assertEqual(data['rounds']['1']['text'], identity + '整片意见')

    def test_browsing_does_not_pack_and_click_uses_only_explicit_manifest(self):
        self.register()
        key = self.works['F001']
        manifest = key + '/07-返修交接/草稿.jianying.json'
        video = key + '/06-视频生产/候选/P001-一采.mp4'
        self.write(manifest, json.dumps({'name': '隔离成片', 'media': [{'file': video, 'member': 'P001.mp4'}]}))
        with patch.object(episode_downloads.jianying_export, 'export_archive') as export:
            def write_package(files, path, name, timeline_members, archive_format):
                path.write_bytes(b'isolated package')
            export.side_effect = write_package
            self.detail()
            response = self.client.get(self.api + '/works/F001/production-downloads')
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data['一采']['videos']['count'], 1)
            package, = data['workPackages']
            self.assertEqual(package['rounds'], [1])
            self.assertEqual(data['一采']['videos']['packages'][0]['url'], package['zip'])
            self.assertIsNone(data['后处理']['videos']['url'])
            export.assert_not_called()
            download = self.client.get(data['一采']['videos']['url'] + '&format=jypack')
            self.assertEqual(download.status_code, 200, download.text)
            self.assertEqual(export.call_args.args[0], [(self.project / video, 'P001.mp4')])
            self.assertEqual(export.call_args.args[4], 'jypack')

    def test_work_status_and_material_review_read_only_the_current_evidence(self):
        self.register()
        key = self.works['F001']
        status = self.project / key / '作品状态.md'
        status.write_text('当前阶段与下一步：样片已取回，等用户看图。\n\n' + status.read_text()
                          + '\n| 交付状态 | 交付说明 | 归档交接记录 |\n| --- | --- | --- |\n| 样片审阅中 | 审阅后再登记采用 | — |\n')
        directory = key + '/05-资产/'
        groups = [('已采用', 'adopted'), ('待审阅', 'pending'), ('待修改', 'revision'), ('未采用', 'history'), ('参考', 'unknown')]
        rows = []
        for index, (label, _) in enumerate(groups, 1):
            image = f'图{index}.png'
            self.write(directory + image, 'image fixture')
            rows.append(f'| A{index:03d} | {label} | [{image}]({image}) | 该版本的原决定 |')
        self.write(directory + '资产清单与制作说明-v01.md',
                   '| 编号 | 已有／需制作 | 当前文件及版本 | 使用／采用依据 |\n| --- | --- | --- | --- |\n' + '\n'.join(rows))
        data = self.detail()
        self.assertEqual(data['workStatus']['label'], '样片审阅中')
        self.assertIn('样片已取回', data['workStatus']['summaryHtml'])
        self.assertEqual([item['materialGroup'] for item in data['materials']], [group for _, group in groups])
        self.assertTrue(all(item['materialReview']['key'].startswith(directory) and '该版本的原决定' in item['approvalHtml']
                            for item in data['materials']))
        self.assertTrue(all(not video['approved'] for segment in data['segments']['whole'] for video in segment['videos']))

    def test_work_status_and_adoption_use_only_the_linked_versions(self):
        spec = self.register()
        self.register('F002')
        key = self.works['F001']
        alternate = key + '/06-视频生产/候选/旧版/P001-一采.mp4'
        self.write(alternate, 'another version with the same P and R')
        journal = self.project / key / '06-视频生产/执行记录/R001-一采/提交任务清单-装配结果.json'
        data = json.loads(journal.read_text())
        data['tasks'][0]['outputs'].append({'path': alternate})
        journal.write_text(json.dumps(data))
        adoption = key + '/07-返修交接/采用记录.md'
        self.write(adoption, '## 当前采用组合\n\n| 段号 | 采用版本及文件 |\n| --- | --- |\n'
                   '| P001 | [采用版本](../06-视频生产/候选/P001-一采.mp4) |\n')
        self.write(key + '/作品状态.md', '制作状态：后期接续\n当前阶段与下一步：第1轮已采用。\n\n'
                   f'| 对象 | 当前版本/文件 |\n| --- | --- |\n| 视频采用记录 | {adoption} |\n')
        work = self.detail()
        self.assertEqual(work['workStatus']['label'], '后期接续')
        self.assertIn('第1轮已采用', work['workStatus']['summaryHtml'])
        videos = work['segments']['whole'][0]['videos']
        self.assertEqual([video['key'] for video in videos if video['approved']], [spec['segments'][0]['file']])
        self.assertTrue(videos[0]['adoptionKnown'])
        self.assertFalse(self.detail('F002')['segments']['whole'][0]['videos'][0]['approved'])

    def test_before_generation_plan_is_visible_without_a_fake_round(self):
        key = '作品/F003-未生成'
        self.write(key + '/04-分镜声音/分镜与声音制作稿-v01.md', '# 分镜\n### 分段P001｜5秒\n\n#### SH001\n明确计划动作')
        self.write(key + '/作品状态.md', '| 对象 | 当前版本/文件 |\n| --- | --- |\n| 分镜 | ' + key + '/04-分镜声音/分镜与声音制作稿-v01.md |')
        data = self.detail('F003')
        self.assertEqual(data['episodeRounds'], [])
        item, = data['segments']['whole']
        self.assertEqual(item['duration'], 5)
        self.assertTrue(item['planned'])
        self.assertEqual(item['videos'], [])
        self.assertEqual(item['shotIds'], ['SH001'])
        self.assertIn('明确计划动作', item['scriptHtml'])

    def test_bad_source_and_unregistered_candidate_are_not_replaced_with_latest(self):
        spec = self.register()
        spec['script']['file'] = '缺失脚本.md'
        spec['segments'][0]['file'] = '未提交的P001.mp4'
        self.write(self.works['F001'] + '/06-视频生产/制作轮次.json', json.dumps({'rounds': [spec]}))
        data = self.detail()
        round_, = data['sceneRounds']['whole']
        self.assertIsNone(round_['script'])
        self.assertEqual(len(round_['issues']), 2)
        self.assertEqual(round_['segments'][0]['key'], '未提交的P001.mp4')
        self.assertEqual(self.client.get(self.api + '/works/F999/production-detail').status_code, 404)

    def test_archived_director_request_rebases_only_the_declared_archive(self):
        key = self.works['F001']
        archive = '归档/旧稿'
        path = archive + '/09-剧集制作/EP001/定稿.director.json'
        source = {'name': '定稿.mmxpack.zip', 'node_id': '1', 'workflow': {},
                  'media': {'a': '历史制作资料/旧稿/原图.png'}}
        file = self.write(path, json.dumps(source))
        self.write(archive + '/原图.png', 'isolated input')
        self.write(key + '/06-视频生产/历史执行入口.json', json.dumps({'archives': [archive]}))
        with patch('backend.main.director_spec_response', return_value=Response(b'isolated')) as export:
            url = self.api + '/works/F001/production-director'
            self.assertEqual(self.client.get(url, params={'path': path}).status_code, 200)
            self.assertEqual(export.call_args.args[2]['media'], {'a': archive + '/原图.png'})
            self.assertEqual(json.loads(file.read_text()), source)
            export.reset_mock()
            self.assertEqual(self.client.get(url.replace('F001', 'F002'), params={'path': path}).status_code, 404)
            export.assert_not_called()
