"""Compatibility import for the serial-drama image business adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/nora-drama-images/scripts'))
import drama_local_images as _implementation
sys.modules[__name__] = _implementation
