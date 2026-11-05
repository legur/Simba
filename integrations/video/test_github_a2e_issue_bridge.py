"""Safety regression tests for direct A2E quote-only GitHub integration."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_a2e_issue_bridge as bridge

GOOD_URL = "https://static.wixstatic.com/media/7fd7b8_377e66bfa46b4a87a0223b02bec5d6f0~mv2.jpg"

def event(scenes=None, author="legur", label="a2e-quote", kind="simba_a2e_quote"):
    if scenes is None:
        scenes = [{"name": "Prague bridge", "image_url": GOOD_URL,
                   "prompt": "Slow dolly toward Charles Bridge in falling snow."}]
    return {
        "action": "labeled",
        "label": {"name": label},
        "issue": {"number": 8, "user": {"login": author},
                  "body": json.dumps({"kind": kind, "scenes": scenes})},
    }

def success_quote(body, key):
    return {"code": 0, "data": {"available": True, "coins": 30,
                                "perOutputCoins": 30, "exact": True}}

class QuoteOnlySafetyTests(unittest.TestCase):
    def test_a2e_requires_two_nonempty_prompts_even_when_quote_is_exact(self):
        body = bridge.build_bodies(event())[0]
        self.assertEqual(body["negative_prompt"], "blurry, distorted, static")
        bridge.validate_generation_body(body)
        for invalid in (dict(body, negative_prompt=""), dict(body, negative_prompt="   "),
                        dict(body, prompt=""), {k: v for k, v in body.items()
                                                if k != "negative_prompt"}):
            with self.assertRaisesRegex(ValueError, "requires nonempty"):
                bridge.validate_generation_body(invalid)

    def test_a2e_rejects_lora_in_simba_locked_request(self):
        body = bridge.build_bodies(event())[0]
        with self.assertRaises(ValueError):
            bridge.validate_generation_body(dict(body, lora="some_other_model"))

    def test_uses_direct_quote_and_never_paid_start(self):
        calls = []
        def fn(body, key):
            calls.append((body, key))
            return success_quote(body, key)
        report = bridge.run(event(), quote_fn=fn, api_key="sk_test_fake_token_for_unit_tests")
        self.assertIn("QUOTED_NO_CHARGE", report)
        self.assertIn("30 credits", report)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0]["video_time"], 5)
        self.assertEqual(calls[0][0]["model_version"], "a2e")
        self.assertEqual(calls[0][0]["negative_prompt"], "blurry, distorted, static")
        self.assertEqual(calls[0][0]["number_of_images"], 1)
        self.assertNotIn("start", repr(calls[0][0]))
        self.assertEqual(bridge.A2E_QUOTE_URL, "https://api.a2e.ai/v1/generation/quote")

    def test_untrusted_paid_fields_ignored(self):
        scene = {"name": "Prague", "image_url": GOOD_URL, "prompt": "snow",
                 "action": "start", "unlimited": True, "video_time": 60,
                 "max_credits": 5000, "auto_add_audio": True}
        calls = []
        def fn(body, token):
            calls.append(body)
            return success_quote(body, token)
        report = bridge.run(event([scene]), quote_fn=fn,
                            api_key="sk_test_fake_token_for_unit_tests")
        self.assertIn("QUOTED_NO_CHARGE", report)
        self.assertEqual(calls[0]["video_time"], 5)
        self.assertFalse(calls[0]["auto_add_audio"])
        for forbidden in ["action", "unlimited", "max_credits", "confirm_credits"]:
            self.assertNotIn(forbidden, calls[0])

    def test_owner_gate(self):
        self.assertIn("INVALID_REQUEST", bridge.run(event(author="someoneelse"),
                      api_key="sk_test_fake_token_for_unit_tests"))
        self.assertIn("INVALID_REQUEST", bridge.run(event(label="a2e-start"),
                      api_key="sk_test_fake_token_for_unit_tests"))

    def test_hostname_and_url_safety(self):
        bad_urls = [
            "http://static.wixstatic.com/media/x.jpg",
            "https://evil.example/media/x.jpg",
            "https://static.wixstatic.com.evil.example/media/x.jpg",
            "https://static.wixstatic.com@evil.example/media/x.jpg",
            "https://static.wixstatic.com/media/x.jpg?token=x",
            "https://static.wixstatic.com/private/x.jpg"
        ]
        for url in bad_urls:
            report = bridge.run(event([{"name": "x", "image_url": url,
                                       "prompt": "snow"}]),
                                api_key="sk_test_fake_token_for_unit_tests")
            self.assertIn("INVALID_REQUEST", report, msg=url)

    def test_no_key_no_request(self):
        calls = []
        report = bridge.run(event(), quote_fn=lambda x, y: calls.append((x,y)),
                            api_key="")
        self.assertIn("SETUP_REQUIRED", report)
        self.assertEqual(calls, [])

    def test_quote_failure_redacted_and_does_not_retry(self):
        calls = []
        def fail(body, key):
            calls.append(body)
            raise bridge.QuoteError("sk_NEVER_PRINT_THIS")
        report = bridge.run(event(), quote_fn=fail,
                            api_key="sk_test_fake_token_for_unit_tests")
        self.assertIn("QUOTE_FAILED", report)
        self.assertNotIn("sk_NEVER_PRINT_THIS", report)
        self.assertEqual(len(calls), 1)

    def test_credits_require_exact_available_response(self):
        variants = [
            {"code": 0, "data": {"available": False, "coins": 30, "exact": True}},
            {"code": 0, "data": {"available": True, "coins": 30, "exact": False}},
            {"code": 999, "data": {"available": True, "coins": 30, "exact": True}},
            {"code": 0, "data": {"available": True, "coins": None, "exact": True}},
            {"code": 0, "data": {"available": True, "coins": -1, "exact": True}},
        ]
        for value in variants:
            report = bridge.run(event(), quote_fn=lambda body, key: value,
                                api_key="sk_test_fake_token_for_unit_tests")
            self.assertIn("QUOTE_FAILED", report)

    def test_six_scene_limit(self):
        scene = {"name": "x", "image_url": GOOD_URL, "prompt": "snow"}
        self.assertIn("INVALID_REQUEST", bridge.run(event([scene] * 7),
                      api_key="sk_test_fake_token_for_unit_tests"))

    def test_endpoint_payload_contract(self):
        calls = []
        class FakeResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self): return b'{"code":0,"data":{"available":true,"coins":35,"exact":true}}'
        # request_quote delegates to urllib. Verify exact endpoint and JSON request.
        real_urlopen = bridge.urlopen
        try:
            def stub(request, timeout=None):
                calls.append(request)
                return FakeResponse()
            bridge.urlopen = stub
            value = bridge.request_quote(
                {"name":"Prague","image_url":GOOD_URL,"prompt":"snow",
                 "model_version":"a2e","video_time":5},
                 "sk_fake_test_token")
        finally:
            bridge.urlopen = real_urlopen
        self.assertEqual(value["data"]["coins"], 35)
        self.assertEqual(calls[0].full_url, bridge.A2E_QUOTE_URL)
        payload = json.loads(calls[0].data)
        self.assertEqual(payload["endpoint"], "/api/v1/userImage2Video/start")
        self.assertEqual(payload["requestBody"]["video_time"], 5)
        self.assertEqual(calls[0].get_method(), "POST")


if __name__ == "__main__":
    unittest.main()
