"""Read-only HTTP and shared document rendering for Chloe review records."""
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from backend.chloe_production import workspace
from backend.chloe_publication import publication  # Register shared document/asset dependencies.
from backend.chloe_models import linked_html
from backend.parsers import documents

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'.agents/skills/chloe-review/scripts'))
import chloe_review_browser as review

router = APIRouter(prefix='/reviews')


def overview(root, api):
    data, allowed = review.read(root)
    base = api+'/reviews'
    rows = data['conclusions'] + data['trials']
    for video in data['videos']:
        video['cover'] = base+'/files/'+quote(video['coverKey'], safe='/') if video['coverKey'] else None
        rows += video['reviews'] + video['publications'] + [r for s in video['samples'] for r in s['rows']]
    for row in rows:
        row['html'] = {k: linked_html(f'[{k}](<{v}>)' if urlsplit(v).scheme in {'http', 'https'} and not any(c.isspace() for c in v) else v, row['source'], allowed, base) for k, v in row['fields'].items()}
    return data


@router.get('')
def listing(request: Request):
    space = workspace(request)
    try:
        return overview(space.root, space.api)
    except (ValueError, OSError) as error:
        raise HTTPException(409, '复盘资料读取失败：'+str(error)) from error


@router.get('/document')
def document(path: str, request: Request):
    space = workspace(request)
    try:
        target = review.file(space.root, path)
        if target.suffix.lower() == '.md':
            _, allowed = review.read(space.root)
            return {'title': target.stem, 'html': linked_html(target.read_text('utf-8-sig'), path, allowed, space.api+'/reviews')}
        return documents.plain_text_preview(target)[0]
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(404, str(error)) from error


@router.get('/files/{key:path}')
def file(key: str, request: Request, download: bool = False):
    space = workspace(request)
    try:
        target = review.file(space.root, key)
        return FileResponse(target, filename=target.name,
                            content_disposition_type='attachment' if download else 'inline',
                            headers={'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': 'sandbox'})
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(404, str(error)) from error
