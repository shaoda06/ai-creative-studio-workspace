"""Read Chloe publication preparations and manage unreferenced final files."""
from datetime import datetime, timezone
from functools import lru_cache
import html
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import sys
import tempfile
from urllib.parse import quote, unquote, urlsplit
from markdown_it import MarkdownIt

SKILLS = Path(__file__).resolve().parents[2]
for skill in ('chloe-positioning', 'studio-workspace-browser', 'studio-video-processing'):
    sys.path.insert(0, str(SKILLS / skill / 'scripts'))

from chloe_documents import LINK, MISSING, media_reference, read_document, records, template
import project_resources as resources
from video_metadata import probe


def project_context(root, name):
    if not re.fullmatch(r'V\d{3,}-.+', name) or '/' in name or '\\' in name:
        raise FileNotFoundError('视频项目不存在')
    project = resources.local(root, 'projects/'+name)
    if project.parent != root/'projects' or not project.is_dir() or (project/'.archived').exists():
        raise FileNotFoundError('视频项目不存在')
    identity, title = name.split('-', 1)
    doc = read_document(root, project/'README.md', template('chloe-creative', '视频README模板.md'),
                        {'identity': identity, 'title': title})
    return project, identity, title, doc


def final_files(project):
    folder = project/'成片'
    if not folder.exists():
        return []
    if folder.is_symlink():
        raise ValueError('成片目录不能指向项目外部')
    files = []
    for path in sorted(folder.rglob('*')):
        if any(part.startswith('.') for part in path.relative_to(folder).parts):
            continue
        if path.is_file() and path.suffix.lower() in resources.KINDS['视频']:
            if not path.resolve().is_relative_to(folder):
                raise ValueError('成片文件越出成片目录')
            files.append(path.resolve())
    return files


@lru_cache(maxsize=256)
def final_video_metadata(path, _revision):
    try:
        info = probe(path)
    except (OSError, ValueError):
        return None
    return {field: info[field] for field in ('width', 'height', 'duration')}


def final_file_info(path):
    info = path.stat()
    created = getattr(info, 'st_birthtime', None)
    file_time = created if created is not None else info.st_mtime
    revision = (info.st_ino, info.st_mtime_ns, info.st_size)
    return {
        'fileTime': datetime.fromtimestamp(file_time, timezone.utc).isoformat(),
        'fileTimeSource': 'created' if created is not None else 'modified',
        'videoMetadata': final_video_metadata(path, revision),
    }


def validate_final_name(filename):
    if (not filename or filename.startswith('.') or any(c in filename for c in '/\\:<>|?*"')
            or any(ord(c) < 32 for c in filename) or PureWindowsPath(filename).is_reserved()
            or Path(filename).suffix.lower() not in resources.KINDS['视频']):
        raise ValueError('请选择有效的视频文件名')


def import_final(root, name, filename, stream):
    project, _, _, _ = project_context(root, name)
    validate_final_name(filename)
    folder = project / '成片'
    if folder.is_symlink():
        raise ValueError('成片目录不能使用符号链接')
    folder.mkdir(exist_ok=True)
    target = folder / filename
    if target.exists() or target.is_symlink():
        raise FileExistsError('成片目录已有同名文件，请改名后录入')
    # A writable staging file stays invisible to listing until validation and an atomic no-clobber save.
    with tempfile.TemporaryDirectory(prefix='.upload-', dir=folder) as staging:
        pending = Path(staging) / filename
        with pending.open('wb') as output:
            shutil.copyfileobj(stream, output)
        duration = probe(pending)['duration']
        if duration is None or duration <= 0:
            raise ValueError('无法确认视频时长')
        try:
            os.link(pending, target)
        except FileExistsError as error:
            raise FileExistsError('成片目录已有同名文件，请改名后录入') from error
    return {'name': filename, 'key': target.relative_to(root).as_posix()}


def preparations(root, project, identity, title):
    path = resources.local(root, (project/'发布资料.md').relative_to(root).as_posix())
    if not path.exists():
        return []
    return records(read_document(root, path, template('chloe-handoff', '发布资料模板.md'),
                                {'identity': identity, 'title': title}), '发布资料')


