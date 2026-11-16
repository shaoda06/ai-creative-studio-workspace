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
from backend.chloe_reference_assets import CLOTHING, asset_cards, asset_context, asset_detail, asset_file, asset_router
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


@style_router.get('/styles')
def list_styles(request: Request):
    space = request_space(request)
    try:
        return read_styles(style_path(space.root))
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@write_router.post('/styles', status_code=201)
def add_style(change: StyleChange, request: Request):
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
            save_text(path, style_heading+'\n\n'+''.join(f'- {item}\n' for item in styles))
        return styles
    except FileNotFoundError as error:
        raise HTTPException(404, '服装资料目录不存在') from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


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
            value = styles[0] if len(styles) == 1 else json.dumps(styles, ensure_ascii=False)
            if info.get('风格') != value:
                body = path.read_bytes().decode('utf-8')
                match = re.search(r'^[ \t]*## 服装信息[ \t]*\r?\n(.*?)(?=^[ \t]*## |\Z)', body, re.S | re.M)
                section = match[1]
                newline = '\r\n' if '\r\n' in section else '\n'
                row = f'| 风格 | {value} |'
                if '风格' in info:
                    edited = re.sub(r'(?m)^[ \t]*\|[ \t]*风格[ \t]*\|[^\r\n]*', lambda _: row, section, count=1)
                else:
                    edited = re.sub(r'(?m)^[ \t]*\|[ \t]*组成与穿法[ \t]*\|', lambda found: row+newline+found[0], section, count=1)
                body = body[:match.start(1)]+edited+body[match.end(1):]
                read_document(space.root, path, template('chloe-assets', '服装说明模板.md'),
                              {'identity': identity, 'title': title}, body=body)
                save_text(path, body)
        return {'outfitStyles': styles} if isinstance(change, StylesChange) else {'outfitStyle': styles[0]}
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
