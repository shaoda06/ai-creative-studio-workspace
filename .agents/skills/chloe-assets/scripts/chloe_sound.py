"""Register an audio original in a Chloe project's shared sound library."""
import argparse
import filecmp
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from chloe_resources import common_owner, exact_reference, import_media, resources
from chloe_init import initialize_asset
from chloe_documents import SOUND_TYPES, media_reference, read_document, records, sound_type, template


def record_sound(project, source, identity, title, category, source_note, tags='无', description='无'):
    root, owner = common_owner(project)
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() not in resources.KINDS['音频']:
        raise ValueError('声音收录脚本接收音频原件')
    if not re.fullmatch(r'A[0-9]{3,}', identity) or int(identity[1:]) < 1 or category not in SOUND_TYPES:
        raise ValueError('核对声音编号及分类')
    if title != title.strip() or not title or any(char in title for char in '/\\<>:"?*'):
        raise ValueError('声音名称须能用作目录名')
    if any(not field.strip() or any(char in field for char in '|\n\r\0')
           for field in (title, source_note, tags, description)):
        raise ValueError('名称、来源说明、标签和声音说明须为非空单行文字')

    folder = owner / '共用素材' / '声音'
    path = folder / f'{identity}-{title}' / '声音说明.md'
    if any(entry != path.parent for entry in folder.glob(f'{identity}-*')):
        raise ValueError('声音编号已用于其他名称')
    schema = template('chloe-assets', '声音说明模板.md')
    values = {'identity': identity, 'title': title}
    if path.is_file():
        document = read_document(root, path, schema, values)
        originals = [row for row in records(document, '参考版本') if row['用途'] == '声音原始参考']
        if originals:
            for row in originals:
                ref = media_reference(root, path, row['资源引用'])
                if sound_type(document) == category and filecmp.cmp(source, root / ref['file'], shallow=False):
                    return exact_reference(root, ref['resource_id'], ref['version'])
            raise ValueError('同编号已有其他原始参考，请按声音说明记录新增来源')
        if sound_type(document) != category:
            raise ValueError('同编号的声音分类与录入参数不同')

    ref = None
    for entry in resources.read_index(owner)['files'].values():
        if entry['kind'] != '音频':
            continue
        shared = owner / entry['file']
        if shared.is_file() and filecmp.cmp(source, shared, shallow=False):
            ref = exact_reference(root, entry['resource_id'], entry['version'])
            break
    if ref is None:
        registered = import_media(root, source, f'声音/{identity}/原件')
        ref = exact_reference(root, registered['resource_id'], registered['version'])

    initialize_asset(root, '声音', identity, title)
    relative = Path(os.path.relpath(root / ref['file'], path.parent)).as_posix()
    link = f'[共用:{ref["resource_id"]}@{ref["version"]}](<{relative}>)'
    body = path.read_text('utf-8')
    body = body.replace('| 来源说明 | 待核实 |', f'| 来源说明 | {source_note} |', 1)
    body = body.replace(f'| 声音分类 | {SOUND_TYPES[-1]} |', f'| 声音分类 | {category} |', 1)
    body = body.replace('| 标签 | 无 |', f'| 标签 | {tags} |', 1)
    body = body.replace('| 声音说明 | 无 |', f'| 声音说明 | {description} |', 1)
    first, adoption = body.split('\n## 当前采用', 1)
    body = first.rstrip() + f'\n| 声音原始参考 | {link} | 见来源说明 | 不适用 |\n\n## 当前采用' + adoption
    read_document(root, path, schema, values, body=body)
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        pending = Path(stream.name)
        stream.write(body)
    try:
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)
    return ref


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--type', choices=SOUND_TYPES, required=True)
    parser.add_argument('--source-note', required=True)
    parser.add_argument('--tags', default='无')
    parser.add_argument('--description', default='无')
    args = parser.parse_args()
    print(json.dumps(record_sound(args.project_root, args.file, args.id, args.title, args.type,
                                  args.source_note, args.tags, args.description), ensure_ascii=True, indent=2))
