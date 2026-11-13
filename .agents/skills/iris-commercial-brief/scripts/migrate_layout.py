"""Migrate a multi-work Iris project to the numbered layout. Default: inventory only."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, unquote, urlsplit
from zipfile import ZipFile, ZIP_DEFLATED


ROOTS = {'资源': '02-资源', '作品': '03-作品', '08-完单复盘': '04-完单复盘', '归档': '98-归档'}
CURRENT_JSON = {'制作轮次.json', '历史执行入口.json', '视频修改意见.json', '项目概况展示.json'}
HISTORY = {'归档', '历史版本', '执行记录', '执行附件'}


def translate(key, moves):
    for old, new in moves.items():
        if key == old or key.startswith(old + '/'):
            return new + key[len(old):]
    return key


def paths(project):
    moves = dict(ROOTS)
    works = sorted(path for path in (project / '作品').glob('F*') if path.is_dir())
    if not works or any((project / target).exists() or not (project / source).is_dir() for source, target in ROOTS.items()):
        raise ValueError(f'项目须具备完整的迁移前目录：{project}')
    empty = []
    for work in works:
        source = work.relative_to(project).as_posix()
        exports = work / '07-返修交接/成片'
        general = work / '99-综合资料'
        if not exports.is_dir() or (work / '08-成片').exists() or not general.is_dir():
            raise ValueError(f'作品须具备完整的迁移前目录：{work}')
        if any(path.name != '.DS_Store' for path in general.iterdir()):
            raise ValueError(f'作品综合资料须先确认归属：{general}')
        empty.append(general)
        moves[exports.relative_to(project).as_posix()] = translate(source, ROOTS) + '/08-成片'
    return dict(sorted(moves.items(), key=lambda item: -len(item[0]))), empty


def translate_json(value, project, moves):
    if isinstance(value, str):
        prefix = project.as_posix() + '/'
        if value.startswith(prefix):
            return prefix + translate(value[len(prefix):], moves)
        return translate(value, moves)
    if isinstance(value, dict):
        return {translate_json(key, project, moves): translate_json(item, project, moves) for key, item in value.items()}
    if isinstance(value, list):
        return [translate_json(item, project, moves) for item in value]
    return value


def rewrite_markdown(text, file, project, moves):
    old_key = file.relative_to(project).as_posix()
    new_parent = Path(translate(old_key, moves)).parent

    def link(match):
        value = match[2] or match[3]
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match[0]
        spelling = unquote(parsed.path)
        path = Path(spelling)
        rooted = spelling.split('/')[0] in ROOTS
        if path.is_absolute():
            target = path
        elif rooted:
            target = project / path
        else:
            target = file.parent / path
        target = target.resolve()
        if not target.is_relative_to(project):
            return match[0]
        key = target.relative_to(project).as_posix()
        mapped = translate(key, moves)
        if mapped == key and new_parent == Path(old_key).parent:
            return match[0]
        if path.is_absolute():
            rewritten = str(project / mapped)
        elif rooted:
            rewritten = mapped
        else:
            rewritten = os.path.relpath(mapped, new_parent.as_posix())
        if parsed.path.endswith('/'):
            rewritten += '/'
        if '%' in parsed.path:
            rewritten = quote(rewritten, safe='/')
        if parsed.query:
            rewritten += '?' + parsed.query
        if parsed.fragment:
            rewritten += '#' + parsed.fragment
        if rewritten == value:
            return match[0]
        return match[1] + ('<' + rewritten + '>' if match[2] is not None else rewritten) + ')'

    link_pattern = r'(!?\[[^\]\n]*\]\()(?:<([^>\n]+)>|([^()\n]+))\)'
    path_pattern = re.compile(
        r'(?<![\w/.-])(?:(?:\.\./)+)?(?:作品/F\d+[^|`\n]*?|资源|归档|08-完单复盘)'
        r'/[^|`<>\n\s；，、。)）]+'
    )

    def plain(value):
        def path(match):
            key = match[0]
            if not key.startswith('../'):
                return translate(key, moves)
            target = (file.parent / key).resolve()
            if not target.is_relative_to(project):
                return key
            mapped = translate(target.relative_to(project).as_posix(), moves)
            result = os.path.relpath(mapped, new_parent.as_posix())
            return result + '/' if key.endswith('/') else result
        return path_pattern.sub(path, value)

    lines = []
    for line in text.splitlines(keepends=True):
        pieces = []
        start = 0
        for match in re.finditer(link_pattern, line):
            pieces.extend((plain(line[start:match.start()]), link(match)))
            start = match.end()
        pieces.append(plain(line[start:]))
        lines.append(''.join(pieces))
    result = ''.join(lines)
    if file.name == 'README.md' and Path(old_key).parts[0] == '作品':
        result = result.replace('`07-返修交接/成片/`', '`08-成片/`')
    return result


def migrate(project, *, apply=False):
    project = project.resolve()
    moves, empty = paths(project)
    index = project / '资源/资源索引.json'
    original = json.loads(index.read_text(encoding='utf-8-sig'))
    data = translate_json(original, project, moves)
    data['aliases'] = {key: translate(value, moves) for key, value in original['aliases'].items()}
    data['aliases'].update({translate(key, moves): translate(value, moves)
                            for key, value in original['aliases'].items() if translate(key, moves) != translate(value, moves)})
    data['aliases'].update(moves)
    data['alias_stamps'] = original.get('alias_stamps', {}) | data.get('alias_stamps', {})
    data['outputs'] = {key: translate(value, moves) for key, value in original['outputs'].items()} | data['outputs']
    edits = {index: (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()}
    for file in sorted(project.rglob('*')):
        if not file.is_file() or file.is_symlink() or file == index:
            continue
        relative = file.relative_to(project)
        if any(part.startswith('.') or part in HISTORY for part in relative.parts):
            continue
        if file.suffix == '.md':
            if relative.parts[0] == '01-客户资料':
                continue
            raw = file.read_bytes()
            encoding = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
            old = raw.decode(encoding)
            new = rewrite_markdown(old, file, project, moves)
            if new != old:
                edits[file] = new.encode(encoding)
        elif file.name in CURRENT_JSON or file.name.endswith('.jianying.json') or (
                relative.parts[0] == '资源' and file.name == '版本信息.json'):
            old = json.loads(file.read_text(encoding='utf-8-sig'))
            new = translate_json(old, project, moves)
            if new != old:
                edits[file] = (json.dumps(new, ensure_ascii=False, indent=2) + '\n').encode()
    result = {'project': project.name, 'works': len(empty), 'rewritten': len(edits), 'moves': moves}
    if not apply:
        return result

    stamp = datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')
    backup = project / '归档' / f'Iris目录迁移前-{stamp}.zip'
    renamed = []
    written = []
    with ZipFile(backup, 'x', ZIP_DEFLATED) as archive:
        archive.writestr('目录路径映射.json', json.dumps(moves, ensure_ascii=False, indent=2))
        for file in edits:
            archive.write(file, file.relative_to(project))
        for directory in empty:
            for file in directory.iterdir():
                archive.write(file, file.relative_to(project))
    try:
        for old, new in ROOTS.items():
            (project / old).rename(project / new)
            renamed.append((old, new))
        for old, new in moves.items():
            if old not in ROOTS:
                intermediate = translate(old, ROOTS)
                (project / intermediate).rename(project / new)
                renamed.append((intermediate, new))
        for source, body in edits.items():
            key = source.relative_to(project).as_posix()
            target = project / translate(key, moves)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    stream.write(body)
                    stream.close()
                    os.chmod(temporary, target.stat().st_mode)
                    temporary.replace(target)
                    written.append(key)
                finally:
                    temporary.unlink(missing_ok=True)
        for directory in empty:
            current = project / translate(directory.relative_to(project).as_posix(), ROOTS)
            (current / '.DS_Store').unlink(missing_ok=True)
            current.rmdir()
    except Exception:
        for old, new in reversed(renamed):
            (project / new).rename(project / old)
        with ZipFile(backup) as archive:
            for key in written:
                (project / key).write_bytes(archive.read(key))
            for directory in empty:
                directory.mkdir(exist_ok=True)
                key = (directory / '.DS_Store').relative_to(project).as_posix()
                if key in archive.namelist():
                    (project / key).write_bytes(archive.read(key))
        raise
    result['backup'] = translate(backup.relative_to(project).as_posix(), ROOTS)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True, help='Project root containing the original Iris work directories')
    parser.add_argument('--apply', action='store_true', help='Save original affected documents and move directories')
    args = parser.parse_args()
    print(json.dumps(migrate(args.project, apply=args.apply), ensure_ascii=False, indent=2))
