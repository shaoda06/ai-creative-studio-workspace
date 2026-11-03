"""Retention tests use temporary caches, logs and isolated media only."""
import json
import logging
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend.services.projects import CACHE_SCHEMA, ProjectStore
SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
SHARED = Path(__file__).resolve().parents[2] / '.agents/skills/studio-workspace-browser/scripts'
sys.path[:0] = [str(SCRIPTS), str(SHARED)]
from media_files import store_media
from prepare_test_media import prepare
from service_logging import PollFilter


class CacheRetentionTests(unittest.TestCase):
    def test_startup_retires_old_root_schema_and_removed_projects_but_keeps_current_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            projects = root / 'projects'
            (projects / '现项目').mkdir(parents=True)
            cache = root / 'cache'
            store = ProjectStore(projects, cache_directory=cache, version='new-release')
            store.save_cache('现项目', {}, {'keep': '版本递增也保留'}, 'current')
            current = cache / '现项目/current.json'
            saved = current.read_bytes()
            for name, workspace, schema in [('旧路径', '/old/projects', CACHE_SCHEMA),
                                             ('旧结构', str(projects), CACHE_SCHEMA - 1),
                                             ('已删项目', str(projects), CACHE_SCHEMA)]:
                path = cache / name / 'part.json'
                path.parent.mkdir()
                path.write_text(json.dumps({'workspace': workspace, 'schema': schema, 'data': {}}))
            # Missing schema was used by older cache writers and is incompatible too.
            (cache / '现项目/legacy.json').write_text(json.dumps({'workspace': str(projects), 'data': {}}))
            (cache / 'unknown.json').write_text('{}')
            result = store.prune_cache()
            self.assertEqual(result['files'], 4)
            self.assertEqual(current.read_bytes(), saved)
            self.assertEqual(store.load_cache('现项目', {}, 'current'), {'keep': '版本递增也保留'})
            self.assertTrue((cache / 'unknown.json').exists())
            self.assertFalse((cache / '旧路径').exists())
            self.assertEqual(store.prune_cache()['files'], 0)


