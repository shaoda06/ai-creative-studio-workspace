"""Read commercial task evidence into the shared video reviewer, without EP directories."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlsplit

import execution_records as records
import project_resources as resources
from prepared_documents import read_journal
from h3_browser_context import empty_context, request_context
from iris_works import work_root, historical_sources

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-video-processing/scripts'))
from postprocess_products import product_rows
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-h3-songssx/scripts'))
from songssx_workflow import TASK_TYPE as SONGSSX_TASK

STAGES = {'video-first-pass': '一采', 'video-second-pass': '二采', 'video-postprocess': '后处理'}
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.webm')


def production_section(project, work=None):
    root = work_root(project, work)
    return next(((root / name).relative_to(project).as_posix() for name in ('06-视频生产', '06-视频制作') if (root / name).is_dir()), None)


def local_key(project, value, old_root=None):
    path = Path(value)
    if path.is_absolute():
        path = path.relative_to(old_root or project)
    target = (project / path).resolve()
    if not target.is_relative_to(project.resolve()) or any(part.startswith('.') for part in path.parts):
        raise ValueError('制作资料越出项目：' + str(value))
    return resources.resolve_file(project, target).relative_to(project.resolve()).as_posix()


def file_url(api, key):
    return api + '/files/' + quote(key, safe='/')


def video_products(project, api, declared):
    products = []
    for row in product_rows(declared):
        key = local_key(project, row['file'])
        path = project / key
        if path.suffix.lower() not in VIDEO_EXTENSIONS or not path.is_file():
            raise ValueError('登记的候选产物不可播放或已缺失：' + key)
        info = path.stat()
        products.append({'id': row['id'], 'label': row['label'], 'default': row['default'],
                         'key': key, 'url': file_url(api, key),
                         'fileRevision': f'{info.st_size}:{info.st_mtime_ns}'})
    return products


def production_data(project, api, work=None, *, legacy_fallback=True, executions=None, scene_executions=None):
    section = production_section(project, work)
    segments, batches, contexts, bindings = {}, [], {}, {}
    if not section:
        return {'segments': [], 'batches': [], 'issues': []}
    directories = [project / section / '执行记录']
    if work is not None:
        directories.extend(historical_sources(project, work, 'records'))
    journals = sorted({path for directory in directories for path in directory.rglob('*-装配结果.json')})
    for journal_path in journals:
        local_key(project, journal_path)
        journal = read_journal(journal_path)
        if not journal.get('accepted'):
            continue  # Prepared-only/archived attempts are not submitted candidates.
        batch_key = journal_path.relative_to(project).as_posix()
        batch_name = journal_path.parent.name
        run = re.match(r'(R\d{3,})(?:-|$)', batch_name)
        if not run:
            raise ValueError('商业批次记录缺少R编号：' + batch_key)
        batch_segments = []
        for task in journal['tasks']:
            if scene_executions is not None and task['task_type'] == SONGSSX_TASK:
                target, = task['outputs']
                key = local_key(project, target['path'], task['project'])
                scene_executions.setdefault(key, []).append({
                    'batch': batch_key, 'record': local_key(project, task['record_dir'], task['project']),
                    'run': run[1], 'segments': [row['p'] for row in task['video_plan']['segments']],
                })
                continue
            stage = STAGES.get(task['task_type'])
            if not stage:
                continue
            record = project / local_key(project, task['record_dir'], task['project'])
            request_path = record / task.get('request_name', '请求.json')
            request = records.read(request_path) if records.exists(request_path) else None
            state_path = record / '后台任务状态.json'
            state = records.read(state_path) if records.exists(state_path) else {}
            check_path = record / '执行检查报告.json'
            sources = records.read(check_path).get('sources', {}) if records.exists(check_path) else {}
            product_path = record / '视频产物.json'
            products = {local_key(project, key): value for key, value in records.read(product_path)['candidates'].items()} if records.exists(product_path) else {}
            outputs = (task.get('segment_plan') or {}).get('targets', []) + task.get('outputs', [])
            task_segments = []
            for target in outputs:
                key = local_key(project, target['path'], task['project'])
                identity = re.search(r'(?:^|/)(P\d{3,})(?:-|\.)', key)
                if not identity:
                    raise ValueError('商业视频输出缺少分段编号：' + key)
                segment = identity[1]
                path = project / key
                if path.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue
                task_segments.append((segment, key))
                item = segments.setdefault(segment, {'id': segment, 'duration': 0, 'scriptHtml': '', 'videos': []})
                if any(video['key'] == key for video in item['videos']):
                    continue
                context = request_context(project, task, target.get('index', 0), request, api, sources, bindings, resolve_key=local_key, file_link=file_url) if request else empty_context('实际提交请求尚未保存；不以准备稿替代生成记录。')
                if stage == '后处理':
                    input_keys = [local_key(project, upload['file'], task['project']) for upload in task.get('uploads', [])]
                    source = next((contexts[source] for source in input_keys if source in contexts), None)
                    if source:
                        context = deepcopy(source)
                        context['source'] = '后处理输入所对应的生成记录'
                contexts[key] = context
                if request and stage != '后处理':
                    context['prompts']['englishUrl'] = file_url(api, request_path.relative_to(project).as_posix())
                info = path.stat() if path.is_file() else None
                video = {'key': key, 'url': file_url(api, key) if info else '', 'run': run[1], 'stage': stage,
                         'approved': False, 'adoptionKnown': False, 'candidateNumber': 1 + sum(v['stage'] == stage for v in item['videos']),
                         'fileRevision': str(info.st_size) + ':' + str(info.st_mtime_ns) if info else '',
                         'context': context, 'deliveryStatus': '已取回' if info else '未取回',
                         'taskStatus': state.get('status', '未记录'), 'taskStateUrl': file_url(api, state_path.relative_to(project).as_posix()),
                         'checkedAt': state.get('updated_at', '')}
                if key in products:
                    video['products'] = video_products(project, api, products[key])
                item['videos'].append(video)
                if request and task.get('segment_plan'):
                    director = request['prompt'][task['segment_plan']['director_node']]['inputs']
                    group = json.loads(director['timeline_data'])['segments'][target['index']]
                    item['duration'] = group.get('durationSec') or group['length'] / director['frame_rate']
                batch_segments.append({'id': segment, 'stage': stage, 'key': key})
            if executions is not None and task_segments:
                executions.append({'task': task, 'record': record, 'batch': batch_name, 'stage': stage,
                                   'segments': task_segments, 'request': request, 'state': state, 'sources': sources})
        if batch_segments:
            batches.append({'id': batch_key, 'name': batch_name, 'segments': batch_segments,
                            'url': file_url(api, batch_key)})
    if not segments and legacy_fallback:
        return legacy_production(project, api, work)
    return {'segments': sorted(segments.values(), key=lambda item: item['id']), 'batches': batches,
            'issues': ['候选按实际执行记录展示；网页不根据任务完成或文件存在推断业务采用。']}


def legacy_sources(project, work=None):
    if work is not None:
        return historical_sources(project, work, 'archives')
    return sorted(path for folder in ('归档', '历史制作资料') for path in (project / folder).glob('*')
                  if path.is_dir() and (path / '09-剧集制作').is_dir())


def legacy_links(value, prefix):
    if isinstance(value, dict):
        return {key: prefix + item if isinstance(item, str) and item and (key == 'url' or key.endswith('Url'))
                and not urlsplit(item).scheme and not item.startswith(('/', '#')) else legacy_links(item, prefix)
                for key, item in value.items()}
    if isinstance(value, list):
        return [legacy_links(item, prefix) for item in value]
    if isinstance(value, str) and ('href=' in value or 'src=' in value):
        return re.sub(r'(href|src)="([^"\n]+)"', lambda match: match[0] if urlsplit(match[2]).scheme or match[2].startswith(('/', '#'))
                      else match[1] + '="' + prefix + match[2] + '"', value)
    return value


def legacy_production(project, api, work=None):
    from backend.parsers.project import build_data
    segments, batches = [], []
    for source in legacy_sources(project, work):
        root_key = local_key(project, source)
        prefix = api + '/files/' + quote(root_key, safe='/') + '/'
        for episode in sorted((source / '09-剧集制作').iterdir()):
            if not episode.is_dir() or not re.fullmatch(r'EP\d{3,}|片头|片尾', episode.name):
                continue
            data = build_data(source, web_episode_navigation=True, load_scope='09-剧集制作', episode_id=episode.name, episode_mode='playback')
            for entry in data['catalogues']['09-剧集制作']['children']:
                for scene, items in entry.get('segments', {}).items():
                    batch_segments = []
                    for item in items:
                        item = legacy_links(deepcopy(item), prefix)
                        identity = episode.name + '-' + scene + '-' + item['id']
                        for video in item['videos']:
                            context_key = '-'.join((identity, video['run'], video['stage']))
                            video['key'] = root_key + '/' + video['key']
                            video['contextUrl'] = api + ('/works/' + work if work else '') + '/production-context?source=' + quote(root_key, safe='') + '&identity=' + quote(context_key, safe='')
                        item['label'] = item['id']
                        item['id'] = identity
                        segments.append(item)
                        if item['videos']:
                            latest = max(item['videos'], key=lambda v: (list(STAGES.values()).index(v['stage']), v['candidateNumber']))
                            batch_segments.append({'id': identity, 'stage': latest['stage'], 'key': latest['key']})
                    if batch_segments:
                        batches.append({'id': root_key + '/' + episode.name + '/' + scene, 'name': '历史 · ' + episode.name + ' / ' + scene,
                                        'readOnly': True, 'url': prefix, 'segments': batch_segments})
    return {'segments': segments, 'batches': batches, 'issues': ['历史制作资料只读展示，保留原采用事实，不重新开启生产。'] if batches else []}


def legacy_context(project, api, source, identity, work=None):
    from backend.parsers.project import build_data
    from backend.parsers.generation import load_context
    root = project / local_key(project, source)
    if root not in legacy_sources(project, work) or not re.fullmatch(r'(EP\d{3,}|片头|片尾)-C\d{3,}-P\d{3,}-R\d{3,}-(一采|二采|后处理)', identity):
        raise FileNotFoundError('历史生成记录不存在')
    data = build_data(root, web_episode_navigation=True, load_scope='09-剧集制作', episode_id=identity.split('-')[0], episode_mode='playback')
    if identity not in data['generationContexts']:
        return empty_context('该次历史生成资料关联尚未记录。')
    value = load_context(root, identity, historical_contexts(root, data['generationContexts']))['context']
    return legacy_links(value, api + '/files/' + quote(source, safe='/') + '/')


def historical_contexts(root, contexts):
    """Rebase only the original root explicitly recorded in the archived README."""
    readme = root / 'README.md'
    declared = re.search(r'当前目录仍为\s*`([^`]+)`', readme.read_text('utf-8')) if readme.is_file() else None
    if not declared:
        return contexts
    original = Path(declared[1])
    result = deepcopy(contexts)
    for context in result.values():
        for references in context.get('references', {}).values():
            for reference in references:
                path = Path(reference['file'])
                if path.is_absolute() and path.is_relative_to(original):
                    reference['file'] = local_key(root, path.relative_to(original))
    return result


def notes_path(project, work=None):
    section = production_section(project, work)
    if not section:
        raise FileNotFoundError('项目尚无视频生产资料')
    return project / local_key(project, section + '/视频修改意见.json')
