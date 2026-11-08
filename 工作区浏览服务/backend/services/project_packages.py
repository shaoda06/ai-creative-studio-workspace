"""Build a draft package from explicit project-scoped media, without business parsing."""
import json

from pydantic import BaseModel, Field

from backend.services.episode_downloads import zip_response


class Media(BaseModel):
    file: str
    member: str
    timeline: bool = True


class Manifest(BaseModel):
    name: str = Field(min_length=1)
    media: list[Media] = Field(min_length=1)


def package_response(projects, name, path, archive_format):
    manifest = projects.file(name, path)
    if not manifest.name.endswith('.jianying.json'):
        raise ValueError('剪映打包清单须以.jianying.json结尾')
    spec = Manifest.model_validate(json.loads(manifest.read_text('utf-8-sig')))
    files = [(projects.file(name, item.file), item.member) for item in spec.media]
    timeline = {item.member for item in spec.media if item.timeline}
    return zip_response(files, spec.name + '.zip', archive_format, timeline_members=timeline)
