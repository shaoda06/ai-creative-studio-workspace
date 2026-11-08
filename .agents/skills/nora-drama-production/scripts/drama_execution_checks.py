"""Short-drama source, composition and content associations for preparation."""
import json
from pathlib import Path
import re
from project_paths import project_file, recorded_paths

def context_checks(store, data, *, mapping=None, bindings=None, timelines=None, segment_context=None, segment_plan_checked=False, path_scope=None):
    if bindings is None:  # Legacy supplement or standalone context-only check.
        documents, bindings = {}, []
        for item in data.uploads:
            value = data.workflow[item['node']]['inputs'][item['input']]
            if 'json-path' in item:
                key = (item['node'], item['input'])
                if key not in documents:
                    documents[key] = json.loads(value)
                value = documents[key]
                for part in item['json-path']:
                    value = value[part]
            bindings.append((item, value))
    planned = {value: {'input_path': value, 'file': item['file']} for item, value in bindings}
    context = store.generation_context.prepare_generation_context(data.project, Path(data.record_dir),
                data.workflow, data.task_type, planned, check_only=True, mapping=mapping, timelines=timelines,
                segment_context=segment_context, segment_plan_checked=segment_plan_checked, path_scope=path_scope)
    return (context or {}).get('files', [])


def storyboard_index_checks(data, mapping):
    from drama_browser_project import table_records, storyboard_index_identity, production_scene_ids
    episode = mapping['scene'].split('-')[0]
    base = '09-剧集制作/' + episode
    script_key = base + '/02-剧集剧本/' + episode + '-本集剧本.md'
    index_key = base + '/03-分镜脚本/' + episode + '-分镜索引.md'
    script = project_file(data.project, script_key).read_text('utf-8-sig')
    index = project_file(data.project, index_key).read_text('utf-8-sig')
    scenes = production_scene_ids(script, episode)
    if not scenes:
        raise ValueError(script_key + '：缺少内容正文或完整场次标题')
    rows = table_records(index, ('场次', '分段', '分段计划时长（秒）'))
    if not rows:
        raise ValueError(index_key + '：没有可读取的分段表')
    for row in rows:
        try:
            storyboard_index_identity(episode, scenes, row)
        except ValueError as error:
            raise ValueError(index_key + '：' + str(error)) from error
    return {'ok': True, 'rows': len(rows),
            'files': [str(project_file(data.project, key)) for key in (script_key, index_key)]}


def content_checks(data, mapping, report):
    from h3_prompt_checks import audit
    result = audit(data.project, data.workflow, mapping)
    report['content_checks'] = result
    if not result['ok']:
        issues = result['issues'] + [issue for group in result['groups'] for issue in group['issues']]
        raise ValueError('H3正文与内容核对未通过：' + '；'.join(
            dict.fromkeys(issue['code'] + ': ' + issue['detail'] for issue in issues)))
    return result['sources']


def check_existing_video_identity(data, mapping):
    if not mapping:
        return
    stage = {'video-first-pass': '一采', 'video-second-pass': '二采', 'video-postprocess': '后处理'}[data.task_type]
    stage_folder = {'一采': '01-一采', '二采': '02-二采', '后处理': '03-后处理'}[stage]
    for index in mapping['selected_indices']:
        entry = mapping['segments'][index]
        identity = entry['segment'] + '-' + entry['round'] + '-' + stage
        episode, scene = entry['segment'].split('-')[:2]
        root = Path(data.project) / '09-剧集制作' / episode
        folders = [root / '其他资料/候选视频', root / '06-阶段采用视频' / stage_folder / (scene + '-场次'),
                   root / '其他资料/阶段采用视频' / stage_folder / (scene + '-场次')]
        if any(file.is_file() and file.suffix in ('.mp4', '.webm', '.mov')
               for folder in folders for file in folder.glob(identity + '.*')):
            raise ValueError('候选编号已有视频文件，重新生成须使用新R；失败取回请沿原任务恢复：' + identity)



def read_mapping(data):
    path = Path(data.record_dir) / '输入映射.json'
    return json.loads(path.read_text('utf-8-sig')) if path.exists() else {}


def basis_fields(store, data, mapping):
    result = {}
    if mapping:
        result['mapping'] = recorded_paths(data.project, {name: mapping[name] for name in (
            'scene', 'task_type', 'screenplay_version', 'scene_storyboard_version', 'scene_modification_round', 'selected_indices', 'segments', 'content_review') if name in mapping}, relative=True)
        if data.task_type.startswith('video-'):
            revision = store.generation_context.scene_round_basis(data.project, mapping, data.task_type)
            if revision is not None:
                result['scene_composition'] = revision
    return result


def associated_sources(data, mapping, composition):
    files = set()
    if mapping:
        if mapping.get('storyboard_file'):
            files.add(project_file(data.project, mapping['storyboard_file'], recorded=True))
        for context in mapping.get('generation_contexts', []):
            files.update(project_file(data.project, name, recorded=True) for name in context.get('prompts', {}).values())
    if composition:
        files.update(project_file(data.project, composition[kind]['file'], recorded=True) for kind in ('script', 'storyboard'))
    return files


def check_episode_composition(data, prepared_input):
    if 'scene_composition' not in prepared_input:
        raise ValueError('新视频任务必须填写scene_modification_round，关联单集修改轮次后再准备；不得用执行时间线代替')
    from episode_rounds import episode_manifest_key, validate_episode_manifest
    mapping = prepared_input['mapping']
    episode = mapping['scene'].split('-')[0]
    manifest = Path(data.project) / episode_manifest_key(episode)
    if not manifest.exists() or not any(item['number'] == mapping['scene_modification_round']
            for item in validate_episode_manifest(json.loads(manifest.read_text('utf-8-sig')), episode)['rounds']):
        raise ValueError('新视频任务须先登记单集共用的修改轮次，旧场次轮次仅用于历史任务')
