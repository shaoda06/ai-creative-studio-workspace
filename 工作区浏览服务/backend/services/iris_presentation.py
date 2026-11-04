"""Select the current Iris documents and adopted media for the project page."""
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

from backend.parsers.documents import cells
import project_resources as resources


MAIN_NAMES = {
    '01-客户资料': r'需求与来源(?:记录)?',
    '02-参考分析': r'制作简报',
    '03-创意脚本': r'制作脚本|正式剧本',
    '04-分镜声音': r'分镜与声音制作稿',
    '05-资产': r'资产清单(?:与制作说明)?',
    '06-视频生产': r'生产任务(?:-.+)?',
    '07-返修交接': r'返修与剪辑交接(?:记录)?|剪映草稿交付(?:-.+)?|交接说明',
    '08-完单复盘': r'项目复盘|复盘',
}
LINK = re.compile(r'\[([^\]]+)\]\((?:<([^>]+)>|([^)]+))\)')
MEDIA_KINDS = {'图片': 'image', '视频': 'video', '音频': 'audio'}
CUSTOMER_FOLDER = '01-客户资料'
BRIEF_FOLDER = '02-参考分析'
ASSET_FOLDER = '05-资产'
PROCESS_FOLDERS = {'其他资料', '历史版本', '工作稿', '执行记录'}
STAGE_ARCHIVE_FOLDERS = {
    '03-创意脚本': {'03-创意脚本', '03-创意与脚本', '02-剧集剧本'},
    '04-分镜声音': {'04-分镜声音', '04-分镜与视觉方案', '03-分镜脚本'},
}


def table(text, *columns):
    """Read the first table with the requested headers, before later histories."""
    lines = iter(text.splitlines())
    for line in lines:
        if not line.lstrip().startswith('|'):
            continue
        headers = cells(line)
        if not set(columns).issubset(headers):
            continue
        if not re.fullmatch(r'\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*', next(lines, '')):
            continue
        for row in lines:
            if not row.strip():
                continue
            if not row.lstrip().startswith('|'):
                break
            values = cells(row)
            if len(values) == len(headers):
                yield dict(zip(headers, values))
        return


def entries(value):
    links = [(title, angle or bare) for title, angle, bare in LINK.findall(value)]
    return links or [('', part.strip().strip('`')) for part in re.split(r'[；;]|<br\s*/?>', value)]


def brief_sources(projects, project, api, files, primary):
    root = projects.project(project)
    customer = next((item['children'] for item in files if item['key'] == CUSTOMER_FOLDER), [])
    requirement_name = MAIN_NAMES[CUSTOMER_FOLDER]
    candidates = {item['key'] for item in customer if item['kind'] == 'file'
                  and not re.fullmatch(rf'{requirement_name}(?:-v\d+(?:\.\d+)*)?\.md', item['name'], re.IGNORECASE)}
    for folder in customer:
        if folder['kind'] == 'group' and folder['name'] in {'原始参考', '客户原件', '原始资料', '参考资料'}:
            candidates.update(item['key'] for item in folder['children'] if item['kind'] == 'file')
    index = resources.read_index(root) or {}
    candidates.update(key for key in index.get('aliases', {})
                      if key.startswith(CUSTOMER_FOLDER + '/') and not PROCESS_FOLDERS.intersection(Path(key).parts))
    # New projects may reference imported originals by resource version directly.
    for key in (*primary.get(CUSTOMER_FOLDER, []), *primary.get(BRIEF_FOLDER, [])):
        source = root / key
        for _, angle, bare in LINK.findall(source.read_text('utf-8-sig')):
            href = urlsplit(angle or bare)
            target = (source.parent / unquote(href.path)).resolve()
            if not href.scheme and not href.netloc and target.is_relative_to(root):
                relative = target.relative_to(root).as_posix()
                ref = index.get('files', {}).get(relative)
                if ref and ref.get('origin') in {'user_upload', 'import'}:
                    candidates.add(relative)

    items = {}
    for key in sorted(candidates, key=lambda path: (Path(path).suffix.lower() != '.md', path)):
        try:
            file = projects.file(project, key)
        except FileNotFoundError:
            continue
        relative = file.relative_to(root).as_posix()
        items[relative] = {
            'kind': MEDIA_KINDS.get(resources.media_kind(file), 'file'),
            'name': file.name,
            'key': relative,
            'url': api + '/projects/' + quote(project, safe='') + '/files/' + quote(relative, safe='/'),
        }
    return list(items.values())


