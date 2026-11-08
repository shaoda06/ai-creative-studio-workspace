"""Read bundled formal and backup workflows; never submit or modify them."""
from pathlib import Path
from urllib.parse import quote
from workflow_paths import workflow_locations


def catalogue(root: Path) -> list[dict]:
    items = []
    for category, directory, group in workflow_locations(root):
        for canvas in sorted(directory.glob('*.workflow.json')):
            name = canvas.name.removesuffix('.workflow.json')
            api = directory / (name + '.api.json')
            items.append({'name': name, 'group': group,
                          'canvasUrl': '/api/workflows/files/' + quote(category + '/' + canvas.name, safe='/'),
                          'apiUrl': '/api/workflows/files/' + quote(category + '/' + api.name, safe='/') if api.is_file() else None})
    return items
