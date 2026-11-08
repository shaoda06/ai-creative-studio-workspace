"""Deterministic Markdown field and file-link formatting, supplied by the caller."""
import os
import re

def fields(text, values):
    for name, content in values.items():
        text = re.sub(r'^- ' + re.escape(name) + r'：[^\n]*', lambda _: '- ' + name + '：' + content, text, flags=re.M)
    return text


def link(draft, target, title=None):
    return '[' + (title or target.name) + '](' + os.path.relpath(target, draft.parent).replace(os.sep, '/').replace(' ', '%20') + ')'
