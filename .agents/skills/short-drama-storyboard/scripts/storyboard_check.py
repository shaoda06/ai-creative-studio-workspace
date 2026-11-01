"""Compatibility entry; the implementation lives in the workspace-prefixed skill."""
import importlib.util
from pathlib import Path
import sys

_PATH = (Path(__file__).resolve().parent / '../../nora-drama-storyboard/scripts/storyboard_check.py').resolve()
sys.path.insert(0, str(_PATH.parent))
if __name__ == '__main__':
    import runpy
    runpy.run_path(str(_PATH), run_name='__main__')
else:
    _spec = importlib.util.spec_from_file_location('_nora_compat_nora_drama_storyboard_storyboard_check', _PATH)
    _module = sys.modules.get(_spec.name)
    if _module is None:
        _module = importlib.util.module_from_spec(_spec)
        sys.modules[_spec.name] = _module
        _spec.loader.exec_module(_module)
    sys.modules[__name__] = _module
    globals().update(vars(_module))
