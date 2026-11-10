"""Read AiMixer groups and keyframe slots from a submitted request."""
import json
import re
from h3_prompt_format import digest


def group_mode(workflow, node, index):
    inputs = workflow[node]['inputs']
    timeline = json.loads(inputs['timeline_data'])
    group = timeline['segments'][index]
    raw = group.get('taskType') or group.get('task_type') or timeline['global'].get('taskType') or inputs['task_type']
    match = re.match(r'^(r2v|rv2v|v2v|t2v|i2v|fl2v)\b', raw.strip().lower())
    if not match:
        raise ValueError('无法识别H3分段模式：' + raw)
    return match[1], group


def keyframe_slots(group):
    images = {item['index']: item for item in group.get('refs', [])}
    for index, field in ((0, 'startImage'), (1, 'endImage')):
        image = group.get(field)
        if image and (image.get('imageFile') or image.get('imageB64')):
            images[index] = image
    image = group.get('genImage')
    if 0 not in images and image and (image.get('imageFile') or image.get('imageB64')):
        images[0] = image
    return {index for index, image in images.items() if image.get('imageFile') or image.get('imageB64')}


def selected_groups(workflow):
    for node_id, node in workflow.items():
        if node['class_type'] != 'MiniMaxH3Director':
            continue
        timeline = json.loads(node['inputs']['timeline_data'])
        common = timeline['global'] if timeline['global'].get('commonEnabled') else {}
        indices = sorted(timeline['runSelection']) if timeline.get('runSelectEnabled') else range(len(timeline['segments']))
        for index in indices:
            group = timeline['segments'][index]
            prompt = '\n\n'.join(p.strip() for p in (common.get('prompt', ''), group['prompt']) if p.strip())
            # Bind the text, duration, references and continuity settings that were reviewed.
            mode, _ = group_mode(workflow, str(node_id), index)
            reviewed = {'common': common, 'group': group}
            if mode != 'r2v':
                reviewed['mode'] = mode
            signature = digest(json.dumps(reviewed, ensure_ascii=False, sort_keys=True))
            yield str(node_id), index, prompt, signature
