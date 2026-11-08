"""Create Chloe's fixed workspace, asset and video skeletons without replacing content."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / 'studio-workspace-browser/scripts'))
import project_resources as resources
from workspace_setup import register_workspace

ASSETS = {
    '商品': ('商品资料', 'G', '商品说明.md'),
    '模特': ('共用素材/AI模特', 'M', '模特说明.md'),
    '服装': ('共用素材/服装', 'O', '服装说明.md'),
    '造型': ('共用素材/造型', 'L', '造型说明.md'),
    '场景': ('共用素材/场景', 'S', '场景说明.md'),
    '声音': ('共用素材/声音', 'A', '声音说明.md'),
}


def workspace_path(value):
    path = Path(value).resolve()
    if path.name != 'Chloe Workspace':
        raise ValueError('请选择名为 Chloe Workspace 的独立目录')
    return path


def project_name(name):
    if (not isinstance(name, str) or not name.strip() or name != name.strip()
            or name in {'待命名', '未命名', '待确定', '没想好', '项目名称', '项目名', '账号名称',
                        'TODO', 'TBD', 'Untitled', 'projects', '综合资料'}
            or name.startswith('.') or any(c in name for c in '/\\\n\r\0|<>:"?*')):
        raise ValueError('必须使用用户明确提供的项目名称、代号或社交媒体账号名称，不能使用占位名称或路径字符')
    return name


def project_path(value):
    path = Path(value).resolve()
    workspace_path(path.parent)
    project_name(path.name)
    return path


def write_template(path, skill, template, **fields):
    body = (SKILLS / skill / 'templates' / template).read_text('utf-8')
    fields['skills'] = Path(os.path.relpath(SKILLS, path.parent)).as_posix()
    fields['studio'] = Path(os.path.relpath(SKILLS.parents[1], path.parent)).as_posix()
    for key, value in fields.items():
        body = body.replace('{{' + key + '}}', str(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(body)
    except FileExistsError:
        pass  # Reinitialization only fills missing skeleton files.


def resource_area(owner):
    for kind in resources.KINDS:
        (owner / '资源' / kind).mkdir(parents=True, exist_ok=True)
    resources.initialize(owner, managed=True)


def initialize_workspace(value):
    root = workspace_path(value)
    write_template(root / 'README.md', 'chloe-positioning', '工作区README模板.md')
    return root


def initialize_project(value, name):
    root = workspace_path(value) / project_name(name)
    if root.resolve().parent != workspace_path(value):
        raise ValueError('项目目录越出工作区')
    if not (root.parent / 'README.md').is_file():
        raise ValueError('请先初始化工作区')
    for directory in ('projects', '综合资料', *('综合资料/' + item[0] for item in ASSETS.values())):
        (root / directory).mkdir(parents=True, exist_ok=True)
    write_template(root / 'README.md', 'chloe-positioning', '项目README模板.md', title=name)
    write_template(root / 'projects/README.md', 'chloe-creative', '视频索引说明模板.md')
    for name in ('账号定位', '选品记录', '运营复盘'):
        write_template(root / f'综合资料/{name}.md', 'chloe-positioning', name + '模板.md')
    resource_area(root / '综合资料')
    return root


def named_folder(parent, identity, title, prefix):
    if not re.fullmatch(prefix + r'[0-9]{3,}', identity) or int(identity[len(prefix):]) < 1:
        raise ValueError('编号应为 ' + prefix + '001 等正整数编号')
    if not title.strip() or title != title.strip() or any(c in title for c in '/\\\n\r\0|'):
        raise ValueError('名称不能为空、带首尾空白、路径分隔符或表格竖线')
    path = parent / (identity + '-' + title)
    if path.resolve().parent != parent.resolve():
        raise ValueError('目录越出所属资料范围')
    others = [p for p in parent.glob(identity + '-*') if p != path]
    if others:
        raise ValueError('编号已用于另一名称：' + others[0].name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def initialize_video(value, identity, title):
    root = project_path(value)
    owner = root / '综合资料'
    if not resources.enabled(owner) or not (root / 'projects').is_dir():
        raise ValueError('请先初始化具名项目')
    with resources.index_lock(owner):
        project = named_folder(root / 'projects', identity, title, 'V')
        for directory in ('资源/图片', '资源/视频', '资源/音频', '剪辑交接', '成片', '执行记录', '历史版本'):
            (project / directory).mkdir(parents=True, exist_ok=True)
        for filename, template in [('README.md', '视频README模板.md'), ('脚本.md', '脚本模板.md'),
                                   ('制作记录.md', '制作记录模板.md')]:
            write_template(project / filename, 'chloe-creative', template, identity=identity, title=title)
        for name in ('制作轮次', '视频修改意见'):
            write_template(project / (name+'.json'), 'chloe-production', name+'模板.json')
        resource_area(project)
        references = project / '资源/共用引用.json'
        if not references.exists():
            resources.write_json(references, {'format': 1, 'references': {}})
    return project


def initialize_asset(value, kind, identity, title):
    root = project_path(value)
    owner = root / '综合资料'
    if not resources.enabled(owner):
        raise ValueError('请先初始化具名项目')
    directory, prefix, filename = ASSETS[kind]
    with resources.index_lock(owner):
        asset = named_folder(owner / directory, identity, title, prefix)
        skill = 'chloe-selection' if kind == '商品' else 'chloe-assets'
        template = filename.replace('.md', '模板.md')
        write_template(asset / filename, skill, template, identity=identity, title=title, kind=kind)
    return asset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True, help='真实或隔离的 Chloe Workspace 目录')
    commands = parser.add_subparsers(dest='action', required=True)
    workspace = commands.add_parser('workspace', help='仅建立工作区入口；不代建项目')
    workspace.add_argument('--register', action='store_true', help='登记到统一浏览服务；不启动服务')
    project = commands.add_parser('project', help='用用户明确提供的名称建立独立项目；没有名称时禁止初始化')
    project.add_argument('--name', required=True, help='用户确认的项目名称、代号或社交媒体账号名称；无默认值')
    video = commands.add_parser('video', help='建立一条视频；不生成媒体或新建账号配置')
    video.add_argument('--project-name', required=True, help='所属已建档项目的准确目录名')
    video.add_argument('--id', required=True, help='已确定的视频编号，例如 V001')
    video.add_argument('--name', required=True, help='商品与视频主题组成的名称')
    asset = commands.add_parser('asset', help='建立商品或共用资产说明；不复制媒体')
    asset.add_argument('--project-name', required=True, help='所属已建档项目的准确目录名')
    asset.add_argument('--kind', choices=ASSETS, required=True)
    asset.add_argument('--id', required=True, help='G/M/O/L/S/A 加正整数编号，例如 M001')
    asset.add_argument('--name', required=True)
    args = parser.parse_args()
    if args.action == 'workspace':
        result = initialize_workspace(args.workspace)
        if args.register:
            register_workspace(result, identity='chloe', name='Chloe视频带货', view='chloe-commerce',
                               production_adapter='chloe-production', project_layout='nested')
    elif args.action == 'project':
        result = initialize_project(args.workspace, args.name)
    elif args.action == 'video':
        result = initialize_video(workspace_path(args.workspace) / project_name(args.project_name), args.id, args.name)
    else:
        result = initialize_asset(workspace_path(args.workspace) / project_name(args.project_name), args.kind, args.id, args.name)
    print(json.dumps({'path': str(result)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
