"""Select current approved drama deliverables in their actual business order."""
from pathlib import Path
import posixpath
import re
import sys
from urllib.parse import unquote, urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'nora-drama-production/scripts'))
from drama_video_products import default_product

STAGES = {'后处理': '03-后处理', '二采': '02-二采', '一采': '01-一采'}
KINDS = {'videos': '已采用视频', 'canvas': '画布'}


def video_archive_name(name, episode):
    label = episode if episode in ('片头', '片尾') else f'第{int(episode[2:])}集'
    return f'{name}-{label}-已采用视频.zip'


def video_member_name(path, scene_number, segment_number):
    if segment_number is None:
        return f'第{scene_number}场-已采用{path.suffix}'
    return f'第{scene_number}场-第{segment_number}段-已采用{path.suffix}'


def indexed_episode(episode, data):
    selected = next((item for item in data['catalogues']['09-剧集制作']['children']
                     if item['name'] == episode), None)
    if selected is None:
        raise FileNotFoundError('剧集不存在')
    return selected


class VideoFiles(list):
    """All revision files, with one timeline clip per segment."""
    def __init__(self):
        super().__init__()
        self.timeline_members = set()


def append_revision(files, store, name, video, scene_number, segment_number):
    primary = default_product(video)
    for product in video.get('products') or [video]:
        path = store.file(name, product['key'])
        stat = path.stat()
        if product['fileRevision'] != f'{stat.st_mtime_ns}-{stat.st_size}':
            raise ValueError('已采用文件已变化，请等待页面同步后重新下载')
        member = video_member_name(path, scene_number, segment_number)
        if product['key'] != primary['key']:
            member = f'第{scene_number}场-第{segment_number}段-{path.name}'
        else:
            files.timeline_members.add(member)
        files.append((path, member))


def delivery_records(text, source):
    """Read explicit whole-scene and direct-reuse decisions from the existing work draft."""
    section = re.search(r'^### 交付采用组合[ \t]*\n(.*?)(?=^#{1,3} |\Z)', text, re.M | re.S)
    if section is None:
        return {}
    rows = {}
    for line in section[1].splitlines():
        if not line.startswith('|'):
            continue
        cells = [cell.strip() for cell in re.split(r'(?<!\\)\|', line.strip().strip('|'))]
        if cells[0] in ('对象', '---'):
            continue
        if len(cells) != 6 or cells[0] in rows:
            raise ValueError('交付采用组合的对象须唯一且各列齐全')
        identity, number, stage, run, file, basis = cells
        link = re.fullmatch(r'\[[^\]]+\]\((<[^>]+>|[^)]+)\)', file)
        target = urlsplit(link[1].strip('<>')) if link else None
        if (not target or target.scheme or target.netloc or target.path.startswith('/') or not target.path
                or target.query or target.fragment or not re.fullmatch(r'R\d{3,}', run)
                or basis in ('', '无', '待确认', '待审核', '未批准', '—')):
            raise ValueError('交付采用组合缺少准确文件、R编号或采用依据：' + identity)
        key = posixpath.normpath(posixpath.join(posixpath.dirname(source), unquote(target.path)))
        if key.startswith('../') or key == '..':
            raise ValueError('交付采用文件超出项目范围：' + identity)
        rows[identity] = {'round': number, 'stage': stage, 'run': run, 'key': key}
    return rows


def songssx_adoption(scene_rounds, record, segments=None):
    matches = [item for item in scene_rounds
               if str(item['number']) == record['round'] and item.get('songssx', {}).get('video')]
    if len(matches) == 1:
        candidate = matches[0]
        video = candidate['songssx']['video']
        if video['url'] and all(video[key] == record[key] for key in ('stage', 'run', 'key')):
            if segments is not None and (not segments or [part['id'] for part in candidate['segments']] != segments):
                raise ValueError('整场采用轮次与当前分镜分段范围不一致')
            return video
    raise ValueError('整场采用与对应轮次已取回的文件不一致')


