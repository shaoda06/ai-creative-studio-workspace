"""Project-owned media families, immutable versions and exact file references."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from uuid import uuid4

KINDS = {'图片': {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.avif'},
         '视频': {'.mp4', '.mov', '.webm', '.mkv', '.m4v', '.avi'},
         '音频': {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus', '.aac'}}
PREFIX = {'图片': 'IMG', '视频': 'VID', '音频': 'AUD'}
_CACHE = {}


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def index_path(project):
    return Path(project).resolve() / '资源/资源索引.json'


def enabled(project):
    data = read_index(project)
    return data is not None and data.get('managed', False)


def local(project, value):
    project = Path(project).resolve()
    path = Path(value)
    path = (path if path.is_absolute() else project / path).resolve()
    if not path.is_relative_to(project):
        raise ValueError('资源路径越出所属项目：' + str(value))
    return path


def relative(project, value):
    return local(project, value).relative_to(Path(project).resolve()).as_posix()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, prefix='.' + path.name, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_index(project):
    path = index_path(project)
    if not path.is_file():
        return None
    state = path.stat()
    stamp = (state.st_ino, state.st_mtime_ns, state.st_size)
    cached = _CACHE.get(path)
    if cached is None or cached[0] != stamp:
        cached = _CACHE[path] = (stamp, json.loads(path.read_text('utf-8')))
    return cached[1]


def initialize(project, *, managed=False):
    path = index_path(project)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation keeps a simultaneous first import from replacing an index.
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'format': 1, 'managed': managed, 'families': {}, 'next_versions': {}, 'outputs': {}, 'files': {}, 'aliases': {}}, stream)
        try:
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
        finally:
            temporary.unlink()
    if managed and not read_index(project).get('managed'):
        with edit_index(project) as data:
            data['managed'] = True
    return path


@contextmanager
def edit_index(project):
    path = initialize(project)
    with path.with_suffix('.lock').open('a+b') as lock:
        if sys.platform == 'win32':
            import msvcrt
            lock.seek(0)
            if not lock.read(1):
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = deepcopy(read_index(project))
            yield data
            write_json(path, data)
            _CACHE.pop(path, None)
        finally:
            if sys.platform == 'win32':
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def media_kind(value):
    suffix = Path(value).suffix.lower()
    return next((kind for kind, extensions in KINDS.items() if suffix in extensions), None)


def resolve_file(project, value):
    path = local(project, value)
    data = read_index(project)
    alias = data['aliases'].get(relative(project, path)) if data else None
    return local(project, alias) if alias else path


def reference(project, value):
    path = resolve_file(project, value)
    data = read_index(project)
    return deepcopy(data['files'].get(relative(project, path))) if data else None


def matches_recorded_stamp(project, value, stamp):
    """A byte-compared migration may combine aliases with different old mtimes."""
    data = read_index(project)
    if data is None:
        return False
    key = relative(project, value)
    original = data.get('alias_stamps', {}).get(key)
    if original is None or list(stamp) != [original['bytes'], original['mtime_ns']]:
        return False
    ref = reference(project, key)
    path = local(project, ref['file'])
    return path.is_file() and not path.stat().st_mode & 0o222 and path.stat().st_size == original['bytes'] and (path.parent / '版本信息.json').is_file()


def version_file(project, resource_id, version):
    data = read_index(project)
    matches = [item for item in data['files'].values() if item['resource_id'] == resource_id and item['version'] == version]
    if not matches:
        raise FileNotFoundError(f'没有这个资源版本：{resource_id}@{version}')
    return local(project, matches[0]['file'])


def label(ref):
    return ref['resource_id'] + '@' + ref['version']


def family_key(value):
    """A caller-declared logical name; business numbering belongs to its adapter."""
    return (media_kind(value) or '媒体') + '/' + Path(value).stem


def _reserve(project, data, output, *, key, family=None, resource_id=None, origin='generated', producer=None, parent=None, name=None, alias=True):
    old = relative(project, output)
    if key in data['outputs']:
        return data['files'][data['outputs'][key]]
    if old in data['files']:
        raise ValueError('已有资源版本不能作为新输出位置：' + old)
    if alias and old in data['aliases']:
        raise ValueError('历史地址已绑定原版本，不能用于新输出：' + old)
    kind = media_kind(output)
    if kind is None:
        raise ValueError('不支持的媒体格式：' + str(output))
    parent_ref = None
    if parent:
        parent_path = local(project, data['aliases'].get(relative(project, parent), relative(project, parent)))
        parent_ref = data['files'].get(relative(project, parent_path))
        if parent_ref is None:
            raise ValueError('实际来源须先登记为固定资源版本：' + str(parent))
    if resource_id:
        entry = next((item for item in data['families'].values() if item['resource_id'] == resource_id), None)
        if entry is None:
            raise ValueError('没有这个资源编号：' + resource_id)
    else:
        family = family or (parent_ref['family_key'] if parent_ref else family_key(output))
        entry = data['families'].get(family)
        if entry is None:
            resource_id = PREFIX[kind] + '-' + uuid4().hex[:12]
            entry = data['families'][family] = {'resource_id': resource_id, 'kind': kind, 'family_key': family}
            write_json(Path(project) / '资源' / kind / resource_id / '资源信息.json',
                       {**entry, 'name': name or Path(output).stem, 'created_at': now()})
    if entry['kind'] != kind:
        raise ValueError('不同媒体类型使用独立资源，来源在记录中关联')
    resource_id = entry['resource_id']
    number = data['next_versions'].get(resource_id, 1)
    data['next_versions'][resource_id] = number + 1
    version = f'V{number:03d}'
    destination = Path(project) / '资源' / kind / resource_id / version / Path(output).name
    ref = {'resource_id': resource_id, 'version': version, 'file': relative(project, destination),
           'family_key': entry['family_key'], 'kind': kind, 'origin': origin, 'producer': producer,
           'parent': {field: parent_ref[field] for field in ('resource_id', 'version', 'file', 'kind')} if parent_ref else None}
    data['outputs'][key] = ref['file']
    data['files'][ref['file']] = ref
    if alias and not old.startswith('资源/'):
        data['aliases'][old] = ref['file']
    return ref


def reserve(project, output, *, key=None, **options):
    with edit_index(project) as data:
        ref = _reserve(project, data, output, key=key or relative(project, output), **options)
    return deepcopy(ref)


def facts(path):
    path = Path(path)
    kind = media_kind(path)
    result = {'bytes': path.stat().st_size}
    if kind == '图片':
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(path) as image:
                result.update(width=image.width, height=image.height, format=image.format)
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as error:
            raise ValueError('图片无法解码') from error
    else:
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)],
                               capture_output=True, text=True, check=True)
        info = json.loads(probe.stdout)
        result['duration_seconds'] = float(info['format']['duration'])
        for stream in info['streams']:
            if stream['codec_type'] == 'video' and kind == '视频':
                result.update(width=stream['width'], height=stream['height'], codec=stream['codec_name'])
                if stream.get('avg_frame_rate') not in (None, '0/0'):
                    result['fps'] = float(Fraction(stream['avg_frame_rate']))
                break
        result['audio'] = any(stream['codec_type'] == 'audio' for stream in info['streams'])
    return result


def finish(project, value, *, info=None):
    ref = reference(project, value)
    if ref is None:
        return None
    path = local(project, ref['file'])
    metadata = path.parent / '版本信息.json'
    details = info if info is not None else facts(path)
    if metadata.exists():
        previous = json.loads(metadata.read_text('utf-8'))
        if previous['facts']['bytes'] != path.stat().st_size:
            raise ValueError('资源版本的文件发生变化：' + label(ref))
        return ref
    path.chmod(path.stat().st_mode & ~0o222)
    write_json(metadata, {**ref, 'registered_at': now(), 'facts': details})
    return ref


def register(project, source, *, resource_id=None, name=None, origin='user_upload', producer=None,
             parent=None, key=None, output=None, family=None, info=None, source_range=None):
    """Import once; a new independent upload is not inferred from its filename."""
    from media_files import store_media
    project, source = Path(project).resolve(), Path(source).resolve()
    if source_range is not None and (parent is None or source_range[0] < 0 or source_range[1] <= 0):
        raise ValueError('处理区间须指明实际来源版本，且起点非负、长度为正')
    output = output or project / source.name
    family = family or ('导入/' + uuid4().hex if resource_id is None else None)
    ref = reserve(project, output, key=key or '导入/' + uuid4().hex, resource_id=resource_id,
                  family=family, origin=origin, producer=producer, parent=parent, name=name, alias=False)
    destination = local(project, ref['file'])
    store_media(project, destination, source=source)
    finish(project, destination, info=info)
    if source_range is not None:
        if not ref['parent']:
            raise ValueError('处理区间须同时指明实际来源版本')
        start, duration = source_range
        if start < 0 or duration <= 0:
            raise ValueError('处理起点须非负，长度须为正数')
        metadata = destination.parent / '版本信息.json'
        data = json.loads(metadata.read_text('utf-8'))
        recorded = {'start_seconds': start, 'duration_seconds': duration}
        if 'source_range' in data and data['source_range'] != recorded:
            raise ValueError('重试的来源区间与已有记录不同')
        data['source_range'] = recorded
        write_json(metadata, data)
    return ref


def catalog(project, resource_id=None):
    data = read_index(project)
    if data is None:
        return []
    families = {item['resource_id']: {**json.loads((Path(project) / '资源' / item['kind'] / item['resource_id'] / '资源信息.json').read_text('utf-8')),
                                     'versions': []} for item in data['families'].values() if resource_id is None or item['resource_id'] == resource_id}
    for ref in data['files'].values():
        if ref['resource_id'] not in families:
            continue
        metadata = local(project, ref['file']).parent / '版本信息.json'
        if metadata.is_file():
            version = json.loads(metadata.read_text('utf-8'))
            families[ref['resource_id']]['versions'].append(version)
    for family in families.values():
        family['versions'].sort(key=lambda item: item['version'])
    return sorted((item for item in families.values() if item['versions']), key=lambda item: (item['kind'], item['name']))


def refs_in(project, document):
    """Add exact references alongside existing local paths, not inside original API blobs."""
    found = {}
    def visit(value):
        if isinstance(value, dict):
            for field, child in value.items():
                if field != 'original_file':
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str) and media_kind(value):
            path = Path(value)
            root = Path(project).resolve()
            if not (path if path.is_absolute() else root / path).resolve().is_relative_to(root):
                return
            ref = reference(project, value)
            if ref is not None:
                found[label(ref)] = ref
    visit(document)
    return list(found.values())


def route_task(project, payload):
    """Resolve local inputs and allocate exact outputs before a task is accepted."""
    if not enabled(project):
        return payload
    record = relative(project, payload['record_dir'])
    plan = payload.get('image_plan')
    parent = (plan.get('base_file') or plan.get('upscale', {}).get('source')) if plan else None
    formal = plan.get('formal') if plan else None
    target_family = reference(project, formal) if formal else None
    explicit = plan.get('resource_id') if plan else None
    renamed = {}
    targets = [*payload.get('outputs', []), *(payload.get('segment_plan') or {}).get('targets', [])]
    for target in targets:
        old = relative(project, target['path'])
        ref = reference(project, old)
        if ref is not None and ref['producer'] != record:
            raise ValueError('新任务须使用新的输出位置；已有版本保持不变：' + old)
        if ref is None:
            actual_parent = target.get('base_file') or parent
            if actual_parent is None and payload['task_type'] == 'video-postprocess':
                sources = [item['file'] for item in payload.get('uploads', [])
                           if media_kind(item.get('file', '')) == '视频' and reference(project, item['file'])]
                if len(set(sources)) == 1:
                    actual_parent = sources[0]
            ref = reserve(project, old, key=record + '/' + Path(old).name,
                          resource_id=target.get('resource_id') or explicit or (target_family['resource_id'] if target_family else None),
                          family=target.get('resource_key') or (family_key(formal) if formal else None),
                          parent=actual_parent,
                          origin='process' if payload['task_type'] in ('image-upscale', 'video-postprocess') else 'generated',
                          producer=record)
        target.update(path=str(local(project, ref['file'])), resource_id=ref['resource_id'], version=ref['version'])
        renamed[old] = ref
    for upload in payload.get('uploads', []):
        if isinstance(upload.get('file'), str):
            upload['file'] = str(resolve_file(project, upload['file']))
            ref = reference(project, upload['file'])
            if ref:
                upload['resource'] = {key: ref[key] for key in ('resource_id', 'version')}
    if plan:
        for image in plan['images']:
            old = relative(project, image['path'])
            ref = renamed.get(old) or reference(project, old)
            image['path'] = ref['file']
            image['resource_id'], image['version'] = ref['resource_id'], ref['version']
        ref = reference(project, plan['images'][0]['path'])
        plan['resource_id'], plan['resource_version'] = ref['resource_id'], ref['version']
        if plan.get('upscale'):
            plan['upscale']['source'] = relative(project, resolve_file(project, plan['upscale']['source']))
            plan['upscale']['formal'] = ref['file']
            plan['formal'] = ref['file']
    return payload


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='项目图片、视频、音频资源与不可覆盖版本；不生成媒体或批准采用')
    parser.add_argument('--project', type=Path, required=True)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('init')
    commands.add_parser('list')
    add = commands.add_parser('import')
    add.add_argument('--file', type=Path, required=True)
    add.add_argument('--name')
    add.add_argument('--resource-id', help='同一素材的修订版本填写原资源编号；独立素材不填')
    add.add_argument('--origin', choices=['user_upload', 'import', 'generated', 'process'], default='user_upload')
    add.add_argument('--key', help='同一次导入的稳定身份；重试复用，不把文件名当导入身份')
    add.add_argument('--parent', help='实际来源文件；提取音轨等跨类型结果会建立新资源并保留来源')
    add.add_argument('--producer', help='本项目内实际技术处理记录目录')
    add.add_argument('--start', type=float, help='来源连续区间起点，单位秒；与--duration配对')
    add.add_argument('--duration', type=float, help='来源连续区间长度，单位秒')
    args = parser.parse_args()
    if args.action == 'init':
        print(initialize(args.project, managed=True))
    elif args.action == 'list':
        print(json.dumps(catalog(args.project), ensure_ascii=False))
    else:
        if (args.start is None) != (args.duration is None) or args.start is not None and not args.parent:
            parser.error('--start与--duration须配对，并同时提供--parent')
        print(json.dumps(register(args.project, args.file, resource_id=args.resource_id, name=args.name,
                                  origin=args.origin, key=args.key, parent=args.parent, producer=args.producer,
                                  source_range=(args.start, args.duration) if args.start is not None else None), ensure_ascii=False))
