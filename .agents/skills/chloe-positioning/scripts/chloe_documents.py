"""Read and check Chloe's fixed Markdown directly against its maintained templates."""
import argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import urlsplit

from chloe_init import ASSETS, SKILLS, asset_template_skill, resources, workspace_path, project_path

sys.path.insert(0, str(SKILLS / 'studio-storyboard/scripts'))
from storyboard_fields import read_shots

MISSING = {'待确定', '待核实', '未取得', '不适用', '无'}
DISPLAY_IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp'}
LINK = re.compile(r'\[([^\]\n]+)\]\(<([^>\n]+)>\)')
MEDIA = re.compile(r'\[(共用|本视频):((?:IMG|VID|AUD)-[a-zA-Z0-9-]+)@(V[0-9]{3,})\]\(<([^>\n]+)>\)')
PREFIXES = {'事项编号': 'I', '记录编号': 'B', '事实编号': 'F', '条件编号': 'C', '卖点编号': 'S',
            '执行编号': 'E', '审阅编号': 'R', '返修编号': 'X', '交接编号': 'J',
            '发布编号': 'P', '采集编号': 'D', '复盘编号': 'R', '验证编号': 'T', '修订编号': 'U',
            '核对编号': 'K', '镜头编号': 'SH', '资料编号': 'Q'}
REQUIRED_ASSET_IMAGES = {
    '模特说明.md': ('正面面部', '全身三视图原图'),
    '造型说明.md': ('造型面部三视图', '全身三视图原图', '全身三视图遮面版'),
    **{label+'说明.md': (label+'展示图',) for label in ('发型', '服装', '配饰', '场景')},
}


def parse(text):
    """Preserve ordered sections and tables; no inference from narrative prose."""
    result = {'title': '', 'sections': []}
    section = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('# '):
            if result['title'] or section:
                raise ValueError(f'第{i+1}行：一级标题重复或位置错误')
            result['title'] = line[2:]
        elif line.startswith('## '):
            section = {'heading': line[3:], 'tables': [], 'text': []}
            result['sections'].append(section)
        elif re.match(r'^#{3,4} SH\d{3,}(?:｜|\s|$)', line) and section and section['heading'] == '镜头与分镜':
            section['text'].append(lines[i])
        elif line.startswith('#'):
            raise ValueError(f'第{i+1}行：不支持的标题层级')
        elif line.startswith('|'):
            if section is None:
                raise ValueError(f'第{i+1}行：表格缺少所属章节')
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = lines[i].strip()
                if not row.endswith('|'):
                    raise ValueError(f'第{i+1}行：表格行必须以竖线结束')
                cells = [cell.strip() for cell in row[1:-1].split('|')]
                if rows and len(cells) != len(rows[0]):
                    raise ValueError(f'第{i+1}行：表格列数变化，正文竖线请写&#124;')
                if any(not cell for cell in cells):
                    raise ValueError(f'第{i+1}行：单元格为空')
                rows.append(cells)
                i += 1
            if len(rows) < 2 or not all(re.fullmatch(':?-{3,}:?', v) for v in rows[1]):
                raise ValueError('表格缺少标准分隔行')
            section['tables'].append({'columns': rows[0], 'rows': rows[2:]})
            continue
        elif line:
            if section is None:
                raise ValueError(f'第{i+1}行：正文缺少所属章节')
            section['text'].append(lines[i])
        i += 1
    if not result['title']:
        raise ValueError('缺少一级标题')
    return result


def template(skill, name):
    return SKILLS / skill / 'templates' / name


def documents(root):
    yield root/'README.md', template('chloe-positioning', '项目README模板.md'), {'title': root.name}
    yield root/'projects/README.md', template('chloe-creative', '视频索引说明模板.md'), {}
    for name in ('账号定位', '选品记录', '运营复盘'):
        yield root/f'综合资料/{name}.md', template('chloe-positioning', name+'模板.md'), {}
    for kind, (folder, prefix, filename) in ASSETS.items():
        parent = root/'综合资料'/folder
        if kind in {'发型', '配饰', '参考视频'} and not parent.exists():
            continue
        if not parent.is_dir():
            raise ValueError('缺少固定目录：'+str(parent))
        for item in sorted(p for p in parent.iterdir() if p.is_dir() and not p.name.startswith('.')):
            if not re.fullmatch(prefix+r'\d{3,}-.+', item.name):
                raise ValueError('资产目录编号格式错误：'+str(item))
            identity, title = item.name.split('-', 1)
            yield item/filename, template(asset_template_skill(kind), filename.replace('.md', '模板.md')), {'identity': identity, 'title': title}
    for item in sorted(p for p in (root/'projects').iterdir() if p.is_dir() and not p.name.startswith('.')):
        if not re.fullmatch(r'V\d{3,}-.+', item.name):
            raise ValueError('视频目录编号格式错误：'+str(item))
        identity, title = item.name.split('-', 1)
        for name, source in [('README.md','视频README模板.md'),('脚本.md','脚本模板.md'),('制作记录.md','制作记录模板.md')]:
            yield item/name, template('chloe-creative', source), {'identity': identity, 'title': title}

        if (item/'发布资料.md').is_file():
            yield item/'发布资料.md', template('chloe-handoff', '发布资料模板.md'), {'identity': identity, 'title': title}


