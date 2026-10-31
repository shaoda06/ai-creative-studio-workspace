"""Compatibility import for the common workflow registry."""
import importlib.util
from pathlib import Path
import sys
_PATH = Path(__file__).resolve().parents[2] / 'nora-comfyui/scripts/workflow_paths.py'
_spec = importlib.util.spec_from_file_location('nora_workflow_paths', _PATH)
_module = sys.modules.get(_spec.name)
if _module is None:
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
sys.modules[__name__] = _module
globals().update({name: value for name, value in vars(_module).items() if not name.startswith('_')})
