"""Render the two fixed Chloe look review layouts from measured source images."""

import argparse
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-character-proportions/scripts'))
from proportion_charts import BACKGROUND, INK, LEGEND, MUTED, font_path, measure, percentage, point_name


VIEWS = ('正面', '右侧 45°', '背面')
FACE_ITEMS = ('face', 'shoulder')
FACE_WIDTH = 1280
FULL_HEIGHT = 960
MARGIN = 36
GAP = 28
IMAGE_TOP = 166


def panel_measurements(panel, input_dir, legend, face, baseline):
    source = panel['source']
    if not isinstance(source, str) or '@' not in source or not all(source.split('@', 1)):
        raise ValueError('source 须填写准确的图片资源编号与版本，如 IMG-…@V001')
    common = {'image': panel['image'], 'source': source}
    if face:
        points = panel['views']
        if set(points) != set(VIEWS):
            raise ValueError('views 须按正面、右侧 45°、背面填写三组测量点')
        if any(set(points[view]) - set(FACE_ITEMS) for view in VIEWS):
            raise ValueError('面部送审只填写 face 和 shoulder 测量点')
        inputs = [{**common, 'name': view, 'horizontal': points[view]} for view in VIEWS]
    else:
        inputs = [{**common, 'name': '基础模特正面' if baseline else '全身定装候选',
                   'vertical': panel['vertical'] if baseline else {}}]
    measured = [measure(item, input_dir, legend) for item in inputs]
    picture = measured[0][1]
    scale = FACE_WIDTH / picture.width if face else FULL_HEIGHT / picture.height
    size = (round(picture.width * scale), round(picture.height * scale))
    return picture.resize(size, Image.Resampling.LANCZOS), scale, [record for record, _ in measured]


def draw_face(draw, panels, image_bottom, font):
    for x, (_, scale, records) in panels:
        for index, record in enumerate(records):
            text_x = x + round(index * FACE_WIDTH / 3) + 12
            row = 0
            for point in record['horizontal']:
                if point['width_px'] is None:
                    continue
                y = IMAGE_TOP + round(point['y'] * scale)
                left = x + round(point['left'] * scale)
                right = x + round(point['right'] * scale)
                draw.line((left, y, right, y), fill=point['color'], width=3)
                for edge in (left, right):
                    draw.line((edge, y - 10, edge, y + 10), fill=point['color'], width=3)
                value = f"{point['width_px'] * scale:.0f} px"
                if point['width_pct'] is not None:
                    value += f" · {point['width_pct']}%"
                draw.text((text_x, image_bottom + 15 + row * 35), f'{point_name(point)}  {value}', fill=point['color'], font=font)
                row += 1
            ratio = record['face_to_shoulder']
            if ratio is not None:
                name = '面肩比（估）' if any(point['estimate'] for point in record['horizontal'][:2]) else '面肩比'
                draw.text((text_x, image_bottom + 15 + row * 35), f'{name}  1∶{ratio:.2f}', fill=INK, font=font)
    draw.text((MARGIN, image_bottom + 134), '像素值按两张图同宽后的画面计算。百分比以各自面宽为 100%。', fill=MUTED, font=font)
    if any(view['horizontal'][1]['estimate'] for _, (_, _, views) in panels for view in views):
        draw.text((MARGIN, image_bottom + 168), '肩宽（估）沿肩部高度的可见外轮廓取点。背面比较视觉肩宽。', fill=MUTED, font=font)


def draw_full(draw, panels, image_bottom, font, note_font):
    left, (_, scale, base_records) = panels[0]
    right, (candidate, _, _) = panels[1]
    end = right + candidate.width - 1
    baseline = base_records[0]
    for point in baseline['vertical']:
        if point['y'] is None:
            continue
        y = IMAGE_TOP + round(point['y'] * scale)
        name = point_name(point)
        if point['position_pct'] is not None:
            name += f"  {percentage(point['position_pct'], 1)}"
        label_font = font if draw.textlength(name, font=font) <= left - 24 else font.font_variant(size=19)
        draw.text((left - 16, y), name, fill=point['color'], font=label_font, anchor='rm')
        if point['estimate']:
            for x in range(left, end + 1, 14):
                draw.line((x, y, min(x + 8, end), y), fill=point['color'], width=3)
        else:
            draw.line((left, y, end, y), fill=point['color'], width=3)
    note = '全部线位和百分比取自左侧基础模特的正面，以头顶到落地线为 100%。右侧按同一高度对照。'
    if baseline['height_px'] is None:
        note = '全部线位取自左侧基础模特的正面。头顶或落地线取点缺失，按原画面高度对照可见线位。'
    draw.text((MARGIN, image_bottom + 22), note, fill=MUTED, font=note_font)


