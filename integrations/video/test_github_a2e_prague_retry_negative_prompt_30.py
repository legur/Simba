"""Regression tests for support-confirmed negative_prompt one-time retry."""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_a2e_prague_retry_negative_prompt_30 as m
from github_a2e_prague_one_clip_3days import Stopped


def event(label=m.LABEL):
    return {"action": "labeled", "label": {"name": label},
            "repository": {"full_name": "legur/Simba"},
            "issue": {"number": 8, "user": {"login": "legur"}}}


def run_mocks(*, cdn_ok=True, price=30, paid_raises=False, history_ok=True):
    calls = []
    def make(name, outcome):
        def fn(*args, **kwargs):
            calls.append(name)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome(*args, **kwargs) if callable(outcome) else outcome
        return fn
    fakes = {
        "verify_staged_image": make("CDN_GET", cdn_ok),
        "already_started": make("HISTORY_GET", None if history_ok else Stopped("Duplicate task")),
        "exact_quote": make("FREE_QUOTE", price),
        "journal": make("JOURNAL", None),
        "a2e_start": make("PAID_START", (m.StopGeneration("A2E_START_HTTP_400_CODE_400")
                                      if paid_raises else {
                 "code": 0, "data": {"_id": "507f1f77bcf86cd799439011",
                                      "current_status": "initialized"}})),
        "a2e_status": make("STATUS_GET", {
            "code": 0, "data": {"current_status": "completed",
                               "result_url": "https://cdn.example/video.mp4"}}),
        "download_video": make("DOWNLOAD", lambda url, dest: dest.write_bytes(b"MP4" * 500)),
    }
    return calls, fakes


class OneExistingAssetTests(unittest.TestCase):
    def _execute(self, calls, fakes, *, label=m.LABEL, cap=30):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(m.os.environ, {"A2E_API_KEY": "sk_fake_unit_test_123456789"}), ExitStack() as stack:
                for name, fun in fakes.items():
                    stack.enter_context(patch.object(m, name, side_effect=fun))
                output = m.run(event(label), Path(td), max_new=cap, pause=lambda sec: None)
                artifacts = [p.name for p in Path(td).glob("*.mp4")]
                self.assertTrue((Path(td) / "report.md").exists())
                return output, artifacts

    def test_one_prepublished_image_one_video_exactly_30_credits(self):
        calls, fakes = run_mocks()
        result, artifacts = self._execute(calls, fakes)
        self.assertEqual(result["status"], "VIDEO_READY")
        self.assertEqual(result["video_quote_credits"], 30)
        self.assertEqual(result["new_presign_credits"], 0)
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(calls.count("PAID_START"), 1)
        self.assertEqual(calls.count("JOURNAL"), 1)
        self.assertEqual(calls, ["CDN_GET", "HISTORY_GET", "FREE_QUOTE",
                                 "JOURNAL", "PAID_START", "STATUS_GET", "DOWNLOAD"])

    def test_cdn_failure_stops_before_spending(self):
        calls, fakes = run_mocks(cdn_ok=False)
        result, _ = self._execute(calls, fakes)
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual(calls, ["CDN_GET"])

    def test_existing_a2e_task_stops_before_spending(self):
        calls, fakes = run_mocks(history_ok=False)
        result, _ = self._execute(calls, fakes)
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual(calls, ["CDN_GET", "HISTORY_GET"])

    def test_quote_above_limit_blocks_paid_start(self):
        calls, fakes = run_mocks(price=31)
        result, _ = self._execute(calls, fakes)
        self.assertEqual(result["status"], "STOPPED")
        self.assertNotIn("JOURNAL", calls)
        self.assertNotIn("PAID_START", calls)

    def test_wrong_label_or_cap_blocks_all_requests(self):
        for label, cap in (("a2e-quote", 30), (m.LABEL, 31)):
            calls, fakes = run_mocks()
            result, _ = self._execute(calls, fakes, label=label, cap=cap)
            self.assertEqual(result["status"], "STOPPED")
            self.assertEqual(calls, [])

    def test_paid_http_error_not_retried(self):
        calls, fakes = run_mocks(paid_raises=True)
        result, _ = self._execute(calls, fakes)
        self.assertEqual(result["status"], "STOPPED")
        self.assertIn("A2E_START_HTTP_400_CODE_400", result["note"])
        self.assertEqual(calls.count("PAID_START"), 1)
        self.assertNotIn("STATUS_GET", calls)

    def test_history_fails_closed_if_matching_image(self):
        rows = [
            {"_id": "1", "name": "other-task", "image_url": m.SOURCE_CDN,
             "createdAt": "2026-11-05T00:00:00Z"}
        ]
        with patch.object(m, "read_json", return_value={
            "code": 0, "data": {"count": 1, "rows": rows}
        }):
            with self.assertRaises(Stopped):
                m.already_started("sk_fake")
        with patch.object(m, "read_json", return_value={
            "code": 0, "data": {"count": 0, "rows": []}
        }):
            m.already_started("sk_fake")

    def test_support_required_negative_prompt_is_in_generation_body(self):
        body = m.build_body(m.SOURCE_CDN)
        self.assertEqual(body["negative_prompt"], "blurry, distorted, static")
        self.assertTrue(body["prompt"].strip())
        self.assertNotIn("lora", body)
        self.assertEqual(m.LABEL, "a2e-negative-prompt-one-video-30-20261105")
        self.assertEqual(m.JOURNAL_MARKER, "A2E_PRAGUE_NEGATIVE_PROMPT_FIX_PAID_START_20261105_ONCE")

    def test_missing_negative_prompt_stops_before_free_quote_and_paid_start(self):
        calls, fakes = run_mocks()
        original = m.build_body(m.SOURCE_CDN)
        original.pop("negative_prompt")
        with patch.object(m, "build_body", return_value=original):
            result, _ = self._execute(calls, fakes)
        self.assertEqual(result["status"], "STOPPED")
        self.assertIn("negative_prompt", result["note"])
        self.assertNotIn("FREE_QUOTE", calls)
        self.assertNotIn("JOURNAL", calls)
        self.assertNotIn("PAID_START", calls)

    def test_a2e_request_uses_same_exact_existing_image(self):
        body=m.build_body(m.SOURCE_CDN)
        self.assertEqual(body["image_url"], m.SOURCE_CDN)
        self.assertEqual(body["video_time"], 5)
        self.assertEqual(body["number_of_images"], 1)
        self.assertEqual(body["model_version"], "a2e")
        self.assertEqual(body["negative_prompt"], "blurry, distorted, static")
        self.assertFalse(body["auto_add_audio"])

if __name__ == "__main__":
    unittest.main()
