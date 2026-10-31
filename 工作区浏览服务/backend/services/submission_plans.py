"""Build submission artifacts from one project task list; prepare all before queueing any."""
from copy import deepcopy
import asyncio
import json
from pathlib import Path
import re
from urllib.parse import unquote

from project_paths import project_file
from workflow_paths import workflow_file, workflow_root
from backend.services.director_uploads import pairs
from backend.services.execution_checks import write_json
from backend.services import image_closeout as images
from backend.services.prepared_documents import Documents, publish
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / ".agents/skills/nora-drama-images/scripts"))
from drama_image_plans import (SEEDS, SIZES, reference, choose_seed, generation_record,
                               adoption_updates, build_image, image_workflow, remote_prefix)
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/nora-h3/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/nora-drama-production/scripts'))
from h3_workflow import prepare_technical, widget, disconnect
from drama_video_plans import build_video as build_drama_video


def build_video(root, spec, documents):
    adapter = spec.get('video_plan', {}).get('adapter', 'serial-drama')
    if adapter == 'technical':
        return prepare_technical(root, spec, documents)
    if adapter != 'serial-drama':
        raise ValueError('未登记的视频计划适配：' + adapter)
    return build_drama_video(root, spec, documents)





def submission_response(store, journal, *, reused=False):
    accepted = journal['accepted']
    ids = [item['local_task_id'] for item in accepted if item.get('local_task_id')]
    group_id = store.rows[ids[0]]['state'].get('group_id') if ids else None
    group = store.group_status(group_id) if group_id else None
    return dict(status=('completed' if group and group['status'] == 'completed' or not group and all(item['status'] == 'completed' for item in accepted) else 'enqueued'),
                tasks=accepted, reused=reused, next_action='end-turn',
                **({'group_id': group_id, 'group': group} if group else {}))


