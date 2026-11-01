"""Read a local workspace service without business identities or adoption policy."""
import json
from pathlib import Path
import sys
import urllib.request
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'nora-comfyui/scripts'))
from comfyui_client import strict_json


def open_service(workspace, timeout):
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
    return base, get
