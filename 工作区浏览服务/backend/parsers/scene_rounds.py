"""Compatibility import for the business-owned review/round adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/short-drama-storyboard/scripts'))
import drama_browser_rounds as _implementation
sys.modules[__name__] = _implementation
