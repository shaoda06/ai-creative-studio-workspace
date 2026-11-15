"""Reuse read-only workbench views while their source files stay unchanged."""
from dataclasses import dataclass, field
from collections import OrderedDict
import os
from pathlib import Path
from secrets import token_hex
import stat
from threading import Lock

from fastapi.responses import JSONResponse, Response
from project_resources import reuse_read_indexes


def snapshot(roots):
    files = {}
    for root in roots:
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
    data: dict | list | None = None
    tag: str = ''


class ReadViews:
    def __init__(self):
        self.views = OrderedDict()
        self.lock = Lock()

    def read(self, key, roots, build):
        key = (key, tuple(roots))
        with self.lock:
            if key not in self.views:
                self.views[key] = ReadView()
            view = self.views[key]
            self.views.move_to_end(key)
            if len(self.views) > 128:
                self.views.popitem(last=False)
        with view.lock:
            sources = snapshot(roots)
            if view.sources != sources:
                with reuse_read_indexes():
                    data = build()
                tag = '"' + token_hex(16) + '"'
                # Keep the response for this request, but never cache a build
                # across a concurrent change to its source files.
                if sources == snapshot(roots):
                    view.sources, view.data, view.tag = sources, data, tag
                return data, tag
            return view.data, view.tag


views = ReadViews()


def respond_view(request, key, roots, build):
    data, tag = views.read(key, roots, build)
    return view_response(request, tag, lambda: data)


def view_response(request, tag, build):
    headers = {'ETag': tag, 'Cache-Control': 'private, no-cache'}
    requested = request.headers.get('if-none-match', '').split(',')
    if any(value.strip().removeprefix('W/') in (tag, '*') for value in requested):
        return Response(status_code=304, headers=headers)
    return JSONResponse(build(), headers=headers)
