"""Round downloads reference originals, without requiring or changing adoption."""
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
from backend.services import episode_downloads, jianying_draft
from backend.main import workspace_production_download, workspace_production_downloads
from fastapi import HTTPException


class ChloeRoundDownloadTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.ChloeProductionTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        case = self.case
        case.plan()
        self.originals = {}
        rounds = []
        for number, stage in enumerate(('一采', '二采', '后处理'), 1):
            segments = []
            for i in range(2):
                identity, execution = f'P{i+1:03}', f'E{(number-1)*2+i+1:03}'
                self.originals[number, identity] = case.candidate(identity, execution, stage=stage)[0]
                segments.append((identity, execution))
            rounds.append(case.round(number, segments))
        case.candidate('P001', 'E007', run='R002', output=False)
        case.candidate('P002', 'E008', run='R002', output=False)
        rounds.append(case.round(4, [('P001', 'E007'), ('P002', 'E008')]))
        rounds.append(case.round(5, [('P001', 'E003'), ('P002', 'E006')]))
        self.originals[5, 'P001'] = self.originals[2, 'P001']
        self.originals[5, 'P002'] = self.originals[3, 'P002']
        case.rounds(rounds)
        text = case.record.read_text()
        for execution, upstream, kind in [('E003','E001','视频生成'),('E004','E002','视频生成'),('E005','E003','视频处理'),('E006','E004','视频处理')]:
            text = text.replace(f'| {execution} | {kind} | 不适用 |', f'| {execution} | {kind} | {upstream} |')
        case.record.write_text(text)
        space = SimpleNamespace(projects=case.projects, api=case.api)
        self.request = SimpleNamespace(state=SimpleNamespace(workspace_space=space))
        self.adapter = patch('backend.main.production.workbench', return_value=fixtures.browser)
        self.adapter.start(); self.addCleanup(self.adapter.stop)
        self.management = patch('backend.main.management_request', return_value=True)
        self.management.start(); self.addCleanup(self.management.stop)
        self.temporary = Path(case.temp.name)/'downloads'

    async def consume(self, response, interrupt=False):
        chunks = []
        async def send(message):
            if message['type'] == 'http.response.body':
                if interrupt:
                    raise asyncio.CancelledError()
                chunks.append(message['body'])
        await response({'type': 'http', 'method': 'GET', 'headers': []}, None, send)
        return b''.join(chunks)

    def snapshot(self):
        return {p.relative_to(self.case.root): p.read_bytes() for p in self.case.root.rglob('*') if p.is_file()}

    def test_three_stages_round_switch_archive_bytes_and_cleanup(self):
        before = self.snapshot()
        with patch.object(episode_downloads, 'DOWNLOAD_DIRECTORY', self.temporary), patch.object(
            jianying_draft.MediaInfo, 'parse', return_value=SimpleNamespace(
                video_tracks=[SimpleNamespace(duration=2500, width=1536, height=864, frame_rate='24.000')],
                general_tracks=[], image_tracks=[])):
            for number in (1, 2, 3, 5):
                listing = workspace_production_downloads(self.case.project.name, 'V001', self.request, round_number=number)
                self.assertEqual(listing['workPackages'], [])
                self.assertEqual(listing['round']['videos']['count'], 2)
                self.assertIn(f'round={number}', listing['round']['videos']['url'])
                self.assertNotIn('stage=', listing['round']['videos']['url'])
                for format in ('zip', 'jypack'):
                    response = workspace_production_download(self.case.project.name, 'V001', self.request, number, archive_format=format)
                    self.assertTrue(Path(response.path).is_file())
                    payload = asyncio.run(self.consume(response))
                    with ZipFile(BytesIO(restore_package(payload) if format == 'jypack' else payload)) as archive:
                        for identity in ('P001', 'P002'):
                            self.assertEqual(archive.read(identity+'-R001.mp4'), self.originals[number, identity].read_bytes())
                        if format == 'zip':
                            self.assertEqual(archive.namelist(), ['P001-R001.mp4', 'P002-R001.mp4'])
                        else:
                            draft = json.loads(archive.read('draft_content.json'))
                            materials = {m['id']:m for m in draft['materials']['videos']}
                            segments = draft['tracks'][0]['segments']
                            self.assertEqual([materials[s['material_id']]['path'].split('/')[-1] for s in segments], ['P001-R001.mp4','P002-R001.mp4'])
                    self.assertEqual(list(self.temporary.iterdir()), [])
            response = workspace_production_download(self.case.project.name, 'V001', self.request, 1, '一采', 'zip')
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(self.consume(response, interrupt=True))
            self.assertEqual(list(self.temporary.iterdir()), [])
            with patch.object(episode_downloads.jianying_export, 'export_archive', side_effect=ValueError('隔离打包失败')):
                with self.assertRaises(HTTPException) as error:
                    workspace_production_download(self.case.project.name, 'V001', self.request, 1, '一采', 'jypack')
                self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(list(self.temporary.iterdir()), [])
        self.assertEqual(before, self.snapshot())

    def test_empty_wrong_round_and_missing_original(self):
        listing = workspace_production_downloads(self.case.project.name, 'V001', self.request, round_number=4)
        self.assertIsNone(listing['round']['videos']['url'])
        for number, stage, status in [(4, '一采', 409), (1, '二采', 409), (99, '一采', 404)]:
            with self.assertRaises(HTTPException) as error:
                workspace_production_download(self.case.project.name, 'V001', self.request, number, stage, 'zip')
            self.assertEqual(error.exception.status_code, status)
        self.originals[1, 'P001'].unlink()
        with self.assertRaises(HTTPException) as error:
            workspace_production_download(self.case.project.name, 'V001', self.request, 1, '一采', 'zip')
        self.assertEqual(error.exception.status_code, 409)

    def test_canvas_labels_come_from_selected_round_and_execution(self):
        case = self.case
        for execution in ('E001', 'E003', 'E006'):
            folder = case.project/'执行记录'/execution
            folder.mkdir(parents=True)
            (folder/'任务.workflow.json').write_text('{}')
        case.record.write_text(case.record.read_text().replace('| E006 | 视频处理 | E004 | H3 |', '| E006 | 视频处理 | E004 | RIFE插帧＋RTX超分 |'))
        before = self.snapshot()
        with patch.object(fixtures.browser, 'task_for', side_effect=lambda project, row: ({}, project/'执行记录'/row['执行编号'])):
            listing = workspace_production_downloads(case.project.name, 'V001', self.request, round_number=5)
            files = listing['round']['canvas']['files']
            self.assertEqual([f['label'] for f in files], ['P001 · 二采 · E003', 'P002 · 后处理 · E006'])
            self.assertEqual([f['description'] for f in files], ['H3', 'RIFE插帧＋RTX超分'])
            self.assertEqual([f['name'] for f in files], ['任务.workflow.json']*2)
            legacy = fixtures.browser.downloads(case.projects, case.project.name, case.api, 'V001')
            self.assertEqual(files[0]['url'], legacy['二采']['canvas']['files'][0]['url'])
            self.assertNotIn('label', legacy['二采']['canvas']['files'][0])
        self.assertEqual(before, self.snapshot())

        # One execution can produce multiple segments: keep one original canvas.
        _, reference, _ = case.resource(key='same-execution-second-output')
        fixtures.add_row(case.record, '视频分段执行', ['P002','一采','R003','E001','P002视频','0'])
        fixtures.add_row(case.record, '输出记录', ['E001','P002视频',reference])
        case.rounds([case.round(1, [('P001','E001'),('P002','E001')])])
        before = self.snapshot()
        with patch.object(fixtures.browser, 'task_for', side_effect=lambda project, row: ({}, project/'执行记录'/row['执行编号'])):
            files = workspace_production_downloads(case.project.name, 'V001', self.request, round_number=1)['round']['canvas']['files']
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0]['label'], 'P001、P002 · 一采 · E001')
        self.assertEqual(before, self.snapshot())
