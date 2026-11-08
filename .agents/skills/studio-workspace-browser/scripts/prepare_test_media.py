"""Prepare explicitly retained test media; intermediate work always lives in a temporary directory."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.request import urlopen

from media_files import store_media
from project_paths import project_file


def prepare(root, plan):
    root = Path(root).resolve()
    outputs = [project_file(root, item['output']) for item in plan['files']]
    retained = []
    with tempfile.TemporaryDirectory(prefix='studio-test-media-') as directory:
        for command in plan.get('commands', []):
            subprocess.run([part.replace('{tmp}', directory) for part in command],
                           cwd=directory, check=True, stdin=subprocess.DEVNULL)
        for index, (item, output) in enumerate(zip(plan['files'], outputs)):
            source = item['source'].replace('{tmp}', directory)
            if source.startswith(('https://', 'http://')):
                downloaded = Path(directory) / (str(index) + output.suffix)
                with urlopen(source, timeout=30) as response, downloaded.open('wb') as stream:
                    shutil.copyfileobj(response, stream)
                source = downloaded
            else:
                source = Path(source)
                if not source.is_absolute():
                    source = root / source
            raw = source.read_bytes()
            store_media(root, output, raw, source=source)
            retained.append({'path': str(output), 'bytes': len(raw)})
    return {'files': retained, 'temporary_directory': directory, 'temporary_removed': not Path(directory).exists()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='准备隔离测试媒体：相同内容共用存储，临时下载和转码文件自动清理')
    parser.add_argument('--root', type=Path, required=True, help='已确定的隔离测试根目录')
    parser.add_argument('--manifest', type=Path, required=True, help='明确要保留的媒体及可选临时处理命令JSON')
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, json.loads(args.manifest.read_text('utf-8'))), ensure_ascii=False))
