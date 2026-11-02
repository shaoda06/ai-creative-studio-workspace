"""Registered project spaces owned by the common browser service."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib.parse import quote

from backend.services.project_files import ProjectFiles


@dataclass
class Workspace:
    id: str
    name: str
    root: Path
    runtime: Path
    view: str
    projects: ProjectFiles
    tasks: object = None

    @property
    def api(self):
        return '/api/workspaces/' + self.id

    def public(self):
        return {'id': self.id, 'name': self.name, 'view': self.view, 'projects': self.projects.discover()}


class Workspaces:
    def __init__(self, root, runtime, projects, version):
        self.items = {'nora': Workspace('nora', 'Nora视频创作', root, runtime, 'serial-drama', projects)}
        path = runtime / 'workspaces.json'
        registered = json.loads(path.read_text('utf-8')) if path.is_file() else []
        for item in registered:
            identity = item['id']
            target = Path(item['path']).resolve()
            if not re.fullmatch(r'[a-z][a-z0-9-]*', identity) or identity in self.items:
                raise ValueError('项目空间ID无效或重复：' + identity)
            if target in [space.root for space in self.items.values()] or not (target / 'projects').is_dir():
                raise ValueError('项目空间目录重复或缺少projects目录：' + identity)
            state = target / '工作区浏览服务/runtime'
            self.items[identity] = Workspace(identity, item['name'], target, state, 'files',
                ProjectFiles(target / 'projects'))

    def get(self, identity):
        return self.items[identity]

    def public(self):
        return [space.public() for space in self.items.values()]


def scope_links(value, api):
    """Keep generated resource links in the space that owns the data."""
    if isinstance(value, dict):
        return {key: scope_links(item, api) for key, item in value.items()}
    if isinstance(value, list):
        return [scope_links(item, api) for item in value]
    if isinstance(value, str) and value.startswith('/api/projects/'):
        return api + value[4:]
    if isinstance(value, str) and value.startswith('/#/projects/'):
        return '/#/spaces/' + api.rsplit('/', 1)[1] + value[2:]
    if isinstance(value, str) and ('href=' in value or 'src=' in value):
        return re.sub(r'(href|src)="/api/projects/', lambda match: match[1] + '="' + api + '/projects/', value)
    return value


def project_tree(projects, name, api):
    root = projects.project(name)
    prefix = api + '/projects/' + quote(name, safe='') + '/files/'

    def read(directory):
        result = []
        for path in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
            if path.name.startswith('.') or path.is_symlink():
                continue
            key = path.relative_to(root).as_posix()
            if path.is_dir():
                result.append({'kind': 'group', 'name': path.name, 'key': key, 'children': read(path)})
            elif path.is_file():
                item = {'kind': 'file', 'name': path.name, 'key': key,
                        'url': prefix + quote(key, safe='/')}
                if path.name.endswith('.jianying.json'):
                    package = api + '/projects/' + quote(name, safe='') + '/jianying-download?path=' + quote(key, safe='')
                    item['jianying'] = {'jypack': package + '&format=jypack', 'zip': package + '&format=zip'}
                result.append(item)
        return result

    return {'name': name, 'files': read(root)}
