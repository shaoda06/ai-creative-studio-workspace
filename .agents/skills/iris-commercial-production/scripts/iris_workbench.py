"""Iris business projection for the complete shared production page. Read only."""
from copy import deepcopy
from html import escape
import json
from math import isclose
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

from director_export import submitted_media
from backend.parsers import documents
from backend.parsers.documents import cells
from backend.services.iris_presentation import asset_review, delivery_overview, table, entries, work_view
from iris_works import discover_works, work_root
import iris_browser_production as production


SHOT_HEADING = re.compile(r'(?m)^####\s+(SH\d{3,})(?!\d)[^\n]*\n')


def document_ref(project, api, path):
    key = path.relative_to(project).as_posix()
    return {'kind': 'document', 'name': path.name, 'key': key, 'url': production.file_url(api, key)}


def document(projects, name, api, key, version=''):
    path = projects.file(name, key)
    ref = document_ref(projects.project(name), api, path)
    html = production.legacy_links(documents.markdown(path.read_text('utf-8-sig'), ref['key']), api + '/files/')
    return {**ref, 'version': version, 'doc': {'title': path.stem, 'html': html, 'url': ref['url']}}


def work_status(projects, name, space_api, project, root):
    path = root / '作品状态.md'
    if not path.is_file():
        return None, {'items': []}, {}
    path = projects.file(name, path.relative_to(project).as_posix())
    api = space_api + '/projects/' + quote(name, safe='')
    ref = document_ref(project, api, path)
    text = path.read_text('utf-8-sig')
    delivery = delivery_overview(projects, name, space_api, project, text)
    summary = re.search(r'(?m)^(?:-\s*)?(?:当前阶段与下一步|状态)[：:]\s*([^\n]+)', text)
    stage = re.search(r'(?m)^(?:-\s*)?制作状态[：:][ \t]*([^\n]+)', text)
    records = {row['对象']: row['当前版本/文件'] for row in table(text, '对象', '当前版本/文件')}
    return {'label': stage[1].strip() if stage else '', 'summaryHtml': production.legacy_links(
        documents.markdown(summary[1], ref['key']), api + '/files/'
    ) if summary else '', 'deliverySummary': delivery['summary'], 'record': ref}, delivery, records


def adopted_segments(projects, name, project, root, record):
    path = projects.file(name, record)
    if path.suffix != '.md' or not path.is_relative_to(root / '07-返修交接'):
        raise ValueError('视频采用记录须位于本作品的返修交接目录')
    section = re.search(r'(?ms)^## 当前采用组合[ \t]*\n(.*?)(?=^#{1,2} |\Z)', path.read_text('utf-8-sig'))
    if not section:
        return set()
    adopted = set()
    for row in table(section[1], '段号', '采用版本及文件'):
        for _, link in entries(row['采用版本及文件']):
            href = urlsplit(link)
            relative = Path(unquote(href.path))
            if href.scheme or href.netloc or relative.is_absolute():
                raise ValueError('采用版本须引用本项目的媒体文件')
            key = production.local_key(project, (path.parent / relative).resolve())
            adopted.add((row['段号'], key))
    return adopted


def segment_text(text, identity):
    """Use an explicit P heading or P table row; never assign the entire film to a segment."""
    match = re.search(r'(?m)^(#{2,4})\s+(?:分段\s*)?' + re.escape(identity) + r'(?!\d)[^\n]*', text)
    if match:
        tail = text[match.end():]
        end = re.search(r'(?m)^#{1,' + str(len(match[1])) + r'}\s', tail)
        return text[match.start():match.end()] + tail[:end.start() if end else len(tail)]
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.match(r'\s*\|\s*' + re.escape(identity) + r'\s*\|', line):
            header = index - 1
            while header >= 0 and lines[header].lstrip().startswith('|'):
                header -= 1
            return '\n\n'.join('**' + label + '**：' + value for label, value in zip(cells(lines[header + 1]), cells(line)))
    return ''


def segment_rows(text):
    for field in ('生成段', '段号', '生产段'):
        rows = {row[field]: row for row in table(text, field) if re.fullmatch(r'P\d{3,}', row[field])}
        if rows:
            return rows
    return {}


