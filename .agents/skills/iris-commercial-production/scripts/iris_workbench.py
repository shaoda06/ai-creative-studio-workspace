"""Iris business projection for the complete shared production page. Read only."""
from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote

from backend.parsers import documents
from backend.parsers.documents import cells
from backend.services.iris_presentation import table, entries, work_view
from iris_works import discover_works, work_root
import iris_browser_production as production


def document(projects, name, api, key, version=''):
    path = projects.file(name, key)
    project = projects.project(name)
    key = path.relative_to(project).as_posix()
    html = documents.markdown(path.read_text('utf-8-sig'), key)
    html = production.legacy_links(html, api + '/files/')
    return {'kind': 'document', 'name': path.name, 'key': key, 'version': version,
            'url': production.file_url(api, key), 'doc': {'title': path.stem, 'html': html,
                                                        'url': production.file_url(api, key)}}


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


def items(projects, name):
    project = projects.project(name)
    result = []
    for item in discover_works(project) or []:
        archived = bool(production.legacy_sources(project, item['id']))
        result.append({'kind': 'group', 'name': item['id'], 'title': item['name'], 'key': item['key'],
                       'readOnly': archived, 'statusHtml': '<span class="status-badge status-gray">历史归档</span>' if archived else ''})
    return result


def validate_notes(project, work, identities, changes):
    if production.legacy_sources(project, work):
        raise ValueError('历史制作归档只读')
    rounds = {item['number']: {(entry['id'], entry['stage'], entry['run']) for entry in item['segments']}
              for item in round_spec(project, work)}
    if (any(item.number not in rounds for item in changes.rounds)
            or any((note.segment, note.stage, note.run) not in identities
                   or note.roundNumber is not None and (note.segment, note.stage, note.run) not in rounds.get(note.roundNumber, set())
                   for note in changes.notes)):
        raise ValueError('意见须对应本作品已有候选及已登记的整片轮次')


def legacy_detail(project, api, work):
    """Keep the archive's native scene/round/source data instead of flattened batch cards."""
    from backend.parsers.project import build_data
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
    data = build_data(archive, web_episode_navigation=True, load_scope='09-剧集制作',
                      episode_id=episodes[0].name, episode_mode='playback')
    original = next(item for item in data['catalogues']['09-剧集制作']['children'] if item['name'] == episodes[0].name)
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
                identity = '-'.join((episodes[0].name, scene, segment['id'], video['run'], video['stage']))
                video['contextUrl'] = api + '/works/' + work + '/production-context?source=' + quote(archive_key, safe='') + '&identity=' + quote(identity, safe='')
    result.update(name=work, readOnly=True, productionComplete=False)
    return result


def detail(projects, name, space_api, work):
    project = projects.project(name)
    root = work_root(project, work)
    api = space_api + '/projects/' + quote(name, safe='')
    entry = next(item for item in discover_works(project) if item['id'] == work)
    legacy = legacy_detail(project, api, work)
    if legacy is not None:
        return {**legacy, 'title': entry['name']}
    data = production.production_data(project, api, work)
    segments = data['segments']
    by_id = {item['id']: item for item in segments}
    rounds = []
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
            item['scriptHtml'] = rendered
            values.append({**{k: value[k] for k in ('id', 'duration', 'stage', 'run')}, 'key': key,
                           'scriptHtml': rendered, 'scriptUrl': plan['url'] if plan else ''})
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
                    business_shots = list(re.finditer(r'(?m)^####\s+(SH\d+)[^\n]*\n', text))
                    if business_shots and len(business_shots) == len(context['shots']):
                        for offset, match in enumerate(business_shots):
                            end = business_shots[offset + 1].start() if offset + 1 < len(business_shots) else len(text)
                            part = text[match.start():end]
                            context['shots'][offset].update(id=match[1], html=production.legacy_links(documents.markdown(part, plan['key']), api + '/files/'))
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
        rounds.append({'number': number, 'created_at': spec['created_at'], 'note': spec.get('note', ''),
                       'episodeRound': True, 'script': script, 'storyboard': storyboard, 'issues': issues, 'segments': values})
    rounds.sort(key=lambda item: item['number'])
    view = work_view(projects, name, space_api, work, production)
    primary = view['irisPresentation']['primary']
    current_sources = {}
    for field, folder in [('script', '03-创意脚本'), ('storyboard', '04-分镜声音')]:
        values = primary.get(folder, [])
        current_sources[field] = document(projects, name, api, values[0], re.search(r'v\d+', values[0])[0] if re.search(r'v\d+', values[0]) else '') if len(values) == 1 else None
    if not rounds and current_sources['storyboard']:
        board = current_sources['storyboard']
        text = projects.file(name, board['key']).read_text('utf-8-sig')
        # Explicit P headings also give a useful page before the first generated candidate.
        for match in re.finditer(r'(?m)^#{2,4}\s+(?:分段\s*)?(P\d{3,})[^\n]*', text):
            identity = match[1]
            item = by_id.setdefault(identity, {'id': identity, 'duration': 0, 'videos': []})
            part = segment_text(text, identity)
            duration = re.search(r'(\d+(?:\.\d+)?)秒', match[0])
            item.update(planned=not item['videos'], scriptHtml=production.legacy_links(documents.markdown(part, board['key']), api + '/files/'),
                        scriptUrl=board['url'], duration=float(duration[1]) if duration else item['duration'])
    materials = [{**item['media'], 'materialGroup': 'adopted', 'materialStatus': '已采用', 'materialNote': item['title']}
                 for item in view['irisPresentation']['adopted'] if item['media']['kind'] == 'image']
    return {'kind': 'group', 'name': work, 'title': entry['name'], 'key': entry['key'], 'scenes': ['whole'],
            'segments': {'whole': sorted(by_id.values(), key=lambda item: item['id'])},
            'sceneRounds': {'whole': rounds}, 'episodeRounds': [{'number': item['number'], 'scenes': ['whole']} for item in rounds],
            'script': current_sources['script'], 'storyboards': {'whole': current_sources['storyboard']} if current_sources['storyboard'] else {},
            'directorSheets': {'whole': director_sheets(projects, name, api, root)},
            'materials': materials, 'productionComplete': False, 'productionIssues': []}


