"""Move a flat Iris project into one explicitly named work, preserving task evidence.

Dry-run is the default. The caller supplies the work identity and scope; this
script does not infer works, adoption, generation authorization or delivery.
"""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import zipfile


STAGES = ['01-客户资料', '02-参考分析', '03-创意脚本', '04-分镜声音', '05-资产', '06-视频生产', '07-返修交接', '99-综合资料']
LINK = re.compile(r'(!?\[[^\]]*\])\((?:<([^>]+)>|([^\n)]+))\)')
PRESERVED = {'执行记录', '执行附件', '候选', '采用', '审阅'}


def migration_files(project, folder):
    mapping = {'项目状态.md': folder + '/作品状态.md'}
    for stage in STAGES:
        if stage == '99-综合资料':
            continue  # Project-wide unclassified material keeps its existing scope.
        for source in sorted((project / stage).rglob('*')):
            relative = source.relative_to(project)
            if (not source.is_file() or source.is_symlink() or source.name.startswith('.')
                    or any(part in PRESERVED for part in relative.parts[1:-1])):
                continue
            # Nested technical trial folders and unpacked historical bundles stay
            # in place. Current business prose lives at the stage root or below
            # the existing director/other-materials folders.
            if len(relative.parts) > 2 and relative.parts[1] not in {'导演表', '其他资料'}:
                continue
            if stage == '01-客户资料' and not re.match(r'需求与来源', source.name):
                continue
            mapping[relative.as_posix()] = folder + '/' + relative.as_posix()
    return mapping


def sections(text):
    parts = re.split(r'^## (.+)\n', text, flags=re.MULTILINE)
    return {parts[index]: parts[index + 1].strip() for index in range(1, len(parts), 2)}


