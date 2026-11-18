"""Cache validated Chloe documents against their actual file/version dependencies."""
from functools import lru_cache
import json
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

from backend.services.read_views import ReadViews
from chloe_documents import LINK, MEDIA, SKILLS, owner_for, parse, records, read_document as validate_document
import project_resources as resources

documents = ReadViews(limit=512)


def stamp(path):
    try:
        state = path.stat()
        return state.st_ino, state.st_mtime_ns, state.st_size
    except FileNotFoundError:
        return None


@lru_cache(maxsize=512)
def dependencies(path, revision, summary=False):
    text = path.read_text('utf-8-sig')
    if summary:
        doc = parse(text)
        values = [row['资源引用'] for row in records(doc, '当前采用')]
        if path.name == '声音说明.md':
            values.extend(row['资源引用'] for row in records(doc, '参考版本') if row['用途'] == '声音原始参考')
        if path.name == '参考视频说明.md':
            values.extend(row['内容'] for row in records(doc, '参考视频信息') if row['字段'] == '播放版本引用')
        text = '\n'.join(values)
    links = set()
    for _, href in LINK.findall(text):
        target = urlsplit(href)
        if not target.scheme and not target.netloc:
            links.add(path.parent / unquote(target.path))
    references = tuple(dict.fromkeys(MEDIA.findall(text)))
    return links, references


def document_sources(root, path, source=None):
    with resources.reuse_read_indexes():
        return _document_sources(root, path, source)


def _document_sources(root, path, source=None, *, summary=False):
    files = {path}
    if source is not None:
        files.update((source, SKILLS / 'chloe-positioning/references/固定资料写法规范.md'))
    revision = stamp(path)
    if revision is None:
        return {path: None}
    links, references = dependencies(path, revision, summary)
    files.update(links)
    result = {}
    for scope, identity, version, href in references:
        owner = root / '综合资料' if scope == '共用' else owner_for(root, path)
        # Compare only referenced entries, so an unrelated resource import does
        # not invalidate every document using the shared resource index.
        target = Path(os.path.abspath(path.parent / href))
        key = target.relative_to(owner).as_posix()
        index = resources.read_index(owner)
        result[(owner, identity, version)] = json.dumps(index['files'].get(key) if index is not None else None, sort_keys=True)
        files.add(target.parent / '版本信息.json')
    owner = owner_for(root, path)
    if owner != root / '综合资料':
        files.add(owner / '资源/共用引用.json')
    result.update((file, stamp(file)) for file in files)
    return result


def read_document(root, path, source, substitutions, *, body=None):
    if body is not None:
        return validate_document(root, path, source, substitutions, body=body)
    return documents.read((root, path, tuple(substitutions.items())), [source],
            lambda: validate_document(root, path, source, substitutions),
            source_snapshot=lambda: document_sources(root, path, source))[0]


def read_catalog_document(root, path, source, substitutions):
    files = [path, source, SKILLS / 'chloe-positioning/references/固定资料写法规范.md']
    return documents.read((root, path, 'catalog', tuple(substitutions.items())), files,
        lambda: validate_document(root, path, source, substitutions, check_references=False))[0]


def asset_sources(root, folder, pattern, *, summary=False):
    result = {}
    with resources.reuse_read_indexes():
        for path in sorted(folder.glob(pattern)):
            result.update(_document_sources(root, path, summary=summary))
    for skill in ('chloe-assets', 'chloe-positioning', 'chloe-creative', 'chloe-reference-videos'):
        for path in (SKILLS / skill / 'templates').glob('*.md'):
            result[path] = stamp(path)
    guide = SKILLS / 'chloe-positioning/references/固定资料写法规范.md'
    result[guide] = stamp(guide)
    return result
