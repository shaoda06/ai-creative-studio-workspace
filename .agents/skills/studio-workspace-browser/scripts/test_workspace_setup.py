"""Exercise the three public initialization flows in a fresh, isolated Studio."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
COMMANDS = {
    'Nora': ['.agents/skills/nora-drama-positioning/scripts/workspace_init.py'],
    'Iris': ['.agents/skills/iris-commercial-brief/scripts/workspace_init.py'],
    'Chloe': ['.agents/skills/chloe-positioning/scripts/chloe_init.py'],
}


class WorkspaceSetupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'Studio'
        # Only public skills and root instructions; no existing workspaces or runtime.
        files = subprocess.check_output(['git', 'ls-files', '--cached', '--others',
                                         '--exclude-standard', '-z', '--', '.agents/skills',
                                         'AGENTS.md', 'README.md'], cwd=ROOT).decode().split('\0')
        for name in dict.fromkeys(files):
            if name and (ROOT / name).is_file():
                target = self.root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)

    def run_initializer(self, business, *, register=True, check=True):
        command = [sys.executable, '-B', *COMMANDS[business], '--workspace',
                   f'workspaces/{business} Workspace']
        if business == 'Chloe':
            command.append('workspace')
        if register:
            command.append('--register')
        return subprocess.run(command, cwd=self.root, capture_output=True, text=True, check=check,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def test_clean_download_registers_each_business_and_preserves_existing_data(self):
        for business in COMMANDS:
            self.run_initializer(business)
            area = self.root / f'workspaces/{business} Workspace'
            self.assertEqual([p.name for p in (area / 'projects').iterdir()], ['README.md'])
            for doc in (area / 'README.md', area / 'projects/README.md'):
                for target in re.findall(r'\]\(([^)]+)\)', doc.read_text()):
                    self.assertTrue((doc.parent / target.split('#')[0]).exists(), (doc, target))
            (area / 'README.md').write_text('本地专用约定，保留。')
            (area / 'comfyui-config.json').write_text('{"local": true}')
        iris = self.root / 'workspaces/Iris Workspace'
        (iris / '.git').mkdir()
        (iris / '.git/HEAD').write_text('ref: refs/heads/private\n')
        registry = self.root / '工作区浏览服务/runtime/workspaces.json'
        entries = json.loads(registry.read_text())
        self.assertEqual([e['id'] for e in entries], ['commercial', 'chloe'])
        entries[0].update(name='本地显示名称', task_history_archives=[])
        registry.write_text(json.dumps(entries, ensure_ascii=False))
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*')
                  if p.is_file() and ('workspaces' in p.parts or 'runtime' in p.parts)}
        for business in COMMANDS:
            self.run_initializer(business)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*')
                 if p.is_file() and ('workspaces' in p.parts or 'runtime' in p.parts)}
        self.assertEqual(before, after)
        self.assertFalse(list((self.root / '工作区浏览服务/runtime').rglob('*.sqlite')))
        direction = self.root / 'workspaces/Chloe Workspace/综合资料/账号定位.md'
        self.assertIn('| 发布平台 | 待确定 |', direction.read_text())

    def test_no_registration_without_flag_and_conflict_does_not_overwrite(self):
        self.run_initializer('Iris', register=False)
        registry = self.root / '工作区浏览服务/runtime/workspaces.json'
        self.assertFalse(registry.exists())
        self.run_initializer('Iris')
        entries = json.loads(registry.read_text())
        entries[0]['path'] = str(self.root / 'another/Iris Workspace')
        registry.write_text(json.dumps(entries))
        before = registry.read_bytes()
        result = self.run_initializer('Iris', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('已有空间登记', result.stderr)
        self.assertEqual(registry.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
