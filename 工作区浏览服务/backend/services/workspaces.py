"""Registered project spaces owned by the common browser service."""
from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote

from backend.services.project_files import ProjectFiles
from workspace_project_index import read_archive


@dataclass
class Workspace:
    id: str
    name: str
    root: Path
    runtime: Path
    view: str
    projects: ProjectFiles
    tasks: object = None
    production_adapter: str | None = None
    project_layout: str = 'flat'
    context: str | None = None

    @property
    def api(self):
        return '/api/workspaces/' + self.id + ('/contexts/' + quote(self.context, safe='') if self.context else '')

    def public(self):
        return {'id': self.id, 'name': self.name, 'view': self.view, **({'project_layout': self.project_layout} if self.project_layout != 'flat' else {}),
                'projects': self.contexts() if self.project_layout == 'nested' else self.projects.discover()}

    def contexts(self):
        return [{'id': path.name, 'name': path.name, **read_archive(path)} for path in sorted(self.root.iterdir())
                if not path.name.startswith('.') and not path.is_symlink() and path.is_dir()
                and (path / 'README.md').is_file() and (path / 'projects').is_dir()
                and (path / '综合资料').is_dir()]

    def select(self, name):
        if self.project_layout != 'nested' or name not in {item['id'] for item in self.contexts()}:
            raise KeyError(name)
        root = self.root / name
        return replace(self, root=root, name=name, projects=ProjectFiles(root / 'projects'), context=name)


class Workspaces:
    def __init__(self, root, runtime, projects, version):
        runtime = Path(runtime).resolve()
        self.items = {'nora': Workspace('nora', 'Nora视频创作', root, runtime / 'workspaces/nora', 'serial-drama', projects)}
        path = runtime / 'workspaces.json'
        registered = json.loads(path.read_text('utf-8')) if path.is_file() else []
        for item in registered:
            identity = item['id']
            target = Path(item['path']).resolve()
            if not re.fullmatch(r'[a-z][a-z0-9-]*', identity) or identity in self.items:
                raise ValueError('项目空间ID无效或重复：' + identity)
            layout = item.get('project_layout', 'flat')
            if layout not in ('flat', 'nested'):
                raise ValueError('项目目录布局无效：' + identity)
            if target in [space.root for space in self.items.values()] or not target.is_dir() or (layout == 'flat' and not (target / 'projects').is_dir()):
                raise ValueError('项目空间目录重复或缺少projects目录：' + identity)
            runtime_id = item.get('runtime_id', identity)
            if not re.fullmatch(r'[a-z][a-z0-9-]*', runtime_id):
                raise ValueError('运行资料标识无效：' + runtime_id)
            state = runtime / 'workspaces' / runtime_id
            if state in [space.runtime for space in self.items.values()]:
                raise ValueError('运行资料目录重复：' + runtime_id)
            view = item.get('view', 'files')
            if view not in ('files', 'iris-commercial', 'chloe-commerce'):
                raise ValueError('项目空间页面类型无效：' + identity)
            self.items[identity] = Workspace(identity, item['name'], target, state, view,
                ProjectFiles(target / 'projects', nested=layout == 'nested'),
                production_adapter=item.get('production_adapter'), project_layout=layout)

        self.task_history_archives = {}
        for item in registered:
            space = self.items[item['id']]
            for entry in item.get('task_history_archives', []):
                source = entry['source_space']
                project = entry['project']
                relative = Path(entry['directory'])
                project_root = space.projects.project(project)
                directory = (project_root / relative).resolve()
                if (source not in self.items or relative.is_absolute()
                        or not relative.parts or any(part.startswith('.') for part in relative.parts)
                        or not directory.is_relative_to(project_root) or not directory.is_dir()):
                    raise ValueError('历史任务归档登记无效：' + project)
                prefix = f'{space.api}/projects/{quote(project, safe="")}/files/{quote(relative.as_posix(), safe="/")}/'
                for task_id in entry['task_ids']:
                    key = (source, task_id)
                    if key in self.task_history_archives:
                        raise ValueError('历史任务归档重复登记：' + task_id)
                    self.task_history_archives[key] = (directory, prefix)

    def get(self, identity):
        return self.items[identity]

    def public(self):
        return [space.public() for space in self.items.values()]


def scope_links(value, api, review_page=None):
    """Keep generated resource links in the space that owns the data."""
    if isinstance(value, dict):
        return {key: scope_links(item, api, review_page) for key, item in value.items()}
    if isinstance(value, list):
        return [scope_links(item, api, review_page) for item in value]
    if isinstance(value, str) and value.startswith('/api/projects/'):
        return api + value[4:]
    if value == '/#/':
        if review_page:
            return review_page('@shared')
        return '/#/spaces/' + api.rsplit('/', 1)[1]
    if isinstance(value, str) and value.startswith('/#/projects/'):
        if review_page:
            return review_page(unquote(value.removeprefix('/#/projects/')))
        return '/#/spaces/' + api.rsplit('/', 1)[1] + value[2:]
    if isinstance(value, str) and ('href=' in value or 'src=' in value):
        return re.sub(r'(href|src)="/api/projects/', lambda match: match[1] + '="' + api + '/projects/', value)
    return value


def jianying_links(api, project, key):
    package = api + '/projects/' + quote(project, safe='') + '/jianying-download?path=' + quote(key, safe='')
    return {'jypack': package + '&format=jypack', 'zip': package + '&format=zip'}


def project_tree(projects, name, api, directory=None):
    root = projects.project(name)
    prefix = api + '/projects/' + quote(name, safe='') + '/files/'

    def read(directory):
        result = []
        for path in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
            if path.name.startswith('.') or path.is_symlink():
                continue
            key = path.relative_to(root).as_posix()
            if path.is_dir():
                result.append({'kind': 'group', 'name': path.name, 'key': key, 'children': [] if key == '资源' else read(path)})
            elif path.is_file():
                item = {'kind': 'file', 'name': path.name, 'key': key,
                        'url': prefix + quote(key, safe='/')}
                if path.name.endswith('.jianying.json'):
                    item['jianying'] = jianying_links(api, name, key)
                if path.name.endswith('.director.json'):
                    item['director'] = api + '/projects/' + quote(name, safe='') + '/director-download?path=' + quote(key, safe='')
                result.append(item)
        return result

    return {'name': name, 'files': read(directory or root)}
