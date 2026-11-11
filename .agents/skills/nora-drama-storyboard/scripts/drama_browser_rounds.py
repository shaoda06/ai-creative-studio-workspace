"""Project episode compositions and retain explicit legacy scene history."""
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import quote

import scene_rounds as rounds

from episode_rounds import episode_manifest_key, scene_entries, validate_episode_manifest


def songssx_contexts(project, data, workflow, segments, storyboard, storyboard_key):
    from drama_browser_generation import storyboard_context
    from project_paths import project_file, scope_workspace, SHARED_DIRECTORY
    from project_resources import resolve_file
    from songssx_workflow import PLANNER

    timeline = json.loads(workflow[PLANNER]['inputs']['timeline_data'])
    prepared = timeline if workflow is data['workflow'] else json.loads(data['workflow'][PLANNER]['inputs']['timeline_data'])
    sources = {binding['json-path'][1]: binding['file'] for binding in data['uploads']
               if binding['node'] == PLANNER and binding['input'] == 'timeline_data'}
    images = {item['id']: sources[index] for index, item in enumerate(timeline['images'])}
    for row, gen, prepared_gen in zip(segments, timeline['segmentConfig']['segments'], prepared['segmentConfig']['segments'], strict=True):
        context = (storyboard_context(storyboard, row['p'], storyboard_key) if storyboard is not None else
                   {'scriptHtml': '', 'shots': [], 'dialogues': [], 'issues': []})
        chinese = row.get('prompt_zh', '') if gen['prompt'] == prepared_gen['prompt'] else ''
        context.update(shotTimingSource='plan', prompts={'english': gen['prompt'], 'chinese': chinese},
                       references={'common': [], 'segment': []})
        for index, identity in enumerate(gen['images'], 1):
            key = images[identity]
            root = project
            if key.startswith('@shared/'):
                root = scope_workspace(project) / SHARED_DIRECTORY
                key = key.removeprefix('@shared/')
            source = resolve_file(root, project_file(root, key, recorded=True))
            item = {'name': source.name, 'label': f'<Picture {index}>', 'kind': 'image'}
            if source.is_file():
                url = quote(source.relative_to(root).as_posix(), safe='/-._~')
                item['url'] = '/api/projects/%40shared/files/' + url if root != project else url
            else:
                item['missing'] = True
                context['issues'].append('该次输入原素材缺失：' + source.name)
            context['references']['segment'].append(item)
        yield context


def songssx_scene(project, entry, storyboard, storyboard_key):
    from execution_records import exists, read
    from project_paths import project_file
    from project_resources import resolve_file
    from songssx_workflow import FPS, TASK_TYPE, WORKFLOW

    key = entry['songssx_execution']
    directory = project_file(project, key)
    report = directory / '执行检查报告.json'
    state_file = directory / '后台任务状态.json'
    state = read(state_file) if exists(state_file) else {}
    recorded = state.get('task_type') == TASK_TYPE and state.get('record_dir') == key and bool(state.get('id'))
    result = {'recorded': recorded, 'segments': []}
    if not exists(report):
        if recorded:
            entry['issues'].append('Songssx 执行检查报告缺失')
        return result
    data = read(report)['prepared_input']
    plan = data.get('video_plan', {})
    segments = plan.get('segments', [])
    if (data.get('task_type') != TASK_TYPE or plan.get('workflow_id') != WORKFLOW
            or data.get('record_dir') != key
            or [(row['p'], row['planned_seconds']) for row in segments]
            != [(segment['id'], segment['duration']) for segment in entry['segments']]):
        entry['issues'].append('Songssx 执行记录与本轮场次或分段不匹配')
        result['recorded'] = False
        return result
    target, = data['outputs']
    media = project_file(project, target['path'])
    actual = resolve_file(project, media)
    relative = actual.relative_to(project).as_posix()
    run = entry['segments'][0]['run']
    receipt = directory / target['response_name']
    saved = recorded and exists(receipt) and actual.is_file()
    stamp = actual.stat() if saved else None
    revision = f'{stamp.st_mtime_ns}-{stamp.st_size}' if stamp else ''
    result['segments'] = [{'id': row['p'], 'gen': row['gen'], 'start': row['output_frames'][0] / FPS,
                           'end': row['output_frames'][1] / FPS} for row in segments]
    request = directory / data.get('request_name', '请求.json')
    workflow = read(request)['prompt'] if exists(request) else data['workflow']
    for segment, context in zip(result['segments'], songssx_contexts(
            project, data, workflow, segments, storyboard, storyboard_key), strict=True):
        segment['context'] = context
    result['video'] = {
        'key': relative, 'url': quote(relative, safe='/-._~') + '?v=' + revision if saved else '',
        'run': run, 'stage': rounds.SCENE_GENERATION, 'approved': False, 'candidateNumber': int(run[1:]),
        'fileRevision': revision,
        'taskStatus': state.get('status', ''), 'deliveryStatus': '已取回' if saved else '',
        'taskStateUrl': quote((Path(key) / state_file.name).as_posix(), safe='/-._~') if recorded else '',
        'checkedAt': state.get('updated_at', ''),
    }
    return result


def load_episode_rounds(episode, read):
    raw = read(episode_manifest_key(episode))
    if raw is None:
        return []
    return [{'number': item['number'], 'scenes': list(item['scenes'])}
            for item in validate_episode_manifest(json.loads(raw), episode)['rounds']]

def load_scene_rounds(project, episode, scene, read):
    from backend.parsers.project import field, markdown, document_header
    from backend.parsers.generation import segment_body
    result = []
    for entry in scene_entries(project, episode, scene, read):
        item = {**entry, 'issues': []}
        record = episode_manifest_key(episode) if entry.get('episodeRound') else rounds.manifest_key(episode, scene)
        item['record'] = {'kind': 'json', 'name': Path(record).name, 'key': record, 'url': quote(record, safe='/-._~')}
        documents = {}
        for kind in ('script', 'storyboard'):
            reference = entry[kind]
            file = reference['file']
            if Path(file).is_absolute() or not (project / file).resolve().is_relative_to(project):
                raise ValueError('场次轮次文档越出项目：' + file)
            text = read(file)
            if text is None or field(text, '文档版本').rstrip('。') != reference['version']:
                item['issues'].append(('剧本' if kind == 'script' else '分镜') + '文件缺失或版本不匹配')
                item[kind] = None
                continue
            documents[kind] = text
            doc = {'title': Path(file).stem, 'html': markdown(text, file), 'url': quote(file, safe='/-._~'), **document_header(text, file)}
            item[kind] = {'kind': 'document', 'name': Path(file).stem, 'key': file, 'url': doc['url'], 'doc': doc, 'version': reference['version']}
        item['segments'] = [{**segment,
            'scriptHtml': markdown(segment_body(documents.get('storyboard', ''), segment['id']), entry['storyboard']['file']),
            'scriptUrl': quote(entry['storyboard']['file'], safe='/-._~')} for segment in entry['segments']]
        if item.get('songssx_execution'):
            item['songssx'] = songssx_scene(project, item, documents.get('storyboard'), entry['storyboard']['file'])
        result.append(item)
    return result
