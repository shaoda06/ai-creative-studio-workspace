"""H3 canvas conversion and explicit media-slot binding; no business paths."""
from copy import deepcopy
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-comfyui/scripts'))
import workflow_graph as pairs
from project_paths import project_file

def widget(graph, node, **values):
    named = node['widgets_values_named']
    for key, content in values.items():
        if key not in named:
            raise ValueError('基准不存在控件：' + key)
        slot = next((i for i in node.get('inputs', []) if i['name'] == key), None)
        if slot and slot.get('link') is not None:
            disconnect(graph, slot)
        named[key] = content
    if isinstance(node['widgets_values'], dict):
        node['widgets_values'].update(values)
    else:
        node['widgets_values'] = list(named.values())


def disconnect(graph, slot):
    key = slot['link']
    if key is None:
        return
    link = next(pairs.link_tuple(link) for link in graph['links'] if pairs.link_tuple(link)[0] == key)
    origin = next(n for n in graph['nodes'] if n['id'] == link[1])
    origin['outputs'][link[2]]['links'].remove(key)
    graph['links'] = [item for item in graph['links'] if pairs.link_tuple(item)[0] != key]
    slot['link'] = None


def reference_bindings(api, references, subfolder, existing=()):
    uploads = list(existing)
    timelines = {key: json.loads(node['inputs']['timeline_data']) for key,node in api.items() if node['class_type']=='MiniMaxH3Director'}
    for ref in {item['placeholder']: item for item in references}.values():
        file = Path(ref['file'])
        placeholder, matched = ref['placeholder'], False
        for key, node in api.items():
            for name, content in node['inputs'].items():
                slots = []
                if content == placeholder:
                    slots.append(None)
                elif node['class_type'] == 'MiniMaxH3Director' and name == 'timeline_data':
                    timeline = timelines[key]
                    for area, block in [(['global'], timeline['global']), *[(['segments', i], item) for i, item in enumerate(timeline['segments'])]]:
                        for array, field in [('refs', 'imageFile'), ('refVideos', 'videoFile'), ('refAudios', 'audioFile')]:
                            for index, item in enumerate(block.get(array, [])):
                                if item.get(field) == placeholder:
                                    slots.append(area + [array, index, field])
                for path in slots:
                    upload = dict(file=str(file), node=key, input=name, subfolder=subfolder,
                                  **{'response-name': f'上传响应-{len(uploads)+1:03d}.json'})
                    if path is not None:
                        upload['json-path'] = path
                    uploads.append(upload)
                    matched = True
        if not matched:
            raise ValueError('视频参考未对应实际画布槽位：' + placeholder)
    return uploads

def prepare_technical(root, spec, documents):
    record = project_file(root, spec['record_dir'])
    canvas = json.loads(project_file(root, spec['canvas']).read_text('utf-8-sig'))
    api = pairs.Canvas(canvas).api(spec['output_nodes'])
    refs = [{**item, 'file': str(project_file(root, item['file']))} for item in spec.get('references', [])]
    uploads = reference_bindings(api, refs, record.name, spec.get('uploads', []))
    documents.new_json(record / '任务.workflow.json', canvas)
    documents.new_json(record / '任务.api.json', api)
    return dict(project=str(root), task_type=spec['task_type'], title=spec['title'], workflow=api,
                record_dir=str(record), video_plan=spec['video_plan'], submission_plan=spec.get('submission_plan'),
                uploads=uploads, outputs=spec.get('outputs', []), segment_plan=spec.get('segment_plan'),
                attempt_name='提交尝试.json', request_name='请求.json', response_name='提交响应.json', history_name='执行结果.json')
