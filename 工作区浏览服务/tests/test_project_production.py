import json
from urllib.parse import quote
from backend.services.production import iris_browser_production as business
from backend.services.review_notes import ProjectReviewNotes
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
from fastapi.testclient import TestClient
from backend import main
from backend.services.projects import ProjectStore
from backend.services.workspaces import Workspaces
from tests.http_case import HttpTestCase
import execution_records as records


class ProjectProductionTests(HttpTestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.primary, self.other = self.root / 'nora', self.root / 'iris'
        for root in (self.primary, self.other):
            (root / 'projects/同名项目').mkdir(parents=True)
        runtime = self.root / 'runtime'
        runtime.mkdir()
        (runtime / 'workspaces.json').write_text(json.dumps([{
            'id': 'commercial', 'name': 'Iris', 'path': str(self.other), 'view': 'iris-commercial',
            'production_adapter': 'iris-commercial-production',
        }]))
        self.spaces = Workspaces(self.primary, runtime, ProjectStore(self.primary / 'projects'), 'test')
        override = patch.object(main.app.state, 'workspaces', self.spaces, create=True)
        override.start()
        self.addCleanup(override.stop)
        self.client = TestClient(main.app, base_url='http://localhost:8782', client=('127.0.0.1', 50000), headers={'Origin': 'http://localhost:8782'})
        self.addCleanup(self.client.close)
        self.api = '/api/workspaces/commercial'
        self.project = self.other / 'projects/同名项目'
        self.directory = self.project / '06-视频生产/执行记录/R001-一采'
        self.directory.mkdir(parents=True)
        self.api += '/projects/' + quote('同名项目')
        (self.project / 'face.png').write_bytes(b'face')
        self.key = '06-视频生产/候选/R001/P001-一采.mp4'
        output = self.project / self.key
        output.parent.mkdir(parents=True)
        output.write_bytes(b'isolated video')
        workflow = {'502': {'class_type': 'MiniMaxH3Director', 'inputs': {'frame_rate': 24, 'timeline_data': json.dumps({
            'global': {'commonEnabled': False}, 'segments': [{'durationSec': 3, 'prompt': 'detailed_description:\\n[Shot 1]\\ntime: 0-3\\nActual shot.\\noverall_soundscape: Silence.', 'refs': [{'index': 2, 'imageFile': 'remote/face.png'}]}]})}}}
        self.task = {'task_type': 'video-first-pass', 'project': '/old/workspace/projects/同名项目',
            'record_dir': '/old/workspace/projects/同名项目/06-视频生产/执行记录/R001-一采', 'outputs': [],
            'uploads': [{'file': '/old/workspace/projects/同名项目/face.png', 'node': '502', 'input': 'timeline_data', 'json-path': ['segments', 0, 'refs', 0, 'imageFile']}],
            'segment_plan': {'director_node': '502', 'targets': [{'index': 0, 'path': self.key}]}}
        self.journal = self.directory / '提交任务清单-v01-装配结果.json'
        self.journal.write_text(json.dumps({'tasks': [self.task], 'accepted': [{'local_task_id': 'fixture'}]}))
        records.initialize(self.directory)
        records.write(self.directory / '请求.json', {'prompt': workflow})
        self.note = {'segment': 'P001', 'stage': '一采', 'run': 'R001', 'text': '00.01.0秒：隔离意见', 'fileRevision': 'fixture-v1', 'expectedText': ''}

    def test_submitted_evidence_and_compact_request(self):
        result = self.client.get(self.api + '/production')
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(len(data['batches']), 1)
        video = data['segments'][0]['videos'][0]
        self.assertFalse(video['approved'])
        self.assertFalse(video['adoptionKnown'])
        self.assertEqual(video['context']['references']['segment'][0]['label'], 'Picture 3')
        self.assertIn('/commercial/', video['url'])
        self.assertIn('Actual shot.', video['context']['prompts']['english'])
        self.assertEqual(video['context']['shots'][0]['duration'], 3)
        self.assertEqual(self.client.get(self.api).json()['productionSection'], '06-视频生产')
        self.assertEqual([space['view'] for space in self.client.get('/api/workspaces').json()], ['serial-drama', 'iris-commercial'])
        self.assertFalse((self.project / '09-剧集制作').exists())
        self.assertFalse((self.project / '06-视频生产/视频修改意见.json').exists())

    def test_missing_result_recovers_without_adoption(self):
        target = self.project / self.key
        target.unlink()
        missing = self.client.get(self.api + '/production').json()['segments'][0]['videos'][0]
        self.assertEqual(missing['url'], '')
        target.write_bytes(b'restored')
        restored = self.client.get(self.api + '/production').json()['segments'][0]['videos'][0]
        self.assertTrue(restored['url'])
        self.assertFalse(restored['approved'])

    def test_prepared_only_is_not_a_candidate(self):
        self.journal.write_text(json.dumps({'tasks': [self.task], 'accepted': []}))
        self.assertEqual(self.client.get(self.api + '/production').json()['segments'], [])

    def test_archived_nora_source_remains_read_only(self):
        self.journal.unlink()
        archive = self.project / '归档/Nora原项目'
        (archive / '09-剧集制作/EP001').mkdir(parents=True)
        video = {'key': '片段.mp4', 'url': '片段.mp4', 'stage': '后处理', 'run': 'R001', 'candidateNumber': 1}
        data = {'catalogues': {'09-剧集制作': {'children': [{'segments': {'C001': [{'id': 'P001', 'videos': [video]}]}}]}}}
        with patch('backend.parsers.project.build_data', return_value=data) as build:
            response = self.client.get(self.api + '/production')
        self.assertEqual(response.status_code, 200, response.text)
        build.assert_called_once()
        self.assertEqual(build.call_args.args[0], archive.resolve())
        result = response.json()
        self.assertTrue(result['batches'][0]['readOnly'])
        self.assertEqual(result['segments'][0]['videos'][0]['key'], '归档/Nora原项目/片段.mp4')

    def test_shared_review_storage_keeps_dialogue_edits(self):
        edit = {'shot': 'SH001', 'index': 0, 'speaker': '讲解人', 'original': '原句', 'replacement': '新句'}
        value = self.note | {'dialogueEdits': [edit], 'expectedDialogueEdits': []}
        result = self.client.put(self.api + '/production-notes', json=value)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['dialogueEdits'], [edit])
        self.assertEqual(self.client.put(self.api + '/production-notes', json=value).status_code, 409)
        old_client = self.note | {'text': '保留台词修改', 'expectedText': self.note['text']}
        result = self.client.put(self.api + '/production-notes/export', json={'notes': [old_client], 'rounds': []})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['notes']['P001/一采/R001']['dialogueEdits'], [edit])

    def test_notes_are_scoped_persistent_and_conflict_safe(self):
        self.assertEqual(self.client.get(self.api + '/production-notes').json(), {'notes': {}, 'rounds': {}})
        response = self.client.put(self.api + '/production-notes', json=self.note)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.put(self.api + '/production-notes', json=self.note).status_code, 409)
        reopened = ProjectReviewNotes().read(business.notes_path(self.project))
        self.assertEqual(reopened.notes['P001/一采/R001'].text, self.note['text'])
        self.assertFalse((self.primary / 'projects/同名项目/06-视频生产').exists())
        change = dict(self.note, text='已核对', expectedText=self.note['text'])
        result = self.client.put(self.api + '/production-notes/export', json={'notes': [change], 'rounds': []})
        self.assertEqual(result.status_code, 200, result.text)

    def test_notes_reject_other_candidates_foreign_origins_and_archived_projects(self):
        self.assertEqual(self.client.put(self.api + '/production-notes', json=dict(self.note, run='R999')).status_code, 409)
        self.assertEqual(self.client.put(self.api + '/production-notes', json=self.note, headers={'Origin': 'https://unrelated.invalid'}).status_code, 403)
        (self.project / '.archived').write_text('历史只读')
        self.assertEqual(self.client.put(self.api + '/production-notes', json=self.note).status_code, 409)

    def test_paths_and_symlinks_cannot_leave_project(self):
        self.task['segment_plan']['targets'][0]['path'] = '../foreign.mp4'
        self.journal.write_text(json.dumps({'tasks': [self.task], 'accepted': [{'local_task_id': 'fixture'}]}))
        self.assertEqual(self.client.get(self.api + '/production').status_code, 409)
        self.assertEqual(self.client.get(self.api + '/production-context', params={'source': '../foreign', 'identity': 'EP001-C001-P001-R001-一采'}).status_code, 409)
        foreign = self.root / 'foreign-notes.json'
        foreign.write_text('private')
        (self.project / '06-视频生产/视频修改意见.json').symlink_to(foreign)
        self.assertEqual(self.client.get(self.api + '/production-notes').status_code, 503)
        self.assertEqual(foreign.read_text(), 'private')

    def test_changed_reference_is_not_shown_as_the_original(self):
        source = self.project / 'face.png'
        info = source.stat()
        records.write(self.directory / '执行检查报告.json', {'sources': {'face.png': [info.st_size, info.st_mtime_ns]}})
        source.write_bytes(b'changed source')
        value = self.client.get(self.api + '/production').json()['segments'][0]['videos'][0]['context']
        self.assertNotIn('url', value['references']['segment'][0])
        self.assertTrue(any('执行后变化' in issue for issue in value['issues']))

    def test_missing_request_does_not_use_prepared_workflow(self):
        archive = self.directory / records.ARCHIVE
        data = json.loads(archive.read_text())
        del data['records']['请求.json']
        archive.write_text(json.dumps(data))
        self.task['workflow'] = {'planned': 'never displayed as submitted'}
        self.journal.write_text(json.dumps({'tasks': [self.task], 'accepted': [{'local_task_id': 'fixture'}]}))
        context = self.client.get(self.api + '/production').json()['segments'][0]['videos'][0]['context']
        self.assertEqual(context['prompts']['english'], '')
        self.assertIn('实际提交请求尚未保存', context['issues'][0])

    def test_archive_rebases_only_the_explicit_original_root_in_memory(self):
        (self.project / 'README.md').write_text('当前目录仍为`/old/workspace/projects/同名项目/`。')
        contexts = {'version': {'references': {'common': [], 'segment': [
            {'file': '/old/workspace/projects/同名项目/face.png', 'label': 'Picture 1'},
            {'file': '/other/projects/同名项目/face.png', 'label': 'Picture 2'}]}}}
        value = business.historical_contexts(self.project, contexts)
        self.assertEqual(value['version']['references']['segment'][0]['file'], 'face.png')
        self.assertEqual(value['version']['references']['segment'][1]['file'], '/other/projects/同名项目/face.png')
        self.assertTrue(contexts['version']['references']['segment'][0]['file'].startswith('/old/'))