def listing(root, api):
    result = []
    for path in sorted((root/'projects').glob('V*-*/README.md')):
        if (path.parent/'.archived').exists():
            continue
        project, identity, title, doc = project_context(root, path.parent.name)
        current = {row['字段']: row['内容'] for row in records(doc, '定位与当前进度')}
        result.append({'project': project.name, 'id': identity, 'title': title,
                       'status': current['视频状态'], 'finalCount': len(final_files(project))})
    return result


def plain(value):
    return html.unescape(re.sub(r'<br\s*/?>', '\n', value, flags=re.I))


def detail(root, name, api):
    project, identity, title, doc = project_context(root, name)
    rows = preparations(root, project, identity, title)
    base = f'{api}/publication-videos/{quote(name)}/files/'
    def media(path, kind):
        key = path.relative_to(root).as_posix()
        return {'kind': kind, 'name': path.name, 'key': key, 'url': base+quote(key, safe='/')}
    materials = []
    for row in rows:
        film = None if row['成片文件'] in MISSING else media((project/LINK.fullmatch(row['成片文件'])[2]).resolve(), 'video')
        covers = []
        for label in ('横版封面', '竖版封面'):
            image = None
            if row[label+'引用'] not in MISSING:
                ref = media_reference(root, project/'发布资料.md', row[label+'引用'])
                image = media(resources.local(root, ref['file']), 'image')
            covers.append({'label': label, 'media': image})
        materials.append({'id': row['资料编号'], 'fields': {k: plain(v) for k,v in row.items()}, 'film': film, 'covers': covers})
    history = []
    for row in records(doc, '发布记录'):
        link = LINK.fullmatch(row['文案'])
        public_link = LINK.fullmatch(row['发布链接'])
        public_url = public_link[2] if public_link else row['发布链接']
        public_url = public_url if urlsplit(public_url).scheme in {'http', 'https'} else None
        history.append({'url': public_url, 'fields': {k:plain(v) for k,v in row.items()},
                        'materialId': link[1] if link and link[2] == '发布资料.md' else None})
    finals = []
    for path in final_files(project):
        try:
            info = final_file_info(path)
        except FileNotFoundError:
            continue
        finals.append({**media(path, 'video'), **info})
    finals.sort(key=lambda item: item['fileTime'], reverse=True)
    return {'project': name, 'id': identity, 'title': title, 'finals': finals,
            'materials': materials, 'history': history}


def media_file(root, name, key):
    project, identity, title, doc = project_context(root, name)
    allowed = set(final_files(project))
    for source, rows in [(project/'发布资料.md', preparations(root, project, identity, title)),
                         (project/'README.md', records(doc, '发布记录'))]:
        for row in rows:
            for field in ('横版封面引用', '竖版封面引用'):
                if row[field] not in MISSING:
                    ref = media_reference(root, source, row[field])
                    path = resources.local(root, ref['file'])
                    if path.suffix.lower() in resources.KINDS['图片']:
                        allowed.add(path)
    target = resources.local(root, key)
    if target not in allowed:
        raise FileNotFoundError('不是本视频成片或已引用的发布封面')
    return target


def retarget_final_links(source, text, before, after):
    relative = Path(os.path.relpath(after, source.parent)).as_posix()

    def update(match):
        if match[1]:
            return match[0]
        raw = match[2] or match[3]
        if raw.startswith(('/', '\\')) or re.match(r'[a-z][a-z\d+.-]*:', raw, re.I):
            return match[0]
        if (source.parent / raw).resolve() == before:
            return '](<' + relative + '>)'
        link = urlsplit(raw)
        decoded = Path(unquote(link.path))
        if link.scheme or link.netloc or decoded.is_absolute() or (source.parent / decoded).resolve() != before:
            return match[0]
        if not (link.query or link.fragment):
            return '](<' + relative + '>)'
        rewritten = link._replace(path=quote(relative, safe='/')).geturl()
        return '](<' + rewritten + '>)'

    # The fixed records use bracketed destinations; also accept ordinary relative Markdown links.
    pattern = r'(`+[^`\r\n]+`+)|\]\((?:<([^>\r\n]+)>|([^\s<>()]+))\)'
    lines = text.splitlines(keepends=True)
    fragments = []
    start = 0
    for block in MarkdownIt('commonmark').parse(text):
        if block.type not in ('fence', 'code_block'):
            continue
        first, end = block.map
        fragments.extend((re.sub(pattern, update, ''.join(lines[start:first])), ''.join(lines[first:end])))
        start = end
    fragments.append(re.sub(pattern, update, ''.join(lines[start:])))
    return ''.join(fragments)


