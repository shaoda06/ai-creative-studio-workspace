"""Select current approved drama deliverables in their actual business order."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'nora-drama-production/scripts'))
from drama_video_products import default_product

STAGES = {'后处理': '03-后处理', '二采': '02-二采', '一采': '01-一采'}
KINDS = {'videos': '已采用视频', 'canvas': '画布'}


def video_archive_name(name, episode):
    label = episode if episode in ('片头', '片尾') else f'第{int(episode[2:])}集'
    return f'{name}-{label}-已采用视频.zip'


def video_member_name(path, scene_number, segment_number):
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


def completed_episode_videos(store, name, episode, data):
    selected = indexed_episode(episode, data)
    if not selected['productionComplete']:
        raise ValueError('本集制作尚未完成')
    if not selected['scenes'] or selected.get('productionIssues'):
        raise ValueError('本集分段资料尚未齐备')
    files = VideoFiles()
    for scene_number, scene in enumerate(selected['scenes'], 1):
        segments = selected['segments'][scene]
        if not segments:
            raise ValueError('本集分段资料尚未齐备')
        for segment_number, segment in enumerate(segments, 1):
            videos = [video for video in segment['videos'] if video['stage'] == '后处理' and video['approved']]
            if len(videos) != 1:
                raise ValueError('本集尚未全部批准后处理已采用')
            append_revision(files, store, name, videos[0], scene_number, segment_number)
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
