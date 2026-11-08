"""Document snapshots with exact project resource references, never media copies."""
import argparse
from contextlib import contextmanager
from copy import copy
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

import project_resources as resources

MANIFEST = '快照资源引用.json'
BUNDLES = {'.zip', '.jypack', '.7z', '.tar', '.gz', '.safetensors', '.latent'}
EXCLUDED = {'.git', '.codex', '.venv', 'node_modules', '__pycache__'}


def member_path(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value or ':' in value:
        raise ValueError('快照内路径必须相对项目且不能越界：' + value)
    return path


def media_reference(project, value):
    ref = resources.reference(project, value)
    if ref is None:
        raise ValueError('媒体须先登记为项目资源版本：' + str(value))
    path = resources.local(project, ref['file'])
    if path.stat().st_mode & 0o222:
        raise ValueError('快照只能引用已只读保存的资源版本：' + str(value))
    return {key: ref[key] for key in ('resource_id', 'version', 'file', 'kind')} | {'bytes': path.stat().st_size}


def referenced_file(project, ref):
    actual = media_reference(project, ref['file'])
    if actual != ref:
        raise ValueError('快照引用的具体资源版本或大小已变化：' + ref['file'])
    return resources.local(project, ref['file'])


@contextmanager
def write_zip(target, *, replace=False):
    target = Path(target)
    before = target.stat() if replace else None
    if not replace and target.exists():
        raise FileExistsError('快照已存在，复用原入口或另选实际版本：' + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.zip', delete=False) as stream:
        pending = Path(stream.name)
    try:
        with ZipFile(pending, 'w', compression=ZIP_DEFLATED) as bundle:
            yield bundle
        with ZipFile(pending) as bundle:
            bad = bundle.testzip()
            if bad:
                raise ValueError('快照文件未通过完整读取：' + bad)
        if replace:
            current = target.stat()
            if (current.st_ino, current.st_size, current.st_mtime_ns) != (before.st_ino, before.st_size, before.st_mtime_ns):
                raise ValueError('整理期间快照发生变化，未替换原件')
            pending.replace(target)
        else:
            os.link(pending, target)
    finally:
        pending.unlink(missing_ok=True)


def create(project, output, includes):
    project = Path(project).resolve()
    output = resources.local(project, output)
    documents = {}
    manifest = {'format': 1, 'media': {}, 'attachments': {}, 'unparsed_documents': {}}
    selected = set()
    for item in includes:
        path = resources.local(project, item)
        if not path.exists():
            raise FileNotFoundError(path)
        for file in path.rglob('*') if path.is_dir() else [path]:
            if file.is_file() and not EXCLUDED.intersection(file.relative_to(project).parts) and file != output:
                resources.local(project, file)
                selected.add(file)
    for path in sorted(selected):
        key = path.relative_to(project).as_posix()
        if key == MANIFEST:
            raise ValueError('源文件占用了快照清单名称：' + key)
        if resources.media_kind(path):
            manifest['media'][key] = media_reference(project, path)
            continue
        if path.suffix.lower() in BUNDLES:
            manifest['attachments'][key] = {'file': key, 'bytes': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns}
            continue
        documents[key] = path
        refs = []
        if path.suffix.lower() == '.json':
            try:
                refs = resources.refs_in(project, json.loads(path.read_text('utf-8-sig')))
            except json.JSONDecodeError as error:
                manifest['unparsed_documents'][key] = str(error)
        elif path.suffix.lower() == '.md':
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text('utf-8-sig')):
                parsed = urlsplit(link.strip('<>'))
                if not parsed.scheme and resources.media_kind(unquote(parsed.path)):
                    source = resources.local(project, path.parent / unquote(parsed.path))
                    ref = media_reference(project, source)
                    manifest['media'][source.relative_to(project).as_posix()] = ref
        for ref in refs:
            manifest['media'][ref['file']] = media_reference(project, ref['file'])
    with write_zip(output) as bundle:
        for key, path in documents.items():
            bundle.write(path, key)
        bundle.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
    return {'documents': len(documents), 'media_references': len(manifest['media']),
            'attachment_references': len(manifest['attachments']), 'unparsed_documents': manifest['unparsed_documents']}


def compact(project, archive, mapping):
    """Explicitly authorized conversion; compare every omitted member in full."""
    project = Path(project).resolve()
    archive = resources.local(project, archive)
    manifest = {'format': 1, 'media': {}, 'attachments': {}, 'unparsed_documents': {}}
    removed_bytes = 0
    with ZipFile(archive) as original:
        if MANIFEST in original.namelist():
            saved = json.loads(original.read(MANIFEST))
            for ref in saved['media'].values():
                referenced_file(project, ref)
            return {'changed': False, 'media_references': len(saved['media'])}
        for item in original.infolist():
            member_path(item.filename)
            if item.is_dir() or not resources.media_kind(item.filename):
                continue
            ref = media_reference(project, mapping[item.filename])
            source = referenced_file(project, ref)
            with original.open(item) as left, source.open('rb') as right:
                while True:
                    block = left.read(1024 * 1024)
                    if block != right.read(1024 * 1024):
                        raise ValueError('快照媒体与固定版本内容不同，原包未修改：' + item.filename)
                    if not block:
                        break
            manifest['media'][item.filename] = ref
            removed_bytes += item.compress_size
        with write_zip(archive, replace=True) as bundle:
            bundle.comment = original.comment
            for item in original.infolist():
                if item.filename not in manifest['media']:
                    with original.open(item) as source, bundle.open(copy(item), 'w') as target:
                        shutil.copyfileobj(source, target)
            bundle.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
            # Original records must survive byte-for-byte before publishing the smaller archive.
            bundle.close()
            with ZipFile(bundle.filename) as result:
                for item in original.infolist():
                    if not item.is_dir() and item.filename not in manifest['media']:
                        with original.open(item) as left, result.open(item.filename) as right:
                            while True:
                                block = left.read(1024 * 1024)
                                if block != right.read(1024 * 1024):
                                    raise ValueError('快照原记录变化，未替换原件：' + item.filename)
                                if not block:
                                    break
            original.close()
    return {'changed': True, 'media_references': len(manifest['media']), 'removed_media_zip_bytes': removed_bytes,
            'documents_preserved': sum(not item.is_dir() and item.filename not in manifest['media'] for item in original.infolist())}


def restore(project, archive, destination):
    project = Path(project).resolve()
    archive = resources.local(project, archive)
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('仅恢复到新的独立目录，不覆盖原资料：' + str(destination))
    with ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read(MANIFEST))
        sources = {key: referenced_file(project, ref) for key, ref in manifest['media'].items()}
        for key, ref in manifest['attachments'].items():
            source = resources.local(project, ref['file'])
            state = source.stat()
            if (state.st_size, state.st_mtime_ns) != (ref['bytes'], ref['mtime_ns']):
                raise ValueError('快照引用的附件已变化：' + key)
            sources[key] = source
        for key in [*bundle.namelist(), *sources]:
            member_path(key)
        destination.mkdir(parents=True)
        for item in bundle.infolist():
            target = destination / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)
        for key, source in sources.items():
            target = destination / key
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open('rb') as stream, target.open('xb') as output:
                shutil.copyfileobj(stream, output)
    return {'restored_records_and_manifest': len(bundle.infolist()), 'restored_references': len(sources)}


