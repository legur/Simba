#!/usr/bin/env python3
"""Build and deploy the 25 public Motion Lab files to the EXISTING Wix Headless site.

GitHub is canonical. This is a destructive Wix static *drop*, so the updater
always sends the complete allowlisted site, never a patch. No private files,
runtime adapters, customer data, or voice/media assets may enter the bundle.
No secret, OAuth access token, or user data is written to the repository.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
SITE_ID = "795efbc2-50c4-435e-939e-537cb2df75c7"
# Account that owns the Wix Headless site; an API key needs the account header.
ACCOUNT_ID = "7fd7b840-06ec-4c55-bee4-b7f932f5f07b"
SITE_URL = "https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com"
API_URL = (
    "https://www.wixapis.com/headless-business-setup/v1/"
    f"headless-business/{SITE_ID}"
)
SITE_FILES = (
    "index.html", "styles.css", "app.js", "transitions.js",
    "text.html", "text.css", "text.js",
    "subtitles.html", "subtitles.css", "subtitles.js",
    "camera.html", "camera.css", "camera.js",
    "storyboard.html", "storyboard.css", "storyboard.js", "visual_editor.js", "scene_pages.js",
    "director_core.js", "director_semantic.js", "director_analysis.js", "motionlab_v2_ui.js",
    "creative.html", "creative.css", "creative.js",
)
MAX_SITE_BYTES = 20 * 1024 * 1024
HTML_FILES = tuple(p for p in SITE_FILES if p.endswith(".html"))


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        value = values.get("href") if tag in ("link", "a") else values.get("src")
        if tag in ("link", "a", "script", "img") and value:
            self.references.append(value)


def collect_site_files(root: Path = ROOT) -> dict[str, bytes]:
    """Fail closed if any expected page is absent or contains broken links."""
    result: dict[str, bytes] = {}
    for filename in SITE_FILES:
        file = root / filename
        if not file.is_file() or file.is_symlink():
            raise ValueError(f"Missing/nonregular site file: {filename}")
        raw = file.read_bytes()
        if not raw:
            raise ValueError(f"Empty site file: {filename}")
        raw.decode("utf-8")
        result[filename] = raw
    if sum(len(b) for b in result.values()) > MAX_SITE_BYTES:
        raise ValueError("Site exceeds Wix static drop's 20 MiB limit")
    for page in HTML_FILES:
        parser = Links()
        parser.feed(result[page].decode("utf-8"))
        for href in parser.references:
            url = urllib.parse.urlsplit(href)
            if url.scheme or url.netloc or not url.path or href.startswith("//"):
                continue
            target = (root / urllib.parse.unquote(url.path)).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError(f"{page}: unsafe local link {href!r}")
            if target.name not in result or target.parent != root.resolve():
                raise ValueError(f"{page}: local link absent from site bundle: {href!r}")
    return result


def build_bundle(destination: Path, root: Path = ROOT) -> dict:
    files = collect_site_files(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for filename in sorted(files):
            entry = zipfile.ZipInfo(filename, date_time=(2024, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            z.writestr(entry, files[filename])
    manifest = {
        "site_id": SITE_ID,
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())},
        "archive_bytes": destination.stat().st_size,
    }
    if manifest["archive_bytes"] > 20 * 1024 * 1024:
        raise ValueError("Wix ZIP exceeds maximum allowed size")
    return manifest


def check_remote_files(data: dict) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        raise ValueError("Wix files API returned an unexpected response")
    remote = [x.get("path") for x in data["files"] if isinstance(x, dict)]
    if len(remote) != len(set(remote)):
        raise ValueError("Wix reports duplicate file paths: refusing destructive drop")
    missing = sorted(set(SITE_FILES) - set(remote))
    extras = sorted(set(remote) - set(SITE_FILES) - {"wix.config.json"})
    if missing or extras:
        raise ValueError(
            "Wix files have diverged from the protected 21-file deployment set. "
            f"Missing={missing}; extras={extras}. Resolve the drift before deployment."
        )


def make_auth_header(token: str) -> str:
    value = token.strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError("Missing or malformed Wix API key")
    # Wix API keys go verbatim in Authorization; do not prefix them with Bearer.
    return value


def wix_files_snapshot(auth: str) -> dict:
    req = urllib.request.Request(
        API_URL + "/files",
        headers={"Authorization": auth, "wix-account-id": ACCOUNT_ID, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Wix files returned HTTP {resp.status}")
            return json.load(resp)
    except urllib.error.HTTPError as error:
        # Only a diagnostic code, never credentials or echoed request metadata.
        code = "unknown"
        try:
            payload = json.loads(error.read(32768))
            details = payload.get("details") or {}
            app_error = details.get("applicationError") or {}
            code = str(app_error.get("code") or payload.get("code") or "unknown")[:90]
        except (ValueError, TypeError, AttributeError):
            pass
        raise RuntimeError(f"Wix files API HTTP {error.code}; error code: {code}") from None


def publish(bundle: Path, auth: str) -> dict:
    if not bundle.is_file():
        raise ValueError("Missing ZIP; build first")
    with tempfile.TemporaryDirectory() as temp:
        response_path = Path(temp) / "wix-drop-result.json"
        args = [
            "curl", "--silent", "--show-error", "--max-time", "150",
            "-X", "POST",
            API_URL + "/drop?campaign=github-actions&agent=simba",
            "-H", "Authorization: " + auth,
            "-H", "wix-account-id: " + ACCOUNT_ID,
            "-F", f"files=@{bundle};filename=motion-lab.zip;type=application/zip",
            "-o", str(response_path),
            "-w", "%{http_code}",
        ]
        # This POST is NOT retried: a timeout may occur after Wix published.
        process = subprocess.run(args, capture_output=True, text=True, check=False)
        status = process.stdout.strip()
        if process.returncode or not status.startswith("2"):
            raise RuntimeError(
                f"Wix static drop status HTTP {status or 'unknown'}. "
                "Do not retry automatically: check the live files before rerunning."
            )
        response = json.loads(response_path.read_text(encoding="utf-8"))
    if response.get("siteUrl", "").rstrip("/") != SITE_URL:
        raise RuntimeError("Wix drop responded with a different site URL; verify manually")
    if not response.get("uploadId"):
        raise RuntimeError("Wix drop has no uploadId; verify manually")
    return response


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "deploy"))
    parser.add_argument("--bundle", type=Path, default=Path("/tmp/motionlab-site.zip"))
    args = parser.parse_args()
    try:
        manifest = build_bundle(args.bundle)
        print(f"Bundle: {len(manifest['files'])} public files / {manifest['archive_bytes']} bytes")
        if args.action == "build":
            print("Build-only mode; Wix not contacted.")
            return 0
        auth = make_auth_header(os.environ.get("WIX_API_KEY", ""))
        before = wix_files_snapshot(auth)
        check_remote_files(before)
        print("Remote static site is the expected 16-file Motion Lab; publishing.", flush=True)
        result = publish(args.bundle, auth)
        print("Wix accepted the upload; checking remote inventory.", flush=True)
        after = wix_files_snapshot(auth)
        check_remote_files(after)
        print(f"PUBLISHED: {SITE_URL} (upload ID recorded by Wix)")
        print(f"GitHub commit: {os.environ.get('GITHUB_SHA', 'unavailable')}")
        return 0
    except (ValueError, OSError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as error:
        print(f"Motion Lab deployment stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
