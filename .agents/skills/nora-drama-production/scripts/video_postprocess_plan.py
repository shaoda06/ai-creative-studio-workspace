#!/usr/bin/env python3
"""Build one postprocessing submission list from completed second-pass approval reports; no queueing."""
import argparse
import copy
import json
from pathlib import Path

import sys
_SKILLS = Path(__file__).resolve().parents[2]
for _skill in ("studio-comfyui", "studio-h3", "studio-video-processing", "nora-video-prompts", "nora-drama-production", "nora-drama-handoff", "nora-drama-storyboard"):
    sys.path.insert(0, str(_SKILLS / _skill / "scripts"))

import video_approve
from episode_rounds import episode_manifest_key, validate_episode_manifest
from project_paths import project_file
from workflow_paths import VIDEO_POSTPROCESS_BASELINE, workflow_file
from video_workflow import assemble, plan_output, assemble_output
from video_metadata import probe

PROFILES = {'crop': '切镜保护插帧与裁切', 'upscale': '切镜保护插帧与超分'}


def build(project, request, output):
    root = Path(project).resolve(strict=True)
    output = project_file(root, output)
    episode = request['episode']
    manifest = validate_episode_manifest(video_approve.adopt.load(root / episode_manifest_key(episode)), episode)
    composition = next((r for r in manifest['rounds'] if r['number'] == request['round']), None)
    if composition is None:
        raise ValueError('指定后处理轮次不存在：' + str(request['round']))
    if not request['authorization'].strip():
        raise ValueError('后处理执行授权不能为空')
    choice = request.get('video_postprocess')
    if choice is not None:
        if set(choice) - {'resolution', 'fps', 'fit'} or not {'resolution', 'fps'} <= set(choice):
            raise ValueError('video_postprocess须提供resolution、fps，可选fit')
    else:
        profile, orientation = request['profile'], request['orientation']
        if profile not in PROFILES or orientation not in ('landscape', 'portrait'):
            raise ValueError('profile应为crop/upscale，orientation应为landscape/portrait')
    sources = {}
    for name in request['approval_reports']:
        report_path = project_file(root, name)
        report = video_approve.adopt.load(report_path)
        if report.get('stage') == '二采' and 'sources' in report:
            approved = report['sources']
        else:
            finalization = report.get('finalization')
            if not finalization:
                raise ValueError('来源二采报告缺少已采用的实际来源：' + name)
            batches = finalization['batches'] if 'batches' in finalization else [finalization]
            if any(batch['stage'] != '二采' for batch in batches):
                raise ValueError('来源报告不是二采：' + name)
            approved = [source for batch in batches for source in batch['sources']]
        if report['state'] != 'completed':
            raise ValueError('来源二采采用尚未完成：' + name)
        for source in approved:
            identity = source['identity']
            if identity in sources:
                raise ValueError('重复来源二采身份：' + identity)
            sources[identity] = (source, report_path.relative_to(root).as_posix())
    if choice is None:
        baseline = workflow_file(VIDEO_POSTPROCESS_BASELINE)
        width, height = (1920, 1080) if orientation == 'landscape' else (1080, 1920)
    tasks, canvases, reused = [], {}, []
    for scene, data in composition['scenes'].items():
        for segment in data['segments']:
            if segment['stage'] != '后处理':
                raise ValueError('本轮须明确全部后处理对象；先用scene_rounds登记范围')
            part = f'{episode}-{scene}-{segment["id"]}'
            identity = f'{part}-{segment["run"]}-后处理'
            chosen = video_approve.selected(root, part, '二采')
            if chosen not in sources:
                raise ValueError('缺少当前采用二采的完成报告：' + part)
            source, approval = sources[chosen]
            video = project_file(root, source['selected_path'], recorded=True)
            if not video.is_file():
                raise ValueError('来源二采文件缺失：' + chosen)
            directory = Path(f'09-剧集制作/{episode}/其他资料/执行附件/{identity}')
            canvas_path = directory / '内容画布.workflow.json'
            placeholder = 'planned/' + video.name
            if choice is not None:
                configuration = plan_output(probe(video), choice['resolution'], choice['fps'], choice.get('fit'))
                canvas = assemble_output(placeholder, identity, configuration)
                if canvas is None:
                    reused.append(dict(identity=identity, source=chosen, file=video.relative_to(root).as_posix(),
                                       approval_basis=approval, configuration=configuration))
                    continue
                width, height = configuration['output_size']
                description = '按已选输出规格处理；保留原音轨和播放时长。'
                delivery = f"{width}×{height}、{configuration['fps']:g}fps、H.264/yuv420p/CRF19。"
            else:
                canvas = assemble(profile, placeholder, identity, (width, height),
                                  (0, 4) if orientation == 'landscape' else (4, 0))
                description = '已采用二采逐段后处理，保留原音轨和播放时长。'
                delivery = f'{PROFILES[profile]}；{width}×{height}、30fps、H.264/yuv420p/CRF19。'
            canvases[project_file(root, canvas_path)] = canvas
            tasks.append({'task_type': 'video-postprocess', 'title': part + ' · 后处理',
                          'authorization': request['authorization'],
                          'description': description,
                          'delivery_basis': delivery,
                          'canvas': canvas_path.as_posix(), 'record_dir': directory.as_posix(),
                          'output_nodes': ['16'], 'output_root': request['output_root'],
                          'references': [{'file': video.relative_to(root).as_posix(), 'placeholder': placeholder,
                                          'purpose': '当前采用二采原片，批准及实际来源见approval_basis'}],
                          'mapping': {'scene': episode + '-' + scene,
                                      'screenplay_version': composition['script']['version'],
                                      'scene_storyboard_version': data['storyboard']['version'],
                                      'scene_modification_round': composition['number'], 'selected_indices': [0],
                                      'segments': [{'segment': part, 'round': segment['run'], 'source': chosen,
                                                    'duration_seconds': segment['duration'],
                                                    'local_execution_dir': directory.as_posix()}],
                                      'source_video': video.relative_to(root).as_posix(),
                                      'baseline': str(baseline) if choice is None else 'studio-video-processing', 'approval_basis': approval}})
            if choice is not None:
                tasks[-1]['video_postprocess'] = dict(choice, source=video.relative_to(root).as_posix())
                tasks[-1]['mapping']['postprocess_configuration'] = configuration
    plan = {'business_scope': {'episode': episode, 'episode_round': composition['number'],
                              'expected_video_count': len(tasks), 'scenes': list(composition['scenes']),
                              'delivery': '整轮全部成果齐备并按后处理自动采用规则收尾后统一交付，正常部分成功静默。'},
            'tasks': tasks, 'reused_sources': reused}
    # Refuse all collisions before creating anything; existing accepted plans remain immutable.
    for path in [output, *canvases]:
        if path.exists():
            raise ValueError('目标已存在，沿原清单接续，不覆盖：' + str(path))
    for path, value in [*canvases.items(), (output, plan)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'state': 'planned' if tasks else 'reuse', 'reused_sources': reused, 'task_count': len(tasks), 'plan': output.relative_to(root).as_posix(),
            'next_action': 'comfyui_dispatch --plan；reused_sources沿原文件交回业务记录，不入队' if tasks else '沿用reused_sources原文件并交回业务记录；无需上传或入队'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, help='项目根目录，绝对路径或相对当前工作目录')
    parser.add_argument('--request', required=True, help='项目内JSON：episode、round、video_postprocess（resolution/fps/fit）、authorization、approval_reports、output_root')
    parser.add_argument('--output', required=True, help='新任务清单的项目相对路径；已有文件拒绝覆盖')
    args = parser.parse_args()
    try:
        request = video_approve.adopt.load(project_file(args.project, args.request))
        result = build(args.project, request, args.output)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'state': 'needs_attention', 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
