"""Read-only H3 request projection for shared review UI; never submit or adopt."""
import html
import json
from pathlib import Path
import re
import project_resources as resources


def empty_context(issue):
    return {'scriptHtml': '', 'shots': [], 'prompts': {'english': '', 'chinese': ''},
            'references': {'common': [], 'segment': []}, 'issues': [issue] if issue else []}


def request_context(project, task, index, request, api, sources, bindings, *, resolve_key, file_link):
    source_checks = {resolve_key(project, key, task['project']): (key, stamp) for key, stamp in sources.items()}
    workflow = request['prompt']
    director = next(((node, value['inputs']) for node, value in workflow.items()
                     if value['class_type'] == 'MiniMaxH3Director'), None)
    if not director:
        return empty_context('本次技术处理没有H3提示词；未找到可追溯的生成来源。')
    node, inputs = director
    timeline = json.loads(inputs['timeline_data'])
    group = timeline['segments'][index]
    common = timeline['global'] if timeline['global'].get('commonEnabled') else {}
    prompt = '\n\n'.join(text.replace('\\n', '\n').strip() for text in
                         (common.get('prompt', ''), group.get('prompt', '')) if text.strip())
    result = empty_context('执行记录未关联分镜快照；这里展示当次实际提示词中的镜头描述。')
    result['prompts']['english'] = prompt
    # Only recorded shot times enable alignment. Never guess timings from prose.
    body = re.split(r'(?m)^detailed_description:\s*', prompt)[-1]
    body = re.split(r'(?m)^(?:overall_soundscape|non_diegetic_music):', body)[0]
    for match in re.finditer(r'\[Shot (\d+)\](.*?)(?=\[Shot \d+\]|\Z)', body, re.S):
        text = match[2].strip()
        timing = re.search(r'(?:^|\n)\s*(?:time|timing):\s*(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)', text, re.I)
        duration = float(timing[2]) - float(timing[1]) if timing else None
        rendered = '<h4>SH' + match[1].zfill(3) + '</h4><p>' + html.escape(text).replace('\n', '<br>') + '</p>'
        shot = {'id': 'SH' + match[1].zfill(3), 'duration': duration if duration and duration > 0 else None, 'html': rendered}
        if shot['duration'] is not None:
            shot['start'] = float(timing[1])
        result['shots'].append(shot)
    if result['shots'] and all(shot['duration'] is not None for shot in result['shots']):
        result['shotTimingSource'] = 'recorded'
    result['scriptHtml'] = ''.join(shot['html'] for shot in result['shots'])
    for upload in task.get('uploads', []):
        slot = upload.get('json-path', [])
        if upload.get('node') != node or upload.get('input') != 'timeline_data' or not slot or slot[0] not in ('global', 'segments'):
            continue
        reference = timeline
        for field in slot:
            reference = reference[field]
        key = resolve_key(project, upload['file'], task['project'])
        bindings[(slot[-1], reference)] = (key, source_checks.get(key))
    for group_name, values in (('common', common), ('segment', group)):
        refs = [(field, item) for field, collection in (('imageFile', 'refs'), ('videoFile', 'refVideos'), ('audioFile', 'refAudios'))
                for item in values.get(collection, [])]
        refs += [('imageFile', values[field]) for field in ('startImage', 'endImage', 'genImage') if (values.get(field) or {}).get('imageFile')]
        if (values.get('referenceVideo') or {}).get('videoFile'):
            refs.append(('videoFile', values['referenceVideo']))
        for field, reference in refs:
            remote = reference.get(field)
            if not remote:
                continue
            kind = {'imageFile': 'image', 'videoFile': 'video', 'audioFile': 'audio'}[field]
            key, checked = bindings.get((field, remote), (None, None))
            label = {'image': 'Picture', 'video': 'Video', 'audio': 'Audio'}[kind] + ' ' + str(reference.get('index', 0) + 1)
            material = {'name': Path(key or remote).name, 'kind': kind, 'label': label}
            if key and (project / key).is_file():
                info = (project / key).stat()
                if checked is not None and checked[1] != [info.st_size, info.st_mtime_ns] and not resources.matches_recorded_stamp(project, checked[0], checked[1]):
                    material['missing'] = True
                    result['issues'].append('参考原文件已在执行后变化，未将当前文件冒充当次输入：' + key)
                else:
                    material['url'] = file_link(api, key)
            else:
                material['missing'] = True
                result['issues'].append('该次参考素材未关联本地原文件或文件已缺失：' + material['name'])
            result['references'][group_name].append(material)
    return result


