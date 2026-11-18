"""Reuse read-only workbench views while their source files stay unchanged."""
from dataclasses import dataclass, field
from collections import OrderedDict
from hashlib import sha256
import os
import json
from pathlib import Path
from secrets import token_hex
import stat
from threading import Lock
from contextvars import ContextVar
from time import perf_counter
from backend.services.request_diagnostics import record_read_timing

reading = ContextVar('reading_view', default=False)

from fastapi.responses import JSONResponse, Response
from project_resources import reuse_read_indexes, write_json


def snapshot(roots):
    files = {}
    for root in roots:
        if not root.is_dir():
            try:
                info = root.stat()
                files[root] = (info.st_ino, info.st_mtime_ns, info.st_size)
            except FileNotFoundError:
                files[root] = None
            continue
        boundary = root.resolve()
        pending = [(boundary, '')]
        while pending:
            directory, prefix = pending.pop()
            try:
                with os.scandir(directory) as entries:
                    children = list(entries)
            except FileNotFoundError:
                continue
            for item in children:
                key = (root, prefix + item.name)
                if item.name.startswith('.') and item.name != '.archived':
                    continue
                try:
                    info = item.stat(follow_symlinks=False)
                    if item.is_symlink() or (os.name == 'nt' and info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                        if not Path(item.path).resolve().is_relative_to(boundary) or item.is_dir():
                            continue
                        info = item.stat()
                except FileNotFoundError:
                    # An atomic rename/removal will be detected by the next scan.
                    continue
                if stat.S_ISDIR(info.st_mode):
                    pending.append((item.path, key[1] + '/'))
                elif stat.S_ISREG(info.st_mode):
                    files[key] = (info.st_mtime_ns, info.st_size)
    return files


@dataclass
class ReadView:
    lock: Lock = field(default_factory=Lock)
    sources: dict | None = None
    data: object = None
    revision: str = ''


class ReadViews:
    def __init__(self, limit=128):
        self.views = OrderedDict()
        self.lock = Lock()
        self.limit = limit

    def read(self, key, roots, build, *, source_snapshot=None, cache_file=None):
        outer = not reading.get()
        token = reading.set(True)
        try:
            return self._read(key, roots, build, source_snapshot, outer, cache_file)
        finally:
            reading.reset(token)

    def _read(self, key, roots, build, source_snapshot, measure, cache_file):
        key = (key, tuple(roots))
        with self.lock:
            if key not in self.views:
                self.views[key] = ReadView()
            view = self.views[key]
            self.views.move_to_end(key)
            if len(self.views) > self.limit:
                self.views.popitem(last=False)
        started = perf_counter()
        with view.lock:
            if measure:
                record_read_timing('view_wait', perf_counter() - started)
            scan = source_snapshot or (lambda: snapshot(roots))
            started = perf_counter()
            sources = scan()
            if measure:
                record_read_timing('source_check', perf_counter() - started)
            signature = json.dumps(sorted((str(path), value) for path, value in sources.items()),
                                   ensure_ascii=False, sort_keys=True) if cache_file else None
            if view.sources is None and cache_file and cache_file.is_file():
                saved = json.loads(cache_file.read_text('utf-8'))
                if saved['key'] == str(key) and saved['sources'] == signature and sources == scan():
                    view.sources, view.data, view.revision = sources, saved['data'], saved['revision']
            if view.sources != sources:
                started = perf_counter()
                with reuse_read_indexes():
                    data = build()
                if measure:
                    record_read_timing('view_build', perf_counter() - started)
                revision = token_hex(16)
                # Keep the response for this request, but never cache a build
                # across a concurrent change to its source files.
                started = perf_counter()
                stable = sources == scan()
                if measure:
                    record_read_timing('source_recheck', perf_counter() - started)
                if stable:
                    view.sources, view.data, view.revision = sources, data, revision
                    if cache_file:
                        write_json(cache_file, {'key': str(key), 'sources': signature, 'data': data, 'revision': revision})
                return data, revision
            return view.data, view.revision


views = ReadViews()


def respond_view(request, key, roots, build, *, source_snapshot=None):
    data, revision = views.read(key, roots, build, source_snapshot=source_snapshot)
    return view_response(request, revision, lambda: data)


def view_response(request, revision, build):
    # A source revision can serve several pages, filters and candidate contexts.
    variant = sha256(f'{revision}\0{request.url.path}?{request.url.query}'.encode()).hexdigest()
    tag = f'"{variant}"'
    headers = {'ETag': 'W/' + tag, 'Cache-Control': 'private, no-cache'}
    requested = request.headers.get('if-none-match', '').split(',')
    if any(value.strip().removeprefix('W/') in (tag, '*') for value in requested):
        return Response(status_code=304, headers=headers)
    return JSONResponse(build(), headers=headers)
