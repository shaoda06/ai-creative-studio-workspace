"""Assemble existing video workflows from explicit technical inputs."""
from copy import deepcopy
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'nora-comfyui/scripts'))
from workflow_paths import workflow_file

WORKFLOWS = {'crop': 'RIFE-自动切镜保护裁切', 'upscale': 'RTX-RIFE-自动切镜保护超分插帧'}


def assemble(method, source, prefix, size, crop_offset=(0, 0)):
    canvas = json.loads(workflow_file(WORKFLOWS[method]).read_text('utf-8-sig'))
    width, height = size
    for node in canvas['nodes']:
        if node['type'] == 'LoadVideo':
            node['widgets_values_named']['file'] = source
            node['widgets_values'] = list(node['widgets_values_named'].values())
        elif node['id'] == 1:
            values = node['widgets_values_named']
            if method == 'crop':
                values.update(width=width, height=height, x=crop_offset[0], y=crop_offset[1])
            else:
                values.update({'resize_type.width': width, 'resize_type.height': height})
            node['widgets_values'] = list(values.values())
        elif node['type'] == 'VHS_VideoCombine':
            node['widgets_values_named']['filename_prefix'] = prefix
            node['widgets_values']['filename_prefix'] = prefix
    return canvas
