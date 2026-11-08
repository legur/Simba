from __future__ import annotations

import contextlib
import io
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from integrations.video import github_secret_job as job


TRUSTED_ENV = {
    "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_ACTOR": "legur", "GITHUB_TRIGGERING_ACTOR": "legur",
    "GITHUB_REPOSITORY_OWNER": "legur", "GITHUB_REPOSITORY": "legur/Simba",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_WORKFLOW": "Simba video — private GitHub Secrets render",
    "GITHUB_WORKFLOW_REF": "legur/Simba/.github/workflows/simba-video-secrets-render.yml@refs/heads/main",
    "GITHUB_SHA": "a" * 40, "GITHUB_WORKFLOW_SHA": "a" * 40,
}


def spec(**updates):
    value = {
        "packageId": "prague-ad",
        "sourcePost": "SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/prague.md",
        "scenes": [{"image": "media/scene.jpg", "lines": [{"text": "Prague"}]}],
        "end": {"poster": "media/cover.png"},
    }
    value.update(updates)
    return value


def make_zip(path: Path, entries: dict[str, bytes], *, executable: str | None = None,
             symlink: str | None = None) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            if name == executable:
                info.external_attr = (stat.S_IFREG | 0o755) << 16
            elif name == symlink:
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, data)


class InputValidationTests(unittest.TestCase):
    def test_drive_ids_are_strict(self):
        self.assertEqual(job.validate_drive_id("1Ab_c-DEfghijkLMNop"), "1Ab_c-DEfghijkLMNop")
        for value in ("", "short", "abc defghijkl", "${{ secrets.X }}", "id;echo-x"):
            with self.subTest(value=value), self.assertRaises(job.JobError):
                job.validate_drive_id(value)

    def test_runtime_must_be_owner_dispatch_on_main(self):
        job.validate_runtime(TRUSTED_ENV)
        for key, value in (("GITHUB_EVENT_NAME", "push"), ("GITHUB_ACTOR", "other"),
                           ("GITHUB_TRIGGERING_ACTOR", "other"), ("GITHUB_REF", "refs/heads/dev"),
                           ("GITHUB_WORKFLOW_SHA", "b" * 40)):
            bad = dict(TRUSTED_ENV, **{key: value})
            with self.subTest(key=key), self.assertRaises(job.JobError):
                job.validate_runtime(bad)

    def test_checkout_head_must_equal_immutable_workflow_sha(self):
        completed = mock.Mock(stdout="a" * 40 + "\n")
        with mock.patch.object(job.subprocess, "run", return_value=completed):
            self.assertEqual(job.validate_checkout_identity(Path("repo"), TRUSTED_ENV), "a" * 40)
        completed.stdout = "b" * 40 + "\n"
        with mock.patch.object(job.subprocess, "run", return_value=completed), self.assertRaises(job.JobError):
            job.validate_checkout_identity(Path("repo"), TRUSTED_ENV)

    def test_spec_defaults_to_simba_and_rejects_edge(self):
        value = spec()
        job.validate_and_normalize_spec(value)
        self.assertEqual(value["voice"]["provider"], "simba")
        with self.assertRaisesRegex(job.JobError, "simba"):
            job.validate_and_normalize_spec(spec(voice={"provider": "edge"}))

    def test_source_post_is_trusted_approved_checkout_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            approved = root / "SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/prague.md"
            approved.parent.mkdir(parents=True)
            approved.write_text("STATUS: APPROVED\n\n## APPROVED_TEXT\nText\n", encoding="utf-8")
            self.assertEqual(job.validate_source_post(root, spec()), approved.resolve())
            for source in ("../secret.md", "https://example.test/post.md", "README.md"):
                with self.subTest(source=source), self.assertRaises(job.JobError):
                    job.validate_source_post(root, spec(sourcePost=source))

    def test_legacy_approved_source_uses_body_after_metadata(self):
        renderer = job._load_renderer_module()
        legacy = (
            "# MSC Black Friday\n\n"
            "Статус: APPROVED · решение Leo «Берём»\n"
            "SOURCE: Leo; STATUS: APPROVED, NOT PUBLISHED.\n\n"
            "Первый абзац рекламы.\n\nВторой абзац.\n"
        )
        body, approved = renderer.parse_approved_source(legacy)
        self.assertTrue(approved)
        self.assertEqual(body, "Первый абзац рекламы.\n\nВторой абзац.\n")

    def test_approval_mention_without_explicit_status_line_is_rejected(self):
        renderer = job._load_renderer_module()
        body, approved = renderer.parse_approved_source(
            "# Draft\n\nSOURCE: text is APPROVED by someone\n\nDraft copy\n"
        )
        self.assertFalse(approved)
        self.assertIsNone(body)


