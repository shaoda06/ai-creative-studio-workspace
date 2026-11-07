"""Initialize Iris's local workspace without creating orders or replacing records."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-workspace-browser/scripts'))
from workspace_setup import write_template, register_workspace


def initialize_workspace(value):
    root = Path(value).expanduser().resolve()
    if root.name != 'Iris Workspace':
        raise ValueError('请选择名为 Iris Workspace 的独立目录')
    write_template(root / 'README.md', 'iris-commercial-brief', '工作区README模板.md')
    write_template(root / 'projects/README.md', 'iris-commercial-brief', '项目目录说明模板.md')
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--register', action='store_true', help='登记到统一浏览服务；不启动服务')
    args = parser.parse_args()
    root = initialize_workspace(args.workspace)
    if args.register:
        register_workspace(root, identity='commercial', name='Iris商业视频', view='iris-commercial',
                           production_adapter='iris-commercial-production', runtime_id='iris')
    print(json.dumps({'path': str(root)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
