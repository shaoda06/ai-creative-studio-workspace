"""Assemble existing video workflows from explicit technical inputs."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-comfyui/scripts'))
from workflow_paths import VIDEO_RELAYVSR, VIDEO_RIFE, VIDEO_RTX, workflow_file


def load_workflow(name):
    return json.loads(workflow_file(name).read_text('utf-8-sig'))


def assemble_relayvsr(source, prefix):
    canvas = load_workflow(VIDEO_RELAYVSR)
    nodes = {node['id']: node for node in canvas['nodes']}
    nodes[1]['widgets_values_named']['file'] = nodes[1]['widgets_values'][0] = source
    nodes[106]['widgets_values_named']['filename_prefix'] = nodes[106]['widgets_values'][0] = prefix
    return canvas


def assemble(method, source, prefix, size, crop_offset=(0, 0)):
    if method not in ('crop', 'upscale'):
        raise ValueError(f'未知固定后处理方式：{method}')
    return _assemble_standard(source, prefix, 30, True, method if method == 'upscale' else 'none', size,
                              (*size, *crop_offset) if method == 'crop' else None)


def plan_output(metadata, resolution, fps, fit=None):
    """Resolve user choices once for both the question preview and execution."""
    import math
    from fractions import Fraction
    sw, sh, sf = metadata['width'], metadata['height'], metadata['frame_rate']
    width, height = (sw, sh) if resolution == 'original' else resolution
    if any(type(v) is not int or v <= 0 or v % 2 for v in (width, height)):
        raise ValueError('输出宽高须为正偶数；请修改分辨率，不自动改写输入')
    target_fps = sf if fps == 'original' else fps
    if type(target_fps) not in (int, float) or not math.isfinite(target_fps) or not 1 <= target_fps <= 240:
        raise ValueError('输出帧率须为1～240之间的数值')
    different = sw * height != sh * width
    if fit not in (None, 'contain', 'crop'):
        raise ValueError('fit须为contain或crop')
    if different and fit is None:
        raise ValueError('源视频与目标比例不同，请选择保留比例或裁切')
    scale = (max if fit == 'crop' else min)(Fraction(width, sw), Fraction(height, sh))
    if fit == 'crop':
        rw, rh = (math.ceil(v * scale / 2) * 2 for v in (sw, sh))
        dw, dh = rw - width, rh - height
        crop = dict(left=dw // 2, right=dw - dw // 2, top=dh // 2, bottom=dh - dh // 2)
        output = [width, height]
    else:
        rw, rh = (max(2, math.floor(v * scale / 2 + Fraction(1, 2)) * 2) for v in (sw, sh))
        crop = dict(left=0, right=0, top=0, bottom=0)
        output = [rw, rh]
    resize = [rw, rh]
    method = 'none' if resize == [sw, sh] else ('upscale' if scale > 1 else 'resize')
    return dict(source_size=[sw, sh], source_fps=sf, target_size=[width, height],
                output_size=output, resize_size=resize, fps=target_fps, fit=fit,
                crop=crop, resize_method=method, needs_fit=different,
                reuse=output == [sw, sh] and not any(crop.values()) and target_fps == sf)


def questions(metadata, resolution=None):
    """Popup arguments; supply resolution after step 1 for the conditional step 3."""
    sw, sh, sf = metadata['width'], metadata['height'], metadata['frame_rate']
    default = '1920×1080' if sw >= sh else '1080×1920'
    result = [dict(title='第1步：输出分辨率｜请选择输出分辨率，或输入宽×高。',
                   options=[f'保持原分辨率（{sw}×{sh}）', f'{default}（默认）']),
              dict(title='第2步：输出帧率｜请选择输出帧率，或输入数值。',
                   options=[f'保持原帧率（{sf:g}fps）', '30fps（默认）', '60fps'])]
    if resolution is not None:
        keep = plan_output(metadata, resolution, 'original', 'contain')
        if keep['needs_fit']:
            cut = plan_output(metadata, resolution, 'original', 'crop')
            c = cut['crop']
            details = []
            for a, b, label in [('left', 'right', '左右'), ('top', 'bottom', '上下')]:
                if c[a] or c[b]:
                    details.append(f'{label}各裁{c[a]}像素' if c[a] == c[b] else f'{label[0]}裁{c[a]}、{label[1]}裁{c[b]}像素')
            w, h = keep['output_size']
            tw, th = cut['output_size']
            rw, rh = cut['resize_size']
            resize = '' if cut['resize_method'] == 'none' else f'先缩放至{rw}×{rh}，'
            result.append(dict(title='第3步：画面适配｜源视频与目标比例不同，请选择处理方式。',
                               options=[f'保留比例（输出{w}×{h}）', f'裁切至{tw}×{th}（{resize}{"，".join(details)}）']))
    return result


def assemble_output(source, prefix, plan):
    """Return a canvas or None when the original file already satisfies the choices."""
    if plan['reuse']:
        return None
    crop = plan['crop']
    box = (*plan['output_size'], crop['left'], crop['top']) if any(crop.values()) else None
    return _assemble_standard(source, prefix, plan['fps'], plan['fps'] != plan['source_fps'],
                              plan['resize_method'], plan['resize_size'], box)


def _assemble_standard(source, prefix, fps, interpolate, method, size, box):
    canvas = load_workflow(VIDEO_RTX)
    nodes = {n['id']: n for n in canvas['nodes']}
    loader = nodes[6]
    loader['widgets_values_named']['file'] = source
    loader['widgets_values'] = list(loader['widgets_values_named'].values())
    active = [nodes[6], nodes[7]]
    edges = [(6, 0, 7, 0, 'VIDEO')]
    image, fps_link = (7, 0), (7, 2)
    if interpolate:
        rife = next(node for node in load_workflow(VIDEO_RIFE)['nodes'] if node['id'] == 12)
        rife['widgets_values_named']['target_fps'] = fps
        rife['widgets_values'] = list(rife['widgets_values_named'].values())
        rife['title'] = f"切镜保护插帧｜目标{fps:g}fps"
        active.append(rife)
        edges.extend([(7, 0, 12, 0, 'IMAGE'), (7, 2, 12, 1, 'FLOAT')])
        image, fps_link = (12, 0), (12, 1)
    if method != 'none':
        w, h = size
        if method == 'upscale':
            resize = nodes[1]
            values = resize['widgets_values_named']
            values.update({'resize_type.width': w, 'resize_type.height': h})
            resize['widgets_values'] = list(values.values())
        else:
            values = dict(upscale_method='lanczos', width=w, height=h, crop='disabled')
            resize = dict(id=1, type='ImageScale', pos=[1210, 290], size=[280, 180], flags={}, mode=0,
                          properties={'Node name for S&R': 'ImageScale'},
                          inputs=[dict(name='image', type='IMAGE', link=None)],
                          outputs=[dict(name='IMAGE', type='IMAGE', links=[])],
                          widgets_values_named=values, widgets_values=list(values.values()))
        resize['title'] = f"尺寸处理｜{w}×{h}"
        active.append(resize)
        edges.append((*image, 1, 0, 'IMAGE'))
        image = (1, 0)
    if box is not None:
        values = dict(zip(('width', 'height', 'x', 'y'), box))
        crop = dict(id=25, type='ImageCrop', pos=[1530, 290], size=[280, 180], flags={}, mode=0,
                    properties={'Node name for S&R': 'ImageCrop'},
                    inputs=[dict(name='image', type='IMAGE', link=None)],
                    outputs=[dict(name='IMAGE', type='IMAGE', links=[])],
                    widgets_values_named=values, widgets_values=list(values.values()))
        active.append(crop)
        edges.append((*image, 25, 0, 'IMAGE'))
        image = (25, 0)
    saver = nodes[16]
    values = dict(frame_rate=fps, filename_prefix=prefix)
    saver['widgets_values_named'].update(values)
    saver['widgets_values'].update(values)
    active.append(saver)
    edges.extend([(*image, 16, 0, 'IMAGE'), (*fps_link, 16, 4, 'FLOAT'), (7, 1, 16, 1, 'AUDIO')])
    canvas['nodes'], canvas['links'] = active, []
    for order, node in enumerate(active):
        node['order'] = order
        for item in node.get('inputs', []):
            item['link'] = None
        for item in node.get('outputs', []):
            item['links'] = []
    nodes = {n['id']: n for n in active}
    for key, (origin, slot, target, target_slot, kind) in enumerate(edges, 1):
        canvas['links'].append([key, origin, slot, target, target_slot, kind])
        nodes[origin]['outputs'][slot]['links'].append(key)
        nodes[target]['inputs'][target_slot]['link'] = key
    canvas['last_node_id'], canvas['last_link_id'] = max(nodes), len(edges)
    return canvas


def configure_postprocess(root, spec):
    """Shared task adapter: probe the exact bound local source before assembly."""
    from project_paths import project_file
    from video_metadata import probe
    if spec['task_type'] != 'video-postprocess':
        raise ValueError('video_postprocess仅用于后处理任务')
    choice = spec['video_postprocess']
    if set(choice) - {'source', 'resolution', 'fps', 'fit'} or not {'source', 'resolution', 'fps'} <= set(choice):
        raise ValueError('video_postprocess须提供source、resolution、fps，可选fit')
    source = project_file(root, choice['source'])
    refs = [r for r in spec['references'] if project_file(root, r['file']) == source]
    if len(refs) != 1:
        raise ValueError('后处理source须对应唯一的视频参考文件')
    plan = plan_output(probe(source), choice['resolution'], choice['fps'], choice.get('fit'))
    canvas = assemble_output(refs[0]['placeholder'], spec['title'], plan)
    if canvas is None:
        raise ValueError('源视频已满足所选规格：直接沿用原文件，无需提交后处理任务')
    return canvas, plan
