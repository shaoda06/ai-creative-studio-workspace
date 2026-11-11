"""Build disposable WebP previews from exact shared-image versions."""
import os
from pathlib import Path
import subprocess
from tempfile import NamedTemporaryFile

from fastapi import HTTPException
from fastapi.responses import FileResponse
from PIL import Image, ImageOps

import project_resources as resources

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
THUMBNAIL_EDGE = 768


def thumbnail_url(original):
    return f'{original}?thumbnail={THUMBNAIL_EDGE}'


def cached_preview(path, media_type, render):
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                render(stream)
            # Publish a complete file without replacing another request's result.
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
        finally:
            if temporary is not None:
                temporary.unlink()
    return FileResponse(path, media_type=media_type, headers={
        'Cache-Control': 'private, max-age=86400',
        'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': 'sandbox',
    })


def thumbnail_response(space, source, edge):
    if edge != THUMBNAIL_EDGE or source.suffix.lower() not in IMAGE_EXTENSIONS:
        raise HTTPException(404, '没有这种图片缩略图')
    owner = space.root / '综合资料'
    ref = resources.reference(owner, source)
    if not ref or resources.local(owner, ref['file']) != source:
        raise HTTPException(404, '缩略图需要准确的图片资源版本')
    directory = space.runtime / 'thumbnails' / str(edge) / ref['resource_id']
    cached = directory / f'{ref["version"]}.webp'

    def render(stream):
        with Image.open(source) as image:
            ImageOps.exif_transpose(image, in_place=True)
            if image.mode == 'P':
                image = image.convert('RGBA')
            image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
            image.save(stream, 'WEBP', quality=82, icc_profile=image.info.get('icc_profile'))

    return cached_preview(cached, 'image/webp', render)


def video_cover_response(runtime, source, resource_id, version):
    path = runtime / 'reference-video-covers' / resource_id / f'{version}.jpg'

    def render(stream):
        edge = THUMBNAIL_EDGE
        scale = f"scale='min({edge},iw)':'min({edge},ih)':force_original_aspect_ratio=decrease"
        try:
            frame = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(source), '-map', '0:V:0',
                                    '-frames:v', '1', '-vf', scale, '-c:v', 'mjpeg', '-q:v', '3', '-threads', '1',
                                    '-f', 'image2pipe', 'pipe:1'], capture_output=True, check=True, timeout=30).stdout
        except FileNotFoundError as error:
            raise HTTPException(503, '读取视频封面需要 FFmpeg') from error
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise HTTPException(422, '无法读取视频首帧') from error
        if not frame:
            raise HTTPException(422, '视频没有可解码的首帧')
        stream.write(frame)

    return cached_preview(path, 'image/jpeg', render)
