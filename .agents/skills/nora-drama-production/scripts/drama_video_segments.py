"""Serial-drama association and candidate targets for H3 segment tasks."""
import json
from pathlib import Path
from h3_results import remote_file

def targets(data, mapping=None, *, segment_context=None):
    from backend.services.comfy_tasks import paths
    project = segment_context['project'] if segment_context is not None else Path(data.project).resolve()
    if mapping is None:
        mapping = json.loads((Path(data.record_dir) / '输入映射.json').read_text('utf-8-sig'))
    stage = {'video-first-pass': '一采', 'video-second-pass': '二采'}[data.task_type]
    result = []
    for index in mapping['selected_indices']:
        segment = mapping['segments'][index]
        identity = f"{segment['segment']}-{segment['round']}-{stage}"
        record = (segment_context['entries'][index]['directory'] if segment_context is not None
                  else paths.project_file(project, segment['local_execution_dir'], recorded=True))
        episode = segment['segment'].split('-')[0]
        explicit = next((item for item in data.segment_plan.targets if item.index == index), None)
        candidate = Path(explicit.path) if explicit else project / '09-剧集制作' / episode / '其他资料/候选视频' / (identity + '.mp4')
        result.append({'index': index, 'identity': identity, 'record': record, 'candidate': candidate, 'response_name': explicit.response_name if explicit else f'最终取回-{index:03d}.json'})
    return result


def validate(data, *, mapping=None, timelines=None, path_scope=None):
    from backend.services.comfy_tasks import generation_context
    plan = data.segment_plan
    if mapping is None:
        mapping = json.loads((Path(data.record_dir) / '输入映射.json').read_text('utf-8-sig'))
    context = generation_context.validate_segment_context(data.project, data.workflow, data.task_type, mapping,
                                                           timelines=timelines, path_scope=path_scope)
    director = data.workflow[plan.director_node]
    if director is not context['director'] or plan.report_node not in data.workflow:
        raise ValueError('分段计划必须绑定实际导演台及报告节点')
    # Require the report node's input to be this director's report output (slot 5).
    if [plan.director_node, 5] not in data.workflow[plan.report_node]['inputs'].values():
        raise ValueError('报告节点未连接该导演台report输出')
    timeline = context['timeline']
    if timeline['output'].get('exportMode') != 'segments':
        raise ValueError('分段取回需要原生segments导出')
    selected = context['indices']
    explicit = plan.targets
    if explicit and (len(explicit) != len(selected) or {item.index for item in explicit} != set(selected)):
        raise ValueError('本机成果目标必须逐一对应实际执行分段')
    if len({Path(item.path) for item in explicit}) != len(explicit):
        raise ValueError('分段目标路径不能重复')
    for item in targets(data, mapping, segment_context=context):
        if item['candidate'].exists():
            raise ValueError('本轮候选已存在；核对原任务，不得重复提交')
    remote_file(plan.output_root, plan.output_root.rstrip('/\\') + '/minimax_seg_export/validation/seg_0000.mp4')
    return context
