"""Portable, atomic technical records; legacy individual evidence stays readable.

The workspace backend is the sole writer of a compact task archive. Its worker
threads share the lock below. Independent legacy clients keep exclusive files.
"""
import json
import os
from pathlib import Path
import tempfile
from threading import RLock

ARCHIVE = '执行档案.json'
_LOCK = RLock()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("Non-finite JSON value: " + value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def _load(path):
    return strict_json(path.read_bytes())


def _save(path, value, *, pretty=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.execution-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, **({'indent': 2} if pretty else {'separators': (',', ':')}))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def initialize(directory):
    path = Path(directory) / ARCHIVE
    with _LOCK:
        if not path.exists():
            _save(path, {'format': 1, 'records': {}, 'versions': {}})
    return path


def exists(path):
    path = Path(path)
    if path.is_file():
        return True
    archive = path.parent / ARCHIVE
    return archive.is_file() and path.name in _load(archive)['records']


def read(path):
    path = Path(path)
    if path.is_file():
        return _load(path)
    archive = path.parent / ARCHIVE
    if archive.is_file():
        records = _load(archive)['records']
        if path.name in records:
            return records[path.name]
    raise FileNotFoundError(path)


def text(path):
    return json.dumps(read(path), ensure_ascii=False, indent=2) + '\n'


def backing_file(path):
    path = Path(path)
    if path.is_file():
        return path
    if exists(path):
        return path.parent / ARCHIVE
    raise FileNotFoundError(path)


def write(path, value, *, new=False, compact=None):
    path = Path(path)
    archive = path.parent / ARCHIVE
    if compact is False or compact is None and not archive.is_file():
        if not new:
            _save(path, value, pretty=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x' if new else 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        return
    with _LOCK:
        if path.is_file():
            raise FileExistsError('旧独立凭据不能原位改成聚合记录：' + str(path))
        data = _load(archive) if archive.is_file() else {'format': 1, 'records': {}, 'versions': {}}
        if new and path.name in data['records']:
            raise FileExistsError(path)
        if not new and data['records'].get(path.name) == value:
            return
        data['records'][path.name] = value
        data['versions'][path.name] = data['versions'].get(path.name, 0) + 1
        _save(archive, data)


def entry_stamp(path):
    path = Path(path)
    archive = path.parent / ARCHIVE
    if not archive.is_file():
        raise FileNotFoundError(path)
    data = _load(archive)
    if path.name not in data['records']:
        raise FileNotFoundError(path)
    return len(json.dumps(data['records'][path.name], ensure_ascii=False)), data['versions'][path.name]


def stamp(path):
    path = Path(path)
    try:
        current = path.stat()
    except FileNotFoundError:
        return entry_stamp(path)
    return current.st_size, current.st_mtime_ns


def write_entries(directory, values):
    """Publish a consistent state/event snapshot with one atomic replacement."""
    archive = Path(directory) / ARCHIVE
    with _LOCK:
        data = _load(archive) if archive.is_file() else {'format': 1, 'records': {}, 'versions': {}}
        changed = False
        for name, value in values.items():
            if (Path(directory) / name).is_file():
                raise FileExistsError('旧独立凭据不能原位改成聚合记录：' + name)
            if data['records'].get(name) != value:
                data['records'][name] = value
                data['versions'][name] = data['versions'].get(name, 0) + 1
                changed = True
        if changed:
            _save(archive, data)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='读取聚合或旧式执行凭据；只在明确指定export时另存文件')
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('read', 'export'):
        item = commands.add_parser(command)
        item.add_argument('path', help='执行档案.json或原逻辑凭据路径；相对路径按当前目录解析')
        if command == 'export':
            item.add_argument('--output', required=True, help='明确的新JSON文件路径，不覆盖已有文件')
    args = parser.parse_args()
    value = read(Path(args.path))
    if args.command == 'export':
        if exists(Path(args.output)):
            raise FileExistsError(args.output)
        write(Path(args.output), value, new=True, compact=False)
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
