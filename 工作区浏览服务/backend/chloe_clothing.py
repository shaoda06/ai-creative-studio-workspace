"""Read clothing records and their original, versioned media without copying."""
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.chloe_models import asset_content, linked_files, linked_html, request_space
from backend.chloe_overview import fields
from backend.parsers import documents
from chloe_documents import read_document, template
import project_resources as resources

router = APIRouter(prefix='/shared-clothing')


def clothing_documents(root):
    folder = resources.local(root, '综合资料/共用素材/服装')
    seen = set()
    for path in sorted(folder.glob('O*-*/服装说明.md')):
        if not path.resolve().is_relative_to(folder):
            raise ValueError('服装说明越出服装资料目录')
        identity, name = path.parent.name.split('-', 1)
        if identity in seen:
            raise ValueError('服装编号重复：' + identity)
        seen.add(identity)
        doc = read_document(root, path, template('chloe-assets', '服装说明模板.md'),
                            {'identity': identity, 'title': name})
        yield identity, name, path, doc


def clothing_context(root, identity):
    for item in clothing_documents(root):
        if item[0] == identity:
            return item
    raise FileNotFoundError('服装资料不存在：' + identity)


def clothing_detail(root, identity, api):
    _, name, path, doc = clothing_context(root, identity)
    base = f'{api}/shared-clothing/{quote(identity)}'
    return {'id': identity, 'name': name, 'description': fields(doc, '服装信息')['服装说明'],
            **asset_content(root, path, doc, linked_files(root, path, doc), base),
            'url': base + '/files/' + quote(path.relative_to(root).as_posix(), safe='/')}


def clothing_cards(root, api):
    cards = []
    for identity, name, path, doc in clothing_documents(root):
        base = f'{api}/shared-clothing/{quote(identity)}'
        content = asset_content(root, path, doc, linked_files(root, path, doc), base)
        cover = next((image['media'] for image in content['images']
                      if image['adopted'] and image['purpose'] == '服装展示图'), None)
        cards.append({'id': identity, 'name': name, 'media': cover})
    return cards


def clothing_file(root, identity, key):
    _, _, path, doc = clothing_context(root, identity)
    if key not in linked_files(root, path, doc):
        raise FileNotFoundError('文件未被该服装直接引用')
    return resources.local(root, key)


@router.get('')
def listing(request: Request):
    space = request_space(request)
    try:
        return clothing_cards(space.root, space.api)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get('/{identity}')
def detail(identity: str, request: Request):
    space = request_space(request)
    try:
        return clothing_detail(space.root, identity, space.api)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get('/{identity}/files/{key:path}')
def file(identity: str, key: str, request: Request, download: bool = False):
    space = request_space(request)
    try:
        path = clothing_file(space.root, identity, key)
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
        file = clothing_file(space.root, identity, path)
        if file.suffix.lower() == '.md':
            _, _, source, doc = clothing_context(space.root, identity)
            base = f'{space.api}/shared-clothing/{quote(identity)}'
            return {'title': file.stem, 'html': linked_html(file.read_text('utf-8-sig'), path,
                    linked_files(space.root, source, doc), base)}
        return documents.plain_text_preview(file)[0]
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
