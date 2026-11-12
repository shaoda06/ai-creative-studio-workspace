"""Derive the common workbench entries from the object's formal records."""


def recorded_workflows(scene_rounds, *, aimixer_recorded):
    workflows = ['aimixer'] if aimixer_recorded else []
    if any(round_.get('songssx', {}).get('recorded') for rounds in scene_rounds.values() for round_ in rounds):
        workflows.append('songssx')
    return workflows
