"""Explicit business adapters for the common production reviewer."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/iris-commercial-production/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-workspace-browser/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-h3/scripts'))
import iris_browser_production

ADAPTERS = {'iris-commercial-production': iris_browser_production}


def adapter(space):
    if space.production_adapter not in ADAPTERS:
        raise FileNotFoundError('该资料区未登记视频制作接入')
    return ADAPTERS[space.production_adapter]