def director_sheets(projects, name, api, root):
    candidates, formal = [], []
    records = sorted((root / '04-分镜声音/导演表').glob('导演表来源与登记*.md'))
    for record in records:
        for row in table(record.read_text('utf-8-sig'), '页码', '来源分镜版本', '图表版本／候选编号', '候选原图', '正式采用图'):
            version, candidate = re.split(r'[/／]', row['图表版本／候选编号'])
            for _, link in entries(row['候选原图']):
                path = projects.file(name, production.local_key(projects.project(name), (record.parent / unquote(link)).resolve()))
                key = path.relative_to(projects.project(name)).as_posix()
                image = {'kind': 'image', 'name': path.name, 'key': key, 'url': production.file_url(api, key),
                         'page': int(row['页码'].split('/')[0]), 'sourceVersion': row['来源分镜版本'],
                         'version': version, 'candidateNumber': int(candidate), 'adopted': row['正式采用图'].startswith('[')}
                candidates.append(image)
                if image['adopted']:
                    formal.append(image)
    return {'candidates': candidates, 'formal': formal,
            'record': document(projects, name, api, records[-1].relative_to(projects.project(name)).as_posix()) if records else None}


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


def downloads(projects, name, space_api, work, scene='whole'):
    project = projects.project(name)
    api = space_api + '/projects/' + quote(name, safe='')
    result = {stage: {kind: {'count': 0, 'url': None, 'files': []} for kind in ('videos', 'director', 'canvas')}
              for stage in ('一采', '二采', '后处理')}
    values = detail(projects, name, space_api, work)
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
    candidates = {video['key']: video for items in values.get('segments', {}).values() for item in items for video in item['videos']}
    # Only existing explicit delivery manifests enable packaging; opening the tab does not pack.
    view = work_view(projects, name, space_api, work, production)
    manifests = [item['file']['key'] for item in view['irisPresentation']['delivery']['items']
                 if item['file']['key'].endswith('.jianying.json')]
    for manifest in dict.fromkeys(manifests):
        path = projects.file(name, manifest)
        spec = json.loads(path.read_text('utf-8-sig'))
        media = [item for item in spec['media'] if item.get('timeline', True)]
        keys = [production.local_key(project, item['file']) for item in media]
        stages = {candidates[key]['stage'] for key in keys if key in candidates}
        if len(stages) != 1 or not all(key in candidates for key in keys):
            continue
        stage = stages.pop()
        package = {'name': spec['name'], 'count': len(keys), 'url': api + '/jianying-download?path=' + quote(manifest, safe='') + '&format=zip'}
        resource = result[stage]['videos']
        resource.setdefault('packages', []).append(package)
        if len(resource['packages']) == 1:
            resource.update(count=package['count'], url=package['url'])
    return result
