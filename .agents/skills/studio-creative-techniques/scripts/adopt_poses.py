"""Adopt approved, annotated poses from a review record into the shared guide."""

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL.parent / 'studio-image-processing/scripts'))
from image_files import png, store_media


@dataclass(frozen=True)
class Candidate:
    source_number: str
    name: str
    description: str
    labels: tuple[str, ...]
    image: bytes


def filename_part(value):
    if (not value.strip() or value.endswith(('.', ' ')) or
            re.search(r'[<>:"/\\|?*\x00-\x1f\[\]()]', value)):
        raise ValueError(f'名称无法安全用作文件名和 Markdown 标题：{value!r}')
    return value


def read_review(review, only):
    sections = {}
    for section in re.split(r'^##[ \t]+', review.read_text(encoding='utf-8-sig'), flags=re.M)[1:]:
        title, _, body = section.partition('\n')
        if not title.startswith('原帖 '):
            continue
        heading = re.fullmatch(r'原帖 ([0-9]+) (.+)', title)
        if not heading or heading[1] in sections:
            raise ValueError(f'送审序号缺失或重复：{title}')
        sections[heading[1]] = (heading[2].strip(), body)
    if not sections:
        raise ValueError('送审记录缺少「## 原帖 序号 名称」条目')
    if only is not None and set(only) - sections.keys():
        raise ValueError('送审记录没有这些序号：' + '、'.join(sorted(set(only) - sections.keys())))

    for number, (name, body) in sections.items():
        if only is not None and number not in only:
            continue
        name = filename_part(name)
        description = re.search(
            r'^\*\*定姿正文\*\*[：:][ \t]*(.*?)(?=^\*\*图上标注\*\*[：:])', body, re.M | re.S)
        labels = re.search(r'^\*\*图上标注\*\*[：:][ \t]*(.+)$', body, re.M)
        link = re.search(r'\[独立带标注线稿\]\(<?([^\n]+?\.png)>?\)', body)
        if not description or not description[1].strip() or not labels or not link:
            raise ValueError(f'原帖 {number} 缺定姿正文、图上标注或独立带标注线稿链接')
        short_labels = tuple(label.strip() for label in labels[1].split('；'))
        if not all(short_labels):
            raise ValueError(f'原帖 {number} 有空白图注')
        image_path = (review.parent / link[1]).resolve()
        if Path(link[1]).is_absolute() or not image_path.is_relative_to(review.parent):
            raise ValueError(f'原帖 {number} 的线稿应使用本轮送审目录内的相对链接')
        image = image_path.read_bytes()
        try:
            if png(image) != (1086, 1448):
                raise ValueError('尺寸必须为 1086 × 1448 像素')
        except ValueError as error:
            raise ValueError(f'原帖 {number} 的线稿校验失败：{error}') from error
        yield Candidate(number, name, description[1].strip(), short_labels, image)


def render_entry(identity, candidate, category):
    name = candidate.name
    link = f'../../assets/人物姿态/{category}/{name}.png'
    if ' ' in link:
        link = f'<{link}>'
    labels = '\n'.join('- ' + label for label in candidate.labels)
    return (f'## {identity} {name}\n\n{candidate.description}\n\n'
            f'![{identity} {name}]({link})\n\n**图上短标注**\n\n{labels}')


def replace_text(path, text):
    with TemporaryDirectory(prefix='.pose-adopt-', dir=path.parent) as directory:
        pending = Path(directory) / path.name
        pending.write_text(text, encoding='utf-8', newline='\n')
        pending.replace(path)


