"""Build annotated line art, side-by-side comparisons and the matching adoption record."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

from adopt_poses import filename_part, read_review

RECORD = Path('送审记录.md')
LONG_IMAGE = Path('左右对照长图.png')
FIT = ('format=rgb24,scale=1086:1448:force_original_aspect_ratio=decrease,'
       'setsar=1,pad=1086:1448:(ow-iw)/2:(oh-ih)/2:white')


def on_canvas(x, y):
    return type(x) is int and type(y) is int and 0 <= x < 1086 and 0 <= y < 1448


def read_manifest(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    items = data['items']
    if not items:
        raise ValueError('送审清单没有条目')
    if len({item['n'] for item in items}) != len(items):
        raise ValueError('送审序号重复')
    for item in items:
        number = item['n']
        if not re.fullmatch(r'[0-9]+', number):
            raise ValueError(f'送审序号应为数字字符串：{number!r}')
        filename_part(item['name'])
        if '\n' in item['name'] or not item['pose'].strip():
            raise ValueError(f'原帖 {number} 缺单行名称或定姿正文')
        if not item.get('lineart'):
            raise ValueError(f'原帖 {number} 缺原生线稿路径')
        if not item.get('source') and not item.get('note', '').strip():
            raise ValueError(f'原帖 {number} 暂缺原图，请在 note 说明缺项和未核实内容')
        for field in ('source', 'lineart'):
            value = item.get(field) if field == 'source' else item[field]
            item[field] = (path.parent / value).resolve(strict=True) if value else None
        if not item['annotations']:
            raise ValueError(f'原帖 {number} 缺图注')
        for label in item['annotations']:
            text = label['text']
            if (not text.strip() or any(char in text for char in '\r\n；') or
                    not on_canvas(label['x'], label['y'])):
                raise ValueError(f'原帖 {number} 图注应为单行短句并标出画布内的整数坐标')
            if 'leader' in label:
                points = label['leader']
                if (not isinstance(points, list) or len(points) != 4 or
                        not on_canvas(*points[:2]) or not on_canvas(*points[2:])):
                    raise ValueError(f'原帖 {number} 引线应填写画布内的 [起点X, 起点Y, 终点X, 终点Y]')
    return data.get('title', '人物姿态送审记录'), items


def render(folder, inputs, filters, destination, *, graph=False):
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y']
    for image in inputs:
        command.extend(['-i', str(image)])
    command.extend(['-filter_threads', '1', '-filter_complex_threads', '1',
                    '-filter_complex' if graph else '-vf', filters, '-frames:v', '1',
                    '-threads', '1', str(destination)])
    result = subprocess.run(command, cwd=folder, capture_output=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise ValueError(f'{destination.name} 排版失败：{result.stderr.strip()}')


def text_filter(folder, tag, text, x, y, size):
    path = folder / 'text' / f'{tag}.txt'
    path.write_text(text, encoding='utf-8')
    return (f'drawtext=fontfile=style.ttf:textfile=text/{path.name}:expansion=none:'
            f'fontcolor=0x303845:fontsize={size}:borderw=1:bordercolor=0x303845:x={x}:y={y}')


def make_pair(folder, item):
    number = item['n']
    annotated = Path('带标注线稿') / f'{number}.png'
    pair = Path('左右对比') / f'{number}.png'
    labels = [text_filter(folder, f'{number}-label-{i}', label['text'], label['x'], label['y'], 36)
              for i, label in enumerate(item['annotations'])]
    leaders = []
    for label in item['annotations']:
        if 'leader' in label:
            x1, y1, x2, y2 = label['leader']
            leaders.extend([
                f'drawbox=x={min(x1, x2)}:y={y1}:w={abs(x2 - x1) + 1}:h=1:color=0x9AA2AE:t=fill',
                f'drawbox=x={x2}:y={min(y1, y2)}:w=1:h={abs(y2 - y1) + 1}:color=0x9AA2AE:t=fill',
            ])
    render(folder, [item['lineart']], ','.join([FIT, *leaders, *labels]), annotated)

    left = FIT
    if item['source'] is None:
        left += ',lutrgb=r=255:g=255:b=255,' + text_filter(
            folder, f'{number}-missing', '原图暂缺，见送审记录', '(w-tw)/2', '(h-th)/2', 36)
    header = [
        'pad=2196:1536:0:88:white',
        'drawbox=x=1097:y=90:w=2:h=1428:color=0xDCE1E7:t=fill',
        text_filter(folder, f'{number}-heading', f"原帖 {number}　{item['name']}", 24, 11, 40),
        text_filter(folder, f'{number}-left', '原帖单图', 24, 59, 26),
        text_filter(folder, f'{number}-right', '带标注线稿', 1134, 59, 26),
    ]
    filters = (f'[0:v]{left},pad=1110:1448:0:0:white[l];'
               '[1:v]format=rgb24,setsar=1[r];[l][r]hstack,' + ','.join(header))
    render(folder, [item['source'] or item['lineart'], annotated], filters, pair, graph=True)
    return annotated, pair


def image_link(title, path):
    return f'[{title}](<{path.as_posix()}>)'


def local_link(path, base):
    try:
        return Path(os.path.relpath(path, base))
    except ValueError:  # Windows drive letters differ.
        return path


def prepare(manifest, target, font):
    title, items = read_manifest(manifest)
    if font is None:
        font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/STKAITI.TTF'
    font = font.resolve(strict=True)
    target.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix='.pose-review-', dir=target) as pending:
        folder = Path(pending)
        shutil.copyfile(font, folder / 'style.ttf')
        for name in ('text', '带标注线稿', '左右对比'):
            (folder / name).mkdir()
        record = [f'# {title}', '', image_link('整轮左右对照长图', LONG_IMAGE)]
        files = []
        pairs = []
        for item in items:
            annotated, pair = make_pair(folder, item)
            files.extend([annotated, pair])
            pairs.append(pair)
            sources = [image_link('原帖单图', local_link(item['source'], target))] if item['source'] else []
            links = [*sources, image_link('原生线稿', local_link(item['lineart'], target)),
                     image_link('单组全尺寸对比', pair), image_link('独立带标注线稿', annotated)]
            labels = '；'.join(label['text'] for label in item['annotations'])
            record.extend(['', f"## 原帖 {item['n']} {item['name']}", '', ' · '.join(links), '',
                           f"**定姿正文**：{item['pose']}", '', f'**图上标注**：{labels}'])
            if item.get('note'):
                record.extend(['', f"**逐图复核**：{item['note']}"])
        if len(pairs) == 1:
            shutil.copyfile(folder / pairs[0], folder / LONG_IMAGE)
        else:
            scaled = [f'[{i}:v]scale=1640:-2,setsar=1[r{i}]' for i in range(len(pairs))]
            rows = ''.join(f'[r{i}]' for i in range(len(pairs)))
            render(folder, pairs, ';'.join([*scaled, f'{rows}vstack=inputs={len(pairs)}']),
                   LONG_IMAGE, graph=True)
        (folder / RECORD).write_text('\n'.join(record) + '\n', encoding='utf-8')
        # Use the actual adoption reader to validate its input and every annotated PNG.
        checked = [candidate.source_number for candidate in read_review(folder / RECORD, None)]
        if checked != [item['n'] for item in items]:
            raise ValueError('生成的送审记录与长图条目顺序不一致')
        files.extend([LONG_IMAGE, RECORD])
        lock = target / '.pose-review-publishing'
        lock.mkdir()
        try:
            for file in files:
                if (target / file).exists() and (target / file).read_bytes() != (folder / file).read_bytes():
                    raise ValueError(f'已有不同的送审产出，请另用输出目录：{target / file}')
            for file in files:
                if not (target / file).exists():
                    (target / file).parent.mkdir(parents=True, exist_ok=True)
                    (folder / file).rename(target / file)
        finally:
            lock.rmdir()
    return {'count': len(items), 'record': str(target / RECORD), 'comparison': str(target / LONG_IMAGE)}


def main():
    parser = argparse.ArgumentParser(description='用同一份姿态送审数据生成带标注线稿、左右对照与可录入的送审记录。')
    parser.add_argument('--manifest', type=Path, required=True, help='UTF-8 JSON 送审数据；图片路径相对该文件所在目录')
    parser.add_argument('--output', type=Path, help='产出目录，默认与送审数据同目录；已有不同产出时使用新目录')
    parser.add_argument('--font', type=Path, help='华文楷体字体文件；默认 Windows Fonts 中的 STKAITI.TTF')
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    try:
        result = prepare(manifest, args.output.resolve() if args.output else manifest.parent, args.font)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f'送审资料制作失败：{error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
