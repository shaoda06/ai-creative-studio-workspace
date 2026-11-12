"""Register the Iris production round from an assembled task group."""
import json
from pathlib import Path
import re
import sys

from prepared_documents import Documents, publish
from project_paths import project_file
from iris_works import work_root
from iris_workbench import SHOT_HEADING, apply_plan_timing, scene_segments, segment_rows, segment_text
from iris_browser_production import SONGSSX_TASK, STAGES, VIDEO_EXTENSIONS, local_key
from backend.services.scene_postprocess import output_for_source
from songssx_workflow import PLANNER, shot_blocks

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-storyboard/scripts'))
from storyboard_fields import read_shots


def work_file(project, directory, value):
    path = project_file(project, value)
    if not path.is_relative_to(directory):
        raise ValueError('轮次资料不在本作品的指定目录：' + str(value))
    return path


def source(project, directory, value):
    path = work_file(project, directory, value['file'])
    version = value['version']
    if path.suffix != '.md' or not re.fullmatch(r'v\d{2,}', version) or not path.stem.endswith('-' + version):
        raise ValueError('轮次用稿须引用版本匹配的 Markdown：' + path.name)
    return path, {'file': path.relative_to(project).as_posix(), 'version': version}


def storyboard_plan(path):
    text = path.read_text('utf-8-sig')
    rows = segment_rows(text)
    if not rows:
        raise ValueError('分镜须有明确的 P 段计划表：' + path.name)
    durations, counts = {}, {}
    shot_ids = set()
    for identity, row in rows.items():
        part = segment_text(text, identity)
        ids = SHOT_HEADING.findall(part)
        if not ids or len(read_shots(part)) != len(ids) or shot_ids.intersection(ids) or len(set(ids)) != len(ids):
            raise ValueError(identity + ' 须有唯一且完整的逐镜正文')
        shot_ids.update(ids)
        length = row.get('请求时长') or row.get('目标时长') or row.get('目标段长', '')
        match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*秒', length)
        if not match or not float(match[1]):
            raise ValueError(identity + ' 的分镜计划缺少正数请求时长')
        durations[identity] = float(match[1])
        counts[identity] = len(ids)
        timing = {'shots': [{'id': f'SH{number:03d}', 'duration': None} for number in range(1, len(ids) + 1)]}
        apply_plan_timing(timing, row, durations[identity], ids)
        if timing.get('shotTimingSource') != 'plan':
            raise ValueError(identity + ' 的镜号、段内时码与计划时长不一致')
    return durations, counts, scene_segments(list(rows), rows)