def enums():
    guide = parse((SKILLS/'chloe-positioning/references/固定资料写法规范.md').read_text('utf-8'))
    section = next(s for s in guide['sections'] if s['heading'] == '固定状态词')
    return {row[0]: set(row[1].split('、')) for row in section['tables'][0]['rows']}


def owner_for(root, path):
    relative = path.relative_to(root)
    return root/'projects'/relative.parts[1] if relative.parts[0] == 'projects' and len(relative.parts) > 2 else root/'综合资料'


def media_reference(root, path, value):
    match = MEDIA.fullmatch(value)
    if not match:
        raise ValueError('资源引用必须为[共用或本视频:资源编号@准确版本](<相对路径>)：'+value)
    scope, identity, version, href = match.groups()
    owner = root/'综合资料' if scope == '共用' else owner_for(root, path)
    if scope == '本视频' and owner == root/'综合资料':
        raise ValueError('共用资产不能引用本视频归属')
    target = resources.version_file(owner, identity, version)
    if not target.is_file() or not (target.parent/'版本信息.json').is_file():
        raise ValueError('资源版本尚未完整保存：'+value)
    if Path(href).is_absolute() or (path.parent/href).resolve() != target:
        raise ValueError('资源链接与准确版本不一致：'+value)
    return {'owner': owner.relative_to(root).as_posix(), 'resource_id': identity, 'version': version,
            'file': target.relative_to(root).as_posix()}


def value_check(field, value, choices):
    if value in {'-', '—', 'TODO', '同上'} or '{{' in value:
        raise ValueError(field+'含未填写占位或不明确值')
    if field in choices and value not in choices[field]:
        raise ValueError(field+'不是规定值：'+value)
    if value in MISSING:
        return
    if field.endswith('时间'):
        parsed = datetime.fromisoformat(value)
        if 'T' not in value or parsed.tzinfo is None:
            raise ValueError(field+'须使用带时区ISO时间')
    if field.endswith(('秒', '像素')) or field in ('帧率', '指标值'):
        try:
            number = Decimal(value)
        except InvalidOperation as error:
            raise ValueError(field+'须使用数字') from error
        if not number.is_finite() or (field != '指标值' and number < 0):
            raise ValueError(field+'须为有限数字，时长及媒体规格不能为负')
    if field == '脚本版本' and not re.fullmatch(r'v\d{2,}', value):
        raise ValueError('脚本版本须为v01等格式')


def read_document(root, path, source, substitutions, *, body=None):
    text = source.read_text('utf-8')
    for key, value in substitutions.items():
        text = text.replace('{{'+key+'}}', value)
    expected = parse(text)
    actual = parse(path.read_text('utf-8') if body is None else body)
    if actual['title'] != expected['title']:
        raise ValueError('标题、对象编号或名称与模板／目录不一致')
    if [s['heading'] for s in actual['sections']] != [s['heading'] for s in expected['sections']]:
        raise ValueError('章节名称、顺序、数量与模板不一致')
    choices = enums()
    for section, schema in zip(actual['sections'], expected['sections']):
        tables = schema['tables']
        if section['heading'] == '镜头与分镜' and section['tables']:
            # Previously filed scripts used this table, which remains readable.
            tables = [{'columns': ['镜头编号', '时长秒', '景别与构图', '主体与商品动作', '商品可见细节',
                                   '场景与机位', '对白或旁白', '字幕', '音乐与环境声', '参考需求'], 'rows': []}]
        if len(section['tables']) != len(tables):
            raise ValueError(section['heading']+'：表格缺失或额外增加')
        if section['heading'] == '镜头与分镜':
            shots = read_shots('\n'.join(section['text']), ('商品可见细节', '字幕', '参考需求'))
            identities = [shot['fields']['镜号'] for shot in shots]
            if len(identities) != len(set(identities)) or any(not re.fullmatch(r'SH\d{3,}', identity) for identity in identities):
                raise ValueError('镜头编号重复或格式错误')
            if shots and section['tables']:
                raise ValueError('镜头与分镜：逐镜正文和旧表格重复维护')
            for shot in shots:
                value_check('时长秒', shot['fields']['时长'].removesuffix('秒').strip(), choices)
            section['shots'] = shots
        for tab, base in zip(section['tables'], tables):
            if tab['columns'] != base['columns']:
                raise ValueError(section['heading']+'：表头或列序与模板不一致')
            fixed = tab['columns'] == ['字段', '内容']
            if fixed:
                names = [r[0] for r in tab['rows']]
                expected_names = [r[0] for r in base['rows']]
                if path.name in REQUIRED_ASSET_IMAGES and section['heading'] == '资产身份' and '资产状态' not in names:
                    expected_names.remove('资产状态')  # Existing records default to 制作中.
                if path.name == '服装说明.md' and section['heading'] == '服装信息' and names == ['服装说明']:
                    expected_names = names  # Older records remain readable without classification.
                if names != expected_names:
                    raise ValueError(section['heading']+'：固定字段缺失、重复、改名或顺序改变')
            seen = set()
            for row in tab['rows']:
                record = dict(zip(tab['columns'], row))
                pairs = [row] if fixed else zip(tab['columns'], row)
                for field, value in pairs:
                    value_check(field, value, choices)
                    if fixed and field in ('视频编号','资产编号','商品编号') and dict(base['rows'])[field] == substitutions.get('identity') and value != substitutions['identity']:
                        raise ValueError(field+'与目录不符')
                    if field in ('资产名称','视频名称','商品名称') and fixed and value != substitutions.get('title'):
                        raise ValueError(field+'与目录不符')
                    if field == '资产类型' and value != dict(base['rows'])[field]:
                        raise ValueError('资产类型与模板不符')
                    if field in ('资源引用','横版封面引用','竖版封面引用') and value not in MISSING:
                        ref = media_reference(root, path, value)
                        if field.endswith('封面引用') and Path(ref['file']).suffix.lower() not in resources.KINDS['图片']:
                            raise ValueError(field+'必须引用准确图片版本')
                    elif (path.name in REQUIRED_ASSET_IMAGES and section['heading'] == '当前采用'
                          and field == '资源引用' and value not in MISSING):
                        ref = media_reference(root, path, value)
                        if Path(ref['file']).suffix.lower() not in resources.KINDS['图片']:
                            raise ValueError('图片资产的当前采用须引用图片')
                    elif value.startswith(('[共用:', '[本视频:')):
                        media_reference(root, path, value)
                    for label, href in LINK.findall(value):
                        if not re.match(r'https?://', href) and not (path.parent/href.split('#')[0]).exists():
                            raise ValueError('文件链接不存在：'+href)
                        if re.fullmatch(r'T\d{3,}', label):
                            verification_reference(root, path, label, href)
                if not fixed:
                    field = tab['columns'][0]
                    if field in PREFIXES and not re.fullmatch(PREFIXES[field]+r'\d{3,}', row[0]):
                        raise ValueError(field+'编号格式错误：'+row[0])
                    key = (row[0],)
                    if section['heading'] in ('输入记录','输出记录'):
                        key = (row[0], row[1])
                    elif section['heading'] == '效果数据':
                        key = (record['采集编号'],record['指标名称'],record['统计口径'])
                    elif field not in PREFIXES and section['heading'] not in ('当前采用','选品列表'):
                        continue
                    if key in seen:
                        raise ValueError(section['heading']+'：记录身份重复 '+str(key))
                    seen.add(key)
    check_relations(root, path, actual)
    return actual


