"""Explicit business adapters for the common production reviewer."""
from pathlib import Path
import sys
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/iris-commercial-production/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-workspace-browser/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-h3-aimixer/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/studio-h3-songssx/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / '.agents/skills/chloe-production/scripts'))
import chloe_browser_production
import iris_browser_production
import iris_workbench

ADAPTERS = {'iris-commercial-production': (iris_browser_production, iris_workbench),
            'chloe-production': (chloe_browser_production, chloe_browser_production)}


def registered(space):
    if space.production_adapter not in ADAPTERS:
        raise FileNotFoundError('该资料区未登记视频制作接入')
    return ADAPTERS[space.production_adapter]


def adapter(space):
    return registered(space)[0]


def workbench(space):
    return registered(space)[1]


def summary(detail, path, view, revision):
    def context_link(item, **identity):
        if item.get('context') is None:
            return item
        params = dict(identity, v=revision)
        if view is not None:
            params['view'] = view
        return {**{key: value for key, value in item.items() if key != 'context'},
                'contextUrl': quote(path, safe='/') + '/context?' + urlencode(params)}

    def round_summary(scene, round_):
        songssx = round_.get('songssx')
        if not songssx:
            return round_
        segments = [context_link(item, scene=scene, segment=item['id'], round_number=round_['number'])
                    for item in songssx['segments']]
        return {**round_, 'songssx': {**songssx, 'segments': segments}}

    return {**detail,
            'segments': {scene: [{**item, 'videos': [context_link(video, scene=scene, segment=item['id'],
                           key=video['key'], stage=video['stage'], run=video['run']) for video in item['videos']]}
                           for item in items] for scene, items in detail.get('segments', {}).items()},
            'sceneRounds': {scene: [round_summary(scene, round_) for round_ in rounds]
                            for scene, rounds in detail.get('sceneRounds', {}).items()}}


def context(detail, scene, segment, key, stage, run, round_number):
    if round_number is not None:
        round_ = next((item for item in detail.get('sceneRounds', {}).get(scene, []) if item['number'] == round_number), {})
        candidates = (item for item in round_.get('songssx', {}).get('segments', []) if item['id'] == segment)
    else:
        candidates = (video for item in detail.get('segments', {}).get(scene, []) if item['id'] == segment
                      for video in item['videos'] if (video['key'], video['stage'], video['run']) == (key, stage, run))
    value = next(candidates, {}).get('context')
    if value is None:
        raise FileNotFoundError('原候选资料不存在')
    return value