def migrate(project, folder, title, description, *, apply=False, archives=(), closed=False):
    project = Path(project).resolve()
    if not re.fullmatch(r'F\d{3,}-.+', folder):
        raise ValueError('作品目录须为 F编号-名称')
    if (project / '作品').exists():
        raise FileExistsError('项目已有作品目录，不能重复执行迁移')
    prefix = '作品/' + folder
    mapping = migration_files(project, prefix)
    index_path = project / '资源/资源索引.json'
    aliases = json.loads(index_path.read_text('utf-8-sig')).get('aliases', {}) if index_path.is_file() else {}
    readme = (project / 'README.md').read_text('utf-8-sig')
    original_sections = sections(readme)
    records = [str(path.relative_to(project)) for path in (project / '06-视频生产/执行记录',) if path.is_dir()]
    result = {'project': project.name, 'work': prefix, 'moved': mapping, 'records': records, 'archives': list(archives)}
    if not apply:
        return result

    # A single compact backup preserves original prose and navigation without
    # duplicating the media library or execution history.
    backup = project / '归档/多作品迁移前文档-20261106.zip'
    backup.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(backup, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in project.glob('*.md'):
            if path.name != '项目状态.md':
                archive.write(path, path.name)
        for key in mapping:
            archive.write(project / key, key)
        archive.writestr('迁移对应.json', json.dumps(result, ensure_ascii=False, indent=2))

    def destination(path):
        if path.is_relative_to(project):
            key = path.relative_to(project).as_posix()
            if key in STAGES and key != '01-客户资料':
                return project / prefix / key
            return project / mapping.get(key, aliases.get(key, key))
        return path

    def rewrite(text, old_key, new_key):
        old, new = project / old_key, project / new_key
        lines = []
        table_headers = []
        def plain(value):
            def path(match):
                value = match[0]
                if '://' in value:
                    return value
                candidate = (old.parent / value).resolve()
                rooted = (project / value).resolve()
                # Unlinked internal paths beginning with a stage/resource name
                # use the existing project-root convention. Other bare paths
                # (e.g. 采用/A003.png) are relative to the source document.
                is_rooted = value.split('/')[0] in {*STAGES, '资源', '归档', '08-完单复盘'}
                source = rooted if is_rooted else candidate
                if not source.is_relative_to(project):
                    return value
                key = source.relative_to(project).as_posix()
                if not (source.exists() or key in aliases or key in mapping):
                    return value
                target = destination(source)
                return target.relative_to(project).as_posix() if is_rooted else os.path.relpath(target, new.parent)
            return re.sub(r'(?<![\w/])[\w.\-\u4e00-\u9fff]+(?:/[^\s|；;，<>`\[\]()：]+)+/?', path, value)
        for line in text.splitlines():
            if line.startswith('|') and ('当前版本/文件' in line or '项目文件' in line or '归档交接记录' in line):
                table_headers = [cell.strip() for cell in line.strip().strip('|').split('|')]
            elif line.strip() and not line.startswith('|'):
                table_headers = []
            project_table = bool(table_headers) and old_key == '项目状态.md'
            def link(match):
                href = urlsplit(match[2] or match[3])
                if href.scheme or href.netloc or not href.path:
                    return match[0]
                relative = Path(unquote(href.path))
                source = (project / relative if project_table else old.parent / relative).resolve()
                target = destination(source)
                value = target.relative_to(project).as_posix() if project_table and target.is_relative_to(project) else os.path.relpath(target, new.parent)
                value += ('?' + href.query if href.query else '') + ('#' + href.fragment if href.fragment else '')
                label = match[1].replace('项目状态', '作品状态') if source == project / '项目状态.md' else match[1]
                return label + '(<'+ value + '>)'
            parts, start = [], 0
            for match in LINK.finditer(line):
                parts.extend((plain(line[start:match.start()]), link(match)))
                start = match.end()
            parts.append(plain(line[start:]))
            line = ''.join(parts)
            lines.append(line)
        return '\n'.join(lines) + '\n'

    for old_key, new_key in mapping.items():
        old, new = project / old_key, project / new_key
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        if new.suffix == '.md':
            text = rewrite(new.read_text('utf-8-sig'), old_key, new_key)
            if old_key == '项目状态.md':
                text = re.sub(r'^# .+$', '# ' + folder.split('-', 1)[0] + ' 作品状态', text, count=1, flags=re.MULTILINE)
                text = text.replace('项目：', '项目 / 作品：', 1)
                text = text.replace('\n当前阶段与下一步：', '\n作品编号与名称：' + folder + '\n当前阶段与下一步：', 1)
            new.write_text(text)
        elif new.name.endswith('.jianying.json'):
            spec = json.loads(new.read_text('utf-8-sig'))
            for item in spec['media']:
                item['file'] = destination((project / item['file']).resolve()).relative_to(project).as_posix()
            new.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n')

    work = project / prefix
    for stage in STAGES:
        (work / stage).mkdir(parents=True, exist_ok=True)
    (work / '07-返修交接/成片').mkdir(exist_ok=True)
    history = {'records': records, 'archives': list(archives)}
    (work / '06-视频生产/历史执行入口.json').write_text(json.dumps(history, ensure_ascii=False, indent=2) + '\n')
    work_readme = '# ' + folder.split('-', 1)[0] + '｜' + title + '\n\n'
    work_readme += '## 作品说明\n\n' + description + '\n\n'
    work_readme += '## 作品专用约定\n\n' + rewrite(original_sections['项目专用约定'], 'README.md', prefix + '/README.md').strip() + '\n\n'
    work_readme += '## 阶段资料入口\n\n' + rewrite(original_sections['目录与资料入口'], 'README.md', prefix + '/README.md').strip() + '\n\n'
    work_readme += '## 进度与版本入口\n\n从[作品状态](作品状态.md)核对本片有效版本、授权、审阅与下一步。\n\n'
    work_readme += '## 接续要求\n\n先读[项目说明](../../README.md)、[项目状态](../../项目状态.md)，再读本文件和作品状态，按当前阶段接续。媒体仍引用项目资源版本。\n\n'
    work_readme += '## 历史与特殊事项\n\n' + rewrite(original_sections['历史与特殊事项'], 'README.md', prefix + '/README.md').strip() + '\n\n历史执行及审阅附件保持原位置，通过本片状态及[历史执行入口](06-视频生产/历史执行入口.json)查阅。\n'
    (work / 'README.md').write_text(work_readme)

    project_readme = readme.split('\n', 1)[0] + '\n\n## 项目说明\n\n' + original_sections['项目说明'] + '\n\n'
    project_readme += '## 项目专用约定\n\n本项目可包含多件作品；同片横竖、长短版归该作品的交付版本。各片的具体内容与规格见作品说明。媒体统一按[项目资源与版本规则](../../../../.agents/skills/studio-workspace-browser/references/项目资源与版本管理.md)存入本项目资源库。\n\n'
    project_readme += '## 目录与资料入口\n\n- [' + folder + '](<' + prefix + '/README.md>)\n'
    project_readme += '- [共享客户资料](01-客户资料/)\n- [项目资源](资源/资源索引.json)\n- [整单复盘](08-完单复盘/)\n- [历史归档](归档/)\n\n'
    project_readme += '## 进度与版本入口\n\n从[项目状态](项目状态.md)核对共用事项及作品状态入口。\n\n'
    project_readme += '## 接续要求\n\n先读[Iris 工作区说明](../../README.md)、本文件与项目状态；制作具体作品时再读作品 README、作品状态及对应阶段技能。\n\n'
    project_readme += '## 历史与特殊事项\n\n' + original_sections['历史与特殊事项'] + '\n\n迁移前入口和文稿保存在[原文备份](归档/多作品迁移前文档-20261106.zip)。历史任务保持原记录。\n'
    (project / 'README.md').write_text(project_readme)
    state = '# 项目状态\n\n项目：' + project.name + '\n整体事项与下一步：具体制作从作品状态接续。\n\n## 作品入口\n\n'
    state += '| 作品编号 | 作品名称与入口 | 作品状态入口 |\n| --- | --- | --- |\n'
    state += '| ' + folder.split('-', 1)[0] + ' | [' + title + '](<' + prefix + '/README.md>) | [作品状态](<' + prefix + '/作品状态.md>) |\n\n'
    state += '## 项目共用决定与授权\n\n沿用项目与作品已有有效约定。本次目录迁移不新增媒体生成、采用或对外交付授权。\n\n'
    state += '## 跨作品待办与职责\n\n目前登记一件作品，暂无独立跨作品事项；各阶段职责见作品状态。\n\n'
    state += '## 整单交付与复盘\n\n' + ('用户已明确完成最终交付，原说明与后续高清候选审阅事实见作品状态；[项目复盘](08-完单复盘/复盘.md)保留。' if closed else '尚无用户明确整单最终交付的记录，按作品状态中的实际交接范围接续。') + '\n'
    (project / '项目状态.md').write_text(state)
    # Current project-only Markdown outside the moved stages may still link a
    # moved business file. Exclude immutable archives and execution evidence.
    for source in project.glob('*.md'):
        if source.name in {'README.md', '项目状态.md'}:
            continue
        source.write_text(rewrite(source.read_text('utf-8-sig'), source.name, source.name))
    removed = []
    for stage in STAGES:
        base = project / stage
        for path in sorted(base.rglob('*'), reverse=True):
            if (path.is_dir() and not PRESERVED.intersection(path.relative_to(base).parts)
                    and not any(path.iterdir())):
                path.rmdir()
        if base.is_dir() and not any(base.iterdir()) and stage not in {'01-客户资料', '99-综合资料'}:
            base.rmdir()
            removed.append(stage)
    result['removed_empty'] = removed
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--work', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--description', required=True)
    parser.add_argument('--archive', action='append', default=[])
    parser.add_argument('--closed', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(migrate(args.project, args.work, args.title, args.description,
                             apply=args.apply, archives=args.archive, closed=args.closed), ensure_ascii=False, indent=2))
