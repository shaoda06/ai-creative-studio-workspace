"""Read explicit shot fields using the shared Markdown template as their schema."""
from pathlib import Path
import re

TEMPLATE = Path(__file__).resolve().parents[1] / 'templates/逐镜正文模板.md'
FIELDS = tuple(re.findall(r'^\*\*([^*\n]+)\*\*：', TEMPLATE.read_text('utf-8'), re.M))
HEADING = re.compile(r'^#{3,4}\s+([^\n]*SH\d{3,}[^\n]*)\n', re.M)
FIELD = re.compile(r'^\*\*([^*\n]+)\*\*：([^\n]*(?:\n(?!\*\*|#{1,4} |```|---\s*$)[^\n]*)*)', re.M)


def read_shots(text, extra_fields=()):
    headings = list(HEADING.finditer(text))
    shots = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = re.split(r'^#{1,3}\s+', text[heading.end():end], maxsplit=1, flags=re.M)[0]
        pairs = [(match[1], match[2].strip()) for match in FIELD.finditer(body)]
        names = [name for name, _ in pairs]
        if names != list(FIELDS + tuple(extra_fields)):
            raise ValueError(heading[1] + '：逐镜字段缺失、重复、顺序错误或含未声明字段')
        if any(not value for _, value in pairs):
            raise ValueError(heading[1] + '：逐镜字段为空')
        shots.append({'heading': heading[1], 'fields': dict(pairs)})
    return shots
