"""Offline tests: no A2E generation, Google credentials or network needed."""
from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path
from unittest import TestCase, main, mock

spec = importlib.util.spec_from_file_location(
    "a2e_drive_archiver",
    Path(__file__).with_name("a2e_drive_archiver.py"),
)
archiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archiver)

FOLDER = "1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj"
TASK_A = "6aec681b899ba60e0500350a"
TASK_B = "6aec6d631b36595765cac60b"


class ArchiveTests(TestCase):
    def test_safe_result_urls(self):
        self.assertTrue(archiver.safe_video_url(
            "https://3days-apac.downloadaivideo.com/a/b.mp4"))
        for bad in (
            "http://3days-apac.downloadaivideo.com/x",
            "https://downloadaivideo.com.evil.example/x.mp4",
            "https://user:password@video.a2e.ai/x.mp4",
            "https://localhost/a.mp4",
            "file:///tmp/result.mp4", None,
        ):
            with self.subTest(url=bad):
                self.assertFalse(archiver.safe_video_url(bad))

    def test_only_recent_completed_unique_task_ids(self):
        now = datetime(2026, 11, 6, tzinfo=timezone.utc)
        rows = [
            {"_id": TASK_A, "current_status": "completed",
             "createdAt": "2026-11-05T14:00:00Z"},
            {"_id": TASK_A, "current_status": "completed",
             "createdAt": "2026-11-05T14:00:00Z"},
            {"_id": TASK_B, "current_status": "processing",
             "createdAt": "2026-11-05T14:00:00Z"},
            {"_id": "6aabcdeff1", "current_status": "completed",
             "createdAt": "2026-10-10T14:00:00Z"},
        ]
        self.assertEqual(archiver.recent_completed_ids(rows, now), [TASK_A])
        with self.assertRaisesRegex(archiver.ArchiveError, "Malformed task ID"):
            archiver.recent_completed_ids([{"_id": "../bad", "current_status": "completed"}], now)

    def test_history_pagination_scans_all_pages_and_rejects_incomplete(self):
        a = [{"_id": str(i).zfill(10)} for i in range(100)]
        b = [{"_id": TASK_A}]
        with mock.patch.object(archiver, "_api_get", side_effect=[
            {"rows": a, "count": 101}, {"rows": b, "count": 101},
        ]) as read:
            self.assertEqual(len(archiver.list_records("sk_test")), 101)
            self.assertEqual(read.call_count, 2)
        with mock.patch.object(archiver, "MAX_PAGES", 1), \
             mock.patch.object(archiver, "_api_get", return_value={"rows": a, "count": 101}):
            with self.assertRaisesRegex(archiver.ArchiveError, "incomplete|Too many"):
                archiver.list_records("sk_test")

    def test_api_only_gets_expected_path(self):
        with mock.patch.object(archiver, "urlopen") as read:
            response = read.return_value.__enter__.return_value
            response.status = 200
            with mock.patch.object(archiver.json, "load", return_value={"code": 0, "data": {"rows": []}}):
                self.assertEqual(
                    archiver._api_get(
                        "https://api.a2e.ai/v1/userImage2Video/allRecords?pageNum=1&pageSize=100",
                        "sk_fake"),
                    {"rows": []})
                request = read.call_args.args[0]
                self.assertEqual(request.get_method(), "GET")
                self.assertEqual(request.get_header("User-agent"), "Genjutsu")
            with self.assertRaisesRegex(archiver.ArchiveError, "read-only"):
                archiver._api_get("https://api.a2e.ai/v1/userImage2Video/start", "sk_fake")

    def test_existing_drive_file_verified_before_skip(self):
        good = {"id": "drive123", "size": "4096", "md5Checksum": "b" * 32,
                "parents": [FOLDER], "appProperties": {"sha256": "a" * 64}}
        self.assertEqual(archiver.verify_existing(
            good, folder=FOLDER, size=4096, md5="b" * 32, sha="a" * 64), "drive123")
        for bad in (
            dict(good, md5Checksum="0" * 32),
            dict(good, size="4095"),
            dict(good, parents=["other_folder"]),
        ):
            with self.assertRaisesRegex(archiver.ArchiveError, "collision"):
                archiver.verify_existing(
                    bad, folder=FOLDER, size=4096, md5="b" * 32, sha="a" * 64)

    def test_drive_listing_uses_actual_pageSize_argument(self):
        class Files:
            def list(self, **kwargs):
                self.args = kwargs
                return self
            def execute(self, **kwargs):
                return {"files": [], "nextPageToken": None}
        files = Files()
        drive = mock.Mock()
        drive.files.return_value = files
        self.assertEqual(archiver.drive_matches(drive, FOLDER, "A2E_test.mp4"), [])
        self.assertEqual(files.args["pageSize"], 100)

    def test_run_archives_existing_completed_without_any_paid_a2e_call(self):
        rows = [{"_id": TASK_A, "current_status": "completed",
                 "createdAt": datetime.now(timezone.utc).isoformat()}]
        detail = {"_id": TASK_A, "current_status": "completed",
                  "result_url": "https://3days-apac.downloadaivideo.com/x.mp4"}
        def download(_, target):
            target.write_bytes(b"\x00\x00\x00\x18ftyp" + b"x" * 3000)
            return "a" * 64, "b" * 32, len(target.read_bytes())
        with mock.patch.object(archiver, "already_verified_on_drive", return_value=None), \
             mock.patch.object(archiver, "detail_for_task", return_value=detail), \
             mock.patch.object(archiver, "download_mp4", side_effect=download), \
             mock.patch.object(archiver, "verify_mp4", return_value=5.0), \
             mock.patch.object(archiver, "archive_mp4", return_value=("uploaded", "drive123")) as upload:
            result = archiver.run("sk_fake", FOLDER, scan_rows=rows, client=object())
        self.assertEqual(result["status"], "OK")
        self.assertEqual(len(result["uploaded"]), 1)
        self.assertEqual(upload.call_count, 1)


    def test_already_archived_does_not_redownload(self):
        rows = [{"_id": TASK_A, "current_status": "completed",
                 "createdAt": datetime.now(timezone.utc).isoformat()}]
        record = {"task_id": TASK_A, "file_id": "abc", "bytes": 1234, "sha256": "a" * 64}
        with mock.patch.object(archiver, "already_verified_on_drive", return_value=record), \
             mock.patch.object(archiver, "detail_for_task") as detail:
            report = archiver.run("sk_fake", FOLDER, scan_rows=rows, client=object())
        self.assertEqual(len(report["already_archived"]), 1)
        detail.assert_not_called()

    def test_missing_oauth_never_silently_reports_success(self):
        with mock.patch.dict(archiver.os.environ, {}, clear=True):
            with self.assertRaisesRegex(archiver.ArchiveError, "not configured"):
                archiver.oauth_drive_client()


if __name__ == "__main__":
    main()
