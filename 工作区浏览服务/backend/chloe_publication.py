"""HTTP access to Chloe's publication adapter and its explicitly referenced media."""
from pathlib import Path
import sys
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from backend.chloe_production import workspace
from backend import chloe_overview  # Load the shared Chloe document reader.

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'.agents/skills/chloe-handoff/scripts'))
import chloe_publication_browser as publication

router = APIRouter(prefix='/publication-videos')
write_router = APIRouter(prefix='/publication-videos')


@router.get('')
def listing(request: Request):
    space = workspace(request)
    try:
        return publication.listing(space.root, space.api)
    except (ValueError, OSError) as error:
        raise HTTPException(409, '发布资料读取失败：'+str(error)) from error


@router.get('/{name}')
def detail(name: str, request: Request):
    space = workspace(request)
    try:
        return publication.detail(space.root, name, space.api)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except (ValueError, OSError) as error:
        raise HTTPException(409, '发布资料读取失败：'+str(error)) from error


@write_router.post('/{name}/files', status_code=201)
def upload_final(name: str, request: Request, file: Annotated[UploadFile, File()]):
    space = workspace(request)
    try:
        return publication.import_final(space.root, name, file.filename, file.file)
    except FileExistsError as error:
        raise HTTPException(409, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, '成片录入失败：'+str(error)) from error
    except OSError as error:
        raise HTTPException(503, '成片录入失败：'+str(error)) from error


@router.get('/{name}/files/{key:path}')
def media(name: str, key: str, request: Request, download: bool = False):
    space = workspace(request)
    try:
        target = publication.media_file(space.root, name, key)
        return FileResponse(target, filename=target.name,
                            content_disposition_type='attachment' if download else 'inline',
                            headers={'X-Content-Type-Options': 'nosniff'})
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(404, str(error)) from error


@write_router.delete('/{name}/files/{key:path}')
def delete_final(name: str, key: str, request: Request):
    space = workspace(request)
    try:
        publication.delete_final(space.root, name, key)
        return {'ok': True}
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except (ValueError, OSError) as error:
        raise HTTPException(409, '成片删除失败：'+str(error)) from error
