"""Expose the shared pose guide as a read-only Chloe asset list."""
import re
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from backend.chloe_asset_pages import AssetPage, AssetRow, asset_page
from backend.chloe_models import request_space
from backend.chloe_thumbnails import production_thumbnail, thumbnail_url
from backend.services.read_views import view_response, views

ENDPOINT = 'shared-poses'
POSE_SKILL = Path(__file__).resolve().parents[2] / '.agents/skills/studio-creative-techniques'
router = APIRouter(prefix='/' + ENDPOINT)


@dataclass(frozen=True)
class Pose:
    id: str
    name: str
    category: str
    description: str
    image: Path

    def card(self, api):
        url = f'{api}/{ENDPOINT}/{quote(self.id, safe="")}/image'
        return {'id': self.id, 'name': self.name, 'description': self.description,
                'media': {'kind': 'image', 'key': self.id, 'name': self.name,
                          'url': url, 'thumbnailUrl': thumbnail_url(url)}}


def read_poses(skill):
    references = skill / 'references'
    categories = (references / '人物姿态').resolve()
    assets = (skill / 'assets').resolve()
    guide = (references / '人物姿态参考表.md').read_text(encoding='utf-8')
    poses = {}
    for category, filename in re.findall(r'^- \[([^\]\n]+)\]\(人物姿态/([^/\\\n]+\.md)\)$', guide, re.M):
        source = (categories / filename).resolve()
        if not source.is_relative_to(categories):
            raise ValueError(f'姿态分类文件超出参考目录：{category}')
        headings = re.split(r'^##[ \t]+', source.read_text(encoding='utf-8'), flags=re.M)[1:]
        for block in headings:
            heading, _, body = block.partition('\n')
            entry = re.fullmatch(rf'({re.escape(category)}-[0-9]{{3}})[ \t]+(.+)', heading.strip())
            if not entry:
                continue
            identity, name = entry.groups()
            link = re.search(r'^!\[[^\]\n]*\]\(<?([^\n]+?\.png)>?\)[ \t]*$', body, re.M)
            if not link:
                raise ValueError(f'正式姿态缺少线稿：{identity}')
            image = (source.parent / link[1]).resolve()
            if not image.is_relative_to(assets) or not image.is_file():
                raise ValueError(f'正式姿态线稿不可用：{identity}')
            if identity in poses:
                raise ValueError(f'正式姿态编号重复：{identity}')
            poses[identity] = Pose(identity, name, category, body[:link.start()].strip(), image)
    return poses


def catalog():
    try:
        return views.read(ENDPOINT, [POSE_SKILL / 'references', POSE_SKILL / 'assets'],
                          partial(read_poses, POSE_SKILL))
    except (ValueError, OSError) as error:
        raise HTTPException(409, str(error)) from error


@router.get('')
def listing(request: Request, options: AssetPage = Depends()):
    space = request_space(request)
    poses, revision = catalog()
    rows = [AssetRow(pose.id, partial(pose.card, space.api), '可用', True, type=pose.category) for pose in poses.values()]
    return view_response(request, revision, partial(asset_page, rows, options))


@router.get('/{identity}/image')
def image(identity: str, request: Request, thumbnail: int | None = None):
    space = request_space(request)
    poses, _ = catalog()
    pose = poses.get(identity)
    if pose is None:
        raise HTTPException(404, '未找到已收录的姿态')
    if thumbnail is not None:
        return production_thumbnail(space.runtime, pose.image, thumbnail, request)
    return FileResponse(pose.image, media_type='image/png',
                        headers={'Cache-Control': 'private, no-cache', 'X-Content-Type-Options': 'nosniff'})
