"""Prepare Chloe director-sheet pages and reserve their record identities."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

SKILLS = Path(__file__).resolve().parents[2]
for name in ('chloe-production', 'chloe-assets', 'studio-storyboard', 'studio-imagegen'):
    sys.path.insert(0, str(SKILLS / name / 'scripts'))

from chloe_production import director_slot, document, fields
from chloe_result_records import link, now, put, rows, save
from chloe_resources import resources, video_root
from chloe_documents import media_reference
from director_sheet_check import COLUMNS, validate_plan
from imagegen_tool import generation_call
from storyboard_fields import read_shots


EXTRA_FIELDS = ('商品可见细节', '字幕', '参考需求')
PLAN_FILE = '导演表制作计划.json'
PROMPT_FILE = '导演表提示词.md'
MANIFEST_FILE = '生图参数.json'


def reference_inputs(project, record, items):
    root = project.parent.parent
    common = json.loads((project / '资源/共用引用.json').read_text('utf-8'))['references']
    inputs, paths = [], []
    for item in items:
        key = item.get('key', '不适用')
        expected = common[key] if key != '不适用' else None
        if expected is None:
            reference = item['reference']
        else:
            reference = link(record, root / expected['file'], f"共用:{expected['resource_id']}@{expected['version']}")
        actual = media_reference(root, record, reference)
        if (expected is not None and actual != expected or
                expected is None and actual['owner'] != project.relative_to(root).as_posix()):
            raise ValueError('导演表参考须绑定本视频准确资源或已登记的共用引用键')
        target = root / actual['file']
        if resources.media_kind(target) != '图片':
            raise ValueError('导演表参考必须是图片：'+str(target))
        paths.append(str(target))
        inputs.append({'输入槽位': f"Picture {len(paths)}／{item['slot']}", '共用引用键': key, '资源引用': reference})
    return inputs, paths


def chart_identity(directory, body, source_version, requested):
    sheets = [director_slot(row['输出槽位']) for row in rows(body, '输出记录')]
    history = {(sheet['version'], sheet['sourceVersion'], sheet.get('candidateNumber', 0))
               for sheet in sheets if sheet is not None}
    for path in directory.glob('*/'+PLAN_FILE):
        plan = json.loads(path.read_text('utf-8-sig'))
        history.add((plan['chart_version'], plan['source_version'], plan['candidate']))
    occupied = {int(version[1:]) for version, _, _ in history}
    if requested is not None:
        if not re.fullmatch(r'v\d{2,}', requested) or int(requested[1:]) < 1:
            raise ValueError('图表版本须为 v01 等格式')
        if int(requested[1:]) in occupied:
            raise ValueError('图表版本已使用或已预留：'+requested)
    version = requested or f'v{max(occupied, default=0)+1:02d}'
    candidate = max((n for _, source, n in history if source == source_version), default=0)+1
    return version, candidate


def page_prompt(plan, page, frame, direction, inputs):
    header = (f"{plan['object']}｜导演分镜表\n脚本 {plan['source_version']}｜图表 {plan['chart_version']}"
              f"｜第 {page['page']}／{len(plan['pages'])} 页｜" + '、'.join(row['镜号'] for row in page['rows']))
    references = '\n'.join(row['输入槽位'] for row in inputs)
    contents = '\n\n'.join('\n'.join(f'{col}：{row[col]}' for col in COLUMNS) for row in page['rows'])
    return (f'画一张宽横版中文导演分镜表。白底、黑灰铅笔速写、细线、清晰简体中文。逐字保留页头。\n{header}\n\n'
            f'列顺序为 {"｜".join(COLUMNS)}。一镜一行，分镜图列优先留宽。每格画幅 {frame}。\n'
            f'同一镜号的关键姿态放在同一格。沿用以下逐镜内容和实际参考。\n\n'
            f'{direction.strip()}\n\n{references}\n\n{contents}\n')


def prepare(project, source, brief, basis, *, page_size=6, chart_version=None):
    project = Path(project).resolve()
    if project != video_root(project.parent.parent, project.name):
        raise ValueError('须指定 Chloe 单条视频的实际目录')
    source = resources.local(project, source)
    if not 1 <= page_size <= 6:
        raise ValueError('每页镜头数须为 1 至 6')
    if not basis.strip():
        raise ValueError('须填写本轮实际制作授权')
    info = fields(document(project, source.relative_to(project)), '脚本信息')
    available = {shot['fields']['镜号']: shot['fields']
                 for shot in read_shots(source.read_text('utf-8-sig'), EXTRA_FIELDS)}
    selected = [row['shot'] for row in brief['shots']]
    table = []
    for item in brief['shots']:
        shot = available[item['shot']]
        visual = {'分镜图': item['sketch'], '情绪/动作': item['action']}
        table.append({key: visual[key] if key in visual else shot[key] for key in COLUMNS})
    pages = [{'page': n, 'rows': table[i:i+page_size]} for n, i in enumerate(range(0, len(table), page_size), 1)]
    record = project / '制作记录.md'
    directory = project / '执行记录'
    inputs, paths = reference_inputs(project, record, brief.get('references', []))

    with resources.index_lock(project):
        body = record.read_text('utf-8')
        version, candidate = chart_identity(directory, body, info['脚本版本'], chart_version)
        used = [row['执行编号'] for row in rows(body, '执行记录')] + [path.name for path in directory.iterdir()]
        first = max((int(m[1]) for name in used if (m := re.match(r'^E(\d+)', name))), default=0)+1
        plan_path = directory / f'E{first:03d}' / PLAN_FILE
        plan = {'source': (Path('../..') / source.relative_to(project)).as_posix(),
                'source_version': info['脚本版本'], 'object': project.name.replace('-', ' ', 1),
                'chart_version': version, 'candidate': candidate, 'extra_fields': list(EXTRA_FIELDS),
                'shot_ids': selected, 'pages': pages}
        validate_plan(plan, plan_path.parent)
        files = {plan_path: plan}
        prepared = []
        for offset, page in enumerate(pages):
            execution = f'E{first+offset:03d}'
            folder = directory / execution
            prompt = page_prompt(plan, page, info['画幅'], brief.get('direction', ''), inputs)
            call = generation_call(prompt, paths, f'{project.name}-{execution}-imagegen')
            manifest = folder / MANIFEST_FILE
            prompt_path = folder / PROMPT_FILE
            body = put(body, '执行记录', ['执行编号'], {
                '执行编号': execution, '执行类型': '图片生成', '上游执行': '不适用',
                '工具与模式': '内置 Imagegen 多图参考生成' if paths else '内置 Imagegen 文生图',
                '提示词或正文': link(record, prompt_path, '导演表提示词'),
                '参数记录': link(record, plan_path, '导演表制作计划'), '授权依据': basis,
                '任务ID': '未取得', '开始时间': '未取得', '结束时间': '未取得',
                '执行状态': '准备中', '结果说明': f'导演表第 {page["page"]} 页候选。'})
            for item in inputs:
                body = put(body, '输入记录', ['执行编号', '输入槽位'], {'执行编号': execution, **item})
            number = page['page']
            slot = f"导演表/脚本{plan['source_version']}/图表{version}/候选{candidate}/第{number}页"
            files[prompt_path] = prompt
            files[manifest] = {
                'tool': 'image_gen', 'mode': 'generate', 'requested_layout': '宽横版',
                'references': paths, 'prompt_file': PROMPT_FILE,
                'plan': os.path.relpath(plan_path, folder),
                'video_project': project.name, 'task_id': '未取得',
                'business_result': {'adapter': 'chloe-image', 'document': record.name,
                                    'execution': execution, 'outputs': [{'slot': slot, 'purpose': f'导演表/第{number}页'}]}}
            prepared.append({'page': number, 'execution': execution, 'manifest': str(manifest), 'call': call})
        created = []
        try:
            for path, value in files.items():
                if not path.parent.exists():
                    path.parent.mkdir()
                    created.append(path.parent)
                with path.open('x', encoding='utf-8') as output:
                    created.append(path)
                    output.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)+'\n')
            save(record, body)
        except OSError:
            for path in reversed(created):
                path.rmdir() if path.is_dir() else path.unlink()
            raise
    return {'source_version': plan['source_version'], 'chart_version': version, 'candidate': candidate,
            'plan': str(plan_path), 'pages': prepared}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path, help='Chloe 单条视频的绝对目录')
    parser.add_argument('--source', required=True, help='相对视频目录的本次源脚本')
    parser.add_argument('--brief', required=True, type=Path, help='本轮逐镜画法及参考的 UTF-8 JSON')
    parser.add_argument('--basis', required=True, help='本轮实际制表授权依据')
    parser.add_argument('--page-size', type=int, default=6, help='每页最多镜头数，1 至 6，默认 6')
    parser.add_argument('--chart-version', help='默认自动取号，显式指定时拒绝已使用或已预留的版本')
    args = parser.parse_args()
    brief = json.loads(args.brief.read_text('utf-8-sig'))
    result = prepare(args.project, args.source, brief, args.basis,
                     page_size=args.page_size, chart_version=args.chart_version)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
