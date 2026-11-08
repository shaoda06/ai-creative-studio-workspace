"""Locate registered task connections in the common service's runtime only."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-comfyui/scripts'))
from execution_records import strict_json


def read_connection(workspace):
    workspace = Path(workspace).resolve()
    runtime = next((folder / '工作区浏览服务/runtime' for folder in (workspace, *workspace.parents)
                    if (folder / '工作区浏览服务/runtime/workspaces/nora/task-service.json').is_file()), None)
    if runtime is None:
        raise FileNotFoundError('总工作区没有任务服务连接配置，请按浏览工具运行说明启动统一后台')
    primary = strict_json((runtime / 'workspaces/nora/task-service.json').read_bytes())
    if workspace in (runtime.parent.parent, Path(primary['workspace']).resolve()):
        return primary
    registered = strict_json((runtime / 'workspaces.json').read_bytes())
    for item in registered:
        root = Path(item['path']).resolve()
        if workspace == root or (item.get('project_layout') == 'nested' and workspace.parent == root
                                 and (workspace / 'README.md').is_file() and (workspace / 'projects').is_dir()):
            config = runtime / 'workspaces' / item.get('runtime_id', item['id']) / 'task-service.json'
            return strict_json(config.read_bytes())
    raise ValueError('资料工作区未登记到统一后台：' + str(workspace))
