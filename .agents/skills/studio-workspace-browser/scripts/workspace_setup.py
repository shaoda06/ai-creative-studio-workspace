"""Shared file creation and space registration for business-owned initializers."""
import json
import os
from pathlib import Path
import tempfile

SKILLS = Path(__file__).resolve().parents[2]


def write_template(path, skill, template):
    path = Path(path)
    body = (SKILLS / skill / 'templates' / template).read_text('utf-8')
    body = body.replace('{{skills}}', Path(os.path.relpath(SKILLS, path.parent)).as_posix())
    body = body.replace('{{studio}}', Path(os.path.relpath(SKILLS.parents[1], path.parent)).as_posix())
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(body)
    except FileExistsError:
        if not path.is_file():
            raise


def register_workspace(root, *, identity, name, view, production_adapter=None, runtime_id=None, project_layout='flat'):
    root = Path(root).resolve()
    if (project_layout not in ('flat', 'nested') or root.parent.name != 'workspaces'
            or not (root / ('README.md' if project_layout == 'nested' else 'projects')).exists()):
        raise ValueError('登记须使用总工作区 workspaces 下已初始化的资料区')
    if identity == 'nora':
        if root.name != 'Nora Workspace':
            raise ValueError('默认 Nora 空间须使用 Nora Workspace 目录')
        return  # The common service discovers this fixed directory directly.
    runtime = root.parent.parent / '工作区浏览服务/runtime'
    path = runtime / 'workspaces.json'
    entries = json.loads(path.read_text('utf-8')) if path.exists() else []
    entry = {'id': identity, 'name': name, 'path': str(root), 'view': view,
             'production_adapter': production_adapter, 'runtime_id': runtime_id or identity}
    if project_layout != 'flat':
        entry['project_layout'] = project_layout
    for current in entries:
        if current['id'] == identity or Path(current['path']).resolve() == root:
            if (current['id'] != identity or Path(current['path']).resolve() != root
                    or current.get('view', 'files') != view
                    or current.get('production_adapter') != production_adapter
                    or current.get('project_layout', 'flat') != project_layout
                    or current.get('runtime_id', identity) != entry['runtime_id']):
                raise ValueError('已有空间登记与本次初始化不一致，请按运行资料规范处理：' + identity)
            return  # Keep the display name, archive mapping and other local fields.
        if current.get('runtime_id', current['id']) == entry['runtime_id']:
            raise ValueError('运行资料目录已由其他空间使用：' + entry['runtime_id'])
    entries.append(entry)
    runtime.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=runtime, delete=False) as stream:
        json.dump(entries, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    os.replace(stream.name, path)