def scene_segments(identities, rows):
    assigned = [rows.get(identity, {}).get('场次', '').strip() for identity in identities]
    if all(scene in ('', '整片') for scene in assigned):
        return {'whole': identities}
    scenes = {}
    previous = None
    for identity, scene in zip(identities, assigned):
        if not re.fullmatch(r'S\d{3,}', scene):
            raise ValueError(f'{identity} 的场次未登记或编号无效（应为 S001 形式）')
        if scene in scenes and scene != previous:
            raise ValueError(f'{scene} 的分段在整片轮次中须连续排列')
        scenes.setdefault(scene, []).append(identity)
        previous = scene
    return scenes


def listed_shots(row):
    value = row.get('对应镜号') or row.get('所含原镜号') or row.get('源摄影镜头', '')
    interval = re.fullmatch(r'SH(\d{3,})\s*[-–—]\s*SH(\d{3,})', value.strip())
    if interval:
        first, last = map(int, interval.groups())
        return [f'SH{number:03d}' for number in range(first, last + 1)]
    ids = re.split(r'[、,，\s]+', value.strip())
    return ids if all(re.fullmatch(r'SH\d{3,}', identity) for identity in ids) and len(set(ids)) == len(ids) else []


def apply_plan_timing(context, row, duration, business_ids):
    shots = context['shots']
    if context.get('shotTimingSource') == 'recorded':
        return
    ids = listed_shots(row)
    declared = row.get('段内Shot及时间', '')
    if not ids or len(ids) != len(shots) or (business_ids and ids != business_ids):
        return
    if declared:
        spans = []
        end = 0.0
        for index, part in enumerate(re.split(r'[；;]', declared), 1):
            match = re.fullmatch(r'\s*Shot\s+(\d+)\s*[:：]\s*(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*秒\s*', part)
            if not match or int(match[1]) != index:
                return
            start, stop = map(float, match.groups()[1:])
            if not isclose(start, end, abs_tol=1e-6) or stop <= start:
                return
            spans.append((start, stop - start))
            end = stop
        request_length = row.get('请求时长') or row.get('目标时长') or row.get('目标段长', '')
        requested = re.fullmatch(r'(\d+(?:\.\d+)?)\s*秒', request_length)
        plan_duration = float(requested[1]) if requested else duration
        if len(spans) != len(shots) or not isclose(end, plan_duration, abs_tol=1e-6) or spans[-1][0] >= duration:
            return
    elif len(ids) == 1 and duration > 0:
        # An explicitly mapped single shot starts at the beginning of the segment.
        spans = [(0, duration)]
    else:
        return
    for index, (shot, (start, planned)) in enumerate(zip(shots, spans), 1):
        if shot['id'] != f'SH{index:03d}' or (shot['duration'] is not None and (
                not isclose(shot['duration'], planned, abs_tol=1e-6)
                or not isclose(shot['start'], start, abs_tol=1e-6))):
            return
    for shot, (start, planned) in zip(shots, spans):
        shot.update(start=start, duration=planned)
    context['shotTimingSource'] = 'plan'


def source(projects, name, api, declaration, issues):
    if not declaration:
        return None
    try:
        return document(projects, name, api, declaration['file'], declaration['version'])
    except FileNotFoundError:
        issues.append('本轮来源文件缺失：' + declaration['file'])
        return None


def round_spec(project, work):
    root = work_root(project, work)
    path = root / '06-视频生产/制作轮次.json'
    if not path.resolve().is_relative_to(root):
        raise ValueError('制作轮次索引必须位于本作品目录内')
    return json.loads(path.read_text('utf-8-sig'))['rounds'] if path.is_file() else []


def current_status_label(status, delivery, archived):
    label = status['label'] if status else ''
    return label or ('' if archived else delivery.get('status')) or '未登记制作状态'


def items(projects, name, space_api):
    project = projects.project(name)
    result = []
    for item in discover_works(project) or []:
        archived = bool(production.legacy_sources(project, item['id']))
        status, delivery, _ = work_status(projects, name, space_api, project, project / item['key'])
        result.append({'kind': 'group', 'name': item['id'], 'title': item['name'], 'key': item['key'],
                       'hasArchive': archived, 'workStatusLabel': current_status_label(status, delivery, archived)})
    return result


