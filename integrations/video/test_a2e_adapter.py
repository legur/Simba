"""Offline tests for Simba's A2E adapter; never contacts Wix or bills A2E."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import importlib.util


MODULE = Path(__file__).with_name("a2e_adapter.py")
spec = importlib.util.spec_from_file_location("simba_a2e", MODULE)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class A2EAdapterTests(unittest.TestCase):
    def test_quote_body_image_and_model(self):
        a = argparse.Namespace(image_url="https://images.example.com/a.jpg",
                               image_file=None, prompt="Gentle camera push", name="Scene 1")
        self.assertEqual(adapter.quote_body(a)["video_time"], 5)
        self.assertEqual(adapter.quote_body(a)["model_version"], "a2e")

    def test_url_safety(self):
        for url in ("http://images.example.com/a.png",
                    "https://localhost/video.mp4", "https://127.0.0.1/a.mp4",
                    "https://user:pass@media.example.com/a.mp4"):
            with self.subTest(url=url), self.assertRaises(adapter.BridgeError):
                adapter.safe_video_url(url)
        adapter.safe_video_url("https://cdn.example.com/a.mp4")

    def test_payment_limit_blocks_before_gateway(self):
        with tempfile.TemporaryDirectory() as td:
            q = Path(td) / "scene.quote.json"
            q.write_text(json.dumps({"request_body": {"name": "test"},
                                     "quote": {"credits": 11}}), encoding="utf-8")
            with patch.object(adapter, "call_gateway") as gateway:
                with self.assertRaises(adapter.BridgeError):
                    adapter.start_once(q, 10)
                gateway.assert_not_called()

    def test_unknown_paid_outcome_does_not_retry(self):
        with tempfile.TemporaryDirectory() as td:
            q = Path(td) / "scene.quote.json"
            q.write_text(json.dumps({"request_body": {"name": "test"},
                                     "quote": {"credits": 2}}), encoding="utf-8")
            with patch.object(adapter, "call_gateway", side_effect=adapter.BridgeError("timeout")) as gw:
                with self.assertRaises(adapter.BridgeError):
                    adapter.start_once(q, 5)
                with self.assertRaises(adapter.BridgeError):
                    adapter.start_once(q, 5)
                gw.assert_called_once()

    def test_missing_secret_prevents_request(self):
        with patch.dict("os.environ", {"SIMBA_A2E_GATEWAY_TOKEN": ""}):
            with self.assertRaises(adapter.BridgeError):
                adapter.token()


if __name__ == "__main__":
    unittest.main()
