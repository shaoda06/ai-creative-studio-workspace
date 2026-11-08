import json
from pathlib import Path
import tempfile
import unittest
from backend.services.project_files import ProjectFiles
from backend.services.workspaces import Workspaces


class ChloeWorkspaceTests(unittest.TestCase):
    def test_commerce_view_is_registered_without_project_or_production_adapter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            primary, account, runtime = root/'primary', root/'account', root/'runtime'
            for path in (primary/'projects', account/'projects', runtime):
                path.mkdir(parents=True)
            (runtime/'workspaces.json').write_text(json.dumps([
                {'id':'account-demo', 'name':'带货账号', 'path':str(account), 'view':'chloe-commerce'}]))
            spaces = Workspaces(primary, runtime, ProjectFiles(primary/'projects'), 'test')
            space = spaces.get('account-demo')
            self.assertEqual(space.public(), {'id':'account-demo', 'name':'带货账号', 'view':'chloe-commerce', 'projects':[]})
            self.assertIsNone(space.production_adapter)
            self.assertEqual(space.runtime, runtime/'workspaces/account-demo')
