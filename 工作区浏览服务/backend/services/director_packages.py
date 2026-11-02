"""Native H3 downloads use frozen project inputs and request-scoped temporary files."""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from pydantic import BaseModel, Field
from typing import Literal

from backend.services import episode_downloads

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-h3/scripts'))
import director_export


class DirectorSpec(BaseModel):
    name: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    media: dict[str, str]
    media_origin: Literal['input', 'pack'] = 'input'
    url: str | None = None
    api: str | None = None
    workflow: dict[str, dict] | None = None


def package_response(projects, name, path):
    manifest = projects.file(name, path)
    if not manifest.name.endswith('.director.json'):
        raise ValueError('导演包重建清单须以.director.json结尾')
    spec = json.loads(manifest.read_text('utf-8-sig'))
    return spec_response(projects, name, spec)


def spec_response(projects, name, spec):
    spec = DirectorSpec.model_validate(spec).model_dump(exclude_none=True)
    if ('api' in spec) == ('workflow' in spec):
        raise ValueError('导演包清单须指定一份保存的API或内嵌导出工程')
    filename = spec['name']
    if Path(filename).name != filename or not filename.endswith('.mmxpack.zip'):
        raise ValueError('导演包清单须提供不含目录的.mmxpack.zip文件名')
    root = projects.project(name)
    # Resolve all project file boundaries before contacting ComfyUI.
    media = {key: projects.file(name, value) for key, value in spec['media'].items()}
    api = projects.file(name, spec['api']) if 'api' in spec else None
    files = {**{value: media[key] for key, value in spec['media'].items()},
             **({spec['api']: api} if api is not None else {})}
    episode_downloads.DOWNLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        folder = stack.enter_context(TemporaryDirectory(prefix='director-', dir=episode_downloads.DOWNLOAD_DIRECTORY))
        target = Path(folder) / filename
        director_export.export_package(spec, files.__getitem__, root.parent.parent, target)
        response = episode_downloads.VideoZipResponse(target, media_type='application/zip', filename=filename)
        response.cleanup = stack.pop_all()
    return response
