"""Shared locations for bundled workflows; project task copies keep their own paths."""
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2] / 'studio-h3'
WORKFLOW_GROUPS = (
    ('Qwen-image-2-1', 'formal'),
    ('Minimax-H3', 'formal'),
    ('后处理综合', 'formal'),
    ('非正式工作流', 'backup'),
)


def workflow_root(skill=SKILL_ROOT):
    return Path(skill) / 'references/workflows'


def workflow_locations(root):
    """Stable download categories can refer to tool-owned physical folders."""
    root = Path(root)
    if root.resolve() == workflow_root().resolve():
        skills = SKILL_ROOT.parent
        return [('Qwen-image-2-1', skills / 'studio-qwen-image/references/workflows', 'formal'),
                ('Minimax-H3', root / 'Minimax-H3', 'formal'),
                ('后处理综合', skills / 'studio-video-processing/references/workflows', 'formal'),
                ('后处理综合', skills / 'studio-image-processing/references/workflows', 'formal'),
                ('非正式工作流', root / '非正式工作流', 'backup')]
    return [(name, root / name, group) for name, group in WORKFLOW_GROUPS]


def workflow_directories(root):
    return [(directory, group) for _, directory, group in workflow_locations(root)]


def workflow_download(root, filename):
    """Resolve only exact registered category/file keys, never user path traversal."""
    if not filename.endswith(('.workflow.json', '.api.json')):
        return None
    matches = []
    for category, directory, _ in workflow_locations(root):
        if filename != category + '/' + Path(filename).name:
            continue
        path = (directory / Path(filename).name).resolve()
        # Tool folders may be outside the legacy root; each retains its own boundary.
        scope = Path(root) if directory.is_relative_to(Path(root)) else directory.parent.parent
        if path.is_relative_to(scope.resolve()) and path.parent == directory.resolve() and path.is_file():
            matches.append(path)
    return matches[0] if len(matches) == 1 else None


def workflow_file(name, kind='workflow', *, root=None):
    """Locate one formal baseline by name, without coupling callers to its category."""
    root = workflow_root() if root is None else Path(root)
    matches = [directory / f'{name}.{kind}.json'
               for directory, group in workflow_directories(root)
               if group == 'formal' and (directory / f'{name}.{kind}.json').is_file()]
    if len(matches) != 1:
        raise ValueError(f'正式工作流应有唯一文件，实际找到{len(matches)}份：{name}.{kind}.json')
    return matches[0]