def validate_notes(project, work, identities, changes, view=None):
    if view == 'archive' or (view is None and production.legacy_sources(project, work)):
        raise ValueError('历史制作归档只读')
    rounds = {item['number']: {(entry['id'], entry['stage'], entry['run']) for entry in item['segments']}
              for item in round_spec(project, work)}
    if (any(item.number not in rounds for item in changes.rounds)
            or any((note.segment, note.stage, note.run) not in identities
                   or note.roundNumber is not None and (note.segment, note.stage, note.run) not in rounds.get(note.roundNumber, set())
                   for note in changes.notes)):
        raise ValueError('意见须对应本作品已有候选及已登记的整片轮次')


def archive_episode(project, work):
    sources = production.legacy_sources(project, work)
    if not sources:
        return None
    if len(sources) != 1:
        raise ValueError('一件作品只能登记一份原短剧制作归档')
    archive = sources[0]
    episodes = [path for path in (archive / '09-剧集制作').iterdir()
                if path.is_dir() and re.fullmatch(r'EP\d{3,}', path.name)]
    if len(episodes) != 1:
        raise ValueError('历史作品须明确对应一集原制作资料')
    return archive, episodes[0].name


def legacy_detail(project, api, work, archived):
    """Keep the archive's native scene/round/source data instead of flattened batch cards."""
    from backend.parsers.project import build_data
    archive, episode = archived
    data = build_data(archive, web_episode_navigation=True, load_scope='09-剧集制作',
                      episode_id=episode, episode_mode='playback')
    original = next(item for item in data['catalogues']['09-剧集制作']['children'] if item['name'] == episode)
    archive_key = archive.relative_to(project).as_posix()
    prefix = api + '/files/' + quote(archive_key, safe='/') + '/'
    result = production.legacy_links(deepcopy(original), prefix)

    def keys(value):
        if isinstance(value, dict):
            return {k: archive_key + '/' + v if k == 'key' and isinstance(v, str) and v else keys(v) for k, v in value.items()}
        if isinstance(value, list):
            return [keys(item) for item in value]
        return value

    result = keys(result)
    for scene, segments in result.get('segments', {}).items():
        for segment in segments:
            for video in segment['videos']:
                identity = '-'.join((episode, scene, segment['id'], video['run'], video['stage']))
                video['contextUrl'] = api + '/works/' + work + '/production-context?source=' + quote(archive_key, safe='') + '&identity=' + quote(identity, safe='')
    result.update(name=work, readOnly=True, productionComplete=False)
    return result


