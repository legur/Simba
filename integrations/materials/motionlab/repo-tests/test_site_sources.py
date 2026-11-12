"""Preproduction Motion Lab source inventory: all published static pages and their local assets."""
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("index.html", "text.html", "subtitles.html", "camera.html", "storyboard.html", "creative.html")
STYLES = ("styles.css", "text.css", "subtitles.css", "camera.css", "storyboard.css", "creative.css")
SCRIPTS = ("app.js", "transitions.js", "text.js", "subtitles.js", "camera.js", "storyboard.js", "motionlab_drive_config.js", "motionlab_drive_bridge.js", "visual_editor.js", "scene_pages.js", "creative.js")


class LocalReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in ("link", "script", "img", "a"):
            url = values.get("href") if tag in ("link", "a") else values.get("src")
            if url:
                self.refs.append(url)


class MotionLabSiteIntegrityTests(unittest.TestCase):
    def test_exact_expected_files_are_present(self):
        for name in (*PAGES, *STYLES, *SCRIPTS):
            with self.subTest(file=name):
                self.assertTrue((ROOT / name).is_file(), name)

    def test_all_local_html_references_resolve(self):
        for name in PAGES:
            parser = LocalReferences()
            parser.feed((ROOT / name).read_text(encoding="utf-8"))
            for reference in parser.refs:
                parsed = urlsplit(reference)
                if parsed.scheme or parsed.netloc or reference.startswith(("#", "//", "mailto:")):
                    continue
                destination = (ROOT / parsed.path).resolve()
                with self.subTest(page=name, href=reference):
                    self.assertTrue(destination.is_relative_to(ROOT), "Path escapes source root")
                    self.assertTrue(destination.is_file(), f"Missing {reference} in {name}")

    def test_preproduction_creative_catalog_contract(self):
        js = (ROOT / "creative.js").read_text(encoding="utf-8")
        for marker in ("const OBJECTS=", "const ROUTES=", "const MUSIC=",
                       "const TEMPLATES=", "DRAFT_NOT_DELIVERED",
                       "rendering_authorized:false", "publishing_authorized:false"):
            with self.subTest(marker=marker):
                self.assertIn(marker, js)

    def test_storyboard_exposes_runtime_handoff_without_fake_approval(self):
        js = (ROOT / "storyboard.js").read_text(encoding="utf-8")
        for keyword in ("SIMBA_MOTIONLAB_READY", "SIMBA_MOTIONLAB_START",
                        "SIMBA_MOTIONLAB_SELECTION", "SIMBA_MOTIONLAB_ACK"):
            with self.subTest(keyword=keyword):
                self.assertIn(keyword, js)


if __name__ == "__main__":
    unittest.main()