def adopt(skill, category, candidates):
    references = skill / 'references'
    guide = references / '人物姿态参考表.md'
    catalog = references / '人物姿态' / f'{category}.md'
    registration = f'- [{category}](人物姿态/{category}.md)'
    heading = f'# {category}'
    text = (catalog.read_text(encoding='utf-8') if catalog.exists() else
            f'{heading}\n\n收录和转写按[人物姿态参考表](../人物姿态参考表.md)。\n')
    entries = {}
    used = set()
    for section in re.split(r'^##[ \t]+', text, flags=re.M)[1:]:
        title = section.partition('\n')[0]
        match = re.fullmatch(rf'({re.escape(category)}-([0-9]{{3}})) (.+)', title)
        if match:
            identity, number, name = match.groups()
            if number in used or name.casefold() in entries:
                raise ValueError(f'分类表有重复编号或名称：{title}')
            used.add(number)
            entries[name.casefold()] = (identity, '## ' + section.strip())

    guide_text = guide.read_text(encoding='utf-8')
    updated_guide = guide_text
    if registration not in guide_text.splitlines():
        heading_location = re.search(r'^## 分类与查用\n\n', guide_text, re.M)
        if not heading_location:
            raise ValueError('人物姿态参考表缺少「分类与查用」小节')
        start = heading_location.end()
        updated_guide = guide_text[:start] + registration + '\n' + guide_text[start:]
        if not guide_text[start:].startswith('- ['):
            updated_guide = guide_text[:start] + registration + '\n\n' + guide_text[start:]

    next_number = max((int(number) for number in used), default=0) + 1
    additions = []
    results = []
    names = set()
    for candidate in candidates:
        key = candidate.name.casefold()
        if key in names:
            raise ValueError(f'送审记录有重复名称：{candidate.name}')
        names.add(key)
        destination = skill / 'assets/人物姿态' / category / f'{candidate.name}.png'
        existing = entries.get(key)
        if existing:
            identity, previous = existing
            if previous != render_entry(identity, candidate, category) or destination.read_bytes() != candidate.image:
                raise ValueError(f'{identity} 已有同名条目，内容不同，不覆盖')
        else:
            if next_number > 999:
                raise ValueError(f'{category} 已用完三位流水号')
            identity = f'{category}-{next_number:03d}'
            next_number += 1
            if destination.exists() and destination.read_bytes() != candidate.image:
                raise ValueError(f'正式线稿已有不同内容，不覆盖：{destination}')
            additions.append((render_entry(identity, candidate, category), destination, candidate.image))
        results.append({'source': candidate.source_number, 'id': identity, 'name': candidate.name,
                        'state': '已收录' if existing else '新收录'})

    for _, destination, image in additions:
        store_media(skill, destination, image)
        if destination.read_bytes() != image:
            raise ValueError(f'正式线稿与送审图字节不一致：{destination}')
    if additions:
        catalog.parent.mkdir(parents=True, exist_ok=True)
        updated = text.rstrip() + '\n\n' + '\n\n'.join(block for block, _, _ in additions) + '\n'
        replace_text(catalog, updated)
        if catalog.read_text(encoding='utf-8') != updated:
            raise ValueError(f'分类表写入校验失败：{catalog}')
    if updated_guide != guide_text:
        replace_text(guide, updated_guide)
    return results


def main():
    parser = argparse.ArgumentParser(description='用户确认采用后，按送审记录批量把带标注线稿和定姿文字录入人物姿态参考表。')
    parser.add_argument('--review', required=True, type=Path, help='送审记录 Markdown 文件；相对路径从当前目录解析')
    parser.add_argument('--category', required=True, help='正式分类名，例如站姿或坐姿；新增分类从 001 开始')
    parser.add_argument('--only', nargs='+', metavar='原帖序号',
                        help='只收录已确认的原帖序号，如 02 07；省略则按送审顺序收录整批')
    args = parser.parse_args()
    try:
        category = filename_part(args.category.strip())
        candidates = list(read_review(args.review.resolve(), args.only))
        lock = SKILL / 'references/.pose-adoption-in-progress'
        try:
            lock.mkdir()
        except FileExistsError as error:
            raise ValueError(f'已有录入正在进行；如上一进程已中断，核实后清理空目录再重跑：{lock}') from error
        try:
            results = adopt(SKILL, category, candidates)
        finally:
            lock.rmdir()
    except (OSError, ValueError) as error:
        parser.exit(1, f'收录失败：{error}\n')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
