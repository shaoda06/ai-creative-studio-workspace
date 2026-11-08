from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from io import BytesIO
import json
from pathlib import Path
import tempfile
from threading import Barrier, local
import unittest
from unittest.mock import patch
from urllib.parse import quote
import wave

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from backend.routes.project_resources import create_router
from backend.services.project_files import ProjectFiles
import media_files
import project_resources as resources


class ProjectResourceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        app = FastAPI()
        app.include_router(create_router(lambda request: ProjectFiles(self.root), lambda: None))
        self.client = TestClient(app)
        self.url = '/api/projects/project/resources'

    def png(self, color):
        stream = BytesIO(); Image.new('RGB', (12, 8), color).save(stream, format='PNG')
        return stream.getvalue()

    def test_uploaded_reference_and_revision_keep_original_and_business_records(self):
        first = self.client.post(self.url, files={'file': ('参考图.png', self.png('red'))}, data={'upload_key': 'one'})
        self.assertEqual(first.status_code, 200, first.text)
        one = first.json()
        repeated = self.client.post(self.url, files={'file': ('参考图.png', self.png('red'))}, data={'upload_key': 'one'})
        self.assertEqual(repeated.json(), one)
        second = self.client.post(self.url, files={'file': ('修改图.png', self.png('blue'))},
                                  data={'resource_id': one['resource_id'], 'parent_version': one['version'], 'upload_key': 'two'})
        self.assertEqual(second.status_code, 200, second.text)
        two = second.json()
        self.assertEqual(two['resource_id'], one['resource_id'])
        self.assertEqual(two['version'], 'V002')
        draft = self.project / '审核.md'
        draft.write_text(f'# 图片审核\n\n## 本轮意见\n\n资源：[修改2]({quote(two["file"],safe="/")})；未通过，手部需调整。\n')
        detail = self.client.get(self.url + '/' + one['resource_id']).json()
        self.assertEqual(len(detail['versions']), 2)
        self.assertIn('未通过', detail['versions'][1]['uses'][0]['excerpt'])
        self.assertIn('资源/图片/', detail['versions'][1]['media']['key'])
        self.assertNotIn('approved', detail)
        listing = self.client.get(self.url + '?kind=图片&q=参考').json()
        self.assertEqual(listing['total'], 1)
        self.assertEqual(listing['items'][0]['version_count'], 2)
        self.assertEqual((self.project / one['file']).read_bytes(), self.png('red'))

    def test_concurrent_uploads_keep_distinct_versions_and_share_readonly_data(self):
        resources.initialize(self.project, managed=True)
        original_lock = resources.index_lock
        original_copy = media_files.shutil.copyfile
        held = local()
        arriving = Barrier(2)
        raw = self.png('red')

        @contextmanager
        def tracked_lock(project):
            with original_lock(project) as index:
                held.project = Path(project)
                try:
                    yield index
                finally:
                    del held.project

        def copy(source, target):
            self.assertEqual(getattr(held, 'project', None), self.project)
            return original_copy(source, target)

        def upload(key):
            arriving.wait(timeout=5)
            return self.client.post(self.url, files={'file': (key + '.png', raw)}, data={'upload_key': key})

        with patch.object(resources, 'index_lock', tracked_lock), \
             patch.object(media_files.shutil, 'copyfile', side_effect=copy) as copied, \
             ThreadPoolExecutor(max_workers=2) as workers:
            responses = list(workers.map(upload, ('first', 'second')))
        self.assertEqual([response.status_code for response in responses], [200, 200])
        copied.assert_called_once()
        first, second = [response.json() for response in responses]
        self.assertNotEqual(first['resource_id'], second['resource_id'])
        self.assertNotEqual(first['file'], second['file'])
        self.assertTrue((self.project / first['file']).samefile(self.project / second['file']))
        for ref in (first, second):
            version = self.client.get(self.url + '/' + ref['resource_id']).json()['versions'][0]
            self.assertEqual((version['file'], version['version'], version['origin']),
                             (ref['file'], ref['version'], 'user_upload'))
            self.assertEqual((self.project / ref['file']).read_bytes(), raw)
            self.assertEqual((self.project / ref['file']).stat().st_mode & 0o222, 0)

    def test_audio_upload_has_real_duration_and_no_invented_generation(self):
        stream = BytesIO()
        with wave.open(stream, 'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(8000); audio.writeframes(b'\0\0' * 800)
        response = self.client.post(self.url, files={'file': ('参考音色.wav', stream.getvalue())})
        self.assertEqual(response.status_code, 200, response.text)
        ref = response.json()
        detail = self.client.get(self.url + '/' + ref['resource_id']).json()
        version = detail['versions'][0]
        self.assertEqual(version['origin'], 'user_upload')
        self.assertAlmostEqual(version['facts']['duration_seconds'], .1)
        self.assertIsNone(version['producer'])
        self.assertEqual(version['media']['kind'], 'audio')

    def test_boundary_bad_format_and_archived_project(self):
        self.assertEqual(self.client.post(self.url, files={'file': ('../outside.png', self.png('red'))}).status_code, 422)
        self.assertEqual(self.client.post(self.url, files={'file': ('bad.png', b'not-an-image')}).status_code, 422)
        (self.project / '.archived').write_text('read-only')
        self.assertEqual(self.client.post(self.url, files={'file': ('test.png', self.png('red'))}).status_code, 409)

    def test_prepared_outputs_and_inputs_use_exact_resource_versions(self):
        resources.initialize(self.project, managed=True)
        source = self.root / 'original.png'; source.write_bytes(self.png('red'))
        first = resources.register(self.project, source, key='base')
        payload = {'task_type': 'image-upscale', 'record_dir': '执行附件/修图1', 'outputs': [{'path': '候选/修图1.png'}],
                   'uploads': [{'file': first['file']}], 'image_plan': {'images': [{'path': '候选/修图1.png', 'width': 24, 'height': 16}],
                    'upscale': {'source': first['file'], 'formal': '参考图/正式.png'}, 'resource_id': first['resource_id']}}
        routed = resources.route_task(self.project, payload)
        target = routed['outputs'][0]
        self.assertEqual(target['resource_id'], first['resource_id'])
        self.assertEqual(target['version'], 'V002')
        self.assertEqual(routed['image_plan']['upscale']['formal'], resources.relative(self.project,target['path']))
        self.assertEqual(routed['uploads'][0]['resource']['version'], 'V001')
