"""Check the AiMixer node’s first-pass and continuity cache on the target."""
import asyncio
import json


async def check_target_cache(self, key, workflow):
    data = self.rows[key]['input']
    if data.task_type in ('video-first-pass', 'video-second-pass'):
        self.save(key, phase='target_cache')
        for node_id, node in workflow.items():
            if node['class_type'] != 'MiniMaxH3Director':
                continue
            inputs = node['inputs']
            payload = {name: inputs[name] for name in (
                'timeline_data', 'task_type', 'global_prompt', 'total_frames', 'frame_rate', 'width', 'height',
                'ref_max_size', 'seed', 'cfg', 'steps', 'sampler', 'scheduler', 'shift_video', 'shift_audio') if name in inputs}
            payload.update(node_id=node_id, cache_name=inputs.get('cache_name', ''), sigmas_linked='sigmas' in inputs)
            for name in ('refine', 'selflift', 'semantic_bridge'):
                if name in inputs:
                    pack = workflow[inputs[name][0]]['inputs']
                    payload[name] = {field: value for field, value in pack.items() if not isinstance(value, list)}
                    payload[name]['has_sigmas_tensor'] = 'sigmas' in pack
            result = await asyncio.to_thread(self.client_for(data).json, '/minimax/director/first_pass_cache_status',
                json.dumps(payload, ensure_ascii=False).encode('utf8'), {'Content-Type': 'application/json'})
            self.record(key, 'target_cache', 'checked', url=data.url, response=result)
            if type(result.get('can_confirm_refine')) is not bool:
                raise ValueError('阶段缓存状态不明确；未提交生成，请核对原任务')
            if data.task_type == 'video-second-pass' and result.get('can_confirm_refine') is not True:
                raise ValueError('目标节点的一采缓存缺失或不匹配，不能执行二采；请核对来源缓存后处理，不会自动重做一采')
            if data.task_type == 'video-first-pass' and (result.get('can_confirm_refine') is True
                    or result.get('selected_matched', 0) > 0):
                raise ValueError('目标节点已有匹配的一采缓存，当前工作流会进入二采；请先核对目标节点缓存与任务阶段')
            timeline = json.loads(inputs['timeline_data'])
            # A matching first-pass latent already contains its original context;
            # only a new first pass needs a predecessor's final cache as a guide.
            if data.task_type == 'video-first-pass' and timeline.get('runSelectEnabled'):
                selected = set(timeline['runSelection'])
                cached = {item['index']: item for item in result['segments']}
                for index in selected:
                    if index and index - 1 not in selected and timeline['segments'][index].get('continuityFromPrev'):
                        previous = cached.get(index - 1, {})
                        matches = previous.get('final_matches') is True
                        if not matches:
                            differences = previous.get('final_diff_keys', [])
                            # First-pass guide uses the matching pre-refine source. A change
                            # confined to Refine settings does not invalidate that source.
                            matches = (previous.get('exists') is True and previous.get('matches') is True
                                       and previous.get('final_exists') is True and bool(differences)
                                       and all(name.startswith('refine_') for name in differences))
                        if not matches:
                            raise ValueError('目标节点缺少匹配的前段衔接缓存：组序 ' + str(index - 1))
