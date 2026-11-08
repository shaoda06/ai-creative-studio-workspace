"""Global read views over the registered spaces; task ownership stays unchanged."""
from datetime import datetime

from backend.services.task_history import task_history
from backend.services.workspaces import scope_links


def snapshot(spaces):
    result = {'tasks': [], 'local_tasks': [], 'remote_nodes': [],
              'local_counts': {}, 'history_updated_at': {}}
    nodes = {}
    for space in spaces.items.values():
        data = space.tasks.public(include_history=False)
        source = {'workspace_id': space.id, 'workspace_name': space.name, 'api_prefix': space.api}
        for field in ('tasks', 'local_tasks'):
            result[field].extend({**scope_links(item, space.api), **source} for item in data[field])
        for node in data['remote_nodes']:
            previous = nodes.get(node['url'])
            if previous is None or (node['updated_at'] or '') > (previous['updated_at'] or ''):
                nodes[node['url']] = node
        for url, counts in data['local_counts'].items():
            total = result['local_counts'].setdefault(url, {'queued': 0, 'paused': 0, 'history': 0})
            for category, count in counts.items():
                total[category] += count
        for url, updated in data['history_updated_at'].items():
            previous = result['history_updated_at'].get(url)
            result['history_updated_at'][url] = max(previous or '', updated or '') or None
    result['remote_nodes'] = list(nodes.values())
    return result


def history(spaces, search='', result='all', offset=0, limit=20):
    items, total = [], 0
    for space in spaces.items.values():
        page = task_history(space.tasks, search=search, result=result, limit=offset + limit)
        total += page['total']
        items.extend({**item, 'workspace_id': space.id, 'workspace_name': space.name,
                      'api_prefix': space.api} for item in page['items'])
    items.sort(key=lambda item: (
        datetime.fromisoformat(item.get('ended_at') or item['created_at']).timestamp(),
        item['created_at'], item['id'], item['workspace_id']), reverse=True)
    end = min(offset + limit, total)
    return {'items': items[offset:end], 'total': total,
            'next_offset': end if end < total else None}
