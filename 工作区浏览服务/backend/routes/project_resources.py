"""Project media versions; business approvals remain in their original records."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
from typing import Annotated
from urllib.parse import quote, unquote, urlsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
import project_resources as resources

_USES = {}


def usages(project):
    files = [path for path in project.rglob('*') if path.is_file()
             and (path.suffix == '.md' or path.name in ('执行档案.json', '资源关联.json'))
             and not any(part in ('资源', '历史版本', '历史制作资料', '归档', '.git') for part in path.relative_to(project).parts)]
    stamp = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in files)
    index = resources.index_path(project)
    stamp += ((str(index), index.stat().st_mtime_ns, index.stat().st_size),)
    cached = _USES.get(project)
    if cached and cached[0] == stamp:
        return cached[1]
    result = {}
    for path in files:
        if path.suffix == '.json':
            data = json.loads(path.read_text('utf-8-sig'))
            association = data.get('records', {}).get('资源关联.json') if path.name == '执行档案.json' else data
            if association:
                for ref in resources.refs_in(project, association):
                    result.setdefault(resources.label(ref), []).append({'path': path.relative_to(project).as_posix(),
                        'heading': path.parent.name + ' · 技术资源关联', 'excerpt': '原技术资料中的资源引用；实际提交与业务采用见原执行及审阅记录。'})
            continue
        heading = path.stem
        seen = set()
        for line in path.read_text('utf-8-sig').splitlines():
            if line.startswith('#'):
                heading = line.lstrip('# ').strip()
            for href in re.findall(r'\]\(([^)]+)\)', line):
                parsed = urlsplit(href.strip('<>'))
                if parsed.scheme or not resources.media_kind(parsed.path):
                    continue
                target = (path.parent / unquote(parsed.path)).resolve()
                if not target.is_relative_to(project):
                    continue
                ref = resources.reference(project, target)
                if ref is None:
                    continue
                key = (resources.label(ref), heading)
                if key in seen:
                    continue
                seen.add(key)
                result.setdefault(resources.label(ref), []).append({
                    'path': path.relative_to(project).as_posix(), 'heading': heading,
                    'excerpt': re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', line).strip()[:240]})
    _USES[project] = (stamp, result)
    return result


def create_router(projects, write_access, *, prefix='/api/projects/{name}/resources'):
    router = APIRouter(prefix=prefix, tags=['project-resources'])

    def project(request, name, writable=False):
        try:
            return projects(request).project(name, writable=writable)
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except PermissionError as error:
            raise HTTPException(409, str(error)) from error

    @router.get('')
    def listing(name: str, request: Request, q: str = '', kind: str = '',
                page: Annotated[int, Query(ge=1)] = 1,
                page_size: Annotated[int, Query(ge=1, le=50)] = 12) -> dict:
        root = project(request, name)
        items = [item for item in resources.catalog(root)
                 if (not kind or item['kind'] == kind) and (not q or q.casefold() in (item['name'] + item['resource_id']).casefold())]
        start = (page - 1) * page_size
        return {'total': len(items), 'page': page, 'page_size': page_size,
                'items': [{key: value for key, value in item.items() if key != 'versions'} | {'version_count': len(item['versions'])}
                          for item in items[start:start + page_size]]}

    @router.get('/{resource_id}')
    def detail(name: str, resource_id: str, request: Request) -> dict:
        root = project(request, name)
        items = resources.catalog(root, resource_id)
        if not items:
            raise HTTPException(404, '资源不存在或尚无实际产出')
        item = items[0]
        base = request.url.path.rsplit('/resources', 1)[0]
        referenced = usages(root)
        for version in item['versions']:
            version['media'] = {'kind': {'图片': 'image', '视频': 'video', '音频': 'audio'}[item['kind']],
                                'key': version['file'], 'name': Path(version['file']).name,
                                'url': base + '/files/' + quote(version['file'], safe='/')}
            version['uses'] = [{**use, 'document': {'kind': 'json' if use['path'].endswith('.json') else 'markdown', 'key': use['path'],
                                'name': use['heading'], 'url': base + '/files/' + quote(use['path'], safe='/')}}
                               for use in referenced.get(resources.label(version), [])]
        return item

    @router.post('', dependencies=[Depends(write_access)])
    def upload(name: str, request: Request, file: Annotated[UploadFile, File()],
               resource_id: Annotated[str | None, Form()] = None,
               parent_version: Annotated[str | None, Form()] = None,
               title: Annotated[str | None, Form(max_length=200)] = None,
               upload_key: Annotated[str | None, Form(max_length=100)] = None) -> dict:
        root = project(request, name, writable=True)
        filename = file.filename or ''
        if not filename or Path(filename).name != filename or '\\' in filename or filename.startswith('.') or resources.media_kind(filename) is None:
            raise HTTPException(422, '请选择有效的图片、视频或音频文件')
        parent = None
        try:
            if parent_version:
                if not resource_id:
                    raise ValueError('指定来源版本时须同时指定资源编号')
                parent = resources.version_file(root, resource_id, parent_version)
            with tempfile.TemporaryDirectory(prefix='studio-resource-upload-') as directory:
                source = Path(directory) / filename
                with source.open('wb') as stream:
                    shutil.copyfileobj(file.file, stream)
                info = resources.facts(source)
                return resources.register(root, source, resource_id=resource_id, name=title,
                                          origin='user_upload', parent=parent, info=info,
                                          key='上传/' + upload_key if upload_key else None)
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except (ValueError, subprocess.CalledProcessError) as error:
            raise HTTPException(422, '无法导入该媒体：' + str(error)) from error
        except OSError as error:
            raise HTTPException(503, '资源保存失败：' + str(error)) from error

    return router
