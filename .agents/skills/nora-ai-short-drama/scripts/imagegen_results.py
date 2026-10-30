"""Compatibility command for the serial-drama image business stage."""
import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / 'nora-drama-images/scripts/imagegen_results.py'
_spec = importlib.util.spec_from_file_location('nora_drama_image_cli', _PATH)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
main = _module.main

if __name__ == '__main__':
    main()
