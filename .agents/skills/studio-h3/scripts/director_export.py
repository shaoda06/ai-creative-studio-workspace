"""Export an explicit frozen H3 package specification; never submit generation."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-comfyui/scripts'))
import comfyui_client as client
import comfyui_config
import execution_records as recordio
from h3_pack import MEDIA, verify_pack


def export_package(spec, resolve_file, workspace, output, timeout=300):
    workflow = copy.deepcopy(spec['workflow']) if 'workflow' in spec else recordio.read(resolve_file(spec['api']))
    node = spec['node_id']
    if workflow[node]['class_type'] != 'MiniMaxH3Director':
        raise ValueError('导演包清单必须指向原生导演台节点')
    media = {remote: resolve_file(local) for remote, local in spec['media'].items()}
    timeline = client.strict_json(workflow[node]['inputs']['timeline_data'])
    url = spec.get('url')
    if not url:
        urls = comfyui_config.remote_urls(workspace)
        if len(urls) != 1:
            raise ValueError('导演包清单须明确使用哪个ComfyUI节点')
        url = urls[0]
    connection = comfyui_config.client_for(workspace, url, timeout)
    def restore_inputs():
        nonlocal media
        replacements, uploaded = {}, {}
        for remote, local in media.items():
            if local not in uploaded:
                uploaded[local] = client.upload(connection, argparse.Namespace(
                    file=local, subfolder='studio-director-downloads'))['input_path']
            replacements[remote] = uploaded[local]

        def restore(value):
            if isinstance(value, dict):
                for key, content in value.items():
                    if key in MEDIA and content:
                        value[key] = replacements[content]
                    else:
                        restore(content)
            elif isinstance(value, list):
                for item in value:
                    restore(item)

        restore(timeline)
        media = {replacements[remote]: local for remote, local in media.items()}
        workflow[node]['inputs']['timeline_data'] = json.dumps(timeline, ensure_ascii=False)

    # Native exporters treat package-relative paths as already packed and skip them.
    # Restore those references before export, even when dryRun reports no missing files.
    if spec.get('media_origin') == 'pack':
        restore_inputs()
    with tempfile.TemporaryDirectory(prefix='director-api-', dir=Path(output).parent) as folder:
        source = Path(folder) / 'export.api.json'
        source.write_text(json.dumps(workflow, ensure_ascii=False), encoding='utf-8')
        args = argparse.Namespace(workflow=source, node_id=node, output=output)
        try:
            result = client.export_pack(connection, args)
        except client.ClientError as error:
            if error.code != 'missing_assets' or spec.get('media_origin') == 'pack':
                raise
            restore_inputs()
            source.write_text(json.dumps(workflow, ensure_ascii=False), encoding='utf-8')
            result = client.export_pack(connection, args)
        verify_pack({'pack': output, 'workflow': workflow, 'node': node, 'timeline': timeline, 'media': media})
    return result
