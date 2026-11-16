"""Shared read-only asset records; media stay in their original versioned files."""
import json
from dataclasses import dataclass
from functools import partial
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from backend.services.read_views import respond_view
from fastapi.responses import FileResponse

from backend.chloe_asset_pages import AssetPage, AssetRow, respond_asset_page
from backend.chloe_models import adopted_media, asset_content, linked_files, linked_html, model_context, request_space
from backend.chloe_overview import fields
from backend.chloe_thumbnails import IMAGE_EXTENSIONS, thumbnail_response
from backend.parsers import documents
from chloe_documents import DEFAULT_OUTFIT_STYLE, MISSING, asset_status, read_document, records, template
from chloe_init import asset_template_skill
import project_resources as resources

@dataclass
class AssetKind:
    label: str
    prefix: str
    endpoint: str


HAIR = AssetKind('发型', 'H', 'shared-hair')
CLOTHING = AssetKind('服装', 'O', 'shared-clothing')
ACCESSORIES = AssetKind('配饰', 'C', 'shared-accessories')
SCENES = AssetKind('场景', 'S', 'shared-scenes')
VOICES = AssetKind('声音', 'A', 'shared-voices')


def asset_documents(root, kind, requested_id=None, *, id_prefix=''):
    folder = resources.local(root, '综合资料/共用素材/'+kind.label)
    seen = set()
    for path in sorted(folder.glob(f'{kind.prefix}*-*/{kind.label}说明.md')):
        identity, name = path.parent.name.split('-', 1)
        if (requested_id is not None and identity != requested_id) or not identity.casefold().startswith(id_prefix):
            continue
        if not path.resolve().is_relative_to(folder):
            raise ValueError(kind.label+'说明越出资料目录')
        if identity in seen:
            raise ValueError(kind.label+'编号重复：' + identity)
        seen.add(identity)
        doc = read_document(root, path, template(asset_template_skill(kind.label), kind.label+'说明模板.md'),
                            {'identity': identity, 'title': name})
        yield identity, name, path, doc


def asset_context(root, identity, kind):
    for item in asset_documents(root, kind, identity):
        return item
    raise FileNotFoundError(kind.label+'资料不存在：' + identity)


def clothing_classification(info):
    form = info.get('服装形态')
    return {
        'clothingForm': form if form not in MISSING else None,
        'bodyArea': info['部位'] if form == '单件' else None,
        'outfitSource': info['套装来源'] if form == '套装' else None,
        'outfitStyle': info.get('风格', DEFAULT_OUTFIT_STYLE) if form == '套装' else None,
    }


def asset_detail(root, identity, api, kind):
    _, name, path, doc = asset_context(root, identity, kind)
    base = f'{api}/{kind.endpoint}/{quote(identity)}'
    content = asset_content(root, path, doc, linked_files(root, path, doc), base,
                            ('audio', 'video') if kind == VOICES else ('image',))
    if kind == VOICES:
        content['versions'] = content.pop('images')
        for item in content['versions']:
            info = json.loads((resources.local(root, item['media']['key']).parent/'版本信息.json').read_text('utf-8'))
            item['duration'] = info['facts'].get('duration_seconds')
        content['models'] = [{'id': row['对象编号'], 'name': row['对象编号']+' · '+model_context(root, row['对象编号'])[0]}
                             for row in records(doc, '关联资料') if row['关系'] == '模特']
    info = fields(doc, kind.label+'信息')
    if kind == ACCESSORIES:
        content['type'] = info['配饰类型']
    if kind == CLOTHING:
        content.update(clothing_classification(info))
        if content['clothingForm'] == '套装':
            content['composition'] = info['组成与穿法']
    return {'id': identity, 'name': name, 'description': info[kind.label+'说明'],
            **content, 'url': base + '/files/' + quote(path.relative_to(root).as_posix(), safe='/')}


