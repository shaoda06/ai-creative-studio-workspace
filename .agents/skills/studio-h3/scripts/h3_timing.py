"""Compatibility for AiMixer workers started before the skills were split."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-h3-aimixer/scripts'))
from aimixer_timing import sync_timing
