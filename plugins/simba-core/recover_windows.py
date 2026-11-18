#!/usr/bin/env python3
"""Windows-safe Simba CORE recovery using ONLY selected files from GitHub ZIP.

The broken local Git checkout/index is NOT consulted. No git, shell scripts,
secrets, paid APIs, publication, destructive cleanup, or Windows policy changes.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
from urllib.request import Request, urlopen
from zipfile import ZipFile, BadZipFile

PINNED_SHA = "984aeb911d71609936b83b3bd8608434050a0c82"
SOURCE = "https://codeload.github.com/legur/Simba/zip/" + PINNED_SHA
PREFIXES = (
    "integrations/core/", "plugins/simba-core/",
    "SIMBA KNOWLEDGE BASE/", "Симба (Писатель)/", "Critic/",
)
ROOT_FILES = frozenset(("AGENTS.md", "ROUTER_v10.1.md", "META-Governance-v8.1.md"))
REQUIRED = (
    "integrations/core/editorial_live_runner.py",
    "integrations/core/editorial_receipts_audit.py",
    "plugins/simba-core/server/simba_core_mcp.py",
    "SIMBA KNOWLEDGE BASE/00_CORE/KNOWLEDGE_MAP.md",
    "Симба (Писатель)/Simba-v5.0.md", "Critic/Critic-5.7.md",
)
MAX_ZIP = 200 * 1024 * 1024
MAX_SELECTED = 100 * 1024 * 1024


def members(zf):
    top = set()
    accepted = []
    cumulative = 0
    for info in zf.infolist():
        parts = PurePosixPath(info.filename).parts
        if not parts:
            continue
        top.add(parts[0])
        if len(parts) < 2 or info.is_dir():
            continue
        relative = parts[1:]
        if any(p in ("", ".", "..") or any(c in p for c in (":", "|", "\\"))
               for p in relative):
            continue
        name = "/".join(relative)
        if name not in ROOT_FILES and not any(name.startswith(p) for p in PREFIXES):
            continue
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError("ZIP symlink blocked: " + name)
        cumulative += info.file_size
        if cumulative > MAX_SELECTED or len(accepted) > 6000:
            raise ValueError("Selected CORE payload is unexpectedly large")
        accepted.append((info, relative))
    if len(top) != 1 or not next(iter(top)).startswith("Simba-"):
        raise ValueError("Unexpected ZIP root; extraction refused")
    have = {"/".join(parts) for _, parts in accepted}
    if not set(REQUIRED).issubset(have):
        raise ValueError("Required CORE files missing from downloaded ZIP")
    return accepted


def recover_zip(archive, destination):
    destination = Path(destination).resolve()
    with ZipFile(archive) as zf:
        selected = members(zf)
        for info, parts in selected:
            path = destination.joinpath(*parts)
            if destination not in path.resolve().parents:
                raise ValueError("ZIP path escapes destination")
            path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, path.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
    return len(selected)


def download(target):
    req = Request(SOURCE, headers={"User-Agent": "SimbaCore-Windows-Recovery/1.0"})
    with urlopen(req, timeout=120) as src, open(target, "wb") as dst:
        if int(src.headers.get("Content-Length") or 0) > MAX_ZIP:
            raise ValueError("Download too large")
        downloaded = 0
        while True:
            block = src.read(1024 * 1024)
            if not block:
                break
            downloaded += len(block)
            if downloaded > MAX_ZIP:
                raise ValueError("Download exceeded safety limit")
            dst.write(block)


def main():
    if os.name != "nt":
        print("Windows-only installer: no local files changed", file=sys.stderr)
        return 2
    appdata = os.environ.get("LOCALAPPDATA")
    if not appdata:
        print("LOCALAPPDATA missing", file=sys.stderr)
        return 2
    destination = Path(appdata) / "SimbaCore" / "Repo"
    print("SIMBA CORE: selective ZIP recovery, no Git checkout or paid calls")
    print("Source commit:", PINNED_SHA[:12])
    print("Destination:", destination)
    try:
        with tempfile.TemporaryDirectory(prefix="simba-core-recovery-") as temp:
            filename = Path(temp) / "safe-source.zip"
            download(filename)
            count = recover_zip(filename, destination)
        print("Extracted safe CORE files:", count)
        for rel in REQUIRED:
            ready = (destination / rel).is_file()
            print("OK" if ready else "MISSING", rel)
            if not ready:
                raise ValueError("CORE recovery incomplete")
        print("CORE_FILES_READY_LOCAL_MCP_NOT_CONNECTED")
        return 0
    except (OSError, ValueError, BadZipFile) as exc:
        print("BLOCKED:", type(exc).__name__, str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
