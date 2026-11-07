"""Workspace-level entry; project detail and review use the common production routes."""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from backend.services import production

router=APIRouter()


def workspace(request):
    space=request.state.workspace_space
    if space.view!='chloe-commerce':raise HTTPException(404,'本空间未接入带货视频制作')
    return space


@router.get('/production-videos')
def videos(request:Request):
    space=workspace(request)
    try:
        return [item for project in space.projects.discover()
                for item in production.workbench(space).items(space.projects,project['id'],space.api)]
    except (ValueError,KeyError,OSError) as error:
        raise HTTPException(409,'视频制作资料读取失败：'+str(error)) from error


@router.get('/production-files/{path:path}')
def media(path:str,request:Request,download:bool=False):
    space=workspace(request);relative=Path(path)
    if relative.is_absolute() or any(part.startswith('.') for part in relative.parts):
        raise HTTPException(404,'资源不存在')
    target=(space.root/relative).resolve()
    if not (target.is_relative_to(space.root/'综合资料/资源') or target.is_relative_to(space.root/'projects')) or not target.is_file():
        raise HTTPException(404,'资源不存在')
    # This route serves referenced media only, never workspace configuration or private task records.
    if target.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.mp4','.mov','.webm','.wav','.mp3','.m4a','.flac'}:
        raise HTTPException(404,'不是媒体文件')
    return FileResponse(target,filename=target.name if download else None,content_disposition_type='attachment' if download else 'inline')
