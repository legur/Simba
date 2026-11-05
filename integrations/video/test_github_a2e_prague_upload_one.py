"""Offline tests for 1-credit A2E presigned image upload with no video generation."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_a2e_prague_upload_one as upload


def event(label="a2e-upload-one-max1", number=8, author="legur"):
    return {
        "action": "labeled",
        "label": {"name": label},
        "repository": {"full_name": "legur/Simba"},
        "issue": {"number": number, "user": {"login": author}}
    }


class UploadOneTests(unittest.TestCase):
    def test_happy_path_only_one_credit_one_upload_zero_generations(self):
        order = []
        def fee(key):
            order.append("fee")
            return 1.0
        def jpg():
            order.append("source")
            return bytes.fromhex("ffd8") + b"a" * 1024
        def journal(amount):
            order.append("journal")
        def presign(key, size):
            order.append("presign")
            self.assertEqual(size, 1026)
            return "https://storage.example.com/upload?token=xyz", "https://cdn.example.com/image.jpg"
        def put(url, data):
            order.append("put")
        def verify(url):
            order.append("verify")
            return True
        def quote(url, key):
            order.append("quote")
            return 30.0
        with tempfile.TemporaryDirectory() as td, (
            patch.dict(upload.os.environ, {"A2E_API_KEY": "sk_test_fake_token_9876543210"})), (
            patch.object(upload, "api_get_pricing", side_effect=fee)), (
            patch.object(upload, "read_source_image", side_effect=jpg)), (
            patch.object(upload, "claim_once", side_effect=journal)), (
            patch.object(upload, "charged_presign", side_effect=presign)), (
            patch.object(upload, "upload_bytes", side_effect=put)), (
            patch.object(upload, "verify_staged_image", side_effect=verify)), (
            patch.object(upload, "quote_uploaded", side_effect=quote)):
            state = upload.run(event(), Path(td))
            self.assertEqual(state["status"], "IMAGE_UPLOADED_AND_VIDEO_QUOTED")
            self.assertFalse(state["generation_started"])
            self.assertEqual(state["quoted_video_credits"], 30)
            self.assertEqual(state["presign_fee_credits"], 1)
        self.assertEqual(order, ["fee", "source", "journal", "presign", "put", "verify", "quote"])

    def test_fee_above_cap_prevents_presign(self):
        calls = []
        with tempfile.TemporaryDirectory() as td, (
            patch.dict(upload.os.environ, {"A2E_API_KEY": "sk_fake_test_token_123456789"})), (
            patch.object(upload, "api_get_pricing", side_effect=upload.UploadStopped("R2 fee too high"))), (
            patch.object(upload, "charged_presign", side_effect=lambda *args: calls.append(1))):
            state = upload.run(event(), Path(td))
        self.assertEqual(state["status"], "STOPPED")
        self.assertEqual(calls, [])

    def test_reject_unapproved_owner_or_issue(self):
        for ev in (event(author="someoneelse"), event(number=9), event(label="a2e-generate-180")):
            with tempfile.TemporaryDirectory() as td:
                state = upload.run(ev, Path(td))
                self.assertEqual(state["status"], "STOPPED")

    def test_existing_upload_journal_prevents_charge(self):
        with patch.object(upload, "gh_request", side_effect=[
            [{"body": upload.JOURNAL_MARKER, "id": 1}]
        ]) as gh:
            with self.assertRaises(upload.UploadStopped):
                upload.claim_once(1)
        self.assertEqual(gh.call_count, 1)

    def test_journal_written_before_charge(self):
        methods = []
        def gh(method, body=None):
            methods.append(method)
            return [] if method == "GET" else {"id": 123}
        with patch.object(upload, "gh_request", side_effect=gh):
            upload.claim_once(1)
        self.assertEqual(methods, ["GET", "POST"])

    def test_presign_uses_documented_3days_image_bucket(self):
        calls = []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self, *a): return b'{"code":0,"data":{"uploadUrl":"https://storage.example.com/put","cdnUrl":"https://3days-apac.makefun.ai/media.jpg"}}'
        def fake_urlopen(req, timeout):
            calls.append(req)
            return Response()
        with patch.object(upload, "urlopen", side_effect=fake_urlopen):
            signed, cdn = upload.charged_presign("sk_dummy_fake_key_for_testing", 1026)
        self.assertEqual(len(calls), 1)
        payload = json.loads(calls[0].data)
        self.assertEqual(payload["bucket"], "3days-apac")
        self.assertNotIn("purpose", payload)
        self.assertEqual(payload["contentType"], "image/jpeg")
        self.assertEqual(payload["fileSize"], 1026)
        self.assertEqual(cdn, "https://3days-apac.makefun.ai/media.jpg")
        self.assertEqual(calls[0].get_method(), "POST")

    def test_staged_cdn_get_sends_explicit_support_user_agent(self):
        calls = []
        class Response:
            status = 206
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, count):
                return bytes.fromhex("ffd8") + b"x" * 1022
        def fake_open(req, timeout):
            calls.append(req)
            return Response()
        with patch.object(upload, "urlopen", side_effect=fake_open):
            self.assertTrue(upload.verify_staged_image(
                "https://3days-apac.downloadaivideo.com/test-image.jpg"))
        self.assertEqual(len(calls), 1)
        headers = {k.lower(): v for k, v in calls[0].headers.items()}
        self.assertEqual(calls[0].get_method(), "GET")
        self.assertEqual(headers.get("user-agent"), "Genjutsu")
        self.assertEqual(headers.get("range"), "bytes=0-1023")
        self.assertNotIn("authorization", headers)

    def test_signed_put_has_no_authorization(self):
        calls = []
        class FakeResponse:
            status = 204
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return "https://cdn.a2e.example/one-time?sig=abc"
        def urlopen(req, timeout):
            calls.append(req)
            return FakeResponse()
        with patch.object(upload, "urlopen", side_effect=urlopen):
            upload.upload_bytes("https://cdn.a2e.example/one-time?sig=abc", b"TEST")
        self.assertEqual(calls[0].get_method(), "PUT")
        self.assertFalse(any(k.lower() == "authorization" for k in calls[0].headers))
        self.assertEqual(calls[0].data, b"TEST")

    def test_validates_public_https_upload_urls(self):
        for u in ["http://example.com/file", "https://localhost/file", "file:///tmp/x"]:
            with self.assertRaises(upload.UploadStopped):
                upload.valid_storage_url(u)
        self.assertEqual(upload.valid_storage_url("https://storage.example.com/x"),
                         "https://storage.example.com/x")


if __name__ == "__main__":
    unittest.main()
