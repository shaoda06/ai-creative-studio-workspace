"""Compatibility import for the business-owned browser projection."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/nora-drama-production/scripts'))
import drama_video_products as _implementation
sys.modules[__name__] = _implementation