def records(doc, heading):
    section = next((s for s in doc['sections'] if s['heading'] == heading), None)
    return [dict(zip(t['columns'], row)) for t in section['tables'] for row in t['rows']] if section else []


def asset_status(path, doc):
    identity = {row['字段']: row['内容'] for row in records(doc, '资产身份')}
    adopted = {row['用途'] for row in records(doc, '当前采用')}
    required = REQUIRED_ASSET_IMAGES[path.name]
    return {'id': identity['资产编号'], 'name': identity['资产名称'], 'status': identity.get('资产状态', '制作中'),
            'missing_images': [purpose for purpose in required if purpose not in adopted]}


def verification_reference(root, path, identity, href):
    filename, _, anchor = href.partition('#')
    target = (path.parent/filename).resolve()
    if target != root/'综合资料/运营复盘.md' or anchor != '建议验证':
        raise ValueError('T编号须链接本工作区运营复盘的建议验证章节')
    # Read row identity only: a source review may link back to this T row.
    source = parse(target.read_text('utf-8'))
    matches = [row for row in records(source, '建议验证') if row['验证编号'] == identity]
    if len(matches) != 1:
        raise ValueError('T编号须对应唯一存在的建议验证记录：'+identity)


def has_evidence(path, value):
    """Evidence must name a source URL or an existing original file."""
    if re.fullmatch(r'https?://[^\s]+', value):
        return True
    return any(re.fullmatch(r'https?://[^\s]+', href) or
               (path.parent/href.split('#')[0]).is_file() for _, href in LINK.findall(value))


def review_record(root, path, value, prefixes):
    match = LINK.fullmatch(value)
    if not match or not re.fullmatch('['+prefixes+r']\d{3,}', match[1]):
        raise ValueError('复盘来源须用D或R编号链接原视频README中的记录')
    identity, href = match.groups()
    filename, _, anchor = href.partition('#')
    target = (path.parent/filename).resolve()
    if (target.name != 'README.md' or target.parent.parent != root/'projects' or
            not re.fullmatch(r'V\d{3,}-.+', target.parent.name) or not target.is_file()):
        raise ValueError('复盘来源须链接本工作区实际视频README')
    heading, field = ('效果数据', '采集编号') if identity.startswith('D') else ('单条复盘', '复盘编号')
    if anchor and anchor != heading:
        raise ValueError('复盘来源章节与记录编号不一致')
    video, title = target.parent.name.split('-', 1)
    source = read_document(root, target, template('chloe-creative', '视频README模板.md'), {'identity': video, 'title': title})
    rows = [row for row in records(source, heading) if row[field] == identity]
    if not rows:
        raise ValueError('复盘来源引用不存在的'+field+'：'+identity)
    if identity.startswith('D') and all(row['指标值'] in MISSING for row in rows):
        raise ValueError('复盘来源的采集记录尚无实际指标值')
    return rows


