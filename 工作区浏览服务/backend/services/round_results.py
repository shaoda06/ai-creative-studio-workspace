"""Compatibility module for production round reporting."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/nora-drama-production/scripts'))
import drama_round_results as _implementation
sys.modules[__name__] = _implementation
