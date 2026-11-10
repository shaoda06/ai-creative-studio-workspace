"""Project-relative file identities; legacy evidence is read without rewriting it."""
from pathlib import Path, PureWindowsPath
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-workspace-browser/scripts'))


SHARED_SCOPE = '@shared'
SHARED_DIRECTORY = '综合资料'


class MissingTaskContext(ValueError):
    """A task's named project directory is no longer present."""


def scope_name(root, workspace=None):
    root = Path(root)
    name = SHARED_SCOPE if root.name == SHARED_DIRECTORY and root.parent.name != 'projects' else root.name
    if workspace is not None:
        owner = scope_workspace(root)
        workspace = Path(workspace).resolve()
        if owner != workspace:
            if owner.parent != workspace or '::' in owner.name:
                raise ValueError('任务不属于该工作区的具名项目')
            return owner.name + '::' + name
    return name


def scope_workspace(root):
    root = Path(root).resolve()
    if root.parent.name == 'projects':
        return root.parent.parent
    if root.name == SHARED_DIRECTORY:
        return root.parent
    raise ValueError('任务目录必须是工作区projects下的项目或综合资料')


def scope_root(workspace, value, *, recorded=False):
    workspace = Path(workspace).resolve()
    spelling = str(value)
    if '::' in spelling:
        context, name = spelling.split('::', 1)
        owner = (workspace / context).resolve()
        if not context or context.startswith('.') or '/' in context or '\\' in context or owner.parent != workspace:
            raise ValueError('所属项目不存在或越界')
        if owner == workspace / context and not owner.exists() and not owner.is_symlink():
            raise MissingTaskContext('所属项目不存在或越界')
        if not (owner / 'README.md').is_file() or not (owner / 'projects').is_dir() or not (owner / SHARED_DIRECTORY).is_dir():
            raise ValueError('所属项目不存在或越界')
        return scope_root(owner, name, recorded=recorded)
    if Path(spelling).is_absolute():
        absolute = Path(spelling).resolve()
        owner = scope_workspace(absolute)
        if owner.parent == workspace and (owner / 'README.md').is_file():
            return scope_root(owner, absolute, recorded=False)
    if not recorded and not Path(spelling).is_absolute() and PureWindowsPath(spelling).name != spelling:
        raise ValueError('项目必须是当前工作区内的项目名或绝对路径')
    if spelling == SHARED_SCOPE:
        path = workspace / SHARED_DIRECTORY
        if path.resolve() != path:
            raise ValueError('共用任务目录不能重定向到其他目录')
    elif recorded or not Path(spelling).is_absolute():
        path = workspace / 'projects' / PureWindowsPath(spelling).name
    else:
        path = Path(spelling)
    path = path.resolve()
    if path.parent == workspace / 'projects' and path.name == SHARED_SCOPE:
        raise ValueError('共用任务标识不能用作项目目录名')
    if path != workspace / SHARED_DIRECTORY and path.parent != workspace / 'projects':
        raise ValueError('任务必须属于当前工作区projects下的项目或综合资料')
    return path


def input_file(project, value, *, recorded=False):
    """Read an exact registered shared resource, or a file in the owning project."""
    project = Path(project).resolve()
    spelling = str(value)
    if not spelling.startswith('@shared/') and (not Path(spelling).is_absolute() or Path(spelling).resolve().is_relative_to(project)):
        return project_file(project, value, recorded=recorded)
    shared = scope_workspace(project) / SHARED_DIRECTORY
    candidate = shared / spelling[len('@shared/'):] if spelling.startswith('@shared/') else Path(spelling)
    if candidate.is_absolute() and candidate.resolve().is_relative_to(shared / '资源') and shared != project:
        import project_resources as resources
        path = candidate.resolve()
        reference = resources.reference(shared, path)
        if reference is None or path != resources.version_file(shared, reference['resource_id'], reference['version']):
            raise ValueError('共用输入必须引用已登记的准确资源版本')
        if not path.is_file() or not (path.parent / '版本信息.json').is_file():
            raise ValueError('共用输入尚未完整保存')
        return path
    return _project_file(project, value, recorded=recorded)


def input_key(project, value):
    project = Path(project).resolve()
    path = input_file(project, value, recorded=True)
    if path.is_relative_to(project):
        return path.relative_to(project).as_posix()
    return '@shared/' + path.relative_to(scope_workspace(project) / SHARED_DIRECTORY).as_posix()


def input_reference(project, value):
    import project_resources as resources
    project = Path(project).resolve()
    path = input_file(project, value)
    owner = project if path.is_relative_to(project) else scope_workspace(project) / SHARED_DIRECTORY
    return resources.reference(owner, path)


def project_file(project, value, *, recorded=False):
    project = Path(project).resolve()
    return _project_file(project, value, recorded=recorded)


