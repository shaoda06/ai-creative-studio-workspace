"""Image file checks without visual judgement or business records."""
import hashlib
from copy import deepcopy
import json
import os
from pathlib import Path
import struct
import zlib
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-comfyui/scripts'))
from project_paths import project_file
import execution_records as recordio
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-workspace-browser/scripts'))
from media_files import store_media

def png(raw):
    """Validate PNG chunks, CRCs, compression, scanline sizes and filter bytes without viewing."""
    if raw[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('成果不是PNG')
    offset, image, compressed, ended = 8, None, bytearray(), False
    while offset + 12 <= len(raw):
        length = struct.unpack('>I', raw[offset:offset + 4])[0]
        kind, body = raw[offset + 4:offset + 8], raw[offset + 8:offset + 8 + length]
        end = offset + 12 + length
        if end > len(raw) or zlib.crc32(kind + body) != struct.unpack('>I', raw[end - 4:end])[0]:
            raise ValueError('PNG截断或CRC错误')
        if kind == b'IHDR':
            if image is not None or offset != 8 or length != 13:
                raise ValueError('PNG头错误')
            image = struct.unpack('>IIBBBBB', body)
        elif kind == b'IDAT':
            compressed.extend(body)
        elif kind == b'IEND':
            ended = length == 0 and end == len(raw)
            break
        offset = end
    if not image or not ended:
        raise ValueError('PNG缺少头或结束块')
    width, height, depth, color, compression, filtering, interlace = image
    allowed = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
    if not width or not height or depth not in allowed.get(color, ()) or compression or filtering or interlace not in (0, 1):
        raise ValueError('PNG编码参数无效')
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    passes = [(0, 0, 1, 1)] if not interlace else [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8),
              (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
    rows = []
    for x, y, dx, dy in passes:
        w, h = max(0, (width - x + dx - 1) // dx), max(0, (height - y + dy - 1) // dy)
        if w and h:
            rows.append((h, (w * channels * depth + 7) // 8 + 1))
    expected = sum(h * size for h, size in rows)
    decoder = zlib.decompressobj()
    try:
        pixels = decoder.decompress(compressed, expected + 1)
    except zlib.error as error:
        raise ValueError('PNG压缩数据不可解码') from error
    if len(pixels) != expected or not decoder.eof or decoder.unused_data:
        raise ValueError('PNG解码数据量不符')
    pos = 0
    for h, size in rows:
        if any(pixels[pos + row * size] > 4 for row in range(h)):
            raise ValueError('PNG扫描行滤波器无效')
        pos += h * size
    return width, height



def store_png(project, destination, raw, *, source=None, replace=False, prior=None, origin='import'):
    """Keep the PNG API while all immutable media use the same storage implementation."""
    import project_resources as resources
    destination = project_file(project, destination)
    if resources.enabled(project):
        ref = resources.reference(project, destination)
        if ref is None:
            parent = source if source is not None and Path(source).resolve().is_relative_to(Path(project).resolve()) else None
            ref = resources.reserve(project, destination, key='保存/' + resources.relative(project, destination),
                                    family=resources.family_key(destination), parent=parent, origin=origin)
            destination = resources.local(project, ref['file'])
        resources.finish(project, destination, raw=raw, source=source, replace=replace, prior=prior)
    else:
        store_media(project, destination, raw, source=source, replace=replace, prior=prior)
    return destination



def inspect_remote(data, state, outputs, planned):
    """Check actual requests, upload bindings and PNG receipts, without business documents."""
    root = Path(data.project)
    request_path = Path(data.record_dir) / data.request_name
    request = recordio.read(request_path)
    accepted = deepcopy(data.workflow)
    upload_receipts = {}
    for binding in data.uploads:
        receipt_path = Path(data.record_dir) / binding['response-name']
        receipt = upload_receipts[receipt_path] = recordio.read(receipt_path)['data']
        accepted[binding['node']]['inputs'][binding['input']] = receipt['input_path']
    if request['prompt'] != accepted or request['client_id'] != state['client_id']:
        raise ValueError('图片实际请求与已接受任务不符')
    inspected = []
    checked = [request_path, *upload_receipts]
    for item in outputs:
        candidate = project_file(root, item['path'], recorded=True)
        raw = candidate.read_bytes()
        width, height = png(raw)
        target = planned[candidate]
        if (width, height) != (target['width'], target['height']):
            raise ValueError('图片实际尺寸不符：' + item['path'])
        receipt = project_file(root, item['receipt'], recorded=True)
        checked.extend((candidate, receipt))
        proof = recordio.read(receipt)['data']
        remote = {name: item['remote'][name] for name in ('filename', 'subfolder', 'type')}
        if (proof['bytes'] != len(raw) or proof['sha256'] != hashlib.sha256(raw).hexdigest() or proof['remote'] != remote
                or project_file(root, proof['path'], recorded=True) != candidate):
            raise ValueError('图片与取回凭据不符：' + item['path'])
        store_png(root, candidate, raw)
        inspected.append({**item, 'width': width, 'height': height, 'format': 'PNG', 'decoded': True,
                          'image': True})
    return inspected, checked, upload_receipts, request


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='项目内PNG原字节保存与共享；不生成图片、不修改采用记录')
    parser.add_argument('--project', required=True, type=Path, help='实际项目根目录；所有输出及归档必须在此目录内')
    parser.add_argument('--source', required=True, type=Path, help='实际PNG源文件；外部来源只读入，不与其他项目硬链接')
    parser.add_argument('--output', required=True, help='相对项目的输出路径；相同字节复用，不覆盖不同内容')
    parser.add_argument('--archive', help='替换不同正式图片时必填的项目内旧图归档路径；先归档再原子替换')
    parser.add_argument('--resource-id', help='同一制作目标的新版本填写原资源编号')
    parser.add_argument('--key', help='同一次保存的稳定身份，重试复用')
    parser.add_argument('--parent', help='本次修改实际使用的来源文件，须为项目资源版本')
    args = parser.parse_args()
    import project_resources as resources
    target = project_file(args.project, args.output)
    source = args.source if args.source.is_absolute() else project_file(args.project, args.source)
    raw = source.read_bytes()
    width, height = png(raw)
    if resources.enabled(args.project):
        if args.archive:
            parser.error('资源版本不覆盖旧图，不使用--archive；新修订填写--resource-id')
        ref = resources.register(args.project, source, resource_id=args.resource_id, key=args.key,
                                 parent=args.parent, output=target, origin='import')
        print(json.dumps(dict(path=ref['file'], resource_id=ref['resource_id'], version=ref['version'],
                              width=width, height=height, bytes=len(raw), format='PNG', decoded=True), ensure_ascii=False))
        sys.exit(0)
    old = target.read_bytes() if target.exists() else None
    stamp = target.stat() if target.exists() else None
    if old is not None and old != raw:
        if not args.archive:
            parser.error('替换已有不同图片须提供 --archive，旧图必须保留')
        archive = project_file(args.project, args.archive)
        if archive in (target, source.resolve()):
            parser.error('归档不得与源文件或输出为同一路径')
        store_png(args.project, archive, old, source=target)
    store_png(args.project, target, raw, source=source, replace=old is not None and old != raw,
              prior=[stamp.st_size, stamp.st_mtime_ns] if stamp else None)
    print(json.dumps(dict(path=str(target), width=width, height=height, bytes=len(raw), format='PNG', decoded=True), ensure_ascii=False))
