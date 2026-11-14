"""Iris work identities and explicitly declared historical execution sources."""
import json
from pathlib import Path
import re
from project_resources import resolve_file


def work_status_label(lines):
    for line in lines:
        match = re.match(r'^(?:-\s*)?制作状态[：:][ \t]*(.+)', line)
        if match:
            return match[1].strip()
    return ''


def project_works(projects, name):
    works = discover_works(projects.project(name))
    for work in works or []:
        try:
            path = projects.file(name, work['key'] + '/作品状态.md')
            with path.open(encoding='utf-8-sig') as stream:
                work['statusLabel'] = work_status_label(stream)
        except FileNotFoundError:
            continue
    return works


def discover_works(project):
    directory = project / ('03-作品' if (project / '03-作品').exists() else '作品')
    if directory.is_symlink():
        raise ValueError('作品目录不能指向项目外部或其他目录')
    if not directory.is_dir():
        return None  # Legacy project, before the authorized work migration.
    works = []
    for path in sorted(directory.iterdir()):
        match = re.fullmatch(r'(F\d{3,})-(.+)', path.name)
        if not match or not path.is_dir() or path.is_symlink():
            continue
        if any(item['id'] == match[1] for item in works):
            raise ValueError('作品编号重复：' + match[1])
        works.append({'id': match[1], 'name': match[2], 'key': path.relative_to(project).as_posix()})
    return works


def work_root(project, work):
    if work is None:
        return project
    if not re.fullmatch(r'F\d{3,}', work):
        raise FileNotFoundError('作品编号无效')
    entry = next((item for item in discover_works(project) or [] if item['id'] == work), None)
    if entry is None:
        raise FileNotFoundError('作品不存在：' + work)
    return project / entry['key']


def historical_sources(project, work, kind):
    source = work_root(project, work) / '06-视频生产/历史执行入口.json'
    if not source.is_file():
        return []
    declaration = json.loads(source.read_text('utf-8-sig'))
    paths = []
    for value in declaration.get(kind, []):
        relative = Path(value)
        target = resolve_file(project, relative)
        if (relative.is_absolute() or not relative.parts
                or any(part.startswith('.') for part in relative.parts)
                or not target.is_relative_to(project.resolve()) or not target.is_dir()):
            raise ValueError('历史执行来源无效：' + value)
        paths.append(target)
    return paths