def linked_object(root, path, identity, value, prefix):
    match = LINK.fullmatch(value)
    if not re.fullmatch(prefix+r'\d{3,}', identity) or not match:
        raise ValueError('对象编号或说明链接格式错误：'+identity)
    target = (path.parent/match[2]).resolve()
    kind, (folder, _, filename) = next((kind, item) for kind, item in ASSETS.items() if item[1] == prefix)
    if (target.name != filename or target.parent.name.split('-',1)[0] != identity or
            target.parent.parent != root/'综合资料'/folder or not target.is_file()):
        raise ValueError('对象编号与说明文件不匹配：'+identity)
    return kind


def check_outfit_sources(root, path, doc, source):
    if source == '提取':
        if not any(row['用途'] == '服装参考图' for row in records(doc, '参考版本')):
            raise ValueError('提取套装登记为可用前须记录原服装参考图')
        return

    adopted = media_reference(root, path, records(doc, '当前采用')[0]['资源引用'])
    display = next((row for row in records(doc, '参考版本')
                    if row['用途'] == '服装展示图' and media_reference(root, path, row['资源引用']) == adopted), None)
    executions = {row['执行编号']: row for row in records(doc, '执行记录')}
    number = display['执行编号'] if display else None
    visited = set()
    while number in executions and number not in visited:
        visited.add(number)
        execution = executions[number]
        if execution['执行状态'] != '已完成':
            break
        if execution['执行类型'] == '图片生成':
            inputs = [media_reference(root, path, row['资源引用']) for row in records(doc, '输入记录')
                      if row['执行编号'] == number and row['资源引用'] not in MISSING]
            versions = {(ref['resource_id'], ref['version']) for ref in inputs}
            if 1 <= len(versions) <= 5 and all(Path(ref['file']).suffix.lower() in DISPLAY_IMAGE_SUFFIXES for ref in inputs):
                return
            break
        number = execution['上游执行']
    raise ValueError('合成套装登记为可用前须关联正式图的已完成生图执行，并记录 1–5 项准确图片输入')


