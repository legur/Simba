"""Offline no-duplicate/no-retry budget tests for remaining five A2E Prague scenes."""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_a2e_prague_full_reel_five as m


def event(label=m.LABEL):
    scenes = [
        {"name": name, "image_url": url, "prompt": "Prague cinematic moving camera " + name}
        for name, url in zip(m.SCENE_NAMES, m.EXPECTED_URLS)
    ]
    return {
        "action": "labeled", "label": {"name": label},
        "repository": {"full_name": "legur/Simba"},
        "issue": {"number": 8, "user": {"login": "legur"},
                  "body": json.dumps({"kind": "simba_a2e_quote", "scenes": scenes})},
    }


def helpers(stage_fee=1.0, quote=30, cdn_ok=True, rejected_at=None):
    calls = []

    def track(label, result=None):
        def fn(*args, **kwargs):
            calls.append((label, args, kwargs))
            if isinstance(result, Exception):
                raise result
            if callable(result):
                return result(*args, **kwargs)
            return result
        return fn

    fakes = {
        "api_get_pricing": track("price", stage_fee),
        "ensure_no_duplicate_tasks": track("history"),
        "read_source_jpeg": track("source", bytes.fromhex("ffd8") + b"j" * 2048),
        "exact_quote": track("quote", quote),
        "download_video": track("first_video", lambda url, target: target.write_bytes(b"X" * 2000)),
        "journal": track("journal"),
        "charged_presign": track("presign", (
            "https://signed.storage.example.com/put?sig=fake",
            "https://3days-apac.downloadaivideo.com/test.jpg",
        )),
        "upload_bytes": track("put"),
        "verify_staged_image": track("cdn_get", cdn_ok),
        "a2e_start": track("start", lambda body, key: {
            "code": 0,
            "data": {"_id": "507f1f77bcf86cd799439011"}
        }),
        "poll_to_completion": track(
            "poll", lambda task_id, key, target, pause=None: target.write_bytes(b"Y" * 2000)
        ),
    }
    return calls, fakes


class FullPragueTests(unittest.TestCase):
    def execute(self, calls, fakes, *, ev=None, cap=155):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(m.os.environ, {"A2E_API_KEY": "sk_test_dummy_example_2026"}), ExitStack() as stack:
                for name, fn in fakes.items():
                    stack.enter_context(patch.object(m, name, side_effect=fn))
                result = m.run(ev or event(), Path(td), max_new=cap, pause=lambda _: None)
                files = sorted(p.name for p in Path(td).glob("scene_*.mp4"))
                report = (Path(td) / "report.md").read_text()
                return result, files, report

    def test_five_shots_six_mp4_total_within_155(self):
        calls, fakes = helpers()
        result, files, report = self.execute(calls, fakes)
        self.assertEqual(result["status"], "ALL_SIX_CLIPS_READY")
        self.assertEqual(len(result["completed"]), 5)
        self.assertEqual(files, ["scene_01.mp4", "scene_02.mp4", "scene_03.mp4",
                                 "scene_04.mp4", "scene_05.mp4", "scene_06.mp4"])
        self.assertEqual(result["staging_spend_credits"], 5)
        self.assertEqual(result["video_spend_estimate_credits"], 150)
        names = [x[0] for x in calls]
        self.assertEqual(names.count("presign"), 5)
        self.assertEqual(names.count("start"), 5)
        self.assertEqual(names.count("journal"), 10)
        self.assertEqual(names.count("quote"), 10)
        self.assertEqual(names.count("poll"), 5)
        self.assertEqual(names.count("first_video"), 1)
        self.assertLess(names.index("journal"), names.index("presign"))
        self.assertLess(names.index("cdn_get"), names.index("start"))
        self.assertIn("ALL_SIX_CLIPS_READY", report)

    def test_price_above_ceiling_blocks_all_paid_calls(self):
        calls, fakes = helpers(quote=31)
        result, _, _ = self.execute(calls, fakes)
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual(sum(x[0] == "presign" for x in calls), 0)
        self.assertEqual(sum(x[0] == "start" for x in calls), 0)

    def test_presign_above_one_credit_blocks_all_paid_calls(self):
        calls, fakes = helpers(stage_fee=1.01)
        result, _, _ = self.execute(calls, fakes)
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual(sum(x[0] == "presign" for x in calls), 0)
        self.assertEqual(sum(x[0] == "start" for x in calls), 0)

    def test_cdn_error_stops_before_any_video_start(self):
        calls, fakes = helpers(cdn_ok=False)
        result, files, report = self.execute(calls, fakes)
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual(result["staging_spend_credits"], 1)
        self.assertEqual(len(files), 1)
        self.assertEqual(sum(x[0] == "start" for x in calls), 0)
        self.assertEqual(sum(x[0] == "presign" for x in calls), 1)

    def test_paid_400_stops_after_exactly_one_start(self):
        calls, fakes = helpers()
        fakes["a2e_start"] = lambda body, key: (
            calls.append(("start", (), {})) or
            (_ for _ in ()).throw(m.StopGeneration("A2E_START_HTTP_400_CODE_400")))
        result, files, _ = self.execute(calls, fakes)
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual(len(files), 1)
        self.assertEqual(sum(x[0] == "start" for x in calls), 1)
        self.assertEqual(sum(x[0] == "presign" for x in calls), 1)
        self.assertEqual(result["video_spend_estimate_credits"], 30)

    def test_wrong_label_or_cap_no_spend(self):
        for ev, cap in ((event(label="old-unused-label"), 155), (event(), 156)):
            calls, fakes = helpers()
            result, files, report = self.execute(calls, fakes, ev=ev, cap=cap)
            self.assertEqual(result["status"], "STOPPED")
            self.assertEqual(len(calls), 0)
            self.assertEqual(files, [])

    def test_approved_pinned_names_urls_and_prompts(self):
        bodies = m.validate_event(event(), 155)
        self.assertEqual([x["image_url"] for x in bodies], m.EXPECTED_URLS)
        self.assertEqual([x["name"] for x in bodies], m.SCENE_NAMES)
        self.assertTrue(all(x["negative_prompt"] == "blurry, distorted, static" for x in bodies))
        self.assertTrue(all(x["video_time"] == 5 and x["auto_add_audio"] is False for x in bodies))

    def test_reconciliation_rejects_prior_scene_2_task(self):
        ev = event()
        bodies = m.validate_event(ev, 155)
        fake_reply = {
            "code": 0,
            "data": {"count": 1, "rows": [{"_id": "old", "name": bodies[1]["name"]}]}
        }
        with patch.object(m, "read_json", return_value=fake_reply):
            with self.assertRaisesRegex(m.Stopped, "previously submitted"):
                m.ensure_no_duplicate_tasks("sk_dummy", bodies)

    def test_exact_quote_requires_negative_prompt(self):
        body = m.validate_event(event(), 155)[1]
        body.pop("negative_prompt")
        with patch.object(m, "request_quote", side_effect=AssertionError("No free quote should be attempted")):
            with self.assertRaises(m.Stopped):
                m.exact_quote(body, "sk_dummy")

if __name__ == "__main__":
    unittest.main()
