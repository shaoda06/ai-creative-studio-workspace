"""Compatibility module; current implementation is maintained by its skill."""
import importlib.util
from pathlib import Path
import sys

_PATH = Path(__file__).resolve().parents[3] / '.agents/skills/studio-jianying/scripts/jianying_draft.py'
_spec = importlib.util.spec_from_file_location('nora_jianying_draft', _PATH)
_module = sys.modules.get('nora_jianying_draft')
if _module is None:
    sys.path.insert(0, str(_PATH.parent))
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
sys.modules[__name__] = _module
globals().update({name: value for name, value in vars(_module).items() if not name.startswith("_")})