class SecureZipTests(unittest.TestCase):
    def valid_entries(self):
        return {
            "video-spec.json": json.dumps(spec()).encode(),
            "media/scene.jpg": b"jpeg-data",
            "media/cover.png": b"png-data",
        }

    def test_extracts_only_declared_media_and_rewrites_simba_default(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "input.zip"
            make_zip(archive, self.valid_entries())
            destination = root / "job"
            normalized = job.extract_job_zip(archive, destination)
            self.assertEqual(normalized["voice"]["provider"], "simba")
            self.assertEqual(
                sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()),
                ["media/cover.png", "media/scene.jpg", "video-spec.json"],
            )

    def test_rejects_traversal_symlink_executable_and_extra_files(self):
        cases = []
        traversal = self.valid_entries(); traversal["../escape.jpg"] = b"x"; cases.append((traversal, None, None))
        symlink = self.valid_entries(); cases.append((symlink, None, "media/scene.jpg"))
        executable = self.valid_entries(); cases.append((executable, "media/scene.jpg", None))
        extra = self.valid_entries(); extra["run.py"] = b"print('no')"; cases.append((extra, None, None))
        with tempfile.TemporaryDirectory() as folder:
            for index, (entries, executable_name, symlink_name) in enumerate(cases):
                archive = Path(folder) / f"bad-{index}.zip"
                make_zip(archive, entries, executable=executable_name, symlink=symlink_name)
                with self.subTest(index=index), self.assertRaises(job.JobError):
                    job.extract_job_zip(archive, Path(folder) / f"out-{index}")

    def test_rejects_url_absolute_and_parent_media_paths(self):
        for media in ("https://example.test/a.jpg", "/tmp/a.jpg", "../a.jpg", "C:/a.jpg"):
            value = spec(scenes=[{"image": media, "lines": [{"text": "x"}]}])
            with self.subTest(media=media), self.assertRaises(job.JobError):
                job.validate_and_normalize_spec(value)

    def test_restricted_workflow_rejects_code_drawn_inserts(self):
        value = spec(scenes=[{"insert": {"type": "route"}, "lines": [{"text": "Route"}]}])
        with self.assertRaisesRegex(job.JobError, "insert"):
            job.validate_and_normalize_spec(value)

    def test_offer_and_end_backgrounds_are_safe_and_declared(self):
        value = spec(offer={"bg": "media/offer.jpg"}, end={"bg": "media/scene.jpg"})
        job.validate_and_normalize_spec(value)
        self.assertEqual(job.referenced_media(value), {"media/scene.jpg", "media/offer.jpg"})
        for media in ("https://example.test/bg.jpg", "/tmp/bg.jpg", "../bg.jpg", "C:/bg.jpg"):
            with self.subTest(media=media), self.assertRaises(job.JobError):
                job.validate_and_normalize_spec(spec(offer={"bg": media}))
        with self.assertRaises(job.JobError):
            job.validate_and_normalize_spec(spec(end={"bg": {"not": "a path"}}))

    def test_zip_directory_entries_are_bounded_and_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            too_many = root / "too-many.zip"
            with zipfile.ZipFile(too_many, "w") as archive:
                for name, data in self.valid_entries().items():
                    archive.writestr(name, data)
                for index in range(job.MAX_ZIP_ENTRIES):
                    archive.writestr(f"dirs/{index}/", b"")
            with self.assertRaisesRegex(job.JobError, "entry count"):
                job.extract_job_zip(too_many, root / "many-out")

            nonempty_dir = root / "nonempty-dir.zip"
            with zipfile.ZipFile(nonempty_dir, "w") as archive:
                for name, data in self.valid_entries().items():
                    archive.writestr(name, data)
                archive.writestr("bad/", b"x")
            with self.assertRaises(job.JobError):
                job.extract_job_zip(nonempty_dir, root / "dir-out")

    def test_zip_rejects_file_as_parent_before_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "collision.zip"
            value = spec(scenes=[
                {"image": "a.jpg", "lines": [{"text": "one"}]},
                {"image": "a.jpg/b.png", "lines": [{"text": "two"}]},
            ])
            entries = {
                "video-spec.json": json.dumps(value).encode(),
                "a.jpg": b"parent-file", "a.jpg/b.png": b"child-file",
                "media/cover.png": b"cover",
            }
            make_zip(archive, entries)
            destination = root / "must-not-exist"
            with self.assertRaisesRegex(job.JobError, "file-as-parent"):
                job.extract_job_zip(archive, destination)
            self.assertFalse(destination.exists())

    def test_tts_caps_apply_before_marker_with_clip_voice_excluded(self):
        too_many = spec(scenes=[{
            "image": "media/scene.jpg",
            "lines": [{"text": f"line {index}"} for index in range(17)],
        }])
        with self.assertRaisesRegex(job.JobError, "cap"):
            job.validate_tts_budget(too_many)

        too_long_total = spec(scenes=[{
            "image": "media/scene.jpg", "lines": [{"text": "x" * 401} for _ in range(3)],
        }])
        with self.assertRaisesRegex(job.JobError, "cap"):
            job.validate_tts_budget(too_long_total)

        single_too_long = spec(scenes=[{
            "image": "media/scene.jpg", "lines": [{"text": "x" * 451, "fromClip": True}],
        }])
        with self.assertRaisesRegex(job.JobError, "1-450"):
            job.validate_tts_budget(single_too_long)

        clip_only = spec(scenes=[{
            "clip": "media/source.mp4", "voice": "clip",
            "lines": [{"text": "existing clip speech " * 30} for _ in range(20)],
        }])
        self.assertEqual(job.validate_tts_budget(clip_only), (0, 0))


