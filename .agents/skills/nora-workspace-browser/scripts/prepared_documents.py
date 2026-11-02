"""Exact staged file writes shared by media preparation; no business defaults."""
import json
from copy import deepcopy
from difflib import SequenceMatcher
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'nora-comfyui/scripts'))
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


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _delta(before, after):
    old, new = before.splitlines(keepends=True), after.splitlines(keepends=True)
    return [[start, end, ''.join(new[left:right])]
            for kind, start, end, left, right in SequenceMatcher(None, old, new).get_opcodes()
            if kind != 'equal']


def _restore(before, changes):
    lines = before.splitlines(keepends=True)
    for start, end, replacement in reversed(changes):
        lines[start:end] = [replacement]
    return ''.join(lines)


def write_journal(path, value):
    """Share staged API bodies and store exact edits instead of repeated full text."""
    if value.get('journal_encoding') != 'shared-writes-v1':
        return write_json(path, value)
    stored = deepcopy(value)
    workflows = {}
    for index, task in enumerate(stored['tasks']):
        body = json.dumps(task['workflow'], ensure_ascii=False, indent=2)
        if body in workflows:
            task['workflow_from_task'] = workflows[body]
            del task['workflow']
        else:
            workflows[body] = index
    for update in stored['writes']:
        if update['new'] in workflows:
            update['new_from_workflow'] = workflows[update.pop('new')]
        for field in ('new', 'original'):
            if isinstance(update['old'], str) and isinstance(update.get(field), str):
                changes = _delta(update['old'], update[field])
                if len(json.dumps(changes, ensure_ascii=False)) < len(json.dumps(update[field], ensure_ascii=False)):
                    update[field + '_delta'] = changes
                    del update[field]
    write_json(path, stored)


def read_journal(path):
    """Restore the same in-memory journal for new encoding or legacy full snapshots."""
    value = json.loads(path.read_text('utf-8-sig'))
    if value.get('journal_encoding') == 'shared-writes-v1':
        for task in value['tasks']:
            if 'workflow_from_task' in task:
                task['workflow'] = deepcopy(value['tasks'][task.pop('workflow_from_task')]['workflow'])
        for update in value['writes']:
            if 'new_from_workflow' in update:
                update['new'] = json.dumps(value['tasks'][update.pop('new_from_workflow')]['workflow'],
                                           ensure_ascii=False, indent=2)
            for field in ('new', 'original'):
                if field + '_delta' in update:
                    update[field] = _restore(update['old'], update.pop(field + '_delta'))
    return value


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='只读展开精简或旧式装配记录，不生成新文件或执行任务')
    parser.add_argument('command', choices=['read'])
    parser.add_argument('file', type=Path, help='装配结果JSON路径，相对路径按当前目录解析')
    arguments = parser.parse_args()
    print(json.dumps(read_journal(arguments.file), ensure_ascii=False, indent=2))
