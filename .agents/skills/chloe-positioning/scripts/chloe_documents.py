"""Read and check Chloe's fixed Markdown directly against its maintained templates."""
import argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path, PurePosixPath
import re
import sys

from chloe_init import ASSETS, SKILLS, resources, workspace_path

sys.path.insert(0, str(SKILLS / 'studio-storyboard/scripts'))
from storyboard_fields import read_shots

MISSING = {'待确定', '待核实', '未取得', '不适用', '无'}
LINK = re.compile(r'\[([^\]\n]+)\]\(<([^>\n]+)>\)')
MEDIA = re.compile(r'\[(共用|本视频):((?:IMG|VID|AUD)-[a-zA-Z0-9-]+)@(V[0-9]{3,})\]\(<([^>\n]+)>\)')
PREFIXES = {'事项编号': 'I', '记录编号': 'B', '事实编号': 'F', '条件编号': 'C', '卖点编号': 'S',
            '执行编号': 'E', '审阅编号': 'R', '返修编号': 'X', '交接编号': 'J',
            '发布编号': 'P', '采集编号': 'D', '复盘编号': 'R', '验证编号': 'T', '修订编号': 'U',
            '核对编号': 'K', '镜头编号': 'SH'}


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
    yield root/'README.md', template('chloe-positioning', '工作区README模板.md'), {}
    yield root/'projects/README.md', template('chloe-creative', '视频索引说明模板.md'), {}
    for name in ('账号定位', '选品记录', '运营复盘'):
        yield root/f'综合资料/{name}.md', template('chloe-positioning', name+'模板.md'), {}
    for kind, (folder, prefix, filename) in ASSETS.items():
        parent = root/'综合资料'/folder
        if not parent.is_dir():
            raise ValueError('缺少固定目录：'+str(parent))
        for item in sorted(p for p in parent.iterdir() if p.is_dir() and not p.name.startswith('.')):
            if not re.fullmatch(prefix+r'\d{3,}-.+', item.name):
                raise ValueError('资产目录编号格式错误：'+str(item))
            identity, title = item.name.split('-', 1)
            skill = 'chloe-selection' if kind == '商品' else 'chloe-assets'
            yield item/filename, template(skill, filename.replace('.md', '模板.md')), {'identity': identity, 'title': title}
    for item in sorted(p for p in (root/'projects').iterdir() if p.is_dir() and not p.name.startswith('.')):
        if not re.fullmatch(r'V\d{3,}-.+', item.name):
            raise ValueError('视频目录编号格式错误：'+str(item))
        identity, title = item.name.split('-', 1)
        for name, source in [('README.md','视频README模板.md'),('脚本.md','脚本模板.md'),('制作记录.md','制作记录模板.md')]:
            yield item/name, template('chloe-creative', source), {'identity': identity, 'title': title}


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


def read_document(root, path, source, substitutions):
    text = source.read_text('utf-8')
    for key, value in substitutions.items():
        text = text.replace('{{'+key+'}}', value)
    expected = parse(text)
    actual = parse(path.read_text('utf-8'))
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
            if fixed and [r[0] for r in tab['rows']] != [r[0] for r in base['rows']]:
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
                    if field in ('资源引用','封面引用') and value not in MISSING:
                        media_reference(root, path, value)
                    elif value.startswith(('[共用:', '[本视频:')):
                        media_reference(root, path, value)
                    for _, href in LINK.findall(value):
                        if not re.match(r'https?://', href) and not (path.parent/href.split('#')[0]).exists():
                            raise ValueError('文件链接不存在：'+href)
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


