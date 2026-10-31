"""Read proven drama output identities without inferring approval from filenames."""
import json
from pathlib import Path

def prepared_identities(store, key):
    """Read an existing checked association once; do not infer it from a save name."""
    row = store.rows[key]
    if '_review_identities' not in row:
        data = row['input']
        record = Path(data.record_dir)
        identities = set()
        try:
            report = json.loads((record / '执行检查报告.json').read_text('utf-8-sig'))
        except FileNotFoundError:
            # Legacy registrations can lack preparation reports. Fill only this missing link.
            if not row['state'].get('preparation_required'):
                try:
                    mapping = json.loads((record / '输入映射.json').read_text('utf-8-sig'))
                    identities = {item['identity'] for item in mapping.get('generation_contexts', [])}
                except (OSError, ValueError, KeyError, TypeError):
                    pass
        except (OSError, ValueError):
            pass
        else:
            try:
                if report.get('ok'):
                    mapping = report.get('prepared_input', {}).get('mapping', {})
                    stage = {'video-first-pass': '一采', 'video-second-pass': '二采', 'video-postprocess': '后处理'}[data.task_type]
                    identities = {f"{mapping['segments'][index]['segment']}-{mapping['segments'][index]['round']}-{stage}"
                                  for index in mapping.get('selected_indices', [])}
            except (KeyError, TypeError, AttributeError, IndexError):
                pass
        if identities:
            row['_review_identities'] = identities
        return identities
    return row['_review_identities']
