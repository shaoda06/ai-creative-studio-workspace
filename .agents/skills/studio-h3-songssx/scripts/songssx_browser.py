"""Project a recorded Songssx scene into the shared production workbench."""
import json
from pathlib import Path
import re
from urllib.parse import quote


def scene_playbacks(outputs):
    """A round may select one reviewed, timeline-aligned file per scene."""
    selected = {}
    for output in outputs:
        if 'playback' not in output:
            continue
        item = output['playback']
        if (not isinstance(item, dict) or set(item) != {'scene', 'run', 'stage'}
                or not isinstance(item['scene'], str) or not item['scene']
                or not isinstance(item['run'], str) or not re.fullmatch(r'R[0-9]{3,}', item['run'])
                or item['stage'] not in ('场次生成', '后处理')
                or item['scene'] in selected):
            raise ValueError('整场主播放须为场次登记唯一且有效的批次与阶段')
        selected[item['scene']] = output
    return selected


def playback_video(project, output):
    from backend.services.scene_postprocess import review_output
    from project_paths import project_file

    item = {key: value for key, value in output.items() if key != 'playback'}
    if 'postprocess' in item:
        key = review_output(project, item, lambda key: key).get('key')
    else:
        path = project_file(project, item['file'])
        if path.suffix.lower() != '.mp4':
            raise ValueError('整场主播放须引用完整 MP4')
        key = path.relative_to(project).as_posix() if path.is_file() else None
    stamp = (project / key).stat() if key else None
    revision = f'{stamp.st_mtime_ns}-{stamp.st_size}' if stamp else ''
    run, stage = output['playback']['run'], output['playback']['stage']
    return {'key': key or '', 'url': quote(key, safe='/-._~') + '?v=' + revision if key else '',
            'run': run, 'stage': stage, 'approved': False, 'candidateNumber': int(run[1:]),
            'fileRevision': revision, 'deliveryStatus': '已取回' if key else '未取回'}


def set_scene_playback(project, scene, output):
    if not scene.get('recorded') or not scene.get('segments'):
        raise ValueError('整场主播放须关联已登记的 Songssx 时间轴')
    scene['video'] = playback_video(project, output)
    for segment in scene['segments']:
        segment['context']['source'] = '原 Songssx 分段生成记录'


def songssx_contexts(project, data, workflow, segments, context_for, media_url=None):
    from project_paths import project_file, scope_workspace, SHARED_DIRECTORY
    from project_resources import resolve_file
    from songssx_workflow import PLANNER

    timeline = json.loads(workflow[PLANNER]['inputs']['timeline_data'])
    prepared = timeline if workflow is data['workflow'] else json.loads(data['workflow'][PLANNER]['inputs']['timeline_data'])
    media_types = (('images', 'Picture', 'image'), ('audios', 'Audio', 'audio'))
    slots = {(binding['json-path'][0], binding['json-path'][1]): binding['file'] for binding in data['uploads']
             if binding['node'] == PLANNER and binding['input'] == 'timeline_data'}
    sources = {pool: {item['id']: slots[pool, index] for index, item in enumerate(timeline.get(pool, []))}
               for pool, _, _ in media_types}
    for row, gen, prepared_gen in zip(segments, timeline['segmentConfig']['segments'], prepared['segmentConfig']['segments'], strict=True):
        context = context_for(row['p'])
        chinese = row.get('prompt_zh', '') if gen['prompt'] == prepared_gen['prompt'] else ''
        context.update(shotTimingSource='plan', prompts={'english': gen['prompt'], 'chinese': chinese},
                       references={'common': [], 'segment': []})
        for pool, label, kind in media_types:
            for index, identity in enumerate(gen.get(pool, []), 1):
                key = sources[pool][identity]
                root = project
                if key.startswith('@shared/'):
                    root = scope_workspace(project) / SHARED_DIRECTORY
                    key = key.removeprefix('@shared/')
                source = resolve_file(root, project_file(root, key, recorded=True))
                item = {'name': source.name, 'label': f'<{label} {index}>', 'kind': kind}
                if source.is_file():
                    if media_url:
                        item['url'] = media_url(source)
                    else:
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


def songssx_scene(project, entry, context_for, *, media_url=None):
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
    if 'gap_repair' in plan:
        entry['issues'].append('Songssx 补生成结果是局部片段，接回原片后才可登记为整场')
        result['recorded'] = False
        return result
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
            project, data, workflow, segments, context_for, media_url), strict=True):
        segment['context'] = context
    target, = data['outputs']
    if postprocess := entry.get('songssx_postprocess'):
        from backend.services.scene_postprocess import output_for_source

        source = resolve_file(project, project_file(project, entry.get('postprocess_source', target['path'])))
        directory, state, recorded, processed = songssx_task(project, postprocess, 'video-postprocess')
        key = postprocess
        if processed is None:
            if recorded:
                entry['issues'].append('Songssx 后处理执行检查报告缺失')
            return result
        try:
            if processed.get('record_dir') != key:
                raise ValueError('Songssx 后处理记录目录不符')
            target = output_for_source(project, processed, source)
        except ValueError:
            entry['issues'].append('Songssx 后处理须对应本场原视频及一个整场 MP4')
            return result
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
