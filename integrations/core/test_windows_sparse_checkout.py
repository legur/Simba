"""Offline Git archive regression for Windows-invalid unrelated repo paths.

GitHub Actions normally runs on Linux, so it cannot reproduce the Windows
Win32 invalid-path exception itself. It CAN prove the extracted archive omits
Archivarius entirely, including names invalid on Windows, and never invokes
a checkout or resets an existing index.
"""
from pathlib import Path
import importlib.util
import zipfile
import shutil
import subprocess
import tempfile
import unittest
import zipfile


CORE = (
    "integrations/core",
    "plugins/simba-core",
    "SIMBA KNOWLEDGE BASE",
    "Симба (Писатель)",
    "Critic",
)
FILES = (
    "integrations/core/editorial_live_runner.py",
    "plugins/simba-core/server/simba_core_mcp.py",
    "SIMBA KNOWLEDGE BASE/00_CORE/KB_RUNTIME_PROTOCOL.md",
    "Симба (Писатель)/Simba-v5.0.md",
    "Critic/Critic-5.7.md",
)
BAD_ON_WINDOWS = "Archivarius/portrait 9:16.md"


def git(*arguments):
    return subprocess.run(
        ["git", *map(str, arguments)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, check=True, timeout=20,
    )


def build_repo(root):
    upstream = root / "upstream"
    upstream.mkdir()
    git("init", "-q", "-b", "main", upstream)
    git("-C", upstream, "config", "user.name", "Offline CI")
    git("-C", upstream, "config", "user.email", "ci@example.invalid")
    for name in FILES + (BAD_ON_WINDOWS,):
        path = upstream / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Offline fixture: " + name, encoding="utf-8")
    git("-C", upstream, "add", ".")
    git("-C", upstream, "commit", "-qm", "Synthetic Windows-unfriendly repository")
    return upstream


def extract_selected_tree(checkout, archive):
    git("-C", checkout, "archive", "--format=zip",
        "--output=" + str(archive), "HEAD", "--", *CORE)
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        assert BAD_ON_WINDOWS not in names, "Bad path unexpectedly selected"
        assert all(not name.startswith("Archivarius/") for name in names)
        z.extractall(checkout)
    return names


@unittest.skipUnless(shutil.which("git"), "Git is required for archive extraction test")
class WindowsArchiveCheckoutTest(unittest.TestCase):
    def test_no_checkout_clone_extracts_only_safe_core_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            upstream = build_repo(root)
            checkout = root / "Repo"
            archive = root / "safe.zip"
            git("clone", "--no-checkout", "--branch", "main", upstream, checkout)
            self.assertFalse((checkout / FILES[0]).exists())
            extract_selected_tree(checkout, archive)
            for name in FILES:
                self.assertTrue((checkout / name).is_file(), name)
            self.assertFalse((checkout / BAD_ON_WINDOWS).exists())

    def test_partial_failed_clone_recovers_without_checkout_or_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            upstream = build_repo(root)
            checkout = root / "Repo"
            archive = root / "safe.zip"
            git("clone", "--branch", "main", upstream, checkout)
            missing = checkout / FILES[0]
            missing.unlink()
            # User has already attempted sparse checkout but a later checkout
            # failed because Git's existing index still lists illegal paths.
            git("-C", checkout, "sparse-checkout", "init", "--cone")
            git("-C", checkout, "sparse-checkout", "set", "--cone", "--", *CORE)
            extract_selected_tree(checkout, archive)
            self.assertTrue(missing.is_file())
            for name in FILES:
                self.assertTrue((checkout / name).is_file(), name)
            # The archive never touches unrelated folders or Git metadata.
            self.assertTrue((checkout / ".git").exists())
            self.assertFalse((checkout / BAD_ON_WINDOWS).exists())

    def test_archive_members_never_expose_bad_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            upstream = build_repo(root)
            checkout = root / "Repo"
            archive = root / "safe.zip"
            git("clone", "--no-checkout", "--branch", "main", upstream, checkout)
            names = extract_selected_tree(checkout, archive)
            self.assertTrue(any(x.startswith("Симба (Писатель)/") for x in names))
            self.assertTrue(any(x.startswith("SIMBA KNOWLEDGE BASE/") for x in names))
            self.assertFalse(any("9:16" in x for x in names))


class SafeGithubZipRecoveryTest(unittest.TestCase):
    def test_installer_filters_invalid_windows_names_without_git(self):
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "plugins/simba-core/recover_windows.py"
        spec = importlib.util.spec_from_file_location("simba_windows_zip_recovery", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            archive = base / "repo.zip"
            dest = base / "existing-partial-repo"
            (dest / ".git").mkdir(parents=True)
            (dest / ".git" / "index").write_bytes(b"existing-index-must-remain")
            prefix = "Simba-" + module.PINNED_SHA + "/"
            with zipfile.ZipFile(archive, "w") as zf:
                for name in module.REQUIRED:
                    zf.writestr(prefix + name, "core-fixture")
                zf.writestr(prefix + "Archivarius/portrait 9:16.md", "invalid Windows path")
                zf.writestr(prefix + "Archivarius/TIA/TIA-011 | bad.txt", "invalid Windows path")
            self.assertEqual(module.recover_zip(archive, dest), len(module.REQUIRED))
            for name in module.REQUIRED:
                self.assertTrue((dest / name).is_file(), name)
            self.assertFalse((dest / "Archivarius").exists())
            self.assertEqual((dest / ".git" / "index").read_bytes(),
                             b"existing-index-must-remain")

    def test_installer_rejects_archive_missing_required_file(self):
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "plugins/simba-core/recover_windows.py"
        spec = importlib.util.spec_from_file_location("simba_windows_zip_recovery_absent", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            archive = base / "missing.zip"
            dest = base / "no-write-on-invalid"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("Simba-" + module.PINNED_SHA + "/" + module.REQUIRED[0], "only one file")
            with self.assertRaisesRegex(ValueError, "Required CORE files missing"):
                module.recover_zip(archive, dest)
            self.assertFalse(dest.exists())

    def test_installer_is_never_billing_or_shell_execution(self):
        root = Path(__file__).resolve().parents[2]
        code = (root / "plugins/simba-core/recover_windows.py").read_text(encoding="utf-8")
        self.assertIn("codeload.github.com/legur/Simba/zip/", code)
        self.assertIn("MAX_ZIP", code)
        self.assertNotIn("subprocess.", code)
        self.assertNotIn("os.system", code)
        self.assertNotIn("OPENAI_API_KEY", code)
        self.assertNotIn("SIMBA_CORE_ALLOW_BILLABLE", code)
        self.assertNotIn("git checkout", code.split('def main():', 1)[-1])


if __name__ == "__main__":
    unittest.main()
