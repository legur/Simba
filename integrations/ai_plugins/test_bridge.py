import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import bridge


class BridgeTests(unittest.TestCase):
    def package(self):
        return {"content": "Цена и условия без изменений", "channelIds": [12],
                "textStatus": "APPROVED_TEXT"}

    def test_dry_run_never_calls_network(self):
        with patch.object(bridge, "api_request") as api:
            result = bridge.create_draft(self.package())
        api.assert_not_called()
        self.assertEqual(result["request"]["status"], "draft")
        self.assertEqual(result["request"]["content"], self.package()["content"])

    def test_send_creates_only_draft(self):
        with patch.object(bridge, "api_request", return_value={"id": 77}) as api:
            result = bridge.create_draft(self.package(), send=True)
        self.assertEqual(result["status"], "DRAFT_CREATED")
        self.assertEqual(api.call_args.args[0], "/api/posts")
        self.assertEqual(api.call_args.args[1]["status"], "draft")

    def test_rejects_scheduled_and_published(self):
        for status in ["scheduled", "published", "publish_now"]:
            with self.subTest(status=status), self.assertRaises(bridge.IntegrationError):
                bridge.draft_payload(dict(self.package(), status=status))

    def test_rejects_scheduling_fields(self):
        for field in ["scheduledAt", "scheduled_at", "repeatSchedule", "publishWhenApproved",
                      "autoPlugEnabled", "autoRepostEnabled", "publishNow"]:
            with self.subTest(field=field), self.assertRaises(bridge.IntegrationError):
                bridge.draft_payload(dict(self.package(), **{field: True}))

    def test_unapproved_text_blocked(self):
        for state in [None, "TEXT_READY_FOR_LEO", "DRAFT"]:
            with self.subTest(state=state), self.assertRaises(bridge.IntegrationError):
                bridge.draft_payload(dict(self.package(), textStatus=state))

    def test_media_requires_final_visual(self):
        package = dict(self.package(), mediaFiles=[9])
        with self.assertRaises(bridge.IntegrationError):
            bridge.draft_payload(package)
        package["visualStatus"] = "FINAL_VISUAL_READY"
        self.assertEqual(bridge.draft_payload(package)["mediaFiles"], [9])

    def test_invalid_channel_and_media_ids(self):
        for ids in [[], [True], [-1], ["1"], None]:
            with self.subTest(ids=ids), self.assertRaises(bridge.IntegrationError):
                bridge.draft_payload(dict(self.package(), channelIds=ids))
        with self.assertRaises(bridge.IntegrationError):
            bridge.draft_payload(dict(self.package(), mediaFiles=[True]))

    def test_unknown_fields_not_forwarded(self):
        result = bridge.draft_payload(dict(self.package(), providerSecret="hidden"))
        self.assertNotIn("providerSecret", result)
        self.assertNotIn("textStatus", result)

    def test_missing_credentials_block_before_network(self):
        with patch.dict(bridge.os.environ, {}, clear=True), patch.object(bridge.urllib.request, "build_opener") as opener:
            with self.assertRaisesRegex(bridge.IntegrationError, "NOT_CONFIGURED"):
                bridge.api_request("/api/channels")
        opener.assert_not_called()

    def test_missing_scanner_is_explicit(self):
        with patch.object(bridge.shutil, "which", return_value=None):
            with self.assertRaisesRegex(bridge.IntegrationError, "SCANNER_UNAVAILABLE"):
                bridge.scan("not-used.txt")

    def test_scan_preserves_findings_without_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.txt"
            path.write_text("Данный текст", encoding="utf-8")
            with patch.object(bridge.shutil, "which", return_value="/bin/ru-humanizer"), patch.object(
                bridge.subprocess, "run", return_value=Mock(returncode=1, stdout='{"findings": ["данный"]}')
            ) as run:
                result = bridge.scan(path)
            self.assertEqual(result["scanner_exit_code"], 1)
            self.assertFalse(result["automatic_rewrite"])
            self.assertIn("--json", run.call_args.args[0])
            self.assertEqual(path.read_text(encoding="utf-8"), "Данный текст")

    def test_invalid_scanner_report_is_failure(self):
        with tempfile.NamedTemporaryFile() as source:
            with patch.object(bridge.shutil, "which", return_value="scanner"), patch.object(
                bridge.subprocess, "run", return_value=Mock(returncode=2, stdout="traceback")
            ):
                with self.assertRaisesRegex(bridge.IntegrationError, "INVALID_REPORT"):
                    bridge.scan(source.name)

    def test_redirects_disabled(self):
        handler = bridge.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "redirect", {}, "https://example.org"))

    def test_extraction_returns_source_hash_and_unverified_status(self):
        import hashlib
        import sys
        import types
        document = Mock(content="Таблица", tables=[Mock(markdown="|Цена|", cells=[["Цена"]])])
        async def extract(*args):
            return Mock(summary=Mock(errors=0), results=[document])
        module = types.SimpleNamespace(ExtractInput=Mock(), ExtractionConfig=Mock(), OcrConfig=Mock(), extract=extract)
        with tempfile.NamedTemporaryFile() as source:
            source.write(b"source"); source.flush()
            with patch.dict(sys.modules, {"xberg": module}), patch.object(bridge.importlib.metadata, "version", return_value="test"):
                result = asyncio.run(bridge.extract_document(source.name))
        self.assertEqual(result["sha256"], hashlib.sha256(b"source").hexdigest())
        self.assertEqual(result["status"], "EXTRACTED_UNVERIFIED")
        self.assertEqual(result["documents"][0]["tables"][0]["cells"], [["Цена"]])


if __name__ == "__main__":
    unittest.main()
