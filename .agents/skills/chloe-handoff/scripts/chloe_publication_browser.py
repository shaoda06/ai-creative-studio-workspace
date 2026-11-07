"""Read Chloe publication preparations and original media without writing business state."""
import html
from pathlib import Path
import re
from urllib.parse import quote, urlsplit

from chloe_documents import LINK, MISSING, media_reference, read_document, records, template
import project_resources as resources


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
        cover = None
        if row['封面引用'] not in MISSING:
            ref = media_reference(root, project/'发布资料.md', row['封面引用'])
            cover = media(resources.local(root, ref['file']), 'image')
        materials.append({'id': row['资料编号'], 'fields': {k: plain(v) for k,v in row.items()}, 'film': film, 'cover': cover})
    history = []
    for row in records(doc, '发布记录'):
        link = LINK.fullmatch(row['文案'])
        public_link = LINK.fullmatch(row['发布链接'])
        public_url = public_link[2] if public_link else row['发布链接']
        public_url = public_url if urlsplit(public_url).scheme in {'http', 'https'} else None
        history.append({'url': public_url, 'fields': {k:plain(v) for k,v in row.items()},
                        'materialId': link[1] if link and link[2] == '发布资料.md' else None})
    return {'project': name, 'id': identity, 'title': title,
            'finals': [media(path, 'video') for path in final_files(project)],
            'materials': materials, 'history': history}


def media_file(root, name, key):
    project, identity, title, doc = project_context(root, name)
    allowed = set(final_files(project))
    for source, rows in [(project/'发布资料.md', preparations(root, project, identity, title)),
                         (project/'README.md', records(doc, '发布记录'))]:
        for row in rows:
            if row['封面引用'] not in MISSING:
                ref = media_reference(root, source, row['封面引用'])
                path = resources.local(root, ref['file'])
                if path.suffix.lower() in resources.KINDS['图片']:
                    allowed.add(path)
    target = resources.local(root, key)
    if target not in allowed:
        raise FileNotFoundError('不是本视频成片或已引用的发布封面')
    return target
