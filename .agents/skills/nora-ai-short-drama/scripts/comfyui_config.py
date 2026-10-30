"""Compatibility entry; implementation is owned by the shared tool skill."""
import importlib.util
from pathlib import Path
import sys

_PATH = Path(__file__).resolve().parents[2] / 'nora-comfyui/scripts/comfyui_config.py'
_spec = importlib.util.spec_from_file_location('nora_shared_comfyui_config', _PATH)
_module = sys.modules.get('nora_shared_comfyui_config')
if _module is None:
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
globals().update({name: value for name, value in vars(_module).items() if not name.startswith('_')})
if __name__ == '__main__':
    sys.exit(_module.main())
else:
    sys.modules[__name__] = _module