def asset_card(root, base, kind, path, metadata, adoption):
    media_kinds = ('audio', 'video') if kind == VOICES else ('image',)
    current = adopted_media(root, path, base, adoption, media_kinds) if adoption else None
    card = {**metadata, 'media': current['media'] if current else None}
    if kind in (CLOTHING, VOICES):
        card['reference'] = {'resource': current['resource'], 'version': current['version']} if current else None
    if kind == VOICES and current:
        info = json.loads((resources.local(root, current['media']['key']).parent/'版本信息.json').read_text('utf-8'))
        card['reference']['duration'] = info['facts'].get('duration_seconds')
    return card


def asset_rows(root, api, kind):
    purpose = '声音参考' if kind == VOICES else kind.label+'展示图'
    rows = []
    for identity, name, path, doc in asset_documents(root, kind):
        status = '' if kind == VOICES else asset_status(path, doc)['status']
        info = fields(doc, kind.label+'信息')
        classification = clothing_classification(info) if kind == CLOTHING else {}
        asset_type = info['配饰类型'] if kind == ACCESSORIES else classification.get('outfitStyle') or classification.get('bodyArea')
        if asset_type in MISSING:
            asset_type = None
        models = tuple(row['对象编号'] for row in records(doc, '关联资料') if row['关系'] == '模特') if kind == VOICES else ()
        metadata = {'id': identity, 'name': name, **classification}
        if kind == VOICES:
            metadata.update(models=list(models), description=info['声音说明'])
        else:
            metadata['status'] = status
        if kind == ACCESSORIES:
            metadata['type'] = asset_type
        adoption = next((row for row in records(doc, '当前采用') if row['用途'] == purpose), None)
        base = f'{api}/{kind.endpoint}/{quote(identity)}'
        card = partial(asset_card, root, base, kind, path, metadata, adoption)
        rows.append(AssetRow(identity, card, status, bool(adoption), classification.get('clothingForm'), asset_type, models))
    return rows


def asset_cards(root, api, kind):
    return [row.card() for row in asset_rows(root, api, kind)]


def asset_file(root, identity, key, kind):
    _, _, path, doc = asset_context(root, identity, kind)
    if key not in linked_files(root, path, doc):
        raise FileNotFoundError('文件未被该'+kind.label+'直接引用')
    return resources.local(root, key)


def asset_router(kind):
    router = APIRouter(prefix="/"+kind.endpoint)

    @router.get('')
    def listing(request: Request, options: AssetPage = Depends()):
        space = request_space(request)
        try:
            return respond_asset_page(request, space, kind.endpoint, options,
                                      lambda: asset_rows(space.root, space.api, kind), folders=[space.root / '综合资料'])
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error


    @router.get('/{identity}')
    def detail(identity: str, request: Request):
        space = request_space(request)
        try:
            return respond_view(request, (space.api, kind.endpoint, identity), [space.root / '综合资料'],
                                lambda: asset_detail(space.root, identity, space.api, kind))
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error


    @router.get('/{identity}/files/{key:path}')
    def file(identity: str, key: str, request: Request, download: bool = False, thumbnail: int | None = None):
        space = request_space(request)
        try:
            path = asset_file(space.root, identity, key, kind)
            if thumbnail is not None and not download:
                return thumbnail_response(space, path, thumbnail)
            inline = path.suffix.lower() in IMAGE_EXTENSIONS | resources.KINDS['音频'] | resources.KINDS['视频']
            return FileResponse(path, filename=path.name if download or not inline else None,
                                headers={'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': 'sandbox'})
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error


    @router.get('/{identity}/document')
    def document(identity: str, path: str, request: Request):
        space = request_space(request)
        try:
            file = asset_file(space.root, identity, path, kind)
            if file.suffix.lower() == '.md':
                _, _, source, doc = asset_context(space.root, identity, kind)
                base = f'{space.api}/{kind.endpoint}/{quote(identity)}'
                return {'title': file.stem, 'html': linked_html(file.read_text('utf-8-sig'), path,
                        linked_files(space.root, source, doc), base)}
            return documents.plain_text_preview(file)[0]
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    return router
