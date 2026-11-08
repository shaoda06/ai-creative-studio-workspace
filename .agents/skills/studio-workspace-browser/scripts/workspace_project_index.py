"""Read the shared workspace project-list format without business writes."""
from pathlib import Path
import re


INDEX_NAME = "项目总索引.md"


def read_archive(project):
    """Read explicit project-management fields; production status is independent."""
    project = Path(project).resolve()
    path = project / 'README.md'
    if not path.is_file():
        return {}
    if not path.resolve().is_relative_to(project):
        raise ValueError('项目 README 不在项目内：' + project.name)
    text = path.read_text(encoding='utf-8-sig')
    text = re.sub(r'(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$', '', text)
    fields = {}
    for key, value in re.findall(r'^- (项目管理状态|归档原因|最近归档时间|最近恢复时间)：([^\r\n]*)$', text, re.MULTILINE):
        if key in fields:
            raise ValueError(f'{project.name}：归档字段重复：{key}')
        fields[key] = value.strip()
    if not fields:
        return {}
    status = fields.get('项目管理状态')
    if status not in ('进行中', '已归档'):
        raise ValueError(f'{project.name}：项目管理状态须为进行中或已归档')
    if status == '已归档' and any(fields.get(key, '') in ('', '无') for key in ('归档原因', '最近归档时间')):
        raise ValueError(f'{project.name}：已归档项目须填写归档原因和最近归档时间')
    return {'archive': {'status': 'archived' if status == '已归档' else 'active',
                        'reason': fields.get('归档原因', ''),
                        'archivedAt': fields.get('最近归档时间', ''),
                        'restoredAt': fields.get('最近恢复时间', '')}}


def read_index(root):
    path = Path(root) / INDEX_NAME
    text = path.read_text(encoding="utf-8-sig") if path.exists() else "# 项目总索引\n\n| 编号 | 项目名称 |\n| --- | --- |\n"
    rows = re.findall(r"^[ \t]*\|[ \t]*[0-9]+[ \t]*\|[ \t]*([^|\r\n]+?)[ \t]*\|(?:[^\r\n]*\|)?[ \t]*$", text, re.MULTILINE)
    names = rows or re.findall(r"^[ \t]*[0-9]+\.[ \t]+([^\r\n]+?)[ \t]*$", text, re.MULTILINE)
    return text, names
