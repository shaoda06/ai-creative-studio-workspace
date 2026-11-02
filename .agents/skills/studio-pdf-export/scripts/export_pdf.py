"""Export an already selected Markdown version; content and approval belong to the caller."""
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unicodedata

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]


def merge_config(base, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_config(base[key], value)
        else:
            base[key] = value
    return base


def norm(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text)).translate(str.maketrans('⻅⻆⻚⻛⻝⻬⻓', '见角页风食齐长'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='获批Markdown或明确授权的隔离样稿；图片相对该文件')
    parser.add_argument('--profile', required=True, type=Path, help='JSON覆盖固定布局；watermark.text必填，品牌由调用方提供')
    parser.add_argument('--layout', required=True, choices=['text', 'album', 'mixed'], help='文字、图册或混合稿；混合稿支持方向分页标记')
    parser.add_argument('--orientation', choices=['portrait', 'landscape'], help='首段方向；text/mixed默认竖向，album默认横向')
    parser.add_argument('--output', required=True, type=Path, help='新建PDF，不覆盖已有版本；同时新建同名.检查.json')
    parser.add_argument('--node', default='node', help='已安装的Node可执行文件，不安装依赖')
    parser.add_argument('--node-modules', type=Path, help='可选Node包目录，以NODE_PATH提供marked和playwright')
    args = parser.parse_args()
    started = time.perf_counter()
    source, output = args.source.resolve(), args.output.resolve()
    report_file = output.with_suffix('.检查.json')
    if output.exists() or report_file.exists():
        raise FileExistsError('输出版本已存在，请另存新版本')
    cfg = merge_config(json.loads((ROOT/'assets/layout.json').read_text()), json.loads(args.profile.read_text('utf-8-sig')))
    wm = cfg['watermark']
    if not wm.get('text') or wm['layer'] != 'over' or not 0 < wm['opacity'] <= 1 or wm['count'] <= 0:
        raise ValueError('须提供有效水印文字、数量、不透明度，叠加方式为over')
    for orientation, dims in cfg['pages'].items():
        if len(wm['positions_mm'][orientation]) != wm['count']:
            raise ValueError('水印数量与该方向位置数量不一致')
        if any(not 0 <= x <= dims['width_mm'] or not 0 <= y <= dims['height_mm'] for x,y in wm['positions_mm'][orientation]):
            raise ValueError('水印中心必须在页面内')
    markdown = source.read_text('utf-8-sig')
    pieces = re.split(r'^<!-- pdf-page: (portrait|landscape) -->\s*$', markdown, flags=re.M)
    current = args.orientation or ('landscape' if args.layout == 'album' else 'portrait')
    segments = []
    if pieces[0].strip():
        segments.append(dict(orientation=current, markdown=pieces[0]))
    for direction, body in zip(pieces[1::2], pieces[2::2]):
        if body.strip():
            segments.append(dict(orientation=direction, markdown=body))
    if not segments:
        raise ValueError('Markdown没有可导出正文')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.pdf-export-', dir=output.parent) as temporary:
        work = Path(temporary)
        job = dict(source=str(source), config=cfg, segments=segments, work=str(work), result=str(work/'render-result.json'))
        (work/'job.json').write_text(json.dumps(job, ensure_ascii=False))
        env = dict(os.environ)
        if args.node_modules:
            env['NODE_PATH'] = str(args.node_modules.resolve())
        subprocess.run([args.node, str(ROOT/'scripts/render.mjs'), str(work/'job.json')], env=env, check=True)
        render = json.loads((work/'render-result.json').read_text())
        writer = PdfWriter()
        page_orientations = []
        expected = []
        for part in render['parts']:
            reader = PdfReader(part['file'])
            part_text = norm(''.join(page.extract_text() for page in reader.pages))
            missing = [line for line in part['text'].splitlines() if norm(line) and norm(line) not in part_text]
            if missing:
                raise ValueError('PDF缺少正文：' + repr(missing[:5]))
            expected.extend(norm(page.extract_text()).count(norm(wm['text'])) for page in reader.pages)
            page_orientations.extend([part['orientation']]*len(reader.pages))
            writer.append(reader)
        watermarks = {key:PdfReader(file) for key,file in render['watermarks'].items()}
        if any(len(reader.pages) != 1 or norm(reader.pages[0].extract_text()).count(norm(wm['text'])) != wm['count'] for reader in watermarks.values()):
            raise ValueError('固定水印层页数或文字数量异常')
        total = len(writer.pages)
        pages = []
        for index, (page, orientation) in enumerate(zip(writer.pages, page_orientations), 1):
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            page.merge_page(watermarks[orientation].pages[0], over=True)
            footer = BytesIO()
            canvas = Canvas(footer, pagesize=(width,height))
            canvas.setFillColorRGB(.45,.45,.45)
            canvas.setFont('Helvetica', cfg['page_number_pt'])
            canvas.drawCentredString(width/2, cfg['page_number_bottom_pt'], f'{index} / {total}')
            canvas.save(); footer.seek(0)
            page.merge_page(PdfReader(footer).pages[0], over=True)
            pages.append(dict(page=index, orientation=orientation, width_pt=width, height_pt=height))
        writer.add_metadata({'/Title':source.stem, '/Producer':'Fixed Markdown PDF export'})
        result = BytesIO(); writer.write(result); raw = result.getvalue(); check = PdfReader(BytesIO(raw))
        fonts, font_types = set(), set()
        for index, page in enumerate(check.pages):
            text = norm(page.extract_text())
            if text.count(norm(wm['text'])) != wm['count'] + expected[index] or f'{index+1}/{total}' not in text:
                raise ValueError('合并后水印数量或连续页码不符')
            for font in page['/Resources'].get('/Font', {}).values():
                data = font.get_object()
                font_types.add(str(data['/Subtype']))
                if data.get('/BaseFont'):
                    fonts.add(str(data['/BaseFont']))
        if cfg['font_family'] == 'PingFang SC':
            for part in render['parts']:
                if re.search(r'[\u4e00-\u9fff]', part['text']) and not any(font['familyName'] == 'PingFang SC' for font in part['fonts']):
                    raise ValueError('正文未实际使用指定苹方字体，检查本机字体')
            if '/Type3' not in font_types and not any('PingFang' in font for font in fonts):
                raise ValueError('PDF缺少苹方字形或具名字体')
        with output.open('xb') as stream:
            stream.write(raw)
        report = dict(source=str(source), output=str(output), layout=args.layout, config=cfg, page_count=total, pages=pages,
                      images=render['images'], fonts=sorted(fonts), pdf_font_types=sorted(font_types),
                      renderer_fonts=sorted({font['postScriptName'] for part in render['parts'] for font in part['fonts']}),
                      elapsed_seconds=round(time.perf_counter()-started,3),
                      checks=dict(markdown_text_present=True, images_loaded_and_proportional=True, continuous_page_numbers=True,
                                  watermark_count_all_pages=True, watermark_over_images=True), visual_review='pending')
        with report_file.open('x',encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(status='exported', output=str(output), report=str(report_file), pages=total,
                          elapsed_seconds=report['elapsed_seconds'], visual_review='pending'), ensure_ascii=False))


if __name__ == '__main__':
    main()