def check_relations(root, path, doc):
    if path.name == '服装说明.md':
        info = {row['字段']: row['内容'] for row in records(doc, '服装信息')}
        form = info.get('服装形态')
        if form == '单件' and (info['部位'] in MISSING or info['套装来源'] != '不适用'):
            raise ValueError('单件须填写部位，套装来源填不适用')
        if form == '套装' and (info['套装来源'] in MISSING or info['组成与穿法'] in MISSING or info['部位'] != '不适用'):
            raise ValueError('套装须填写来源及组成与穿法，部位填不适用')
    if path.name == ASSETS['参考视频'][2]:
        info = {row['字段']: row['内容'] for row in records(doc, '参考视频信息')}
        if info['播放版本引用'] not in MISSING:
            if any(info[key] in MISSING for key in ('来源', '内容简介', '原件引用', '登记依据')):
                raise ValueError('参考视频登记须记录来源、内容简介、原件和登记依据')
            if info['来源'] != '用户提供':
                platform, _, address = info['来源'].partition('－')
                url = urlsplit(address)
                if not platform.strip() or not re.fullmatch(r'https?://[^\s<>]+', address) or not url.hostname:
                    raise ValueError('来源须为用户提供或平台名－实际视频网址')
            for key in ('原件引用', '播放版本引用'):
                ref = media_reference(root, path, info[key])
                if ref['owner'] != '综合资料' or resources.media_kind(ref['file']) != '视频':
                    raise ValueError(key+'须引用本项目的准确共用视频版本')
    if path.name in {'模特说明.md', '造型说明.md'}:
        for heading in ('参考版本', '当前采用'):
            for row in records(doc, heading):
                if row['用途'].split('/', 1)[0] not in REQUIRED_ASSET_IMAGES[path.name]:
                    raise ValueError(path.name+'：'+heading+'图片用途不在固定图种内：'+row['用途'])
    if path.name in {'发型说明.md', '服装说明.md', '配饰说明.md', '场景说明.md'}:
        label = path.name[:2]
        for row in records(doc, '参考版本'):
            if row['用途'] not in {label+'参考图', label+'展示图'}:
                raise ValueError(label+'用途须为'+label+'参考图或'+label+'展示图')
        for row in records(doc, '当前采用'):
            if row['用途'] != label+'展示图':
                raise ValueError(label+'当前采用只登记'+label+'展示图')
    if path.name in {'发型说明.md', '服装说明.md', '配饰说明.md', '场景说明.md'}:
        for heading in ('参考版本', '当前采用'):
            for row in records(doc, heading):
                ref = media_reference(root, path, row['资源引用'])
                if Path(ref['file']).suffix.lower() not in DISPLAY_IMAGE_SUFFIXES:
                    raise ValueError(path.stem+'：'+heading+'须引用PNG、JPEG或WebP图片')
    if path.name == '声音说明.md':
        for heading in ('参考版本', '当前采用'):
            for row in records(doc, heading):
                purpose = row['用途']
                if purpose not in {'声音原始参考', '声音参考'}:
                    raise ValueError('声音用途须为声音原始参考或声音参考')
                if heading == '当前采用' and purpose != '声音参考':
                    raise ValueError('声音当前采用只登记声音参考')
                ref = media_reference(root, path, row['资源引用'])
                suffix = Path(ref['file']).suffix.lower()
                allowed = resources.KINDS['音频'] if purpose == '声音参考' else resources.KINDS['音频'] | resources.KINDS['视频']
                if suffix not in allowed:
                    raise ValueError('声音参考须为音频，原始参考须为音频或视频')
        for row in records(doc, '关联资料'):
            if row['关系'] == '模特' and not re.fullmatch(r'M\d{3,}', row['对象编号']):
                raise ValueError('关联模特须使用M编号')
    current = {r['字段']:r['内容'] for r in records(doc,'定位与当前进度')}
    if current and current['商品编号'] not in MISSING:
        linked_object(root,path,current['商品编号'],current['商品资料'],'G')
    for row in records(doc,'选品列表'):
        linked_object(root,path,row['商品编号'],row['商品资料'],'G')
    linked = set()
    for row in records(doc,'关联资料'):
        identity = row['对象编号']
        if identity not in MISSING:
            prefix = identity.rstrip('0123456789')
            if prefix not in {item[1] for item in ASSETS.values()}:
                raise ValueError('关联对象编号类型错误')
            linked_object(root,path,identity,row['说明文件'],prefix)
            linked.add(identity)
    look = {r['字段']:r['内容'] for r in records(doc,'造型信息')}
    if look and look['模特编号'] not in MISSING:
        if not re.fullmatch(r'M\d{3,}', look['模特编号']) or look['模特编号'] not in linked:
            raise ValueError('造型信息与关联资料不一致：模特编号')
    for heading in ('款式与事实','带货条件'):
        identities = [(r['款式或SKU'],r['字段']) for r in records(doc,heading)]
        if len(set(identities)) != len(identities):
            raise ValueError(heading+'：同一SKU字段重复')
    for row in records(doc,'当前采用'):
        if any(row[field] in MISSING for field in ('资源引用','采用依据','采用时间')):
            raise ValueError('当前采用必须有准确资源、采用依据和时间')
    if path.name in REQUIRED_ASSET_IMAGES and any(
        row['字段'] == '资产状态' and row['内容'] == '可用' for row in records(doc, '资产身份')
    ):
        state = asset_status(path, doc)
        if state['missing_images']:
            raise ValueError('资产登记为可用前须采用：'+'、'.join(state['missing_images']))
        decisions = [row for row in records(doc, '采用变更') if row['变更范围'] == '资产状态']
        if not decisions or decisions[-1]['原值或原版本'] != '制作中' or decisions[-1]['新值或新版本'] != '可用' or any(
            decisions[-1][field] in MISSING for field in ('依据', '记录时间')
        ):
            raise ValueError('资产登记为可用须记录用户明确批准的依据和时间')
        if path.name == '服装说明.md' and form == '套装':
            check_outfit_sources(root, path, doc, info['套装来源'])
    script = {r['字段']:r['内容'] for r in records(doc,'脚本信息')}
    if script and script['脚本状态'] == '已确认' and any(script[k] in MISSING for k in ('确认依据','确认时间')):
        raise ValueError('已确认脚本缺少确认依据或时间')
    if script and records(doc, '分段计划'):
        check_segment_plan(doc, script['计划时长秒'])
    executions = {r['执行编号'] for r in records(doc,'执行记录')}
    if path.name == '场景说明.md':
        for row in records(doc, '执行记录'):
            if row['上游执行'] not in MISSING and row['上游执行'] not in executions:
                raise ValueError('场景说明：'+row['执行编号']+'引用不存在的上游执行：'+row['上游执行'])
    reviews = {r['审阅编号'] for r in records(doc,'审阅记录')}
    for heading in ('输入记录','输出记录','参考版本'):
        for row in records(doc, heading):
            if row['执行编号'] not in MISSING and row['执行编号'] not in executions:
                raise ValueError(heading+'引用不存在的执行编号：'+row['执行编号'])
    for row in records(doc,'返修记录'):
        for field, available in [('原执行编号',executions),('后续执行编号',executions),('审阅编号',reviews)]:
            if row[field] not in MISSING and row[field] not in available:
                raise ValueError(field+'未找到：'+row[field])
    owner = owner_for(root, path)
    for row in records(doc,'输入记录'):
        if '输入用途' in row:
            purpose = row['输入用途']
            if purpose not in {'模特参考', '服装参考', '发型参考', '配饰参考', '其他参考'}:
                raise ValueError('输入用途须为模特参考、服装参考、发型参考、配饰参考或其他参考')
            if purpose in {'服装参考', '发型参考', '配饰参考'}:
                if row['资源引用'] in MISSING:
                    raise ValueError(purpose+'须引用具体图片版本，无图片时不建输入行')
                image = media_reference(root, path, row['资源引用'])
                if not image['resource_id'].startswith('IMG-') or Path(image['file']).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
                    raise ValueError(purpose+'须引用PNG、JPEG或WebP图片')
        if row['资源引用'] in MISSING:
            continue
        ref = media_reference(root,path,row['资源引用'])
        if owner != root/'综合资料' and ref['owner'] == '综合资料':
            data = json.loads((owner/'资源/共用引用.json').read_text('utf-8'))
            if data['references'].get(row['共用引用键']) != ref:
                raise ValueError('实际共用输入与共用引用表不一致')
        elif row['共用引用键'] != '不适用':
            raise ValueError('非视频共用输入的引用键须为不适用')
    for row in records(doc, '发布资料'):
        if row['成片文件'] not in MISSING:
            match = LINK.fullmatch(row['成片文件'])
            if not match or Path(match[2]).is_absolute():
                raise ValueError('成片文件必须链接本视频成片目录的实际视频')
            target = (path.parent/match[2]).resolve()
            if not target.is_relative_to(owner/'成片') or not target.is_file() or target.suffix.lower() not in resources.KINDS['视频']:
                raise ValueError('成片文件必须链接本视频成片目录的实际视频')
        if row['挂品链接'] not in MISSING and not re.match(r'^https?://[^\s]+$', row['挂品链接']):
            raise ValueError('挂品链接须为HTTP(S)原始链接')
    for row in records(doc,'发布记录'):
        copy_link = LINK.fullmatch(row['文案'])
        if copy_link and copy_link[2] == '发布资料.md':
            identity, title = owner.name.split('-', 1)
            prepared = read_document(root, owner/'发布资料.md', template('chloe-handoff', '发布资料模板.md'), {'identity': identity, 'title': title})
            material = next((r for r in records(prepared, '发布资料') if r['资料编号'] == copy_link[1]), None)
            if material is None:
                raise ValueError('发布记录引用不存在的发布资料编号')
            for actual, source in [('发布文件','成片文件'),('标签','话题'),('款式或SKU','款式或SKU'),('挂品链接','挂品链接')]:
                if row[actual] != material[source]:
                    raise ValueError('发布记录与所引用资料不一致：'+actual)
            for field in ('横版封面引用', '竖版封面引用'):
                if row[field] != '不适用' and row[field] != material[field]:
                    raise ValueError('发布记录与所引用资料不一致：'+field)
        match = LINK.fullmatch(row['发布文件'])
        if not match:
            raise ValueError('发布文件必须直接链接本视频成片目录的实际文件')
        target = (path.parent/match[2]).resolve()
        if not target.is_relative_to(owner/'成片') or not target.is_file():
            raise ValueError('发布文件必须直接链接本视频成片目录的实际文件')
        if target.suffix.lower() not in resources.KINDS['视频']:
            raise ValueError('发布文件必须是支持的视频文件，不能引用文本、图片或音频')
        if row['发布方式'] == '定时发布' and row['计划发布时间'] in MISSING:
            raise ValueError('定时发布缺少计划发布时间')
        if row['发布进展'] == '已发布':
            if row['授权依据'] in MISSING:
                raise ValueError('已发布记录缺少实际授权或手动发布反馈依据')
            if not has_evidence(path, row['结果证据']):
                raise ValueError('已发布记录的发布结果证据须链接原文件或来源URL')
    if current:
        published = any(r['发布进展'] == '已发布' for r in records(doc,'发布记录'))
        if (current['视频状态'] == '已发布') != published:
            raise ValueError('视频状态与实际已发布记录不一致')
    publication_rows = {r['发布编号']: r for r in records(doc, '发布记录')}
    for row in records(doc,'效果数据'):
        if row['发布编号'] not in publication_rows:
            raise ValueError('效果数据引用不存在的发布编号')
        publication = publication_rows[row['发布编号']]
        if (publication['发布进展'] not in {'已发布', '已撤回'} or
                any(publication[k] in MISSING for k in ('授权依据', '结果证据'))):
            raise ValueError('效果数据须关联有实际发布依据的记录，撤回后保留历史发布事实')
        if not has_evidence(path, publication['结果证据']):
            raise ValueError('效果数据关联的发布结果证据须链接原文件或来源URL')
        if row['指标值'] not in MISSING and not has_evidence(path, row['来源']):
            raise ValueError('效果数据的实际指标须链接原始来源')
        if (row['采集时间'] not in MISSING and publication['实际发布时间'] not in MISSING
                and datetime.fromisoformat(row['采集时间']) < datetime.fromisoformat(publication['实际发布时间'])):
            raise ValueError('效果数据采集时间不得早于实际发布时间')
    snapshots = {}
    for heading, fields in (
        ('效果数据', ('统计起始时间', '统计结束时间', '采集时间')),
        ('跨视频结论', ('观察起始时间', '观察结束时间', '记录时间')),
    ):
        for row in records(doc, heading):
            known = [(field, datetime.fromisoformat(row[field])) for field in fields if row[field] not in MISSING]
            for (first, start), (second, end) in zip(known, known[1:]):
                if start > end:
                    raise ValueError(heading+'：'+first+'不得晚于'+second)
    for row in records(doc,'效果数据'):
        window = tuple(row[k] for k in ('发布编号','采集时间','统计起始时间','统计结束时间'))
        if row['采集编号'] in snapshots and snapshots[row['采集编号']] != window:
            raise ValueError('同一采集编号的发布对象或时间窗口不一致')
        snapshots[row['采集编号']] = window
    captures = {r['采集编号'] for r in records(doc,'效果数据')}
    for row in records(doc,'单条复盘'):
        if row['采集编号'] != '不适用' and not set(row['采集编号'].split('、')) <= captures:
            raise ValueError('单条复盘引用不存在的采集编号')
        if row['采集编号'] != '不适用':
            for capture in row['采集编号'].split('、'):
                if not any(r['采集编号'] == capture and r['指标值'] not in MISSING for r in records(doc, '效果数据')):
                    raise ValueError('单条复盘引用的采集记录尚无实际指标值')
        if row['采集编号'] == '不适用' and not has_evidence(path, row['内容判断']+' '+row['局限']):
            raise ValueError('纯内容复盘须在内容判断或局限中链接实际成片或原分析记录')
    for row in records(doc, '跨视频结论'):
        sources = [m.group() for m in LINK.finditer(row['视频与证据'])]
        if not sources:
            raise ValueError('跨视频结论须链接实际采集或单条复盘记录')
        for source in sources:
            review_record(root, path, source, 'DR')
    conclusions = {r['复盘编号']: r for r in records(doc,'跨视频结论')}
    for row in records(doc,'建议验证'):
        if LINK.fullmatch(row['复盘编号']):
            source = review_record(root, path, row['复盘编号'], 'R')[0]
        elif row['复盘编号'] not in conclusions:
            raise ValueError('建议验证引用不存在的复盘编号')
        else:
            source = conclusions[row['复盘编号']]
        if source['调整建议'] in MISSING:
            raise ValueError('建议验证的来源复盘尚无具体调整建议')
        for _, href in LINK.findall(row['验证对象']):
            if not re.fullmatch(r'https?://[^\s]+', href) and not (path.parent/href.split('#')[0]).is_file():
                raise ValueError('验证对象须链接具体文件，不能只链接目录')
        has_result = bool(row['验证结果'].strip()) and row['验证结果'] not in MISSING
        if row['采用状态'] == '采用':
            if not row['采用依据'].strip() or row['采用依据'] in MISSING:
                raise ValueError('建议验证：采用须有采用依据')
        if row['采用状态'] == '采用' or has_result:
            if not LINK.search(row['验证对象']):
                raise ValueError('建议验证：采用或填写结果时须链接实际验证对象')
            if not row['验证方法'].strip() or row['验证方法'] in MISSING:
                raise ValueError('建议验证：采用或填写结果时须有验证方法')
        evidence_links = LINK.findall(row['结果证据'])
        if has_result and not evidence_links:
            raise ValueError('建议验证：填写验证结果时须链接结果证据')
        for _, href in evidence_links:
            if not re.fullmatch(r'https?://[^\s]+', href) and not (path.parent/href.split('#')[0]).is_file():
                raise ValueError('建议验证：每个结果证据链接须指向具体文件或来源URL：'+href)


