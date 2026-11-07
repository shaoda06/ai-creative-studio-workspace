"""Shared read-only clothing and scene records; media stay in their original versioned files."""
from dataclasses import dataclass
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.chloe_models import asset_content, linked_files, linked_html, request_space
from backend.chloe_overview import fields
from backend.parsers import documents
from chloe_documents import read_document, template
import project_resources as resources

@dataclass
class AssetKind:
    label: str
    prefix: str
    endpoint: str


CLOTHING = AssetKind('服装', 'O', 'shared-clothing')
SCENES = AssetKind('场景', 'S', 'shared-scenes')


def asset_documents(root, kind):
    folder = resources.local(root, '综合资料/共用素材/'+kind.label)
    seen = set()
    for path in sorted(folder.glob(f'{kind.prefix}*-*/{kind.label}说明.md')):
        if not path.resolve().is_relative_to(folder):
            raise ValueError(kind.label+'说明越出资料目录')
        identity, name = path.parent.name.split('-', 1)
        if identity in seen:
            raise ValueError(kind.label+'编号重复：' + identity)
        seen.add(identity)
        doc = read_document(root, path, template('chloe-assets', kind.label+'说明模板.md'),
                            {'identity': identity, 'title': name})
        yield identity, name, path, doc


def asset_context(root, identity, kind):
    for item in asset_documents(root, kind):
        if item[0] == identity:
            return item
    raise FileNotFoundError(kind.label+'资料不存在：' + identity)


def asset_detail(root, identity, api, kind):
    _, name, path, doc = asset_context(root, identity, kind)
    base = f'{api}/{kind.endpoint}/{quote(identity)}'
    return {'id': identity, 'name': name, 'description': fields(doc, kind.label+'信息')[kind.label+'说明'],
            **asset_content(root, path, doc, linked_files(root, path, doc), base),
            'url': base + '/files/' + quote(path.relative_to(root).as_posix(), safe='/')}


def asset_cards(root, api, kind):
    cards = []
    for identity, name, path, doc in asset_documents(root, kind):
        base = f'{api}/{kind.endpoint}/{quote(identity)}'
        content = asset_content(root, path, doc, linked_files(root, path, doc), base)
        cover = next((image['media'] for image in content['images']
                      if image['adopted'] and image['purpose'] == kind.label+'展示图'), None)
        cards.append({'id': identity, 'name': name, 'media': cover})
    return cards


def asset_file(root, identity, key, kind):
    _, _, path, doc = asset_context(root, identity, kind)
    if key not in linked_files(root, path, doc):
        raise FileNotFoundError('文件未被该'+kind.label+'直接引用')
    return resources.local(root, key)


def asset_router(kind):
    router = APIRouter(prefix="/"+kind.endpoint)

    @router.get('')
    def listing(request: Request):
        space = request_space(request)
        try:
            return asset_cards(space.root, space.api, kind)
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error


    @router.get('/{identity}')
    def detail(identity: str, request: Request):
        space = request_space(request)
        try:
            return asset_detail(space.root, identity, space.api, kind)
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error


    @router.get('/{identity}/files/{key:path}')
    def file(identity: str, key: str, request: Request, download: bool = False):
        space = request_space(request)
        try:
            path = asset_file(space.root, identity, key, kind)
            inline = path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}
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
