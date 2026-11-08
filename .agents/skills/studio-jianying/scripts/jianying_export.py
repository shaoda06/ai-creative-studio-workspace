"""Export explicitly ordered media as a Jianying draft archive."""
import argparse
import json
from pathlib import Path, PurePosixPath
from zipfile import ZIP_STORED, ZipFile

from jianying_draft import draft_files
from jianying_package import encode_jypack


def export_archive(files, path, name, timeline_members=None, archive_format='zip'):
    members = [member for _, member in files]
    if len(set(members)) != len(members):
        raise ValueError('归档成员名重复')
    if not files or timeline_members is not None and not set(members) & timeline_members:
        raise ValueError('时间线至少需要一个视频')
    for member in members:
        value = PurePosixPath(member)
        if value.is_absolute() or '..' in value.parts or '\\' in member:
            raise ValueError('归档成员必须为包内相对路径')
        if member in ('draft_content.json', 'draft_info.json', 'draft_meta_info.json'):
            raise ValueError('媒体名与草稿文件冲突')
    with ZipFile(path, 'w', compression=ZIP_STORED) as bundle:
        for source, member in files:
            bundle.write(source, member)
        for member, content in draft_files(files, name, timeline_members).items():
            bundle.writestr(member, content.encode('utf-8'))
    if archive_format == 'jypack':
        encode_jypack(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--format', choices=('zip', 'jypack'), default='zip')
    args = parser.parse_args()
    spec = json.loads(args.manifest.read_text(encoding='utf-8'))
    files = [(Path(item['file']), item['member']) for item in spec['media']]
    timeline = {item['member'] for item in spec['media'] if item.get('timeline', True)}
    # Claim only this output; a failed export must not remove an existing file.
    with args.output.open('xb'):
        pass
    try:
        export_archive(files, args.output, spec['name'], timeline, args.format)
    except BaseException:
        args.output.unlink()
        raise
    print(args.output.resolve())


if __name__ == '__main__':
    main()
