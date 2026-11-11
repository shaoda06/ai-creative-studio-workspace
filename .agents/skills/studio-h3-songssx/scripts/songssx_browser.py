"""Project a recorded Songssx scene into the shared production workbench."""
import json
from pathlib import Path
from urllib.parse import quote


def songssx_contexts(project, data, workflow, segments, context_for):
    from project_paths import project_file, scope_workspace, SHARED_DIRECTORY
    from project_resources import resolve_file
    from songssx_workflow import PLANNER

    timeline = json.loads(workflow[PLANNER]['inputs']['timeline_data'])
    prepared = timeline if workflow is data['workflow'] else json.loads(data['workflow'][PLANNER]['inputs']['timeline_data'])
    sources = {binding['json-path'][1]: binding['file'] for binding in data['uploads']
               if binding['node'] == PLANNER and binding['input'] == 'timeline_data'}
    images = {item['id']: sources[index] for index, item in enumerate(timeline['images'])}
    for row, gen, prepared_gen in zip(segments, timeline['segmentConfig']['segments'], prepared['segmentConfig']['segments'], strict=True):
        context = context_for(row['p'])
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


def songssx_task(project, key, task_type):
    from execution_records import exists, read
    from project_paths import project_file
    directory = project_file(project, key)
    report = directory / '执行检查报告.json'
    state_file = directory / '后台任务状态.json'
    state = read(state_file) if exists(state_file) else {}
    recorded = state.get('task_type') == task_type and state.get('record_dir') == key and bool(state.get('id'))
    return directory, state, recorded, read(report)['prepared_input'] if exists(report) else None


def songssx_scene(project, entry, context_for):
    from execution_records import exists, read
    from project_paths import project_file
    from project_resources import resolve_file
    from songssx_workflow import FPS, TASK_TYPE, WORKFLOW

    key = entry['songssx_execution']
    directory, state, recorded, data = songssx_task(project, key, TASK_TYPE)
    result = {'recorded': recorded, 'segments': []}
    if data is None:
        if recorded:
            entry['issues'].append('Songssx 执行检查报告缺失')
        return result
    plan = data.get('video_plan', {})
    segments = plan.get('segments', [])
    if (data.get('task_type') != TASK_TYPE or plan.get('workflow_id') != WORKFLOW
            or data.get('record_dir') != key
            or [(row['p'], row['planned_seconds']) for row in segments]
            != [(segment['id'], segment['duration']) for segment in entry['segments']]):
        entry['issues'].append('Songssx 执行记录与本轮场次或分段不匹配')
        result['recorded'] = False
        return result
    result['segments'] = [{'id': row['p'], 'gen': row['gen'], 'start': row['output_frames'][0] / FPS,
                           'end': row['output_frames'][1] / FPS} for row in segments]
    request = directory / data.get('request_name', '请求.json')
    workflow = read(request)['prompt'] if exists(request) else data['workflow']
    for segment, context in zip(result['segments'], songssx_contexts(
            project, data, workflow, segments, context_for), strict=True):
        segment['context'] = context
    target, = data['outputs']
    if postprocess := entry.get('songssx_postprocess'):
        source = resolve_file(project, project_file(project, target['path']))
        directory, state, recorded, processed = songssx_task(project, postprocess, 'video-postprocess')
        key = postprocess
        if processed is None:
            if recorded:
                entry['issues'].append('Songssx 后处理执行检查报告缺失')
            return result
        if (processed.get('task_type') != 'video-postprocess' or processed.get('record_dir') != key
                or len(processed['outputs']) != 1 or Path(processed['outputs'][0]['path']).suffix.lower() != '.mp4'
                or {resolve_file(project, project_file(project, upload['file'])) for upload in processed['uploads']} != {source}):
            entry['issues'].append('Songssx 后处理须对应本场原视频及一个整场 MP4')
            return result
        target, = processed['outputs']
    actual = resolve_file(project, project_file(project, target['path']))
    relative = actual.relative_to(project).as_posix()
    stage = entry['segments'][0]['stage']
    run = entry['segments'][0]['run']
    saved = recorded and exists(directory / target['response_name']) and actual.is_file()
    stamp = actual.stat() if saved else None
    revision = f'{stamp.st_mtime_ns}-{stamp.st_size}' if stamp else ''
    result['video'] = {
        'key': relative, 'url': quote(relative, safe='/-._~') + '?v=' + revision if saved else '',
        'run': run, 'stage': stage, 'approved': False, 'candidateNumber': int(run[1:]),
        'fileRevision': revision,
        'taskStatus': state.get('status', ''), 'deliveryStatus': '已取回' if saved else '',
        'taskStateUrl': quote((Path(key) / '后台任务状态.json').as_posix(), safe='/-._~') if recorded else '',
        'checkedAt': state.get('updated_at', ''),
    }
    return result