class ServiceLogTests(unittest.TestCase):
    def test_poll_filter_retains_errors_writes_and_non_polling_reads(self):
        quiet = PollFilter()
        def record(method, path, status):
            return logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s %s %s %s %s',
                                     ('client', method, path, '1.1', status), None)
        for path in ('/api/service', '/api/projects', '/api/comfy/tasks?include_history=false',
                     '/api/workspaces/commercial/comfy/tasks', '/api/projects/test/status', '/api/task-monitor'):
            self.assertFalse(quiet.filter(record('GET', path, 200)))
            self.assertTrue(quiet.filter(record('GET', path, 500)))
            self.assertTrue(quiet.filter(record('POST', path, 200)))
        self.assertTrue(quiet.filter(record('GET', '/api/projects/test/file?path=x', 200)))
        self.assertTrue(quiet.filter(record('GET', '/api/service', 403)))

    def test_shared_rotating_handler_captures_tracebacks_and_bounds_backups(self):
        with tempfile.TemporaryDirectory() as folder:
            script = '''
import logging, pathlib, sys
from service_logging import configure
handler = configure(pathlib.Path(sys.argv[1]))
handler.maxBytes = 2048
for index in range(100):
    logging.getLogger('uvicorn.error').info('worker %s ' + 'x' * 150, index)
try:
    raise ValueError('retained-error')
except ValueError:
    logging.getLogger('backend').exception('failure')
logging.getLogger('uvicorn.access').info('%s %s %s %s %s', 'client', 'GET', '/api/service', '1.1', 200)
logging.shutdown()
'''
            subprocess.run([sys.executable, '-B', '-c', script, folder], cwd=SCRIPTS, check=True)
            logs = list(Path(folder).glob('server.log*'))
            self.assertEqual(len(logs), 3)
            self.assertLessEqual(sum(path.stat().st_size for path in logs), 3 * 2048)
            content = (Path(folder) / 'server.log').read_text()
            self.assertIn('ValueError: retained-error', content)
            self.assertNotIn('/api/service', content)

    def test_upgrade_trims_oversized_legacy_log_and_keeps_recent_content(self):
        with tempfile.TemporaryDirectory() as folder:
            old = Path(folder) / 'server.log'
            old.write_bytes(b'old-poll\n' * (12 * 1024 * 1024 // 9) + b'recent-before-upgrade\n')
            subprocess.run([sys.executable, '-B', '-c',
                            'from pathlib import Path; from service_logging import configure; '
                            'import sys,logging; configure(Path(sys.argv[1])); logging.shutdown()', folder],
                           cwd=SCRIPTS, check=True)
            self.assertLess(old.stat().st_size, 3 * 1024 * 1024)
            self.assertIn('recent-before-upgrade', old.read_text())
            self.assertFalse((Path(folder) / 'server.log.1').exists())


class TestMediaPreparationTests(unittest.TestCase):
    def test_reruns_reuse_media_paths_without_linking_external_project(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            external = root / '真实项目'
            external.mkdir()
            source = external / '原.mov'
            source.write_bytes(b'movie-source')
            mode = source.stat().st_mode
            sample = root / '隔离样稿'
            plan = {'files': [{'source': str(source), 'output': 'media/final.mov'},
                              {'source': str(source), 'output': 'files/原路径.mov'}]}
            one = prepare(sample, plan)
            kept = sample / 'media/final.mov'
            inode = kept.stat().st_ino
            two = prepare(sample, plan)
            self.assertTrue(kept.samefile(sample / 'files/原路径.mov'))
            self.assertFalse(kept.samefile(source))
            self.assertEqual(kept.stat().st_ino, inode)
            self.assertEqual(kept.stat().st_mode & 0o222, 0)
            self.assertEqual(source.stat().st_mode, mode)
            self.assertTrue(one['temporary_removed'] and two['temporary_removed'])

    def test_transcode_intermediates_removed_after_success_and_command_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            marker = root / 'temp-location.txt'
            command = [sys.executable, '-B', '-c',
                       'import pathlib,sys; p=pathlib.Path(sys.argv[1]); '
                       'pathlib.Path(sys.argv[2]).write_text(str(p)); '
                       '(p/"intermediate.mp4").write_bytes(b"frames"); '
                       '(p/"final.mov").write_bytes(b"finished")', '{tmp}', str(marker)]
            plan = {'commands': [command], 'files': [{'source': '{tmp}/final.mov', 'output': 'media/final.mov'}]}
            self.assertTrue(prepare(root / 'sample', plan)['temporary_removed'])
            self.assertFalse(Path(marker.read_text()).exists())
            self.assertEqual((root / 'sample/media/final.mov').read_bytes(), b'finished')
            plan['commands'].append([sys.executable, '-B', '-c', 'raise SystemExit(7)'])
            with self.assertRaises(subprocess.CalledProcessError):
                prepare(root / 'sample', plan)
            self.assertFalse(Path(marker.read_text()).exists())

    def test_failed_download_cleans_partial_file_and_conflicting_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            paths = []
            def failed_read(size):
                paths.extend(root.glob('studio-test-media-*'))
                raise ConnectionError('interrupted')
            plan = {'files': [{'source': 'https://example.invalid/video.mov', 'output': 'media/final.mov'}]}
            with patch('prepare_test_media.tempfile.tempdir', str(root)), \
                    patch('prepare_test_media.urlopen') as download, self.assertRaises(ConnectionError):
                # Let the second read fail after bytes have actually been written.
                response = download.return_value.__enter__.return_value
                chunks = iter([b'partial-download'])
                response.read.side_effect = lambda size: next(chunks, None) or failed_read(size)
                prepare(root / 'sample', plan)
            self.assertTrue(paths)
            self.assertFalse(any(path.exists() for path in paths))
            output = root / 'sample/media/final.mov'
            store_media(root / 'sample', output, b'old')
            changed = root / 'new.mov'
            changed.write_bytes(b'new')
            with self.assertRaisesRegex(ValueError, '已有不同内容'):
                prepare(root / 'sample', {'files': [{'source': str(changed), 'output': 'media/final.mov'}]})
            self.assertEqual(output.read_bytes(), b'old')
