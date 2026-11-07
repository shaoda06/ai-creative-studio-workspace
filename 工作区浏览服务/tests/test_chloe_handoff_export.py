"""Chloe handoff history and direct second-pass reuse through package export."""
import asyncio
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from tests import test_chloe_production as fixtures
from tests.test_jianying_package import restore_package
from chloe_production import check, state
from chloe_documents import records
from backend.services import episode_downloads, jianying_draft
from backend.services.project_packages import package_response


class ChloeHandoffExportTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.ChloeProductionTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.project = self.case.project

    def packages(self):
        case = self.case
        return fixtures.browser.downloads(case.projects, self.project.name, case.api, 'V001')['workPackages']

    def assert_export(self, path):
        spec = json.loads(path.read_text())
        before = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        temporary = Path(self.case.temp.name) / 'downloads'
        async def consume(response):
            chunks = []
            async def send(message):
                if message['type'] == 'http.response.body':
                    chunks.append(message['body'])
            await response({'type': 'http', 'method': 'GET', 'headers': []}, None, send)
            return b''.join(chunks)
        with patch.object(episode_downloads, 'DOWNLOAD_DIRECTORY', temporary), patch.object(
            jianying_draft.MediaInfo, 'parse', return_value=SimpleNamespace(
                video_tracks=[SimpleNamespace(duration=2500, width=1536, height=864, frame_rate='24.000')],
                general_tracks=[], image_tracks=[])):
            for format in ('zip', 'jypack'):
                response = package_response(self.case.projects, self.project.name, path.relative_to(self.project).as_posix(), format)
                payload = asyncio.run(consume(response))
                with ZipFile(BytesIO(restore_package(payload) if format == 'jypack' else payload)) as archive:
                    self.assertIsNone(archive.testzip())
                    for item in spec['media']:
                        self.assertEqual(archive.read(item['member']), (self.project / item['file']).read_bytes())
                    draft = json.loads(archive.read('draft_content.json'))
                    self.assertEqual(draft, json.loads(archive.read('draft_info.json')))
                    materials = {m['id']: m for m in draft['materials']['videos']}
                    segments = draft['tracks'][0]['segments']
                    self.assertEqual([materials[s['material_id']]['path'].split('/')[-1] for s in segments],
                                     [m['member'] for m in spec['media'] if m['timeline']])
                    self.assertEqual([s['target_timerange']['start'] for s in segments], [0, 2500000])
                self.assertEqual(list(temporary.glob('*')), [])
        self.assertEqual(before, {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob('*') if p.is_file()})

    def test_historical_package_survives_new_adoption_and_exports_original_files(self):
        self.case.test_old_handoff_preserves_adoption_history_after_replacement_or_cancellation()
        self.assertEqual(self.packages()[0]['rounds'], [3])
        self.assert_export(self.project / '剪辑交接/交接.jianying.json')
        readme = self.project / 'README.md'
        readme.write_text(readme.read_text().replace('| 可下载 |', '| 待核对 |'))
        self.assertEqual(self.packages(), [])
        readme.write_text(readme.read_text().replace('| 待核对 |', '| 可下载 |').replace('| J001 | 2026-11-07T12:10', '| J001 | 2026-11-07T12:40'))
        with self.assertRaisesRegex(ValueError, '尚未采用或已取消采用'):
            self.packages()

    def test_direct_and_mixed_second_pass_reuse_without_synthetic_processing(self):
        case = self.case
        case.plan()
        case.candidate('P001', 'E001'); case.candidate('P002', 'E002')
        case.candidate('P001', 'E003', stage='二采'); case.candidate('P002', 'E004', stage='二采')
        case.record.write_text(case.record.read_text().replace('| E003 | 视频生成 | 不适用 |', '| E003 | 视频生成 | E001 |').replace('| E004 | 视频生成 | 不适用 |', '| E004 | 视频生成 | E002 |'))
        rounds = [case.round(1, [('P001', 'E001'), ('P002', 'E002')]), case.round(2, [('P001', 'E003'), ('P002', 'E004')])]
        case.rounds(rounds)
        data = state(self.project)
        outputs = {(r['执行编号'], r['输出槽位']): r['资源引用'] for r in records(data['doc'], '输出记录')}
        media = []
        for i, v in enumerate(data['rounds'][2]['values']):
            reference = outputs[v['execution'], v['slot']]
            fixtures.add_row(self.project / 'README.md', '当前采用', [v['id']+'/二采', reference, '原二采批准及技术核对', '2026-11-07T12:00:00+08:00'])
            media.append({'file': (case.root/v['ref']['file']).relative_to(self.project).as_posix(), 'member': str(i)+'.mp4', 'timeline': True})
        old = self.project/'剪辑交接/直接沿用.jianying.json'
        old.write_text(json.dumps({'name': '直接沿用', 'media': media}))
        fixtures.add_row(self.project/'README.md', '剪映交接', ['J001', '2026-11-07T12:10:00+08:00', '[清单](<剪辑交接/直接沿用.jianying.json>)', '可下载', '整片批准及技术核对'])
        self.assertEqual(check(self.project)['candidates'], 4)
        self.assertEqual(self.packages()[0]['rounds'], [2])
        self.assert_export(old)
        # Only P001 needs processing; P002 retains its exact second-pass file/execution.
        path, reference, _ = case.candidate('P001', 'E005', stage='后处理')
        case.record.write_text(case.record.read_text().replace('| E005 | 视频处理 | 不适用 |', '| E005 | 视频处理 | E003 |'))
        rounds.append(case.round(3, [('P001', 'E005'), ('P002', 'E004')], base_round=2, changed_segments=['P001']))
        case.rounds(rounds)
        fixtures.add_row(self.project/'README.md', '当前采用', ['P001/后处理', reference, '二采批准及处理报告', '2026-11-07T12:20:00+08:00'])
        mixed = self.project/'剪辑交接/混合组合.jianying.json'
        mixed.write_text(json.dumps({'name': '混合组合', 'media': [{**media[0], 'file': path.relative_to(self.project).as_posix()}, media[1]]}))
        fixtures.add_row(self.project/'README.md', '剪映交接', ['J002', '2026-11-07T12:30:00+08:00', '[清单](<剪辑交接/混合组合.jianying.json>)', '可下载', '完整组合技术合格'])
        self.assertEqual(check(self.project)['candidates'], 5)
        self.assertEqual({tuple(p['rounds']) for p in self.packages()}, {(2,), (3,)})
        download = fixtures.browser.downloads(case.projects, self.project.name, case.api, 'V001')
        self.assertEqual(download['后处理']['videos']['packages'][0]['name'], '混合组合')
        self.assertEqual(download['二采']['videos']['packages'][0]['name'], '直接沿用')
        self.assert_export(mixed)
