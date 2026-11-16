"""Render proportion charts and record the supplied image measurements."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


LEGEND = Path(__file__).resolve().parents[1] / "assets" / "比例图例.json"
BODY_HEIGHT = 820
BACKGROUND = "#F3F6F7"
INK = "#23372F"
MUTED = "#52646C"
DIVIDER = "#899A9D"
UNKNOWN = "无法判断"


def font_path(requested):
    if requested:
        return requested
    windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    candidates = [
        windows / "msyh.ttc",
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise ValueError("找不到中文字体，请用 --font 提供中文字体文件")


def read_points(raw, legend, axis, crop):
    entries = [item for item in legend if axis in item]
    if not isinstance(raw, dict) or raw.keys() - {item["id"] for item in entries}:
        raise ValueError(f"{axis} 含无效测量项，请核对固定图例")
    coords = ("y",) if axis == "vertical" else ("y", "left", "right")
    limits = {"y": (crop[1], crop[3]), "left": (crop[0], crop[2]), "right": (crop[0], crop[2])}
    points = []
    for item in entries:
        key, title = item["id"], item[axis]
        entry = raw.get(key, {"missing": "未提供测量点"})
        if not isinstance(entry, dict) or entry.keys() - {*coords, "estimate", "missing"}:
            raise ValueError(f"{title} 含无效测量字段")
        estimate, missing = entry.get("estimate"), entry.get("missing")
        for reason in ("estimate", "missing"):
            if reason in entry and (not isinstance(entry[reason], str) or not entry[reason].strip()):
                raise ValueError(f"{title} 的 {reason} 需填写原因")
        point = {"id": key, "title": title, "color": item["color"], "estimate": estimate, "missing": missing}
        if missing:
            if estimate or any(coord in entry for coord in coords):
                raise ValueError(f"{title} 的缺项原因和测量坐标应择一填写")
            point.update(dict.fromkeys(coords))
        else:
            for coord in coords:
                value = entry.get(coord)
                low, high = limits[coord]
                if type(value) not in (float, int) or not low <= value < high:
                    raise ValueError(f"{title} 的 {coord} 必须在裁切范围内")
                point[coord] = value
            if axis == "horizontal" and point["left"] >= point["right"]:
                raise ValueError(f"{title} 左端坐标应小于右端坐标")
        points.append(point)
    return points


def measure(person, input_dir, legend):
    name = person["name"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("人物栏须填写名称或版本")
    path = (input_dir / Path(person["image"]).expanduser()).resolve()
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        size = image.size
        crop = person.get("crop", [0, 0, *size])
        if (
            not isinstance(crop, list) or len(crop) != 4
            or any(type(value) is not int for value in crop)
            or not (0 <= crop[0] < crop[2] <= size[0] and 0 <= crop[1] < crop[3] <= size[1])
        ):
            raise ValueError("crop 须为图像范围内的整数裁切框")
        foreground = image.crop(crop).convert("RGBA")
        view = Image.new("RGB", foreground.size, "white")
        view.paste(foreground, mask=foreground.getchannel("A"))

    vertical = read_points(person.get("vertical", {}), legend, "vertical", crop)
    horizontal = read_points(person.get("horizontal", {}), legend, "horizontal", crop)
    measured_y = [point["y"] for point in vertical if point["y"] is not None]
    if any(first >= second for first, second in zip(measured_y, measured_y[1:])):
        raise ValueError("纵向测量点须按固定顺序从上到下")
    vertical_y = {point["id"]: point["y"] for point in vertical if point["y"] is not None}
    for point in horizontal:
        if point["y"] is not None and point["id"] in vertical_y and point["y"] != vertical_y[point["id"]]:
            raise ValueError(f"{point['title']} 的 y 须与对应纵向标线一致")

    crown, floor = vertical[0]["y"], vertical[-1]["y"]
    height = floor - crown if crown is not None and floor is not None else None
    for point in vertical:
        y = point["y"]
        point["position_pct"] = round(100 * (y - crown) / height, 1) if height and y is not None else None
    intervals = []
    for first, second in zip(vertical, vertical[1:]):
        a, b = first["position_pct"], second["position_pct"]
        intervals.append({
            "from": first["id"], "to": second["id"],
            "label": f"{first['title']}—{second['title']}",
            "height_pct": round(b - a, 1) if a is not None and b is not None else None,
        })

    for point in horizontal:
        point["width_px"] = point["right"] - point["left"] if point["y"] is not None else None
    face, shoulder = (point["width_px"] for point in horizontal[:2])
    for point in horizontal:
        width = point["width_px"]
        point["width_pct"] = round(100 * width / face) if face and width is not None else None

    record = {
        "name": name,
        "image": str(path),
        "source": person.get("source") or str(path),
        "note": person.get("note", ""),
        "image_size": list(size),
        "crop": crop,
        "height_px": height,
        "face_width_px": face,
        "vertical": vertical,
        "intervals": intervals,
        "horizontal": horizontal,
        "face_to_shoulder": round(shoulder / face, 2) if face and shoulder else None,
    }
    return record, view


def percentage(value, digits):
    return UNKNOWN if value is None else f"{value:.{digits}f}%"


def point_name(point):
    return point["title"] + ("（估）" if point["estimate"] else "")


def shortened(draw, text, font, width):
    if draw.textlength(text, font=font) <= width:
        return text
    while draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


def chart(subjects, axis, fonts, *, frame_axis=None):
    vertical = axis == "vertical"
    left, right = (165, 162) if vertical else (12, 176)
    if frame_axis == "width":
        height_to_width = max(view.height / view.width for _, view in subjects)
        frame_width = round(BODY_HEIGHT / height_to_width)
        scales = [frame_width / view.width for _, view in subjects]
    elif frame_axis == "height":
        scales = [BODY_HEIGHT / view.height for _, view in subjects]
    else:
        scales = [BODY_HEIGHT / (data["height_px"] or view.height) for data, view in subjects]
    sizes = [(max(1, round(view.width * scale)), max(1, round(view.height * scale)))
             for (_, view), scale in zip(subjects, scales)]
    picture_width = max(286, *(width for width, _ in sizes))
    crown_offsets = [
        round((data["vertical"][0]["y"] - data["crop"][1]) * scale) if not frame_axis and data["height_px"] else 0
        for (data, _), scale in zip(subjects, scales)
    ]
    body_top = 57 + max(crown_offsets)
    picture_bottom = max(body_top - offset + size[1] for offset, size in zip(crown_offsets, sizes))
    panel_height = picture_bottom + 44
    panel_width = left + picture_width + right
    panel_count = len(subjects)
    columns = min(3, panel_count)
    rows = (panel_count + columns - 1) // columns
    gap = 12
    canvas = Image.new("RGB", (columns * (panel_width + gap) - gap, rows * (panel_height + gap) - gap + 34), "#CBD3D5")
    draw = ImageDraw.Draw(canvas)
    title_font, label_font, value_font, small_font = fonts

    for index, ((data, view), scale, size, offset) in enumerate(zip(subjects, scales, sizes, crown_offsets)):
        panel_x = (index % columns) * (panel_width + gap)
        panel_y = (index // columns) * (panel_height + gap)
        image_x = panel_x + left + (picture_width - size[0]) // 2
        image_y = panel_y + body_top - offset
        readout_x = panel_x + left + picture_width + 13
        draw.rectangle((panel_x, panel_y, panel_x + panel_width - 1, panel_y + panel_height - 1), fill=BACKGROUND)
        draw.rectangle((panel_x + left, panel_y + 46, readout_x - 14, panel_y + picture_bottom), fill="white")
        canvas.paste(view.resize(size, Image.Resampling.LANCZOS), (image_x, image_y))
        name = shortened(draw, data["name"], title_font, left + picture_width - 28)
        draw.text((panel_x + 14, panel_y + 12), name, font=title_font, fill=INK)
        heading = "相邻区间" if vertical else "相对面宽"
        draw.text((readout_x, panel_y + 18), heading, font=small_font, fill=MUTED)

        points = data[axis]
        offset_x, offset_y = data["crop"][:2]
        positions = [image_y + round((point["y"] - offset_y) * scale) if point["y"] is not None else None for point in points]
        numeric_y = [y for y in positions if y is not None]
        min_gap = 25 if vertical else 46
        inline = len(numeric_y) == len(positions) and all(b - a >= min_gap for a, b in zip(numeric_y, numeric_y[1:]))
        for idx, (point, y) in enumerate(zip(points, positions)):
            color, name = point["color"], point_name(point)
            label_y = y if inline else panel_y + 79 + idx * 54
            if vertical:
                if y is not None:
                    x0, x1 = panel_x + left + 4, readout_x - 18
                    if point["estimate"]:
                        for pixel in range(x0, x1, 14):
                            draw.line((pixel, y, min(pixel + 7, x1), y), fill=color, width=2)
                    else:
                        draw.line((x0, y, x1, y), fill=color, width=2)
                label = f"{name} {percentage(point['position_pct'], 1)}"
                draw.text((panel_x + 11, label_y), label, font=label_font, fill=color, anchor="lm")
            else:
                if y is not None:
                    x0 = image_x + round((point["left"] - offset_x) * scale)
                    x1 = image_x + round((point["right"] - offset_x) * scale)
                    draw.line((x0, y, x1, y), fill=color, width=2)
                    for x in (x0, x1):
                        draw.line((x, y - 10, x, y + 10), fill=color, width=2)
                draw.text((readout_x, label_y - 21), name, font=label_font, fill=color)
                draw.text((readout_x, label_y + 1), percentage(point["width_pct"], 0), font=value_font, fill=INK)

        if vertical:
            for idx, interval in enumerate(data["intervals"]):
                value = percentage(interval["height_pct"], 1)
                if inline:
                    a, b = positions[idx] + 4, positions[idx + 1] - 4
                    draw.line((readout_x, a, readout_x, b), fill=DIVIDER, width=2)
                    for edge in (a, b):
                        draw.line((readout_x, edge, readout_x + 7, edge), fill=DIVIDER)
                    draw.text((readout_x + 16, (a + b) // 2), value, font=value_font, fill=INK, anchor="lm")
                else:
                    y = panel_y + 62 + idx * 54
                    draw.text((readout_x, y), interval["label"], font=small_font, fill=MUTED)
                    draw.text((readout_x, y + 21), value, font=label_font, fill=INK)
        else:
            ratio = data["face_to_shoulder"]
            ratio_label = f"面肩比 1∶{ratio:.2f}" if ratio is not None else f"面肩比 {UNKNOWN}"
            draw.text((readout_x, panel_y + picture_bottom + 11), ratio_label, font=label_font, fill=INK)

        note_y = panel_y + picture_bottom + 11
        if not data["height_px"]:
            draw.text((panel_x + 12, note_y), "全身高度无法判断，按取景显示", font=small_font, fill=MUTED)

    footer_y = canvas.height - 34
    draw.rectangle((0, footer_y, canvas.width - 1, canvas.height - 1), fill=BACKGROUND)
    note = "头顶到落地线为 100%，右侧为相邻区间。" if vertical else "面宽取眉眼高度的左右脸部皮肤边缘。"
    draw.text((12, footer_y + 8), note, font=small_font, fill=MUTED)
    return canvas


def main():
    parser = argparse.ArgumentParser(description="按固定图例生成纵向、横向人物比例图和测量记录")
    parser.add_argument("input", type=Path, help="UTF-8 测量输入 JSON")
    parser.add_argument("--output-dir", required=True, type=Path, help="本轮成图和记录的输出目录")
    parser.add_argument("--font", type=Path, help="中文 TTF、TTC 或 OTF 字体，默认查找系统字体")
    args = parser.parse_args()
    try:
        legend = json.loads(LEGEND.read_text(encoding="utf-8"))
        people = json.loads(args.input.read_text(encoding="utf-8-sig"))["people"]
        if not isinstance(people, list) or not people:
            raise ValueError("people 须为至少包含一名人物的列表")
        subjects = []
        for index, person in enumerate(people, 1):
            try:
                subjects.append(measure(person, args.input.resolve().parent, legend))
            except (ValueError, TypeError, OSError, KeyError) as exc:
                raise ValueError(f"第 {index} 栏：{exc}") from exc
        paths = {
            "vertical": args.output_dir.resolve() / "纵向比例图.png",
            "horizontal": args.output_dir.resolve() / "横向比例图.png",
            "record": args.output_dir.resolve() / "比例分析记录.json",
        }
        for path in paths.values():
            if path.exists():
                raise ValueError(f"输出已经存在，请使用新的输出目录：{path}")
        font = font_path(args.font)
        fonts = tuple(ImageFont.truetype(str(font), size) for size in (22, 17, 22, 15))
        rendered = {axis: chart(subjects, axis, fonts) for axis in ("vertical", "horizontal")}
        record = {
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "input": str(args.input.resolve()),
            "basis": {"vertical": "头顶到落地线", "horizontal": "眉眼高度的面宽"},
            "people": [data for data, _ in subjects],
            "outputs": {axis: {"path": str(paths[axis]), "size": list(image.size)} for axis, image in rendered.items()},
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for axis, image in rendered.items():
            image.save(paths[axis])
        paths["record"].write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=True))
    except (ValueError, TypeError, OSError, KeyError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
