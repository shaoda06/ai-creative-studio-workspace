"""Compatibility entry for the owning business/tool implementation."""
import importlib.util
from pathlib import Path
import runpy
import sys
_PATH = (Path(__file__).resolve().parent / '../../nora-comfyui/scripts/workflow_baselines.py').resolve()
sys.path.insert(0, str(_PATH.parent))
if __name__ == "__main__":
    runpy.run_path(str(_PATH), run_name="__main__")
else:
    _spec = importlib.util.spec_from_file_location('nora_workflow_baselines', _PATH)
    _module = sys.modules.get(_spec.name)
    if _module is None:
        _module = importlib.util.module_from_spec(_spec)
        sys.modules[_spec.name] = _module
        _spec.loader.exec_module(_module)
    sys.modules[__name__] = _module
    globals().update({name: value for name, value in vars(_module).items() if not name.startswith("_")})
