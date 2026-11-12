"""Offline tests for the native-ChatGPT Rafael package adapter."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import chatgpt_rafael as raf
import handoff


class ChatGPTRafaelTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.images = self.root / "chatgpt-rendered-images"
        for i in range(1, 4):
            folder = self.images / f"option_{i}"
            folder.mkdir(parents=True)
            for j in range(1, 4):
                # Distinct files and actual RGB pixel data, not fake file paths.
                im = Image.new("RGB", (820, 1250), (i*40, j*50, i*j*15))
                im.save(folder / f"scene_{j}.png")
        self.archive = self.root / "private-archive-upload-pending.zip"
        self.source = self.root / "SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/approved.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("STATUS: APPROVED\n## APPROVED_TEXT\n"
                               + "Исторический город приглашает на прогулку. " * 8)
        self.project = {
            "schema_version": 1, "id": "demo-chatgpt", "title": "ChatGPT storyboard smoke",
            "stage": "STORYBOARD_PENDING", "next_action": "Create three illustrated storyboards",
            "updated_at": "2026-11-10", "aliases": [], "references": [],
            "sources": [{"path": self.source.relative_to(self.root).as_posix(),
                        "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()}],
            "assets": [{"id": "approved-script", "kind": "script", "state": "available",
                        "url": "https://drive.google.com/file/d/approved-private-script/view",
                        "evidence": "Leo selected variant 2"}],
            "approvals": {"editorial": "pending", "publication": "pending"},
            "working_asset_id": None, "approved_asset_id": None,
        }
        self.project["stage_handoffs"] = {
            "script": {"input_fingerprint": handoff.source_fingerprint(self.project),
                       "state": "approved", "approval_evidence": "Leo selected text 2",
                       "options_presented": 3, "options_evidence": "private draft",
                       "selected_option": 2, "assets": ["approved-script"]}
        }
        self.path = self.root / "campaigns/demo-chatgpt/project.json"
        self.path.parent.mkdir(parents=True)
        self.save()
        self.provenance = {"source": "CHATGPT_IMAGE_TOOL",
                           "session_evidence": "test-only: image tool generation receipts"}

    def save(self):
        self.path.write_text(json.dumps(self.project, ensure_ascii=False))

    def test_validated_handoff_and_three_prompt_concepts(self):
        project, receipt = raf.validated_stage(self.root, "demo-chatgpt")
        self.assertEqual(project["id"], "demo-chatgpt")
        self.assertEqual(len(receipt), 64)
        concepts = raf.prompt_set()
        self.assertEqual(len(concepts), 3)
        self.assertEqual(len({c["visual_approach"] for c in concepts}), 3)
        self.assertTrue(all("ChatGPT native" in c["generator"] for c in concepts))

    def test_real_frame_zip_previews_and_unapproved_state(self):
        result = raf.package(self.root, "demo-chatgpt", self.images, self.archive,
                             provenance=self.provenance)
        self.assertEqual(result["verified_distinct_input_images"], 9)
        self.assertEqual(result["verified_previews"], 3)
        self.assertFalse(result["approved"])
        self.assertFalse(result["archive_verified_on_private_drive"])
        self.assertFalse(result["published"])
        self.assertEqual(result["paid_api_calls"], 0)
        with zipfile.ZipFile(self.archive) as z:
            manifest = json.loads(z.read("manifest.json"))
            self.assertEqual(manifest["selected_script_option"], 2)
            self.assertEqual(len(manifest["options"]), 3)
            self.assertEqual(len([n for n in z.namelist() if n.endswith("scene_1.jpg")]), 3)
            self.assertEqual(len([n for n in z.namelist() if n.endswith("preview.png")]), 3)
            self.assertEqual(sum(len(opt["scenes"]) for opt in manifest["options"]), 9)
        with self.assertRaises(raf.RafaelError):
            raf.package(self.root, "demo-chatgpt", self.images, self.archive,
                        provenance=self.provenance)

    def test_missing_or_duplicate_real_images_block(self):
        self.images.joinpath("option_3/scene_3.png").unlink()
        with self.assertRaises(raf.RafaelError):
            raf.package(self.root, "demo-chatgpt", self.images, self.archive,
                        provenance=self.provenance)
        self.assertFalse(self.archive.exists())
        self.images.joinpath("option_3/scene_3.png").write_bytes(
            self.images.joinpath("option_1/scene_1.png").read_bytes())
        with self.assertRaises(raf.RafaelError):
            raf.package(self.root, "demo-chatgpt", self.images, self.archive,
                        provenance=self.provenance)

    def test_no_unapproved_source_or_forged_provenance(self):
        with self.assertRaises(raf.RafaelError):
            raf.package(self.root, "demo-chatgpt", self.images, self.archive,
                        provenance={"source": "WIKIMEDIA", "session_evidence": "pretend"})
        self.project["stage_handoffs"]["script"]["selected_option"] = None
        self.save()
        with self.assertRaises(raf.RafaelError):
            raf.validated_stage(self.root, "demo-chatgpt")
        self.assertFalse(self.archive.exists())

    def test_stale_source_blocks(self):
        self.source.write_text(self.source.read_text() + "text changed")
        with self.assertRaises(raf.RafaelError):
            raf.validated_stage(self.root, "demo-chatgpt")

    def test_prepare_requires_no_image_provider_or_paid_calls(self):
        output = io.StringIO()
        from unittest.mock import patch
        with patch("sys.stdout", output):
            status = raf.main(["--root", str(self.root),
                               "--project", "demo-chatgpt", "--prepare-only"])
        self.assertEqual(status, 0)
        document = json.loads(output.getvalue())
        self.assertEqual(document["status"], "CHATGPT_RENDER_REQUIRED")
        self.assertFalse(document["ready_for_a2e"])


if __name__ == "__main__":
    unittest.main()
