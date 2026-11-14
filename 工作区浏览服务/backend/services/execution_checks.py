"""Tool-owned local preparation report. No remote capability query or generation POST."""
import json
import re
import tempfile
from pathlib import Path

from project_paths import input_file, input_key, input_reference, project_file, recorded_paths, PreparationPaths

from backend.services.video_tasks import business as business_video

import sys
_SKILLS = Path(__file__).resolve().parents[3] / '.agents/skills'
for _name in ('studio-h3', 'studio-h3-aimixer', 'studio-h3-songssx', 'nora-drama-production', 'nora-serial-drama', 'studio-workspace-browser'):
    sys.path.insert(0, str(_SKILLS / _name / 'scripts'))
from h3_inputs import director_checks
import songssx_workflow
from drama_execution_checks import (context_checks, storyboard_index_checks, content_checks,
                                    read_mapping as read_business_mapping, basis_fields, associated_sources, check_episode_composition)
from drama_execution_checks import check_existing_video_identity as check_drama_identity


def check_existing_video_identity(data, mapping):
    if business_video(data):
        return check_drama_identity(data, mapping)


from prepared_documents import write_json as write_document_json
import execution_records as recordio


def write_json(path, value):
    if (Path(path).parent / recordio.ARCHIVE).is_file() and Path(path).name in (REPORT, '结果收尾报告.json'):
        recordio.write(path, value, compact=True)
    else:
        write_document_json(path, value)

def read_mapping(data):
    from backend.services.video_tasks import technical
    if data.task_type.startswith('video-') and technical(data):
        return {}
    return read_business_mapping(data)


REPORT = '执行检查报告.json'




def basis(store, data, mapping=None):
    payload = store.portable_input(data)
    if data.record_format == 'legacy':
        payload.pop('record_format', None)
    for name in ('image_plan', 'video_plan'):
        if payload.get(name) is None:
            payload.pop(name, None)  # Existing reports have no newer media associations.
    for name in ('desktop', 'thread_id', 'source_session_name', 'timeout', 'start_paused',
                 'image_batch_id', 'image_batch_size'):
        payload.pop(name, None)
    if mapping is None:
        mapping = read_mapping(data)
    if mapping:
        payload.update(basis_fields(store, data, mapping))
    return payload


def _file_stamp(path, observed):
    if path not in observed:
        current = path.stat()
        observed[path] = (current.st_size, current.st_mtime_ns)
    return observed[path]


def sources(data, extra=(), mapping=None, *, observed=None, composition=None):
    observed = {} if observed is None else observed
    files = {Path(item['file']) for item in data.uploads}
    files.update(Path(path) for path in extra)
    record = Path(data.record_dir)
    files.update(record.glob('*.api.json'))
    files.update(record.glob('*.workflow.json'))
    if mapping is None:
        mapping = read_mapping(data)
    files.update(associated_sources(data, mapping, composition))
    return {input_key(data.project, path): list(_file_stamp(path, observed)) for path in sorted(files)}


def read_report(data):
    path = Path(data.record_dir) / REPORT
    if not recordio.exists(path):
        return None
    report = recordio.read(path)
    if not isinstance(report, dict) or 'prepared_input' not in report:
        raise ValueError('执行检查报告位置已有其他资料；不覆盖，请核对目录')
    return report


def write_report(data, report):
    path = Path(data.record_dir) / REPORT
    write_json(path, report)