def detail(projects, name, space_api, work, view=None, *, executions=None):
    project = projects.project(name)
    root = work_root(project, work)
    api = space_api + '/projects/' + quote(name, safe='')
    entry = next(item for item in discover_works(project) if item['id'] == work)
    status, delivery, records = work_status(projects, name, space_api, project, root)
    archived = archive_episode(project, work) if view != 'current' else None
    if view == 'archive' and not archived:
        raise FileNotFoundError('本作品没有登记历史制作归档')
    if archived:
        archive, _ = archived
        legacy = legacy_detail(project, api, work, archived)
        history = archived_director_sheets(projects, name, api, project, archive)
        if history and len(legacy['scenes']) == 1:
            sheet = legacy.setdefault('directorSheets', {}).setdefault(legacy['scenes'][0],
                                                                      {'candidates': [], 'formal': [], 'record': None})
            sheet['history'] = history
        if status:
            status.update(label=delivery['status'], summaryHtml='')
            handoff = delivery['archivedHandoff']
            if handoff and (project / handoff).is_relative_to(archive):
                status['record'] = document_ref(project, api, project / handoff)
        return {**legacy, 'title': entry['name'], 'workStatus': status}
    if status:
        has_archive = bool(production.legacy_sources(project, work))
        if has_archive:
            status['deliverySummary'] = ''
        status['label'] = current_status_label(status, delivery, has_archive)
    data = production.production_data(project, api, work, legacy_fallback=False, executions=executions)
    segments = data['segments']
    adoption = records.get('视频采用记录')
    if adoption:
        adopted = adopted_segments(projects, name, project, root, adoption)
        for item in segments:
            for video in item['videos']:
                if (item['id'], video['key']) in adopted:
                    video.update(approved=True, adoptionKnown=True)
    by_id = {item['id']: item for item in segments}
    rounds = []
    groups_by_round = {}
    numbers = set()
    for spec in round_spec(project, work):
        number = spec['number']
        if not isinstance(number, int) or number < 1 or number in numbers:
            raise ValueError('整片制作轮次编号须为不重复的正整数')
        numbers.add(number)
        issues = []
        script = source(projects, name, api, spec.get('script'), issues)
        storyboard = source(projects, name, api, spec.get('storyboard'), issues)
        plan = source(projects, name, api, spec.get('plan') or spec.get('storyboard'), issues)
        plan_text = projects.file(name, plan['key']).read_text('utf-8-sig') if plan else ''
        rows = segment_rows(plan_text)
        values = []
        for value in spec['segments']:
            identity = value['id']
            if not re.fullmatch(r'P\d{3,}', identity) or any(item['id'] == identity for item in values):
                raise ValueError('整片轮次分段编号无效或重复：' + identity)
            key = production.local_key(project, value['file'])
            item = by_id.setdefault(identity, {'id': identity, 'duration': value['duration'], 'scriptHtml': '', 'videos': []})
            candidate = next((video for video in item['videos'] if video['key'] == key
                              and video['stage'] == value['stage'] and video['run'] == value['run']), None)
            if not candidate:
                issues.append(identity + ' 的指定候选未在原执行记录找到，不换用其他版本')
            text = segment_text(plan_text, identity)
            rendered = production.legacy_links(documents.markdown(text, plan['key']), api + '/files/') if text else ''
            row = rows.get(identity, {})
            business_shots = list(SHOT_HEADING.finditer(text))
            shot_ids = [shot[1] for shot in business_shots] or listed_shots(row)
            item['scriptHtml'] = rendered
            values.append({**{k: value[k] for k in ('id', 'duration', 'stage', 'run')}, 'key': key,
                           'scriptHtml': rendered, 'scriptUrl': plan['url'] if plan else '', 'shotIds': shot_ids})
            if candidate and plan:
                context = candidate.get('context')
                if context and not context.get('businessSource'):
                    context['businessSource'] = plan['key']
                    # The actual request remains the source of model shots and prompts.
                    if rendered:
                        context['scriptHtml'] = rendered
                        context['scriptUrl'] = plan['url']
                        context['source'] = '分镜按已登记的业务依据；提示词来自' + context.get('source', '实际执行记录')
                        context['issues'] = [issue for issue in context['issues'] if issue != '执行记录未关联分镜快照；这里展示当次实际提示词中的镜头描述。']
                    for label, link in entries(text):
                        if label == '中文':
                            target = (project / plan['key']).parent / unquote(link)
                            path = project / production.local_key(project, target.resolve())
                            if path.is_file():
                                context['prompts'].update(chinese=path.read_text('utf-8-sig'), chineseUrl=production.file_url(api, path.relative_to(project).as_posix()))
                    if value.get('prompt'):
                        prompt = projects.file(name, value['prompt'])
                        chinese = re.search(r'^##\s+\d*\s*(?:同版)?中文[^\n]*\n(.*?)(?=^##\s|\Z)', prompt.read_text('utf-8-sig'), re.M | re.S)
                        if chinese:
                            context['prompts'].update(chinese=chinese[1].strip().removeprefix('```text').removesuffix('```').strip(), chineseUrl=production.file_url(api, prompt.relative_to(project).as_posix()))
                    apply_plan_timing(context, row, value['duration'], [shot[1] for shot in business_shots])
                    if business_shots and len(business_shots) == len(context['shots']):
                        for offset, match in enumerate(business_shots):
                            end = business_shots[offset + 1].start() if offset + 1 < len(business_shots) else len(text)
                            part = text[match.start():end]
                            context['shots'][offset].update(id=match[1], html=production.legacy_links(documents.markdown(part, plan['key']), api + '/files/'))
                    elif not business_shots and len(shot_ids) == len(context['shots']) and all(
                            shot['id'] == f'SH{index:03d}' for index, shot in enumerate(context['shots'], 1)):
                        for shot, shot_id in zip(context['shots'], shot_ids):
                            shot['html'] = shot['html'].replace(f"<h4>{shot['id']}</h4>", f'<h4>{shot_id}</h4>', 1)
                            shot['id'] = shot_id
                    dialogues = []
                    for shot in business_shots:
                        end = next((other.start() for other in business_shots if other.start() > shot.start()), len(text))
                        part = text[shot.start():end]
                        for match in re.finditer(r'\*\*台词与发声者\*\*：([^\n“]+)：“([^”]+)”', part):
                            dialogues.append({'shot': shot[1], 'index': 0, 'speaker': match[1].split('，')[0], 'original': match[2]})
                    if not dialogues and context['prompts']['chinese']:
                        for match in re.finditer(r'([^\n，。]*?)S\d+同期声：([^\n]+)', context['prompts']['chinese']):
                            dialogues.append({'shot': context['shots'][0]['id'] if context['shots'] else 'SH001', 'index': len(dialogues), 'speaker': match[1], 'original': match[2]})
                    context['dialogues'] = dialogues
        planned = set(re.findall(r'(?m)^(?:#{2,4}\s+(?:分段\s*)?|\|\s*)(P\d{3,})(?!\d)', plan_text))
        missing = sorted(planned - {item['id'] for item in values})
        if missing:
            issues.append('本轮缺少计划分段：' + '、'.join(missing))
        if not values:
            raise ValueError('整片轮次至少需要一个明确分段')
        groups_by_round[number] = scene_segments([item['id'] for item in values], rows)
        rounds.append({'number': number, 'created_at': spec['created_at'], 'note': spec.get('note', ''),
                       'episodeRound': True, 'script': script, 'storyboard': storyboard, 'issues': issues, 'segments': values})
    rounds.sort(key=lambda item: item['number'])
    presentation = work_view(projects, name, space_api, work, production, include_archives=False)['irisPresentation']
    primary = presentation['primary']
    registered = {}
    for field, folder in [('制作脚本', '03-创意脚本'), ('分镜与声音', '04-分镜声音'),
                          ('资产清单', '05-资产'), ('生产任务', '06-视频生产')]:
        key = records.get(field, '')
        if Path(key).suffix.lower() == '.md':
            path = projects.file(name, key)
            if not path.is_relative_to(root / folder):
                raise ValueError('现行制作资料须位于本作品对应阶段：' + key)
            registered[folder] = path.relative_to(project).as_posix()
    current_sources = {}
    for field, folder in [('script', '03-创意脚本'), ('storyboard', '04-分镜声音')]:
        values = [registered[folder]] if folder in registered else primary.get(folder, [])
        current_sources[field] = document(projects, name, api, values[0], re.search(r'v\d+', values[0])[0] if re.search(r'v\d+', values[0]) else '') if len(values) == 1 else None
    production_task = document_ref(project, api, project / registered['06-视频生产']) if '06-视频生产' in registered else None
    scene_members = {}
    scene_rounds = {}
    episode_rounds = []
    for round_ in rounds:
        groups = groups_by_round[round_['number']]
        episode_rounds.append({'number': round_['number'], 'scenes': list(groups)})
        entries_by_id = {item['id']: item for item in round_['segments']}
        for scene, identities in groups.items():
            scene_members.setdefault(scene, {}).update((identity, by_id[identity]) for identity in identities)
            scene_rounds.setdefault(scene, []).append({**round_, 'segments': [entries_by_id[identity] for identity in identities]})
    current_plan = production_task or current_sources['storyboard']
    if not rounds and current_plan:
        text = projects.file(name, current_plan['key']).read_text('utf-8-sig')
        rows = segment_rows(text)
        headings = {match[1]: match[0] for match in re.finditer(r'(?m)^#{2,4}\s+(?:分段\s*)?(P\d{3,})[^\n]*', text)}
        planned_ids = list(dict.fromkeys([*rows, *headings]))
        for identity in planned_ids:
            item = by_id.setdefault(identity, {'id': identity, 'duration': 0, 'videos': []})
            part = segment_text(text, identity)
            row = rows.get(identity, {})
            duration = re.search(r'(\d+(?:\.\d+)?)\s*秒', row.get('请求时长') or row.get('目标时长') or headings.get(identity, ''))
            item.update(planned=not item['videos'], scriptHtml=production.legacy_links(documents.markdown(part, current_plan['key']), api + '/files/'),
                        scriptUrl=current_plan['url'], shotIds=SHOT_HEADING.findall(part) or listed_shots(row),
                        duration=float(duration[1]) if duration else item['duration'])
        scene_members = {scene: {identity: by_id[identity] for identity in identities}
                         for scene, identities in scene_segments(planned_ids, rows).items()}
    assigned_ids = {identity for members in scene_members.values() for identity in members}
    unassigned = {identity: item for identity, item in by_id.items() if identity not in assigned_ids}
    if unassigned or not scene_members:
        scene_members.setdefault('whole', {}).update(unassigned)
    listing = [registered['05-资产']] if '05-资产' in registered else primary.get('05-资产', [])
    material_record = document_ref(project, api, project / listing[0]) if len(listing) == 1 else None
    review = asset_review(projects, name, space_api, listing[0]) if listing and listing != primary.get('05-资产') else presentation['assetReview']
    materials = [{**item['media'], 'materialGroup': item['group'], 'materialStatus': item['status'],
                  'materialNote': ' · '.join(filter(None, (item['title'], item['version']))), 'materialReview': material_record,
                  'approvalHtml': production.legacy_links(documents.markdown(item['decision'], listing[0]), api + '/files/')}
                 for item in review if item['media']['kind'] == 'image']
    label = status['label'] if status else ''
    status_html = '<span class="status-badge status-gray">' + escape(label) + '</span>' if label else ''
    return {'kind': 'group', 'name': work, 'title': entry['name'], 'key': entry['key'], 'scenes': list(scene_members),
            'segments': {scene: list(items.values()) for scene, items in scene_members.items()},
            'sceneRounds': {scene: scene_rounds.get(scene, []) for scene in scene_members}, 'episodeRounds': episode_rounds,
            'script': current_sources['script'], 'storyboards': {scene: current_sources['storyboard'] for scene in scene_members} if current_sources['storyboard'] else {},
            'directorSheets': {'whole': director_sheets(projects, name, api, root)},
            'materials': materials, 'materialRecord': material_record, 'productionTask': production_task,
            'workStatus': status, 'statusHtml': status_html,
            'productionComplete': False, 'productionIssues': []}


