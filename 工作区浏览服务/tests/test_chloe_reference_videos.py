"""Exercise Chloe reference video registration and the actual media routes."""
from io import BytesIO
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from PIL import Image

from backend.chloe_reference_videos import router
from backend.chloe_resource_library import visual_titles
from chloe_documents import check_workspace
from chloe_init import initialize_asset, initialize_project, initialize_workspace, resources


class ChloeReferenceVideoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = initialize_project(initialize_workspace(self.base/'Chloe Workspace'), '隔离样例')
        self.owner = self.root/'综合资料'
        self.space = SimpleNamespace(view='chloe-commerce', root=self.root, api='/api/workspaces/test',
                                     runtime=self.base/'runtime')
        self.base_url = self.space.api + '/shared-reference-videos'

        def select(request: Request):
            request.state.workspace_space = self.space

        app = FastAPI()
        app.include_router(router, prefix=self.space.api, dependencies=[Depends(select)])
        self.client = self.enterContext(TestClient(app))

    def test_legacy_project_and_draft_stay_empty(self):
        (self.owner/'共用素材/参考视频').rmdir()
        self.assertEqual(self.client.get(self.base_url).json(), [])
        self.assertEqual(check_workspace(self.root)['errors'], [])
        initialize_asset(self.root, '参考视频', 'RV001', '待确认样例')
        self.assertEqual(self.client.get(self.base_url).json(), [])
        self.assertEqual(self.client.get(self.base_url+'/RV001').status_code, 404)

    def test_registered_crop_uses_its_first_frame_and_exact_playback(self):
        original = self.base/'original.mp4'
        clip = self.base/'clip.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:s=160x90:d=1',
                        '-f', 'lavfi', '-i', 'color=blue:s=160x90:d=1', '-filter_complex', 'concat=n=2:v=1:a=0',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(original)], check=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-ss', '1', '-i', str(original), '-t', '1',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(clip)], check=True)
        original_ref = resources.register(self.owner, original, origin='import', key='fixture-source')
        asset = initialize_asset(self.root, '参考视频', 'RV001', '隔离测试视频')
        document = asset/'参考视频说明.md'
        trimmed_ref = resources.register(self.owner, clip, resource_id=original_ref['resource_id'],
                                         parent=original_ref['file'], origin='process', key='fixture-trim',
                                         producer=document.relative_to(self.owner).as_posix(), source_range=(1, 1))

        def link(ref):
            path = os.path.relpath(resources.local(self.owner, ref['file']), asset)
            return f'[共用:{ref["resource_id"]}@{ref["version"]}](<{path}>)'

        pending = document.read_text('utf-8')
        source = '示例平台－https://example.test/video/42'
        registered = (pending.replace('| 来源 | 待核实 |', f'| 来源 | {source} |')
                      .replace('| 内容简介 | 待确定 |', '| 内容简介 | 蓝色测试画面。 |')
                      .replace('| 原件引用 | 未取得 |', f'| 原件引用 | {link(original_ref)} |')
                      .replace('| 播放版本引用 | 未取得 |', f'| 播放版本引用 | {link(trimmed_ref)} |')
                      .replace('| 登记依据 | 未取得 |', '| 登记依据 | 测试夹具确认保留后半段。 |'))
        document.write_text(registered.replace(source, '混合分享文案 https://example.test/s/42'), 'utf-8')
        self.assertEqual(self.client.get(self.base_url).status_code, 409)
        document.write_text(registered, 'utf-8')
        self.assertEqual(check_workspace(self.root, only=document)['errors'], [])

        card, = self.client.get(self.base_url).json()
        self.assertEqual(card['name'], '隔离测试视频')
        details = self.client.get(self.base_url+'/RV001').json()
        self.assertEqual(details['sourceUrl'], 'https://example.test/video/42')
        self.assertEqual(details['duration'], 1)
        self.assertEqual((details['aspectRatio'], details['width'], details['height']), ('16:9', 160, 90))
        cover = self.client.get(card['coverUrl'])
        self.assertEqual(cover.status_code, 200)
        self.assertEqual(cover.headers['content-type'], 'image/jpeg')
        self.assertIn('max-age', cover.headers['cache-control'])
        with Image.open(BytesIO(cover.content)) as image:
            red, _, blue = image.convert('RGB').getpixel((0, 0))
            self.assertGreater(blue, red + 150)
        with patch('backend.chloe_thumbnails.subprocess.run', side_effect=AssertionError('封面应复用缓存')):
            self.assertEqual(self.client.get(card['coverUrl']).content, cover.content)
        response = self.client.get(details['media']['url'], headers={'Range': 'bytes=0-31'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, clip.read_bytes()[:32])
        self.assertEqual(self.client.get(details['media']['url'].replace('/V002', '/V001')).status_code, 404)
        self.assertEqual(visual_titles(self.root)[(resources.local(self.owner, trimmed_ref['file']),
                                                   trimmed_ref['resource_id'], trimmed_ref['version'])],
                         ['隔离测试视频 · 参考视频'])

        document.write_text(registered.replace(source, '用户提供').replace(link(trimmed_ref), link(original_ref)), 'utf-8')
        details = self.client.get(self.base_url+'/RV001').json()
        self.assertIsNone(details['sourceUrl'])
        self.assertEqual(details['source'], '用户提供')
        self.assertEqual(details['duration'], 2)
        self.assertTrue(details['media']['url'].endswith('/V001'))

    def test_display_dimensions_follow_the_video_rotation(self):
        source = self.base/'landscape.mp4'
        rotated = self.base/'portrait.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:s=160x90:d=1',
                        '-c:v', 'libx264', str(source)], check=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-display_rotation', '90', '-i', str(source),
                        '-c', 'copy', str(rotated)], check=True)
        facts = resources.facts(rotated)
        self.assertEqual((facts['width'], facts['height']), (160, 90))
        self.assertEqual((facts['display_width'], facts['display_height'], facts['display_aspect_ratio']), (90, 160, '9:16'))