def register(project, spec, tasks, batch, now, *, write, reprepare=False):
    work = work_root(project, spec['work'])
    if work == project:
        raise ValueError('轮次登记须指定 F 作品')
    production = work / '06-视频生产'
    batch = work_file(project, production / '执行记录', batch)
    batch_key = batch.relative_to(project).as_posix()
    run = re.match(r'(R\d{3,})(?:-|$)', batch.parent.name)
    if not run:
        raise ValueError('装配结果所在批次目录须以 R 编号开头')
    record = work_file(project, production, spec['record'])
    if record.suffix != '.md' or not record.is_file():
        raise ValueError('轮次须引用本作品实际生产或后处理记录')
    record_key = record.relative_to(project).as_posix()
    storyboard, storyboard_ref = source(project, work / '04-分镜声音', spec['storyboard'])
    durations, counts, scenes = storyboard_plan(storyboard)
    metadata = {'record': record_key, 'storyboard': storyboard_ref, 'note': spec.get('note', '')}
    if 'script' in spec:
        script, metadata['script'] = source(project, work / '03-创意脚本', spec['script'])
        if not script.is_file():
            raise FileNotFoundError(script)
    prompts = {}
    for identity, name in spec.get('prompts', {}).items():
        path = work_file(project, production, name)
        if path.suffix != '.md' or not path.is_file():
            raise ValueError('提示词引用须指向本作品的 Markdown：' + str(name))
        prompts[identity] = path.relative_to(project).as_posix()

    documents = Documents(project)
    index = work_file(project, production, production / '制作轮次.json')
    current = documents.read(index)
    data = json.loads(current) if current is not None else {'rounds': []}
    rounds = {row['number']: row for row in data['rounds']}
    if len(rounds) != len(data['rounds']) or any(type(number) is not int or number < 1 for number in rounds):
        raise ValueError('制作轮次编号须为不重复的正整数')
    matching = [row for row in rounds.values() if row.get('record') == record_key]
    if len(matching) > 1:
        raise ValueError('本批生产记录对应多轮，请先核对原轮次')
    existing = matching[0] if matching else None
    number = existing['number'] if existing else max(rounds, default=0) + 1
    base_number = spec.get('base_round')
    if base_number is not None and (type(base_number) is not int or base_number not in rounds or base_number >= number):
        raise ValueError('base_round 须指向本作品已登记的较早轮次')
    base = rounds[base_number] if base_number is not None else {}
    own_batches = set(existing.get('batches', [])) - set(base.get('batches', [])) if existing else set()
    rebuild = reprepare and own_batches == {batch_key}
    if existing and (any(existing.get(key) != value for key, value in metadata.items())
                     or existing.get('base_round') != base_number or existing.get('plan')):
        if not rebuild:
            raise ValueError('本轮已登记其他用稿或来源轮次，请沿用原记录或提交新轮')
    previous = existing if existing and not rebuild else base
    selected = {item['id']: item for item in previous.get('segments', [])}
    review_outputs = list(existing.get('review_outputs', [])) if existing and not rebuild else []
    changes = {}
    for task in tasks:
        directory = work_file(project, batch.parent, task['record_dir'])
        plan = task.get('video_plan') or {}
        kind = task['task_type']
        outputs = (task.get('segment_plan') or {}).get('targets', []) + task['outputs']
        if plan.get('adapter') != 'technical' or not outputs:
            raise ValueError('Iris 轮次须关联实际技术视频任务及输出')
        if kind == SONGSSX_TASK:
            identities = [item['p'] for item in plan['segments']]
            output, = outputs
            if 'gap_repair' in plan:
                identity, = identities
                if identity not in selected:
                    raise ValueError('补生成须先登记本轮沿用的原分段')
                path = project_file(project, output['path']).relative_to(project).as_posix()
                item = {'label': f'{identity} · {run[1]} 补生成', 'file': path}
                if item not in review_outputs:
                    review_outputs.append(item)
                continue
            if identities not in scenes.values():
                raise ValueError('Songssx GEN 须与分镜中同一整场的 P 段顺序一致')
            if any(item['planned_seconds'] != durations[item['p']] for item in plan['segments']):
                raise ValueError('Songssx GEN 请求时长与分镜计划不一致')
            timeline = json.loads(task['workflow'][PLANNER]['inputs']['timeline_data'])
            for identity, gen in zip(identities, timeline['segmentConfig']['segments'], strict=True):
                if len(shot_blocks(gen['prompt'])) != counts[identity]:
                    raise ValueError(identity + ' 的实际提示词 Shot 数与分镜不一致')
            pairs = [(identity, output) for identity in identities]
            stage = '一采'
        else:
            stage = STAGES[kind]
            pairs = []
            for output in outputs:
                path = project_file(project, output['path'])
                if path.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue
                match = re.match(r'(P\d{3,})(?:-|\.)', path.name)
                if not match:
                    if kind != 'video-postprocess':
                        raise ValueError('逐段输出须以 P 段号开头：' + path.name)
                    upload, = task['uploads']
                    source_path = project_file(project, upload['file']).relative_to(project).as_posix()
                    if source_path not in {local_key(project, item['file']) for item in selected.values()}:
                        raise ValueError('整场后处理须引用本轮沿用的原视频')
                    output_for_source(project, task, source_path)
                    item = {'label': f'{run[1]} 整场后处理', 'postprocess': directory.relative_to(project).as_posix(),
                            'source': source_path}
                    if item not in review_outputs:
                        review_outputs.append(item)
                    continue
                pairs.append((match[1], output))
            if not pairs and not any(item.get('postprocess') == directory.relative_to(project).as_posix()
                                     for item in review_outputs):
                raise ValueError('本批缺少可登记的视频输出')
        for identity, output in pairs:
            if identity not in durations or identity in changes:
                raise ValueError('分段输出重复或分镜未登记：' + identity)
            changes[identity] = {'id': identity, 'duration': durations[identity], 'stage': stage, 'run': run[1],
                                 'file': project_file(project, output['path']).relative_to(project).as_posix()}
            if identity in prompts:
                changes[identity]['prompt'] = prompts[identity]
    if prompts.keys() - changes.keys():
        raise ValueError('提示词引用须属于本批实际生成的 P 段')
    original = {entry['id']: entry for entry in base.get('segments', [])}
    if existing and any(selected.get(identity) not in (None, original.get(identity), entry)
                        and not (batch_key in existing.get('batches', []) and selected[identity]['run'] == run[1])
                        for identity, entry in changes.items()):
        raise ValueError('本轮的 P 段已由其他批次登记，请引用原批次或建立新轮')
    selected.update(changes)
    if set(durations) - selected.keys():
        raise ValueError('本轮缺少候选的 P 段：' + '、'.join(sorted(set(durations) - selected.keys())))
    if any(selected[identity]['duration'] != duration for identity, duration in durations.items()):
        raise ValueError('沿用分段时长与本轮分镜计划不一致')
    segments = [selected[identity] for identity in durations]
    batches = list(dict.fromkeys([*base.get('batches', []), *(existing or {}).get('batches', []), batch_key]))
    item = {'number': number, 'created_at': existing['created_at'] if existing else now,
            **metadata, 'segments': segments, 'batches': batches}
    if base_number is not None:
        item.update(base_round=base_number, changed_segments=[entry['id'] for entry in segments
                                                             if entry != original.get(entry['id'])])
    if review_outputs:
        item['review_outputs'] = review_outputs
    rounds[number] = item
    data['rounds'] = list(rounds.values())
    if write and item != existing:
        documents.put(index, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        publish(project, documents.writes())
    return number
