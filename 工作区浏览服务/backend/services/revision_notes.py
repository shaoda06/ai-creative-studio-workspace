"""Compatibility import for the business-owned review/round adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/nora-drama-production/scripts'))
import drama_revision_notes as _implementation
sys.modules[__name__] = _implementation
