import os
from pathlib import Path
import sys
import tempfile
import unittest
import wave

from backend.chloe_asset_pages import AssetPage, asset_page
from backend.chloe_reference_assets import VOICES, asset_cards, asset_detail, asset_file, asset_rows
from chloe_init import initialize_workspace, initialize_project, initialize_asset, initialize_video, SKILLS
from chloe_documents import SOUND_TYPES
sys.path.insert(0, str(SKILLS/'chloe-assets/scripts'))
from chloe_resources import bind_reference, import_media, resolve_reference
from chloe_sound import record_sound


class ChloeVoicesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = initialize_project(initialize_workspace(self.base/'Chloe Workspace'), '隔离样例')
        self.folder = initialize_asset(self.root, '声音', 'A001', '示例声音')
        self.path = self.folder/'声音说明.md'
        self.api = '/api/workspaces/test'

    def append(self, section, row):
        text = self.path.read_text()
        end = text.index('\n\n', text.index('| ---', text.index('## '+section+'\n')))
        self.path.write_text(text[:end]+'\n| '+' | '.join(row)+' |'+text[end:])

    def audio(self, key, seconds, resource=None):
        path = self.base/(key+'.wav')
        with wave.open(str(path), 'wb') as output:
            output.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            output.writeframes(b'\0\0' * int(seconds * 8000))
        ref = import_media(self.root, path, key, resource_id=resource)
        return ref, f'[共用:{ref["resource_id"]}@{ref["version"]}](<{os.path.relpath(ref["absolute_file"], self.folder)}>)'

    def test_original_candidate_and_exact_adoption_no_copies(self):
        self.assertIsNone(asset_cards(self.root, self.api, VOICES)[0]['media'])
        first, one = self.audio('original', 1)
        second, two = self.audio('candidate', 2, first['resource_id'])
        self.append('参考版本', ['声音原始参考', one, '用户提供', '不适用'])
        self.append('参考版本', ['声音参考', one, one, '不适用'])
        self.append('参考版本', ['声音参考', two, one, '不适用'])
        self.assertIsNone(asset_cards(self.root, self.api, VOICES)[0]['media'])
        self.append('当前采用', ['声音参考', one, '用户试听批准', '2026-11-08T00:00:00+08:00'])
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        data = asset_detail(self.root, 'A001', self.api, VOICES)
        current = [v for v in data['versions'] if v['adopted']]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['version'], first['version'])
        self.assertEqual(current[0]['duration'], 1)
        self.assertEqual(current[0]['media']['kind'], 'audio')
        self.assertEqual(data['description'], '无')
        self.assertEqual(data['models'], [])
        card = asset_cards(self.root, self.api, VOICES)[0]
        self.assertEqual(card['reference'], {'resource':first['resource_id'],'version':first['version'],'duration':1})
        self.assertEqual(asset_file(self.root, 'A001', card['media']['key'], VOICES), Path(first['absolute_file']))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_original_not_adoptable_and_unreferenced_not_exposed(self):
        ref, label = self.audio('unlinked', 1)
        with self.assertRaises(FileNotFoundError):
            asset_file(self.root, 'A001', Path(ref['absolute_file']).relative_to(self.root).as_posix(), VOICES)
        self.append('当前采用', ['声音原始参考', label, '错误采用', '2026-11-08T00:00:00+08:00'])
        with self.assertRaisesRegex(ValueError, '当前采用只登记'):
            asset_detail(self.root, 'A001', self.api, VOICES)

    def test_model_association_and_bad_purpose(self):
        model = initialize_asset(self.root, '模特', 'M001', '示例模特')
        self.append('关联资料', ['模特', 'M001', f'[模特](<{os.path.relpath(model/"模特说明.md",self.folder)}>)', '说话音色'])
        data = asset_detail(self.root, 'A001', self.api, VOICES)
        self.assertEqual(data['models'], [{'id':'M001', 'name':'M001 · 示例模特'}])
        card = asset_cards(self.root, self.api, VOICES)[0]
        self.assertEqual(card['models'], ['M001'])
        self.assertIsNone(card['reference'])
        self.assertEqual(card['description'], '无')
        _, label = self.audio('reference', 1)
        self.append('参考版本', ['旁白', label, '用户提供', '不适用'])
        with self.assertRaisesRegex(ValueError, '声音用途'):
            asset_detail(self.root, 'A001', self.api, VOICES)

    def test_video_original_cannot_be_formal_audio(self):
        video = Path(__file__).resolve().parents[1]/'frontend/public/component-samples/video.webm'
        ref = import_media(self.root, video, 'video-original')
        label = f'[共用:{ref["resource_id"]}@{ref["version"]}](<{os.path.relpath(ref["absolute_file"], self.folder)}>)'
        self.append('参考版本', ['声音原始参考', label, '用户提供视频', '不适用'])
        self.assertEqual(asset_detail(self.root, 'A001', self.api, VOICES)['versions'][0]['media']['kind'], 'video')
        self.path.write_text(self.path.read_text().replace('| 声音原始参考 |', '| 声音参考 |'))
        with self.assertRaisesRegex(ValueError, '声音参考须为音频'):
            asset_detail(self.root, 'A001', self.api, VOICES)

    def test_shared_original_filters_and_binds_to_other_videos(self):
        ref, _ = self.audio('sample', 1)
        source = self.base / 'sample.wav'
        chorus = record_sound(self.root, source, 'A002', '曲目甲', SOUND_TYPES[0], '用户提供', '快节奏')
        self.assertEqual(chorus['resource_id'], ref['resource_id'])
        self.assertEqual(record_sound(self.root, source, 'A002', '曲目甲', SOUND_TYPES[0], '用户提供'), chorus)
        self.path.write_text(self.path.read_text().replace('| 声音分类 | 人物声音参考 |\n| 标签 | 无 |\n', ''))
        rows = asset_rows(self.root, self.api, VOICES)
        filtered = asset_page(rows, AssetPage(page=1, types=[SOUND_TYPES[0]], search='快节奏'), SOUND_TYPES)
        self.assertEqual(tuple(filtered['types']), SOUND_TYPES)
        self.assertEqual([item['id'] for item in filtered['items']], ['A002'])
        self.assertEqual(filtered['items'][0]['reference']['duration'], 1)
        voices = asset_page(rows, AssetPage(types=[SOUND_TYPES[-1]]))
        self.assertEqual([item['id'] for item in voices], ['A001'])
        self.assertIsNone(voices[0]['media'])
        detail = asset_detail(self.root, 'A002', self.api, VOICES)
        self.assertFalse(detail['voiceReference'])
        self.assertFalse(detail['versions'][0]['adopted'])
        self.assertEqual(asset_file(self.root, 'A002', detail['versions'][0]['media']['key'], VOICES),
                         self.root / chorus['file'])
        for identity in ('V001', 'V002'):
            video = initialize_video(self.root, identity, '跨作品复用')
            bind_reference(self.root, video.name, '剪辑/配乐', chorus['resource_id'], chorus['version'])
            self.assertEqual(resolve_reference(self.root, video.name, '剪辑/配乐'), self.root / chorus['file'])
            self.assertFalse(list((video / '资源/音频').rglob('*.wav')))