def check_segment_plan(doc, total_duration):
    section = next(section for section in doc['sections'] if section['heading'] == '镜头与分镜')
    shots = [(shot['fields']['镜号'], shot['fields']['时长'].removesuffix('秒').strip()) for shot in section['shots']]
    if section['tables']:
        shots = [(row['镜头编号'], row['时长秒']) for row in records(doc, '镜头与分镜')]
    planned = records(doc, '分段计划')
    segment_ids = [row['分段编号'] for row in planned]
    if len(segment_ids) != len(set(segment_ids)):
        raise ValueError('分段编号重复')
    covered = [identity for row in planned for identity in row['镜头编号'].split('、')]
    if covered != [identity for identity, _ in shots]:
        raise ValueError('分段计划须按脚本顺序完整覆盖每个镜头一次，不得漏镜、重复或乱序')
    if any(value in MISSING or Decimal(value) <= 0 for _, value in shots):
        raise ValueError('已分段的镜头须填写大于零的实际计划时长')
    durations = {identity: Decimal(value) for identity, value in shots}
    for row in planned:
        if not re.fullmatch(r'P\d{3,}', row['分段编号']):
            raise ValueError('分段编号格式错误')
        if row['时长秒'] in MISSING or Decimal(row['时长秒']) != sum(durations[identity] for identity in row['镜头编号'].split('、')):
            raise ValueError(row['分段编号']+'计划时长须等于所含镜头时长之和')
    if total_duration not in MISSING and Decimal(total_duration) != sum(durations.values()):
        raise ValueError('脚本计划总时长须等于全部镜头及分段时长之和')


