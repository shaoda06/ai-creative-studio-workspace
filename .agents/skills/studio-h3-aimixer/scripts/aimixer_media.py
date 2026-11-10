"""AiMixer mirrors global and segment media into its editor workspace."""


def mirror_path(node, field, path):
    if node['class_type'] != 'MiniMaxH3Director' or field != 'timeline_data' or path[0] not in ('global', 'segments'):
        return None
    if path[0] == 'global':
        return ['batchWorkspaces', 'r2v', 'globalCommon', *path[1:]]
    return ['batchWorkspaces', 'r2v', *path]


def uploaded_fields(path, response, *, director):
    fields = {path[-1]: response['input_path']}
    if director:
        remote = response['remote']
        fields.update(fileName=remote['name'], subfolder=remote['subfolder'], type=remote['type'])
    return fields


def media_parent(document, path):
    for part in path[:-1]:
        document = document[part]
    return document
