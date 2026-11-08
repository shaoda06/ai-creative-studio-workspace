"""Image processing mechanics; dimensions and approval come from the caller."""
from copy import deepcopy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-comfyui/scripts'))
from workflow_graph import Canvas, link_tuple

WORKFLOWS = Path(__file__).resolve().parents[1] / 'references/workflows'


def assemble_rtx(source, *, prefix, remote_output=None, size=None):
    """Prepare the existing RTX workflow; no upload or generation."""
    canvas = json.loads((WORKFLOWS / 'RTX-图片2倍超分.workflow.json').read_text('utf-8-sig'))
    nodes = {n['id']: n for n in canvas['nodes']}
    if size is not None:
        width, height = size
        if any(type(n) is not int or n <= 0 for n in size):
            raise ValueError('超分size须为两个正整数像素宽高')
        resize = nodes[1]
        settings = resize['widgets_values_named']
        resize['widgets_values_named'] = {
            'resize_type': 'target dimensions', 'resize_type.width': width, 'resize_type.height': height,
            **{k: v for k, v in settings.items() if not k.startswith('resize_type')}}
        resize['widgets_values'] = list(resize['widgets_values_named'].values())
        scale = next(i for i in resize['inputs'] if i['name'] == 'resize_type.scale')
        index = resize['inputs'].index(scale)
        resize['inputs'][index:index + 1] = [
            {**deepcopy(scale), 'name': 'resize_type.' + axis, 'localized_name': axis,
             'type': 'INT', 'widget': {'name': 'resize_type.' + axis}}
            for axis in ('width', 'height')]
    for node, values in [(nodes[2], {'image': Path(source).name}),
                         (nodes[3], {'filename_prefix': prefix if remote_output is None else remote_output})]:
        for key, value in values.items():
            if key not in node['widgets_values_named']:
                raise ValueError('基准不存在控件：' + key)
            slot = next((i for i in node.get('inputs', []) if i['name'] == key), None)
            if slot and slot.get('link') is not None:
                link = next(link_tuple(item) for item in canvas['links'] if link_tuple(item)[0] == slot['link'])
                origin = nodes[link[1]]
                origin['outputs'][link[2]]['links'].remove(slot['link'])
                canvas['links'] = [item for item in canvas['links'] if link_tuple(item)[0] != slot['link']]
                slot['link'] = None
            node['widgets_values_named'][key] = value
        if isinstance(node['widgets_values'], dict):
            node['widgets_values'].update(values)
        else:
            node['widgets_values'] = list(node['widgets_values_named'].values())
    uploads = [dict(file=str(source), node='2', input='image', subfolder=prefix,
                    **{'response-name': prefix + '-上传响应.json'})]
    return canvas, Canvas(canvas).api(3), uploads, '3'


def resize(source, destination, target, crop_anchor, *, project):
    """Save a new PNG using the requested dimensions; preserve source and actual geometry."""
    from PIL import Image, ImageOps, __version__
    from io import BytesIO
    from image_files import store_png
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError('本地处理输出已存在，不能覆盖：' + str(destination))
    with Image.open(source) as image:
        image.load()
        width, height = image.size
        scale = max(target[0] / width, target[1] / height)
        crop_width, crop_height = target[0] / scale, target[1] / scale
        left = (width - crop_width) * crop_anchor[0]
        top = (height - crop_height) * crop_anchor[1]
        box = [left, top, left + crop_width, top + crop_height]
        if image.size == tuple(target):
            raw = source.read_bytes()
        else:
            stream = BytesIO()
            ImageOps.fit(image, tuple(target), method=Image.Resampling.LANCZOS,
                         centering=tuple(crop_anchor)).save(stream, format='PNG')
            raw = stream.getvalue()
        destination = store_png(project, destination, raw, source=source, origin='process')
    return dict(path=str(destination), tool='Pillow ' + __version__, source_size=[width, height], crop_box=box)


def validate_processing(data, source, source_size, target, local):
    """Validate explicit processing geometry, bindings and RTX node parameters."""
    if local:
        anchor = local['crop_anchor']
        if (data.workflow or data.uploads or data.outputs[0].node_id != 'local'
                or list(source_size) != local['source_size']):
            raise ValueError('本地处理必须使用原批准图及本地输出，不带远端工作流或上传')
        if not isinstance(anchor, (list, tuple)) or len(anchor) != 2 or any(type(n) not in (int, float) or not 0 <= n <= 1 for n in anchor):
            raise ValueError('crop_anchor须为0到1之间的两个数，表示水平、垂直裁切位置')
    elif any(n < old for n, old in zip(target, source_size)) or target == source_size:
        raise ValueError('RTX不能缩小任意一边或处理同尺寸图片；请使用统一任务清单自动转本地处理')
    elif len(data.uploads) != 1 or Path(data.uploads[0]['file']) != source or data.uploads[0]['node'] != '2' or data.uploads[0]['input'] != 'image':
        raise ValueError('超分上传必须绑定获批原图到节点2')
    if not local:
        workflow = data.workflow
        if (workflow['1']['class_type'] != 'RTXVideoSuperResolution' or workflow['1']['inputs']['images'] != ['2', 0]
                or workflow['3']['class_type'] != 'SaveImage' or workflow['3']['inputs']['images'] != ['1', 0]
                or data.outputs[0].node_id != '3'):
            raise ValueError('超分必须为批准原图→RTX节点1→节点3')
        resize = workflow['1']['inputs']
        if resize['resize_type'] == 'scale by multiplier':
            if resize['resize_type.scale'] != 2:
                raise ValueError('倍数超分只支持2倍')
        elif resize['resize_type'] == 'target dimensions':
            requested = (resize['resize_type.width'], resize['resize_type.height'])
            if any(type(n) is not int for n in requested) or requested != target:
                raise ValueError('RTX指定尺寸与成果计划不符')
        else:
            raise ValueError('不支持的RTX图片尺寸模式')
