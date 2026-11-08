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


TABLE = re.compile(r"^[ \t]*\|[ \t]*编号[ \t]*\|[ \t]*项目名称[ \t]*\|[^\n]*\n(?:[ \t]*\|[^\n]*\|[ \t]*(?:\n|$))+", re.MULTILINE)
STATUSES = ('进行中', '已归档')


def index_entries(text):
    entries = []
    has_tables = bool(TABLE.search(text))
    section = None
    for line in text.splitlines():
        if line.startswith('## '):
            section = line[3:].strip() if line[3:].strip() in STATUSES else None
        row = re.match(r"^\s*\|\s*[0-9]+\s*\|\s*([^|]+?)\s*\|", line)
        legacy = re.match(r"^\s*[0-9]+\.\s+(.+?)\s*$", line) if not has_tables else None
        if row or legacy:
            entries.append((section, (row or legacy)[1]))
    return entries


def read_index(root):
    path = Path(root) / INDEX_NAME
    if path.resolve().parent != Path(root).resolve():
        raise ValueError('项目总索引不在指定目录内')
    text = path.read_text(encoding='utf-8-sig') if path.exists() else ''
    return text, [name for _, name in index_entries(text)]


def project_directories(root, *, nested=False):
    root = Path(root).resolve()
    return [p for p in sorted(root.iterdir()) if p.is_dir() and not p.name.startswith('.')
            and p.name != '综合资料' and p.resolve().parent == root and not (p / '.archived').is_file()
            and (not nested or (not p.is_symlink() and (p / 'README.md').is_file()
                                and (p / 'projects').is_dir() and (p / '综合资料').is_dir()))]


def ordered_projects(root, directories):
    root = Path(root)
    available = {p.name: p for p in directories}
    _, indexed = read_index(root)
    names = dict.fromkeys([*indexed, *sorted(available)])
    projects = [{'id': name, 'name': name, **read_archive(available[name])}
                for name in names if name in available]
    return [p for p in projects if p.get('archive', {}).get('status') != 'archived'] + [
        p for p in projects if p.get('archive', {}).get('status') == 'archived']


def sync_index(root, *, nested=False, project=None):
    """Synchronize classification from READMEs; preserve order within each table."""
    root = Path(root).resolve()
    text, indexed = read_index(root)
    entries = index_entries(text)
    if len(indexed) != len(set(indexed)):
        raise ValueError('项目总索引存在重复项目，请先核对条目')
    if project is None:
        available = {p.name: p for p in project_directories(root, nested=nested)}
    else:
        project = Path(project).resolve()
        if project.parent != root or not project.is_dir():
            raise ValueError('项目须为索引所在目录的实际子目录')
        available = {p.name: p for p in project_directories(root, nested=nested)
                     if p.name in indexed or p == project}
        if project.name not in available:
            raise ValueError('项目不符合当前工作区的项目目录规则')
    if any('|' in name or '\n' in name or '\r' in name for name in available):
        raise ValueError('项目目录名不能包含表格竖线或换行')
    archives = {name: read_archive(path).get('archive', {}) for name, path in available.items()}
    status = {name: '已归档' if value.get('status') == 'archived' else '进行中' for name, value in archives.items()}
    groups = {}
    for group in STATUSES:
        kept = [name for section, name in entries if name in available and status[name] == group and section in (None, group)]
        moved = [name for section, name in entries if name in available and status[name] == group and section not in (None, group)]
        new = [name for name in available if name not in indexed and status[name] == group]
        groups[group] = kept + moved + new
    template = (Path(__file__).resolve().parents[1] / 'templates/项目总索引.md').read_text(encoding='utf-8')
    tables = {}
    for group, table in zip(STATUSES, TABLE.findall(template)):
        rows = []
        for number, name in enumerate(groups[group], 1):
            values = [f'{number:02d}', name]
            if group == '已归档':
                values.append(archives[name]['reason'].replace('|', '&#124;'))
            rows.append('| ' + ' | '.join(values) + ' |')
        tables[group] = table.rstrip() + ('\n' + '\n'.join(rows) if rows else '') + '\n'
    if all(re.search(r'^## ' + group + r'\s*$', text, re.MULTILINE) for group in STATUSES):
        # Only replace the two owned tables; keep notes and other sections in place.
        seen = []
        def replace_table(match):
            headings = re.findall(r'^## (.+)$', text[:match.start()], re.MULTILINE)
            group = headings[-1].strip() if headings else ''
            if group not in STATUSES:
                return match[0]
            seen.append(group)
            return tables[group]
        result = TABLE.sub(replace_table, text)
        if sorted(seen) != sorted(STATUSES):
            raise ValueError('进行中与已归档各须有且只有一张项目表')
    else:
        result = template
        for group, table in zip(STATUSES, TABLE.findall(template)):
            result = result.replace(table, tables[group], 1)
        if text:
            # Migrate a legacy table/list while retaining explanatory prose.
            notes = TABLE.sub('', text)
            if not TABLE.search(text):
                notes = re.sub(r'^\s*[0-9]+\.\s+[^\n]*(?:\n|$)', '', notes, flags=re.MULTILINE)
            notes = re.sub(r'^# 项目总索引\s*$', '', notes, flags=re.MULTILINE).strip()
            if notes:
                result += '\n' + notes + '\n'
    path = root / INDEX_NAME
    if result != text:
        path.write_text(result, encoding='utf-8')
    return path


def register_project(project, *, nested=False):
    project = Path(project).resolve()
    _, names = read_index(project.parent)
    added = project.name not in names
    sync_index(project.parent, nested=nested, project=project)
    return added


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='登记项目或同步项目总索引；不改变项目状态。')
    commands = parser.add_subparsers(dest='action', required=True)
    register = commands.add_parser('register')
    register.add_argument('--project', type=Path, required=True)
    register.add_argument('--nested', action='store_true', help='具名项目直接位于工作区根目录')
    sync = commands.add_parser('sync')
    sync.add_argument('--root', type=Path, required=True, help='项目总索引所在目录')
    sync.add_argument('--nested', action='store_true')
    args = parser.parse_args()
    if args.action == 'register':
        print(register_project(args.project, nested=args.nested))
    else:
        print(sync_index(args.root, nested=args.nested))