def main():
    parser = argparse.ArgumentParser(description='项目快照：保存原记录和固定资源引用，不复制媒体或嵌套打包附件')
    parser.add_argument('--project', type=Path, required=True, help='所属项目根目录')
    commands = parser.add_subparsers(dest='action', required=True)
    add = commands.add_parser('create', help='新建文档与资源引用快照')
    add.add_argument('--output', required=True, help='项目内新ZIP位置；不覆盖已有快照')
    add.add_argument('--include', action='append', required=True, help='本次受影响文件或目录，相对项目；可重复指定，不默认整树备份')
    convert = commands.add_parser('compact', help='仅在明确授权后精简既有完整快照，原记录保持字节不变')
    convert.add_argument('--archive', required=True, help='项目内待整理ZIP')
    convert.add_argument('--mapping', type=Path, required=True, help='JSON对象：包内媒体原路径→项目内准确资源文件')
    recover = commands.add_parser('restore', help='将记录及其引用恢复到新的独立目录')
    recover.add_argument('--archive', type=Path, required=True, help='待恢复ZIP位置')
    recover.add_argument('--destination', type=Path, required=True, help='尚不存在的恢复目录；不覆盖项目')
    args = parser.parse_args()
    if args.action == 'create':
        result = create(args.project, args.output, args.include)
    elif args.action == 'compact':
        result = compact(args.project, args.archive, json.loads(args.mapping.read_text('utf-8')))
    else:
        result = restore(args.project, args.archive, args.destination)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
