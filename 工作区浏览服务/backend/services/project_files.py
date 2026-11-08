"""Common project discovery and file boundaries, without business parsing."""
from pathlib import Path
import execution_records as recordio
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-workspace-browser/scripts'))
from workspace_project_index import ordered_projects, project_directories
from project_resources import resolve_file
from project_paths import scope_root, SHARED_SCOPE


ARCHIVE_MARKER = '.archived'


class ProjectFiles:
    nested = False

    def __init__(self, root, *, nested=False):
        self.root = root.resolve()
        self.nested = nested

    def project(self, name: str, *, writable: bool = False) -> Path:
        if self.nested:
            if '::' not in name:
                raise FileNotFoundError('须指定所属项目')
            path = scope_root(self.root.parent, name)
            if not path.is_dir():
                raise FileNotFoundError('项目不存在')
            if writable and (path / ARCHIVE_MARKER).is_file():
                raise PermissionError('项目已迁移或归档，仅保留只读历史入口')
            return path
        path = scope_root(self.root.parent, name) if name == SHARED_SCOPE else (self.root / name).resolve()
        if (name != SHARED_SCOPE and path.parent != self.root) or not path.is_dir() or name.startswith('.'):
            raise FileNotFoundError('项目不存在')
        if writable and (path / ARCHIVE_MARKER).is_file():
            raise PermissionError('项目已迁移或归档，仅保留只读历史入口')
        return path


    def discover(self):
        if self.nested:
            return [{'id': f'{folder.name}::{item["id"]}', 'name': f'{folder.name} · {item["name"]}'}
                    for folder in sorted(self.root.parent.iterdir())
                    if not folder.name.startswith('.') and not folder.is_symlink() and (folder / 'projects').is_dir()
                    and (folder / 'README.md').is_file() and (folder / '综合资料').is_dir()
                    for item in ProjectFiles(folder / 'projects').discover()]
        return ordered_projects(self.root, project_directories(self.root))


    def file(self, name, relative, revision=None):
        root = self.project(name)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or any(part.startswith('.') for part in Path(relative).parts):
            raise FileNotFoundError('文件不存在或不在项目内')
        path = resolve_file(root, path)
        if not path.is_file() and (not (path.parent / recordio.ARCHIVE).resolve().is_relative_to(root) or not recordio.exists(path)):
            raise FileNotFoundError('文件不存在或不在项目内')
        return path