def check_system(root, owner):
    index = resources.read_index(owner)
    if not index or index['format'] != 1 or index['managed'] is not True:
        raise ValueError('资源索引未按共用格式初始化：'+str(owner))
    for field in ('families','next_versions','outputs','files','aliases'):
        if not isinstance(index[field],dict):
            raise ValueError('资源索引字段类型错误：'+field)
    for kind in resources.KINDS:
        if not (owner/'资源'/kind).is_dir():
            raise ValueError('缺少固定资源分类：'+kind)
    for file, ref in index['files'].items():
        target = resources.local(owner,file)
        family = json.loads((target.parent.parent/'资源信息.json').read_text('utf-8'))
        if ref['file'] != file or family['resource_id'] != ref['resource_id']:
            raise ValueError('资源信息与索引不一致')
        # Queue reservations have an output identity but no version directory yet.
        if not target.parent.exists() and file in index['outputs'].values():
            continue
        info = json.loads((target.parent/'版本信息.json').read_text('utf-8'))
        if any(info[k] != ref[k] for k in ('resource_id','version','file','kind','origin','producer','parent')):
            raise ValueError('版本信息与索引不一致')
        if info['facts']['bytes'] != target.stat().st_size:
            raise ValueError('版本文件大小与记录不符')
    if any(file not in index['files'] for file in index['outputs'].values()):
        raise ValueError('任务输出引用了不存在的资源')
    if owner != root/'综合资料':
        for name in ('剪辑交接','成片'):
            if not (owner/name).is_dir():
                raise ValueError('缺少固定目录：'+name)
        data = json.loads((owner/'资源/共用引用.json').read_text('utf-8'))
        if set(data) != {'format','references'} or data['format'] != 1 or not isinstance(data['references'],dict):
            raise ValueError('共用引用格式错误')
        for key, ref in data['references'].items():
            target = resources.version_file(root/'综合资料',ref['resource_id'],ref['version'])
            expected = {'owner':'综合资料','resource_id':ref['resource_id'],'version':ref['version'],'file':target.relative_to(root).as_posix()}
            if not key.strip() or ref != expected or not target.is_file():
                raise ValueError('共用引用键或准确版本错误：'+key)
        for path in (owner/'剪辑交接').glob('*.jianying.json'):
            check_manifest(owner,path)


