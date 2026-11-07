"""Read Chloe model cards from their sole documents and adopted portrait versions."""
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.chloe_overview import fields
from chloe_documents import media_reference, read_document, records, template
import project_resources as resources

router = APIRouter(prefix='/shared-models')


def model_documents(root):
    folder = resources.local(root, '综合资料/共用素材/AI模特')
    if not folder.is_dir():
        raise FileNotFoundError('模特资料目录不存在')
    seen = set()
    for path in sorted(folder.glob('M*-*/模特说明.md')):
        if not path.resolve().is_relative_to(folder):
            raise ValueError('模特说明越出模特资料目录')
        identity, name = path.parent.name.split('-', 1)
        if identity in seen:
            raise ValueError('模特编号重复：' + identity)
        seen.add(identity)
        doc = read_document(root, path, template('chloe-assets', '模特说明模板.md'),
                            {'identity': identity, 'title': name})
        portraits = [row for row in records(doc, '当前采用') if row['用途'] == '正面面部']
        portrait = media_reference(root, path, portraits[0]['资源引用']) if portraits else None
        if portrait and Path(portrait['file']).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
            raise ValueError('正面面部采用必须为PNG、JPEG或WebP图片')
        yield identity, name, doc, portrait


def model_cards(root, api):
    cards = []
    for identity, name, doc, portrait in model_documents(root):
        media = None
        if portrait:
            key = portrait['resource_id'] + '@' + portrait['version']
            media = {'kind': 'image', 'name': name + ' · 正面面部', 'key': key,
                     'url': f'{api}/shared-models/{quote(identity)}/portrait/{quote(portrait["resource_id"])}/{quote(portrait["version"])}'}
        cards.append({'id': identity, 'name': name, 'identity': fields(doc, '资产身份'),
                      'features': fields(doc, '人物特征'), 'media': media,
                      'version': portrait['version'] if portrait else None})
    return cards


def portrait_file(root, identity, resource_id, version):
    for model_id, _, _, portrait in model_documents(root):
        if model_id == identity and portrait and portrait['resource_id'] == resource_id and portrait['version'] == version:
            return resources.local(root, portrait['file'])
    raise FileNotFoundError('该模特没有采用这个正面面部版本')


@router.get('')
def listing(request: Request):
    space = request.state.workspace_space
    if space.view != 'chloe-commerce':
        raise HTTPException(404, '该空间未接入带货共用模特')
    try:
        return model_cards(space.root, space.api)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get('/{identity}/portrait/{resource_id}/{version}')
def portrait(identity: str, resource_id: str, version: str, request: Request, download: bool = False):
    space = request.state.workspace_space
    if space.view != 'chloe-commerce':
        raise HTTPException(404, '该空间未接入带货共用模特')
    try:
        path = portrait_file(space.root, identity, resource_id, version)
        return FileResponse(path, filename=path.name if download else None,
                            headers={'X-Content-Type-Options': 'nosniff'})
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
