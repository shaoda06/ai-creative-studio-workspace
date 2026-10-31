"""Update the explicit short-drama upload/source association after binding."""
import json
from pathlib import Path
from project_paths import PreparationPaths


def update_mapping(project, record, uploaded_materials, *, path_scope=None):
    path_scope = path_scope if path_scope is not None else PreparationPaths(project)
    mapping_file = record / '输入映射.json'
    original_text = path_scope.io_file(mapping_file).read_text(encoding='utf-8-sig')
    mapping = json.loads(original_text)
    uploaded_files = {path_scope.file(item['file']) for item in uploaded_materials.values()}
    sources = {item['input_path']: item for item in mapping['uploads']
               if path_scope.file(item['file']) not in uploaded_files}
    sources.update(uploaded_materials)
    mapping['uploads'] = list(sources.values())
    text = json.dumps(path_scope.convert(mapping, relative=True), ensure_ascii=False, indent=2) + '\n'
    if original_text != text:
        path_scope.io_file(mapping_file).write_text(text, encoding='utf-8')


def frozen_sources(project, record):
    mapping_file = record / '输入映射.json'
    files = set()
    if mapping_file.exists():
        files.add(mapping_file)
        mapping = json.loads(mapping_file.read_text('utf-8-sig'))
        for context in mapping.get('generation_contexts', []):
            files.update(Path(project) / name for name in context.get('prompts', {}).values())
            if context.get('storyboard'):
                files.add(Path(project) / context['storyboard']['file'])
            files.update(Path(project) / ref['file'] for refs in context.get('references', {}).values() for ref in refs)
    return files
