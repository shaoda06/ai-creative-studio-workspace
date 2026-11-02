import execution_records as recordio
"""Retrieve native H3 segments only from a completed task’s final report."""
import argparse
import asyncio
import json
from pathlib import Path, PureWindowsPath, PurePosixPath
import re

from pydantic import BaseModel, Field
from backend.services.collection_retry import failure, saved_files


class SegmentTarget(BaseModel):
    index: int = Field(ge=0)
    path: str
    response_name: str


class SegmentPlan(BaseModel):
    director_node: str
    report_node: str
    output_root: str
    targets: list[SegmentTarget] = Field(default_factory=list)


import sys
_SKILLS = Path(__file__).resolve().parents[3] / '.agents/skills'
for _name in ('nora-h3', 'nora-drama-production'):
    sys.path.insert(0, str(_SKILLS / _name / 'scripts'))
from h3_results import remote_file, export_paths, REPORT
from drama_video_segments import targets as drama_targets, validate as drama_validate





def targets(data, mapping=None, *, segment_context=None):
    from backend.services.comfy_tasks import paths
    from backend.services.video_tasks import technical
    if technical(data):
        return [dict(index=item.index, identity=f'segment-{item.index:03d}', record=Path(data.record_dir),
                     candidate=Path(item.path), response_name=item.response_name) for item in data.segment_plan.targets]
    return drama_targets(data, mapping, segment_context=segment_context)


def validate_h3_stage(task_type):
    from backend.services.comfy_tasks import client
    if task_type not in ('video-first-pass', 'video-second-pass'):
        raise client.ClientError('invalid_task_type', 'H3 generation requires a first-pass or second-pass task type')


def validate(data, *, mapping=None, timelines=None, path_scope=None):
    from backend.services.comfy_tasks import generation_context
    plan = data.segment_plan
    validate_h3_stage(data.task_type)
    from backend.services.video_tasks import technical
    if technical(data):
        director = data.workflow[plan.director_node]
        if director['class_type'] != 'MiniMaxH3Director':
            raise ValueError('分段计划必须绑定实际导演台')
        timeline = json.loads(director['inputs']['timeline_data'])
        selected = sorted(timeline['runSelection']) if timeline.get('runSelectEnabled') else list(range(len(timeline['segments'])))
        if (not selected or len(selected) != len(set(selected))
                or any(type(index) is not int or index < 0 or index >= len(timeline['segments']) for index in selected)):
            raise ValueError('技术任务运行组序无效')
        if plan.report_node not in data.workflow or [plan.director_node, 5] not in data.workflow[plan.report_node]['inputs'].values():
            raise ValueError('报告节点未连接该导演台report输出')
        if timeline['output'].get('exportMode') != 'segments':
            raise ValueError('分段取回需要原生segments导出')
        if len(plan.targets) != len(selected) or {item.index for item in plan.targets} != set(selected):
            raise ValueError('技术任务须逐一提供运行组的成果路径')
        if len({item.path for item in plan.targets}) != len(plan.targets):
            raise ValueError('分段目标路径不能重复')
        for item in plan.targets:
            if Path(item.path).exists():
                raise ValueError('技术任务成果已存在，沿原任务恢复，不重复提交')
        remote_file(plan.output_root, plan.output_root.rstrip('/\\') + '/minimax_seg_export/validation/seg_0000.mp4')
        return dict(director=director, timeline=timeline, indices=selected)

    return drama_validate(data, mapping=mapping, timelines=timelines, path_scope=path_scope)




async def finish(store, key, result):
    from backend.services.comfy_tasks import paths as project_paths
    data, state = store.rows[key]['input'], store.rows[key]['state']
    row = store.rows[key]
    if row.get('_segment_result') is not result:
        paths, row['_segment_pre_refine'] = export_paths(data, result)
        row['_segment_paths'], row['_segment_result'] = paths, result
        row['_segment_sources'] = {}
    paths = row['_segment_paths']
    pre_refine_by_index = row['_segment_pre_refine']
    output_root = state.get('collection_output_root', data.segment_plan.output_root)
    problems, collected = [], 0
    state.setdefault('segments', {})
    expected_targets = store.rows[key].get('_collection_targets')
    if expected_targets is None:
        expected_targets = store.rows[key]['_collection_targets'] = targets(data)
    verified = store.rows[key].setdefault('_collection_ok', {})
    if state['expected'] != len(expected_targets):
        store.save(key, expected=len(expected_targets))
    for target in expected_targets:
        item = state['segments'].setdefault(str(target['index']), {
            'identity': target['identity'], 'index': target['index'], 'check': '未取回', 'error': None})
        try:
            sources = row['_segment_sources']
            index = target['index']
            pre_refine = pre_refine_by_index[index]
            if index not in sources:
                try:
                    if index not in paths:
                        raise ValueError('最终报告缺少该段的保存路径')
                    source = remote_file(output_root, paths[index])
                    expected = f"seg_{index:04d}{'_pre' if pre_refine else ''}.mp4"
                    if source['filename'] != expected:
                        raise ValueError('最终报告路径与分段身份不一致')
                    sources[index] = source
                except ValueError as error:
                    sources[index] = str(error)
            source = sources[index]
            if isinstance(source, str):
                raise ValueError(source)
            receipt_path = Path(data.record_dir) / target['response_name']
            candidate = target['candidate']
            stamp, receipt_exists = saved_files(receipt_path, candidate)
            proof = (state['prompt_id'], source, stamp)
            fresh = False
            if proof[-1] is not None and verified.get(str(receipt_path)) == proof:
                pass
            elif receipt_exists:
                receipt = recordio.read(receipt_path)
                downloaded = receipt['data']
                if (receipt['prompt_id'] != state['prompt_id'] or downloaded['remote'] != source
                        or project_paths.project_file(data.project, downloaded['path'], recorded=True) != candidate
                        or proof[-1] is None or proof[-1][1][0] != downloaded['bytes']):
                    raise ValueError('已有最终下载凭据与文件不一致，不覆盖文件')
            else:
                downloaded = await asyncio.to_thread(store.client.download, store.client_for(data), argparse.Namespace(
                    filename=source['filename'], subfolder=source['subfolder'], type='output', output=str(candidate), sha256=None))
                downloaded['path'] = store.record_paths(key).relative_file(downloaded['path'])
                recordio.write(receipt_path, {'time': store.client.now(), 'prompt_id': state['prompt_id'],
                                                     'identity': target['identity'], 'data': downloaded}, new=True, compact=data.record_format == 'compact')
                proof = (state['prompt_id'], source, saved_files(receipt_path, candidate)[0])
                fresh = True
            verified[str(receipt_path)] = proof
            item.update(remote=source, path=str(candidate), receipt=str(receipt_path), bytes=proof[-1][1][0], check='已取回', error=None)
            collected += 1
            if fresh:
                store.record(key, 'download', 'success', path=str(candidate), remote=source, receipt=str(receipt_path),
                             attempt=state.get('collection_attempt', 1), _changes={'collected': collected})
        except (store.client.ClientError, OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
            item.update(error=str(error), check='取回失败')
            issue = failure(error, store.client.ClientError, identity=target['identity'])
            problems.append(issue)
            store.record(key, 'download', 'failed', **issue, attempt=state.get('collection_attempt', 1))
    if state['collected'] != collected:
        store.save(key, collected=collected)
    return problems