def delivery_selection(selected):
    scenes = selected.get('deliveryScenes', selected['scenes'])
    if not scenes or selected.get('productionIssues'):
        raise ValueError('本集分段资料尚未齐备')
    records = selected.get('deliveryRecords', {})
    episode = selected['name']
    whole = any(episode + '-' + scene in records for scene in scenes)
    result = []
    for scene_number, scene in enumerate(scenes, 1):
        scene_id = episode + '-' + scene
        segments = [segment for segment in selected['segments'][scene] if not segment.get('historical')]
        if whole:
            record = records.get(scene_id)
            if not record or record['stage'] not in ('场次生成', '后处理'):
                raise ValueError('整场交付采用尚未齐备：' + scene_id)
            video = songssx_adoption(selected['sceneRounds'][scene], record, [part['id'] for part in segments])
            result.append((scene_number, None, video))
            continue
        if not segments:
            raise ValueError('本集分段资料尚未齐备')
        for segment_number, segment in enumerate(segments, 1):
            identity = scene_id + '-' + segment['id']
            record = records.get(identity)
            if record and record['stage'] not in ('二采', '后处理'):
                raise ValueError('分段交付采用的阶段无效：' + identity)
            stage = record['stage'] if record else '后处理'
            videos = [video for video in segment['videos'] if video['stage'] == stage and video['approved']
                      and (not record or all(video[key] == record[key] for key in ('run', 'key')))]
            if len(videos) != 1:
                raise ValueError('分段交付采用尚未齐备：' + identity)
            result.append((scene_number, segment_number, videos[0]))
    return result


def completed_episode_videos(store, name, episode, data):
    selected = indexed_episode(episode, data)
    if not selected['productionComplete']:
        raise ValueError('本集制作尚未完成')
    files = VideoFiles()
    for scene_number, segment_number, video in delivery_selection(selected):
        append_revision(files, store, name, video, scene_number, segment_number)
    return files


def songssx_round_videos(store, name, episode, number, data):
    selected = indexed_episode(episode, data)
    composition = next((item for item in selected.get('episodeRounds', []) if item['number'] == number), None)
    if not composition:
        raise FileNotFoundError('本集没有这个制作轮次')
    files = []
    for scene in composition['scenes']:
        round_ = next((item for item in selected['sceneRounds'].get(scene, []) if item['number'] == number), {})
        video = round_.get('songssx', {}).get('video')
        if not video or not video['url']:
            continue
        path = store.file(name, video['key'])
        stat = path.stat()
        if video['fileRevision'] != f'{stat.st_mtime_ns}-{stat.st_size}':
            raise ValueError('本轮视频文件已变化，请刷新制作页后重新下载')
        files.append((path, f'{scene}-{video["stage"]}-{video["run"]}{path.suffix}'))
    if not files:
        raise FileNotFoundError('本轮暂无可下载的场次视频')
    return files


def resources(store, name, episode, data, scene=None):
    selected = indexed_episode(episode, data)
    if scene is not None and scene not in selected['scenes']:
        raise FileNotFoundError('场次不存在')
    result = {stage: {kind: VideoFiles() if kind == 'videos' else [] for kind in KINDS} for stage in STAGES}
    for scene_number, selected_scene in enumerate(selected['scenes'], 1):
        if scene is not None and selected_scene != scene:
            continue
        for segment_number, segment in enumerate(selected['segments'][selected_scene], 1):
            for video in segment['videos']:
                if video['approved']:
                    append_revision(result[video['stage']]['videos'], store, name, video, scene_number, segment_number)

    root = store.project(name)
    episode_root = root / '09-剧集制作' / episode
    for stage, folder in STAGES.items():
        stage_root = next((base / folder for base in (
            episode_root / '06-阶段采用视频', episode_root / '其他资料/阶段采用视频',
            episode_root / '06-生成结果') if (base / folder).is_dir()), None)
        if stage_root is None:
            continue
        for selected_scene in selected['scenes']:
            if scene is not None and selected_scene != scene:
                continue
            directory = stage_root / (selected_scene + '-场次') / '导演包'
            for source in sorted(directory.glob(episode + '-' + selected_scene + '-*.workflow.json')):
                path = store.file(name, source.relative_to(root).as_posix())
                result[stage]['canvas'].append((path, selected_scene + '-场次/导演包/' + source.name))
    return result
