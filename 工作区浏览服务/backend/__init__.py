"""Workspace browser backend."""

from pathlib import Path
import sys

# Shared technical IO is also available when a service module is imported directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".agents/skills/studio-comfyui/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".agents/skills/studio-workspace-browser/scripts"))
