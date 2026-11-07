"""Read-only projection of Chloe's fixed documents; demo routes use isolated fixtures."""
from pathlib import Path
import sys
from typing import Literal

from fastapi import APIRouter

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL.parent / '.agents/skills/chloe-positioning/scripts'))
from chloe_documents import read_document, records, template


def account_overview(root: Path):
    direction = read_document(root, root/'综合资料/账号定位.md',
                              template('chloe-positioning', '账号定位模板.md'), {})
    return {'direction': fields(direction, '账号方向')}


def fields(doc, heading):
    return {row['字段']: row['内容'] for row in records(doc, heading)}


router = APIRouter(prefix='/api/examples/chloe')


@router.get('/overview')
def example_overview(scenario: Literal['new', 'working'] = 'working'):
    return account_overview(TOOL/'examples/chloe-overview'/scenario)
