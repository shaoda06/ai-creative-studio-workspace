"""Compact records preserve the task lifecycle; all remote calls are simulated."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import main
from backend.services.projects import ProjectStore
from backend.services.request_diagnostics import RequestDiagnostics
from tests.http_case import without_background_tasks
from tests.test_comfy_tasks import TaskTests
from tests.test_collection_retry import CollectionTests
from tests.test_technical_video import TechnicalVideoTests
import execution_records as recordio


class CompactTaskTests(TaskTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.data.record_format = 'compact'

    async def test_success_collects_exact_output_and_preserves_history(self):
        self.seed()
        remote = {'filename': 'real.png', 'subfolder': 'task', 'type': 'output'}
        result = {'state': 'success', 'history': {'status': {'completed': True}}, 'files': [
            {'node_id': '1', 'output_key': 'images', 'index': 0, 'file': remote}]}
        def download(client, args):
            target = Path(args.output)
            target.parent.mkdir()
            target.write_bytes(b'media')
            return {'path': str(target), 'remote': remote, 'bytes': 5}
        with patch.object(self.store.client, 'status', return_value=result), patch.object(self.store.client, 'download', download):
            self.assertTrue(await self.store.reconcile('task'))
        self.assertEqual(self.store.rows['task']['state']['status'], 'completed')
        self.assertEqual(recordio.read(self.record / '执行结果.json')['data']['history'], result['history'])
        self.assertTrue(recordio.exists(self.record / '取回响应.json'))
        self.assertFalse((self.record / '取回响应.json').exists())
        self.assertFalse((self.record / '后台过程记录.json').exists())
        self.assertTrue((self.record / recordio.ARCHIVE).is_file())

    async def test_unregistered_archive_cannot_be_reused_as_a_new_task(self):
        recordio.initialize(self.record)
        recordio.write(self.record / '后台任务状态.json', {'id': 'historical-task'}, compact=True)
        with self.assertRaisesRegex(self.store.client.ClientError, '已有后台登记记录'):
            self.store.validate_registration(self.data)

    async def test_restart_keeps_compact_layout(self):
        await self.store.prepare_only(self.data)
        result = await self.store.enqueue(self.data)
        key = result['local_task_id']
        await self.store.close()
        from backend.services.comfy_tasks import TaskStore
        self.store = TaskStore(self.root / 'runtime', self.root)
        self.assertEqual(self.store.rows[key]['input'].record_format, 'compact')
        self.assertTrue(recordio.exists(self.record / '执行检查报告.json'))
        self.assertFalse((self.record / '执行检查报告.json').is_file())

    async def test_virtual_entries_keep_preview_and_project_boundaries(self):
        await self.store.prepare_only(self.data)
        diagnostics = RequestDiagnostics(self.root / 'isolated-diagnostics')
        self.addCleanup(diagnostics.close_logs)
        with patch.object(main, 'store', ProjectStore(self.root / 'projects')), \
             patch.object(main.app.router, 'lifespan_context', without_background_tasks), \
             patch.object(main.app.state, 'request_diagnostics', diagnostics, create=True):
            with TestClient(main.app) as http:
                relative = (self.record / '执行检查报告.json').relative_to(self.project).as_posix()
                response = http.get('/api/projects/测试项目/files/' + relative)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['ok'])
                self.assertIn('sandbox', response.headers.get('content-security-policy', ''))
                self.assertEqual(http.get('/api/projects/测试项目/document', params={'path': relative}).status_code, 200)
                self.assertEqual(http.get('/api/projects/测试项目/files/.hidden/执行检查报告.json').status_code, 404)
                self.assertEqual(http.get('/api/projects/测试项目/document', params={'path': '../outside.json'}).status_code, 404)


class CompactCollectionTests(CollectionTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.data.record_format = 'compact'

    async def test_restart_retry_reads_terminal_result_from_compact_archive(self):
        self.seed('collection_failed')
        result = self.result()
        history = self.record / self.data.history_name
        recordio.write(history, {'data': result}, compact=True)
        self.assertFalse(history.exists())
        self.assertTrue(recordio.exists(history))
        await self.store.close()
        from backend.services.comfy_tasks import TaskStore
        self.store = TaskStore(self.root / 'runtime', self.root)
        with patch.object(self.store.client, 'download', side_effect=self.download) as download, \
             patch.object(self.store.client, 'submit') as submit, patch.object(self.store, 'queue_notice'):
            await self.store.retry_collection('task')
            await self.store.workers['task']
        self.assertEqual(self.store.rows['task']['state']['status'], 'completed')
        self.assertEqual(self.store.rows['task']['state']['prompt_id'], 'real-id')
        self.assertEqual(download.call_count, 1)
        submit.assert_not_called()


class CompactVideoTests(TechnicalVideoTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.data.record_format = 'compact'


class CompactArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        recordio.initialize(self.directory)

    def test_parallel_backend_writers_keep_every_entry(self):
        def write(number):
            recordio.write(self.directory / f'上传-{number}.json', {'index': number}, new=True, compact=True)
        with ThreadPoolExecutor(max_workers=8) as workers:
            list(workers.map(write, range(40)))
        self.assertEqual(len(list(self.directory.iterdir())), 1)
        for number in range(40):
            self.assertEqual(recordio.read(self.directory / f'上传-{number}.json'), {'index': number})

    def test_failed_replace_keeps_previous_archive(self):
        recordio.write(self.directory / '请求.json', {'prompt': 'approved'}, new=True, compact=True)
        original = (self.directory / recordio.ARCHIVE).read_bytes()
        with patch.object(recordio.os, 'replace', side_effect=OSError('isolated disk failure')):
            with self.assertRaises(OSError):
                recordio.write(self.directory / '提交响应.json', {'prompt_id': 'real'}, new=True, compact=True)
        self.assertEqual((self.directory / recordio.ARCHIVE).read_bytes(), original)
        self.assertFalse(list(self.directory.glob('.execution-*')))

    def test_submission_entry_cannot_be_overwritten(self):
        file = self.directory / '请求.json'
        recordio.write(file, {'prompt': 'approved'}, new=True, compact=True)
        with self.assertRaises(FileExistsError):
            recordio.write(file, {'prompt': 'changed'}, new=True, compact=True)
        self.assertEqual(recordio.read(file), {'prompt': 'approved'})

    def test_other_entries_do_not_invalidate_download_proof(self):
        file = self.directory / '取回.json'
        recordio.write(file, {'bytes': 5}, new=True, compact=True)
        original = recordio.entry_stamp(file)
        recordio.write(self.directory / '后台任务状态.json', {'status': 'completed'}, compact=True)
        self.assertEqual(recordio.entry_stamp(file), original)

    def test_legacy_read_does_not_create_archive(self):
        old = self.directory / 'old'
        old.mkdir()
        file = old / '请求.json'
        file.write_text('{"prompt":"historical"}')
        self.assertEqual(recordio.read(file), {'prompt': 'historical'})
        self.assertFalse((old / recordio.ARCHIVE).exists())


class CompactSubmissionEvidenceTests(CompactArchiveTests):
    def test_post_body_is_preserved_and_repeated_submit_is_blocked(self):
        import argparse
        import hashlib
        from unittest.mock import Mock
        import comfyui_client as client
        remote = Mock(url='http://isolated.invalid')
        remote.json.return_value = {'prompt_id': 'isolated-task'}
        args = argparse.Namespace(record_dir=str(self.directory), attempt_name='提交尝试.json',
            request_name='请求.json', response_name='提交响应.json', record_format='compact')
        workflow = {'1': {'class_type': 'SaveImage', 'inputs': {'seed': 9223372036854775807}}}
        client.submit(remote, args, workflow, 'same-client')
        body = remote.json.call_args.args[1]
        self.assertEqual(recordio.read(self.directory / '请求.json'), recordio.strict_json(body))
        self.assertEqual(recordio.read(self.directory / '提交尝试.json')['request_sha256'], hashlib.sha256(body).hexdigest())
        with self.assertRaises(client.ClientError):
            client.submit(remote, args, workflow, 'same-client')
        self.assertEqual(remote.json.call_count, 1)
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), ['执行档案.json', '提交尝试.json'])

    def test_export_cannot_shadow_an_existing_logical_entry(self):
        recordio.write(self.directory / '请求.json', {'prompt': 'approved'}, new=True, compact=True)
        with patch('sys.argv', ['execution_records.py', 'export', str(self.directory / '请求.json'),
                                '--output', str(self.directory / '请求.json')]):
            with self.assertRaises(FileExistsError):
                recordio.main()
        self.assertFalse((self.directory / '请求.json').exists())

    def test_corrupt_archive_fails_instead_of_silently_resetting_evidence(self):
        archive = self.directory / recordio.ARCHIVE
        archive.write_text('{"records":{},"records":{}}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
            recordio.write(self.directory / '请求.json', {'prompt': 'new'}, new=True, compact=True)
        self.assertEqual(archive.read_text(), '{"records":{},"records":{}}')
