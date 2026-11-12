"""Read registered Chloe reference videos and their exact playback versions."""
import json
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.chloe_models import request_space
from backend.chloe_overview import fields
from backend.chloe_reference_assets import AssetKind, asset_context, asset_documents
from backend.chloe_thumbnails import video_cover_response
from chloe_documents import MISSING, media_reference
from chloe_init import ASSETS
import project_resources as resources

KIND = AssetKind('参考视频', ASSETS['参考视频'][1], 'shared-reference-videos')
SECTION = '参考视频信息'
router = APIRouter(prefix='/' + KIND.endpoint)


def playback_reference(root, path, info):
    value = info['播放版本引用']
    if value in MISSING:
        return None
    return media_reference(root, path, value)


def video_urls(api, identity, ref):
    base = f'{api}/{KIND.endpoint}/{quote(identity)}'
    version = f'{quote(ref["resource_id"])}/{quote(ref["version"])}'
    return f'{base}/cover/{version}', f'{base}/media/{version}'


def registered_video(root, identity):
    _, name, path, doc = asset_context(root, identity, KIND)
    info = fields(doc, SECTION)
    ref = playback_reference(root, path, info)
    if ref is None:
        raise FileNotFoundError('参考视频尚未登记播放版本')
    return name, info, ref


@router.get('')
def listing(request: Request):
    space = request_space(request)
    cards = []
    try:
        for identity, name, path, doc in asset_documents(space.root, KIND):
            ref = playback_reference(space.root, path, fields(doc, SECTION))
            if ref:
                cover, _ = video_urls(space.api, identity, ref)
                cards.append({'id': identity, 'name': name, 'coverUrl': cover, 'status': '可用'})
    except (ValueError, OSError) as error:
        raise HTTPException(409, str(error)) from error
    return cards


@router.get('/{identity}')
def detail(identity: str, request: Request):
    space = request_space(request)
    try:
        name, info, ref = registered_video(space.root, identity)
        path = resources.local(space.root, ref['file'])
        facts = json.loads(path.with_name('版本信息.json').read_text('utf-8'))['facts']
        if 'display_aspect_ratio' not in facts:
            facts = resources.facts(path)
        _, url = video_urls(space.api, identity, ref)
        source = info['来源']
        return {'id': identity, 'name': name, 'status': '可用', 'source': source,
                'sourceUrl': source.partition('－')[2] or None, 'description': info['内容简介'],
                'duration': facts['duration_seconds'], 'width': facts['display_width'], 'height': facts['display_height'],
                'aspectRatio': facts['display_aspect_ratio'],
                'media': {'kind': 'video', 'key': ref['file'], 'name': name, 'url': url}}
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except (ValueError, KeyError) as error:
        raise HTTPException(409, str(error)) from error


def playback_file(space, identity, resource_id, version):
    try:
        _, _, ref = registered_video(space.root, identity)
        if (resource_id, version) != (ref['resource_id'], ref['version']):
            raise FileNotFoundError('该文件不是登记的播放版本')
        return resources.local(space.root, ref['file'])
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get('/{identity}/media/{resource_id}/{version}')
def media(identity: str, resource_id: str, version: str, request: Request):
    space = request_space(request)
    path = playback_file(space, identity, resource_id, version)
    return FileResponse(path, headers={'X-Content-Type-Options': 'nosniff'})


@router.get('/{identity}/cover/{resource_id}/{version}')
def cover(identity: str, resource_id: str, version: str, request: Request):
    space = request_space(request)
    path = playback_file(space, identity, resource_id, version)
    return video_cover_response(space.runtime, path, resource_id, version)
