"""Native director downloads use isolated inputs and a simulated ComfyUI."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import main
from backend.services import director_packages, episode_downloads
from backend.services.projects import ProjectStore
from backend.services.workspaces import Workspaces
from tests.http_case import HttpTestCase
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.agents/skills/nora-drama-production/scripts'))
from test_scene_finalize import NativeClient
import scene_finalize
import video_approve

class DirectorPackageTests(HttpTestCase):
    def setUp(self):
        super().setUp()
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
        self.primary=self.root/'Nora';self.iris=self.root/'Iris'
        self.project=self.iris/'projects/订单';self.project.mkdir(parents=True)
        (self.primary/'projects').mkdir(parents=True)
        runtime=self.root/'runtime';runtime.mkdir()
        (runtime/'workspaces.json').write_text(json.dumps([{'id':'commercial','name':'Iris','path':str(self.iris)}]))
        self.store=ProjectStore(self.primary/'projects');self.spaces=Workspaces(self.primary,runtime,self.store,'test')
        self.downloads=self.root/'downloads'
        timeline={'output':{'prefix':'test'},'global':{'prompt':'frozen prompt','refs':[{'index':0,'imageFile':'ref.png'}]},'segments':[]}
        self.spec={'name':'原生导演包.mmxpack.zip','node_id':'1','url':'http://example.invalid',
            'workflow':{'1':{'class_type':'MiniMaxH3Director','inputs':{'seed':9223372036854775807,'timeline_data':json.dumps(timeline)}}},
            'media':{'ref.png':'原图.png'}}
        self.manifest=self.project/'原生导演包.director.json';self.write()
        (self.project/'原图.png').write_bytes(b'frozen bytes')
        NativeClient.calls=[];NativeClient.media={'ref.png':b'frozen bytes'};NativeClient.missing=NativeClient.corrupt=False
        for override in (patch.object(main.app.state,'workspaces',self.spaces,create=True),patch.object(main,'store',self.store),
            patch.object(episode_downloads,'DOWNLOAD_DIRECTORY',self.downloads),
            patch.object(director_packages.director_export.comfyui_config,'client_for',return_value=NativeClient('http://example.invalid',30))):
            override.start();self.addCleanup(override.stop)
        self.client=TestClient(main.app,base_url='http://localhost',client=('127.0.0.1',50000));self.addCleanup(self.client.close)
        self.base='/api/workspaces/commercial/projects/订单';self.url=self.base+'/director-download'

    def write(self):
        self.manifest.write_text(json.dumps(self.spec,ensure_ascii=False))
    def download(self):
        return self.client.get(self.url,params={'path':self.manifest.name})

    def test_listing_is_lazy_and_repeated_downloads_leave_no_project_or_temporary_package(self):
        item=next(f for f in self.client.get(self.base).json()['files'] if f['name']==self.manifest.name)
        self.assertIn('/commercial/',item['director']);self.assertFalse(NativeClient.calls)
        before={p:p.read_bytes() for p in self.project.iterdir()}
        for i in range(2):
            response=self.client.get(item['director']);self.assertEqual(response.status_code,200,response.text[:100] if response.status_code!=200 else '')
            self.assertEqual(response.headers['content-type'],'application/zip');self.assertTrue(response.content.startswith(b'PK'))
            self.assertEqual(list(self.downloads.iterdir()),[]);self.assertEqual(len(NativeClient.calls),(i+1)*2)
        self.assertEqual(before,{p:p.read_bytes() for p in self.project.iterdir()})
        self.assertTrue(all(route=='/minimax/director/export_pack' for _,route in NativeClient.calls))

    def test_missing_sources_and_cross_project_paths_stop_before_remote_io(self):
        image=self.project/'原图.png';image.unlink();self.assertEqual(self.download().status_code,404);self.assertFalse(NativeClient.calls)
        image.write_bytes(b'frozen bytes')
        for path in ('../别的订单/原图.png',str(self.root/'secret.png')):
            self.spec['media']['ref.png']=path;self.write();self.assertEqual(self.download().status_code,404)
        self.assertFalse(NativeClient.calls)

    def test_missing_remote_inputs_are_restored_once_without_modifying_sources(self):
        NativeClient.missing=True
        def upload(connection,args):
            self.assertEqual(Path(args.file).read_bytes(),b'frozen bytes')
            NativeClient.missing=False;NativeClient.media['restored.png']=b'frozen bytes';return {'input_path':'restored.png'}
        with patch.object(director_packages.director_export.client,'upload',side_effect=upload) as uploaded:
            response=self.download()
        self.assertEqual(response.status_code,200);self.assertEqual(uploaded.call_count,1)
        self.assertEqual(json.loads(self.manifest.read_text())['workflow'],self.spec['workflow'])
        self.assertEqual(list(self.downloads.iterdir()),[])

    def test_package_relative_media_are_uploaded_before_native_preflight(self):
        self.spec['media_origin']='pack';self.write()
        def upload(connection,args):
            self.assertFalse(NativeClient.calls)
            NativeClient.media['restored.png']=b'frozen bytes'
            return {'input_path':'restored.png'}
        with patch.object(director_packages.director_export.client,'upload',side_effect=upload) as uploaded:
            self.assertEqual(self.download().status_code,200)
        self.assertEqual(uploaded.call_count,1)
        self.assertEqual(list(self.downloads.iterdir()),[])

    def test_invalid_manifest_returns_error_before_export(self):
        for value in ({}, {'name':'../bad.mmxpack.zip','node_id':'1','media':{}},
                      {**self.spec,'media':None}, {**self.spec,'media_origin':'unknown'}):
            self.manifest.write_text(json.dumps(value))
            self.assertEqual(self.download().status_code,409)
        self.assertFalse(NativeClient.calls)

    def test_failed_export_cleans_partial_output_and_allows_same_request_retry(self):
        def failed(connection,args):
            Path(args.output).write_bytes(b'partial');raise ValueError('isolated export failure')
        with patch.object(director_packages.director_export.client,'export_pack',side_effect=failed):
            self.assertEqual(self.download().status_code,409)
        self.assertEqual(list(self.downloads.iterdir()),[]);self.assertEqual(self.download().status_code,200)

    def test_cancelled_response_cleans_file_and_directory(self):
        response=director_packages.package_response(self.spaces.get('commercial').projects,'订单',self.manifest.name)
        async def send(message):raise asyncio.CancelledError()
        async def receive():return {'type':'http.disconnect'}
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(response({'type':'http','method':'GET','headers':[],'extensions':{}},receive,send))
        self.assertEqual(list(self.downloads.iterdir()),[])

    def test_historical_zip_link_regenerates_after_zip_removed(self):
        response=self.client.get(self.base+'/files/原生导演包.mmxpack.zip?download=true')
        self.assertEqual(response.status_code,200);self.assertFalse((self.project/'原生导演包.mmxpack.zip').exists())
        self.assertEqual(list(self.downloads.iterdir()),[])

    def test_stage_click_uses_exact_adopted_sources_without_writing_project(self):
        project=self.primary/'projects/剧集';project.mkdir();(project/'原图.png').write_bytes(b'frozen bytes')
        prepared={'pack':Path('本场.mmxpack.zip'),'node':'1','url':self.spec['url'],'workflow':self.spec['workflow'],'media':{'ref.png':project/'原图.png'}}
        before=list(project.iterdir())
        with patch.object(scene_finalize,'indexed_parts',return_value=[('EP001-C001','EP001-C001-P001')]), \
             patch.object(scene_finalize,'selected',return_value='EP001-C001-P001-R002-一采'), \
             patch.object(video_approve,'adopted_source',return_value={'identity':'EP001-C001-P001-R002-一采'}) as source, \
             patch.object(scene_finalize,'prepare',return_value=prepared):
            response=self.client.get('/api/projects/剧集/episodes/EP001/downloads/一采/director?scene=C001')
        self.assertEqual(response.status_code,200);source.assert_called_once_with(project,'EP001-C001-P001-R002-一采','一采')
        self.assertEqual(list(project.iterdir()),before);self.assertEqual(list(self.downloads.iterdir()),[])

    def test_startup_cleans_interrupted_director_download_directory(self):
        self.downloads.mkdir();folder=self.downloads/'director-interrupted';folder.mkdir();(folder/'partial.mmxpack.zip').write_bytes(b'partial')
        episode_downloads.clear_downloads();self.assertEqual(list(self.downloads.iterdir()),[])
