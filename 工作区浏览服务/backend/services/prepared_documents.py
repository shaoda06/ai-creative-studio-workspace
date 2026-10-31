"""Compatibility import for common staged document IO."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/nora-workspace-browser/scripts'))
import prepared_documents as _implementation
sys.modules[__name__] = _implementation