def archived_director_sheets(projects, name, api, project, archive):
    records = sorted(archive.glob('客户项目/*/04-分镜与视觉方案/导演分镜表-当前索引.md'))
    if len(records) != 1:
        return []
    record = projects.file(name, records[0].relative_to(project).as_posix())
    text = record.read_text('utf-8-sig')
    versions = {version: source for source, version in re.findall(r'分镜\s*(v\d+)\s*对应导演表\s*(v\d+)', text)}
    sources = [(record, [link for row in table(text, '页码', '原图入口', '状态') for _, link in entries(row['原图入口'])])]
    for label, link in entries(text):
        if label != '分镜制作工作稿与历史记录':
            continue
        notes = (record.parent / unquote(link)).resolve()
        if notes.is_relative_to(archive) and notes.is_file():
            notes = projects.file(name, notes.relative_to(project).as_posix())
            sources.append((notes, [href for _, href in entries(notes.read_text('utf-8-sig'))]))
    images = []
    seen = set()
    for source, links in sources:
        reference = document_ref(project, api, source)
        for link in links:
            path = (source.parent / unquote(link)).resolve()
            match = re.search(r'导演分镜表-(v\d+)-第(\d+)页\.png$', path.name)
            if not match or (source != record and match[1] not in versions) or not path.is_relative_to(archive) or not path.is_file() or path in seen:
                continue
            path = projects.file(name, path.relative_to(project).as_posix())
            seen.add(path)
            key = path.relative_to(project).as_posix()
            images.append({'kind': 'image', 'name': path.name, 'key': key, 'url': production.file_url(api, key),
                           'page': int(match[2]), 'sourceVersion': versions.get(match[1], ''),
                           'version': match[1], 'sourceRecord': reference})
    return images


