"""Offline tests for the standalone-script approval gate. No provider calls."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO))
import make_video


APPROVED_SCRIPT = """STATUS: APPROVED_SCRIPT
APPROVAL_EVIDENCE: Leo approved this exact script revision
SOURCE_REFERENCE: editorial-brief-2026-11-17

## APPROVED_SCRIPT
Приезжаем во Вьетнам на 10 дней.
"""


class StandaloneScriptSourceTests(unittest.TestCase):
    def test_parse_requires_exact_script_approval_and_provenance(self):
        body, approved = make_video.parse_approved_script(APPROVED_SCRIPT)
        self.assertTrue(approved)
        self.assertIn("10 дней", body)
        for field in ("STATUS: APPROVED_SCRIPT", "APPROVAL_EVIDENCE:", "SOURCE_REFERENCE:"):
            draft = APPROVED_SCRIPT.replace(field, "REMOVED_")
            _, approved = make_video.parse_approved_script(draft)
            self.assertFalse(approved, field)

    def test_rejects_post_approval_as_script_approval(self):
        script = APPROVED_SCRIPT.replace("STATUS: APPROVED_SCRIPT", "STATUS: APPROVED")
        self.assertFalse(make_video.parse_approved_script(script)[1])

    def test_approved_script_can_be_source_for_renderer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "script.md").write_text(APPROVED_SCRIPT, encoding="utf-8")
            with patch.object(make_video, "REPO", root):
                source, approved = make_video.approved_text({"sourceScript": "script.md"})
            self.assertTrue(approved)
            self.assertEqual(make_video.fact_gate({"scenes": [{"lines": [{"text": "10 дней"}]}], "end": {"brand": "Simba by Bon Tours"}}, source), "PASS")

    def test_unapproved_script_fails_closed_except_explicit_draft(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "script.md").write_text(APPROVED_SCRIPT.replace(
                "STATUS: APPROVED_SCRIPT", "STATUS: WORKING"), encoding="utf-8")
            with patch.object(make_video, "REPO", root):
                with self.assertRaises(make_video.Stop):
                    make_video.approved_text({"sourceScript": "script.md"})
                _, approved = make_video.approved_text({"sourceScript": "script.md"}, draft=True)
                self.assertFalse(approved)

    def test_source_fields_mutually_exclusive_and_paths_sandboxed(self):
        with tempfile.TemporaryDirectory() as folder:
            job = Path(folder)
            (job / "photo.jpg").write_bytes(b"fixture")
            base = {"packageId": "standalone", "scenes": [{"image": "photo.jpg", "lines": []}]}

            def load(extra):
                (job / "video-spec.json").write_text(json.dumps({**base, **extra}), encoding="utf-8")
                with patch("music_input.validate_music", return_value=None):
                    return make_video.load_spec(job)

            self.assertEqual(load({"sourceScript": "script.md"})["sourceScript"], "script.md")
            self.assertEqual(load({"sourcePost": "post.md"})["sourcePost"], "post.md")
            with self.assertRaisesRegex(make_video.Stop, "exactly one"):
                load({"sourcePost": "post.md", "sourceScript": "script.md"})
            with self.assertRaisesRegex(make_video.Stop, "exactly one"):
                load({})
            with self.assertRaisesRegex(make_video.Stop, "inside the repository"):
                load({"sourceScript": "../script.md"})


if __name__ == "__main__":
    unittest.main()
