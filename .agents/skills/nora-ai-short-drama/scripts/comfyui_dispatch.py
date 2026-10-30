"""Compatibility command for the shared ComfyUI dispatch tool."""
import importlib.util
from pathlib import Path
import sys

_PATH = Path(__file__).resolve().parents[2] / 'nora-comfyui/scripts/comfyui_dispatch.py'
_spec = importlib.util.spec_from_file_location('nora_shared_dispatch', _PATH)
_module = sys.modules.get(_spec.name)
if _module is None:
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
globals().update({name: value for name, value in vars(_module).items() if not name.startswith('_')})
if __name__ == '__main__':
    _module.main()
else:
    sys.modules[__name__] = _module
