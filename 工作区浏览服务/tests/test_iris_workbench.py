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
            self.assertIsNone(data['后处理']['videos']['url'])
            export.assert_not_called()
            download = self.client.get(data['一采']['videos']['url'] + '&format=jypack')
            self.assertEqual(download.status_code, 200, download.text)
            self.assertEqual(export.call_args.args[0], [(self.project / video, 'P001.mp4')])
            self.assertEqual(export.call_args.args[4], 'jypack')

    def test_before_generation_plan_is_visible_without_a_fake_round(self):
        key = '作品/F003-未生成'
        self.write(key + '/04-分镜声音/分镜与声音制作稿-v01.md', '# 分镜\n### 分段P001｜5秒\n明确计划动作')
        self.write(key + '/作品状态.md', '| 对象 | 当前版本/文件 |\n| --- | --- |\n| 分镜 | ' + key + '/04-分镜声音/分镜与声音制作稿-v01.md |')
        data = self.detail('F003')
        self.assertEqual(data['episodeRounds'], [])
        item, = data['segments']['whole']
        self.assertEqual(item['duration'], 5)
        self.assertTrue(item['planned'])
        self.assertEqual(item['videos'], [])
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
