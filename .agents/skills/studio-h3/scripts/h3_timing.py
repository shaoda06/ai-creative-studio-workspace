"""Assemble explicit fresh H3 timing; caller decides whether cached sources may change."""
from copy import deepcopy
import json
import math

def sync_timing(canvas, selected_indices):
    """Explicit fresh first pass only; cached sources are never normalized in place."""
    for node in canvas['nodes']:
        if node['type'] != 'MiniMaxH3Director':
            continue
        widgets = node['widgets_values_named']
        timeline = json.loads(widgets['timeline_data'])
        if widgets['frame_rate'] != 24:
            raise ValueError('当前H3帧格装配仅适用于24fps；其他帧率保留已配置画布')
        start = 0
        for group in timeline['segments']:
            frames = max(5, math.floor(group['durationSec'] * 24 + .5))
            frames += (5 - frames % 17) % 17
            group.update(start=start, length=frames, frameCount=frames)
            start += frames
        timeline.update(totalFrames=start, frameRate=widgets['frame_rate'], width=widgets['width'],
            height=widgets['height'], refMaxSize=widgets['ref_max_size'], runSelectEnabled=True,
            runSelection=selected_indices)
        timeline['output'].update(width=widgets['width'], height=widgets['height'])
        timeline['batchWorkspaces']['r2v'].update(globalCommon=deepcopy(timeline['global']),
            segments=deepcopy(timeline['segments']), editMode=timeline['editMode'],
            runSelectEnabled=True, runSelection=selected_indices)
        widgets.update(total_frames=start, global_prompt=timeline['global']['prompt'],
            control_after_generate='fixed', timeline_data=json.dumps(timeline, ensure_ascii=False))
        node['widgets_values'] = list(widgets.values())
