"""Compatibility import for shared index reading and drama registration."""
import importlib.util
from pathlib import Path
import sys

_TOOLS = Path(__file__).resolve().parents[2] / 'nora-workspace-browser/scripts'
sys.path.insert(0, str(_TOOLS))
from workspace_project_index import INDEX_NAME, read_index


def register_project(project):
    path = Path(__file__).resolve().parents[2] / 'nora-drama-positioning/scripts/project_index.py'
    spec = importlib.util.spec_from_file_location('nora_positioning_project_index', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.register_project(project)
