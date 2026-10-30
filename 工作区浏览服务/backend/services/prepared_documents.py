"""Exact staged file writes shared by media preparation; no business defaults."""
import json
from pathlib import Path
import tempfile
from project_paths import project_file

class Documents:
    def __init__(self, root, previous_writes=()):
        self.root, self.edits, self.image_sizes = root, {}, {}
        self.previous = {project_file(root, item['path']): item for item in previous_writes}
        for path, item in self.previous.items():
            current = path.read_text('utf-8-sig') if path.exists() else None
            if current not in (item['old'], item['new']):
                raise ValueError('准备资料已变化，不覆盖：' + item['path'])

    def read(self, name):
        path = project_file(self.root, name)
        if path not in self.edits:
            text = path.read_text('utf-8-sig') if path.exists() else None
            # Rebuild from the original inputs, while publishing against the current files.
            previous = self.previous.get(path)
            self.edits[path] = [text, previous.get('original', previous['old']) if previous else text]
        return self.edits[path][1]

    def put(self, name, text):
        self.read(name)
        self.edits[project_file(self.root, name)][1] = text

    def new_json(self, name, value):
        old = self.read(name)
        if old is not None:
            if json.loads(old) != value:
                raise ValueError('执行文件已被占用：' + str(name))
            return
        self.put(name, json.dumps(value, ensure_ascii=False, indent=2))

    def writes(self):
        return [dict(path=p.relative_to(self.root).as_posix(), old=old, new=new,
                     **({'original': self.previous[p].get('original', self.previous[p]['old'])} if p in self.previous else {}))
                for p, (old, new) in self.edits.items() if old != new or p in self.previous]


def publish(root, updates):
    """Replay exact planned writes, without overwriting concurrent edits or historical outputs."""
    for update in updates:
        path = project_file(root, update['path'])
        current = path.read_text('utf-8-sig') if path.exists() else None
        if current == update['new']:
            continue
        if current != update['old']:
            raise ValueError('准备资料已变化，不覆盖：' + update['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(update['new'])
            actual = path.read_text('utf-8-sig') if path.exists() else None
            if actual != current:
                raise ValueError('准备资料并发变化，不覆盖：' + update['path'])
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
