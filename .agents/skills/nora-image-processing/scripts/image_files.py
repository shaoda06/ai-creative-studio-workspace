"""Image file checks without visual judgement or business records."""
import hashlib
from copy import deepcopy
import json
from pathlib import Path
import struct
import zlib
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'nora-comfyui/scripts'))
from project_paths import project_file
import execution_records as recordio

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
        inspected.append({**item, 'width': width, 'height': height, 'format': 'PNG', 'decoded': True,
                          'image': True})
    return inspected, checked, upload_receipts, request