def check_prepared(store, data, *, bound=False, transferred=False, legacy=False, require_scene_round=True, require_content_review=True, file_stamps=None):
    observed = {}
    report = read_report(data)
    if report is None:
        if legacy:
            return None
        raise ValueError('新任务必须先通过准备检查；请使用--prepare-only完成准备，不会在开工时补查')
    expected, actual = report['prepared_input'].copy(), basis(store, data)
    import project_resources as resources
    if resources.enabled(data.project):
        expected = recorded_paths(data.project, expected, relative=True)
    if not require_content_review and 'content_review' not in expected.get('mapping', {}):
        actual.get('mapping', {}).pop('content_review', None)
    if 'title' not in expected:  # Reports made before title became a preparation field.
        actual.pop('title', None)
    if transferred:
        expected.pop('url', None)
        actual.pop('url', None)
    if not report['ok'] or expected != actual:
        raise ValueError('准备资料已变化或检查未通过；请在准备阶段重新调用检查，不会边提交边修改')
    if not legacy and data.task_type == songssx_workflow.TASK_TYPE:
        songssx_workflow.validate(data.workflow, data.video_plan, data.outputs, data.uploads)
    if not legacy and require_scene_round and business_video(data) and 'scene_composition' not in expected:
        raise ValueError('新视频任务必须先关联场次修改轮次；请使用--prepare-only补齐准备，旧登记任务仍按原记录恢复')
    if not legacy and not report.get('new_task_ready'):
        raise ValueError('新任务准备报告尚未覆盖完整登记要求；请使用--prepare-only补齐准备，不会在开工时补查')
    if not legacy:
        check_existing_video_identity(data, actual.get('mapping'))
    if not legacy and require_content_review and needs_content_review(data):
        content = report.get('content_checks', {})
        if content.get('version') != 1 or content.get('ok') is not True:
            raise ValueError('新H3任务缺少本版内容核对及文本检查；请使用--prepare-only补齐，不上传或提交')
    for name, stamp in report['sources'].items():
        if bound and name.endswith(('.api.json', '.workflow.json')):
            continue  # The upload binder owns and validates these actual path changes.
        path = input_file(data.project, name)
        try:
            current = _file_stamp(path, observed)
        except FileNotFoundError:
            raise ValueError('准备资料已变化：' + name + '；请返回准备阶段') from None
        if list(current) != stamp and not resources.matches_recorded_stamp(data.project, name, stamp):
            raise ValueError('准备资料已变化：' + name + '；请返回准备阶段')
    if business_video(data) and 'context_sources' not in report:
        if not legacy:
            raise ValueError('新任务准备报告缺少资料关联检查；请使用--prepare-only补齐准备')
        try:
            extra = context_checks(store, data, segment_plan_checked=data.segment_plan is not None)
            added_sources = {input_key(data.project, path): list(_file_stamp(path, observed))
                             for path in map(Path, extra)}
        except (ValueError, OSError, KeyError, IndexError, TypeError, store.client.ClientError) as error:
            report.update(ok=False, error='旧报告缺项检查失败：' + str(error), context_checked_during='execution')
            write_report(data, report)
            raise ValueError(report['error']) from error
        report['context_sources'] = extra
        report['context_checked_during'] = 'execution'
        report['sources'].update(added_sources)
        write_report(data, report)
    if file_stamps is not None:
        file_stamps.update(observed)
    return report




def fixed_input_checks(store, data):
    client = store.client
    if not data.title.strip():
        raise ValueError('任务标题不能为空')
    for item in data.uploads:
        required = {'file', 'node', 'input', 'subfolder', 'response-name'}
        if not required.issubset(item) or set(item) - required - {'json-path', 'resource'} or not all(isinstance(item[name], str) for name in required):
            raise ValueError('上传映射字段不完整或类型不正确')
        if 'resource' in item:
            import project_resources
            ref = input_reference(data.project, item['file'])
            if ref is None or item['resource'] != {key: ref[key] for key in ('resource_id', 'version')}:
                raise ValueError('上传资源版本与实际输入文件不符')
        if 'json-path' in item and (not isinstance(item['json-path'], list) or not item['json-path']
                                   or any(type(part) not in (str, int) for part in item['json-path'])):
            raise ValueError('JSON素材绑定必须提供字段路径数组')
    names = [data.attempt_name, data.request_name, data.response_name, data.history_name,
             '后台任务状态.json', '后台过程记录.json']
    names += [output.response_name for output in data.outputs]
    names += [item['response-name'] for item in data.uploads]
    if data.segment_plan:
        names += [item.response_name for item in data.segment_plan.targets]
    elif not data.outputs:
        raise ValueError('必须登记预期成果保存映射')
    for name in names:
        client.remote_path(name, filename=True)
    if len(names) != len(set(names)):
        raise ValueError('证据文件名不能重复')
    if recordio.ARCHIVE in names:
        raise ValueError('证据文件名不能占用执行档案.json')
    if '执行检查报告.json' in names:
        raise ValueError('证据文件名不能占用执行检查报告.json')
    for folder in {item['subfolder'] for item in data.uploads}:
        client.remote_path(folder)
    for source in {Path(item['file']) for item in data.uploads}:
        client.remote_path(source.name, filename=True)
        if '"' in source.name:
            raise client.ClientError('invalid_filename', 'Upload filename cannot contain a quote')


