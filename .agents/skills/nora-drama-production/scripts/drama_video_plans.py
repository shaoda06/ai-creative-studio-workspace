"""Short-drama video plan: business identities, source selection and execution records."""
from copy import deepcopy
import json
from pathlib import Path
import sys
_SKILLS = Path(__file__).resolve().parents[2]
for _name in ('studio-comfyui', 'studio-h3', 'nora-drama-images'):
    sys.path.insert(0, str(_SKILLS / _name / 'scripts'))
from project_paths import project_file
import workflow_graph as pairs
from h3_workflow import reference_bindings, widget
from drama_image_plans import remote_prefix

def build_video(root, spec, documents):
    record = project_file(root, spec['record_dir'])
    canvas = json.loads(project_file(root, spec['canvas']).read_text('utf-8-sig'))
    mapping = deepcopy(spec.get('mapping'))
    if mapping is None:
        mapping = json.loads(documents.read(record / '输入映射.json'))
    unbound_mapping = deepcopy(mapping)
    unbound_mapping.setdefault('uploads', [])
    source_index = mapping.setdefault('uploads', [])
    for ref in spec.get('references', []):
        file = project_file(root, ref['file']).relative_to(root.resolve()).as_posix()
        matches = [item for item in source_index if item['input_path'] == ref['placeholder']]
        if any(project_file(root, item['file']) != project_file(root, file) for item in matches):
            raise ValueError('视频参考占位值对应不同源文件：' + ref['placeholder'])
        if not matches:
            source_index.append(dict(input_path=ref['placeholder'], file=file))
    if spec.get('sync_timing'):
        from drama_video_records import sync_timing
        sync_timing(canvas, mapping, spec['task_type'])
    stage = {'video-first-pass': '一采', 'video-second-pass': '二采', 'video-postprocess': '后处理'}[spec['task_type']]
    episode, scene = mapping['scene'].split('-')
    native = any(node['type'] == 'MiniMaxH3Director' for node in canvas['nodes'])
    selected = [mapping['segments'][index] for index in mapping['selected_indices']]
    for node in canvas['nodes']:
        if node['type'] not in ('SaveVideo', 'VHS_VideoCombine', 'SaveImage') or node.get('mode', 0) in (2, 4):
            continue
        if native:
            saved_stage = {504: '一采', 506: '二采'}.get(node['id'], stage)
            folder = '辅助预览'
            identity = f"{mapping['scene']}-{record.name}-{saved_stage}-辅助预览-节点{node['id']}"
        else:
            folder = stage
            identity = (selected[0]['segment'] + '-' + selected[0]['round'] if len(selected) == 1 else mapping['scene'] + '-' + record.name) + '-' + stage
        widget(canvas, node, filename_prefix=remote_prefix(root, '视频生成', episode, scene, folder, identity))
    api = pairs.Canvas(canvas).api(spec['output_nodes'])
    if spec.get('content_review'):
        if mapping.get('content_review'):
            raise ValueError('已有内容核对映射不自动覆盖；新核对请明确使用本次无绑定映射及注释')
        from h3_prompt_checks import bind_review
        mapping['content_review'] = bind_review(root, api, spec['content_review'])
    documents.new_json(record / '任务.workflow.json', canvas)
    documents.new_json(record / '任务.api.json', api)
    mapping_file = record / '输入映射.json'
    existing_mapping = documents.read(mapping_file)
    existing_unbound = json.loads(existing_mapping) if existing_mapping is not None else None
    if existing_unbound is not None:
        existing_unbound.setdefault('uploads', [])
    if existing_unbound == unbound_mapping:
        documents.put(mapping_file, json.dumps(mapping, ensure_ascii=False, indent=2))
    else:
        documents.new_json(mapping_file, mapping)
    outputs = spec.get('outputs', [])
    segment_plan = spec.get('segment_plan')
    if spec['task_type'] in ('video-first-pass', 'video-second-pass') and segment_plan is None:
        director = next(key for key, node in api.items() if node['class_type'] == 'MiniMaxH3Director')
        targets = []
        stage = {'video-first-pass': '一采', 'video-second-pass': '二采'}[spec['task_type']]
        for index in mapping['selected_indices']:
            entry = mapping['segments'][index]
            identity = f"{entry['segment']}-{entry['round']}-{stage}"
            targets.append(dict(index=index, path=f"09-剧集制作/{identity.split('-')[0]}/其他资料/候选视频/{identity}.mp4", response_name=f'最终取回-{index:03d}.json', resource_key='视频/' + entry['segment']))
        segment_plan = dict(director_node=director, report_node=str(spec['report_node']), output_root=spec['output_root'], targets=targets)
    if spec['task_type'] == 'video-postprocess' and not outputs:
        savers = [key for key,node in api.items() if node['class_type']=='VHS_VideoCombine' and node['inputs'].get('format')=='video/h264-mp4']
        if len(mapping['selected_indices']) != 1 or len(savers) != 1:
            raise ValueError('非标准单段MP4后处理须显式提供outputs，不猜测保存节点')
        entry = mapping['segments'][mapping['selected_indices'][0]]
        identity = entry['segment']+'-'+entry['round']+'-后处理'
        outputs = [dict(node_id=savers[0], output_key='gifs', index=0,
            path=f"09-剧集制作/{identity.split('-')[0]}/其他资料/候选视频/{identity}.mp4", response_name='最终取回-000.json', resource_key='视频/' + entry['segment'])]
    uploads = reference_bindings(api,
        [{**item, 'file': str(project_file(root, item['file']))} for item in spec.get('references', [])],
        record.name, spec.get('uploads', []))
    from drama_video_records import prepare_records
    prepare_records(root, None, spec, api, mapping, record, documents)
    return dict(project=str(root), task_type=spec['task_type'], title=spec['title'], workflow=api, record_dir=str(record),
        video_plan={'metadata': 'ffprobe'}, submission_plan=spec.get('submission_plan'),
        uploads=uploads, outputs=outputs, segment_plan=segment_plan, attempt_name='提交尝试.json',
        request_name='请求.json', response_name='提交响应.json', history_name='执行结果.json')
