"""Prepare RIFE first when selected, then split and join the RelayVSR task group."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory

from video_workflow import assemble_output, assemble_relayvsr, plan_output
from execution_records import read, stamp
from project_paths import project_file

SEGMENT_SECONDS = 10
VIDEO_PLAN = {'adapter': 'technical', 'metadata': 'ffprobe'}


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', *map(str, args)], check=True)


def media(path, *, count=False):
    args = ['ffprobe', '-v', 'error', '-of', 'json']
    if count:
        args.append('-count_frames')
    data = json.loads(subprocess.check_output([*args, '-show_streams', str(path)]))
    video = next((stream for stream in data['streams']
                  if stream['codec_type'] == 'video' and not stream.get('disposition', {}).get('attached_pic')), None)
    if video is None:
        raise ValueError(f'{path.name} 没有可处理的主视频轨')
    return video, [stream for stream in data['streams'] if stream['codec_type'] == 'audio']


def save_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def children(data, start, end):
    while start < end:
        size, kind = struct.unpack_from('>I4s', data, start)
        if size < 8 or start + size > end:
            raise ValueError('裁剪输出的 MP4 容器结构无效')
        yield kind, start + 8, start + size
        start += size


def box(data, start, end, name):
    for kind, payload, limit in children(data, start, end):
        if kind == name:
            return payload, limit
    raise ValueError(f'裁剪输出的 MP4 缺少 {name.decode()}')


def trim(source, target, start, frames, fps):
    duration = Fraction(frames, fps)
    ffmpeg('-ss', f'{float(Fraction(start, fps)):.9f}', '-i', source, '-t', f'{float(duration):.9f}',
           '-map', '0:V:0', '-an', '-c', 'copy', '-movie_timescale', fps.numerator, '-movflags', '+faststart', target)
    # Keep any encoded reference frames at the cut while limiting the displayed interval.
    data = bytearray(target.read_bytes())
    movie = box(data, 0, len(data), b'moov')
    header, _ = box(data, *movie, b'mvhd')
    track = box(data, *movie, b'trak')
    track_header, _ = box(data, *track, b'tkhd')
    edit, _ = box(data, *box(data, *track, b'edts'), b'elst')
    if any(data[offset] for offset in (header, track_header, edit)) or struct.unpack_from('>I', data, edit + 4)[0] != 1:
        raise ValueError('本地裁剪输出需要单段 MP4 播放区间')
    ticks = frames * fps.denominator
    struct.pack_into('>I', data, header + 16, ticks)
    struct.pack_into('>I', data, track_header + 20, ticks)
    struct.pack_into('>I', data, edit + 8, ticks)
    target.write_bytes(data)
    actual, _ = media(target, count=True)
    if (int(actual.get('nb_read_frames', 0)) != frames or Fraction(actual['start_time']) != 0
            or Fraction(actual['duration_ts']) * Fraction(actual['time_base']) != duration):
        raise ValueError(f'{target.name} 的本地无转码裁剪未对齐帧数和时长')


def output(node, key, path, root):
    return dict(node_id=node, output_key=key, index=0, path=path.relative_to(root).as_posix(), response_name='取回.json')


def prepare(root, source, record, target, authorization, fps=None):
    if not authorization.strip():
        raise ValueError('请提供本次执行授权')
    if target.suffix.lower() != '.mp4':
        raise ValueError('最终输出文件须使用 .mp4 扩展名')
    if record.exists() or target.exists() or source == target:
        raise FileExistsError('执行目录和结果文件须为本次未占用的路径')
    source_stamp = list(stamp(source))
    video, rate, frames = read_source(source)
    if fps is None:
        return prepare_segments(root, source, record, target, authorization, video, rate, frames, source, source_stamp)
    configuration = plan_output(dict(width=video['width'], height=video['height'], frame_rate=float(rate)), 'original', fps)
    if configuration['reuse']:
        return prepare_segments(root, source, record, target, authorization, video, rate, frames, source, source_stamp)

    folder = record / '整条插帧'
    intermediate = folder / '补帧中间片.mp4'
    if intermediate == target:
        raise ValueError('最终输出与补帧中间片同名，请另选输出路径')
    source_path = source.relative_to(root).as_posix()
    placeholder = 'planned/rife-source.mp4'
    canvas = assemble_output(placeholder, f'{record.name}/RIFE', configuration)
    manifest = dict(group_title=f'{target.stem} · RIFE 插帧', tasks=[
        dict(task_type='video-postprocess', title=f'{target.stem} · RIFE 插帧', authorization=authorization,
             record_dir=folder.relative_to(root).as_posix(), output_nodes=['16'], video_plan=VIDEO_PLAN,
             canvas=(folder / '内容画布.workflow.json').relative_to(root).as_posix(),
             references=[dict(file=source_path, placeholder=placeholder)],
             outputs=[output('16', 'gifs', intermediate, root)])])
    record.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.relayvsr-', dir=record.parent) as temporary:
        work = Path(temporary) / '准备'
        work.mkdir()
        (work / folder.name).mkdir()
        save_json(work / folder.name / '内容画布.workflow.json', canvas)
        save_json(work / '插帧任务清单.json', manifest)
        save_json(work / '联动计划.json', dict(
            source=source_path, source_stamp=source_stamp, size=[video['width'], video['height']],
            duration=str(Fraction(frames, rate)), fps=fps, output=target.relative_to(root).as_posix(),
            authorization=authorization, rife_record=folder.relative_to(root).as_posix(),
            rife_output=intermediate.name))
        work.rename(record)
    return dict(status='prepared', stage='rife', tasks=1, plan=(record / '插帧任务清单.json').relative_to(root).as_posix())


def read_source(source):
    video, _ = media(source, count=True)
    rate = Fraction(video['avg_frame_rate'])
    frames = int(video.get('nb_read_frames', 0))
    if not frames or rate < 1 or rate != Fraction(video['r_frame_rate']):
        raise ValueError('RelayVSR 分段输入须为可读的恒定帧率视频')
    return video, rate, frames


def prepare_after_rife(root, record):
    plan = read(record / '联动计划.json')
    original = project_file(root, plan['source'])
    target = project_file(root, plan['output'])
    segments = record / '超分分段'
    if segments.exists() or target.exists():
        raise FileExistsError('超分分段或最终输出已存在，请使用原任务清单接续')
    report = read(project_file(root, plan['rife_record']) / '结果收尾报告.json')
    item, = report['items']
    source = project_file(root, item['path'])
    source_stamp = item['metadata']['stamp']
    if item['identity'] != plan['rife_output'] or list(stamp(source)) != source_stamp:
        raise ValueError('补帧取回文件与原报告不符')
    video, rate, frames = read_source(source)
    expected_fps = Fraction(str(plan['fps']))
    duration = Fraction(plan['duration'])
    if ([video['width'], video['height']] != plan['size'] or rate != expected_fps
            or abs(Fraction(frames, rate) - duration) >= Fraction(1, rate)):
        raise ValueError('补帧结果的尺寸、帧率或时长与联动计划不符')
    return prepare_segments(root, source, segments, target, plan['authorization'], video, rate, frames,
                            original, plan['source_stamp'], source_stamp)


def prepare_segments(root, source, record, target, authorization, video, rate, frames, original,
                     original_stamp, source_stamp=None):
    if source_stamp is None:
        source_stamp = original_stamp
    if list(stamp(original)) != original_stamp:
        raise ValueError('原片已变化，请核对音轨来源')
    width, height = 2 * video['width'], 2 * video['height']

    def relative(path):
        return path.relative_to(root).as_posix()

    record.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.relayvsr-', dir=record.parent) as temporary:
        work = Path(temporary) / '准备'
        work.mkdir()
        tasks, segments = [], []
        limit = int(SEGMENT_SECONDS * rate)
        for index, start in enumerate(range(0, frames, limit), 1):
            part = f'分段-{index:03d}'
            local = work / part
            local.mkdir()
            folder = record / part
            count = min(limit, frames - start)
            filename = f'{part}-RelayVSR.mp4'
            if target in (folder / '源片.mp4', folder / filename):
                raise ValueError('最终输出与分段文件同名，请另选输出路径')
            trim(source, local / '源片.mp4', start, count, rate)
            placeholder = f'planned/{part}.mp4'
            save_json(local / '内容画布.workflow.json', assemble_relayvsr(placeholder, f'{record.name}/{part}'))
            tasks.append(dict(task_type='video-postprocess', title=f'{target.stem} · RelayVSR {part}',
                              authorization=authorization, record_dir=relative(folder),
                              canvas=relative(folder / '内容画布.workflow.json'), output_nodes=['106'],
                              references=[dict(file=relative(folder / '源片.mp4'), placeholder=placeholder)],
                              outputs=[output('106', 'images', folder / filename, root)], video_plan=VIDEO_PLAN))
            segments.append(dict(start=start, frames=count, record_dir=relative(folder), result=filename))
        save_json(work / '任务清单.json', dict(group_title=f'{target.stem} · RelayVSR 2倍超分', tasks=tasks))
        save_json(work / '分段计划.json', dict(source=relative(original), source_stamp=original_stamp,
                  picture_source=relative(source), merged=relative(target),
                  size=[width, height], fps=str(rate), frames=frames, segments=segments))
        if list(stamp(source)) != source_stamp:
            raise ValueError('裁剪期间源片已变化，请从实际源片重新准备')
        work.rename(record)
    return dict(status='prepared', stage='relayvsr', tasks=len(tasks), plan=relative(record / '任务清单.json'))


def join(root, record):
    plan = json.loads((record / '分段计划.json').read_text(encoding='utf-8'))
    source = project_file(root, plan['source'])
    target = project_file(root, plan['merged'])
    if target.exists():
        raise FileExistsError(target)
    if list(stamp(source)) != plan['source_stamp']:
        raise ValueError('源片已变化，请核对原始音轨')
    _, source_audio = media(source)
    fps = Fraction(plan['fps'])
    width, height = plan['size']
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.relayvsr-', dir=target.parent) as directory:
        temporary = Path(directory)
        entries = ['ffconcat version 1.0']
        for index, segment in enumerate(plan['segments'], 1):
            report = read(project_file(root, segment['record_dir']) / '结果收尾报告.json')
            item, = report['items']
            raw = project_file(root, item['path'])
            received_stamp = item['metadata']['stamp']
            if list(stamp(raw)) != received_stamp:
                raise ValueError(f'分段 {index} 的取回文件已变化，请核对原报告')
            video, _ = media(raw)
            actual = (item['identity'], video['width'], video['height'],
                      Fraction(video['avg_frame_rate']), int(video.get('nb_frames', 0)))
            if actual != (segment['result'], width, height, fps, segment['frames']):
                raise ValueError(f'分段 {index} 的取回身份、分辨率、帧率或帧数不符')
            name = f'{index:04d}.mp4'
            ffmpeg('-i', raw, '-map', '0:V:0', '-an', '-c', 'copy', temporary / name)
            if list(stamp(raw)) != received_stamp:
                raise ValueError(f'拼接期间分段 {index} 的取回文件已变化')
            entries.extend([f'file {name}', f'duration {float(Fraction(segment["frames"], fps)):.9f}'])
        listing = temporary / 'segments.ffconcat'
        listing.write_text('\n'.join(entries) + '\n', encoding='ascii')
        merged = temporary / 'merged.mp4'
        ffmpeg('-f', 'concat', '-i', listing, '-i', source, '-map', '0:V:0', '-map', '1:a?',
               '-c', 'copy', '-movflags', '+faststart', merged)
        actual, audio = media(merged, count=True)
        if ((actual['width'], actual['height']) != (width, height) or Fraction(actual['avg_frame_rate']) != fps
                or int(actual.get('nb_read_frames', 0)) != plan['frames'] or len(audio) != len(source_audio)
                or abs(float(actual['duration']) - plan['frames'] / float(fps)) > 0.5 / float(fps)):
            raise ValueError('合片尺寸、帧率、帧数、时长或音轨与计划不符')
        if list(stamp(source)) != plan['source_stamp']:
            raise ValueError('拼接期间源片已变化，请核对原始音轨')
        target.hardlink_to(merged)
    return dict(status='joined', path=plan['merged'], frames=plan['frames'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    planning = commands.add_parser('prepare', help='准备首阶段任务清单，不上传')
    continuation = commands.add_parser('after-rife', help='按已取回补帧结果裁片并准备 RelayVSR 任务组')
    merging = commands.add_parser('join', help='组取回完成后按原顺序无转码拼接并封回原声')
    for command in (planning, continuation, merging):
        command.add_argument('--project', type=Path, required=True, help='实际项目根目录')
        command.add_argument('--record-dir', required=True, help='项目相对执行目录')
    planning.add_argument('--source', required=True, help='项目相对源视频')
    planning.add_argument('--output', required=True, help='项目相对最终 MP4 位置')
    planning.add_argument('--authorization', required=True, help='本次业务执行授权记录')
    planning.add_argument('--fps', type=float, help='可选补帧目标，先在源尺寸补帧；省略沿用源帧率')
    args = parser.parse_args()
    root = args.project.resolve(strict=True)
    record = project_file(root, args.record_dir)
    if args.command == 'prepare':
        result = prepare(root, project_file(root, args.source), record, project_file(root, args.output),
                         args.authorization, args.fps)
    elif args.command == 'after-rife':
        result = prepare_after_rife(root, record)
    else:
        result = join(root, record)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
