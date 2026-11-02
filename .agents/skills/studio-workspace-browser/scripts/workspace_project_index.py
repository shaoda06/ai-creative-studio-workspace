"""Read the shared workspace project-list format without business writes."""
from pathlib import Path
import re


INDEX_NAME = "项目总索引.md"


def read_index(root):
    path = Path(root) / INDEX_NAME
    text = path.read_text(encoding="utf-8-sig") if path.exists() else "# 项目总索引\n\n| 编号 | 项目名称 |\n| --- | --- |\n"
    rows = re.findall(r"^[ \t]*\|[ \t]*[0-9]+[ \t]*\|[ \t]*([^|\r\n]+?)[ \t]*\|[ \t]*$", text, re.MULTILINE)
    names = rows or re.findall(r"^[ \t]*[0-9]+\.[ \t]+([^\r\n]+?)[ \t]*$", text, re.MULTILINE)
    return text, names
