"""Register a drama project without changing existing index order."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "nora-workspace-browser/scripts"))
from workspace_project_index import INDEX_NAME, read_index


def register_project(project):
    project = Path(project)
    text, names = read_index(project.parent)
    if project.name in names:
        return False
    table = re.search(r"^[ \t]*\|[ \t]*编号[ \t]*\|[ \t]*项目名称[ \t]*\|[ \t]*$", text, re.MULTILINE)
    line = f"| {len(names) + 1:02d} | {project.name} |" if table else f"{len(names) + 1}. {project.name}"
    separator = "\n" if names or table else "\n\n"
    (project.parent / INDEX_NAME).write_text(
        text.rstrip() + separator + line + "\n", encoding="utf-8")
    return True