def check_new_targets(data):
    if data.segment_plan and not data.segment_plan.targets:
        raise ValueError('新导演台任务必须显式提供每段本机成果保存路径')




def fixed_checks(store, data, *, mapping=None, legacy=False):
    from backend.services.director_uploads import pairs
    from backend.services import comfy_segments as segments
    fixed_input_checks(store, data)
    from backend.services.business_results import validate as validate_business_result
    validate_business_result(data)
    if data.task_type.startswith('video-'):
        from backend.services.video_tasks import technical
        technical(data)
    if data.image_plan is not None:
        from backend.services.image_tasks import validate_plan
        validate_plan(data)
    path_scope = PreparationPaths.from_resolved(data.project,
                        [data.record_dir, *(item['file'] for item in data.uploads)])
    if not legacy:
        pairs.validate_rtx_inputs(data.workflow)
        check_new_targets(data)
    store.client.validate_workflow(data.workflow)
    if not data.segment_plan and any(node['class_type'] in ('MiniMaxH3Director', 'MiniMaxH3ReferenceToVideo') for node in data.workflow.values()):
        segments.validate_h3_stage(data.task_type)
    targets = [Path(output.path) for output in data.outputs]
    if len(targets) != len(set(targets)):
        raise ValueError('成果保存路径不能重复')
    selectors = [(out.node_id, out.output_key, out.index) for out in data.outputs]
    if any(output.node_id not in data.workflow for output in data.outputs):
        raise ValueError('预期输出节点不在工作流中')
    if len(selectors) != len(set(selectors)):
        raise ValueError('输出身份不能重复')
    documents, bindings = {}, []
    for item in data.uploads:
        if item['node'] not in data.workflow or item['input'] not in data.workflow[item['node']]['inputs']:
            raise ValueError('上传映射必须绑定已有输入')
        if 'json-path' in item:
            field = (item['node'], item['input'])
            if field not in documents:
                documents[field] = json.loads(data.workflow[field[0]]['inputs'][field[1]])
            value = documents[field]
            try:
                for part in item['json-path']:
                    value = value[part]
            except (KeyError, IndexError, TypeError) as error:
                raise ValueError('素材JSON字段路径不匹配：' + str(item['json-path'])) from error
        else:
            value = data.workflow[item['node']]['inputs'][item['input']]
        bindings.append((item, value))
    timelines = {id(node): (documents[(key, 'timeline_data')] if (key, 'timeline_data') in documents
                 else json.loads(node['inputs']['timeline_data'])) for key, node in data.workflow.items()
                 if node['class_type'] == 'MiniMaxH3Director'}
    native_segments = [node for node in data.workflow.values() if node['class_type'] == 'MiniMaxH3Director'
        and timelines[id(node)].get('output', {}).get('exportMode') == 'segments']
    if native_segments and not data.segment_plan:
        raise ValueError('原生H3分段任务必须登记segment-plan以对应最终成果')
    segment_context = None
    if data.segment_plan:
        try:
            segment_context = segments.validate(data, mapping=mapping, timelines=timelines, path_scope=path_scope)
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError('分段计划或输入映射字段不完整：' + str(error)) from error
        if data.outputs:
            raise ValueError('原生分段任务使用segment-plan，不混用末段保存节点作为全组输出')
    plan = data.video_plan or {}
    if data.task_type == songssx_workflow.TASK_TYPE:
        if (plan.get('workflow_id') != songssx_workflow.WORKFLOW or plan.get('adapter') != 'technical'
                or plan.get('metadata') != 'receipt' or data.segment_plan is not None):
            raise ValueError('场次生成须使用已登记的 Songssx 取回计划')
        songssx_workflow.validate(data.workflow, plan, data.outputs, data.uploads)
    elif plan.get('workflow_id') or any(node['class_type'] == 'MiniMaxH3TimelinePlanner' for node in data.workflow.values()):
        raise ValueError('Songssx 时间线须使用场次生成任务入口')
    result = {'segments': director_checks(data.workflow, timelines)}
    if business_video(data):
        result['context_sources'] = context_checks(store, data, mapping=mapping, bindings=bindings,
                                                  timelines=timelines, segment_context=segment_context, path_scope=path_scope)
    return result




def needs_content_review(data):
    return business_video(data) and data.task_type in ('video-first-pass', 'video-second-pass') and any(
        node['class_type'] == 'MiniMaxH3Director' for node in data.workflow.values())






