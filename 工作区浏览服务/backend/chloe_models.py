"""Read Chloe model cards from their sole documents and adopted portrait versions."""
import html
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.chloe_overview import fields
from backend.parsers import documents
from chloe_documents import LINK, media_reference, read_document, records, template
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


def model_context(root, identity):
    for model_id, name, doc, _ in model_documents(root):
        if model_id == identity:
            path = root/'综合资料/共用素材/AI模特'/f'{model_id}-{name}'/'模特说明.md'
            return name, path, doc
    raise FileNotFoundError('模特资料不存在：' + identity)


def linked_files(root, path, doc):
    """Only files directly referenced by this model's business tables are exposed."""
    allowed = {path.relative_to(root).as_posix()}
    for section in doc['sections']:
        for table in section['tables']:
            for row in table['rows']:
                for cell in row:
                    for _, href in LINK.findall(cell):
                        target = urlsplit(href)
                        if target.scheme or target.netloc:
                            continue
                        file = (path.parent / unquote(target.path)).resolve()
                        if file.is_relative_to(root/'综合资料') and file.is_file():
                            allowed.add(file.relative_to(root).as_posix())
    return allowed


def linked_html(text, source, allowed, base):
    rendered = documents.markdown(text, source)
    def replace(match):
        href, key, label = match.groups()
        key = html.unescape(key)
        if key not in allowed:
            return label
        fragment = urlsplit(html.unescape(href)).fragment
        url = base + '/files/' + quote(key, safe='/') + ('#' + fragment if fragment else '')
        return f'<a href="{html.escape(url, quote=True)}" data-doc="{html.escape(key, quote=True)}">{label}</a>'
    return re.sub(r'<a href="([^"]*)" data-doc="([^"]*)">([^<]*)</a>', replace, rendered)


def model_looks(root, identity):
    folder = resources.local(root, '综合资料/共用素材/造型')
    for path in sorted(folder.glob('L*-*/造型说明.md')):
        if not path.resolve().is_relative_to(folder):
            raise ValueError('造型说明越出造型资料目录')
        look_id, name = path.parent.name.split('-', 1)
        doc = read_document(root, path, template('chloe-assets', '造型说明模板.md'),
                            {'identity': look_id, 'title': name})
        if fields(doc, '造型组合')['模特编号'] == identity:
            yield look_id, name, path, doc


def model_files(root, identity, path, doc):
    allowed = linked_files(root, path, doc)
    for _, _, look_path, look_doc in model_looks(root, identity):
        allowed.update(linked_files(root, look_path, look_doc))
    return allowed


def asset_content(root, path, doc, allowed, base):
    source = path.relative_to(root).as_posix()
    adopted = set()
    for row in records(doc, '当前采用'):
        ref = media_reference(root, path, row['资源引用'])
        adopted.add((row['用途'], ref['resource_id'] + '@' + ref['version']))
    images = {}
    # Retain candidates and originals even when they are not currently adopted.
    for row in records(doc, '参考版本') + records(doc, '当前采用'):
        ref = media_reference(root, path, row['资源引用'])
        if Path(ref['file']).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
            raise ValueError('模特参考版本必须为PNG、JPEG或WebP图片')
        key = ref['resource_id'] + '@' + ref['version']
        slot = (row['用途'], key)
        if slot not in images:
            images[slot] = {'purpose': row['用途'], 'resource': ref['resource_id'], 'version': ref['version'],
                           'adopted': slot in adopted,
                           'media': {'kind': 'image', 'name': row['用途'] + ' · ' + key, 'key': ref['file'],
                                     'url': base + '/files/' + quote(ref['file'], safe='/')},
                           'sourceHtml': linked_html(row.get('来源或原图引用', '未取得'), source, allowed, base),
                           'execution': row.get('执行编号', '不适用')}
    sections = []
    for section in doc['sections']:
        if section['heading'] in ('填写说明', '资产身份'):
            continue
        text = []
        for table in section['tables']:
            text.extend(['| ' + ' | '.join(table['columns']) + ' |', '| ' + ' | '.join(['---']*len(table['columns'])) + ' |'])
            text.extend('| ' + ' | '.join(row) + ' |' for row in table['rows'])
        sections.append({'heading': section['heading'], 'html': linked_html('\n'.join(text), source, allowed, base),
                         'empty': not any(t['rows'] for t in section['tables'])})
    return {'images': list(images.values()), 'sections': sections}


def model_detail(root, identity, api):
    name, path, doc = model_context(root, identity)
    base = f'{api}/shared-models/{quote(identity)}'
    allowed = model_files(root, identity, path, doc)
    content = asset_content(root, path, doc, allowed, base)
    looks = []
    for look_id, look_name, look_path, look_doc in model_looks(root, identity):
        cover = next((row for row in records(look_doc, '当前采用') if row['用途'] == '全身三视图遮面版'), None)
        media = None
        if cover:
            ref = media_reference(root, look_path, cover['资源引用'])
            media = {'kind': 'image', 'key': ref['file'], 'name': look_name,
                     'url': base + '/files/' + quote(ref['file'], safe='/')}
        key = look_path.relative_to(root).as_posix()
        looks.append({'id': look_id, 'name': look_name, 'media': media,
                      **asset_content(root, look_path, look_doc, allowed, base),
                      'html': linked_html(look_path.read_text('utf-8-sig').split('## 填写说明')[0], key, allowed, base),
                      'url': base + '/files/' + quote(key, safe='/')})
    return {'id': identity, 'name': name, **content, 'looks': looks,
            'url': base + '/files/' + quote(path.relative_to(root).as_posix(), safe='/')}


def model_file(root, identity, key):
    _, path, doc = model_context(root, identity)
    if key not in model_files(root, identity, path, doc):
        raise FileNotFoundError('文件未被该模特直接引用')
    return resources.local(root, key)


def request_space(request):
    space = request.state.workspace_space
    if space.view != 'chloe-commerce':
        raise HTTPException(404, '该空间未接入带货共用模特')
    return space


@router.get('/{identity}')
def detail(identity: str, request: Request):
    space = request_space(request)
    try:
        return model_detail(space.root, identity, space.api)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get('/{identity}/files/{key:path}')
def linked_file(identity: str, key: str, request: Request, download: bool = False):
    space = request_space(request)
    try:
        path = model_file(space.root, identity, key)
        inline_image = path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}
        return FileResponse(path, filename=path.name if download or not inline_image else None,
                            headers={'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': 'sandbox'})
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get('/{identity}/document')
def linked_document(identity: str, path: str, request: Request):
    space = request_space(request)
    try:
        file = model_file(space.root, identity, path)
        if file.suffix.lower() == '.md':
            _, source, doc = model_context(space.root, identity)
            allowed = model_files(space.root, identity, source, doc)
            base = f'{space.api}/shared-models/{quote(identity)}'
            return {'title': file.stem, 'html': linked_html(file.read_text('utf-8-sig'), path, allowed, base)}
        return documents.plain_text_preview(file)[0]
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
