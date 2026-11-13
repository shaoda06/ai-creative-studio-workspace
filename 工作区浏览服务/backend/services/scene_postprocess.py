"""Resolve a round's whole-video postprocess from its execution evidence."""
from pathlib import Path

import execution_records as records
from project_paths import project_file


def output_for_source(project, task, source):
    if task.get('task_type') != 'video-postprocess' or task.get('segment_plan'):
        raise ValueError('整场后处理须引用独立的视频后处理任务')
    outputs = task.get('outputs', [])
    uploads = {project_file(project, item['file'], recorded=True) for item in task.get('uploads', [])}
    if (len(outputs) != 1 or Path(outputs[0]['path']).suffix.lower() != '.mp4'
            or uploads != {project_file(project, source, recorded=True)}):
        raise ValueError('整场后处理须对应指定源片及一个整场 MP4')
    return outputs[0]


def review_output(project, declaration, file_url):
    if set(declaration) != {'label', 'postprocess', 'source'}:
        raise ValueError('整场后处理审阅须登记 label、postprocess 和 source')
    directory = project_file(project, declaration['postprocess'])
    result = {'kind': 'video', 'name': declaration['label']}
    check = directory / '执行检查报告.json'
    if not records.exists(check):
        return result
    task = records.read(check)['prepared_input']
    if project_file(project, task['record_dir'], recorded=True) != directory:
        raise ValueError('整场后处理执行目录与审阅登记不符')
    target = output_for_source(project, task, declaration['source'])
    path = project_file(project, target['path'], recorded=True)
    state_file = directory / '后台任务状态.json'
    state = records.read(state_file) if records.exists(state_file) else {}
    if (state.get('id') and state.get('task_type') == 'video-postprocess'
            and state.get('record_dir') and project_file(project, state['record_dir'], recorded=True) == directory
            and records.exists(directory / target['response_name']) and path.is_file()):
        relative = path.relative_to(project).as_posix()
        result.update(key=relative, url=file_url(relative))
    return result