def director_sheets(projects, name, api, root):
    project = projects.project(name)
    candidates, formal = [], []
    records = sorted((root / '04-分镜声音/导演表').glob('导演表来源与登记*.md'))
    for record in records:
        reference = document_ref(project, api, projects.file(name, record.relative_to(project).as_posix()))
        for row in table(record.read_text('utf-8-sig'), '页码', '来源分镜版本', '图表版本／候选编号', '候选原图', '正式采用图'):
            version, candidate = re.split(r'[/／]', row['图表版本／候选编号'])
            adopted = next((link for label, link in entries(row['正式采用图']) if label), None)
            for _, link in entries(row['候选原图']):
                path = projects.file(name, production.local_key(project, (record.parent / unquote(link)).resolve()))
                key = path.relative_to(project).as_posix()
                image = {'kind': 'image', 'name': path.name, 'key': key, 'url': production.file_url(api, key),
                         'page': int(row['页码'].split('/')[0]), 'sourceVersion': row['来源分镜版本'],
                         'version': version, 'candidateNumber': int(candidate), 'adopted': adopted is not None,
                         'sourceRecord': reference}
                candidates.append(image)
                if adopted:
                    file = projects.file(name, production.local_key(project, (record.parent / unquote(adopted)).resolve()))
                    key = file.relative_to(project).as_posix()
                    formal.append({**image, 'name': file.name, 'key': key, 'url': production.file_url(api, key)})
    return {'candidates': candidates, 'formal': formal,
            'record': reference if records else None}


