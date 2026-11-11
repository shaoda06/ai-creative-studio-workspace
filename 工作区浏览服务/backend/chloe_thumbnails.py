"""Build disposable WebP previews from exact shared-image versions."""
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import HTTPException
from fastapi.responses import FileResponse
from PIL import Image, ImageOps

import project_resources as resources

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
THUMBNAIL_EDGE = 768


def thumbnail_url(original):
    return f'{original}?thumbnail={THUMBNAIL_EDGE}'


def thumbnail_response(space, source, edge):
    if edge != THUMBNAIL_EDGE or source.suffix.lower() not in IMAGE_EXTENSIONS:
        raise HTTPException(404, '没有这种图片缩略图')
    owner = space.root / '综合资料'
    ref = resources.reference(owner, source)
    if not ref or resources.local(owner, ref['file']) != source:
        raise HTTPException(404, '缩略图需要准确的图片资源版本')
    directory = space.runtime / 'thumbnails' / str(edge) / ref['resource_id']
    cached = directory / f'{ref["version"]}.webp'
    if not cached.is_file():
        directory.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            ImageOps.exif_transpose(image, in_place=True)
            if image.mode == 'P':
                image = image.convert('RGBA')
            image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
            temporary = None
            try:
                with NamedTemporaryFile(dir=directory, suffix='.tmp', delete=False) as stream:
                    temporary = Path(stream.name)
                    image.save(stream, 'WEBP', quality=82, icc_profile=image.info.get('icc_profile'))
                # Publish a complete file without replacing another request's result.
                try:
                    os.link(temporary, cached)
                except FileExistsError:
                    pass
            finally:
                if temporary is not None:
                    temporary.unlink()
    return FileResponse(cached, media_type='image/webp', headers={
        'Cache-Control': 'private, max-age=86400',
        'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': 'sandbox',
    })
