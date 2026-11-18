"""Offline Git regression for Windows-invalid unrelated paths.

Linux checkout permits ':' paths, so this test validates sparse selection and
materialization order, not the Windows PowerShell process itself.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


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


@unittest.skipUnless(shutil.which("git"), "Git is required for sparse checkout test")
class WindowsSparseCheckoutTest(unittest.TestCase):
    def test_no_checkout_then_sparse_then_checkout_materializes_core_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            upstream = root / "upstream"
            upstream.mkdir()
            git("init", "-q", "-b", "main", upstream)
            git("-C", upstream, "config", "user.name", "Offline CI")
            git("-C", upstream, "config", "user.email", "ci@example.invalid")
            for name in FILES + (BAD_ON_WINDOWS,):
                path = upstream / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("Offline fixture", encoding="utf-8")
            git("-C", upstream, "add", ".")
            git("-C", upstream, "commit", "-qm", "Synthetic Windows sparse tree")

            checkout = root / "Repo"
            git("clone", "--no-checkout", "--branch", "main", upstream, checkout)
            git("-C", checkout, "sparse-checkout", "init", "--cone")
            git("-C", checkout, "sparse-checkout", "set", "--cone", "--", *CORE)

            # Regression: sparse-checkout set alone doesn't necessarily
            # create files after a clone with --no-checkout.
            git("-C", checkout, "checkout", "main")
            for name in FILES:
                self.assertTrue((checkout / name).is_file(), name)
            self.assertFalse((checkout / BAD_ON_WINDOWS).exists())

    def test_partial_clone_can_be_recovered_without_wiping_git(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            upstream = root / "upstream"
            upstream.mkdir()
            git("init", "-q", "-b", "main", upstream)
            git("-C", upstream, "config", "user.name", "Offline CI")
            git("-C", upstream, "config", "user.email", "ci@example.invalid")
            for name in FILES + (BAD_ON_WINDOWS,):
                path = upstream / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("Fixture", encoding="utf-8")
            git("-C", upstream, "add", ".")
            git("-C", upstream, "commit", "-qm", "Fixture")
            checkout = root / "Repo"
            git("clone", "--branch", "main", upstream, checkout)
            missing = checkout / FILES[0]
            missing.unlink()
            git("-C", checkout, "sparse-checkout", "init", "--cone")
            git("-C", checkout, "sparse-checkout", "set", "--cone", "--", *CORE)
            git("-C", checkout, "checkout", "main")
            self.assertTrue(missing.is_file())
            self.assertFalse((checkout / BAD_ON_WINDOWS).exists())


if __name__ == "__main__":
    unittest.main()
