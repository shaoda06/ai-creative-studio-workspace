"""Pure unit tests: no local server, no remote calls, no media generation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import comfyui_client as c


class FakeClient:
    url = "http://example.invalid"

    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def json(self, route, data=None, headers=None):
        self.calls.append((route, data))
        if self.error:
            raise self.error
        return self.result


class ClientTests(unittest.TestCase):
    def test_api_shape(self):
        for value in ({}, {"nodes": []}, {"prompt": {}}, {"1": {"inputs": {}}}):
            with self.assertRaises(c.ClientError):
                c.validate_workflow(value)
        c.validate_workflow({"arbitrary-node": {"class_type": "Arbitrary", "inputs": {"seed": 100}}})

    def test_strict_json(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(ValueError):
                c.strict_json(raw)

    def test_paths(self):
        for path in ("../x", "/x", "C:/x", "a\\..\\b", "a\nx"):
            with self.assertRaises(c.ClientError):
                c.remote_path(path)
        self.assertEqual(c.remote_path("测试 文件"), "测试 文件")
        self.assertEqual(c.remote_path("output\\subfolder"), "output\\subfolder")
        with self.assertRaises(c.ClientError):
            c.remote_path("a\\b.png", filename=True)

    def test_url_and_timeout(self):
        for url in ("", "file:///tmp/x", "http://u:p@server", "http://server?token=x"):
            with self.assertRaises(c.ClientError):
                c.Client(url, 30)
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(c.ClientError):
                c.Client("http://server", timeout)

    def test_states(self):
        pid = "p"
        self.assertEqual(c.classify({}, {}, pid)[0], "unknown")
        self.assertEqual(c.classify({}, {"queue_running": [[0, pid]]}, pid)[0], "running")
        self.assertEqual(c.classify({}, {"queue_pending": [[0, pid]]}, pid)[0], "queued")
        self.assertEqual(c.classify({pid: {"status": {"completed": True}}}, {}, pid)[0], "unknown")
        success = {"completed": True, "status_str": "success"}
        self.assertEqual(c.classify({pid: {"status": success}}, {}, pid)[0], "success")
        success["messages"] = [["execution_interrupted", {}]]
        self.assertEqual(c.classify({pid: {"status": success}}, {}, pid)[0], "failed")

    def test_status_does_not_expose_other_jobs_or_submit(self):
        client = FakeClient()
        responses = [{}, {"queue_running": [[0, "other", {"private": "data"}]],
                          "queue_pending": [[1, "mine", {}]]}]
        client.json = lambda route: responses.pop(0)
        result = c.status(client, argparse.Namespace(prompt_id="mine"))
        self.assertEqual(result["state"], "queued")
        self.assertEqual(result["queue"]["queue_running"], [])

    def test_files_are_listed_not_selected(self):
        output = {"99": {"gifs": [{"filename": "a.mp4", "type": "output"},
                                   {"filename": "b.mp4", "type": "output"}]}}
        client = FakeClient({"p": {"status": {"completed": True, "status_str": "success"},
                                    "outputs": output}})
        result = c.status(client, argparse.Namespace(prompt_id="p"))
        self.assertEqual(len(result["files"]), 2)
        self.assertEqual(len(client.calls), 1)

    def submit_case(self, folder, client):
        root = Path(folder)
        wf = root / "api.json"
        if not wf.exists():
            c.write_new(wf, {"1": {"class_type": "Any", "inputs": {"seed": 9007199254740993}}})
        args = argparse.Namespace(workflow=str(wf), record_dir=str(root / "record"),
                                  request_name="request.json", response_name="response.json",
                                  attempt_name="submit-attempt.json")
        return args, lambda: c.submit(client, args)

    def test_submit_is_exact_and_guarded(self):
        with tempfile.TemporaryDirectory() as folder:
            client = FakeClient({"prompt_id": "accepted"})
            args, run = self.submit_case(folder, client)
            self.assertEqual(run()["prompt_id"], "accepted")
            request = json.loads(client.calls[0][1])
            self.assertEqual(request["prompt"], json.loads(Path(args.workflow).read_bytes()))
            with self.assertRaises(c.ClientError) as caught:
                run()
            self.assertEqual(caught.exception.code, "submission_guard")
            self.assertEqual(caught.exception.details['submission_state'], 'not_sent')
            self.assertEqual(len(client.calls), 1)

    def test_file_input_checks_structure_once_and_rejects_ui_canvas(self):
        with tempfile.TemporaryDirectory() as folder:
            client = FakeClient({"prompt_id": "accepted"})
            args, run = self.submit_case(folder, client)
            with patch.object(c, 'validate_workflow', wraps=c.validate_workflow) as check:
                run()
                check.assert_called_once()
        with tempfile.TemporaryDirectory() as folder:
            args, run = self.submit_case(folder, client)
            Path(args.workflow).write_text(json.dumps({'nodes': []}), 'utf-8')
            with self.assertRaises(c.ClientError) as invalid:
                run()
            self.assertEqual(invalid.exception.code, 'invalid_workflow')
            self.assertFalse(Path(args.record_dir).exists())
            self.assertEqual(len(client.calls), 1)

    def test_each_existing_evidence_file_blocks_without_post_or_overwrite(self):
        for field in ('attempt_name', 'request_name', 'response_name'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                client = FakeClient({"prompt_id": "accepted"})
                args, run = self.submit_case(folder, client)
                evidence = Path(args.record_dir) / getattr(args, field)
                evidence.parent.mkdir()
                evidence.write_bytes(b'original evidence')
                with self.assertRaises(c.ClientError) as blocked:
                    run()
                self.assertEqual(blocked.exception.details['submission_state'], 'not_sent')
                self.assertEqual(evidence.read_bytes(), b'original evidence')
                self.assertEqual(list(evidence.parent.iterdir()), [evidence])
                self.assertFalse(client.calls)

    def test_concurrent_reservation_only_one_post_and_loser_is_not_sent(self):
        with tempfile.TemporaryDirectory() as folder:
            client = FakeClient({"prompt_id": "accepted"})
            args, run = self.submit_case(folder, client)
            barrier = threading.Barrier(2)
            write = c.write_new
            def reserve(path, value):
                if Path(path).name == args.attempt_name:
                    barrier.wait(timeout=5)
                return write(path, value)
            def attempt():
                try:
                    return run()['submission_state']
                except c.ClientError as error:
                    self.assertEqual(error.code, 'submission_guard')
                    return error.details['submission_state']
            with patch.object(c, 'write_new', side_effect=reserve), ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: attempt(), range(2)))
            self.assertCountEqual(results, ['accepted', 'not_sent'])
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(json.loads((Path(args.record_dir) / args.response_name).read_bytes()), {'prompt_id': 'accepted'})

    def test_post_timeout_stays_unknown_and_never_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            client = FakeClient(error=c.ClientError("transport_error", "timeout"))
            args, run = self.submit_case(folder, client)
            with self.assertRaises(c.ClientError) as caught:
                run()
            self.assertEqual(caught.exception.code, "submission_unknown")
            with self.assertRaises(c.ClientError):
                run()
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(json.loads((Path(args.record_dir) / "response.json").read_bytes())["submission_state"], "unknown")

    def test_custom_evidence_names(self):
        with tempfile.TemporaryDirectory() as folder:
            client = FakeClient({"prompt_id": "accepted"})
            args, run = self.submit_case(folder, client)
            args.request_name, args.response_name, args.attempt_name = "请求.json", "提交响应.json", "提交尝试.json"
            run()
            self.assertEqual({p.name for p in Path(args.record_dir).iterdir()},
                             {"请求.json", "提交响应.json", "提交尝试.json"})
            with self.assertRaises(c.ClientError):
                run()
            self.assertEqual(len(client.calls), 1)

    def test_malformed_success_response_stays_guarded(self):
        with tempfile.TemporaryDirectory() as folder:
            client = FakeClient({"number": 1})
            args, run = self.submit_case(folder, client)
            with self.assertRaises(c.ClientError) as caught:
                run()
            self.assertEqual(caught.exception.code, "submission_unknown")
            self.assertTrue((Path(args.record_dir) / "response.json").exists())
            with self.assertRaises(c.ClientError):
                run()
            self.assertEqual(len(client.calls), 1)

    def test_rejected_submission_has_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            client = FakeClient(error=c.ClientError("http_error", "bad", http_status=400, response={"error": "bad node"}))
            args, run = self.submit_case(folder, client)
            with self.assertRaises(c.ClientError) as caught:
                run()
            self.assertEqual(caught.exception.code, "submission_rejected")
            self.assertTrue((Path(args.record_dir) / "request.json").exists())

    def test_download_no_overwrite_and_no_partial_file(self):
        class Stream(io.BytesIO):
            headers = {"Content-Length": "4"}
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "out"
            args = argparse.Namespace(filename="x", subfolder="", type="output", output=str(target), sha256=None)
            client = FakeClient()
            client.open = lambda route: Stream(b"abc")
            with self.assertRaises(c.ClientError) as caught:
                c.download(client, args)
            self.assertEqual(caught.exception.code, "incomplete_download")
            self.assertEqual(list(Path(folder).iterdir()), [])
            target.write_bytes(b"keep")
            with self.assertRaises(c.ClientError):
                c.download(client, args)
            self.assertEqual(target.read_bytes(), b"keep")

    def test_download_publish_race_does_not_overwrite(self):
        class Stream(io.BytesIO):
            headers = {"Content-Length": "3"}
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "out"
            args = argparse.Namespace(filename="x", subfolder="", type="output", output=str(target), sha256=None)
            client = FakeClient()
            client.open = lambda route: Stream(b"abc")
            original = c.os.link
            def race(source, dest):
                Path(dest).write_bytes(b"other writer")
                original(source, dest)
            with patch.object(c.os, "link", side_effect=race), self.assertRaises(FileExistsError):
                c.download(client, args)
            self.assertEqual(target.read_bytes(), b"other writer")
            self.assertEqual(len(list(Path(folder).iterdir())), 1)

if __name__ == "__main__":
    unittest.main()