def director_spec(projects, name, work, path):
    project = projects.project(name)
    source = projects.file(name, path)
    archives = production.legacy_sources(project, work)
    archive = next((item for item in archives if source.is_relative_to(item)), None)
    if not source.name.endswith('.director.json') or not (archive or source.is_relative_to(work_root(project, work))):
        raise FileNotFoundError('本作品的导演包清单不存在')
    spec = json.loads(source.read_text('utf-8-sig'))
    if archive:
        # This exact historical archive prefix was retained in the original manifest.
        previous = '历史制作资料/' + archive.name + '/'
        current = archive.relative_to(project).as_posix() + '/'
        def rebase(key):
            return current + key.removeprefix(previous) if key.startswith(previous) else key
        spec['media'] = {slot: rebase(key) for slot, key in spec['media'].items()}
        if 'api' in spec:
            spec['api'] = rebase(spec['api'])
    return spec


def submitted_director_spec(project, execution):
    if execution['stage'] == '后处理':
        raise ValueError('后处理没有原生 H3 导演包')
    request, state = execution['request'], execution['state']
    if not request or not state.get('prompt_id'):
        raise ValueError('缺少实际提交请求或提交凭据')
    workflow = request['prompt']
    nodes = [key for key, node in workflow.items() if node['class_type'] == 'MiniMaxH3Director']
    if len(nodes) != 1:
        raise ValueError('实际请求中无法确定唯一的 H3 导演台')
    url = state.get('remote_url')
    if not url:
        raise ValueError('缺少本次实际提交的服务地址')
    node = nodes[0]
    timeline = json.loads(workflow[node]['inputs']['timeline_data'])
    task = execution['task']
    source_checks = {production.local_key(project, key, task['project']): (key, stamp)
                     for key, stamp in execution['sources'].items()}

    def frozen_file(value):
        key = production.local_key(project, value, task['project'])
        path = project / key
        if not path.is_file():
            raise ValueError('原素材已缺失：' + path.name)
        if key not in source_checks:
            raise ValueError('缺少原素材核对记录：' + path.name)
        original, stamp = source_checks[key]
        info = path.stat()
        if list(stamp) != [info.st_size, info.st_mtime_ns] and not production.resources.matches_recorded_stamp(project, original, stamp):
            raise ValueError('执行后原素材已变更：' + path.name)
        return key

    media = submitted_media(timeline, node, task.get('uploads', []), frozen_file)
    return {'name': execution_label(execution) + '.mmxpack.zip', 'node_id': node,
            'workflow': workflow, 'media': media, 'url': url}


def execution_label(execution):
    batch, record = execution['batch'], execution['record']
    segments = dict.fromkeys(segment for segment, _ in execution['segments'])
    parts = [batch, '、'.join(segments)]
    if record.name not in (batch, '后台执行'):
        parts.append(record.name)
    return ' · '.join(parts)


def execution_director_spec(projects, name, work, record):
    project = projects.project(name)
    executions = []
    production.production_data(project, '', work, legacy_fallback=False, executions=executions)
    source = next((item for item in executions if item['record'].relative_to(project).as_posix() == record), None)
    if source is None:
        raise FileNotFoundError('本作品没有对应的实际执行记录')
    return submitted_director_spec(project, source)


def add_execution_downloads(project, api, work, scene_keys, executions, result):
    seen = set()
    for execution in executions:
        record = execution['record']
        if record in seen or not any(key in scene_keys for _, key in execution['segments']):
            continue
        seen.add(record)
        label = execution_label(execution)
        stage = result[execution['stage']]
        submitted = bool(execution['request'] and execution['state'].get('prompt_id'))
        canvas = record / '任务.workflow.json'
        if submitted and canvas.is_file():
            key = production.local_key(project, canvas)
            stage['canvas']['files'].append({'name': label + ' · 画布', 'url': production.file_url(api, key) + '?download=1'})
            stage['canvas']['count'] += 1
        else:
            reason = '缺少实际执行画布' if submitted else '尚无实际提交凭据'
            stage['canvas'].setdefault('messages', []).append(label + '：' + reason)
        try:
            submitted_director_spec(project, execution)
        except (ValueError, KeyError, IndexError) as error:
            stage['director'].setdefault('messages', []).append(label + '：' + str(error))
        else:
            record_key = record.relative_to(project).as_posix()
            url = api + '/works/' + work + '/production-director?record=' + quote(record_key, safe='')
            stage['director']['files'].append({'name': label + ' · 导演包', 'url': url})
            stage['director']['count'] += 1


