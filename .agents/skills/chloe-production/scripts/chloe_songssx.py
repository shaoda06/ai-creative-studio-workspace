"""Stage Chloe's existing execution and round records for one Songssx timeline."""
import json
import re
import sys

import chloe_production as production

sys.path.insert(0, str(production.SKILLS / 'chloe-assets/scripts'))
from chloe_result_records import link, put, rows
from songssx_workflow import PLANNER, TASK_TYPE, shot_blocks


def register(project, spec, task, plan_file, documents, now):
    if not isinstance(spec, dict) or set(spec) != {'script', 'note'}:
        raise ValueError('chloe_round 须提供本轮脚本快照 script 和制作说明 note')
    if not isinstance(spec['note'], str) or not spec['note'].strip():
        raise ValueError('Chloe 制作说明不能为空')
    record = production.local(project, task['record_dir'])
    execution = record.name
    if record.parent != project / '执行记录' or not re.fullmatch(r'E[0-9]{3,}', execution):
        raise ValueError('Chloe Songssx 须使用本视频执行记录/E编号')
    plan = task['video_plan']
    if task['task_type'] != TASK_TYPE or 'gap_repair' in plan:
        raise ValueError('Chloe Songssx 轮次须提交一个完整场次生成任务')
    target, = task['outputs']
    if production.local(project, target['path']).suffix.lower() != '.mp4':
        raise ValueError('Chloe 整场候选须输出一个 MP4')
    script = production.local(project, spec['script'])
    if script.parent != project / '历史版本' or not script.is_file():
        raise ValueError('Chloe 轮次须引用本视频历史版本中的准确脚本')
    script_key = script.relative_to(project).as_posix()
    _, planned = production.plan(project, script_key)
    segments = plan['segments']
    if [(row['p'], row['planned_seconds']) for row in segments] != [(key, row['duration']) for key, row in planned.items()]:
        raise ValueError('Songssx GEN 的 P 顺序和计划时长须与 Chloe 脚本快照一致')
    timeline = json.loads(task['workflow'][PLANNER]['inputs']['timeline_data'])
    english, chinese = [], []
    for row, gen in zip(segments, timeline['segmentConfig']['segments'], strict=True):
        identity = row['p']
        if len(shot_blocks(gen['prompt'])) != len(planned[identity]['shotIds']):
            raise ValueError(identity + ' 的 Songssx Shot 数须与脚本快照一致')
        if not row.get('prompt_zh', '').strip():
            raise ValueError(identity + ' 缺少同版中文参考 prompt_zh')
        english.append(f"### {identity}\n\n{gen['prompt'].strip()}")
        chinese.append(f"### {identity}\n\n{row['prompt_zh'].strip()}")

    document = project / '制作记录.md'
    body = documents.read(document)
    if any(row['执行编号'] == execution for row in rows(body, '执行记录')):
        raise ValueError('Chloe 已有该执行编号，请沿原清单接续或使用新编号')
    index = project / '制作轮次.json'
    rounds = json.loads(documents.read(index))
    number = len(rounds['rounds']) + 1
    run = f'R{number:03}'
    prompt = record / '提示词.md'
    documents.put(prompt, f'# {execution}｜视频生成提示词\n\n## 模型提示词正文\n\n'
                  + '\n\n'.join(english) + '\n\n## 中文提示词参考版\n\n' + '\n\n'.join(chinese) + '\n')
    body = put(body, '执行记录', ['执行编号'], {
        '执行编号': execution, '执行类型': '视频生成', '上游执行': '不适用', '工具与模式': 'Songssx SelfLift',
        '提示词或正文': link(document, prompt, '提示词'), '参数记录': link(document, plan_file, '任务清单'),
        '授权依据': link(document, plan_file, '本次任务授权'), '任务ID': '未取得', '开始时间': '未取得',
        '结束时间': '未取得', '执行状态': '准备中', '结果说明': '无',
    })
    entries = []
    for row in segments:
        identity = row['p']
        body = put(body, '视频分段执行', ['分段编号', '制作阶段', '候选版本'], {
            '分段编号': identity, '制作阶段': production.SCENE_STAGE, '候选版本': run, '执行编号': execution,
            '输出槽位': production.SCENE_SLOT, '模型分段序号': row['gen'] - 1,
        })
        entries.append(dict(id=identity, execution=execution, slot=production.SCENE_SLOT))
    rounds['rounds'].append(dict(number=number, created_at=now, note=spec['note'].strip(),
                                 script=script_key, segments=entries))
    documents.put(document, body)
    documents.put(index, json.dumps(rounds, ensure_ascii=False, indent=2) + '\n')
    plan['business_result'] = dict(adapter='chloe-video', document=document.name, execution=execution,
                                   round=number, outputs=[dict(slot=production.SCENE_SLOT)], automatic_round=True)
    return number
