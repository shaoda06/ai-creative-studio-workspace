"""Explicit business adapters for the common production reviewer."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/iris-commercial-production/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-workspace-browser/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-h3-aimixer/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-h3-songssx/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/chloe-production/scripts'))
import chloe_browser_production
import iris_browser_production
import iris_workbench

ADAPTERS = {'iris-commercial-production': (iris_browser_production, iris_workbench),
            'chloe-production': (chloe_browser_production, chloe_browser_production)}


def registered(space):
    if space.production_adapter not in ADAPTERS:
        raise FileNotFoundError('该资料区未登记视频制作接入')
    return ADAPTERS[space.production_adapter]


def adapter(space):
    return registered(space)[0]


def workbench(space):
    return registered(space)[1]