def downloads(projects, name, space_api, work, scene='whole', view=None):
    project = projects.project(name)
    api = space_api + '/projects/' + quote(name, safe='')
    result = {stage: {kind: {'count': 0, 'url': None, 'files': []} for kind in ('videos', 'director', 'canvas')}
              for stage in ('一采', '二采', '后处理')}
    executions = []
    values = detail(projects, name, space_api, work, view, executions=executions)
    archive_paths = production.legacy_sources(project, work)
    if values.get('readOnly'):
        if scene == 'whole' and len(values['scenes']) == 1:
            scene = values['scenes'][0]
        if scene not in values['scenes']:
            raise FileNotFoundError('历史场次不存在')
        for stage, folder in [('一采', '01-一采'), ('二采', '02-二采'), ('后处理', '03-后处理')]:
            directory = project / values['key'] / '06-阶段采用视频' / folder / (scene + '-场次') / '导演包'
            for path in sorted(directory.glob('*.json')):
                key = path.relative_to(project).as_posix()
                projects.file(name, key)
                if path.name.endswith('.director.json'):
                    url = api + '/works/' + work + '/production-director?path=' + quote(key, safe='')
                    resource = result[stage]['director']
                elif path.name.endswith('.workflow.json'):
                    url = production.file_url(api, key)
                    resource = result[stage]['canvas']
                else:
                    continue
                resource['files'].append({'name': path.name, 'url': url})
                resource['count'] += 1
    else:
        scene_items = values['segments'].values() if scene == 'whole' else [values['segments'].get(scene, [])]
        scene_keys = {video['key'] for items in scene_items for item in items for video in item['videos']}
        add_execution_downloads(project, api, work, scene_keys, executions, result)
    candidates = {video['key']: video for items in values.get('segments', {}).values() for item in items for video in item['videos']}
    # Only existing explicit delivery manifests enable packaging; opening the tab does not pack.
    _, delivery, _ = work_status(projects, name, space_api, project, work_root(project, work))
    work_packages = []
    covered = {}
    for round_ in values.get('episodeRounds', []):
        files = tuple(segment.get('key') for scene_id in round_['scenes']
                      for group in values['sceneRounds'][scene_id] if group['number'] == round_['number']
                      for segment in group['segments'])
        covered.setdefault(files, []).append(round_['number'])
    items = {item['file']['key']: item for item in delivery['items']}
    for key, item in items.items():
        if bool(values.get('readOnly')) != any((project / key).is_relative_to(path) for path in archive_paths):
            continue
        file = item['file']
        base = {'key': key, 'label': item['title'], 'version': item['version'], 'purpose': item['purpose']}
        if values.get('readOnly') and key.lower().endswith('.jypack'):
            work_packages.append({**base, 'archived': True, 'rounds': [], 'jypack': file['url'] + '?download=1', 'zip': None})
        if not file.get('jianying'):
            continue
        path = projects.file(name, key)
        spec = json.loads(path.read_text('utf-8-sig'))
        media = [item for item in spec['media'] if item.get('timeline', True)]
        keys = [production.local_key(project, item['file']) for item in media]
        if not keys or not all(key in candidates for key in keys):
            continue
        rounds = covered.get(tuple(keys), [])
        if rounds and all(candidates[key]['url'] for key in keys):
            work_packages.append({**base, **file['jianying'], 'rounds': rounds, 'count': len(keys)})
        stages = {candidates[key]['stage'] for key in keys if key in candidates}
        if len(stages) != 1:
            continue
        stage = stages.pop()
        package = {'name': spec['name'], 'count': len(keys), 'url': file['jianying']['zip']}
        resource = result[stage]['videos']
        resource.setdefault('packages', []).append(package)
        if len(resource['packages']) == 1:
            resource.update(count=package['count'], url=package['url'])
    result['workPackages'] = work_packages
    return result