def move_final(source, target):
    if sys.platform == 'win32' or target.exists() and source.samefile(target):
        source.rename(target)
        return
    os.link(source, target)
    try:
        source.unlink()
    except OSError:
        target.unlink()
        raise


def rename_final(root, name, key, stem):
    project, _, _, _ = project_context(root, name)
    source = resources.local(root, key)
    if source not in final_files(project):
        raise FileNotFoundError('不是本视频成片目录内的视频')
    stem = stem.strip()
    if stem.lower().endswith(source.suffix.lower()):
        stem = stem[:-len(source.suffix)].rstrip()
    if '#' in stem:
        raise ValueError('文件名不能包含 #，以便项目内链接正常打开')
    filename = stem + source.suffix
    validate_final_name(filename)
    target = source.with_name(filename)
    if source.name == filename:
        return {'name': filename, 'key': key}
    if target.is_symlink() or (target.exists() and not (
        source.name.casefold() == filename.casefold() and source.samefile(target)
    )):
        raise FileExistsError('已有同名成片，请换一个文件名')

    with tempfile.TemporaryDirectory(prefix='.final-rename-', dir=project) as temporary:
        staged = Path(temporary)
        edits = []
        for document in sorted(project.rglob('*.md')):
            if (any(part.startswith('.') or part == '历史版本' for part in document.relative_to(project).parts)
                    or document.is_symlink() or not document.resolve().is_relative_to(project)):
                continue
            original = document.read_bytes()
            text = original.decode('utf-8')
            updated = retarget_final_links(document, text, source, target)
            if updated != text:
                backup = staged / f'{len(edits)}.original'
                replacement = staged / f'{len(edits)}.updated'
                backup.write_bytes(original)
                replacement.write_bytes(updated.encode('utf-8'))
                edits.append((document, backup, replacement))
        move_final(source, target)
        applied = []
        try:
            for document, backup, replacement in edits:
                if document.read_bytes() != backup.read_bytes():
                    raise ValueError('项目资料正在更新，请重试改名')
                replacement.replace(document)
                applied.append((document, backup))
        except (OSError, ValueError):
            try:
                for document, backup in reversed(applied):
                    backup.replace(document)
            finally:
                move_final(target, source)
            raise
    return {'name': filename, 'key': target.relative_to(root).as_posix()}


def delete_final(root, name, key):
    project, _, _, _ = project_context(root, name)
    target = resources.local(root, key)
    if target not in final_files(project):
        raise FileNotFoundError('不是本视频成片目录内的视频')
    markdown = MarkdownIt('commonmark').enable('table')
    for source in project.rglob('*.md'):
        for block in markdown.parse(source.read_text(encoding='utf-8')):
            for token in block.children or []:
                if token.type != 'link_open':
                    continue
                value = urlsplit(token.attrGet('href'))
                if not value.scheme and (source.parent/unquote(value.path)).resolve() == target:
                    raise ValueError('该成片仍被 '+source.relative_to(project).as_posix()+' 引用，请先处理引用再删除。')
    target.unlink()


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description='把已导出的视频录入 Chloe 成片目录')
    parser.add_argument('--project-root', type=Path, required=True, help='具名项目根目录')
    parser.add_argument('--video', required=True, help='作品目录名')
    parser.add_argument('source', type=Path, help='待录入的视频原件')
    args = parser.parse_args()
    try:
        with args.source.open('rb') as stream:
            result = import_final(args.project_root.resolve(), args.video, args.source.name, stream)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
