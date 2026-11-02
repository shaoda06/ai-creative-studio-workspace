"""Read-only service/tool discovery across workspace scopes, without task startup."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.agents/skills/nora-workspace-browser/scripts'))
import browser_http


class SharedToolDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name) / 'Iris 测试工作区'
        self.runtime = self.workspace / '工作区浏览服务/runtime'
        self.runtime.mkdir(parents=True)
        self.config = self.runtime / 'task-service.json'
        self.config.write_text(json.dumps({'url': 'http://provider.invalid:8782',
            'api_prefix': '/api/workspaces/commercial', 'token': 'private-token-not-for-output'}))
        self.metadata = {'workspace': str(self.workspace), 'tool': str(Path(temporary.name) / '共享提供端/工作区浏览服务'),
                         'ready': True, 'version': 'test-version'}
        self.calls = []

    def opener(self):
        case = self
        class Opener:
            def open(self, url, timeout):
                case.calls.append((url, timeout))
                return io.BytesIO(json.dumps(case.metadata).encode())
        return Opener()

    def test_existing_callers_keep_pair_and_scoped_get(self):
        with patch.object(browser_http.urllib.request, 'build_opener', return_value=self.opener()):
            base, get = browser_http.open_service(self.workspace, 8)
        self.assertEqual(base, 'http://provider.invalid:8782')
        self.assertEqual(self.calls, [('http://provider.invalid:8782/api/workspaces/commercial/service', 8)])

    def test_cli_locates_provider_and_local_skills_without_token_or_writes(self):
        before = self.config.read_bytes()
        output = io.StringIO()
        with patch.object(browser_http.urllib.request, 'build_opener', return_value=self.opener()), \
             patch.object(sys, 'argv', ['browser_http.py', '--workspace', str(self.workspace)]), \
             contextlib.redirect_stdout(output):
            browser_http.main()
        data = json.loads(output.getvalue())
        self.assertEqual(Path(data['workspace_skills']), self.workspace / '.agents/skills')
        self.assertEqual(Path(data['provider_skills']), Path(self.metadata['tool']).parent / '.agents/skills')
        self.assertNotEqual(data['workspace_skills'], data['provider_skills'])
        self.assertNotIn('private-token-not-for-output', output.getvalue())
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(list(self.runtime.iterdir()), [self.config])
        self.assertEqual(len(self.calls), 1)

    def test_primary_workspace_uses_unscoped_api(self):
        self.config.write_text(json.dumps({'url': 'http://provider.invalid:8782', 'token': 'private'}))
        with patch.object(browser_http.urllib.request, 'build_opener', return_value=self.opener()):
            browser_http.open_service(self.workspace, 3, with_metadata=True)
        self.assertEqual(self.calls, [('http://provider.invalid:8782/api/service', 3)])

    def test_wrong_workspace_and_not_ready_stop(self):
        for field, value in [('workspace', str(self.workspace.parent / '另一工作区')), ('ready', False)]:
            with self.subTest(field=field), patch.dict(self.metadata, {field: value}), \
                 patch.object(browser_http.urllib.request, 'build_opener', return_value=self.opener()):
                with self.assertRaisesRegex(ValueError, '未就绪或读取了其他工作区'):
                    browser_http.open_service(self.workspace, 3, with_metadata=True)

    def test_missing_configuration_does_not_create_another_service(self):
        self.config.unlink()
        with self.assertRaises(FileNotFoundError):
            browser_http.open_service(self.workspace, 3, with_metadata=True)
        self.assertEqual(list(self.runtime.iterdir()), [])

    def test_connection_failure_is_preserved_without_fallback(self):
        with patch.object(browser_http.urllib.request, 'build_opener') as factory:
            factory.return_value.open.side_effect = OSError('isolated connection failure')
            with self.assertRaisesRegex(OSError, 'isolated connection failure'):
                browser_http.open_service(self.workspace, 3, with_metadata=True)
        self.assertEqual(factory.return_value.open.call_count, 1)
