"""Prepare serial-drama execution workdrafts from explicit task associations."""
import json
from pathlib import Path
import re

import sys
_SKILLS = Path(__file__).resolve().parents[2]
for _skill in ("studio-comfyui", "studio-h3", "studio-h3-aimixer", "studio-video-processing", "nora-video-prompts", "nora-drama-production", "nora-drama-handoff"):
    sys.path.insert(0, str(_SKILLS / _skill / "scripts"))

from project_paths import project_file
sys.path.insert(0, str(_SKILLS / "studio-workspace-browser/scripts"))
from document_fields import fields, link
STAGES = {'video-first-pass': '一采', 'video-second-pass': '二采', 'video-postprocess': '后处理'}

def prepare_records(root, skill, spec, api, mapping, record, documents):
    stage = STAGES[spec['task_type']]
    template = (Path(__file__).resolve().parents[1]/'templates/分段视频工作稿模板.md').read_text('utf-8-sig')
    template = re.search(r'```markdown\n(.*?)\n```', template, re.S)[1]
    sample = re.search(r'^### R001-一采\s*\n.*?(?=^## 3\.)', template, re.M | re.S)[0]
    directors = [node['inputs'] for node in api.values() if node['class_type']=='MiniMaxH3Director']
    timeline = json.loads(directors[0]['timeline_data']) if directors else None
    for index in mapping['selected_indices']:
        entry = mapping['segments'][index]
        segment, revision = entry['segment'], entry['round']
        episode = segment.split('-')[0]
        draft = root/'09-剧集制作'/episode/'其他资料/工作稿'/f'{segment}-视频制作-工作稿.md'
        text = documents.read(draft)
        if text is None:
            text = template[:template.index('### R001-一采')] + '## 3. 讨论与修改\n\n## 4. 审阅区\n'
            text = text.replace('# EP编号-C编号-P编号-视频制作-工作稿', '# '+draft.stem).replace('<具体审阅章节链接>', '尚未批准')
        heading = revision+'-'+stage
        area = re.search(r'^### '+re.escape(heading)+r'\s*\n.*?(?=^#{1,3} |\Z)', text, re.M | re.S)
        before = area[0] if area else ''
        body = before or sample.replace('### R001-一采', '### '+heading, 1)
        mapping_link = link(draft, record/'输入映射.json', '当次输入映射及冻结资料')
        api_link = link(draft, record/'任务.api.json', '当次实际API')
        state_link = link(draft, record/'后台任务状态.json', '后台共同状态及任务ID')
        authorization = ('执行授权见'+link(draft, project_file(root, spec['submission_plan']), '原任务清单')) if spec.get('submission_plan') else spec['authorization']
        values = {'修订内容及依据': spec.get('description', spec['title'])+'；'+authorization,
            '处理阶段': stage, '执行过程与重试记录': state_link,
            '共同任务证据与状态入口': mapping_link+'；'+state_link,
            '任务状态': '已准备；实际执行见'+state_link, '最近检查时间': '动态状态见'+state_link,
            '来源任务及其具体输出版本、批准依据': ('来源身份：'+entry['source']+'；'+mapping_link) if entry.get('source') else '首次一采；执行授权见本条目',
            '实际输入素材与具体版本、顺序及批准依据（输入映射入口）': mapping_link,
            '本次生成资料关联入口（输入映射generation_contexts，填写按目录规范）': mapping_link,
            '本次冻结的模型提示词入口（后处理不生成空文件）': '不适用，后处理不生成模型正文' if stage=='后处理' else '实际执行前由后台冻结，入口见'+mapping_link,
            '工作流基准、校验值及本次API任务副本入口': api_link+'；'+link(draft, record/'任务.workflow.json','配套画布'),
            '实际完整参数依据及快照入口': api_link,
            '后处理选定交付目标及依据': spec.get('delivery_basis', '按本次已配置API目标；'+api_link) if stage=='后处理' else '不适用',
            '实际种子': str(directors[0]['seed']) if directors else '不适用，后处理无采样种子',
            '请求、上传／提交响应及提交尝试证据入口（按实际产生）': state_link,
            'client ID／prompt ID': state_link,
            '请求秒数': str(entry.get('duration_seconds', entry.get('durationSec', '见实际输入映射'))),
            '计算帧数': str(timeline['segments'][index]['frameCount']) if directors else '后处理帧数由源视频及目标帧率确定；'+api_link,
            '实测时长及数值来源': '待后台读取实际输出', '实际尺寸及数值来源': '待后台读取实际输出',
            '实际帧率及数值来源': '待后台读取实际输出', '实际平均码率及数值来源': '待后台读取实际输出',
            '音轨情况及信息来源': '待后台读取实际输出', '执行状态、执行结果入口与失败／异常说明': state_link,
            '远端实际输出信息与本地输出的对应关系': '尚未取回，实际文件及凭据由后台登记',
            '输出当前入口及取回／展示情况': '尚未取回', '取回核对状态': '未取回',
            '人工审阅记录入口': '实际取回后由后台建立', '用户决定': '尚未产生本次候选，不推定批准',
            '用户采用的具体输出、批准范围、时间与依据': '尚无本次候选的用户决定',
            '后续处理及受影响的下游任务／分段交付': '技术成功不授权下一阶段'}
        if before:
            values = {name:value for name,value in values.items() if re.search(r'^- '+re.escape(name)+r'：(?:\s*$|<)', body, re.M)}
        body = fields(body, values)
        if not before and index != mapping['selected_indices'][0]:
            body = re.sub(r'^- (任务状态|最近检查时间)：[^\n]*\n?', '', body, flags=re.M)
        if area:
            text = text[:area.start()] + body + text[area.end():]
        else:
            marker = re.search(r'^## 3\.', text, re.M)
            text = text[:marker.start()]+body.rstrip()+'\n\n'+text[marker.start():]
        documents.put(draft, text)



def sync_timing(canvas, mapping, task_type):
    if task_type != 'video-first-pass' or any(item.get('source') or item.get('materials_from') for item in mapping['segments']):
        raise ValueError('自动帧数装配只用于无历史来源的新一采；接续保留原画布及缓存输入')
    from aimixer_timing import sync_timing as assemble_timing
    return assemble_timing(canvas, mapping['selected_indices'])
