"""Common project discovery and file boundaries, without business parsing."""
from pathlib import Path
import execution_records as recordio
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/nora-workspace-browser/scripts'))
from workspace_project_index import read_index


ARCHIVE_MARKER = '.archived'


class ProjectFiles:
    def __init__(self, root):
        self.root = root.resolve()

    def project(self, name: str, *, writable: bool = False) -> Path:
        path = (self.root / name).resolve()
        if path.parent != self.root or not path.is_dir() or name.startswith('.'):
            raise FileNotFoundError('项目不存在')
        if writable and (path / ARCHIVE_MARKER).is_file():
            raise PermissionError('项目已迁移或归档，仅保留只读历史入口')
        return path


    def discover(self):
        projects = {p.name for p in self.root.iterdir()
                    if p.is_dir() and not p.name.startswith('.') and p.resolve().parent == self.root
                    and not (p / ARCHIVE_MARKER).is_file()}
        _, indexed = read_index(self.root)
        names = dict.fromkeys([*indexed, *sorted(projects)])
        return [{'id': name, 'name': name} for name in names if name in projects]


    def file(self, name, relative, revision=None):
        root = self.project(name)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or any(part.startswith('.') for part in Path(relative).parts):
            raise FileNotFoundError('文件不存在或不在项目内')
        if not path.is_file() and (not (path.parent / recordio.ARCHIVE).resolve().is_relative_to(root) or not recordio.exists(path)):
            raise FileNotFoundError('文件不存在或不在项目内')
        return path
