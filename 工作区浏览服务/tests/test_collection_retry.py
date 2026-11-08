"""Automatic collection retries against temporary evidence and simulated HTTP only."""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import errno
import http.client
import io
import json
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import AsyncMock, patch
import urllib.error

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from backend.routes.project_resources import create_router
from backend.services import comfy_tasks as t
from backend.services.collection_retry import failure
from backend.services.project_files import ProjectFiles
from backend.services.task_details import task_detail
from tests import test_comfy_tasks as base


import execution_records as recordio
import media_files

class CollectionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = base.TaskTests.asyncSetUp
    asyncTearDown = base.TaskTests.asyncTearDown
    seed = base.TaskTests.seed

    def result(self, files=1):
        return {'state': 'success', 'history': {}, 'files': [
            {'node_id': '1', 'output_key': 'images', 'index': index,
             'file': {'filename': f'{index}.png', 'subfolder': '', 'type': 'output'}} for index in range(files)]}

    def download(self, remote, args):
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'media')
        return {'path': str(target), 'remote': {'filename': args.filename, 'subfolder': args.subfolder, 'type': args.type}, 'bytes': 5}

    async def test_transient_failure_recovers_after_10_30_60_with_one_final_notice(self):
        self.seed('collecting')
        result = self.result()
        (self.record / self.data.history_name).write_text(json.dumps({'data': result}), 'utf8')
        waits = []
        async def waiting(seconds):
            waits.append(seconds)
            self.assertEqual(self.store.rows['task']['state']['status'], 'collecting')
            self.assertEqual(notice.call_count, 0)
            self.assertIsNotNone(self.store.rows['task']['state']['collection_next_retry_at'])
            with self.assertRaises(ValueError):
                await self.store.retry_collection('task')
        calls = 0
        def flaky(remote, args):
            nonlocal calls
            calls += 1
            if calls <= 3:
                raise t.client.ClientError('http_error', 'temporarily unavailable', http_status=503)
            return self.download(remote, args)
        with patch.object(t.client, 'download', flaky), patch.object(t.asyncio, 'sleep', waiting), \
                patch.object(self.store, 'queue_notice') as notice, patch.object(t.client, 'submit') as post:
            await self.store.collect_saved('task')
            self.assertEqual(notice.call_count, 1)
            post.assert_not_called()
        self.assertEqual(calls, 4)
        for actual, expected in zip(waits, (10, 30, 60)):
            self.assertAlmostEqual(actual, expected, delta=.3)
        state = self.store.rows['task']['state']
        self.assertEqual((state['status'], state['collection_attempt'], state['collection_auto_retry']), ('completed', 4, 3))
        events = recordio.read(self.record / '后台过程记录.json')
        self.assertEqual([event['delay_seconds'] for event in events if event['result'] == 'scheduled'], [10, 30, 60])
        self.assertEqual([event['failures'][0]['http_status'] for event in events if event['result'] == 'attempt_failed'], [503] * 3)

    async def test_exhaustion_notifies_once_and_agent_starts_new_budget(self):
        self.seed('collecting')
        (self.record / self.data.history_name).write_text(json.dumps({'data': self.result()}), 'utf8')
        with patch.object(t.client, 'download', side_effect=ConnectionResetError('connection lost')) as download, \
                patch.object(t.asyncio, 'sleep', AsyncMock()) as sleep, patch.object(self.store, 'queue_notice') as notice:
            await self.store.collect_saved('task')
            self.assertEqual((download.call_count, sleep.await_count, notice.call_count), (4, 3, 1))
        state = self.store.rows['task']['state']
        self.assertEqual((state['status'], state['collection_retry_stop']), ('collection_failed', 'exhausted'))
        self.assertEqual(self.store.result_report(['task'])['tasks'][0]['collection_auto_retry'], 3)
        with patch.object(t.client, 'download', self.download), patch.object(self.store, 'queue_notice') as notice:
            await self.store.retry_collection('task')
            await self.store.workers['task']
            self.assertEqual(notice.call_count, 1)
        self.assertEqual((state['status'], state['collection_auto_retry'], state['collection_attempt']), ('completed', 0, 5))

    async def test_permanent_errors_fail_once_without_sleep(self):
        cases = [t.client.ClientError('http_error', 'denied', http_status=code) for code in (400, 401, 403, 404, 422, 501)]
        cases += [PermissionError('no permission'), OSError(errno.ENOSPC, 'disk full'),
                  t.client.ClientError('file_exists', 'do not overwrite'), ValueError('receipt mismatch')]
        self.seed('collecting')
        for error in cases:
            with self.subTest(error=str(error)), patch.object(t.client, 'download', side_effect=error) as download, \
                    patch.object(t.asyncio, 'sleep', AsyncMock()) as sleep:
                await self.store.finish_collection('task', self.result())
                self.assertEqual(download.call_count, 1)
                sleep.assert_not_awaited()
                self.assertEqual(self.store.rows['task']['state']['collection_retry_stop'], 'requires_attention')

    async def test_mixed_temporary_and_missing_output_stops_automatic_retry(self):
        self.seed('collecting')
        self.data.outputs.append(self.data.outputs[0].model_copy(update={'index': 1,
            'path': str(self.project / '候选/second.png'), 'response_name': 'second.json'}))
        with patch.object(t.client, 'download', side_effect=TimeoutError('timeout')) as download, \
                patch.object(t.asyncio, 'sleep', AsyncMock()) as sleep:
            await self.store.finish_collection('task', self.result())
            self.assertEqual(download.call_count, 1)
            sleep.assert_not_awaited()
        issues = self.store.rows['task']['state']['collection_errors']
        self.assertEqual([item['retryable'] for item in issues], [True, False])

    async def test_successful_files_are_reused_and_original_generation_end_is_preserved(self):
        self.seed('collecting')
        self.store.save('task', ended_at='2026-10-10T22:00:00+08:00', expected=2)
        self.data.outputs.append(self.data.outputs[0].model_copy(update={'index': 1,
            'path': str(self.project / '候选/second.png'), 'response_name': 'second.json'}))
        counts = {'0.png': 0, '1.png': 0}
        def flaky(remote, args):
            counts[args.filename] += 1
            if args.filename == '1.png' and counts[args.filename] == 1:
                raise TimeoutError('timeout')
            return self.download(remote, args)
        with patch.object(t.client, 'download', flaky), patch.object(t.asyncio, 'sleep', AsyncMock()):
            await self.store.finish_collection('task', self.result(2))
        self.assertEqual(counts, {'0.png': 1, '1.png': 2})
        state = self.store.rows['task']['state']
        self.assertEqual((state['status'], state['collected']), ('completed', 2))
        self.assertEqual(state['ended_at'], '2026-10-10T22:00:00+08:00')

    async def test_managed_outputs_keep_distinct_versions_and_receipts_on_retry(self):
        t.resourceio.initialize(self.project, managed=True)
        first = self.data.outputs[0]
        first.resource_key = '图片/同一候选目标'
        self.data.outputs.append(first.model_copy(update={'index': 1,
            'path': str(self.project / '候选/second.png'), 'response_name': 'second.json'}))
        self.data = t.TaskInput.model_validate(t.resourceio.route_task(self.project, self.data.model_dump()))
        self.seed('collecting')
        self.store.save('task', expected=2)
        png = io.BytesIO()
        Image.new('RGB', (8, 8), 'red').save(png, format='PNG')
        calls = []

        def download(remote, args):
            calls.append((args.filename, args.output))
            if args.filename == '1.png' and len(calls) == 2:
                raise TimeoutError('retry the same output')
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(png.getvalue())
            return {'path': str(target), 'bytes': target.stat().st_size,
                    'remote': {key: getattr(args, key) for key in ('filename', 'subfolder', 'type')}}

        result = self.result(2)
        with patch.object(t.client, 'download', download), patch.object(t.asyncio, 'sleep', AsyncMock()):
            await self.store.finish_collection('task', result)
            self.assertEqual(await self.store.collect('task', result), [])
        self.assertEqual(self.store.rows['task']['state']['status'], 'completed')
        first, second = self.data.outputs
        self.assertEqual(calls, [('0.png', first.path), ('1.png', second.path), ('1.png', second.path)])
        self.assertEqual((first.resource_id, first.version, second.resource_id, second.version),
                         (first.resource_id, 'V001', first.resource_id, 'V002'))
        self.assertTrue(Path(first.path).samefile(second.path))
        self.assertEqual(len(t.resourceio.read_index(self.project)['files']), 2)
        for index, output in enumerate((first, second)):
            receipt = recordio.read(self.record / output.response_name)['data']
            self.assertEqual(receipt['remote']['filename'], f'{index}.png')
            self.assertEqual(self.project / receipt['path'], Path(output.path))

    async def test_upload_overlaps_background_collection_without_extra_media_data(self):
        t.resourceio.initialize(self.project, managed=True)
        self.data = t.TaskInput.model_validate(t.resourceio.route_task(self.project, self.data.model_dump()))
        self.seed('collecting')
        target = Path(self.data.outputs[0].path)
        app = FastAPI()
        app.include_router(create_router(lambda request: ProjectFiles(self.project.parent), lambda: None))
        http = TestClient(app)
        png = io.BytesIO()
        Image.new('RGB', (8, 8), 'red').save(png, format='PNG')
        raw = png.getvalue()
        copying, collecting, release = Event(), Event(), Event()
        original_copy = media_files.shutil.copyfile
        original_finish = t.resourceio.finish

        def copy(source, destination):
            copying.set()
            if not release.wait(timeout=8):
                raise TimeoutError('upload did not resume')
            return original_copy(source, destination)

        def finish(project, path, **options):
            if Path(path) == target:
                collecting.set()
            return original_finish(project, path, **options)

        def download(remote, args):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            return {'path': str(target), 'bytes': len(raw),
                    'remote': {key: getattr(args, key) for key in ('filename', 'subfolder', 'type')}}

        url = '/api/projects/' + self.project.name + '/resources'
        with patch.object(media_files.shutil, 'copyfile', side_effect=copy), \
             patch.object(t.resourceio, 'finish', side_effect=finish), patch.object(t.client, 'download', side_effect=download):
            upload = asyncio.create_task(asyncio.to_thread(http.post, url, files={'file': ('上传.png', raw)}))
            try:
                self.assertTrue(await asyncio.to_thread(copying.wait, 5))
                collect = asyncio.create_task(self.store.collect('task', self.result()))
                self.assertTrue(await asyncio.to_thread(collecting.wait, 5))
            finally:
                release.set()
            response, problems = await asyncio.gather(upload, collect)

        self.assertEqual(problems, [])
        self.assertEqual(response.status_code, 200, response.text)
        imported = response.json()
        uploaded = self.project / imported['file']
        self.assertNotEqual(uploaded, target)
        self.assertTrue(uploaded.samefile(target))
        version = t.resourceio.reference(self.project, target)
        self.assertNotEqual(t.resourceio.label(version), t.resourceio.label(imported))
        self.assertEqual(version['producer'], '执行附件/任务001')
        self.assertEqual(t.resourceio.reference(self.project, uploaded)['origin'], 'user_upload')
        receipt = recordio.read(self.record / self.data.outputs[0].response_name)['data']
        self.assertEqual((self.project / receipt['path'], receipt['remote']['filename']), (target, '0.png'))
        self.assertEqual(uploaded.read_bytes(), raw)

    async def test_429_uses_retry_after_and_malformed_header_requires_attention(self):
        self.seed('collecting')
        first = t.client.ClientError('http_error', 'limited', http_status=429, retry_after='125', response={'reason': 'rate limited'})
        issue = failure(first, t.client.ClientError)
        self.assertEqual(issue['response'], {'reason': 'rate limited'})
        self.assertEqual(issue['retry_after'], '125')
        calls = 0
        def limited(remote, args):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise first
            return self.download(remote, args)
        with patch.object(t.client, 'download', limited), patch.object(t.asyncio, 'sleep', AsyncMock()) as sleep:
            await self.store.finish_collection('task', self.result())
            self.assertAlmostEqual(sleep.await_args.args[0], 125, delta=.3)
        dated = failure(t.client.ClientError('http_error', 'limited', http_status=429,
            retry_after=format_datetime(datetime.now(timezone.utc) + timedelta(minutes=3))), t.client.ClientError)
        self.assertGreater(dated['retry_after_seconds'], 178)
        invalid = failure(t.client.ClientError('http_error', 'limited', http_status=429, retry_after='bad-date'), t.client.ClientError)
        self.assertFalse(invalid['retryable'])
        self.assertIn('格式无效', invalid['error'])

    async def test_restart_keeps_used_retries_and_resumes_existing_deadline(self):
        self.seed('collecting')
        self.store.save('task', source_session_name='测试会话')
        (self.record / self.data.history_name).write_text(json.dumps({'data': self.result()}), 'utf8')
        blocked = asyncio.Event()
        async def waiting(seconds):
            if self.store.rows['task']['state']['collection_auto_retry'] == 2:
                blocked.set()
                await asyncio.Event().wait()
        with patch.object(t.client, 'download', side_effect=TimeoutError('timeout')), patch.object(t.asyncio, 'sleep', waiting):
            self.store.workers['task'] = asyncio.create_task(self.store.collect_saved('task'))
            await asyncio.wait_for(blocked.wait(), 5)
            deadline = self.store.rows['task']['state']['collection_next_retry_at']
            await self.store.close()
        self.store = t.TaskStore(self.root / 'runtime', self.root)
        state = self.store.rows['task']['state']
        self.assertEqual((state['collection_auto_retry'], state['collection_attempt']), (2, 3))
        self.assertEqual(state['collection_next_retry_at'], deadline)
        with patch.object(t.client, 'download', self.download), patch.object(t.asyncio, 'sleep', AsyncMock()) as sleep, \
                patch.object(self.store, 'queue_notice') as notice, patch.object(self.store, 'schedule', AsyncMock()), \
                patch.object(t.client, 'submit') as post:
            await self.store.start()
            await self.store.workers['task']
            self.assertLessEqual(sleep.await_args.args[0], 60)
            self.assertGreater(sleep.await_args.args[0], 55)
            self.assertEqual(notice.call_count, 1)
            post.assert_not_called()
        self.assertEqual((state['status'], state['collection_auto_retry'], state['collection_attempt']), ('completed', 3, 4))

    async def test_overdue_last_retry_runs_once_then_stops_without_resetting_budget(self):
        self.seed('collecting')
        self.store.save('task', collection_attempt=3, collection_auto_retry=2,
                        collection_next_retry_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
        with patch.object(t.client, 'download', side_effect=TimeoutError('timeout')) as download, \
                patch.object(t.asyncio, 'sleep', AsyncMock()) as sleep:
            await self.store.finish_collection('task', self.result())
        self.assertEqual(download.call_count, 1)
        sleep.assert_not_awaited()
        state = self.store.rows['task']['state']
        self.assertEqual((state['status'], state['collection_auto_retry'], state['collection_attempt']), ('collection_failed', 3, 4))

    async def test_director_final_outputs_share_retry_policy_and_skip_successful_file(self):
        self.seed('collecting')
        self.data.task_type = 'video-second-pass'
        self.data.segment_plan = t.segments.SegmentPlan(director_node='d', report_node='r', output_root='/comfy/output')
        self.data.outputs = []
        self.data.workflow['d'] = {'inputs': {'timeline_data': json.dumps({'segments': [{}, {}]})}}
        items = [{'index': index, 'identity': f'EP003-C001-P00{index + 1}-R001-二采',
                  'candidate': self.project / f'候选/video-{index}.mp4', 'response_name': f'video-{index}.json'} for index in (0, 1)]
        result = {'state': 'success', 'history': {'outputs': {'r': {'text': [
            'Segment 1: mp4 saved → /comfy/output/minimax_seg_export/seg_0000.mp4\n'
            'Segment 2: mp4 saved → /comfy/output/minimax_seg_export/seg_0001.mp4']}}}}
        counts = {'seg_0000.mp4': 0, 'seg_0001.mp4': 0}
        def flaky(remote, args):
            counts[args.filename] += 1
            if args.filename == 'seg_0001.mp4' and counts[args.filename] == 1:
                raise t.client.ClientError('incomplete_download', 'truncated')
            return self.download(remote, args)
        with patch.object(t.segments, 'targets', return_value=items), patch.object(t.client, 'download', flaky), \
                patch.object(t.asyncio, 'sleep', AsyncMock()):
            await self.store.finish_collection('task', result)
        self.assertEqual(counts, {'seg_0000.mp4': 1, 'seg_0001.mp4': 2})
        self.assertEqual(self.store.rows['task']['state']['status'], 'completed')
        events = recordio.read(self.record / '后台过程记录.json')
        successes = [event for event in events if event['stage'] == 'download' and event['result'] == 'success']
        self.assertEqual(len(successes), 2)

    async def test_generation_failure_never_downloads_or_retries(self):
        self.seed()
        with patch.object(t.client, 'download') as download, patch.object(t.asyncio, 'sleep', AsyncMock()) as sleep:
            await self.store.finish_collection('task', {'state': 'failed', 'history': {}})
            download.assert_not_called()
            sleep.assert_not_awaited()
        self.assertEqual(self.store.rows['task']['state']['status'], 'failed')

    async def test_detail_and_history_expose_pending_retry_without_terminal_status(self):
        self.seed('collecting')
        self.store.save('task', collection_attempt=2, collection_auto_retry=1,
                        collection_next_retry_at=t.client.now(), error='HTTP 503', failure_stage='collection')
        self.store.record('task', 'collection_retry', 'scheduled', auto_retry=2, attempt=2,
                          delay_seconds=30, next_retry_at=t.client.now(), error='HTTP 503')
        detail = await task_detail(self.store, 'task')
        self.assertEqual(detail['summary']['collection_auto_retry'], 1)
        self.assertEqual(detail['events'][0]['delay_seconds'], 30)
        from backend.services.task_history import task_history
        self.assertEqual(task_history(self.store, self.data.url)['items'][0]['collection_auto_retry'], 1)
        self.assertEqual(task_history(self.store, self.data.url, result='abnormal')['total'], 0)


class DownloadBoundaryTests(unittest.TestCase):
    def test_http_header_is_preserved_and_read_interruption_is_transport_failure(self):
        remote = t.client.Client('http://test.invalid', 30)
        error = urllib.error.HTTPError('http://test.invalid/view', 429, 'limited', {'Retry-After': '30'}, io.BytesIO(b'{}'))
        with patch.object(remote.opener, 'open', side_effect=error):
            with self.assertRaises(t.client.ClientError) as caught:
                remote.open('/view')
        self.assertEqual(caught.exception.details['retry_after'], '30')
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temporary:
            response = unittest.mock.MagicMock()
            response.__enter__.return_value = response
            response.headers = {'Content-Length': '10'}
            response.read.side_effect = http.client.IncompleteRead(b'abc', 7)
            output = Path(temporary) / 'result.png'
            with patch.object(remote, 'open', return_value=response):
                with self.assertRaises(t.client.ClientError) as caught:
                    t.client.download(remote, argparse.Namespace(filename='a.png', subfolder='', type='output', output=str(output), sha256=None))
            self.assertEqual(caught.exception.code, 'transport_error')
            self.assertFalse(output.exists())
            self.assertFalse(list(Path(temporary).glob('.comfy-download-*')))
