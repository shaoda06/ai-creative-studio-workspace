"""Use Chloe shared media by exact version; never copy it into video projects."""
import argparse
import json
from pathlib import Path
import sys

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / 'studio-workspace-browser/scripts'))
sys.path.insert(0, str(SKILLS / 'chloe-positioning/scripts'))
import project_resources as resources
from chloe_init import project_path


def common_owner(workspace):
    root = project_path(workspace)
    owner = root / '综合资料'
    if not resources.enabled(owner):
        raise ValueError('共用资源区未初始化')
    return root, owner


def video_root(root, project):
    path = (root / 'projects' / project).resolve()
    if Path(project).name != project or path.parent != (root / 'projects').resolve():
        raise ValueError('视频项目必须在当前具名项目的 projects 内')
    if not resources.enabled(path) or not (path / '资源/共用引用.json').is_file():
        raise ValueError('视频项目未通过 Chloe 初始化')
    return path


def exact_reference(workspace, resource_id, version):
    root, owner = common_owner(workspace)
    path = resources.version_file(owner, resource_id, version)
    if not path.is_file() or not (path.parent / '版本信息.json').is_file():
        raise ValueError('资源尚未完成保存，不能绑定输入')
    return {'owner': '综合资料', 'resource_id': resource_id, 'version': version,
            'file': path.relative_to(root).as_posix()}


def import_media(workspace, source, key, *, project=None, resource_id=None,
                 origin='user_upload', record=None, parent=None):
    if not key.strip():
        raise ValueError('导入键不能为空；同一输出重试须沿用稳定身份')
    root, common = common_owner(workspace)
    owner = video_root(root, project) if project else common
    source = Path(source).resolve()
    if source.is_relative_to(root.parent):
        raise ValueError('工作区内已有媒体请引用原版本，不重新导入；实际新处理结果先保存为独立输出')
    if origin in ('generated', 'process') and record is None:
        raise ValueError('生成或处理结果须提供实际执行记录 --record')
    if record is not None:
        actual = resources.local(owner, record)
        if not actual.exists():
            raise FileNotFoundError(actual)
        record = actual.relative_to(owner).as_posix()
    facts = resources.facts(source)
    ref = resources.register(owner, source, resource_id=resource_id, key=key,
                             origin=origin, producer=record, parent=parent, info=facts)
    return {'owner': owner.relative_to(root).as_posix(), **ref,
            'absolute_file': str(resources.local(owner, ref['file']))}


def bind_reference(workspace, project, key, resource_id, version):
    if not key.strip():
        raise ValueError('引用键不能为空；使用任务/镜头/轮次/用途等实际身份')
    root, _ = common_owner(workspace)
    target = video_root(root, project)
    ref = exact_reference(workspace, resource_id, version)
    index = target / '资源/共用引用.json'
    with resources.index_lock(target):
        data = json.loads(index.read_text('utf-8'))
        previous = data['references'].get(key)
        if previous is not None and previous != ref:
            raise ValueError('已有引用键绑定其他版本；新任务或新轮次使用新键，不改写旧引用')
        if previous is None:
            data['references'][key] = ref
            resources.write_json(index, data)
    return ref


def resolve_reference(workspace, project, key):
    root, _ = common_owner(workspace)
    target = video_root(root, project)
    ref = json.loads((target / '资源/共用引用.json').read_text('utf-8'))['references'][key]
    expected = exact_reference(workspace, ref['resource_id'], ref['version'])
    if ref != expected:
        raise ValueError('引用记录与所属资源不符')
    return root / expected['file']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True, help='明确选定的 Chloe 具名项目根目录；共用资源仅属此项目')
    commands = parser.add_subparsers(dest='action', required=True)
    add = commands.add_parser('import', help='导入外部原件或新生成结果；默认存账号共用区')
    add.add_argument('--file', type=Path, required=True)
    add.add_argument('--key', required=True, help='本次导入或任务输出的稳定身份；重试沿用')
    add.add_argument('--project', help='仅本条视频的新产出才指定视频目录名；共用素材不填')
    add.add_argument('--resource-id', help='同一制作目标的修订填写原编号；独立产出不填')
    add.add_argument('--origin', choices=['user_upload', 'import', 'generated', 'process'], default='user_upload')
    add.add_argument('--record', help='所属资源范围内的实际执行记录相对路径，生成和处理时必填')
    add.add_argument('--parent', help='同一资源归属内的准确来源版本文件相对路径')
    bind = commands.add_parser('bind', help='为视频登记不可静默改版的共用引用，不复制媒体')
    bind.add_argument('--project', required=True)
    bind.add_argument('--key', required=True)
    bind.add_argument('--resource-id', required=True)
    bind.add_argument('--version', required=True, help='准确版本，例如 V001；不接受 latest')
    resolve = commands.add_parser('resolve', help='只读解析实际媒体路径；不改变浏览服务访问边界')
    resolve.add_argument('--project', required=True)
    resolve.add_argument('--key', required=True)
    listing = commands.add_parser('list', help='列出已保存版本，不推断采用')
    listing.add_argument('--project')
    args = parser.parse_args()
    if args.action == 'import':
        result = import_media(args.project_root, args.file, args.key, project=args.project,
                              resource_id=args.resource_id, origin=args.origin, record=args.record, parent=args.parent)
    elif args.action == 'bind':
        result = bind_reference(args.project_root, args.project, args.key, args.resource_id, args.version)
    elif args.action == 'resolve':
        result = {'file': str(resolve_reference(args.project_root, args.project, args.key))}
    else:
        root, owner = common_owner(args.project_root)
        result = resources.catalog(video_root(root, args.project) if args.project else owner)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
