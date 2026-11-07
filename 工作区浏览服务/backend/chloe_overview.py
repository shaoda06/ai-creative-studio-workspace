"""Read-only projection of Chloe's fixed documents."""
from pathlib import Path
import sys

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL.parent / '.agents/skills/chloe-positioning/scripts'))
from chloe_documents import read_document, records, template


def account_overview(root: Path):
    direction = read_document(root, root/'综合资料/账号定位.md',
                              template('chloe-positioning', '账号定位模板.md'), {})
    videos = []
    for path in sorted((root/'projects').glob('V*-*/README.md')):
        identity, title = path.parent.name.split('-', 1)
        doc = read_document(root, path, template('chloe-creative', '视频README模板.md'),
                            {'identity': identity, 'title': title})
        videos.append({'progress': fields(doc, '定位与当前进度')})
    return {'direction': fields(direction, '账号方向'), 'videos': videos}


def fields(doc, heading):
    return {row['字段']: row['内容'] for row in records(doc, heading)}
