"""Optional Simba tools. No publishing or scheduling operations are implemented."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request


class IntegrationError(RuntimeError):
    pass


def positive_ids(values):
    if not isinstance(values, list) or not values:
        raise IntegrationError("Provide at least one channel ID")
    if any(type(value) is not int or value <= 0 for value in values):
        raise IntegrationError("IDs must be positive integers")
    return values


def draft_payload(package):
    """Allowlist the documented API fields; never forward workflow controls."""
    if not isinstance(package, dict):
        raise IntegrationError("Package JSON must be an object")
    if package.get("status", "draft") != "draft":
        raise IntegrationError("Only draft status is supported")
    forbidden = {"scheduledAt", "scheduled_at", "repeatSchedule", "publishWhenApproved",
                 "autoPlugEnabled", "autoRepostEnabled", "publishNow"}
    if forbidden.intersection(package):
        raise IntegrationError("Scheduling and publishing fields are forbidden")
    content = package.get("content")
    if not isinstance(content, str) or not content.strip():
        raise IntegrationError("Nonempty approved content is required")
    channels = positive_ids(package.get("channelIds"))
    media = package.get("mediaFiles", [])
    if not isinstance(media, list) or any(type(v) is not int or v <= 0 for v in media):
        raise IntegrationError("mediaFiles must contain existing positive media IDs")
    if package.get("textStatus") != "APPROVED_TEXT":
        raise IntegrationError("APPROVED_TEXT is required")
    if media and package.get("visualStatus") != "FINAL_VISUAL_READY":
        raise IntegrationError("Media requires FINAL_VISUAL_READY")
    return {"content": content, "channels": [{"channelId": v} for v in channels],
            "mediaFiles": media, "status": "draft"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_request(path, payload=None):
    if path not in ("/api/channels", "/api/posts"):
        raise IntegrationError("Unsupported endpoint")
    if path == "/api/posts" and (payload is None or payload.get("status") != "draft"):
        raise IntegrationError("Only draft creation is supported")
    key = os.environ.get("BULKPUBLISH_API_KEY", "").strip()
    if not key:
        raise IntegrationError("BULKPUBLISH_NOT_CONFIGURED: set BULKPUBLISH_API_KEY")
    request = urllib.request.Request(
        "https://app.bulkpublish.com" + path,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Never print headers, bearer credentials or arbitrary response bodies.
        raise IntegrationError(f"BULKPUBLISH_HTTP_{error.code}; no automatic retry") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise IntegrationError("BULKPUBLISH_NETWORK_ERROR; outcome unknown; check dashboard before retry") from None


def create_draft(package, send=False):
    payload = draft_payload(package)
    if not send:
        return {"status": "DRY_RUN", "request": payload}
    result = api_request("/api/posts", payload)
    return {"status": "DRAFT_CREATED", "provider": "BulkPublish", "response": result}


def scan(path, before=None, genre=None):
    executable = shutil.which("ru-humanizer")
    if not executable:
        raise IntegrationError("HUMANIZER_SCANNER_UNAVAILABLE: install optional requirements; use canonical Humanizer manually")
    target = Path(path).resolve(strict=True)
    if not target.is_file():
        raise IntegrationError("Input must be a local regular file")
    command = [executable, str(target), "--json"]
    if before:
        before_path = Path(before).resolve(strict=True)
        if not before_path.is_file():
            raise IntegrationError("before must be a local regular file")
        command.extend(["--before", str(before_path)])
    if genre:
        command.extend(["--genre", genre])
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode not in (0, 1, 2):
        raise IntegrationError("HUMANIZER_SCANNER_FAILED")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise IntegrationError("HUMANIZER_INVALID_REPORT") from None
    return {"status": "SCANNED", "scanner_exit_code": result.returncode,
            "report": report, "automatic_rewrite": False}


async def extract_document(path, language=None):
    source = Path(path).resolve(strict=True)
    if not source.is_file():
        raise IntegrationError("Input must be a local file")
    try:
        from xberg import ExtractInput, ExtractionConfig, OcrConfig, extract
    except ImportError:
        raise IntegrationError("XBERG_UNAVAILABLE: install optional requirements") from None
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    config = ExtractionConfig(ocr=OcrConfig(backend="tesseract", language=language)) if language else ExtractionConfig()
    result = await extract(ExtractInput(kind="uri", uri=str(source)), config)
    if result.summary.errors or not result.results:
        raise IntegrationError("SOURCE_BLOCKED: extraction returned errors or no documents; inspect original")
    documents = []
    for document in result.results:
        documents.append({"content": document.content,
                          "tables": [{"markdown": table.markdown, "cells": table.cells}
                                     for table in (document.tables or [])]})
    return {"status": "EXTRACTED_UNVERIFIED", "source": str(source), "sha256": digest,
            "engine": "xberg", "version": importlib.metadata.version("xberg"),
            "documents": documents, "requires_source_comparison": True}


def doctor():
    versions = {}
    for package in ("xberg", "ru-humanizer"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "NOT_INSTALLED"
    return {"packages": versions,
            "scanner_executable": bool(shutil.which("ru-humanizer")),
            "bulkpublish_credentials_present": bool(os.environ.get("BULKPUBLISH_API_KEY", "").strip()),
            "publication_supported": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("channels")
    draft = commands.add_parser("draft")
    draft.add_argument("package", type=Path)
    draft.add_argument("--send", action="store_true", help="Create remote draft; never publish")
    scanner = commands.add_parser("scan")
    scanner.add_argument("file")
    scanner.add_argument("--before")
    scanner.add_argument("--genre", choices=["academic", "legal", "fiction", "news"])
    extraction = commands.add_parser("extract")
    extraction.add_argument("file")
    extraction.add_argument("--ocr-language")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            output = doctor()
        elif args.command == "channels":
            output = api_request("/api/channels")
        elif args.command == "draft":
            output = create_draft(json.loads(args.package.read_text(encoding="utf-8")), args.send)
        elif args.command == "scan":
            output = scan(args.file, args.before, args.genre)
        else:
            output = asyncio.run(extract_document(args.file, args.ocr_language))
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (IntegrationError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
