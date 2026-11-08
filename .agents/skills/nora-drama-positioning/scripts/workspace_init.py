"""Initialize Nora's local workspace without creating projects or replacing records."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-workspace-browser/scripts'))
from workspace_setup import write_template, register_workspace


def initialize_workspace(value):
    root = Path(value).expanduser().resolve()
    if root.name != 'Nora Workspace':
        raise ValueError('请选择名为 Nora Workspace 的独立目录')
    write_template(root / 'README.md', 'nora-drama-positioning', '工作区README模板.md')
    write_template(root / 'projects/README.md', 'nora-drama-positioning', '项目目录说明模板.md')
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--register', action='store_true', help='核对统一浏览服务默认空间的位置；不启动服务')
    args = parser.parse_args()
    root = initialize_workspace(args.workspace)
    if args.register:
        register_workspace(root, identity='nora', name='Nora视频创作', view='serial-drama')
    print(json.dumps({'path': str(root)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
