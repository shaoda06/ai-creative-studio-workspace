"""Move ordinary project media once, preserving evidence and sealed deliverables.

Stage keeps old media until the caller checks the browser projection. Finalize
only removes verified old entries. No media is backed up or copied across projects.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
import filecmp
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import project_resources as resources
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-comfyui/scripts'))
import execution_records as records
from media_files import store_media


def preserved(relative):
    parts = Path(relative).parts
    return any(part.startswith('.') or part in ('资源', '历史制作资料', '归档', '98-成片交付')
               or any(word in part for word in ('快照', '剪映草稿', '剪映包', '原生交付', '验收', '验证', '核查', '检查', '抽帧', '帧图', '初剪图层', '样稿', '原型')) for part in parts[:-1])


def logical_family(relative):
    """Migration-only interpretation of the existing Nora/Iris business names."""
    path = Path(relative)
    name = re.sub(r'^\d{2,3}-(?=(?:CH|SC|PR|RA)\d)', '', path.stem)
    video = re.search(r'((?:EP\d+|片头|片尾)-C\d+-P\d+)-R\d+-(?:一采|二采|后处理)', name)
    if video and resources.media_kind(path) == '视频':
        return '视频/' + video[1]
    if resources.media_kind(path) == '视频':
        segment = re.search(r'(?:^|[-_])(P\d{3,})(?:[-_]|$)', name)
        if segment and re.search(r'(?:一采|二采|后处理|R\d{3})', relative):
            return '视频/' + segment[1]
    if re.match(r'(?:CH|SC|PR|RA|RV|A)\d{3}|(?:EP\d+|片头|片尾)-', name) or '画风验证' in name:
        name = re.sub(r'-(?:候选-)?v\d+(?=-|$)', '', name, flags=re.I)
        name = re.sub(r'-(?:归档|留存)-\d{8}-\d{6}$', '', name)
        name = re.sub(r'-(?:超分|规格处理)-\d+$', '', name)
        return (resources.media_kind(path) or '媒体') + '/' + name
    return '历史独立素材/' + relative


def output_identity(value):
    """Retain declared historical candidates, runs and processing outputs."""
    stem = Path(value).stem
    if resources.media_kind(value) == '视频':
        match = re.search(r'((?:EP\d+|片头|片尾)-C\d+-P\d+-R\d+-(?:一采|二采|后处理).*)', stem)
    else:
        match = re.search(r'((?:候选|草稿)-v\d+(?:-(?:超分|规格处理)-\d+)?)$', stem, re.I)
    return match[1] if match else None


def key_in(project, value):
    if not isinstance(value, str) or resources.media_kind(value) is None:
        return None
    value = value.replace('\\', '/')
    if Path(value).is_absolute() and not Path(value).resolve().is_relative_to(project):
        marker = '/projects/' + project.name + '/'
        position = value.find(marker)
        if position < 0:
            return None
        value = value[position + len(marker):]
    target = (project / value).resolve()
    if not target.is_relative_to(project):
        return None
    return target.relative_to(project).as_posix()


def inspect(project):
    project = Path(project).resolve()
    if (project / '.archived').exists():
        raise PermissionError('已归档项目保持原样：' + str(project))
    media, protected, documents = {}, [], []
    for folder, dirs, names in os.walk(project, followlinks=False):
        dirs[:] = sorted(name for name in dirs if not name.startswith('.') and name != '资源'
                         and not (Path(folder) / name).is_symlink())
        for name in sorted(names):
            path = Path(folder) / name
            relative = path.relative_to(project).as_posix()
            if path.is_symlink():
                continue
            if resources.media_kind(path):
                if preserved(relative):
                    protected.append(relative)
                else:
                    media[relative] = path
            elif path.suffix.lower() == '.json' and not preserved(relative):
                documents.append(path)
    parent = {key: key for key in media}
    producers, moves, inputs = {}, {}, []

    def visit(value, owner):
        if isinstance(value, list):
            for child in value:
                visit(child, owner)
        elif isinstance(value, dict):
            record = value.get('record_dir', owner)
            if isinstance(record, str) and Path(record).is_absolute():
                marker = '/projects/' + project.name + '/'
                record = record.split(marker, 1)[-1] if marker in record else owner
            if value.get('provider') == 'imagegen' and (candidate := key_in(project, value.get('candidate'))):
                producers[candidate] = value.get('record', record)
            for output in value.get('outputs', []) if isinstance(value.get('outputs'), list) else []:
                if isinstance(output, dict) and (key := key_in(project, output.get('path'))):
                    producers[key] = record
            plan = value.get('segment_plan')
            if isinstance(plan, dict):
                for output in plan.get('targets', []):
                    if key := key_in(project, output.get('path')):
                        producers[key] = record
            if 'original_file' in value and 'file' in value:
                one, two = key_in(project, value['file']), key_in(project, value['original_file'])
                if one and two:
                    inputs.append((one, two))
            if 'source_path' in value and 'selected_path' in value:
                one, two = key_in(project, value['source_path']), key_in(project, value['selected_path'])
                if one and two:
                    moves[one] = two
            for child in value.values():
                if isinstance(child, (dict, list)):
                    visit(child, record)

    parsed, unparsed = [], []
    for path in documents:
        try:
            value = json.loads(path.read_text('utf-8-sig'))
        except json.JSONDecodeError as error:
            unparsed.append({'file': path.relative_to(project).as_posix(), 'error': str(error)})
            continue  # Explicitly report malformed historical evidence, never repair or interpret it.
        visit(value, path.parent.relative_to(project).as_posix())
        parsed.append(path)

    def root(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    identities = {key: {identity} if (identity := output_identity(key)) else set() for key in media}
    owners = {key: {producers[key]} if key in producers else set() for key in media}
    peers = {}

    def join(one, two, *, copied=False):
        if one not in media or two not in media or Path(one).suffix.lower() != Path(two).suffix.lower():
            return
        if not copied and logical_family(one) != logical_family(two):
            return
        if media[one].stat().st_size == media[two].stat().st_size and filecmp.cmp(media[one], media[two], shallow=False):
            peers.setdefault(two, peers.get(one, one))
            first, second = root(one), root(two)
            if first == second:
                return
            # An unlabelled formal copy cannot bridge two distinct executions.
            if len(identities[first] | identities[second]) > 1 or len(owners[first] | owners[second]) > 1:
                return
            parent[second] = first
            identities[first] |= identities[second]
            owners[first] |= owners[second]

    inodes, candidates = {}, defaultdict(list)
    for key, path in media.items():
        state = path.stat()
        inode = (state.st_dev, state.st_ino)
        if inode in inodes:
            join(inodes[inode], key)
        else:
            inodes[inode] = key
        group = (logical_family(key), state.st_size)
        for other in candidates[group]:
            join(other, key)
            if root(other) == root(key):
                break
        candidates[group].append(key)
    for one, two in [*inputs, *moves.items()]:
        join(one, two, copied=True)
    groups = defaultdict(list)
    for key in media:
        groups[root(key)].append(key)
    ordered = []
    for keys in groups.values():
        keys.sort(key=lambda key: (key not in producers, '输入素材' in key, key))
        ordered.append(keys)
    ordered.sort(key=lambda keys: (min(media[key].stat().st_mtime_ns for key in keys), keys[0]))
    return {'project': str(project), 'media': media, 'groups': ordered, 'protected': protected,
            'producers': producers, 'moves': moves, 'inputs': inputs, 'documents': parsed, 'unparsed_evidence': unparsed, 'peers': peers}


def rewrite_links(project, path, aliases, *, text=None):
    if text is None:
        text = path.read_text('utf-8-sig')
    def link(match):
        raw = match[1]
        parsed = urlsplit(raw.strip('<>'))
        if parsed.scheme or not resources.media_kind(parsed.path):
            return match[0]
        source = (path.parent / unquote(parsed.path)).resolve()
        if not source.is_relative_to(project):
            return match[0]
        destination = aliases.get(source.relative_to(project).as_posix())
        if destination is None:
            return match[0]
        relative = Path(os.path.relpath(project / destination, path.parent)).as_posix()
        target = urlunsplit(('', '', quote(relative, safe='/-._~'), parsed.query, parsed.fragment))
        return '](' + ('<' + target + '>' if raw.startswith('<') else target) + ')'
    return re.sub(r'\]\(([^)]+)\)', link, text)


def stage(project, audit):
    project, audit = Path(project).resolve(), Path(audit).resolve()
    report_file = audit / '迁移结果.json'
    if report_file.exists():
        return json.loads(report_file.read_text('utf-8'))
    plan = inspect(project)
    audit.mkdir(parents=True, exist_ok=True)
    mapping, versions = {}, []
    # Publish the complete index after all original media have an immutable peer.
    with resources.edit_index(project) as data:
        for keys in plan['groups']:
            source_key = keys[0]
            ref = resources._reserve(project, data, project / source_key, key='迁移/' + source_key,
                family=logical_family(source_key), origin='legacy', producer=plan['producers'].get(source_key), alias=False)
            target = project / ref['file']
            store_media(project, target, source=plan['media'][plan['peers'].get(source_key, source_key)])
            metadata = target.parent / '版本信息.json'
            if not metadata.exists():
                resources.write_json(metadata, {**ref, 'registered_at': resources.now(),
                    'facts': {'bytes': target.stat().st_size, 'verification': 'legacy_not_revalidated'},
                    'legacy_locations': keys, 'original_modified_at_ns': plan['media'][source_key].stat().st_mtime_ns})
            versions.append(ref)
            for key in keys:
                mapping[key] = ref['file']
        for old, new in plan['moves'].items():
            if old not in mapping and new in mapping:
                mapping[old] = mapping[new]
        data['aliases'].update(mapping)
        data.setdefault('alias_stamps', {}).update({key: {'bytes': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns}
                                                  for key, path in plan['media'].items()})
    associations = {}
    for path in plan['documents']:
        refs = resources.refs_in(project, json.loads(path.read_text('utf-8-sig')))
        if refs:
            item = associations.setdefault(path.parent, {'migration_sources': [], 'references': {}})
            item['migration_sources'].append(path.relative_to(project).as_posix())
            item['references'].update({resources.label(ref): ref for ref in refs})
    for directory, item in associations.items():
        path = directory / '资源关联.json'
        if not records.exists(path):
            resources.write_json(path, {**item, 'references': list(item['references'].values())})
    changed = []
    for path in project.rglob('*.md'):
        key = path.relative_to(project).as_posix()
        # Original review text and historical snapshots keep their bytes.
        if preserved(key) or any(part in ('历史版本', '执行附件', '审阅', '审阅记录') for part in Path(key).parts):
            continue
        new = rewrite_links(project, path, mapping)
        if new != path.read_text('utf-8-sig'):
            backup = audit / '原文档' / key
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(path.read_bytes())
            path.write_text(new, 'utf-8')
            changed.append(key)
    report = {'project': str(project), 'status': 'staged', 'aliases': mapping, 'versions': versions,
        'media_count': len(plan['media']), 'version_count': len(versions), 'protected': plan['protected'],
        'unparsed_evidence': plan['unparsed_evidence'],
        'documents_updated': changed, 'originals': {key: {'bytes': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns}
                                                     for key, path in plan['media'].items()}}
    resources.write_json(report_file, report)
    return report


def finalize(project, audit):
    project, audit = Path(project).resolve(), Path(audit).resolve()
    path = audit / '迁移结果.json'
    report = json.loads(path.read_text('utf-8'))
    if report['project'] != str(project):
        raise ValueError('迁移报告不属于这个项目')
    # Complete validation precedes every removal; interrupted finalization is resumable.
    for old, stamp in report['originals'].items():
        source, target = project / old, project / report['aliases'][old]
        if not target.is_file() or target.stat().st_size != stamp['bytes']:
            raise ValueError('资源目标缺失或大小不符：' + old)
        if source.exists() and ([source.stat().st_size, source.stat().st_mtime_ns] != [stamp['bytes'], stamp['mtime_ns']]
                               or not filecmp.cmp(source, target, shallow=False)):
            raise ValueError('迁移期间原文件已变化，停止移除：' + old)
    for old in report['originals']:
        source = project / old
        target = project / report['aliases'][old]
        if os.name == 'nt' and source.exists():
            source.chmod(source.stat().st_mode | 0o200)
        try:
            source.unlink(missing_ok=True)
        finally:
            if os.name == 'nt':
                target.chmod(target.stat().st_mode & ~0o222)
    removed = []
    parents = {parent for old in report['originals'] for parent in (project / old).parents if parent != project and parent.is_relative_to(project)}
    for folder in sorted(parents, key=lambda item: len(item.parts), reverse=True):
        parts = folder.relative_to(project).parts
        media_container = any(part in ('素材', '输入素材', '候选', '候选视频', '参考图', '其他参考图', '原素材', '正式素材', '06-阶段采用视频', '阶段采用视频', '06-生成结果') for part in parts)
        if not media_container and re.match(r'^(?:\d{2}-|(?:EP|CH|SC|PR)\d{3,}(?:-|$))', folder.name):
            continue  # Keep business stages, episode roots and asset-card directories.
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir(); removed.append(folder.relative_to(project).as_posix())
    resources.initialize(project, managed=True)
    report.update(status='completed', empty_directories_removed=removed)
    resources.write_json(path, report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--audit', type=Path, help='本次授权整理的记录备份与映射目录；不备份媒体')
    parser.add_argument('action', choices=('inspect', 'stage', 'finalize'))
    args = parser.parse_args()
    if args.action == 'inspect':
        data = inspect(args.project)
        print(json.dumps({'project': data['project'], 'media': len(data['media']), 'versions': len(data['groups']),
                          'protected': len(data['protected'])}, ensure_ascii=False))
    else:
        if not args.audit:
            parser.error('stage/finalize必须提供--audit')
        result = (stage if args.action == 'stage' else finalize)(args.project, args.audit)
        print(json.dumps({key: result[key] for key in ('project', 'status', 'media_count', 'version_count')}, ensure_ascii=False))
