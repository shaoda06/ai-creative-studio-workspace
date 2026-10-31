"""Download selected approved videos and stage-specific director files."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi.responses import FileResponse
import sys

_SKILL = Path(__file__).resolve().parents[3] / ".agents/skills/nora-drama-handoff/scripts"
sys.path.insert(0, str(_SKILL))
from drama_delivery import (STAGES, KINDS, VideoFiles, video_archive_name, video_member_name, indexed_episode, append_revision, completed_episode_videos, resources)
sys.path.insert(0, str(_SKILL.parents[1] / 'nora-jianying/scripts'))
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


def zip_response(files, filename, archive_format='zip'):
    # Videos are already compressed. Keep their original bytes.
    DOWNLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        with NamedTemporaryFile(dir=DOWNLOAD_DIRECTORY, prefix='videos-', suffix='.zip', delete=False) as archive:
            path = Path(archive.name)
        stack.callback(path.unlink)
        members = [member for _, member in files]
        if len(set(members)) != len(members):
            raise ValueError('同一分段存在多个已采用，请核对采用记录后重新下载')
        jianying_export.export_archive(files, path, Path(filename).stem,
                                       getattr(files, 'timeline_members', None), archive_format)
        if archive_format == 'jypack':
            filename = str(Path(filename).with_suffix('.jypack'))
        response = VideoZipResponse(archive.name, media_type=(
            'application/vnd.bytedance.jypack' if archive_format == 'jypack' else 'application/zip'), filename=filename)
        stack.pop_all()
    return response