def _project_file(project, value, *, recorded=False):
    spelling = str(value).replace('\\', '/')
    if spelling.startswith('@shared/'):
        raise ValueError('输出或项目文件路径越出项目；共用资源仅可作为输入')
    path = Path(spelling)
    windows = PureWindowsPath(spelling)
    absolute = path.is_absolute() or windows.is_absolute()
    resolved = path.resolve() if absolute else None
    if recorded and absolute and not resolved.is_relative_to(project):
        marker = '/projects/' + project.name + '/'
        position = spelling.casefold().find(marker.casefold())
        if position >= 0:
            spelling = spelling[position + len(marker):]
            path = Path(spelling)
            absolute = False
            resolved = None
    path = resolved if resolved is not None else (path if absolute else project / path).resolve()
    if not path.is_relative_to(project):
        raise ValueError('文件路径越出项目：' + str(value))
    relative = path.relative_to(project)
    if not recorded and relative.parts and relative.parts[0].casefold() in ('projects', project.name.casefold()):
        raise ValueError('文件路径必须相对项目根目录，不得重复 projects/项目名 或项目名：' + str(value))
    from project_resources import resolve_file
    return resolve_file(project, path)


def relative_file(project, value, *, recorded=False):
    project = Path(project).resolve()
    return _project_file(project, value, recorded=recorded).relative_to(project).as_posix()


LOCAL_FIELDS = {'path', 'file', 'record_dir', 'receipt', 'history', 'evidence', 'local_file',
                'approval_record', 'upload_response', 'previous_upload_response', 'reuse_response',
                'local_execution_dir', 'common_evidence_directory', 'expected_local_candidate',
                'mapping', 'mapping_file', 'selected_path', 'original_file', 'source_file', 'source_path', 'saved_outputs'}


class RecordPaths:
    """Project-scoped spelling conversion for records, never a file-access authorization."""

    def __init__(self, project):
        self.project = Path(project).resolve()
        self._files = {}

    @classmethod
    def from_resolved(cls, project, files):
        """Seed only from canonical input paths already checked at the task boundary."""
        self = cls.__new__(cls)
        self.project = Path(project)
        self._files = {}
        if not self.project.is_absolute() or '..' in self.project.parts:
            raise ValueError('记录转换需要已解析的项目根目录')
        for value in files:
            path = Path(value)
            if not path.is_absolute() or '..' in path.parts or (not path.is_relative_to(self.project) and input_file(self.project, path, recorded=True) != path.resolve()):
                raise ValueError('文件路径越出项目：' + str(value))
            self._remember(path)
        return self

    def _remember(self, path):
        self._files[path.as_posix()] = path
        self._files[self._key(path)] = path

    def _key(self, path):
        # Only called with a path already checked at the IO boundary.
        if path.is_relative_to(self.project):
            return path.relative_to(self.project).as_posix()
        return '@shared/' + path.relative_to(self.project.parent.parent / SHARED_DIRECTORY).as_posix()

    def file(self, value):
        spelling = str(value).replace('\\', '/')
        path = self._files.get(spelling)
        if path is None:
            path = input_file(self.project, spelling, recorded=True)
            self._remember(path)
            self._files[spelling] = path
        return path

    def relative_file(self, value):
        return self._key(self.file(value))

    def convert(self, document, *, relative=False, field=''):
        if field == 'error_details':
            return document  # Opaque remote/client errors, never project file identities.
        if isinstance(document, dict):
            return {key: self.convert(value, relative=relative, field=key) for key, value in document.items()}
        if isinstance(document, list):
            return [self.convert(value, relative=relative, field=field) for value in document]
        if isinstance(document, str) and document and field in LOCAL_FIELDS:
            spelling = document.replace('\\', '/')
            if spelling not in self._files and (Path(spelling).is_absolute() or PureWindowsPath(spelling).is_absolute()) and (
                    not spelling.casefold().startswith(self.project.as_posix().casefold() + '/')
                    and ('/projects/' + self.project.name + '/').casefold() not in spelling.casefold()):
                return document  # Preserve remote evidence and external tool paths.
            path = self.file(spelling)
            return self._key(path) if relative else str(path)
        return document


def recorded_paths(project, document, *, relative=False, field=''):
    """Translate local file fields only; remote paths and historical prose stay intact."""
    if field == 'error_details':
        return document
    return RecordPaths(project).convert(document, relative=relative, field=field)


class PreparationPaths(RecordPaths):
    """One preparation phase's addresses; IO always rechecks the actual target."""

    def io_file(self, value):
        spelling = str(value).replace('\\', '/')
        previous = self._files.get(spelling)
        actual = input_file(self.project, spelling, recorded=True)
        if previous is not None and previous != actual:
            raise ValueError('准备资料路径发生变化：' + str(value))
        self._remember(actual)
        self._files[spelling] = actual
        return actual
