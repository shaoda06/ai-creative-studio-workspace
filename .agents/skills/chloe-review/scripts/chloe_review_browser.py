"""Read-only Chloe review projection; records stay in their original documents."""
from pathlib import Path
from urllib.parse import unquote, urlsplit

from chloe_documents import LINK, MISSING, media_reference, read_document, records, template
from chloe_publication_browser import project_context
import project_resources as resources


def references(root, source, value):
    result = []
    for label, href in LINK.findall(value):
        url = urlsplit(href)
        if url.scheme or url.netloc or not url.path:
            continue
        target = (source.parent/unquote(url.path)).resolve()
        if not target.is_relative_to(root):
            continue
        key = target.relative_to(root).as_posix()
        # Same project context only; hidden paths and symlink escapes use the common boundary.
        resources.local(root, key)
        if target.is_file():
            result.append({'label': label, 'key': key, 'section': unquote(url.fragment)})
    return result


def read(root):
    review_path = resources.local(root, '综合资料/运营复盘.md')
    review_doc = read_document(root, review_path, template('chloe-positioning', '运营复盘模板.md'), {})
    allowed = {review_path.relative_to(root).as_posix()}

    def row(source, value, identity):
        refs = [dict(ref, field=field) for field, cell in value.items() for ref in references(root, source, cell)]
        allowed.update(ref['key'] for ref in refs)
        return {'id': value[identity], 'source': source.relative_to(root).as_posix(),
                'fields': value, 'references': refs}

    videos = []
    for path in sorted((root/'projects').glob('V*-*/README.md')):
        if (path.parent/'.archived').exists():
            continue
        project, identity, title, doc = project_context(root, path.parent.name)
        source = project/'README.md'
        allowed.add(source.relative_to(root).as_posix())
        current = {r['字段']: r['内容'] for r in records(doc, '定位与当前进度')}
        publications = [row(source, r, '发布编号') for r in records(doc, '发布记录')]
        samples = {}
        for metric in records(doc, '效果数据'):
            record = row(source, metric, '采集编号')
            samples.setdefault(record['id'], []).append(record)
        reviews = [row(source, r, '复盘编号') for r in records(doc, '单条复盘')]
        cover = None
        for adopted in records(doc, '当前采用'):
            if adopted['用途'].startswith('封面/') and adopted['资源引用'] not in MISSING:
                cover = media_reference(root, source, adopted['资源引用'])['file']
                allowed.add(cover)
                break
        if cover is None:
            for publication in reversed(publications):
                for field in ('竖版封面引用', '横版封面引用'):
                    value = publication['fields'][field]
                    if value not in MISSING:
                        cover = media_reference(root, source, value)['file']
                        allowed.add(cover)
                        break
                if cover:
                    break
        videos.append({'project': project.name, 'id': identity, 'title': title, 'status': current['视频状态'],
                       'source': source.relative_to(root).as_posix(), 'coverKey': cover,
                       'samples': [{'id': key, 'rows': values} for key, values in samples.items()],
                       'reviews': reviews, 'publications': publications})
    conclusions = [row(review_path, r, '复盘编号') for r in records(review_doc, '跨视频结论')]
    trials = [row(review_path, r, '验证编号') for r in records(review_doc, '建议验证')]
    sources = {(r['source'], r['id']): r for r in conclusions + [r for v in videos for r in v['reviews']]}
    for trial in trials:
        value = trial['fields']['复盘编号']
        refs = references(root, review_path, value)
        source_key = (refs[0]['key'], refs[0]['label']) if refs else (review_path.relative_to(root).as_posix(), value)
        trial['origin'] = sources.get(source_key)
    return {'videos': videos, 'conclusions': conclusions, 'trials': trials}, allowed


def file(root, key):
    _, allowed = read(root)
    if key not in allowed:
        raise FileNotFoundError('文件未被本项目复盘资料直接引用')
    return resources.local(root, key)
