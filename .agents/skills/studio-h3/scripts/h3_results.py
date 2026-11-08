"""Interpret native H3 final reports and output-root paths."""
import json
from pathlib import PureWindowsPath, PurePosixPath
import re
REPORT = re.compile(r'^Segment (\d+)(?:/\d+)?: (一采 mp4|mp4) (saved|updated after continuity trim) → (.+)$', re.M)

def remote_file(root, absolute):
    cls = PureWindowsPath if re.match(r'^[A-Za-z]:[\\/]', root) else PurePosixPath
    root, absolute = cls(root), cls(absolute.strip())
    if not root.is_absolute() or not absolute.is_absolute() or '..' in absolute.parts:
        raise ValueError('分段来源必须是已核实output根目录内的绝对路径')
    relative = absolute.relative_to(root)
    if not relative.parts or relative.parts[0] != 'minimax_seg_export' or relative.suffix != '.mp4':
        raise ValueError('分段来源不属于原生MP4导出目录')
    return {'filename': relative.name, 'subfolder': relative.parent.as_posix(), 'type': 'output'}


def export_paths(data, result):
    """Read the original final report using the task's actual export stage."""
    # Standalone SelfLift exports its completed first pass as the final segment MP4.
    pre_refine = data.task_type == 'video-first-pass'
    director_inputs = data.workflow[data.segment_plan.director_node]['inputs']
    if pre_refine:
        pre_refine = not (director_inputs.get('selflift') and not director_inputs.get('refine'))
    timeline = json.loads(director_inputs['timeline_data'])
    refine = data.workflow[director_inputs['refine'][0]]['inputs'] if director_inputs.get('refine') else {}
    pre_refine_by_index = {}
    for index, group in enumerate(timeline['segments']):
        mode = group.get('taskType') or group.get('task_type') or timeline.get('global', {}).get('taskType') or director_inputs.get('task_type', 'r2v')
        pre_refine_by_index[index] = pre_refine and not (mode.startswith('fl2v') and refine.get('skip_fl2v'))
    outputs = result['history'].get('outputs', {}).get(data.segment_plan.report_node, {})
    text = '\n'.join(value for values in outputs.values() if isinstance(values, list)
                     for value in values if isinstance(value, str))
    paths = {}
    for match in REPORT.finditer(text):
        if (match[2] == '一采 mp4') == pre_refine_by_index[int(match[1]) - 1]:
            paths[int(match[1]) - 1] = match[4].strip()
    return paths, pre_refine_by_index
