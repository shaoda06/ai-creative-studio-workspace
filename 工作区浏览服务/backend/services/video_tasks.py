"""Explicit technical video adapter; no serial-drama documents or adoption."""
import json
from pathlib import Path
import execution_records as recordio
from project_paths import project_file


def technical(data):
    adapter = (data.video_plan or {}).get('adapter', 'serial-drama')
    if adapter not in ('serial-drama', 'technical'):
        raise ValueError('未登记的视频结果适配：' + adapter)
    return adapter == 'technical'


def business(data):
    return data.task_type.startswith('video-') and not technical(data)


def register(store, key, outputs, report_file):
    from backend.services.execution_checks import write_json
    from backend.services.video_records import probe
    data, state = store.rows[key]['input'], store.rows[key]['state']
    if data.video_plan.get('metadata') != 'ffprobe':
        raise ValueError('视频技术任务须使用ffprobe媒体核对')
    if recordio.exists(report_file):
        report = recordio.read(report_file)
        if report['task_id'] != key or report['prompt_id'] != state['prompt_id']:
            raise ValueError('视频技术报告不属于原任务')
        for item in report['items']:
            current = project_file(data.project, item['path']).stat()
            if [current.st_size, current.st_mtime_ns] != item['metadata']['stamp']:
                raise ValueError('已核对的视频技术结果发生变化：' + item['path'])
        return report
    if len(outputs) != state['expected']:
        raise ValueError('视频技术取回摘要缺项')
    items = []
    for output in outputs:
        path = project_file(data.project, output['path'])
        receipt = project_file(data.project, output['receipt'])
        if not recordio.exists(receipt):
            raise FileNotFoundError(receipt)
        items.append(dict(identity=output.get('identity') or path.name, path=path.relative_to(Path(data.project)).as_posix(),
                          receipt=receipt.relative_to(Path(data.project)).as_posix(),
                          technical=True, metadata=probe(path)))
    report = dict(task_id=key, prompt_id=state['prompt_id'], adapter='technical', status='registered',
                  recorded_at=store.client.now(), items=items, business_sync={'status': 'not_requested'})
    write_json(report_file, report)
    return report
