"""Legacy backend import alias for the AiMixer segment-plan adapter."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-h3-aimixer/scripts'))
import aimixer_segments

sys.modules[__name__] = aimixer_segments