def check_manifest(owner, path):
    data = json.loads(path.read_text('utf-8'))
    if not isinstance(data['name'],str) or not data['name'].strip() or not data['media']:
        raise ValueError('剪映清单缺少名称或媒体')
    names = set(); timeline = False
    for item in data['media']:
        if not isinstance(item['member'], str) or not item['member'].strip():
            raise ValueError('剪映包内名称不能为空')
        member = PurePosixPath(item['member'])
        if (member.is_absolute() or '..' in member.parts or '\\' in item['member'] or
                item['member'] in names or item['member'] in ('draft_content.json','draft_info.json','draft_meta_info.json')):
            raise ValueError('剪映包内名称重复或越界')
        target = resources.local(owner,item['file'])
        if not target.is_file():
            raise ValueError('剪映媒体不存在')
        if 'timeline' not in item or not isinstance(item['timeline'],bool):
            raise ValueError('Chloe剪映清单必须显式填写布尔值timeline')
        names.add(item['member']);timeline |= item['timeline']
    if not timeline:
        raise ValueError('剪映清单没有时间线媒体')


def check_workspace(root, only=None):
    results = []; errors = []
    entries = list(documents(root))
    if only is not None:
        entries = [entry for entry in entries if entry[0].resolve() == only.resolve()]
        if not entries:
            raise ValueError('不是已登记的Chloe固定文档：'+str(only))
    for path, source, fields in entries:
        try:
            read_document(root,path,source,fields)
            results.append(path.relative_to(root).as_posix())
        except (ValueError, KeyError, TypeError, OSError) as error:
            errors.append({'file':str(path),'error':str(error)})
    if only is None:
        owners = [root/'综合资料']+sorted(p for p in (root/'projects').iterdir() if p.is_dir())
        for owner in owners:
            try:
                check_system(root,owner)
                if owner.parent == root/'projects':
                    sys.path.insert(0, str(SKILLS/'chloe-production/scripts'))
                    from chloe_production import check
                    check(owner)
            except (ValueError, KeyError, TypeError, OSError) as error:
                errors.append({'file':str(owner/'资源'),'error':str(error)})
    return {'checked_documents':len(results)+len([e for e in errors if e['file'].endswith('.md')]),'errors':errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['check','read','asset-status'])
    parser.add_argument('--project-root',required=True,type=Path,help='明确选定的 Chloe 具名项目根目录')
    parser.add_argument('--file',type=Path,help='相对于具名项目根目录的固定文档路径，或绝对路径')
    args = parser.parse_args(); root=project_path(args.project_root)
    path = (root/args.file).resolve() if args.file else None
    if args.action == 'check':
        result = check_workspace(root,path)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        raise SystemExit(1 if result['errors'] else 0)
    if args.action == 'asset-status':
        assets = [asset_status(entry[0], read_document(root, *entry)) for entry in documents(root)
                  if entry[0].name in REQUIRED_ASSET_IMAGES and (path is None or entry[0].resolve() == path)]
        if path is not None and not assets:
            parser.error('不是已登记的Chloe共用图片资产说明')
        print(json.dumps(assets, ensure_ascii=False, indent=2))
        return
    if path is None:
        parser.error('read需要--file')
    entry = next((e for e in documents(root) if e[0].resolve() == path),None)
    if entry is None:
        parser.error('不是已登记的Chloe固定文档')
    print(json.dumps(read_document(root,*entry),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