def check_relations(root, path, doc):
    image_purposes = {
        '模特说明.md': {'正面面部', '面部三视图', '全身三视图原图', '全身三视图遮面版'},
        '造型说明.md': {'全身三视图原图', '全身三视图遮面版'},
    }
    if path.name in image_purposes:
        for heading in ('参考版本', '当前采用'):
            for row in records(doc, heading):
                if row['用途'].split('/', 1)[0] not in image_purposes[path.name]:
                    raise ValueError(path.name+'：'+heading+'图片用途不在固定图种内：'+row['用途'])
    if path.name in {'服装说明.md', '场景说明.md'}:
        label = path.name[:2]
        for row in records(doc, '参考版本'):
            if row['用途'] not in {label+'参考图', label+'展示图'}:
                raise ValueError(label+'用途须为'+label+'参考图或'+label+'展示图')
        for row in records(doc, '当前采用'):
            if row['用途'] != label+'展示图':
                raise ValueError(label+'当前采用只登记'+label+'展示图')
    current = {r['字段']:r['内容'] for r in records(doc,'定位与当前进度')}
    if current and current['商品编号'] not in MISSING:
        linked_object(root,path,current['商品编号'],current['商品资料'],'G')
    for row in records(doc,'选品列表'):
        linked_object(root,path,row['商品编号'],row['商品资料'],'G')
    linked = set()
    for row in records(doc,'关联资料'):
        identity = row['对象编号']
        if identity not in MISSING:
            if identity[:1] not in {item[1] for item in ASSETS.values()}:
                raise ValueError('关联对象编号类型错误')
            linked_object(root,path,identity,row['说明文件'],identity[0])
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
    script = {r['字段']:r['内容'] for r in records(doc,'脚本信息')}
    if script and script['脚本状态'] == '已确认' and any(script[k] in MISSING for k in ('确认依据','确认时间')):
        raise ValueError('已确认脚本缺少确认依据或时间')
    executions = {r['执行编号'] for r in records(doc,'执行记录')}
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
            if row['输入用途'] not in {'模特参考', '服装参考', '其他参考'}:
                raise ValueError('输入用途须为模特参考、服装参考或其他参考')
            if row['输入用途'] == '服装参考':
                if row['资源引用'] in MISSING:
                    raise ValueError('服装参考须引用具体图片版本，无图片时不建输入行')
                clothing = media_reference(root,path,row['资源引用'])
                if not clothing['resource_id'].startswith('IMG-') or Path(clothing['file']).suffix.lower() not in {'.png','.jpg','.jpeg','.webp'}:
                    raise ValueError('服装参考须引用PNG、JPEG或WebP图片')
        if row['资源引用'] in MISSING:
            continue
        ref = media_reference(root,path,row['资源引用'])
        if owner != root/'综合资料' and ref['owner'] == '综合资料':
            data = json.loads((owner/'资源/共用引用.json').read_text())
            if data['references'].get(row['共用引用键']) != ref:
                raise ValueError('实际共用输入与共用引用表不一致')
        elif row['共用引用键'] != '不适用':
            raise ValueError('非视频共用输入的引用键须为不适用')
    publications = {r['发布编号'] for r in records(doc,'发布记录')}
    for row in records(doc,'发布记录'):
        match = LINK.fullmatch(row['发布文件'])
        if not match:
            raise ValueError('发布文件必须直接链接本视频成片目录的实际文件')
        target = (path.parent/match[2]).resolve()
        if not target.is_relative_to(owner/'成片') or not target.is_file():
            raise ValueError('发布文件必须直接链接本视频成片目录的实际文件')
        if row['发布方式'] == '定时发布' and row['计划发布时间'] in MISSING:
            raise ValueError('定时发布缺少计划发布时间')
        if row['发布进展'] == '已发布' and any(row[k] in MISSING for k in ('实际发布时间','平台作品ID','发布链接','授权依据','结果证据')):
            raise ValueError('已发布记录缺少实际发布字段')
    if current:
        published = any(r['发布进展'] == '已发布' for r in records(doc,'发布记录'))
        if (current['视频状态'] == '已发布') != published:
            raise ValueError('视频状态与实际已发布记录不一致')
    for row in records(doc,'效果数据'):
        if row['发布编号'] not in publications:
            raise ValueError('效果数据引用不存在的发布编号')
    snapshots = {}
    for row in records(doc,'效果数据'):
        window = tuple(row[k] for k in ('发布编号','采集时间','统计起始时间','统计结束时间'))
        if row['采集编号'] in snapshots and snapshots[row['采集编号']] != window:
            raise ValueError('同一采集编号的发布对象或时间窗口不一致')
        snapshots[row['采集编号']] = window
    captures = {r['采集编号'] for r in records(doc,'效果数据')}
    for row in records(doc,'单条复盘'):
        if not set(row['采集编号'].split('、')) <= captures:
            raise ValueError('单条复盘引用不存在的采集编号')
    conclusions = {r['复盘编号'] for r in records(doc,'跨视频结论')}
    for row in records(doc,'建议验证'):
        if row['复盘编号'] not in conclusions:
            raise ValueError('建议验证引用不存在的复盘编号')


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
        info = json.loads((target.parent/'版本信息.json').read_text())
        family = json.loads((target.parent.parent/'资源信息.json').read_text())
        if ref['file'] != file or family['resource_id'] != ref['resource_id']:
            raise ValueError('资源信息与索引不一致')
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
        data = json.loads((owner/'资源/共用引用.json').read_text())
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
    data = json.loads(path.read_text())
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
    parser.add_argument('action',choices=['check','read'])
    parser.add_argument('--workspace',required=True,type=Path)
    parser.add_argument('--file',type=Path,help='相对于工作区的固定文档路径，或绝对路径')
    args = parser.parse_args(); root=workspace_path(args.workspace)
    path = (root/args.file).resolve() if args.file else None
    if args.action == 'check':
        result = check_workspace(root,path)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        raise SystemExit(1 if result['errors'] else 0)
    if path is None:
        parser.error('read需要--file')
    entry = next((e for e in documents(root) if e[0].resolve() == path),None)
    if entry is None:
        parser.error('不是已登记的Chloe固定文档')
    print(json.dumps(read_document(root,*entry),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