def render(kind, payload, input_dir):
    face = kind == 'face'
    legend = json.loads(LEGEND.read_text(encoding='utf-8'))
    base = panel_measurements(payload['base'], input_dir, legend, face, baseline=True)
    candidate = panel_measurements(payload['candidate'], input_dir, legend, face, baseline=False)
    model_label = f"基础模特 {payload['model']} {payload['model_version']}"
    look = payload['look']
    base_version = base[2][0]['source'].rsplit('@', 1)[1]
    candidate_version = candidate[2][0]['source'].rsplit('@', 1)[1]
    if face:
        heading = f'{look}  面部三视图'
        mode = '同宽对照 · 各自测宽'
        titles = (f'{model_label} · 头肩底图 {base_version}', f'{look} · 面部候选 {candidate_version}')
    else:
        heading = f'{look}  全身定装三视图'
        mode = '等高对照 · 左侧基准线贯穿'
        titles = (f'{model_label} · 全身底图', f'{look} · 全身定装候选 {candidate_version}')

    left = MARGIN if face else 225
    right = left + base[0].width + GAP
    panels = ((left, base), (right, candidate))
    image_bottom = IMAGE_TOP + max(base[0].height, candidate[0].height)
    canvas = Image.new('RGB', (right + candidate[0].width + MARGIN, image_bottom + (210 if face else 75)), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    font_file = str(font_path(None))
    title_font, panel_font, label_font, line_font = (ImageFont.truetype(font_file, size) for size in (40, 31, 25, 21))
    draw.text((MARGIN, 19), heading, fill=INK, font=title_font)
    draw.text((canvas.width - MARGIN, 28), mode, fill=MUTED, font=panel_font, anchor='rt')
    for (x, (picture, _, records)), title in zip(panels, titles):
        draw.text((x, 79), title, fill=INK, font=panel_font)
        draw.text((x + picture.width, 86), records[0]['source'], fill=MUTED, font=label_font, anchor='rt')
        for index, view in enumerate(VIEWS):
            center = x + round((index + 0.5) * picture.width / 3)
            draw.text((center, 133), view, fill=MUTED, font=label_font, anchor='mt')
        canvas.paste(picture, (x, IMAGE_TOP))
        draw.rectangle((x, IMAGE_TOP, x + picture.width - 1, IMAGE_TOP + picture.height - 1), outline='#CBD3D5', width=1)

    if face:
        draw_face(draw, panels, image_bottom, label_font)
    else:
        draw_full(draw, panels, image_bottom, line_font, label_font)
    info = PngImagePlugin.PngInfo()
    info.add_itxt('ReviewRecord', json.dumps({'kind': kind, 'measurements': {'base': base[2], 'candidate': candidate[2]}}, ensure_ascii=False))
    return canvas, info


def main():
    parser = argparse.ArgumentParser(description='按固定样式绘制 Chloe 造型三视图送审对照 PNG')
    parser.add_argument('kind', choices=('face', 'full'), help='face 为面部三视图，full 为全身定装原图')
    parser.add_argument('input', type=Path, help='UTF-8 测量输入 JSON，图片相对路径以 JSON 所在目录为准')
    parser.add_argument('output', type=Path, help='送审 PNG 路径，输出目录须已存在')
    args = parser.parse_args()
    try:
        if args.output.suffix.lower() != '.png':
            raise ValueError('送审输出须为 .png')
        payload = json.loads(args.input.read_text(encoding='utf-8-sig'))
        canvas, info = render(args.kind, payload, args.input.resolve().parent)
        with args.output.open('xb') as output:
            canvas.save(output, format='PNG', pnginfo=info)
    except (ValueError, TypeError, OSError, KeyError) as exc:
        parser.exit(2, f'{exc}\n')
    print(args.output.resolve())


if __name__ == '__main__':
    main()
