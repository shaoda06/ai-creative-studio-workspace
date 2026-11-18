"""Workspace-level entry; project detail and review use the common production routes."""
from pathlib import Path
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from backend.services import production
from backend.chloe_thumbnails import production_thumbnail
from backend.chloe_read_cache import read_document
from backend.chloe_overview import fields
from chloe_documents import MISSING, records, parse, media_reference, template
import project_resources as resources

router=APIRouter()


def workspace(request):
    space=request.state.workspace_space
    if space.view!='chloe-commerce':raise HTTPException(404,'本空间未接入带货视频制作')
    return space


@router.get('/production-videos')
def videos(request:Request):
    space=workspace(request)
    try:
        with resources.reuse_read_indexes():
            return [video_card(space, project['id']) for project in space.projects.discover()]
    except (ValueError,KeyError,OSError) as error:
        raise HTTPException(409,'视频制作资料读取失败：'+str(error)) from error


def video_card(space, name):
    project = space.projects.project(name)
    identity, title = name.split('-', 1)
    substitutions = {'identity': identity, 'title': title}
    doc = read_document(space.root, project / 'README.md', template('chloe-creative', '视频README模板.md'), substitutions)
    item = production.workbench(space).production_item(name, fields(doc, '定位与当前进度'))
    rounds = json.loads((project / '制作轮次.json').read_text('utf-8'))['rounds']
    source_round = rounds[-1] if rounds else None
    by_number = {row['number']: row for row in rounds}
    while source_round and 'postproduction' in source_round:
        base = source_round['base_round']
        if base >= source_round['number'] or base not in by_number:
            raise ValueError('后期轮次须引用此前存在的制作轮次')
        source_round = by_number[base]
    script = project / (source_round['script'] if source_round else '脚本.md')
    script = resources.local(project, script)
    script_doc = read_document(space.root, script, template('chloe-creative', '脚本模板.md'), substitutions)
    planned = fields(script_doc, '脚本信息')['计划时长秒']
    summary = None if planned in MISSING else {'seconds': float(planned), 'estimated': True}
    if rounds:
        outputs = {(row['执行编号'], row['输出槽位']): row['资源引用']
                   for row in records(parse((project / '制作记录.md').read_text('utf-8')), '输出记录')}
        selected = [rounds[-1]['postproduction']] if 'postproduction' in rounds[-1] else rounds[-1]['segments']
        refs = [outputs.get((entry['execution'], entry['slot'])) for entry in selected]
        if refs and all(refs):
            files = {media_reference(space.root, project / '制作记录.md', value)['file'] for value in refs}
            facts = [json.loads((space.root / file).with_name('版本信息.json').read_text('utf-8'))['facts'] for file in files]
            summary = {'seconds': sum(fact['duration_seconds'] for fact in facts), 'estimated': False}
    return {**item, 'durationSummary': summary}


@router.get('/production-files/{path:path}')
def media(path:str,request:Request,download:bool=False,thumbnail:int|None=None):
    space=workspace(request);relative=Path(path)
    if relative.is_absolute() or any(part.startswith('.') for part in relative.parts):
        raise HTTPException(404,'资源不存在')
    target=(space.root/relative).resolve()
    if not (target.is_relative_to(space.root/'综合资料/资源') or target.is_relative_to(space.root/'projects')) or not target.is_file():
        raise HTTPException(404,'资源不存在')
    # This route serves referenced media only, never workspace configuration or private task records.
    if target.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.mp4','.mov','.webm','.wav','.mp3','.m4a','.flac'}:
        raise HTTPException(404,'不是媒体文件')
    if thumbnail is not None and not download:
        return production_thumbnail(space.runtime, target, thumbnail, request)
    return FileResponse(target,filename=target.name if download else None,content_disposition_type='attachment' if download else 'inline')
