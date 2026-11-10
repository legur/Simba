"""Rafael private archive: true file validation, Drive checksum/readback, no publication."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import rafael_archive as archive


def make_zip(root: Path) -> Path:
    from PIL import Image, ImageDraw
    dest = root / "package.zip"
    files = {}
    options = []
    for option in (1, 2, 3):
        scenes = []
        for scene in (1, 2, 3):
            img = Image.new("RGB", (720, 1280), (option * 39, scene * 44, 80))
            draw = ImageDraw.Draw(img)
            draw.ellipse((scene * 32, 100, 400, 540), fill=(20, 160, option * 44))
            mem = io.BytesIO()
            img.save(mem, format="JPEG", quality=86)
            name = f"option_{option}/scene_{scene}.jpg"
            files[name] = mem.getvalue()
            scenes.append({"scene": scene, "image": name,
                           "image_sha256": archive.digest(files[name])})
        img = Image.new("RGB", (1100, 740), (option*48, 76, 100))
        board = io.BytesIO()
        img.save(board, "PNG")
        name = f"option_{option}/preview.png"
        files[name] = board.getvalue()
        options.append({"option": option, "preview": name,
                        "preview_sha256": archive.digest(board.getvalue()),
                        "scenes": scenes})
    manifest = {
        "schema_version": 1, "project_id": "smoke-chatgpt-rafael",
        "stage": "storyboard", "input_receipt": "f"*64,
        "status": "STORYBOARD_OPTIONS_NEED_LEO", "approval_recorded": False,
        "published": False, "archive_verified": False,
        "generation_evidence": {"source": "CHATGPT_IMAGE_TOOL", "session_evidence": "synthetic_test_only"},
        "options": options,
    }
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False).encode()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            z.writestr(k, v)
    return dest


class Request:
    def __init__(self, result):
        self.result = result
    def execute(self, num_retries=0):
        return self.result


class FakeDrive:
    def __init__(self, data=None, *, broad=False):
        self.data = data
        self.file_id = "test-private-id"
        self.broad = broad
        self.folder = archive.ARCHIVE_FOLDER
        self.rows = {} if data is None else {"id": self.file_id}
        self.calls = 0
    def files(self):
        return self
    def get(self, fileId, fields):
        if fileId == self.folder:
            perms = [{"type":"user","role":"owner"}]
            if self.broad:
                perms.append({"type":"anyone","role":"reader"})
            return Request({"id": self.folder, "mimeType": "application/vnd.google-apps.folder",
                            "capabilities":{"canAddChildren":True}, "permissions": perms})
        data = self.data
        return Request({"id": self.file_id, "name": "Simba_smoke-chatgpt-rafael_RAFAEL_" + "f"*16 + "_3_STORYBOARDS.zip",
                        "parents":[self.folder], "size":str(len(data)),
                        "md5Checksum":hashlib.md5(data).hexdigest(),
                        "appProperties":{"input_receipt":"f"*64, "sha256":archive.digest(data)},
                        "permissions":[{"type":"user","role":"owner"}]})
    def list(self, q, pageSize, fields):
        return Request({"files": ([] if self.data is None else [{"id": self.file_id}])})
    def create(self, body, media_body, fields):
        self.calls += 1
        self.data = media_body.data
        return Request({"id": self.file_id})
    def get_media(self, fileId):
        return Request(self.data)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = make_zip(Path(temp.name))
    def test_synthetic_manifest_and_nine_real_frame_bytes(self):
        payload, manifest = archive.safe_archive(self.path)
        self.assertEqual(len(payload), self.path.stat().st_size)
        self.assertEqual(len(manifest["options"]), 3)
        self.assertEqual(sum(len(i["scenes"]) for i in manifest["options"]), 9)
    def test_detect_corrupted_frame(self):
        with zipfile.ZipFile(self.path) as z:
            pieces = {k:z.read(k) for k in z.namelist()}
        pieces["option_2/scene_2.jpg"] += b"tampered"
        with zipfile.ZipFile(self.path, "w") as z:
            for k, v in pieces.items():
                z.writestr(k, v)
        with self.assertRaises(archive.ArchiveError):
            archive.safe_archive(self.path)
    def test_rejects_broadly_shared_folder_before_upload(self):
        fake = FakeDrive(broad=True)
        with self.assertRaises(archive.ArchiveError):
            archive.archive_private(fake, archive.ARCHIVE_FOLDER, self.path)
        self.assertEqual(fake.calls, 0)
    def test_full_existing_remote_checksum_and_bytes(self):
        data = self.path.read_bytes()
        fake = FakeDrive(data=data)
        result = archive.archive_private(fake, archive.ARCHIVE_FOLDER, self.path)
        self.assertEqual(result["status"], "ALREADY_VERIFIED_PRIVATE")
        self.assertTrue(result["archive_verified"])
        self.assertFalse(result["leo_approved"])
        self.assertEqual(result["paid_api_calls"], 0)
        self.assertEqual(fake.calls, 0)
    def test_remote_bytes_mismatch_rejected(self):
        fake = FakeDrive(data=b"different bytes")
        with self.assertRaises(archive.ArchiveError):
            archive.archive_private(fake, archive.ARCHIVE_FOLDER, self.path)
    def test_new_upload_creates_once_and_readbacks(self):
        fake_http = types.ModuleType("googleapiclient.http")
        class Media:
            def __init__(self, data, mimetype, resumable):
                self.data = data
        fake_http.MediaInMemoryUpload = Media
        fake_google = types.ModuleType("googleapiclient")
        with patch.dict(sys.modules, {"googleapiclient":fake_google,
                                      "googleapiclient.http":fake_http}):
            fake = FakeDrive()
            result = archive.archive_private(fake, archive.ARCHIVE_FOLDER, self.path)
        self.assertEqual(result["status"], "VERIFIED_PRIVATE_UPLOAD")
        self.assertTrue(result["archive_verified"])
        self.assertEqual(fake.calls, 1)
        self.assertEqual(fake.data, self.path.read_bytes())
    def test_dry_run_requires_no_credentials(self):
        from unittest.mock import patch
        output = io.StringIO()
        with patch("sys.stdout", output):
            self.assertEqual(archive.main(["--zip", str(self.path)]), 0)
        self.assertEqual(json.loads(output.getvalue())["status"],
                         "LOCAL_ZIP_VERIFIED_UPLOAD_NOT_EXECUTED")


if __name__ == "__main__":
    unittest.main()
