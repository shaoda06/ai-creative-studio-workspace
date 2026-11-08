"""Automatic, resumable closeout of downloaded candidates and approved image upscales."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, unquote

from backend.services.execution_checks import write_json
from backend.services.result_summary import batch_tasks, summary, outputs as collected_outputs
from project_paths import project_file
from video_adopt import field
import project_progress
from backend.services.image_closeout import verify_browser_entries as verify_image_entries

REPORT = '结果收尾报告.json'


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def relative(base, target):
    return os.path.relpath(target, base.parent).replace('\\', '/').replace(' ', '%20')




import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/nora-drama-production/scripts'))
from drama_video_results import register as register_drama_video, apply_record_updates, business_updates, verify_video_entries


def register(store, key):
    data, state = store.rows[key]['input'], store.rows[key]['state']
    if state['status'] != 'completed' or state['collected'] != state['expected']:
        raise ValueError('只有全部成果取回的任务可以登记待审')
    if not data.task_type.startswith('video-'):
        from backend.services.image_tasks import register as register_image
        from backend.services.business_results import finish
        report_path = Path(data.record_dir) / REPORT
        return finish(data, register_image(store, key, collected_outputs(store, key), report_path), report_path, state)
    from backend.services.video_tasks import technical, register as register_technical
    if technical(data):
        from backend.services.business_results import finish
        report_path = Path(data.record_dir) / REPORT
        return finish(data, register_technical(store, key, collected_outputs(store, key), report_path), report_path, state)
    return register_drama_video(store, key)


def verify(projects, store, key, report):
    data, state = store.rows[key]['input'], store.rows[key]['state']
    name = state['project']
    if report['items'] and all(item.get('technical') or item.get('image') and not item.get('draft') for item in report['items']):
        return {'status': 'not_requested', 'verified_at': store.client.now()}
    entry = projects.get(name, synchronize=True)
    status = projects.status(name)
    if status['updating'] or status['checking'] or status['error']:
        raise ValueError('源资料已登记，网页尚未同步：' + str(status['error']))
    verify_image_entries(projects, name, [item for item in report['items'] if item.get('image') and item.get('draft')])
    verify_video_entries(projects, name, report['items'])
    return {'status': 'verified', 'verified_at': store.client.now(), 'revision': status['revision'], 'updated': status['updated'],
            'review_path': '/#/projects/' + quote(name, safe='')}






async def closeout(store, projects, batch_id, thread_id, record_updates=(), image_plans=None, image_repairs=None):
    ids, _ = batch_tasks(store, batch_id, thread_id)
    for key, plan in (image_plans or {}).items():
        if key not in ids or store.rows[key]['input'].task_type not in ('image', 'image-upscale'):
            raise ValueError('补充的图片关联必须属于本通知')
        row = store.rows[key]
        existing = row['input'].image_plan or row['state'].get('image_closeout_plan')
        if existing is not None and existing != plan:
            raise ValueError('不得改写已接受的图片收尾关联')
        from backend.services.image_closeout import validate_plan
        validate_plan(row['input'].model_copy(update={'image_plan': plan}))
        store.record(key, 'closeout', 'association_repaired', _changes={'image_closeout_plan': plan})
    for key, repair in (image_repairs or {}).items():
        from backend.services import image_closeout as images
        if key not in ids or store.rows[key]['input'].task_type not in ('image', 'image-upscale'):
            raise ValueError('登记修复必须属于本通知的图片任务')
        row = store.rows[key]
        if row['state']['status'] != 'completed' or row['state']['collected'] != row['state']['expected']:
            raise ValueError('登记修复只处理已取回的原成果')
        if row['state'].get('image_registration_repair') == repair:
            continue
        plan = row['input'].image_plan or row['state'].get('image_closeout_plan')
        if plan is None:
            raise ValueError('缺少原图片关联，先补齐真实关联')
        current = row['state'].get('image_registration_updates', images.record_updates(plan))
        updates = await asyncio.to_thread(images.repair_record_updates,
            Path(row['input'].project), [plan['draft']], current, repair, Path(row['input'].record_dir) / REPORT,
            identity={'task_id': key, 'prompt_id': row['state']['prompt_id']})
        store.record(key, 'closeout', 'records_repaired',
                     _changes={'image_registration_updates': updates, 'image_registration_repair': repair})
    return await closeout_tasks(store, projects, ids, record_updates, batch_id=batch_id)




async def closeout_tasks(store, projects, ids, record_updates=(), *, batch_id=None):
    """Internal completion worker; no Agent acknowledgement is required to register."""
    if record_updates and len({store.rows[key]['state']['project'] for key in ids}) != 1:
        raise ValueError('跨项目通知的业务更新须分项目处理，不接受混合更新')
    reports, groups = [], {}
    for key in ids:
        try:
            report = await asyncio.to_thread(register, store, key)
        except (ValueError, OSError, KeyError, TypeError) as error:
            outcome = {'status': 'registration_failed', 'error': str(error), 'report': REPORT,
                       'retryable': isinstance(error, OSError) and not isinstance(error, (PermissionError, FileNotFoundError))}
            if store.rows[key]['state'].get('closeout') != outcome:
                store.record(key, 'closeout', 'registration_failed', _changes={'closeout': outcome}, error=str(error))
            reports.append({'task_id': key, **outcome})
            continue
        groups.setdefault(store.rows[key]['state']['project'], []).append((key, report))
    for group in groups.values():
        key, owner = group[0]
        combined = {'items': [item for _, report in group for item in report['items']]}
        journal = owner.get('record_updates', {})
        fingerprint = digest(json.dumps(record_updates, ensure_ascii=False, sort_keys=True)) if record_updates else journal.get('fingerprint')
        if journal.get('status') != 'applying' and all(
                store.rows[task]['state'].get('closeout', {}).get('status') == 'completed'
                and (not record_updates or store.rows[task]['state']['closeout'].get('record_updates') == fingerprint)
                and (all(item.get('image') or item.get('technical') for item in report['items'])
                     or 'business_sync' in store.rows[task]['state']['closeout'])
                for task, report in group):
            reports.extend({**report, 'browser': store.rows[task]['state']['closeout']['browser'], 'reused': True}
                           for task, report in group)
            continue
        try:
            if journal.get('status') == 'completed' and 'business_sync' not in owner and any(
                    not item.get('image') and not item.get('technical') for item in combined['items']):
                owner['business_sync'] = {'status': 'updated', 'needs_attention': False,
                    'paths': sorted({item['path'] for item in journal['updates']}), 'next_action': None}
            if not record_updates and not journal and 'business_sync' not in owner and any(
                    not item.get('image') and not item.get('technical') for item in combined['items']):
                automatic, owner['business_sync'] = await asyncio.to_thread(business_updates, store, group)
                if automatic:
                    fingerprint = await asyncio.to_thread(apply_record_updates, store, key, automatic,
                        {item['episode'] for item in combined['items'] if not item.get('image') and not item.get('technical')}, owner)
                else:
                    write_json(Path(store.rows[key]['input'].record_dir) / REPORT, owner)
            if record_updates or journal.get('status') == 'applying':
                fingerprint = await asyncio.to_thread(apply_record_updates, store, key, record_updates,
                                        {item['episode'] for item in combined['items'] if not item.get('image') and not item.get('technical')}, owner)
                if record_updates and any(not item.get('image') and not item.get('technical') for item in combined['items']):
                    owner['business_sync'] = {'status': 'updated', 'needs_attention': False,
                        'paths': sorted({item['path'] for item in record_updates}), 'next_action': None}
                    write_json(Path(store.rows[key]['input'].record_dir) / REPORT, owner)
        except (ValueError, OSError, KeyError, TypeError) as error:
            for task, report in group:
                outcome = {'status': 'registration_failed', 'report': REPORT, 'error': str(error)}
                if store.rows[task]['state'].get('closeout') != outcome:
                    store.record(task, 'closeout', 'registration_failed', _changes={'closeout': outcome}, error=str(error))
                reports.append({**report, 'status': 'registration_failed', 'error': str(error)})
            continue
        try:
            browser = await asyncio.to_thread(verify, projects, store, key, combined)
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            for task, report in group:
                outcome = {'status': 'browser_pending', 'report': REPORT, 'error': str(error)}
                if store.rows[task]['state'].get('closeout') != outcome:
                    store.record(task, 'closeout', 'browser_pending', _changes={'closeout': outcome}, error=str(error))
                reports.append({**report, 'browser': {'status': 'pending', 'error': str(error)}})
            continue
        for task, report in group:
            outcome = {'status': 'completed', 'report': REPORT, 'browser': browser, 'record_updates': fingerprint}
            if 'business_sync' in report and report['business_sync'].get('status') == 'updated':
                outcome['business_sync'] = report['business_sync']
            elif not any(item.get('image') for item in report['items']) and 'business_sync' in owner:
                report['business_sync'] = outcome['business_sync'] = owner['business_sync']
                write_json(Path(store.rows[task]['input'].record_dir) / REPORT, report)
            if any(item.get('image') for item in report['items']):
                outcome['display_outputs'] = report['items']
            else:
                outcome['video_outputs'] = report['items']
            store.record(task, 'closeout', 'completed', _changes={'closeout': outcome}, notification_id=batch_id, browser=browser)
            reports.append({**report, 'browser': browser})
    store.refresh_reports(ids)
    for key in ids:
        store.wake_group(key)
    return {'notification_id': batch_id, 'results': reports, 'user_message_ready': bool(reports) and all(
        item.get('browser', {}).get('status') in ('verified', 'not_requested') for item in reports)}
