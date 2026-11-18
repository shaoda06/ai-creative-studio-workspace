"""Read-only, context-scoped Chloe media versions and their existing references."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
from collections import OrderedDict
from threading import Lock
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
from backend.chloe_read_cache import stamp
from backend.services.read_views import views, view_response
from backend.chloe_thumbnails import production_thumbnail, thumbnail_url

router = APIRouter(prefix='/resource-library')
MEDIA = {'图片': 'image', '视频': 'video', '音频': 'audio'}
RELEASE = json.loads((Path(__file__).resolve().parents[1] / 'frontend/package.json').read_text('utf-8'))['version']


metadata_cache = OrderedDict()
metadata_lock = Lock()
loaded_metadata_files = set()
saved_metadata_revisions = {}


def read_metadata(path, revision):
    with metadata_lock:
        cached = metadata_cache.get(path)
        if cached and cached[0] == revision:
            metadata_cache.move_to_end(path)
            return cached[1]
    data = json.loads(path.read_text('utf-8-sig'))
    with metadata_lock:
        metadata_cache[path] = (revision, data)
        metadata_cache.move_to_end(path)
        if len(metadata_cache) > 4096:
            metadata_cache.popitem(last=False)
    return data


def resource_versions(owner):
    for family, version, file in resources.catalog_versions(owner, read_metadata=lambda path: read_metadata(path, stamp(path))):
        yield family['name'], family['kind'], version, file


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
            if kind == '参考视频':
                info = fields(doc, '参考视频信息')
                original = reference_key(path, info['原件引用'])
                playback = reference_key(path, info['播放版本引用'])
                if playback:
                    titles.setdefault(playback, []).append(name+' · 参考视频')
                    if original and original != playback:
                        titles.setdefault(original, []).append(name+' · 原件')
                continue
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


def catalog_sources(root):
    paths = [path for folder, prefix, filename in ASSETS.values()
             for path in (root / '综合资料' / folder).glob(f'{prefix}*-*/{filename}')]
    paths.extend(path for project in (root / 'projects').glob('V*-*')
                 for path in (project / 'README.md', project / '制作记录.md'))
    result = {path: stamp(path) for path in paths}
    for owner in owners(root):
        index = resources.read_index(owner)
        result[resources.index_path(owner)] = stamp(resources.index_path(owner))
        for ref in index['files'].values():
            path = owner / ref['file']
            result[path] = stamp(path)
            for metadata in (path.parent / '版本信息.json', path.parent.parent / '资源信息.json'):
                result[metadata] = stamp(metadata)
            if ref['kind'] == '图片' and owner != root / '综合资料':
                metadata = resources.local(owner, path.parent / '版本信息.json')
                revision = stamp(metadata)
                result[metadata] = revision
                if revision is not None:
                    producer = read_metadata(metadata, revision).get('producer')
                    if producer and Path(producer).suffix == '.json':
                        producer = owner / producer
                        result[producer] = stamp(producer)
    return result


def reference_sources(root):
    return {**catalog_sources(root), **{path: stamp(path) for path in source_documents(root)}}


def catalog_cache_file(space):
    return space.runtime / 'read-views' / space.root.name / f'{RELEASE}-resource-catalog.json'


def catalog_view(root, api, *, cache_file=None):
    metadata_file = cache_file.with_name('resource-metadata.json') if cache_file else None
    if metadata_file and metadata_file not in loaded_metadata_files:
        if metadata_file.is_file():
            saved = json.loads(metadata_file.read_text('utf-8'))
            with metadata_lock:
                for key, (revision, data) in saved.items():
                    path = Path(key)
                    if path.is_relative_to(root):
                        metadata_cache.setdefault(path, (tuple(revision), data))
                while len(metadata_cache) > 4096:
                    metadata_cache.popitem(last=False)
        loaded_metadata_files.add(metadata_file)
    result = views.read((root, api, 'resource-catalog', RELEASE), [root], lambda: build_catalog(root, api),
                        source_snapshot=lambda: catalog_sources(root), cache_file=cache_file)
    if metadata_file and saved_metadata_revisions.get(metadata_file) != result[1]:
        with metadata_lock:
            saved = {str(path): value for path, value in metadata_cache.items()
                     if path.is_relative_to(root) and path.name in {'资源信息.json', '版本信息.json'}}
        if saved:
            resources.write_json(metadata_file, saved)
        saved_metadata_revisions[metadata_file] = result[1]
    return result


def catalog(root, api):
    return catalog_view(root, api)[0]


def build_catalog(root, api):
    entries, scopes = [], []
    project_names = {}
    visuals = visual_titles(root)
    voice_titles = {}
    for _, _, path, doc in asset_documents(root, VOICES, catalog=True):
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
        for family_name, family_kind, version, file in resource_versions(owner):
                key = file.relative_to(root).as_posix()
                display_name = file.name
                if family_kind == '音频':
                    titles = voice_titles.get((file, version['resource_id'], version['version']), [])
                    display_name = '；'.join(dict.fromkeys(titles)) or family_name or file.name
                else:
                    reference = (file, version['resource_id'], version['version'])
                    titles = visuals.get(reference, []) + voice_titles.get(reference, [])
                    if titles:
                        display_name = '；'.join(dict.fromkeys(titles))
                    elif family_kind == '图片' and scope != '综合资料':
                        purpose = file.stem
                        if version.get('producer'):
                            producer = resources.local(owner, version['producer'])
                            if producer.is_file() and producer.suffix == '.json':
                                purpose = read_metadata(producer, stamp(producer)).get('purpose') or purpose
                        if owner not in project_names:
                            project_names[owner] = fields(parse((owner/'README.md').read_text('utf-8-sig')), '定位与当前进度')['视频名称']
                        name = project_names[owner]
                        display_name = name+' · '+purpose
                url = api+'/resource-library/files/'+quote(key, safe='/')
                entries.append({**version, 'name': file.name, 'title': family_name, 'display_name': display_name,
                    'owner': scope, 'owner_label': label, 'file': key,
                    'key': scope+'/'+resources.label(version),
                    'media': {'kind': MEDIA[family_kind], 'key': key, 'name': file.name,
                              'url': url, **({'thumbnailUrl': thumbnail_url(url)} if family_kind == '图片' else {})} if file.is_file() else None})
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
    resolved = {}
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
                candidate = Path(os.path.abspath(path.parent / unquote(parsed.path)))
                # A directory alias keeps the filename. A differently named
                # file can match only through a file symlink; retain that case.
                if candidate.name.casefold() != target.name.casefold() and not candidate.is_symlink():
                    continue
                if candidate not in resolved:
                    resolved[candidate] = candidate.resolve()
                if resolved[candidate] != target or heading in seen:
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


def detail_data(root, api, owner, resource_id, version, *, cache_file=None):
    (entries, _), _ = catalog_view(root, api, cache_file=cache_file)
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
    if not path.is_file():
        raise HTTPException(404, '未找到资源文件或来源记录')
    if path.relative_to(root).as_posix() != key:
        raise HTTPException(404, '文件引用路径已改变')
    for owner in owners(root):
        if path.is_relative_to(owner):
            ref = resources.reference(owner, path)
            metadata = path.parent / '版本信息.json'
            if ref and metadata.is_file():
                version = json.loads(metadata.read_text('utf-8'))
                if all(version[field] == ref[field] for field in ('file', 'resource_id', 'version')):
                    return path
    allowed, _ = views.read((root, 'resource-library-files'), [root], lambda: allowed_files(root),
                           source_snapshot=lambda: reference_sources(root))
    if key not in allowed:
        raise HTTPException(404, '未找到资源文件或来源记录')
    return path


@router.get('')
def listing(request: Request, kind: str = '', owner: str = '', q: str = '',
            page: Annotated[int, Query(ge=1)] = 1,
            page_size: Annotated[int, Query(ge=1, le=48)] = 12):
    space = request_space(request)
    (entries, scopes), revision = catalog_view(space.root, space.api, cache_file=catalog_cache_file(space))
    entries = [v for v in entries if (not kind or v['kind'] == kind) and (not owner or v['owner'] == owner)
               and (not q or q.casefold() in (v['display_name']+' '+v['name']+' '+v['title']+' '+resources.label(v)).casefold())]
    total = len(entries)
    page = min(page, max(1, (total+page_size-1)//page_size))
    return view_response(request, revision, lambda: {
        'items': entries[(page-1)*page_size:page*page_size], 'owners': scopes,
        'total': total, 'page': page, 'page_size': page_size})


@router.get('/detail')
def detail(request: Request, owner: str, resource_id: str, version: str):
    space = request_space(request)
    return detail_data(space.root, space.api, owner, resource_id, version,
                       cache_file=catalog_cache_file(space))


@router.get('/files/{key:path}')
def file(request: Request, key: str, download: bool = False, thumbnail: int | None = None):
    space = request_space(request)
    path = library_file(space.root, key)
    if thumbnail is not None and not download:
        return production_thumbnail(space.runtime, path, thumbnail, request)
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