def prepare_report(store, data, *, at_execution=False, previous=...):
    if data.record_format == 'compact':
        recordio.initialize(data.record_dir)
    """Fixed checks, including legacy execution fallback; never uploads or submits generation."""
    if previous is ...:
        previous = read_report(data)
    report = {'ok': False, 'checked_at': store.client.now(), 'prepared_input': {}, 'sources': {},
              'checked_during': 'execution' if at_execution else 'preparation'}
    try:
        mapping = read_mapping(data)
        report['prepared_input'] = basis(store, data, mapping)
        if not at_execution:
            check_existing_video_identity(data, mapping)
        if not at_execution and business_video(data):
            if 'scene_composition' not in report['prepared_input']:
                check_new_targets(data)
            check_episode_composition(data, report['prepared_input'])
        composition = report['prepared_input'].get('scene_composition')
        expected = previous['prepared_input'].copy() if previous else {}
        if previous and 'title' not in expected:
            expected['title'] = data.title
        requires_content = not at_execution and needs_content_review(data)
        requires_index = not at_execution and business_video(data)
        content_current = (not requires_content or previous is not None
                           and previous.get('content_checks', {}).get('version') == 1
                           and previous['content_checks'].get('ok') is True)
        if previous and previous['ok'] and expected == report['prepared_input']:
            observed = {}
            index_files = previous.get('storyboard_index', {}).get('files', [])
            report['sources'] = sources(data, previous.get('context_sources', []) + previous.get('content_checks', {}).get('sources', []) + index_files, mapping, observed=observed, composition=composition)
            if previous['sources'] == report['sources']:
                if not at_execution and data.task_type == songssx_workflow.TASK_TYPE:
                    songssx_workflow.validate(data.workflow, data.video_plan, data.outputs, data.uploads)
                    if 'business_result' in data.video_plan:
                        from backend.services.business_results import validate as validate_business_result
                        validate_business_result(data)
                report.update(previous)
                changed = False
                if not content_current:
                    content_checks(data, mapping, report)
                    report['sources'] = sources(data, previous.get('context_sources', []) + report['content_checks']['sources'], mapping, observed=observed, composition=composition)
                    changed = True
                if requires_index and not previous.get('storyboard_index', {}).get('ok'):
                    report['storyboard_index'] = storyboard_index_checks(data, mapping)
                    changed = True
                if not at_execution and not previous.get('new_task_ready'):
                    check_new_targets(data)
                    report['new_task_ready'] = True
                    changed = True
                if business_video(data) and 'context_sources' not in previous:
                    extra = context_checks(store, data, mapping=mapping, segment_plan_checked=data.segment_plan is not None)
                    report.update(context_sources=extra, context_checked_during='preparation')
                    report['sources'] = sources(data, extra + report.get('content_checks', {}).get('sources', []), mapping, observed=observed, composition=composition)
                    changed = True
                if changed:
                    report['sources'] = sources(data, report.get('context_sources', []) + report.get('content_checks', {}).get('sources', []) + report.get('storyboard_index', {}).get('files', []), mapping, observed=observed, composition=composition)
                    write_report(data, report)
                return {'prepared': True, 'report': REPORT, 'reused': True,
                        'checks': {'segments': previous['segments']}}
        if requires_index:
            report['storyboard_index'] = storyboard_index_checks(data, mapping)
        if requires_content:
            content_checks(data, mapping, report)
        report.update(fixed_checks(store, data, mapping=mapping, legacy=at_execution))
        if business_video(data):
            report.setdefault('context_sources', [])
        report['sources'] = sources(data, report.get('context_sources', []) + report.get('content_checks', {}).get('sources', []) + report.get('storyboard_index', {}).get('files', []), mapping, composition=composition)
        report['ok'] = True
        if not at_execution:
            report['new_task_ready'] = True
    except (ValueError, OSError, store.client.ClientError) as error:
        report['ok'] = False
        report['error'] = str(error)
        write_report(data, report)
        raise
    except (KeyError, IndexError, TypeError) as error:
        report['ok'] = False
        report['error'] = '本地准备字段不完整或类型不正确：' + str(error)
        write_report(data, report)
        raise ValueError(report['error']) from error
    write_report(data, report)
    result = {'prepared': True, 'report': REPORT, 'checks': {'segments': report['segments']}}
    if at_execution:
        result['sources'] = report['sources']
    return result
