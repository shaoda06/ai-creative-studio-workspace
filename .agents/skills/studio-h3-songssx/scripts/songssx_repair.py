"""Join a returned Songssx repair into its original scene and register round playback."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

from songssx_workflow import FPS, TASK_TYPE, WORKFLOW

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / 'studio-workspace-browser/scripts'))
import execution_records
from prepared_documents import Documents, publish, write_json
from project_paths import project_file
import project_resources as resources
from songssx_browser import scene_playbacks
from video_metadata import probe


def task_output(project, directory):
    checked = execution_records.read(directory / '执行检查报告.json')
    state = execution_records.read(directory / '后台任务状态.json')
    result = execution_records.read(directory / '结果收尾报告.json')
    prepared = checked['prepared_input']
    plan = prepared['video_plan']
    if (not checked.get('ok') or state.get('status') != 'completed'
            or not state.get('id') or state['id'] != result.get('task_id')
            or result.get('adapter') != 'technical' or result.get('status') != 'registered'
            or prepared['task_type'] != TASK_TYPE or plan['workflow_id'] != WORKFLOW
            or project_file(project, prepared['record_dir'], recorded=True) != directory):
        raise ValueError('须使用已完成并取回的 Songssx 场次执行记录')
    target, = prepared['outputs']
    item, = result['items']
    actual = project_file(project, item['path'], recorded=True)
    if (item.get('technical') is not True or actual.suffix.lower() != '.mp4'
            or project_file(project, target['path'], recorded=True) != actual):
        raise ValueError('取回文件与本次执行的 MP4 输出不符')
    return plan, actual, state['id']


def round_scene(project, index, data, number, scene, segment):
    matches = [row for row in data['rounds'] if row['number'] == number]
    if len(matches) != 1:
        raise ValueError(f'找不到唯一的第 {number} 轮')
    row = matches[0]
    if row.get('review_only'):
        raise ValueError('只供联调审阅的轮次不能接续制作返修')
    if 'scenes' in row:
        row = row['scenes'].get(scene, {})
    elif data.get('scene') and data['scene'] != scene:
        raise ValueError('轮次场次与返修场次不符')
    segment_row = next((item for item in row.get('segments', []) if item['id'] == segment), None)
    if segment_row is None:
        raise ValueError('本轮场次缺少返修 GEN 对应的原分段：' + segment)
    if execution := row.get('songssx_execution'):
        return row, execution, None
    if index.name == '制作轮次.json' and row.get('batches') and segment_row.get('file'):
        sys.path.insert(0, str(SKILLS.parents[1] / '工作区浏览服务'))
        for skill in ('iris-commercial-production', 'studio-h3-aimixer'):
            sys.path.insert(0, str(SKILLS / skill / 'scripts'))
        from iris_workbench import scene_segments, segment_rows

        plan = project_file(project, (row.get('plan') or row['storyboard'])['file'], recorded=True)
        groups = scene_segments([item['id'] for item in row['segments']], segment_rows(plan.read_text('utf-8-sig')))
        if segment not in groups.get(scene, []):
            raise ValueError('返修 GEN 不属于本轮指定的场次')
        return row, None, segment_row['file']
    raise ValueError('本轮缺少原 Songssx 时间轴记录')


def frame_count(media):
    count = media['frames']
    if media['frame_rate'] != FPS or not count or not count.is_integer():
        raise ValueError(f'须为可读取准确帧数的 {FPS} fps 视频')
    return int(count)


def interval(value, limit):
    if (not isinstance(value, list) or len(value) != 2
            or any(type(frame) is not int for frame in value)
            or not 0 <= value[0] < value[1] <= limit):
        raise ValueError('帧区间须为有效的 [起帧, 止帧)，从 0 开始且不含止帧')
    return tuple(value)


def ffmpeg(*arguments):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', *map(str, arguments)], check=True)


def splice(source, patch, destination, original, cut, clip, audio):
    start, end = cut
    left, right = clip
    total = frame_count(original)
    # Each tuple gives the input stream, source frame range, and destination frame range.
    pieces = [(0, 0, start, 0, start), (1, left, right, start, end), (0, end, total, end, total)]
    pieces = [piece for piece in pieces if piece[1] != piece[2]]
    filters, video_labels, audio_labels = [], [], []
    for i, (track, lo, hi, target_lo, target_hi) in enumerate(pieces):
        source_count, target_count = hi - lo, target_hi - target_lo
        video = f'[{track}:v:0]trim=start_frame={lo}:end_frame={hi}'
        if source_count != target_count:
            # Sample both endpoints, and space the remaining selected frames evenly between them.
            video += f",select='eq(n,floor(selected_n*{source_count - 1}/{target_count - 1}+0.5))'"
        label = f'[v{i}]'
        filters.append(video + f',setpts=N/({FPS}*TB)' + label)
        video_labels.append(label)
        if audio == 'replacement':
            rate = int(original['audio'][0]['sample_rate'])
            target_samples = round(target_hi * rate / FPS) - round(target_lo * rate / FPS)
            audio_filter = (f'[{track}:a:0]aresample={rate},'
                            f'atrim=start_sample={round(lo * rate / FPS)}:end_sample={round(hi * rate / FPS)},'
                            'asetpts=N/SR/TB')
            if source_count != target_count:
                audio_filter += f',atempo={source_count / target_count:.12g}'
            label = f'[a{i}]'
            filters.append(audio_filter + f',apad=whole_len={target_samples},'
                           f'atrim=end_sample={target_samples},asetpts=N/SR/TB' + label)
            audio_labels.append(label)
    filters.append(''.join(video_labels) + f'concat=n={len(pieces)}:v=1:a=0[v]')
    if audio == 'replacement':
        filters.append(''.join(audio_labels) + f'concat=n={len(pieces)}:v=0:a=1[a]')
        audio_args = ['-map', '[a]', '-c:a', 'aac', '-b:a', '192k']
    elif original['audio']:
        audio_args = ['-map', '0:a:0', '-c:a', 'copy']
    else:
        audio_args = []
    ffmpeg('-i', source, '-i', patch, '-filter_complex', ';'.join(filters), '-map', '[v]',
           '-r', FPS, '-c:v', 'libx264', '-preset', 'fast', '-crf', 18, '-pix_fmt', 'yuv420p',
           *audio_args, '-movflags', '+faststart', destination)


def verify(destination, original):
    output = probe(destination)
    if (frame_count(output) != frame_count(original)
            or (output['width'], output['height']) != (original['width'], original['height'])
            or abs(output['duration'] - frame_count(original) / FPS) > 0.001
            or bool(output['audio']) != bool(original['audio'])):
        raise ValueError('返修整场的尺寸、帧数、时长或音轨与原时间轴不符')
    if output['audio']:
        stream = output['audio'][0]
        if abs(float(stream['duration']) - frame_count(output) / FPS) > 1 / FPS:
            raise ValueError('返修整场音轨时长与视频相差超过一帧')
    ffmpeg('-i', destination, '-map', '0:v:0', '-map', '0:a:0?', '-f', 'null', '-')


def repair(project, spec):
    required = {'source', 'record_dir', 'round_index', 'round', 'scene', 'run', 'frames', 'audio'}
    if missing := required - spec.keys():
        raise ValueError('接回计划缺少：' + '、'.join(sorted(missing)))
    if unknown := spec.keys() - required - {'clip_frames', 'fit'}:
        raise ValueError('接回计划有未知字段：' + '、'.join(sorted(unknown)))
    number, scene, run, audio = (spec[key] for key in ('round', 'scene', 'run', 'audio'))
    if (type(number) is not int or number < 1 or not re.fullmatch(r'[SC]\d{3,}|whole', scene)
            or not re.fullmatch(r'R\d{3,}', run) or audio not in ('source', 'replacement')
            or spec.get('fit', 'exact') not in ('exact', 'retime')):
        raise ValueError('轮次、场次、批次、音轨或长度处理设置无效')
    project = Path(project).resolve()
    source, directory, index = (project_file(project, spec[key]) for key in ('source', 'record_dir', 'round_index'))
    patch_plan, patch, task_id = task_output(project, directory)
    gen, = patch_plan['segments']
    document = Documents(project)
    snapshot = document.read(index)
    if snapshot is None:
        raise FileNotFoundError(index)
    data = execution_records.strict_json(snapshot)
    row, native_execution, native_file = round_scene(project, index, data, number, scene, gen['p'])
    if native_file is not None:
        native_ref = resources.reference(project, native_file)
        if not native_ref or not native_ref.get('producer'):
            raise ValueError('本轮原 Songssx 视频缺少固定资源版本或生成记录')
        native_execution = native_ref['producer']
        if not directory.is_relative_to(index.parent):
            raise ValueError('Iris 替换段执行记录须属于本作品的生产目录')
    native_plan, native_source, _ = task_output(project, project_file(project, native_execution, recorded=True))
    native_ref = resources.reference(project, native_source)
    source_ref = resources.reference(project, source)
    native_timing = [(gen['p'], gen['planned_seconds']) for gen in native_plan['segments']]
    round_timing = [(item['id'], item['duration']) for item in row['segments']
                    if item['id'] in {identity for identity, _ in native_timing}]
    if (native_plan.get('gap_repair') or native_timing != round_timing or not source_ref or not native_ref
            or native_ref['resource_id'] != source_ref['resource_id']
            or native_file is not None and project_file(project, native_file, recorded=True) != native_source
            or gen['p'] not in [row['p'] for row in native_plan['segments']]):
        raise ValueError('原片须为本轮原 Songssx 时间轴对应的整场资源版本')
    original, replacement = probe(source), probe(patch)
    total, generated = frame_count(original), frame_count(replacement)
    if (total != native_plan['segments'][-1]['output_frames'][1] or gen['output_frames'] != [0, generated]
            or (original['width'], original['height']) != (replacement['width'], replacement['height'])):
        raise ValueError('原片或取回段的帧数、尺寸与执行记录不符')
    cut = interval(spec['frames'], total)
    clip = interval(spec.get('clip_frames', [0, generated]), generated)
    target_length, clip_length = cut[1] - cut[0], clip[1] - clip[0]
    gap = patch_plan.get('gap_repair')
    requested_frames = gap['replacement_frames'] if gap else round(gen['planned_seconds'] * FPS)
    if target_length != requested_frames or target_length == total:
        raise ValueError('返修窗口须与单 GEN 请求的原片帧数相符，且至少保留一侧原片')
    if gap and (cut[0] == 0 or cut[1] == total or clip != (0, generated)):
        raise ValueError('双边界补生成须保留两侧原片与补生成段的首尾帧')
    if clip_length < target_length or (clip_length != target_length and
                                       (spec.get('fit') != 'retime' or target_length < 2)):
        raise ValueError('取回片段帧数与窗口不同，请明确选帧或确认 fit=retime')
    if len(original['audio']) > 1 or (audio == 'replacement' and (
            not original['audio'] or len(replacement['audio']) != 1
            or original['audio'][0]['channels'] != replacement['audio'][0]['channels'])):
        raise ValueError('局部替换音轨须为原片与替换段各一条声道数相同的音轨')
    record = directory.relative_to(project).as_posix()
    key = record + '/局部返修接回'
    recipe = dict(task_id=task_id, round_index=index.relative_to(project).as_posix(), round=number,
                  scene=scene, run=run, source=source_ref['file'], patch=patch.relative_to(project).as_posix(),
                  frames=list(cut), clip_frames=list(clip), audio=audio)
    receipt = directory / '局部返修接回.json'
    with resources.index_lock(project):
        stored = json.loads(receipt.read_text('utf-8')) if receipt.exists() else {}
        if stored and stored['input'] != recipe:
            raise ValueError('本次执行已有不同的接回记录，请核对原记录或另起执行')
        existing = resources.read_index(project)['outputs'].get(key)
        current = scene_playbacks(row.get('review_outputs', [])).get(scene)
        if current and (existing is None or current.get('file') != existing):
            raise ValueError('本轮场次已有其他主播放，请核对后再接回')
        if current and current == stored.get('output') and (project / existing).is_file():
            return {**current, 'round': number, 'frames': total, 'fps': FPS}
        if not stored:
            write_json(receipt, {'input': recipe})

    candidate = project / existing if existing else None
    if candidate is None or not (candidate.parent / '版本信息.json').is_file():
        with TemporaryDirectory(prefix='songssx-repair-') as temporary:
            result = Path(temporary) / f'{scene}-{run}-返修整场.mp4'
            splice(source, patch, result, original, cut, clip, audio)
            verify(result, original)
            ref = resources.register(project, result, resource_id=source_ref['resource_id'], parent=source,
                                     origin='generated', producer=record, key=key,
                                     source_range=(cut[0] / FPS, target_length / FPS))
            candidate = project / ref['file']
    else:
        verify(candidate, original)
        ref = resources.reference(project, candidate)

    output = {'label': f'{run} 返修整场 {ref["version"]}', 'file': ref['file'],
              'playback': {'scene': scene, 'run': run, 'stage': '场次生成'}}
    with resources.index_lock(project):
        # Check the same snapshot used to resolve the timeline before replacing the round document.
        if index.read_text('utf-8-sig') != snapshot:
            raise ValueError('制作轮次在接回期间有更新，请用同一计划重试登记')
        outputs = row.setdefault('review_outputs', [])
        if scene not in scene_playbacks(outputs):
            outputs.append(output)
            document.put(index, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
            publish(project, document.writes())
        write_json(receipt, {'input': recipe, 'output': output, 'frames': total, 'fps': FPS})
    return {**output, 'round': number, 'frames': total, 'fps': FPS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    arguments = parser.parse_args()
    try:
        result = repair(arguments.project, execution_records.strict_json(arguments.plan.read_bytes()))
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Songssx 局部返修接回失败：{error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
