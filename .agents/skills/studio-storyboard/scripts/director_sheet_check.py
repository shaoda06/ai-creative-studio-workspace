"""Check a director-sheet execution plan against its explicit source; never write or generate."""
import argparse
import json
from pathlib import Path
import re
from storyboard_fields import read_shots

TEMPLATE = Path(__file__).resolve().parents[1] / 'templates/导演分镜表模板.md'
COLUMNS = tuple(re.search(r'^\| 镜号 .*$', TEMPLATE.read_text('utf-8'), re.M)[0].strip('|').split(' | '))
COLUMNS = tuple(value.strip() for value in COLUMNS)


def check_plan(path):
    path = Path(path)
    plan = json.loads(path.read_text('utf-8-sig'))
    for key in ('object', 'source', 'source_version', 'chart_version'):
        if not isinstance(plan[key], str) or not plan[key].strip():
            raise ValueError('制作计划缺少实际' + key)
    if type(plan['candidate']) is not int or plan['candidate'] < 1:
        raise ValueError('候选编号须为正整数')
    source = (path.parent / plan['source']).resolve()
    shots = read_shots(source.read_text('utf-8-sig'), tuple(plan['extra_fields']))
    ids = [shot['fields']['镜号'] for shot in shots]
    if len(ids) != len(set(ids)):
        raise ValueError('来源分镜镜号重复')
    selected = plan['shot_ids']
    if not selected or len(selected) != len(set(selected)) or selected != [s for s in ids if s in selected]:
        raise ValueError('制作范围镜号未知、重复或顺序错误')
    lookup = {shot['fields']['镜号']: shot['fields'] for shot in shots}
    covered = []
    for number, page in enumerate(plan['pages'], 1):
        if page['page'] != number or not 1 <= len(page['rows']) <= 6:
            raise ValueError('页码须连续且每页1至6镜')
        for row in page['rows']:
            if tuple(row) != COLUMNS or any(not isinstance(v, str) or not v.strip() for v in row.values()):
                raise ValueError('导演表必须按公共八列顺序填写完整内容')
            identity = row['镜号']
            if identity not in lookup:
                raise ValueError('导演表含未知镜号：' + identity)
            for key in ('景别', '运镜', '台词', '音效', '时长'):
                if row[key] != lookup[identity][key]:
                    raise ValueError(identity + '：' + key + '与源字段完整原文不一致')
            covered.append(identity)
    if covered != selected:
        raise ValueError('分页镜头遗漏、重复或顺序与制作范围不一致')
    return {'pages': len(plan['pages']), 'shots': len(covered), 'source': str(source),
            'source_version': plan['source_version'], 'chart_version': plan['chart_version']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(check_plan(args.plan), ensure_ascii=False))


if __name__ == '__main__':
    main()
