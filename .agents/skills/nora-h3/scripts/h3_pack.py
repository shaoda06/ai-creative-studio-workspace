"""Native H3 pack mechanics on explicitly supplied parsed model inputs."""
import copy
import json
from pathlib import Path
import re
import sys
import zipfile
_SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_SKILLS / 'nora-comfyui/scripts'))
import comfyui_client as client
MEDIA = ('imageFile', 'audioFile', 'videoFile', 'pairedAudioFile')
WIDGETS = ('steps', 'sampler', 'scheduler', 'cfg', 'shift_video', 'shift_audio', 'seed', 'task_type')

def lift_common(common, group):
    """公共区差异移入各组；保留绝对素材槽位，本组覆盖公共同槽。"""
    group = copy.deepcopy(group)
    if common['commonEnabled']:
        group['prompt'] = '\n\n'.join(p.strip() for p in (common['prompt'], group['prompt']) if p.strip())
        for field in ('refs', 'refAudios', 'refVideos'):
            local = {r['index']: r for r in group[field]}
            group[field] = sorted({**{r['index']: copy.deepcopy(r) for r in common[field]}, **local}.values(),
                                  key=lambda r: r['index'])
    return group


def verify_pack(prepared):
    """核对原生可移植路径和素材字节，而不是把路径改写误判为正文变化。"""
    with zipfile.ZipFile(prepared['pack']) as archive:
        if archive.testzip():
            raise ValueError('导演包 ZIP 校验失败')
        metadata = client.strict_json(archive.read('pack.json'))
        if metadata['format'] != 'minimax-h3-director-pack' or metadata['formatVersion'] != 1:
            raise ValueError('原生导演包格式不符')
        widgets = {k: prepared['workflow'][prepared['node']]['inputs'][k] for k in WIDGETS
                   if k in prepared['workflow'][prepared['node']]['inputs']}
        if metadata['widgets'] != widgets or metadata['output'] != prepared['timeline']['output']:
            raise ValueError('包内控件／输出配置与整场工程不一致')

        def compare(before, after, where):
            if isinstance(before, dict):
                for key in before:
                    if key in ('fileName', 'subfolder', 'type') and any(before.get(f) for f in MEDIA):
                        continue
                    if key in ('imageB64', 'previewB64', 'previewFrames', 'previewMime'):
                        continue
                    if key in MEDIA and before[key]:
                        media = prepared['media'].get(before[key])
                        if media is None or archive.read(after[key]) != media.read_bytes():
                            raise ValueError('包内素材无法对应冻结字节：' + where + '/' + key)
                    else:
                        compare(before[key], after[key], where + '/' + key)
            elif isinstance(before, list):
                if len(before) != len(after):
                    raise ValueError('包内组序／内容数量不一致：' + where)
                for i, (a, b) in enumerate(zip(before, after)):
                    compare(a, b, where + '/' + str(i))
            elif before != after:
                raise ValueError('包内正文／标签／配置不一致：' + where)

        portable = client.strict_json(archive.read('timeline.json'))
        compare(prepared['timeline'], portable, 'timeline')
        shared = client.strict_json(archive.read('shared_params/shared_params.json'))
        if {k: portable['global'][k] for k in shared} != shared:
            raise ValueError('包内公共区与时间线不一致')
        group_names = sorted((n for n in archive.namelist() if re.fullmatch(r'asset_groups/\d+/group.json', n)),
                             key=lambda n: int(n.split('/')[1]))
        if len(group_names) != len(portable['segments']):
            raise ValueError('导演包分组文件未完整覆盖整场')
        for group, filename in zip(portable['segments'], group_names):
            actual = client.strict_json(archive.read(filename))
            # Native group exports materialize these optional empty fields.
            expected = {'loras': [], 'refImageSize': None, **group}
            if any(k not in expected or expected[k] != value for k, value in actual.items()):
                raise ValueError('包内分组与时间线不一致：' + filename)
