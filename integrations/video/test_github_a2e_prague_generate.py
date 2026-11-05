"""Regression tests for the six-scene 180-credit A2E authorization."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_a2e_prague_generate as paid

def event():
    scenes = []
    for i, url in enumerate(paid.EXPECTED_URLS, 1):
        scenes.append({"name": "Prague %d" % i, "image_url": url, "prompt": "Camera glide"})
    return {"action": "labeled", "label": {"name": "a2e-recover-180"},
            "repository": {"full_name": "legur/Simba"},
            "issue": {"number": 8, "user": {"login": "legur"},
                      "body": json.dumps({"kind": "simba_a2e_quote", "scenes": scenes})}}

def quote_ok(body, key):
    return {"code": 0, "data": {"available": True, "exact": True, "coins": 30}}

class GuardTests(unittest.TestCase):
    def test_video_download_uses_explicit_genjutsu_user_agent(self):
        calls = []
        class Response:
            def __init__(self):
                self.read_count = 0
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return "https://video.cdn.example/ready.mp4"
            def read(self, size):
                self.read_count += 1
                return b"x" * 1024 if self.read_count == 1 else b""
        def fake_open(request, timeout):
            calls.append(request)
            return Response()
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "video.mp4"
            with patch.object(paid, "urlopen", side_effect=fake_open):
                paid.download_video("https://video.cdn.example/ready.mp4", dest)
            self.assertEqual(dest.stat().st_size, 1024)
        self.assertEqual(len(calls), 1)
        headers = {k.lower(): v for k, v in calls[0].headers.items()}
        self.assertEqual(headers.get("user-agent"), "Genjutsu")
        self.assertNotIn("authorization", headers)

    def test_exact_approved_scenes(self):
        bodies = paid.validated_request(event(), 180)
        self.assertEqual(len(bodies), 6)
        self.assertEqual([x["image_url"] for x in bodies], paid.EXPECTED_URLS)
        self.assertTrue(all(x["video_time"] == 5 and x["auto_add_audio"] is False for x in bodies))

    def test_wrong_cap_and_wrong_issue_blocked(self):
        with self.assertRaises(paid.StopGeneration):
            paid.validated_request(event(), 181)
        ev = event()
        ev["issue"]["number"] = 9
        with self.assertRaises(paid.StopGeneration):
            paid.validated_request(ev, 180)

    def test_changed_images_blocked(self):
        ev = event()
        data = json.loads(ev["issue"]["body"])
        data["scenes"][0]["image_url"] = paid.EXPECTED_URLS[1]
        ev["issue"]["body"] = json.dumps(data)
        with self.assertRaises(paid.StopGeneration):
            paid.validated_request(ev, 180)

    def test_fresh_quote_price_cap(self):
        bodies = paid.validated_request(event(), 180)
        self.assertEqual(sum(paid.priced_within_cap(bodies, "sk_test_fake", quote_ok)), 180)
        with self.assertRaises(paid.StopGeneration):
            paid.priced_within_cap(bodies, "sk_test_fake",
                                    lambda body, key: {"code": 0, "data": {
                                        "available": True, "exact": True, "coins": 31}})
        with self.assertRaises(paid.StopGeneration):
            paid.priced_within_cap(bodies, "sk_test_fake",
                                    lambda body, key: {"code": 0, "data": {
                                        "available": False, "exact": False, "coins": 0}})

    def test_journal_blocks_replay_before_charge(self):
        calls = []
        def fake_request(method, json_body=None):
            calls.append(method)
            if method == "GET":
                return [{"body": paid.JOURNAL_MARKER, "user": {"login": "github-actions[bot]"}}]
            raise AssertionError("Paid intent duplicate should not POST")
        with patch.object(paid, "github_request", side_effect=fake_request):
            with self.assertRaises(paid.StopGeneration):
                paid.claim_start()
        self.assertEqual(calls, ["GET"])

    def test_journal_written_before_first_paid_start(self):
        sequence = []
        def fake_request(method, json_body=None):
            sequence.append(method)
            return [] if method == "GET" else {"id": 556}
        with patch.object(paid, "github_request", side_effect=fake_request):
            paid.claim_start()
        self.assertEqual(sequence, ["GET", "POST"])

    def test_paid_submit_only_after_quote_and_durable_journal(self):
        sequence = []
        original_quote = paid.priced_within_cap
        def traced_quote(*args, **kwargs):
            sequence.append("quote")
            return [30.0 for _ in args[0]]
        def traced_claim():
            sequence.append("journal")
        def traced_start(body, key):
            sequence.append("start")
            return {"code": 0, "data": {"_id": "507f1f77bcf86cd799439011", "coins": 30}}
        def traced_status(task_id, key):
            return {"code": 0, "data": {"current_status": "failed"}}
        with tempfile.TemporaryDirectory() as d, (
            patch.dict(paid.os.environ, {"A2E_API_KEY": "sk_test_fake_token_0123456789"})), (
            patch.object(paid, "priced_within_cap", side_effect=traced_quote)), (
            patch.object(paid, "claim_start", side_effect=traced_claim)), (
            patch.object(paid, "verify_no_paid_effect_since_first_attempt", return_value=None)), (
            patch.object(paid, "a2e_start", side_effect=traced_start)), (
            patch.object(paid, "a2e_status", side_effect=traced_status)):
            outcome = paid.run(event(), Path(d), cap=180)
        self.assertEqual(outcome["status"], "PARTIALLY_READY_OR_PROCESSING")
        self.assertEqual(len(outcome["task_ids"]), 6)
        self.assertEqual(sequence.count("start"), 6)
        self.assertEqual(sequence[0], "quote")
        self.assertEqual(sequence[1], "journal")
        self.assertTrue(sequence.index("journal") < sequence.index("start"))

    def test_recovery_requires_zero_tasks_and_zero_credit_consumption(self):
        with patch.object(paid, "read_json", side_effect=[
            {"code": 0, "data": {"rows": [], "count": 0}},
            {"code": 0, "data": {"rows": [], "count": 0}},
        ]):
            paid.verify_no_paid_effect_since_first_attempt("sk_fake")
        with patch.object(paid, "read_json", side_effect=[
            {"code": 0, "data": {"rows": [], "count": 0}},
            {"code": 0, "data": {"rows": [
                {"createdAt": "2026-11-03T20:12:00Z", "amount": -30}
            ], "count": 1}},
        ]):
            with self.assertRaises(paid.StopGeneration):
                paid.verify_no_paid_effect_since_first_attempt("sk_fake")

    def test_http_400_support_trace_id_is_safely_preserved(self):
        import io
        from urllib.error import HTTPError
        good_trace = "3f2c9a1e-8b7d-4c6a-9e15-2d4b7f0a6c81"
        def fake_http_error(req, timeout):
            raw = json.dumps({"code": 400, "msg": "Request failed",
                              "trace_id": good_trace}).encode("utf-8")
            raise HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(raw))
        with patch.object(paid, "urlopen", side_effect=fake_http_error):
            with self.assertRaises(paid.StopGeneration) as ctx:
                paid.a2e_start({"name": "Prague", "image_url": paid.EXPECTED_URLS[0]}, "sk_dummy_for_test")
        self.assertIn("HTTP_400_CODE_400", str(ctx.exception))
        self.assertIn("TRACE_" + good_trace, str(ctx.exception))
        self.assertNotIn("Request failed", str(ctx.exception))

    def test_business_error_trace_is_safely_preserved(self):
        token = "sample_trace_20261104"
        with self.assertRaises(paid.StopGeneration) as ctx:
            paid.checked_api({"code": 400, "msg": "secret error detail", "trace_id": token})
        self.assertIn("TRACE_" + token, str(ctx.exception))
        self.assertNotIn("secret error detail", str(ctx.exception))

    def test_start_error_never_retried(self):
        submissions = []
        with tempfile.TemporaryDirectory() as d, (
            patch.dict(paid.os.environ, {"A2E_API_KEY": "sk_test_fake_token_0123456789"})), (
            patch.object(paid, "priced_within_cap", side_effect=lambda bodies, key: [30.0 for _ in bodies])), (
            patch.object(paid, "claim_start", return_value=None)), (
            patch.object(paid, "verify_no_paid_effect_since_first_attempt", return_value=None)), (
            patch.object(paid, "a2e_start", side_effect=lambda body, key: (
                submissions.append(body) or (_ for _ in ()).throw(paid.StopGeneration("Ambiguous request"))))):
            outcome = paid.run(event(), Path(d), cap=180)
        self.assertEqual(outcome["status"], "STOPPED")
        self.assertEqual(len(submissions), 1)
        self.assertEqual(outcome["current_scene"], 1)

if __name__ == "__main__":
    unittest.main()
