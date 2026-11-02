"""Dispatch model binding persistence and the registered business association."""
from pathlib import Path
import sys
_SKILLS = Path(__file__).resolve().parents[3] / '.agents/skills'
for _name in ('studio-h3', 'studio-comfyui', 'nora-drama-production'):
    sys.path.insert(0, str(_SKILLS / _name / 'scripts'))
import workflow_baselines as pairs
from h3_uploads import save_uploaded_workflow as save_model_inputs
from drama_uploaded_sources import update_mapping


def save_uploaded_workflow(project, record, original, workflow, uploaded_materials, binding_results, *, path_scope=None, business_mapping=True):
    save_model_inputs(project, record, original, workflow, uploaded_materials, binding_results, path_scope=path_scope)
    if business_mapping and uploaded_materials and any(node['class_type'] == 'MiniMaxH3Director' for node in workflow.values()):
        update_mapping(project, record, uploaded_materials, path_scope=path_scope)
