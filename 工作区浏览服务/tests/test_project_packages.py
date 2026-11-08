"""Project-space package requests use scoped manifests and the existing export tool."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import main
from backend.services import episode_downloads
from backend.services.projects import ProjectStore
from backend.services.workspaces import Workspaces
from tests.http_case import HttpTestCase


class ProjectPackageTests(HttpTestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.primary, self.iris = self.root/'primary', self.root/'iris'
        for root in [self.primary, self.iris]:
            (root/'projects/客户项目').mkdir(parents=True)
        self.project = self.iris/'projects/客户项目'
        for name in ['B 中文.mp4', 'A.mp4']:
            (self.project/name).write_bytes(b'HTTP fixture only; exporter mocked')
        self.manifest = self.project/'交接.jianying.json'
        self.spec = {'name': '客户 剪映交接', 'media': [
            {'file': 'B 中文.mp4', 'member': 'B 中文.mp4'},
            {'file': 'A.mp4', 'member': '参考/A.mp4', 'timeline': False}]}
        self.write()
        runtime = self.primary/'工作区浏览服务/runtime'
        runtime.mkdir(parents=True)
        (runtime/'workspaces.json').write_text(json.dumps([{'id':'commercial','name':'Iris','path':str(self.iris)}]))
        spaces = Workspaces(self.primary, runtime, ProjectStore(self.primary/'projects'), 'test')
        for space in spaces.items.values():
            space.tasks = SimpleNamespace(token=space.id, public=lambda **kwargs: {'tasks': []})
        self.downloads = self.root/'downloads'
        for override in [patch.object(main.app.state, 'workspaces', spaces, create=True),
                         patch.object(main.app.state, 'comfy_tasks', spaces.get('nora').tasks, create=True),
                         patch.object(episode_downloads, 'DOWNLOAD_DIRECTORY', self.downloads)]:
            override.start(); self.addCleanup(override.stop)
        self.client = TestClient(main.app, client=('127.0.0.1',50000))
        self.addCleanup(self.client.close)
        self.base='/api/workspaces/commercial/projects/客户项目'

    def write(self):
        self.manifest.write_text(json.dumps(self.spec, ensure_ascii=False))

    def export(self, files, path, name, timeline_members, archive_format):
        Path(path).write_bytes(b'isolated HTTP archive fixture')

    def test_listing_does_not_export_and_download_keeps_order_scope_and_timeline(self):
        with patch.object(episode_downloads.jianying_export, 'export_archive', side_effect=self.export) as export:
            data=self.client.get(self.base).json()
            item=next(item for item in data['files'] if item['name']==self.manifest.name)
            self.assertTrue(item['jianying']['jypack'].startswith('/api/workspaces/commercial/'))
            export.assert_not_called()
            response=self.client.get(item['jianying']['jypack'])
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['content-type'],'application/vnd.bytedance.jypack')
            args=export.call_args.args
            self.assertEqual(args[0],[(self.project/'B 中文.mp4','B 中文.mp4'),(self.project/'A.mp4','参考/A.mp4')])
            self.assertEqual(args[3],{'B 中文.mp4'})
            self.assertEqual(args[4],'jypack')
            self.assertEqual(list(self.downloads.iterdir()),[])
            self.assertEqual(self.client.get(item['jianying']['zip']).status_code,200)
            self.assertEqual(export.call_args.args[4],'zip')
            self.assertEqual(list(self.downloads.iterdir()),[])

    def test_common_endpoint_defaults_to_jypack(self):
        with patch.object(episode_downloads.jianying_export,'export_archive',side_effect=self.export) as export:
            response=self.client.get(self.base+'/jianying-download',params={'path':self.manifest.name})
        self.assertEqual(response.status_code,200)
        self.assertEqual(export.call_args.args[4],'jypack')

    def test_missing_media_stops_before_export_and_recovers_from_same_manifest(self):
        missing=self.project/'B 中文.mp4';original=missing.read_bytes();missing.unlink()
        with patch.object(episode_downloads.jianying_export,'export_archive',side_effect=self.export) as export:
            self.assertEqual(self.client.get(self.base+'/jianying-download',params={'path':self.manifest.name}).status_code,404)
            export.assert_not_called()
            missing.write_bytes(original)
            self.assertEqual(self.client.get(self.base+'/jianying-download',params={'path':self.manifest.name}).status_code,200)
            self.assertEqual(export.call_count,1)

    def test_manifest_and_media_cannot_cross_projects(self):
        (self.iris/'projects/另一个订单').mkdir()
        (self.iris/'projects/另一个订单/secret.mp4').write_bytes(b'private')
        self.spec['media'][0]['file']='../另一个订单/secret.mp4';self.write()
        with patch.object(episode_downloads.jianying_export,'export_archive') as export:
            self.assertEqual(self.client.get(self.base+'/jianying-download',params={'path':self.manifest.name}).status_code,404)
            self.assertEqual(self.client.get(self.base+'/jianying-download',params={'path':'../另一个订单/secret.jianying.json'}).status_code,404)
            export.assert_not_called()

    def test_invalid_manifest_extension_and_format_are_rejected(self):
        for content in ['{', '{"name":"missing media"}', '{"name":"x","media":[]}']:
            self.manifest.write_text(content)
            self.assertEqual(self.client.get(self.base+'/jianying-download',params={'path':self.manifest.name}).status_code,409)
        (self.project/'not-a-plan.json').write_text('{}')
        self.assertEqual(self.client.get(self.base+'/jianying-download',params={'path':'not-a-plan.json'}).status_code,409)
        self.assertEqual(self.client.get(self.base+'/jianying-download',params={'path':self.manifest.name,'format':'other'}).status_code,422)

    def test_export_failure_cleans_partial_output_and_retry_reuses_manifest(self):
        def failed(*args):
            Path(args[1]).write_bytes(b'partial')
            raise ValueError('isolated exporter failure')
        with patch.object(episode_downloads.jianying_export,'export_archive',side_effect=failed):
            response=self.client.get(self.base+'/jianying-download',params={'path':self.manifest.name})
        self.assertEqual(response.status_code,409)
        self.assertIn('isolated exporter failure',response.json()['detail'])
        self.assertEqual(list(self.downloads.iterdir()),[])
        with patch.object(episode_downloads.jianying_export,'export_archive',side_effect=self.export):
            self.assertEqual(self.client.get(self.base+'/jianying-download',params={'path':self.manifest.name}).status_code,200)
        self.assertEqual(list(self.downloads.iterdir()),[])
