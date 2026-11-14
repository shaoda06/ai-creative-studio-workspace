"""Opt-in registered business continuations after common technical result collection."""
from pathlib import Path
import sys

SKILLS=Path(__file__).resolve().parents[3]/'.agents/skills'
REGISTRY={'chloe-image':('chloe-assets','chloe_result_records'),
          'chloe-video':('chloe-production','chloe_results')}


def selected(data):
    plan=(data.video_plan if data.task_type.startswith('video-') else data.image_plan) or {}
    business=plan.get('business_result')
    if business is None:
        return None,None
    if plan.get('adapter')!='technical':
        raise ValueError('业务接续须基于显式technical结果')
    adapter=business['adapter']
    if adapter not in REGISTRY:
        raise ValueError('未登记的业务结果适配：'+adapter)
    if adapter=='chloe-image' and business.get('adopt') and data.task_type!='image-upscale':
        raise ValueError('图片自动采用仅接收超分任务')
    if adapter.endswith('-image') != (not data.task_type.startswith('video-')):
        raise ValueError('业务结果适配与任务类型不符')
    skill,module=REGISTRY[adapter]
    import importlib
    sys.path.insert(0,str(SKILLS/skill/'scripts'))
    return business,importlib.import_module(module)


def validate(data):
    plan,module=selected(data)
    if plan is not None:
        targets = data.segment_plan.targets if data.segment_plan else data.outputs
        if plan['adapter']=='chloe-video':
            checked = module.validate(Path(data.project),plan,len(targets),task=data)
            stages={'video-first-pass':'一采','video-second-pass':'二采','video-postprocess':'后处理',
                    'video-scene-generation':'场次生成'}
            if checked[4]!=stages.get(data.task_type):
                raise ValueError('任务类型与原分段阶段不一致')
        else:
            module.validate(Path(data.project),plan,len(targets))


def finish(data, report, report_path, state=None):
    plan,module=selected(data)
    if plan is None:
        return report
    if report.get('business_sync',{}).get('status')!='updated':
        from project_paths import project_file
        targets = data.segment_plan.targets if data.segment_plan else data.outputs
        by_path = {project_file(data.project,item['path']):item for item in report['items']}
        ordered = {**report, 'items':[by_path[project_file(data.project,t.path)] for t in targets]}
        if state is not None:
            ordered['started_at'] = state.get('started_at')
            ordered['ended_at'] = state.get('ended_at')
        report['business_sync']=module.finish(Path(data.project),plan,ordered,report_path)
        from backend.services.execution_checks import write_json
        write_json(report_path,report)
    return report
