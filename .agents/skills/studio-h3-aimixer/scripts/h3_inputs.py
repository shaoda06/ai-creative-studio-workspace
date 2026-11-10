"""Check explicit H3 request limits and reference slots; no business prerequisites."""
import json
import re
from h3_prompt_format import PROMPT_CHARACTER_LIMIT

def director_checks(workflow, timelines=None):
    rows = []
    for node in workflow.values():
        if node['class_type'] != 'MiniMaxH3Director':
            continue
        timeline = timelines[id(node)] if timelines is not None else json.loads(node['inputs']['timeline_data'])
        common = timeline['global']
        enabled = common.get('commonEnabled', False)
        indices = timeline['runSelection'] if timeline.get('runSelectEnabled') else range(len(timeline['segments']))
        for index in indices:
            group = timeline['segments'][index]
            prompt = '\n\n'.join(part.strip() for part in ([common.get('prompt', ''), group['prompt']] if enabled else [group['prompt']]) if part.strip())
            characters = len(prompt)
            if characters > PROMPT_CHARACTER_LIMIT:
                raise ValueError(f'原组{index}完整提示词超过{PROMPT_CHARACTER_LIMIT}字符')
            if not 0 < group['durationSec'] <= 15:
                raise ValueError(f'原组{index}请求时长不在0—15秒范围内')
            labels, counts, durations = set(), {}, {}
            for field, file_key, label, limit in (
                ('refs', 'imageFile', 'Picture', 9), ('refVideos', 'videoFile', 'Video', 3), ('refAudios', 'audioFile', 'Audio', 3)):
                public, local = list(common.get(field, [])) if enabled else [], list(group.get(field, []))
                if field == 'refVideos':
                    for block, items in ((common, public), (group, local)):
                        legacy = block.get('referenceVideo')
                        if (block is not common or enabled) and legacy and (legacy.get('videoFile') or legacy.get('fileName')) and not any(item['index'] == 0 for item in items):
                            items.insert(0, {**legacy, 'index': 0, 'videoFile': legacy.get('videoFile') or legacy['fileName']})
                if len({item['index'] for item in public}) != len(public) or len({item['index'] for item in local}) != len(local):
                    raise ValueError(f'原组{index}的{label}槽位重复')
                merged = {item['index']: item for item in public}
                merged.update({item['index']: item for item in local})
                if any(type(slot) is not int or slot < 0 or slot >= limit or not item.get(file_key) for slot, item in merged.items()):
                    raise ValueError(f'原组{index}的{label}槽位无效或超限')
                counts[label] = len(merged)
                labels.update((label, slot + 1) for slot in merged)
                if field != 'refs':
                    seconds = [item.get('durationSec') for item in merged.values()]
                    if any(not isinstance(value, (int, float)) or not 2 <= value <= 15 for value in seconds) or sum(seconds) > 15:
                        raise ValueError(f'原组{index}的{label}缺少有效时长或总时长超过15秒')
                    durations[label] = sum(seconds)
            if sum(counts.values()) > 12 or counts['Audio'] and not (counts['Picture'] or counts['Video']):
                raise ValueError(f'原组{index}参考素材组合超限')
            if any((kind, int(slot)) not in labels for kind, slot in re.findall(r'<(Picture|Video|Audio) (\d+)>', prompt)):
                raise ValueError(f'原组{index}正文标签没有对应的实际输入')
            rows.append({'index': index, 'characters': characters, 'remaining': PROMPT_CHARACTER_LIMIT - characters,
                         'seconds': group['durationSec'], 'counts': counts, 'reference_seconds': durations})
    return rows
