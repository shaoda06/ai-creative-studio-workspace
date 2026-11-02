"""Read a local workspace service without business identities or adoption policy."""
import json
from pathlib import Path
import sys
import urllib.request
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-comfyui/scripts'))
from comfyui_client import strict_json


def open_service(workspace, timeout, *, with_metadata=False):
    workspace = Path(workspace).resolve()
    config = strict_json((workspace / '工作区浏览服务/runtime/task-service.json').read_bytes())
    base = config['url'].rstrip('/')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(route, *, text=False):
        with opener.open(base + (config.get('api_prefix', '/api') + route[4:] if route.startswith('/api/') else route), timeout=timeout) as response:
            return response.read().decode('utf-8-sig') if text else json.load(response)

    service = get('/api/service')
    if not service['ready'] or Path(service['workspace']).resolve() != workspace:
        raise ValueError('浏览服务未就绪或读取了其他工作区')
    return (base, get, service) if with_metadata else (base, get)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='只读定位本空间及统一服务的工具真源，不输出token或执行任务')
    parser.add_argument('--workspace', required=True, type=Path, help='含工作区浏览服务/runtime/task-service.json的实际工作区根目录')
    parser.add_argument('--timeout', type=float, default=30, help='每次元数据GET的阻塞超时秒数，默认30')
    args = parser.parse_args()
    _, _, metadata = open_service(args.workspace, args.timeout, with_metadata=True)
    provider = Path(metadata['tool']).parent
    print(json.dumps({'ready': metadata['ready'], 'version': metadata['version'],
                      'workspace': metadata['workspace'], 'tool': metadata['tool'],
                      'workspace_skills': str(provider / '.agents/skills'),
                      'provider_skills': str(provider / '.agents/skills')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
