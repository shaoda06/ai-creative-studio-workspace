"""Agent enqueue preparation: no uploads or remote POST."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import comfyui_dispatch as d


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.root = self.workspace / "projects/test"
        self.root.mkdir(parents=True)
        (self.workspace / 'comfyui-config.json').write_text(json.dumps({'remote-urls':['http://main.invalid:8188','http://backup.invalid:8188']}))
        self.workflow = {'1':{'class_type':'SaveImage','inputs':{'seed':9223372036854775807}}}
        self.path = self.root / 'workflow.json'
        self.path.write_text(json.dumps(self.workflow))
        self.args = argparse.Namespace(project=str(self.root), workflow=str(self.path), task_type='image',
            output_plan='targets.json', task_title='CH001 · 首次生成', uploads=None, eligible_url=None,
            timeout=30, segment_plan=None, record_dir=str(self.root/'record'), monitor='browser', image_plan='image-plan.json')

    def test_only_backend_handoff_no_remote_upload_or_post(self):
        with patch.object(d.browser_tasks,'submit',return_value={'local_task_id':'uuid'}) as handoff, \
                patch.object(d.client,'submit') as post, patch.object(d.client,'upload') as upload:
            result=d.dispatch(self.args)
        self.assertEqual(result['dispatch_state'],'enqueued')
        handoff.assert_called_once_with(self.args,self.workflow,'http://main.invalid:8188',uploads=[])
        post.assert_not_called()
        upload.assert_not_called()

    def test_missing_title_is_not_replaced_by_directory_name(self):
        self.args.task_title=' '
        with patch.object(d.browser_tasks, 'submit', return_value={}) as handoff:
            d.dispatch(self.args)
        self.assertEqual(handoff.call_args.args[0].task_title, ' ')

    def test_h3_relationship_checks_are_delegated_to_preparation_not_repeated_in_cli(self):
        self.workflow['1']['class_type'] = 'MiniMaxH3ReferenceToVideo'
        self.path.write_text(json.dumps(self.workflow))
        for preparing in (True, False):
            self.args.prepare_only = preparing
            with self.subTest(preparing=preparing), \
                    patch.object(d.browser_tasks, 'submit', return_value={}) as handoff, \
                    patch.object(d.client, 'validate_workflow') as check:
                d.dispatch(self.args)
                handoff.assert_called_once()
                check.assert_not_called()

    def test_prepare_only_routes_to_tool_without_agent_validation_or_generation(self):
        self.args.prepare_only = True
        with patch.object(d.browser_tasks, 'submit', return_value={'prepared': True, 'report': '执行检查报告.json'}) as handoff, \
                patch.object(d.client, 'validate_workflow') as check, patch.object(d.client, 'submit') as post:
            result = d.dispatch(self.args)
        self.assertEqual(result['dispatch_state'], 'prepared')
        self.assertTrue(handoff.call_args.args[0].prepare_only)
        check.assert_not_called()
        post.assert_not_called()

    def test_rtx_validation_belongs_to_backend_preparation(self):
        self.args.prepare_only = True
        self.path.write_text(json.dumps({'1': {'class_type': 'RTXVideoSuperResolution', 'inputs': {}}}))
        with patch.object(d.browser_tasks, 'submit', return_value={}) as handoff:
            d.dispatch(self.args)
        handoff.assert_called_once()

    def test_prepared_enqueue_passes_workflow_without_cli_revalidation(self):
        self.args.prepare_only = False
        with patch.object(d.browser_tasks, 'submit', return_value={}) as handoff:
            d.dispatch(self.args)
        handoff.assert_called_once()

    def test_path_validation_is_owned_by_backend_boundary(self):
        self.args.record_dir = 'projects/' + self.root.name + '/执行附件/任务'
        with patch.object(d.browser_tasks, 'submit', return_value={}) as handoff:
            d.dispatch(self.args)
        self.assertEqual(handoff.call_args.args[0].record_dir, self.args.record_dir)

    def test_missing_output_plan_rejected_before_handoff(self):
        self.args.output_plan=None
        with self.assertRaises(ValueError): d.dispatch(self.args)

    def test_upload_mapping_is_passed_without_repeating_backend_checks(self):
        mapping=self.root/'uploads.json'
        mapping.write_text(json.dumps([{'file':'not-yet-present.png','node':'1','input':'image','subfolder':'','response-name':'upload.json'}]))
        self.args.uploads=str(mapping)
        with patch.object(d.browser_tasks,'submit',return_value={}) as handoff:
            d.dispatch(self.args)
        self.assertEqual(handoff.call_args.kwargs['uploads'][0]['file'], 'not-yet-present.png')

    def test_backup_cannot_be_selected(self):
        self.args.eligible_url='http://backup.invalid:8188'
        with self.assertRaises(ValueError): d.dispatch(self.args)

    def test_start_paused_is_explicit_and_keeps_primary_handoff(self):
        params = ['--project', str(self.root), '--task-type', 'image', '--workflow', str(self.path),
                  '--record-dir', str(self.root / 'record'), '--task-title', 'CH001 · 转移实测',
                  '--output-plan', 'targets.json', '--image-plan', 'image-plan.json']
        self.assertFalse(d.parser().parse_args(params).start_paused)
        args = d.parser().parse_args([*params, '--start-paused'])
        with patch.object(d.browser_tasks, 'submit', return_value={'status': 'paused'}) as handoff:
            result = d.dispatch(args)
        self.assertTrue(handoff.call_args.args[0].start_paused)
        self.assertEqual(handoff.call_args.args[2], 'http://main.invalid:8188')
        self.assertEqual(result['status'], 'paused')

    def test_nonempty_ordered_primary_and_legacy_config(self):
        self.assertEqual(d.load_config(self.root,30)['remote-urls'][0],'http://main.invalid:8188')
        (self.workspace/'comfyui-config.json').write_text(json.dumps({'remote-url':'http://main.invalid:8188'}))
        self.assertEqual(len(d.load_config(self.root,30)['remote-urls']),1)

    def test_task_list_is_one_handoff_without_manual_legacy_artifacts(self):
        args = d.parser().parse_args(['--project', str(self.root), '--plan', '任务清单.json'])
        with patch.object(d.browser_tasks, 'submit_plan', return_value={'status': 'enqueued', 'next_action': 'end-turn'}) as call, \
                patch.object(d.browser_tasks, 'submit', side_effect=AssertionError('no legacy handoff')), \
                patch.object(d.client, 'submit', side_effect=AssertionError('no remote')):
            result = d.dispatch(args)
        call.assert_called_once_with(args)
        self.assertEqual(result['next_action'], 'end-turn')

    def test_task_list_prepare_only_and_paused_flags_survive_handoff(self):
        args = d.parser().parse_args(['--project', str(self.root), '--plan', '任务清单.json', '--prepare-only', '--start-paused'])
        with patch.object(d.browser_tasks, 'submit_plan', return_value={'status': 'prepared'}) as call:
            d.dispatch(args)
        self.assertTrue(call.call_args.args[0].prepare_only)
        self.assertTrue(call.call_args.args[0].start_paused)

    def test_reprepare_requires_plan_and_prepare_only(self):
        for flags in (['--reprepare'], ['--plan', '任务清单.json', '--reprepare']):
            args = d.parser().parse_args(['--project', str(self.root), *flags])
            with patch.object(d.browser_tasks, 'submit_plan') as handoff, self.assertRaisesRegex(ValueError, '--prepare-only'):
                d.dispatch(args)
            handoff.assert_not_called()
        args = d.parser().parse_args(['--project', str(self.root), '--plan', '任务清单.json', '--prepare-only', '--reprepare'])
        with patch.object(d.browser_tasks, 'submit_plan', return_value={'status': 'prepared'}) as handoff:
            d.dispatch(args)
        self.assertTrue(handoff.call_args.args[0].reprepare)

    def test_reprepare_flags_reach_backend_payload(self):
        args = d.parser().parse_args(['--project', str(self.root), '--plan', '任务清单.json', '--prepare-only', '--reprepare'])
        with patch.object(d.browser_tasks, 'connection', return_value=(self.root.resolve(), {'workspace': str(self.workspace)}, 'caller', {})), \
                patch.object(d.browser_tasks, 'local_post', return_value={'status': 'prepared'}) as post:
            d.dispatch(args)
        self.assertEqual(post.call_args.args[1], '/submit-plan')
        self.assertTrue(post.call_args.args[2]['reprepare'])
        self.assertTrue(post.call_args.args[2]['prepare_only'])

    def test_shared_songssx_checks_the_planned_scenes_before_handoff(self):
        project = self.workspace.resolve() / '综合资料'
        project.mkdir()
        plan = project / '任务清单.json'
        six_parts = [f'P{i:03}' for i in range(1, 7)]
        cases = [
            ([[part] for part in six_parts], [','.join(six_parts)], '场次和 GEN 不匹配'),
            ([[part] for part in six_parts], [], '填写一组 --songssx-scene'),
            ([['P001']], [], '填写一组 --songssx-scene'),
            ([['P001']], [','.join(six_parts)], '场次和 GEN 不匹配'),
            ([six_parts], [','.join(reversed(six_parts))], '场次和 GEN 不匹配'),
            ([six_parts], [','.join(six_parts)], None),
            ([['P001', 'P002'], ['P003']], ['P001,P002', 'P003'], None),
            ([['P001']], ['P001'], None),
        ]
        for actual, expected, failure in cases:
            plan.write_text(json.dumps({'tasks': [
                {'task_type': 'video-scene-generation',
                 'songssx': {'segments': [{'p': p} for p in scene]}}
                for scene in actual
            ]}), encoding='utf-8')
            args = ['--project', str(project), '--plan', plan.name, '--prepare-only']
            for scene in expected:
                args.extend(['--songssx-scene', scene])
            with self.subTest(actual=actual, expected=expected), \
                    patch.object(d.browser_tasks, 'connection', return_value=(project, {'workspace': str(self.workspace)}, 'caller', {})), \
                    patch.object(d.browser_tasks, 'local_post', return_value={'status': 'prepared'}) as post:
                if failure:
                    with self.assertRaisesRegex(ValueError, failure):
                        d.dispatch(d.parser().parse_args(args))
                    post.assert_not_called()
                else:
                    d.dispatch(d.parser().parse_args(args))
                    post.assert_called_once()

    def test_songssx_scene_check_preserves_reuse_and_excludes_gap_repair(self):
        project = self.workspace.resolve() / '综合资料'
        project.mkdir()
        plan = project / '任务清单.json'
        command = ['--project', str(project), '--plan', plan.name]
        normal = {'task_type': 'video-scene-generation', 'songssx': {'segments': [{'p': 'P001'}]}}
        repair = {'task_type': 'video-scene-generation', 'songssx': {'gap_repair': {}, 'segments': [{'p': 'P002'}]}}
        with patch.object(d.browser_tasks, 'connection', return_value=(project, {'workspace': str(self.workspace)}, 'caller', {})), \
                patch.object(d.browser_tasks, 'local_post', return_value={'status': 'enqueued'}) as post:
            plan.write_text(json.dumps({'tasks': [repair]}), encoding='utf-8')
            d.dispatch(d.parser().parse_args(command))
            post.assert_called_once()
            post.reset_mock()
            plan.write_text(json.dumps({'tasks': [normal, repair]}), encoding='utf-8')
            d.dispatch(d.parser().parse_args([*command, '--songssx-scene', 'P001']))
            post.assert_called_once()
            post.reset_mock()
            original = {'tasks': [normal]}
            plan.write_text(json.dumps(original), encoding='utf-8')
            plan.with_name(plan.stem + '-装配结果.json').write_text(json.dumps({'source': original}), encoding='utf-8')
            d.dispatch(d.parser().parse_args(command))
            post.assert_called_once()
            post.reset_mock()
            reprepare = [*command, '--prepare-only', '--reprepare']
            with self.assertRaisesRegex(ValueError, '填写一组 --songssx-scene'):
                d.dispatch(d.parser().parse_args(reprepare))
            post.assert_not_called()
            d.dispatch(d.parser().parse_args([*reprepare, '--songssx-scene', 'P001']))
            post.assert_called_once()
            self.assertTrue(post.call_args.args[2]['reprepare'])

    def test_songssx_checks_nested_shared_scope_and_reports_incomplete_segments(self):
        project = self.workspace.resolve() / '具名项目' / '综合资料'
        project.mkdir(parents=True)
        plan = project / '任务清单.json'
        command = ['--project', str(project), '--plan', plan.name]
        task = {'task_type': 'video-scene-generation', 'songssx': {'segments': [{}]}}
        plan.write_text(json.dumps({'tasks': [task]}), encoding='utf-8')
        with patch.object(d.browser_tasks, 'connection', return_value=(project, {'workspace': str(self.workspace)}, 'caller', {})), \
                patch.object(d.browser_tasks, 'local_post', return_value={'status': 'enqueued'}) as post:
            with self.assertRaisesRegex(ValueError, '填写一组 --songssx-scene'):
                d.dispatch(d.parser().parse_args(command))
            args = d.parser().parse_args([*command, '--songssx-scene', 'P001'])
            with self.assertRaisesRegex(ValueError, '各段的 p 编号'):
                d.dispatch(args)
            post.assert_not_called()
            task['songssx']['segments'][0]['p'] = 'P001'
            plan.write_text(json.dumps({'tasks': [task]}), encoding='utf-8')
            d.dispatch(args)
            post.assert_called_once()
            self.assertEqual(post.call_args.args[2]['project'], '具名项目::@shared')

    def test_group_status_cli_uses_group_endpoint(self):
        import io
        from contextlib import redirect_stdout
        with patch('sys.argv', ['browser_tasks.py', 'status', '--group-id', 'group-uuid']), \
                patch.object(d.browser_tasks, 'service_call', return_value={'id': 'group-uuid', 'completed_tasks': 1}) as call, \
                redirect_stdout(io.StringIO()) as output:
            d.browser_tasks.main()
        call.assert_called_once_with('groups/group-uuid', workspace=None)
        self.assertEqual(json.loads(output.getvalue())['completed_tasks'], 1)


if __name__=='__main__': unittest.main()
