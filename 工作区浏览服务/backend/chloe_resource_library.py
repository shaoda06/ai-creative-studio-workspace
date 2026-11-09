"""Read-only, context-scoped Chloe media versions and their existing references."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Annotated
from urllib.parse import quote, unquote, urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
import project_resources as resources
from backend.chloe_models import request_space, linked_html
from backend.parsers import documents
from backend.chloe_reference_assets import VOICES, asset_documents
from backend.chloe_overview import fields
from chloe_documents import MEDIA as MEDIA_REFERENCE, parse, records
from chloe_init import ASSETS

router = APIRouter(prefix='/resource-library')
MEDIA = {'图片': 'image', '视频': 'video', '音频': 'audio'}


def reference_key(path, value):
    match = MEDIA_REFERENCE.fullmatch(value)
    if match:
        _, identity, version, href = match.groups()
        return ((path.parent/href).resolve(), identity, version)


def visual_titles(root):
    titles = {}
    for kind, (folder, prefix, filename) in ASSETS.items():
        if kind == '声音':
            continue
        for path in sorted((root/'综合资料'/folder).glob(f'{prefix}*-*/{filename}')):
            path = resources.local(root, path)
            doc = parse(path.read_text('utf-8-sig'))
            name = fields(doc, '商品身份' if kind == '商品' else '资产身份')['商品名称' if kind == '商品' else '资产名称']
            for row in records(doc, '原始素材' if kind == '商品' else '参考版本'):
                key = reference_key(path, row['资源引用'])
                if key:
                    titles.setdefault(key, []).append(name+' · '+row['用途'])
    for path in sorted((root/'projects').glob('V*-*/制作记录.md')):
        path = resources.local(root, path)
        doc = parse(path.read_text('utf-8-sig'))
        identity = fields(parse(path.with_name('README.md').read_text('utf-8-sig')), '定位与当前进度')
        name = identity['视频名称']
        stages = {(r['执行编号'], r['输出槽位']): r for r in records(doc, '视频分段执行')}
        for row in records(doc, '输出记录'):
            stage = stages.get((row['执行编号'], row['输出槽位']))
            key = reference_key(path, row['资源引用'])
            if stage and key:
                titles.setdefault(key, []).append(name+' · '+stage['分段编号']+' · '+stage['制作阶段'])
    return titles


def owners(root):
    candidates = [root/'综合资料', *sorted((root/'projects').glob('V*-*'))]
    return [resources.local(root, p) for p in candidates if resources.enabled(p)]


def catalog(root, api):
    entries, scopes = [], []
    visuals = visual_titles(root)
    voice_titles = {}
    for _, _, path, doc in asset_documents(root, VOICES):
        name = fields(doc, '资产身份')['资产名称']
        versions = {}
        for row in sorted(records(doc, '参考版本'), key=lambda row: row['用途'] != '声音原始参考'):
            key = reference_key(path, row['资源引用'])
            if key:
                purpose = '原始参考' if row['用途'] == '声音原始参考' else row['用途']
                versions.setdefault(key, name+' · '+purpose)
        for key, title in versions.items():
            voice_titles.setdefault(key, []).append(title)
    for owner in owners(root):
        scope = owner.relative_to(root).as_posix()
        label = '共用资源' if scope == '综合资料' else owner.name
        scopes.append({'value': scope, 'label': label})
        for family in resources.catalog(owner):
            for version in family['versions']:
                file = resources.local(owner, version['file'])
                key = file.relative_to(root).as_posix()
                display_name = file.name
                if family['kind'] == '音频':
                    titles = voice_titles.get((file, version['resource_id'], version['version']), [])
                    display_name = '；'.join(dict.fromkeys(titles)) or family['name'] or file.name
                else:
                    reference = (file, version['resource_id'], version['version'])
                    titles = visuals.get(reference, []) + voice_titles.get(reference, [])
                    if titles:
                        display_name = '；'.join(dict.fromkeys(titles))
                    elif family['kind'] == '图片' and scope != '综合资料':
                        purpose = file.stem
                        if version.get('producer'):
                            producer = resources.local(owner, version['producer'])
                            if producer.is_file() and producer.suffix == '.json':
                                purpose = json.loads(producer.read_text('utf-8-sig')).get('purpose') or purpose
                        name = fields(parse((owner/'README.md').read_text('utf-8-sig')), '定位与当前进度')['视频名称']
                        display_name = name+' · '+purpose
                entries.append({**version, 'name': file.name, 'title': family['name'], 'display_name': display_name,
                    'owner': scope, 'owner_label': label, 'file': key,
                    'key': scope+'/'+resources.label(version),
                    'media': {'kind': MEDIA[family['kind']], 'key': key, 'name': file.name,
                              'url': api+'/resource-library/files/'+quote(key, safe='/')} if file.is_file() else None})
    entries.sort(key=lambda item: (datetime.fromisoformat(item['registered_at']), item['key']), reverse=True)
    return entries, scopes


def source_documents(root):
    for owner in owners(root):
        for folder, dirs, files in os.walk(owner, followlinks=False):
            dirs[:] = [name for name in dirs if name != '资源' and not name.startswith('.')]
            for name in sorted(files):
                if name.endswith('.md') and not name.startswith('.'):
                    path = (Path(folder)/name).resolve()
                    if path.is_relative_to(root):
                        yield path


def business_link(root, path, page):
    relative = path.relative_to(root)
    parts = relative.parts
    if parts[0] == 'projects' and len(parts) > 2:
        return page+'?section=production&video='+quote(parts[1])
    if len(parts) >= 5 and parts[:2] == ('综合资料', '共用素材'):
        identity = parts[3].split('-', 1)[0]
        category = {'AI模特': ('models', 'model'), '服装': ('clothing', 'clothing'),
                    '配饰': ('accessories', 'accessory'),
                    '场景': ('scenes', 'scene'), '声音': ('voices', 'voice')}.get(parts[2])
        if category:
            return page+f'?section=assets&asset={category[0]}&{category[1]}='+quote(identity)
        if parts[2] == '造型':
            match = re.search(r'^\| 模特编号 \| (M\d+) \|', path.read_text('utf-8-sig'), re.M)
            if match:
                return page+'?section=assets&asset=models&model='+match[1]+'&modelTab=looks&look='+quote(identity)
    return None


def references(root, entry, api):
    """Only report observed exact links and bindings; absence does not mean unused."""
    uses = []
    target = resources.local(root, entry['file'])
    page = api.replace('/api/workspaces/', '/spaces/', 1)
    for path in source_documents(root):
        heading = path.stem
        seen = set()
        for line in path.read_text('utf-8-sig').splitlines():
            if line.startswith('#'):
                heading = line.lstrip('# ').strip()
            for href in re.findall(r'\]\(([^)]+)\)', line):
                parsed = urlsplit(href.strip('<>'))
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                if (path.parent/unquote(parsed.path)).resolve() != target or heading in seen:
                    continue
                seen.add(heading)
                uses.append({'heading': heading, 'path': path.relative_to(root).as_posix(),
                             'excerpt': re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', line).strip(),
                             'to': business_link(root, path, page)})
    for owner in owners(root):
        binding = owner/'资源/共用引用.json'
        if not binding.is_file():
            continue
        for key, ref in json.loads(binding.read_text('utf-8'))['references'].items():
            if ref['file'] == entry['file'] and ref['resource_id'] == entry['resource_id'] and ref['version'] == entry['version']:
                uses.append({'heading': '共用引用 · '+key, 'path': binding.relative_to(root).as_posix(),
                             'excerpt': '已登记准确版本引用；采用与实际执行以原业务记录为准。',
                             'to': page+'?section=production&video='+quote(owner.name)})
    return uses


def detail_data(root, api, owner, resource_id, version):
    entries, _ = catalog(root, api)
    family = [v for v in entries if v['owner'] == owner and v['resource_id'] == resource_id]
    entry = next((v for v in family if v['version'] == version), None)
    if entry is None:
        raise HTTPException(404, '没有这个资源版本')
    source = resources.local(root, owner)
    parent = entry['parent']
    if parent:
        parent = next((v for v in entries if v['owner'] == owner and v['resource_id'] == parent['resource_id'] and v['version'] == parent['version']), None)
    producer = resources.local(source, entry['producer']) if entry['producer'] else None
    producer_path = producer.relative_to(root).as_posix() if producer else None
    if producer and producer.is_dir():
        producer = resources.local(root, producer/'执行档案.json')
    return {**entry, 'versions': sorted(family, key=lambda v: int(v['version'][1:]), reverse=True),
            'parent_entry': parent, 'producer_path': producer_path,
            'producer_file': producer.relative_to(root).as_posix() if producer and producer.is_file() else None,
            'uses': references(root, entry, api)}


def allowed_files(root):
    paths = {p.relative_to(root).as_posix() for p in source_documents(root)}
    for owner in owners(root):
        for family in resources.catalog(owner):
            for version in family['versions']:
                file = resources.local(owner, version['file'])
                paths.add(file.relative_to(root).as_posix())
                if version['producer']:
                    producer = resources.local(owner, version['producer'])
                    if producer.is_dir():
                        producer = resources.local(root, producer/'执行档案.json')
                    paths.add(producer.relative_to(root).as_posix())
        binding = owner/'资源/共用引用.json'
        if binding.is_file():
            paths.add(binding.relative_to(root).as_posix())
    return paths


def library_file(root, key):
    if Path(key).is_absolute() or any(part.startswith('.') for part in Path(key).parts):
        raise HTTPException(404, '文件不在当前资源库可读范围内')
    try:
        path = resources.local(root, key)
    except ValueError as error:
        raise HTTPException(404, '文件不在当前项目内') from error
    if key not in allowed_files(root) or not path.is_file():
        raise HTTPException(404, '未找到资源文件或来源记录')
    return path


@router.get('')
def listing(request: Request, kind: str = '', owner: str = '', q: str = '',
            page: Annotated[int, Query(ge=1)] = 1,
            page_size: Annotated[int, Query(ge=1, le=48)] = 12):
    space = request_space(request)
    entries, scopes = catalog(space.root, space.api)
    entries = [v for v in entries if (not kind or v['kind'] == kind) and (not owner or v['owner'] == owner)
               and (not q or q.casefold() in (v['display_name']+' '+v['name']+' '+v['title']+' '+resources.label(v)).casefold())]
    total = len(entries)
    page = min(page, max(1, (total+page_size-1)//page_size))
    return {'items': entries[(page-1)*page_size:page*page_size], 'owners': scopes,
            'total': total, 'page': page, 'page_size': page_size}


@router.get('/detail')
def detail(request: Request, owner: str, resource_id: str, version: str):
    space = request_space(request)
    return detail_data(space.root, space.api, owner, resource_id, version)


@router.get('/files/{key:path}')
def file(request: Request, key: str, download: bool = False):
    space = request_space(request)
    path = library_file(space.root, key)
    return FileResponse(path, filename=path.name if download else None,
                        headers={'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': 'sandbox'})


@router.get('/document')
def document(request: Request, path: str):
    space = request_space(request)
    file = library_file(space.root, path)
    if file.suffix.lower() == '.md':
        return {'title': file.stem, 'html': linked_html(file.read_text('utf-8-sig'), path,
                allowed_files(space.root), space.api+'/resource-library')}
    if file.suffix.lower() == '.json':
        return documents.plain_text_preview(file)[0]
    raise HTTPException(404, '该文件不是来源文档')
