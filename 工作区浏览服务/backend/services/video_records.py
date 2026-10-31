"""Compatibility facade for video business records and common technical helpers."""
from pathlib import Path
import sys
_SKILLS = Path(__file__).resolve().parents[3] / ".agents/skills"
for _name in ("nora-drama-production", "nora-h3", "nora-video-processing"):
    sys.path.insert(0, str(_SKILLS / _name / "scripts"))
from drama_video_records import prepare_records, sync_timing, STAGES
from video_metadata import probe