class MarkerAndOutputTests(unittest.TestCase):
    def test_marker_decision_is_create_once_or_abort(self):
        self.assertEqual(job.marker_decision([]), "create")
        with self.assertRaises(job.ReplayBlocked):
            job.marker_decision([{"id": "existing"}])
        with self.assertRaises(job.JobError):
            job.marker_decision([{"id": "one"}, {"id": "two"}])

    def test_marker_name_is_deterministic_without_raw_id(self):
        file_id = "1Ab_c-DEfghijkLMNop"
        name = job.marker_name(file_id)
        self.assertEqual(name, job.marker_name(file_id))
        self.assertNotIn(file_id, name)

    def test_marker_is_created_and_read_back_with_mocked_drive(self):
        class Request:
            def execute(self, **kwargs):
                return {"id": "marker-file-id"}

        class Files:
            def create(self, **kwargs):
                self.kwargs = kwargs
                return Request()

        class Drive:
            def __init__(self):
                self.service = Files()

            def files(self):
                return self.service

        drive = Drive()
        observed = {
            "id": "marker-file-id", "name": job.marker_name("1Ab_c-DEfghijkLMNop"),
            "size": None, "parents": ["1Folder_Abcdefgh"], "permissions": [{"type": "user", "role": "owner"}],
        }
        with mock.patch.object(job, "_global_marker_matches", return_value=[]), \
                mock.patch.object(job, "_get_drive_item", return_value=observed):
            # Derive the exact in-memory marker size without exposing any credential.
            def upload_factory(stream, **kwargs):
                observed["size"] = str(len(stream.getvalue()))
                return object()
            result = job.create_attempt_marker(
                drive, "1Folder_Abcdefgh", "1Ab_c-DEfghijkLMNop",
                {"GITHUB_ACTOR": "legur", "GITHUB_RUN_ID": "7"},
                media_upload_factory=upload_factory,
            )
        self.assertEqual(result["id"], "marker-file-id")
        self.assertEqual(drive.service.kwargs["body"]["parents"], ["1Folder_Abcdefgh"])

    def test_ambiguous_marker_creation_blocks_paid_work_with_mocked_drive(self):
        class Request:
            def execute(self, **kwargs):
                raise TimeoutError("response lost")

        class Files:
            def create(self, **kwargs):
                return Request()

        class Drive:
            def files(self):
                return Files()

        with mock.patch.object(job, "_global_marker_matches", side_effect=[[], [{"id": "maybe-created"}]]):
            with self.assertRaises(job.ReplayBlocked):
                job.create_attempt_marker(
                    Drive(), "1Folder_Abcdefgh", "1Ab_c-DEfghijkLMNop", {},
                    media_upload_factory=lambda *args, **kwargs: object(),
                )

    def test_marker_blocks_same_input_in_a_different_destination(self):
        existing = {"id": "marker-in-first-folder"}
        observed = {"id": existing["id"], "permissions": [{"type": "user", "role": "owner"}]}
        with mock.patch.object(job, "_global_marker_matches", return_value=[existing]), \
                mock.patch.object(job, "_get_drive_item", return_value=observed):
            with self.assertRaises(job.ReplayBlocked):
                job.create_attempt_marker(
                    object(), "1Second_FolderId", "1Ab_c-DEfghijkLMNop", {},
                    media_upload_factory=lambda *args, **kwargs: object(),
                )

    def test_drive_lookup_consumes_all_pages(self):
        class Request:
            def __init__(self, response): self.response = response
            def execute(self, **kwargs): return self.response

        class Files:
            def __init__(self): self.tokens = []
            def list(self, **kwargs):
                self.tokens.append(kwargs.get("pageToken"))
                response = ({"files": [{"id": "one"}], "nextPageToken": "next"}
                            if kwargs.get("pageToken") is None else {"files": [{"id": "two"}]})
                return Request(response)

        class Drive:
            def __init__(self): self.service = Files()
            def files(self): return self.service

        drive = Drive()
        self.assertEqual([row["id"] for row in job._drive_list_all(drive, "trashed = false")], ["one", "two"])
        self.assertEqual(drive.service.tokens, [None, "next"])

    def test_private_drive_guard_rejects_shared_permissions(self):
        private = {"permissions": [{"type": "user", "role": "owner"}], "parents": ["folder"]}
        job._assert_private(private, expected_parent="folder")
        for permission in ({"type": "anyone", "role": "reader"}, {"type": "user", "role": "writer"}):
            with self.subTest(permission=permission), self.assertRaises(job.JobError):
                job._assert_private({"permissions": [permission]})

    def test_existing_drive_output_blocks_before_render(self):
        with mock.patch.object(job, "_drive_matches", side_effect=[[{"id": "existing-video"}]]):
            with self.assertRaisesRegex(job.JobError, "not be overwritten"):
                job.ensure_output_names_available(object(), "1Folder_Abcdefgh", "safe")

    def test_exact_outputs_cannot_escape_or_be_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, data in (("safe.mp4", b"video"), ("safe.srt", b"subs"),
                               ("cover.jpg", b"cover"), ("qa-report.md", b"qa")):
                (root / name).write_bytes(data)
            outputs = job.collect_outputs(root, "safe")
            self.assertEqual([p.name for p in outputs], ["safe.mp4", "safe.srt", "qa-report.md", "cover.jpg"])
            original = Path.is_symlink
            with mock.patch.object(Path, "is_symlink", autospec=True,
                                   side_effect=lambda path: path.name == "safe.mp4" or original(path)):
                with self.assertRaises(job.JobError):
                    job.collect_outputs(root, "safe")

    def test_renderer_and_success_summary_suppress_private_details(self):
        completed = mock.Mock(returncode=0, stdout="PRIVATE SCRIPT", stderr="provider secret detail")
        with mock.patch.object(job.subprocess, "run", return_value=completed) as called:
            self.assertEqual(job.invoke_renderer_privately(Path("repo"), Path("private-job"), {}), 0)
        self.assertTrue(called.call_args.kwargs["capture_output"])

        stdout, stderr = io.StringIO(), io.StringIO()
        uploaded = [{"name": "private-name.mp4", "id": "private-drive-id", "size": 123}]
        with mock.patch.object(job, "run", return_value=uploaded), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(job.main([
                "run", "--source-zip-file-id", "1Ab_c-DEfghijkLMNop",
                "--destination-folder-id", "1Folder_Abcdefgh",
                "--repo-root", ".", "--runner-temp", ".",
            ]), 0)
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertNotIn("PRIVATE SCRIPT", combined)
        self.assertNotIn("private-name", combined)
        self.assertNotIn("private-drive-id", combined)

    def test_unexpected_exception_has_no_traceback_or_private_text(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(job, "run", side_effect=RuntimeError("SECRET provider response")), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = job.main([
                "run", "--source-zip-file-id", "1Ab_c-DEfghijkLMNop",
                "--destination-folder-id", "1Folder_Abcdefgh",
                "--repo-root", ".", "--runner-temp", ".",
            ])
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(result, 2)
        self.assertNotIn("SECRET", combined)
        self.assertNotIn("Traceback", combined)


class RecoveryTests(unittest.TestCase):
    def test_renderer_error_diagnostic_omits_raw_secret_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = mock.Mock(returncode=2, stderr="SECRET_KEY Gemini request rejected (HTTP 403) PRIVATE SCRIPT", stdout="PRIVATE")
            with mock.patch.object(job.subprocess, "run", return_value=result):
                self.assertEqual(job.invoke_renderer_privately(Path("repo"), root, {}), 2)
            raw = (root / "render-diagnostic.json").read_text()
            self.assertNotIn("SECRET", raw)
            self.assertNotIn("PRIVATE", raw)
            self.assertEqual(json.loads(raw)["http_status"], 403)

    def test_recovery_keeps_audio_receipts_and_excludes_unknown_data(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            root = stage / "job"
            cache = root / "voice/.cache"
            cache.mkdir(parents=True)
            stem = "a" * 64
            (cache / (stem + ".wav")).write_bytes(b"existing paid audio")
            (cache / (stem + ".attempt.json")).write_text(json.dumps({"state":"attempt_started", "secret":"NEVER_ARCHIVE"}))
            (cache / "credentials.json").write_text("NEVER_ARCHIVE")
            (root / "render-diagnostic.json").write_text(json.dumps({"category":"renderer_failed", "raw":"NEVER_ARCHIVE"}))
            def upload(drive, folder_id, bundle, marker):
                with zipfile.ZipFile(bundle) as z:
                    self.assertIn("voice/.cache/" + stem + ".wav", z.namelist())
                    self.assertEqual(z.read("voice/.cache/" + stem + ".wav"), b"existing paid audio")
                    self.assertFalse(any(b"NEVER_ARCHIVE" in z.read(n) for n in z.namelist()))
                return {"id":"private-recovery"}
            with mock.patch.object(job, "upload_verified_output", side_effect=upload) as called:
                result = job.preserve_failed_render(object(), "private-folder", root, stage, "marker", "1234")
            self.assertEqual(result["id"], "private-recovery")
            self.assertEqual(called.call_count, 1)

    def test_recovery_rejects_symlink_without_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            root = stage / "job"
            cache = root / "voice/.cache"
            cache.mkdir(parents=True)
            other = stage / "private.txt"
            other.write_text("secret")
            (cache / ("a" * 64 + ".wav")).symlink_to(other)
            with mock.patch.object(job, "upload_verified_output") as upload, self.assertRaises(job.JobError):
                job.preserve_failed_render(object(), "folder", root, stage, "marker", "1234")
            upload.assert_not_called()

if __name__ == "__main__":
    unittest.main()

