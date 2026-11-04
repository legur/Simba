"""Offline safety tests for one A2E 3days staged frame + one video."""
from __future__ import annotations
import json
import sys
import tempfile
from contextlib import ExitStack
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_a2e_prague_one_clip_3days as m


def event(label=m.TRIGGER):
    return {
        "action": "labeled", "label": {"name": label},
        "repository": {"full_name": "legur/Simba"},
        "issue": {"number": 8, "user": {"login": "legur"}}
    }


def fake_success(cdn, price=30):
    calls = []
    def append(name, result):
        calls.append(name)
        return result
    impl = {
        "api_get_pricing": lambda key: append("price", 1.0),
        "read_source_image": lambda: append("source", b"\xff\xd8" + b"a" * 2000),
        "journal": lambda marker, note: append("journal:"+marker, None),
        "charged_presign": lambda key, size: append(
            "presign", ("https://storage.example.com/upload?signed=abc", cdn)
        ),
        "upload_bytes": lambda url, data: append("PUT", None),
        "verify_staged_image": lambda url: append("cdn_GET", True),
        "exact_quote": lambda body, key: append("quote", price),
        "a2e_start": lambda body, key: append(
            "VIDEO_START", {"code": 0, "data": {"_id": "507f1f77bcf86cd799439011"}}
        ),
        "a2e_status": lambda task_id, key: append(
            "STATUS_GET", {"code": 0, "data": {
                "current_status": "completed",
                "result_url": "https://cdn.example.com/video.mp4"
            }}
        ),
        "download_video": lambda url, dest: append("DOWNLOAD", dest.write_bytes(b"MP4")),
    }
    return calls, impl


class OneClipTests(unittest.TestCase):
    def test_budget_and_one_task(self):
        calls, helpers = fake_success("https://3days-apac.makefun.ai/scene1.jpg")
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            m.os.environ, {"A2E_API_KEY": "sk_test_dummy_00000000"}
        ):
            with ExitStack() as stack:
                for name, fake in helpers.items():
                    stack.enter_context(patch.object(m, name, side_effect=fake))
                output = m.run(event(), Path(temp), max_new=31, pause=lambda sec: None)
                self.assertEqual(output["status"], "VIDEO_READY")
                self.assertEqual(output["stage_price"] + output["video_quote"], 31.0)
                self.assertEqual(len(list(Path(temp).glob("*.mp4"))), 1)
        self.assertEqual(calls.count("presign"), 1)
        self.assertEqual(calls.count("VIDEO_START"), 1)
        self.assertLess(calls.index("journal:" + m.PRESIGN_MARKER), calls.index("presign"))
        self.assertLess(calls.index("journal:" + m.START_MARKER), calls.index("VIDEO_START"))
        self.assertLess(calls.index("cdn_GET"), calls.index("VIDEO_START"))
        self.assertLess(calls.index("quote"), calls.index("VIDEO_START"))

    def test_cdn_403_prevents_video_spend(self):
        calls, helpers = fake_success("https://3days-apac.makefun.ai/image.jpg")
        helpers["verify_staged_image"] = lambda url: calls.append("cdn_403") or False
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            m.os.environ, {"A2E_API_KEY": "sk_test_dummy_00000000"}
        ):
            with ExitStack() as stack:
                for name, fake in helpers.items():
                    stack.enter_context(patch.object(m, name, side_effect=fake))
                output = m.run(event(), Path(temp))
        self.assertEqual(output["status"], "STOPPED")
        self.assertIn("cdn", output["note"].lower())
        self.assertNotIn("VIDEO_START", calls)
        self.assertNotIn("quote", calls)

    def test_quote_exceeds_30_blocks_paid_start(self):
        calls, helpers = fake_success("https://3days-apac.makefun.ai/image.jpg", price=31)
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            m.os.environ, {"A2E_API_KEY": "sk_test_dummy_00000000"}
        ):
            with ExitStack() as stack:
                for name, fake in helpers.items():
                    stack.enter_context(patch.object(m, name, side_effect=fake))
                output = m.run(event(), Path(temp))
        self.assertEqual(output["status"], "STOPPED")
        self.assertNotIn("VIDEO_START", calls)
        self.assertNotIn("journal:" + m.START_MARKER, calls)

    def test_exact_quote_validation(self):
        body = m.build_body("https://3days-apac.makefun.ai/image.jpg")
        self.assertEqual(body["model_version"], "a2e")
        self.assertFalse(body["auto_add_audio"])
        self.assertEqual(body["video_time"], 5)
        with patch.object(m, "request_quote", return_value={
                "code": 0, "data": {"available": True, "exact": True, "coins": 30}
            }):
            self.assertEqual(m.exact_quote(body, "sk_dummy"), 30)
        with patch.object(m, "request_quote", return_value={
                "code": 0, "data": {"available": True, "exact": False, "coins": 30}
            }):
            with self.assertRaises(m.Stopped):
                m.exact_quote(body, "sk_dummy")
        with patch.object(m, "request_quote", return_value={
                "code": 0, "data": {"available": True, "exact": True, "coins": 31}
            }):
            with self.assertRaises(m.Stopped):
                m.exact_quote(body, "sk_dummy")

    def test_only_expected_three_day_cdn(self):
        self.assertTrue(m.image_cdn_is_expected("https://3days-apac.makefun.ai/file.jpg"))
        for url in (
            "https://7days-apac.downloadaivideo.com/test.jpg",
            "http://3days-apac.makefun.ai/test.jpg",
            "https://3days-apac.makefun.ai.evil.example/x",
            "https://localhost/test.jpg"
        ):
            self.assertFalse(m.image_cdn_is_expected(url))
            with self.assertRaises(m.Stopped):
                m.build_body(url)

    def test_no_spend_for_wrong_trigger_or_overbudget(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(m.run(event(label="a2e-quote"), Path(temp))["status"], "STOPPED")
            self.assertEqual(m.run(event(), Path(temp), max_new=50)["status"], "STOPPED")

    def test_journal_duplicate_blocks_replay(self):
        def prior_get(method, body=None):
            self.assertEqual(method, "GET")
            return [{"body": m.PRESIGN_MARKER, "id": 10}]
        with patch.object(m, "gh_request", side_effect=prior_get):
            with self.assertRaises(m.Stopped):
                m.journal(m.PRESIGN_MARKER, "one test")

    def test_journal_posts_before_spend(self):
        calls = []
        def handler(method, body=None):
            calls.append(method)
            return [] if method == "GET" else {"id": 44}
        with patch.object(m, "gh_request", side_effect=handler):
            m.journal(m.PRESIGN_MARKER, "test")
        self.assertEqual(calls, ["GET", "POST"])

    def test_no_video_retry_after_ambiguous_error(self):
        calls, helpers = fake_success("https://3days-apac.makefun.ai/image.jpg")
        def rejected(body, key):
            calls.append("VIDEO_START")
            raise m.StopGeneration("A2E_START_HTTP_400_CODE_400")
        helpers["a2e_start"] = rejected
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            m.os.environ, {"A2E_API_KEY": "sk_test_dummy_00000000"}
        ):
            with ExitStack() as stack:
                for name, fake in helpers.items():
                    stack.enter_context(patch.object(m, name, side_effect=fake))
                result = m.run(event(), Path(temp))
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual(calls.count("VIDEO_START"), 1)


if __name__ == "__main__":
    unittest.main()
