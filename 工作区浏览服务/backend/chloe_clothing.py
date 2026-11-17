"""Clothing records and the named project's outfit styles."""
import json
import re
from functools import partial
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.chloe_models import request_space
from backend.chloe_overview import fields
from backend.chloe_reference_assets import CLOTHING, asset_cards, asset_context, asset_detail, asset_documents, asset_file, asset_router
from chloe_documents import DEFAULT_OUTFIT_STYLE, outfit_style_name, outfit_styles, read_document, template
import project_resources as resources


clothing_cards = partial(asset_cards, kind=CLOTHING)
clothing_detail = partial(asset_detail, kind=CLOTHING)
clothing_file = partial(asset_file, kind=CLOTHING)
style_router = APIRouter(prefix='/shared-clothing')
write_router = APIRouter(prefix='/shared-clothing')
router = asset_router(CLOTHING)
style_write_lock = Lock()
style_heading = '# 套装风格分类'


class StyleChange(BaseModel):
    style: str


class StylesChange(BaseModel):
    styles: list[str]


class StyleRename(StyleChange):
    name: str


def style_path(root):
    return resources.local(root, '综合资料/共用素材/服装/套装风格分类.md')


def read_styles(path):
    try:
        text = path.read_text('utf-8')
    except FileNotFoundError:
        return [DEFAULT_OUTFIT_STYLE]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != style_heading or any(not line.startswith('- ') for line in lines[1:]):
        raise ValueError('套装风格分类清单须使用规定标题及逐行列表')
    styles = [outfit_style_name(line[2:]) for line in lines[1:]]
    if DEFAULT_OUTFIT_STYLE not in styles or len(styles) != len({name.casefold() for name in styles}):
        raise ValueError('套装风格分类清单须保留未分类，且名称不能重复')
    return styles


def save_text(path, text):
    stream = NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=path.parent,
                                prefix='.outfit-style-', suffix='.tmp', delete=False)
    temporary = Path(stream.name)
    try:
        with stream:
            stream.write(text)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def save_styles(path, styles):
    save_text(path, style_heading+'\n\n'+''.join(f'- {item}\n' for item in styles))


def outfit_style_edit(root, identity, title, path, info, styles):
    value = styles[0] if len(styles) == 1 else json.dumps(styles, ensure_ascii=False)
    if info.get('风格') == value:
        return None
    original = path.read_bytes().decode('utf-8')
    match = re.search(r'^[ \t]*## 服装信息[ \t]*\r?\n(.*?)(?=^[ \t]*## |\Z)', original, re.S | re.M)
    section = match[1]
    newline = '\r\n' if '\r\n' in section else '\n'
    row = f'| 风格 | {value} |'
    if '风格' in info:
        edited = re.sub(r'(?m)^[ \t]*\|[ \t]*风格[ \t]*\|[^\r\n]*', lambda _: row, section, count=1)
    else:
        edited = re.sub(r'(?m)^[ \t]*\|[ \t]*组成与穿法[ \t]*\|', lambda found: row+newline+found[0], section, count=1)
    body = original[:match.start(1)]+edited+original[match.end(1):]
    read_document(root, path, template('chloe-assets', '服装说明模板.md'),
                  {'identity': identity, 'title': title}, body=body)
    return original, body


@style_router.get('/styles')
def list_styles(request: Request) -> list[str]:
    space = request_space(request)
    try:
        with style_write_lock:
            return read_styles(style_path(space.root))
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@write_router.post('/styles', status_code=201)
def add_style(change: StyleChange, request: Request) -> list[str]:
    space = request_space(request)
    try:
        name = outfit_style_name(change.style)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    try:
        with style_write_lock:
            path = style_path(space.root)
            styles = read_styles(path)
            if name.casefold() in {item.casefold() for item in styles}:
                raise ValueError('该风格已存在')
            styles.append(name)
            save_styles(path, styles)
        return styles
    except FileNotFoundError as error:
        raise HTTPException(404, '服装资料目录不存在') from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


def change_catalog(root, style, name):
    try:
        if name is not None:
            name = outfit_style_name(name)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    try:
        with style_write_lock:
            catalog_path = style_path(root)
            catalog = read_styles(catalog_path)
            if style == DEFAULT_OUTFIT_STYLE:
                raise ValueError('未分类为默认风格，不能重命名或删除')
            if style not in catalog:
                raise HTTPException(404, '该风格已不存在')
            if name == style:
                return catalog
            if name is not None and any(item != style and item.casefold() == name.casefold() for item in catalog):
                raise ValueError('该风格已存在')
            next_catalog = [name if item == style else item for item in catalog if name is not None or item != style]
            edits = []
            for identity, title, path, doc in asset_documents(root, CLOTHING):
                info = fields(doc, '服装信息')
                if info.get('服装形态') != '套装':
                    continue
                selected = outfit_styles(info.get('风格', DEFAULT_OUTFIT_STYLE))
                if style not in selected:
                    continue
                replacement = outfit_styles([name if item == style else item for item in selected
                                             if name is not None or item != style])
                original, updated = outfit_style_edit(root, identity, title, path, info, replacement)
                edits.append((path, original, updated))
            saved = []
            try:
                for path, original, updated in edits:
                    save_text(path, updated)
                    saved.append((path, original))
                save_styles(catalog_path, next_catalog)
            except OSError:
                for path, original in reversed(saved):
                    save_text(path, original)
                raise
            return next_catalog
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except OSError as error:
        raise HTTPException(500, '无法保存风格变更，请检查项目资料是否可写') from error


@write_router.patch('/styles')
def rename_style(change: StyleRename, request: Request) -> list[str]:
    return change_catalog(request_space(request).root, change.style, change.name)


@write_router.delete('/styles')
def delete_style(change: StyleChange, request: Request) -> list[str]:
    return change_catalog(request_space(request).root, change.style, None)


@write_router.put('/{identity}/style')
def change_style(identity: str, change: StylesChange | StyleChange, request: Request):
    space = request_space(request)
    try:
        with style_write_lock:
            _, title, path, doc = asset_context(space.root, identity, CLOTHING)
            info = fields(doc, '服装信息')
            if info.get('服装形态') != '套装':
                raise ValueError('只有套装可以修改风格')
            styles = outfit_styles(change.styles if isinstance(change, StylesChange) else [change.style])
            catalog = read_styles(style_path(space.root))
            if any(name not in catalog for name in styles):
                raise ValueError('请选择已登记的风格')
            edit = outfit_style_edit(space.root, identity, title, path, info, styles)
            if edit:
                save_text(path, edit[1])
        return {'outfitStyles': styles} if isinstance(change, StylesChange) else {'outfitStyle': styles[0]}
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
