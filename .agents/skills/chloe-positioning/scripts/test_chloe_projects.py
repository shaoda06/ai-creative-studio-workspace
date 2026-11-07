"""Named-project initialization and isolation using temporary local fixtures."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from chloe_init import initialize_workspace, initialize_project, initialize_video, initialize_asset
from chloe_documents import check_workspace


class ChloeProjectsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.workspace = initialize_workspace(self.base / 'Chloe Workspace')

    def test_workspace_does_not_create_project_or_account(self):
        self.assertEqual([p.name for p in self.workspace.iterdir()], ['README.md'])
        initialize_workspace(self.workspace)
        self.assertEqual([p.name for p in self.workspace.iterdir()], ['README.md'])

    def test_name_is_required_before_any_project_write(self):
        for name in ['', ' ', '待命名', '未命名', '待确定', '没想好', '项目名称', '../other', 'a/b', 'projects', '综合资料']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                initialize_project(self.workspace, name)
        command = [sys.executable, str(Path(__file__).with_name('chloe_init.py')),
                   '--workspace', str(self.workspace), 'project']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--name', result.stderr)
        self.assertEqual([p.name for p in self.workspace.iterdir()], ['README.md'])

    def test_projects_reuse_local_ids_and_preserve_existing_documents(self):
        for name in ['展示甲', 'ACCOUNT_02']:
            root = initialize_project(self.workspace, name)
            video = initialize_video(root, 'V001', '展示')
            initialize_asset(root, '模特', 'M001', '样例')
            self.assertEqual(check_workspace(root)['errors'], [])
            self.assertEqual(video.relative_to(root).as_posix(), 'projects/V001-展示')
        one = self.workspace / '展示甲'
        body = (one / '综合资料/账号定位.md').read_text().replace('待确定', '明确方向')
        (one / '综合资料/账号定位.md').write_text(body)
        initialize_project(self.workspace, '展示甲')
        self.assertEqual((one / '综合资料/账号定位.md').read_text(), body)
        self.assertNotEqual((self.workspace / 'ACCOUNT_02/综合资料/账号定位.md').read_text(), body)
        with self.assertRaises(ValueError):
            initialize_video(self.workspace, 'V002', '没有选择项目')

    def test_symlink_cannot_create_project_outside_workspace(self):
        external = self.base / 'outside'; external.mkdir()
        (self.workspace / 'alias').symlink_to(external, target_is_directory=True)
        with self.assertRaises(ValueError):
            initialize_project(self.workspace, 'alias')
        self.assertEqual(list(external.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