def archived_documents(files, folders, name_pattern=None):
    def collect(items):
        results = []
        for item in items:
            if item['kind'] == 'group':
                if item['name'] in folders:
                    if item['children']:
                        results.append(item)
                elif item['name'] not in PROCESS_FOLDERS:
                    results.extend(collect(item['children']))
            elif name_pattern and re.fullmatch(name_pattern, item['name']):
                results.append(item)
        return results

    archived = [entry for group in files if group['kind'] == 'group' and group['name'] in {'归档', '历史制作资料'}
                for entry in collect(group['children'])]
    return sorted(archived, key=lambda item: item['kind'] == 'group')


def adopted_media(projects, project, api, listing):
    root = projects.project(project)
    source = root / listing
    content = source.read_text('utf-8-sig')
    rows = list(table(content, '编号', '已有／需制作', '当前文件及版本'))
    legacy = not rows
    if legacy:
        # The older list uses the current link label for the adoption decision.
        rows = table(content, '编号', '对象/版本', '当前入口', '状态及用途')
    items = []
    for row in rows:
        if legacy and re.search(r'未采用|不采用|待审|历史候选|不作当前输入', row['状态及用途']):
            continue
        if not legacy and row['已有／需制作'] != '已采用':
            continue
        for label, href in entries(row['当前入口'] if legacy else row['当前文件及版本']):
            if legacy and not label.startswith(('已采用', '已确认', '当前认可', '已通过', '正式')):
                continue
            link = urlsplit(href)
            path = (source.parent / unquote(link.path)).resolve()
            if link.scheme or link.netloc or not path.is_relative_to(root) or not resources.media_kind(path):
                continue
            try:
                file = projects.file(project, path.relative_to(root).as_posix())
            except FileNotFoundError:
                continue
            key = file.relative_to(root).as_posix()
            kind = MEDIA_KINDS[resources.media_kind(file)]
            ref = resources.reference(root, key)
            items.append({
                'title': row['编号'] + ' · ' + row.get('名称及具体状态', row.get('对象/版本', label)),
                'version': ref['version'] if ref else '',
                'media': {'kind': kind, 'key': key, 'name': file.name,
                          'url': api + '/projects/' + quote(project, safe='') + '/files/' + quote(key, safe='/')},
            })
    return items


def presentation(projects, project, api, files):
    root = projects.project(project)
    status = root / '项目状态.md'
    rows = table(status.read_text('utf-8-sig'), '对象', '当前版本/文件') if status.is_file() else ()
    current = {unquote(path) for row in rows for _, path in entries(row['当前版本/文件'])}
    primary = {}
    for group in files:
        pattern = MAIN_NAMES.get(group['name'])
        if not pattern or group['kind'] != 'group':
            continue
        possible = [item['key'] for item in group['children'] if item['kind'] == 'file'
                    and re.fullmatch(rf'(?:{pattern})(?:-v\d+(?:\.\d+)*)?\.md', item['name'], re.IGNORECASE)]
        selected = [key for key in possible if key in current]
        if group['name'] == '06-视频生产':
            batches = {}
            for key in possible:
                match = re.match(r'生产任务-(R\d+)(?:-|\.)', Path(key).name)
                if match:
                    batches.setdefault(match[1], []).append(key)
            single_records = {keys[0] for keys in batches.values() if len(keys) == 1}
            selected = [key for key in possible if key in current or key in single_records]
        primary[group['name']] = selected or (possible if len(possible) == 1 else [])
    listing = primary.get(ASSET_FOLDER, [])
    sources = brief_sources(projects, project, api, files, primary)
    has_current_brief = primary.get(CUSTOMER_FOLDER) or primary.get(BRIEF_FOLDER) or sources
    stage_archives = {folder: archived_documents(files, folders)
                      for folder, folders in STAGE_ARCHIVE_FOLDERS.items() if not primary.get(folder)}
    if not listing:
        asset_name = MAIN_NAMES[ASSET_FOLDER]
        stage_archives[ASSET_FOLDER] = [
            item for group in archived_documents(files, {ASSET_FOLDER, '05-资产准备'})
            for item in group['children']
            if item['kind'] == 'file' and re.fullmatch(rf'{asset_name}(?:-v\d+(?:\.\d+)*)?\.md', item['name'], re.IGNORECASE)
        ]
    return {
        'primary': primary,
        'adopted': adopted_media(projects, project, api, listing[0]) if len(listing) == 1 else [],
        'brief': {'sources': sources, 'archived': [] if has_current_brief else archived_documents(
            files, {CUSTOMER_FOLDER, '01-甲方资料', BRIEF_FOLDER}, r'制作简报(?:-v\d+(?:\.\d+)*)?\.md')},
        'stageArchives': stage_archives,
    }
