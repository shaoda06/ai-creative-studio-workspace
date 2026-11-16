"""Find Chloe shared assets by the identifier in their existing records."""
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request

from backend.chloe_models import look_cover, model_adoption, model_card, model_looks, model_records, request_space
from backend.chloe_overview import fields
from backend.chloe_poses import catalog
from backend.chloe_reference_assets import ACCESSORIES, CLOTHING, HAIR, SCENES, VOICES, asset_adoption, asset_card, asset_documents
from backend.chloe_reference_videos import KIND as VIDEO, SECTION as VIDEO_SECTION, playback_reference, video_urls
from project_resources import reuse_read_indexes

router = APIRouter()
REFERENCE_GROUPS = (
    (HAIR, 'hair', 'hair'), (CLOTHING, 'clothing', 'clothing'), (ACCESSORIES, 'accessories', 'accessory'),
    (SCENES, 'scenes', 'scene'), (VOICES, 'voices', 'voice'), (VIDEO, 'reference-videos', 'referenceVideo'),
)


def image_preview(media):
    if media:
        return media.get('thumbnailUrl') or media['url']
    return None


def search_entries(root, api, prefix):
    for kind, asset, parameter in REFERENCE_GROUPS:
        if not (prefix.startswith(kind.prefix.casefold()) or kind.prefix.casefold().startswith(prefix)):
            continue
        for identity, name, path, doc in asset_documents(root, kind, id_prefix=prefix):
            preview = None
            if kind == VIDEO:
                reference = playback_reference(root, path, fields(doc, VIDEO_SECTION))
                if reference is None:
                    continue
                preview = video_urls(api, identity, reference)[0]
            elif kind != VOICES:
                base = f'{api}/{kind.endpoint}/{quote(identity)}'
                card = asset_card(root, base, kind, path, {}, asset_adoption(doc, kind))
                preview = image_preview(card['media'])
            params = {'asset': asset, parameter: identity}
            label = kind.label
            if kind == CLOTHING:
                is_outfit = fields(doc, '服装信息').get('服装形态') == '套装'
                params['clothingTab'] = 'outfits' if is_outfit else 'garments'
                label = '套装' if is_outfit else '单件'
            yield {'id': identity, 'name': name, 'category': label, 'params': params, 'previewUrl': preview}
    if prefix.startswith('m'):
        for identity, name, path, doc in model_records(root, id_prefix=prefix):
            card = model_card(root, api, path, doc, model_adoption(doc), {'id': identity, 'name': name})
            yield {'id': identity, 'name': name, 'category': 'AI 模特', 'params': {'asset': 'models', 'model': identity},
                   'previewUrl': image_preview(card['media'])}
    if prefix.startswith('l'):
        for identity, name, path, doc in model_looks(root, id_prefix=prefix):
            model = fields(doc, '造型信息')['模特编号']
            if next(model_records(root, model), None):
                preview = look_cover(root, f'{api}/shared-models/{quote(model)}', path, doc, name)
                yield {'id': identity, 'name': name, 'category': '造型', 'previewUrl': image_preview(preview),
                       'params': {'asset': 'models', 'model': model, 'modelTab': 'looks', 'look': identity}}
    # Pose IDs begin with their registered category name.
    if not prefix.isascii() or '-' in prefix:
        poses, _ = catalog()
        for pose in poses.values():
            if pose.id.casefold().startswith(prefix):
                yield {'id': pose.id, 'name': pose.name, 'category': '姿态', 'params': {'asset': 'poses', 'pose': pose.id},
                       'previewUrl': image_preview(pose.card(api)['media'])}


@router.get('/shared-asset-search')
def search(request: Request, q: Annotated[str, Query(max_length=64)] = ''):
    space = request_space(request)
    prefix = q.strip().casefold()
    if not prefix:
        return []
    try:
        with reuse_read_indexes():
            return sorted(search_entries(space.root, space.api, prefix), key=lambda item: (
                item['id'].casefold() != prefix, item['id'], item['name'],
            ))[:20]
    except (OSError, ValueError) as error:
        raise HTTPException(409, str(error)) from error
