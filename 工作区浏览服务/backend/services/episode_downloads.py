"""Download explicitly selected videos and stage-specific canvases."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, ZIP_STORED

from fastapi.responses import FileResponse
import sys

_SKILL = Path(__file__).resolve().parents[3] / ".agents/skills/nora-drama-handoff/scripts"
sys.path.insert(0, str(_SKILL))
from drama_delivery import (STAGES, KINDS, VideoFiles, video_archive_name, video_member_name, indexed_episode, append_revision, completed_episode_videos, resources)
sys.path.insert(0, str(_SKILL.parents[1] / 'studio-jianying/scripts'))
import jianying_export

DOWNLOAD_DIRECTORY = Path(__file__).resolve().parents[2] / "runtime" / "downloads"

class VideoZipResponse(FileResponse):
    """Remove the request's ZIP after sending, failure, or cancellation."""

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            Path(self.path).unlink()


def clear_downloads():
    """Called once at service startup, before it accepts download requests."""
    DOWNLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for path in DOWNLOAD_DIRECTORY.glob('videos-*.zip'):
        path.unlink()
    # Remove interrupted temporary requests created by pre-retirement versions.
    for path in DOWNLOAD_DIRECTORY.glob('director-*'):
        import shutil
        shutil.rmtree(path)


def songssx_round_videos(store, name, selected, number):
    composition = next((item for item in selected.get('episodeRounds', []) if item['number'] == number), None)
    if not composition:
        raise FileNotFoundError('当前制作对象没有这个制作轮次')
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


def zip_response(files, filename, archive_format='zip', *, timeline_members=None, videos_only=False):
    # Videos are already compressed. Keep their original bytes.
    DOWNLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        with NamedTemporaryFile(dir=DOWNLOAD_DIRECTORY, prefix='videos-', suffix='.zip', delete=False) as archive:
            path = Path(archive.name)
        stack.callback(path.unlink)
        members = [member for _, member in files]
        if len(set(members)) != len(members):
            raise ValueError('同一分段存在多个已采用，请核对采用记录后重新下载')
        if videos_only and archive_format == 'zip':
            with ZipFile(path, 'w', compression=ZIP_STORED) as bundle:
                for source, member in files:
                    bundle.write(source, member)
        else:
            jianying_export.export_archive(files, path, Path(filename).stem,
                                           getattr(files, 'timeline_members', None) if timeline_members is None else timeline_members,
                                           archive_format)
        if archive_format == 'jypack':
            filename = str(Path(filename).with_suffix('.jypack'))
        response = VideoZipResponse(archive.name, media_type=(
            'application/vnd.bytedance.jypack' if archive_format == 'jypack' else 'application/zip'), filename=filename)
        stack.pop_all()
    return response
