"""Offline checks for the fail-closed GitHub -> Wix static site deployer."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from deploy_static import (
    ROOT, SITE_FILES, SITE_ID, SITE_URL,
    build_bundle, check_remote_files, collect_site_files, make_auth_header,
)


class WixDeploymentSafety(unittest.TestCase):
    def test_bundle_contains_only_the_twenty_one_public_files(self):
        with tempfile.TemporaryDirectory() as path:
            bundle = Path(path) / "site.zip"
            manifest = build_bundle(bundle)
            self.assertEqual(manifest["site_id"], SITE_ID)
            self.assertEqual(len(manifest["files"]), 21)
            self.assertLess(bundle.stat().st_size, 20 * 1024 * 1024)
            with zipfile.ZipFile(bundle) as z:
                self.assertEqual(set(z.namelist()), set(SITE_FILES))
                self.assertTrue(z.read("index.html").startswith(b"<!doctype html"))
                self.assertNotIn("motionlab_host_adapter.js", z.namelist())
                self.assertNotIn("README.md", z.namelist())

    def test_remote_inventory_must_match_exactly(self):
        valid = {"files": [{"path": s} for s in SITE_FILES], "revision": "abc"}
        check_remote_files(valid)
        with self.assertRaisesRegex(ValueError, "diverged"):
            check_remote_files({"files": [{"path": s} for s in SITE_FILES[:-1]]})
        with self.assertRaisesRegex(ValueError, "diverged"):
            check_remote_files({"files": valid["files"] + [{"path": "private/data.json"}]})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            check_remote_files({"files": valid["files"] + [{"path": "index.html"}]})
        with self.assertRaises(ValueError):
            check_remote_files({})

    def test_missing_file_is_blocker(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            for filename in SITE_FILES[:-1]:
                (root / filename).write_text("safe content", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Missing"):
                collect_site_files(root)

    def test_local_html_link_must_be_in_allowlist(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            for filename in SITE_FILES:
                (root / filename).write_text("safe content", encoding="utf-8")
            (root / "index.html").write_text(
                '<!doctype html><a href="private/report.md">Oops</a>', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "absent"):
                collect_site_files(root)

    def test_auth_header_never_accepts_blank_or_multiple_lines(self):
        self.assertEqual(make_auth_header("some_token"), "some_token")
        self.assertEqual(make_auth_header(" WixSecret "), "WixSecret")
        for invalid in ("", "  ", "abc\nBearer evil"):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    make_auth_header(invalid)


if __name__ == "__main__":
    unittest.main()
