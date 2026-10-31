"""Compatibility entry; implementation belongs to the owning skill."""
import importlib.util
from pathlib import Path
import sys

_PATH = (Path(__file__).resolve().parent / '../../nora-drama-production/scripts/video_adopt.py').resolve()
_key = 'nora_video_adopt'
_module = sys.modules.get(_key)
if _module is None:
    sys.path.insert(0, str(_PATH.parent))
    _spec = importlib.util.spec_from_file_location(_key, _PATH)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_key] = _module
    _spec.loader.exec_module(_module)
sys.modules[__name__] = _module
globals().update({name: value for name, value in vars(_module).items() if not name.startswith("_")})
if __name__ == "__main__":
    raise SystemExit(_module.main())
