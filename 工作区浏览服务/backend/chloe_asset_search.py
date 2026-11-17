"""Find Chloe shared assets by the identifier in their existing records."""
from functools import cache, partial
from itertools import islice
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request

from backend.chloe_models import look_candidates, look_cover, model_adoption, model_card, model_record_candidates, model_records, request_space
from backend.chloe_overview import fields
from backend.chloe_poses import catalog
from backend.chloe_reference_assets import ACCESSORIES, CLOTHING, HAIR, SCENES, VOICES, asset_adoption, asset_card, asset_document_candidates
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


def reference_result(root, api, kind, asset, parameter, identity, name, path, load):
    doc = load()
    preview = None
    if kind == VIDEO:
        reference = playback_reference(root, path, fields(doc, VIDEO_SECTION))
        if reference is None:
            return None
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
    return {'id': identity, 'name': name, 'category': label, 'params': params, 'previewUrl': preview}


def model_result(root, api, identity, name, path, load):
    doc = load()
    card = model_card(root, api, path, doc, model_adoption(doc), {'id': identity, 'name': name})
    return {'id': identity, 'name': name, 'category': 'AI 模特', 'params': {'asset': 'models', 'model': identity},
            'previewUrl': image_preview(card['media'])}


def look_result(root, api, has_model, identity, name, path, load):
    doc = load()
    model = fields(doc, '造型信息')['模特编号']
    if not has_model(model):
        return None
    preview = look_cover(root, f'{api}/shared-models/{quote(model)}', path, doc, name)
    return {'id': identity, 'name': name, 'category': '造型', 'previewUrl': image_preview(preview),
            'params': {'asset': 'models', 'model': model, 'modelTab': 'looks', 'look': identity}}


def pose_result(api, pose):
    return {'id': pose.id, 'name': pose.name, 'category': '姿态', 'params': {'asset': 'poses', 'pose': pose.id},
            'previewUrl': image_preview(pose.card(api)['media'])}


def search_candidates(root, api, fragment):
    # Project asset numbers consist of a kind code followed by digits.
    code_part = fragment.rstrip('0123456789')
    for kind, asset, parameter in REFERENCE_GROUPS:
        if code_part not in kind.prefix.casefold():
            continue
        for identity, name, path, load in asset_document_candidates(root, kind, id_fragment=fragment):
            yield identity, name, partial(reference_result, root, api, kind, asset, parameter, identity, name, path, load)
    if not code_part or code_part == 'm':
        for identity, name, path, load in model_record_candidates(root, id_fragment=fragment):
            yield identity, name, partial(model_result, root, api, identity, name, path, load)
    if not code_part or code_part == 'l':
        @cache
        def has_model(identity):
            return next(model_records(root, identity), None) is not None

        for identity, name, path, load in look_candidates(root, id_fragment=fragment):
            yield identity, name, partial(look_result, root, api, has_model, identity, name, path, load)
    # Pose IDs begin with their registered category name.
    if not code_part or not fragment.isascii() or '-' in fragment:
        poses, _ = catalog()
        for pose in poses.values():
            if fragment in pose.id.casefold():
                yield pose.id, pose.name, partial(pose_result, api, pose)


def search_entries(root, api, fragment):
    ordered = sorted(search_candidates(root, api, fragment), key=lambda item: (
        item[0].casefold() != fragment, not item[0].casefold().startswith(fragment), item[0], item[1],
    ))
    for _, _, load in ordered:
        result = load()
        if result is not None:
            yield result


@router.get('/shared-asset-search')
def search(request: Request, q: Annotated[str, Query(max_length=64)] = ''):
    space = request_space(request)
    fragment = q.strip().casefold()
    if not fragment:
        return []
    try:
        with reuse_read_indexes():
            return list(islice(search_entries(space.root, space.api, fragment), 20))
    except (OSError, ValueError) as error:
        raise HTTPException(409, str(error)) from error
