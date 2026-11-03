"""Regression tests: GitHub issue bridge must never initiate paid A2E calls."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_a2e_issue_bridge as bridge


def event(scenes=None, author="legur", label="a2e-quote", kind="simba_a2e_quote"):
    if scenes is None:
        scenes = [{"name": "Prague bridge", "image_url":
                   "https://static.wixstatic.com/media/7fd7b8_377e66bfa46b4a87a0223b02bec5d6f0~mv2.jpg",
                   "prompt": "Slow dolly in toward Charles Bridge, no text."}]
    return {
        "action": "labeled",
        "label": {"name": label},
        "issue": {"number": 22, "user": {"login": author},
                  "body": json.dumps({"kind": kind, "scenes": scenes})},
    }


class IssueBridgeSafetyTests(unittest.TestCase):
    def test_quote_only(self):
        calls = []
        def fake(call):
            calls.append(call)
            return {"ok": True, "quote": {"credits": 25}}
        report = bridge.run(event(), quote_fn=fake, gateway_token="x" * 28)
        self.assertIn("QUOTED_NO_CHARGE", report)
        self.assertIn("25 credits", report)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["action"], "quote")
        self.assertEqual(calls[0]["request_body"]["video_time"], 5)

    def test_never_trust_issue_actions_or_prices(self):
        scenes = [{"name": "winter", "image_url":
                   "https://static.wixstatic.com/media/7fd7b8_377e66bfa46b4a87a0223b02bec5d6f0~mv2.jpg",
                   "prompt": "snow", "action": "start", "confirm_credits": True,
                   "max_credits": 9999, "video_time": 500}]
        calls = []
        report = bridge.run(event(scenes), quote_fn=lambda body:
                            (calls.append(body) or {"quote": {"credits": 9}}),
                            gateway_token="x" * 28)
        self.assertIn("QUOTED_NO_CHARGE", report)
        self.assertEqual(calls[0]["action"], "quote")
        self.assertNotIn("confirm_credits", calls[0]["request_body"])
        self.assertNotIn("max_credits", calls[0]["request_body"])
        self.assertEqual(calls[0]["request_body"]["video_time"], 5)

    def test_owner_guard(self):
        self.assertIn("INVALID_REQUEST", bridge.run(event(author="intruder"),
                      gateway_token="x" * 28))
        self.assertIn("INVALID_REQUEST", bridge.run(event(label="a2e-start"),
                      gateway_token="x" * 28))

    def test_image_hostname_guard(self):
        for url in ["http://static.wixstatic.com/media/x.jpg",
                    "https://evil.example/media/x.jpg",
                    "https://static.wixstatic.com.evil.example/media/x.jpg",
                    "https://static.wixstatic.com@evil.example/media/x.jpg"]:
            e = event([{"name": "x", "image_url": url, "prompt": "snow"}])
            self.assertIn("INVALID_REQUEST", bridge.run(e, gateway_token="x" * 28))

    def test_missing_secret_no_calls(self):
        calls = []
        report = bridge.run(event(), quote_fn=lambda x: calls.append(x),
                            gateway_token="")
        self.assertIn("SETUP_REQUIRED", report)
        self.assertEqual(calls, [])

    def test_quote_failure_no_paid_operation(self):
        calls = []
        def fail(payload):
            calls.append(payload)
            raise bridge.BridgeError("unauthorized")
        report = bridge.run(event(), quote_fn=fail, gateway_token="x" * 28)
        self.assertIn("QUOTE_FAILED", report)
        self.assertNotIn("unauthorized", report)
        self.assertEqual([v["action"] for v in calls], ["quote"])

    def test_max_scenes(self):
        scene = {"name": "x", "image_url":
                 "https://static.wixstatic.com/media/safe.jpg", "prompt": "snow"}
        self.assertIn("INVALID_REQUEST", bridge.run(event([scene] * 7),
                      gateway_token="x" * 28))


if __name__ == "__main__":
    unittest.main()
