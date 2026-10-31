"""Compatibility import for the business-owned browser projection."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/nora-profile-images/scripts'))
import profile_browser_projection as _implementation
sys.modules[__name__] = _implementation
