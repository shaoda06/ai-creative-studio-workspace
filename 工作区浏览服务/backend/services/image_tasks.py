"""Explicit image result adapters; technical jobs do not require serial-drama records."""
import json
from pathlib import Path
import execution_records as recordio
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-image-processing/scripts'))
from image_files import inspect_remote
from project_paths import project_file
from backend.services.execution_checks import write_json


def technical(plan):
    adapter = (plan or {}).get('adapter', 'serial-drama')
    if adapter not in ('serial-drama', 'technical'):
        raise ValueError('未登记的图片结果适配：' + adapter)
    return adapter == 'technical'


def validate_names(root, plan, *, required=False):
    if not technical(plan):
        from backend.services.image_closeout import validate_names as validate_business
        return validate_business(root, plan, required=required)
    images = plan['images']
    if not images:
        raise ValueError('图片技术任务须提供明确输出和目标尺寸')
    for item in images:
        project_file(root, item['path'])
        if any(type(item[key]) is not int or item[key] <= 0 for key in ('width', 'height')):
            raise ValueError('图片目标尺寸必须为正整数')


def validate_plan(data):
    if not technical(data.image_plan):
        from backend.services.image_closeout import validate_plan as validate_business
        return validate_business(data)
    validate_names(data.project, data.image_plan)
    planned = {project_file(data.project, item['path']): item for item in data.image_plan['images']}
    if len(planned) != len(data.image_plan['images']) or set(planned) != {Path(out.path) for out in data.outputs}:
        raise ValueError('图片技术计划与成果输出映射不符')
    return planned


def register(store, key, outputs, report_file):
    data, state = store.rows[key]['input'], store.rows[key]['state']
    if not technical(data.image_plan):
        from backend.services.image_closeout import register as register_business
        return register_business(store, key, outputs, report_file)
    if recordio.exists(report_file):
        report = recordio.read(report_file)
        if report['task_id'] != key or report['prompt_id'] != state['prompt_id']:
            raise ValueError('图片技术报告不属于原任务')
        for item in report['checks']:
            current = recordio.stamp(project_file(data.project, item['path']))
            if list(current) != item['stamp']:
                raise ValueError('已核对的图片技术结果发生变化：' + item['path'])
        return report
    planned = validate_plan(data)
    if len(outputs) != len(planned):
        raise ValueError('图片取回摘要缺项')
    inspected, checked, _, _ = inspect_remote(data, state, outputs, planned, align_rtx=True)
    checks = []
    for path in checked:
        current = recordio.stamp(path)
        checks.append(dict(path=path.relative_to(data.project).as_posix(),
                           stamp=list(current)))
    report = dict(task_id=key, prompt_id=state['prompt_id'], status='registered',
                  adapter='technical', recorded_at=store.client.now(), items=inspected, checks=checks)
    write_json(report_file, report)
    return report
