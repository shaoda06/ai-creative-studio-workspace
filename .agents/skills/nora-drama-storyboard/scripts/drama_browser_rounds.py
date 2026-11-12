"""Project episode compositions and retain explicit legacy scene history."""
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import quote

import scene_rounds as rounds

from episode_rounds import episode_manifest_key, scene_entries, validate_episode_manifest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-h3-songssx/scripts'))
from songssx_browser import songssx_scene


def load_episode_rounds(episode, read):
    raw = read(episode_manifest_key(episode))
    if raw is None:
        return []
    return [{'number': item['number'], 'scenes': list(item['scenes'])}
            for item in validate_episode_manifest(json.loads(raw), episode)['rounds']]

def load_scene_rounds(project, episode, scene, read):
    from backend.parsers.project import field, markdown, document_header
    from backend.parsers.generation import segment_body
    from backend.services.scene_postprocess import review_output
    result = []
    for entry in scene_entries(project, episode, scene, read):
        item = {**entry, 'issues': []}
        record = episode_manifest_key(episode) if entry.get('episodeRound') else rounds.manifest_key(episode, scene)
        item['record'] = {'kind': 'json', 'name': Path(record).name, 'key': record, 'url': quote(record, safe='/-._~')}
        documents = {}
        for kind in ('script', 'storyboard'):
            reference = entry[kind]
            file = reference['file']
            if Path(file).is_absolute() or not (project / file).resolve().is_relative_to(project):
                raise ValueError('场次轮次文档越出项目：' + file)
            text = read(file)
            if text is None or field(text, '文档版本').rstrip('。') != reference['version']:
                item['issues'].append(('剧本' if kind == 'script' else '分镜') + '文件缺失或版本不匹配')
                item[kind] = None
                continue
            documents[kind] = text
            doc = {'title': Path(file).stem, 'html': markdown(text, file), 'url': quote(file, safe='/-._~'), **document_header(text, file)}
            item[kind] = {'kind': 'document', 'name': Path(file).stem, 'key': file, 'url': doc['url'], 'doc': doc, 'version': reference['version']}
        item['segments'] = [{**segment,
            'scriptHtml': markdown(segment_body(documents.get('storyboard', ''), segment['id']), entry['storyboard']['file']),
            'scriptUrl': quote(entry['storyboard']['file'], safe='/-._~')} for segment in entry['segments']]
        if entry.get('review_outputs'):
            item['reviewOutputs'] = [review_output(project, output, lambda key: quote(key, safe='/-._~'))
                                     for output in entry['review_outputs']]
        if item.get('songssx_execution'):
            from drama_browser_generation import storyboard_context
            item['songssx'] = songssx_scene(project, item, lambda segment: (
                storyboard_context(documents['storyboard'], segment, entry['storyboard']['file']) if 'storyboard' in documents
                else {'scriptHtml': '', 'shots': [], 'dialogues': [], 'issues': []}))
        result.append(item)
    return result