async def execute(store, payload):
    from backend.services.comfy_tasks import TaskInput, SKILL
    root = project_file(store.workspace / 'projects', payload.project)
    if root.parent != store.workspace / 'projects':
        raise ValueError('任务清单必须属于projects中的单个项目')
    plan_file = project_file(root, payload.plan_file)
    source = json.loads(plan_file.read_text('utf-8-sig'))
    if not source['tasks']:
        raise ValueError('任务清单不能为空')
    if payload.reprepare and not payload.prepare_only:
        raise ValueError('重新装配仅用于--prepare-only，不会直接入队')
    journal_file = plan_file.with_name(plan_file.stem + '-装配结果.json')
    if getattr(payload, 'record_repairs', None) is not None:
        from backend.services import local_images
        if not payload.record_repairs:
            raise ValueError('登记修复映射不能为空，不执行原任务清单')
        if payload.prepare_only or payload.reprepare or payload.start_paused:
            raise ValueError('登记修复不能与准备或暂停提交混用')
        journal = json.loads(journal_file.read_text('utf-8-sig'))
        if journal['thread_id'] != payload.thread_id or journal['source'] != source:
            raise ValueError('登记修复须引用原来源及未变化的原清单')
        targets = {project_file(root, task['record_dir']): task for task in journal['tasks']}
        repairs = []
        for path, repair in payload.record_repairs.items():
            task = targets[project_file(root, path)]
            if not task.get('image_plan', {}).get('local_processing'):
                raise ValueError('此入口只接续已有本地图片成果，远端任务走通知登记修复')
            data = TaskInput(**task, url=store.remote_urls()[0], thread_id=payload.thread_id, desktop=payload.desktop)
            store.resolve_input(data)
            repairs.append((data, repair))
        results = []
        for data, repair in repairs:
            results.append(await asyncio.to_thread(local_images.repair, store, data, repair))
        return dict(status='completed', tasks=results, next_action='end-turn')
    journal = None
    documents = None
    if journal_file.exists():
        journal = json.loads(journal_file.read_text('utf-8-sig'))
        if journal['thread_id'] != payload.thread_id:
            raise ValueError('任务清单来源已改变，不能覆盖原装配记录')
        if payload.reprepare:
            if journal.get('accepted') or any(
                    row['input'].record_dir == str(project_file(root, task['record_dir']))
                    for row in store.rows.values() for task in [*journal['tasks'], *source['tasks']]
                    if 'record_dir' in task):
                raise ValueError('任务已登记，不能重装原清单；请使用原任务ID接续')
            documents = Documents(root, journal['writes'])
            archive = deepcopy(journal)
            archive['preparation_reports'] = []
            for task in journal['tasks']:
                report = project_file(root, task['record_dir']) / '执行检查报告.json'
                if report.exists():
                    archive['preparation_reports'].append(dict(record_dir=task['record_dir'],
                        report=json.loads(report.read_text('utf-8-sig'))))
            index = 1
            while journal_file.with_name(f'{journal_file.stem}-准备归档-{index:03d}.json').exists():
                index += 1
            with journal_file.with_name(f'{journal_file.stem}-准备归档-{index:03d}.json').open('x', encoding='utf-8') as stream:
                json.dump(archive, stream, ensure_ascii=False, indent=2)
            journal = None
    elif payload.reprepare:
        raise ValueError('没有原装配记录，请先按常规入口准备')
    if journal is not None:
        if journal['source'] != source:
            before, after = deepcopy(journal['source']), deepcopy(source)
            for item in [*before['tasks'], *after['tasks']]:
                item.pop('authorization', None)
            if journal.get('accepted') or any(
                    row['input'].record_dir == str(project_file(root, task['record_dir']))
                    for row in store.rows.values() for task in journal['tasks']):
                raise ValueError('任务清单内容已改变，不能覆盖原装配记录')
            if before != after:
                raise ValueError('尚未登记的任务清单内容已改变；修正后使用--prepare-only --reprepare原地重新准备')
            replacements = [(old.get('draft'), old.get('authorization', '仅准备，尚未执行授权'), new.get('authorization', '仅准备，尚未执行授权'))
                            for old, new in zip(journal['source']['tasks'], source['tasks'])]
            for update in journal['writes']:
                revised = update['new']
                for draft, old, new in replacements:
                    if update['path'] == draft:
                        revised = revised.replace('- 生成／修改授权与计数：' + old + '；', '- 生成／修改授权与计数：' + new + '；')
                if revised != update['new']:
                    update['old'], update['new'] = update['new'], revised
            journal['source'] = source
            journal['published'] = False
            write_json(journal_file, journal)
        if len(journal.get('accepted', [])) == len(journal['tasks']):
            return submission_response(store, journal, reused=True)
    else:
        documents = documents or Documents(root)
        tasks = []
        for entry in source['tasks']:
            if not payload.prepare_only and not entry.get('authorization'):
                raise ValueError('生成任务必须写明本次执行授权依据')
            spec = {**entry, 'authorization': entry.get('authorization', '仅准备，尚未执行授权'), 'submission_plan': str(plan_file)}
            task = build_image(root, SKILL, spec, documents, store.client.now()) if spec['task_type'].startswith('image') else build_video(root, spec, documents)
            tasks.append(task)
        journal = dict(source=source, thread_id=payload.thread_id, tasks=tasks, writes=documents.writes())
        write_json(journal_file, journal)
    if not payload.prepare_only and any(not entry.get('authorization') for entry in source['tasks']):
        raise ValueError('此清单仅准备，尚缺实际执行授权依据')
    local_flags = [bool(task.get('image_plan', {}).get('local_processing')) for task in journal['tasks']]
    if any(local_flags) and not all(local_flags):
        raise ValueError('同步本地规格处理与后台任务请分别提交；后台任务清单按完整任务组登记')
    accepted = journal.setdefault('accepted', [])
    while len(accepted) < len(journal['tasks']):
        task = journal['tasks'][len(accepted)]
        data = TaskInput(**task, url=store.remote_urls()[0], thread_id=payload.thread_id, desktop=payload.desktop,
                         start_paused=payload.start_paused, timeout=payload.timeout)
        store.resolve_input(data)
        if not any(row['input'].record_dir == data.record_dir for row in store.rows.values()):
            break
        result = await store.enqueue(data)
        group_id = store.rows[result['local_task_id']]['state'].get('group_id')
        if group_id:
            journal['group_id'] = group_id
        accepted.append(dict(title=data.title, task_type=data.task_type, local_task_id=result['local_task_id'],
                             status=result['status'], record_dir=data.record_dir))
        write_json(journal_file, journal)
    if not journal.get('accepted') and not journal.get('published'):
        publish(root, journal['writes'])
        journal['published'] = True
        write_json(journal_file, journal)
    prepared = []
    inputs = []
    for index, task in enumerate(journal['tasks']):
        data = TaskInput(**task, url=store.remote_urls()[0], thread_id=payload.thread_id, desktop=payload.desktop,
                         start_paused=payload.start_paused, timeout=payload.timeout)
        if index < len(accepted):
            continue
        store.resolve_input(data)
        if any(row['input'].record_dir == data.record_dir for row in store.rows.values()):
            raise ValueError('清单后项已被其他登记占用，请核对原任务，不自动补提')
        if data.image_plan and data.image_plan.get('local_processing'):
            from backend.services import local_images
            report = local_images.prepare(store, data)
        else:
            report = await store.prepare_only(data)
        prepared.append(dict(title=data.title, report=report['report']))
        inputs.append(data)
    if payload.prepare_only or payload.start_paused and any(data.image_plan and data.image_plan.get('local_processing') for data in inputs):
        return dict(status='prepared', tasks=prepared, next_action='review-content')
    if inputs and not accepted and not any(local_flags):
        result = await store.enqueue_group(inputs, source.get('group_title') or plan_file.stem)
        journal['group_id'] = result['group_id']
        journal['accepted'] = [dict(title=data.title, task_type=data.task_type,
            local_task_id=item['local_task_id'], status=item['status'], record_dir=data.record_dir)
            for data, item in zip(inputs, result['tasks'])]
        write_json(journal_file, journal)
        return submission_response(store, journal)
    # Only synchronous local processing and recovery of pre-group partial
    # submissions use this compatibility path. New background plans register above.
    for data in inputs:
        try:
            if data.image_plan and data.image_plan.get('local_processing'):
                from backend.services import local_images
                result = await asyncio.to_thread(local_images.complete, store, data)
            else:
                result = await store.enqueue(data)
        except (ValueError, OSError, store.client.ClientError) as error:
            return dict(status='partial' if accepted else 'failed', tasks=accepted, error=str(error), next_action='inspect-failure')
        accepted.append(dict(title=data.title, task_type=data.task_type, local_task_id=result['local_task_id'],
                             status=result['status'], record_dir=data.record_dir,
                             **({'provider': 'local', 'report': result['report']} if result.get('provider') == 'local' else {})))
        write_json(journal_file, journal)
    return submission_response(store, journal)
