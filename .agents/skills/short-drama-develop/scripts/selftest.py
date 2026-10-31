"""Compatibility entry; implementation belongs to its business stage."""
import importlib.util
from pathlib import Path
import sys

_PATH = Path(__file__).resolve().parents[2] / 'nora-drama-episodes/scripts/selftest.py'
_spec = importlib.util.spec_from_file_location('nora_episodes_selftest', _PATH)
_module = sys.modules.get('nora_episodes_selftest')
if _module is None:
    sys.path.insert(0, str(_PATH.parent))
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
globals().update({name: value for name, value in vars(_module).items() if not name.startswith("_")})
if __name__ == "__main__":
    raise SystemExit(_module.main())
else:
    sys.modules[__name__] = _module
