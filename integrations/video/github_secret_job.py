"""One-shot GitHub Actions runner for a private Simba video job.

Usage (GitHub Actions only)::

    python integrations/video/github_secret_job.py run \
      --source-zip-file-id "$SOURCE_ZIP_FILE_ID" \
      --destination-folder-id "$DESTINATION_FOLDER_ID" \
      --repo-root "$GITHUB_WORKSPACE" --runner-temp "$RUNNER_TEMP"

The two Drive identifiers are ordinary workflow inputs. Google/Gemini credentials
must exist only in the process environment as GitHub Secrets. The source ZIP is
treated strictly as data: it may contain one ``video-spec.json`` and only the
media files named by that spec. Before any TTS call, a permanent private Drive
marker is created. An existing marker, or an ambiguous marker-create response,
blocks all retries so an uncertain paid request cannot be repeated.
Code-drawn ``insert`` scenes are intentionally unsupported in this restricted
workflow until they have a dedicated strict schema; use trusted image/clip
scenes instead.

GitHub workflow inputs, including Drive file/folder IDs, can be visible in the
Actions UI to people who can inspect the repository. They must be treated as
identifiers, not credentials. Renderer output is suppressed because this is a
public repository and its normal progress log includes private script text.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Mapping


DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{10,128}\Z")
PACKAGE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
MAX_ZIP_BYTES = 300 * 1024 * 1024
MAX_ENTRY_BYTES = 250 * 1024 * 1024
MAX_EXPANDED_BYTES = 600 * 1024 * 1024
MAX_FILES = 40
MAX_ZIP_ENTRIES = 80
MAX_SPEC_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024 * 1024
TRUSTED_SOURCE_PARTS = ("SIMBA KNOWLEDGE BASE", "03_CONTENT_LIBRARY")
SECRET_ENV = (
    "GEMINI_API_KEY", "GDRIVE_OAUTH_CLIENT_ID", "GDRIVE_OAUTH_CLIENT_SECRET",
    "GDRIVE_OAUTH_REFRESH_TOKEN",
)
EXPECTED_REPOSITORY = "legur/Simba"
EXPECTED_WORKFLOW = "Simba video — private GitHub Secrets render"
EXPECTED_WORKFLOW_REF = (
    "legur/Simba/.github/workflows/simba-video-secrets-render.yml@refs/heads/main"
)


class JobError(RuntimeError):
    """A safe-to-print validation or operation error."""


class ReplayBlocked(JobError):
    """A permanent attempt marker already exists; never repeat paid work."""


def validate_drive_id(value: str) -> str:
    if not isinstance(value, str) or not DRIVE_ID.fullmatch(value):
        raise JobError("Drive file/folder ID is invalid")
    return value


def validate_runtime(env: Mapping[str, str]) -> None:
    if env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise JobError("This command is restricted to workflow_dispatch")
    if not env.get("GITHUB_ACTOR") or env.get("GITHUB_ACTOR") != env.get("GITHUB_REPOSITORY_OWNER"):
        raise JobError("Only the repository owner may run this workflow")
    if env.get("GITHUB_TRIGGERING_ACTOR") != env.get("GITHUB_REPOSITORY_OWNER"):
        raise JobError("Only an owner-triggered workflow run or rerun is allowed")
    if env.get("GITHUB_REF") != "refs/heads/main":
        raise JobError("The workflow must be dispatched from main")
    if (env.get("GITHUB_REPOSITORY") != EXPECTED_REPOSITORY
            or env.get("GITHUB_WORKFLOW") != EXPECTED_WORKFLOW
            or env.get("GITHUB_WORKFLOW_REF") != EXPECTED_WORKFLOW_REF):
        raise JobError("Unexpected repository or workflow identity")
    sha = env.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[a-f0-9]{40}", sha) or env.get("GITHUB_WORKFLOW_SHA") != sha:
        raise JobError("Workflow definition and checked-out commit identity disagree")


def validate_checkout_identity(repo_root: Path, env: Mapping[str, str]) -> str:
    """Require the local trusted checkout to be the immutable workflow commit."""
    expected = env.get("GITHUB_SHA", "")
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        raise JobError("Trusted checkout identity could not be verified") from None
    observed = completed.stdout.strip()
    if observed != expected:
        raise JobError("Trusted checkout HEAD does not match the workflow commit")
    return observed


def validate_common_voice_guard() -> None:
    """Use the voice module's network-boundary identity policy before Drive OAuth."""
    video_dir = Path(__file__).resolve().parent
    if str(video_dir) not in sys.path:
        sys.path.insert(0, str(video_dir))
    try:
        import simba_voice
        simba_voice._require_github_secrets_workflow()
    except Exception:
        raise JobError("Shared Simba voice workflow identity guard rejected this run") from None


def _load_voice_module():
    video_dir = Path(__file__).resolve().parent
    if str(video_dir) not in sys.path:
        sys.path.insert(0, str(video_dir))
    try:
        import simba_voice
        return simba_voice
    except Exception:
        raise JobError("Trusted Simba voice policy module could not be loaded") from None


def require_secret_environment(env: Mapping[str, str]) -> None:
    if any(not env.get(name) for name in SECRET_ENV):
        raise JobError("Required Google GitHub Secrets are not configured")


def _safe_relative(value: object, *, field: str, extensions: set[str]) -> str:
    if not isinstance(value, str) or not value or len(value) > 240:
        raise JobError(f"{field} must be a short relative media path")
    if "\\" in value or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        raise JobError(f"{field} must be a local relative media path, not a URL or drive path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise JobError(f"{field} must stay inside the job directory")
    if any(part.startswith(".") for part in path.parts):
        raise JobError(f"{field} may not use hidden path components")
    if path.suffix.lower() not in extensions:
        raise JobError(f"{field} has an unsupported media extension")
    return path.as_posix()


def validate_and_normalize_spec(spec: object) -> dict:
    if not isinstance(spec, dict):
        raise JobError("video-spec.json must contain one JSON object")
    package = spec.get("packageId")
    if not isinstance(package, str) or not PACKAGE_ID.fullmatch(package) or ".." in package:
        raise JobError("video-spec.json packageId is unsafe")
    source = spec.get("sourcePost")
    if not isinstance(source, str) or not source:
        raise JobError("video-spec.json sourcePost is required")

    voice = spec.get("voice")
    if voice is None:
        voice = {}
        spec["voice"] = voice
    if not isinstance(voice, dict):
        raise JobError("video-spec.json voice must be an object")
    provider = voice.get("provider", "simba")
    if provider != "simba":
        raise JobError("GitHub Secrets rendering allows only voice.provider=simba")
    voice["provider"] = "simba"

    scenes = spec.get("scenes")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 8:
        raise JobError("video-spec.json needs 1-8 scenes")
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            raise JobError(f"scene {index} must be an object")
        if scene.get("insert") is not None:
            raise JobError("Code-drawn insert scenes are not allowed in this restricted workflow")
        image, clip = scene.get("image"), scene.get("clip")
        if (image is None) == (clip is None):
            raise JobError(f"scene {index} must name exactly one image or clip")
        if image is not None:
            scene["image"] = _safe_relative(image, field=f"scene {index} image", extensions=IMAGE_EXT)
        else:
            scene["clip"] = _safe_relative(clip, field=f"scene {index} clip", extensions=VIDEO_EXT)

    declared_scene_media = {
        scene[field] for scene in scenes for field in ("image", "clip") if scene.get(field)
    }

    def normalize_background(container: dict, field: str) -> None:
        value = container.get("bg")
        if value is None:
            return
        if isinstance(value, str) and value in declared_scene_media:
            container["bg"] = value
            return
        container["bg"] = _safe_relative(value, field=f"{field} bg", extensions=IMAGE_EXT)

    end = spec.get("end")
    if end is not None and not isinstance(end, dict):
        raise JobError("video-spec.json end must be an object")
    if isinstance(end, dict) and end.get("poster") is not None:
        end["poster"] = _safe_relative(end["poster"], field="end poster", extensions=IMAGE_EXT)
    if isinstance(end, dict):
        normalize_background(end, "end")
    offer = spec.get("offer")
    if offer is not None and not isinstance(offer, dict):
        raise JobError("video-spec.json offer must be an object")
    if isinstance(offer, dict):
        normalize_background(offer, "offer")
    music = spec.get("music")
    if music is not None and not isinstance(music, dict):
        raise JobError("video-spec.json music must be an object")
    if isinstance(music, dict) and music.get("file") is not None:
        music["file"] = _safe_relative(music["file"], field="music file", extensions=AUDIO_EXT)
    return spec


def referenced_media(spec: dict) -> set[str]:
    result: set[str] = set()
    for scene in spec["scenes"]:
        for field in ("image", "clip"):
            if scene.get(field):
                result.add(scene[field])
    end = spec.get("end") or {}
    for field in ("poster", "bg"):
        if end.get(field):
            result.add(end[field])
    offer = spec.get("offer") or {}
    if offer.get("bg"):
        result.add(offer["bg"])
    music = spec.get("music") or {}
    if music.get("file"):
        result.add(music["file"])
    if len(result) > MAX_FILES - 1:
        raise JobError("video-spec.json references too many media files")
    return result


def validate_source_post(repo_root: Path, spec: dict) -> Path:
    source = spec.get("sourcePost")
    if not isinstance(source, str) or "\\" in source or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", source):
        raise JobError("sourcePost must be a repository-relative Markdown path")
    rel = PurePosixPath(source)
    if rel.is_absolute() or ".." in rel.parts or tuple(rel.parts[:2]) != TRUSTED_SOURCE_PARTS or rel.suffix.lower() != ".md":
        raise JobError("sourcePost must be an approved post in SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY")
    root = repo_root.resolve()
    trusted = (root / Path(*TRUSTED_SOURCE_PARTS)).resolve()
    path = (root / Path(*rel.parts)).resolve()
    if (not trusted.is_relative_to(root) or not path.is_relative_to(root)
            or not path.is_relative_to(trusted) or not path.is_file() or path.is_symlink()):
        raise JobError("sourcePost is missing or outside the trusted content library")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise JobError("sourcePost cannot be read as UTF-8") from None
    renderer = _load_renderer_module()
    try:
        approved_body, approved = renderer.parse_approved_source(text)
    except Exception:
        raise JobError("sourcePost approval metadata could not be parsed") from None
    if not approved:
        raise JobError("sourcePost is not explicitly APPROVED")
    if not approved_body:
        raise JobError("sourcePost has no approved text body")
    return path


def _zip_member_path(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if "\\" in name or "\x00" in name:
        raise JobError("ZIP contains an unsafe member path")
    path = PurePosixPath(name.rstrip("/"))
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise JobError("ZIP contains a traversal or absolute member path")
    if any(part.startswith(".") for part in path.parts):
        raise JobError("ZIP contains hidden data")
    return path.as_posix()


def _assert_plain_zip_file(info: zipfile.ZipInfo) -> None:
    mode = (info.external_attr >> 16) & 0xFFFF
    kind = stat.S_IFMT(mode)
    if stat.S_ISLNK(mode) or (kind and kind != stat.S_IFREG):
        raise JobError("ZIP links and special files are forbidden")
    if mode & 0o111:
        raise JobError("Executable ZIP members are forbidden")
    if info.flag_bits & 0x1:
        raise JobError("Encrypted ZIP members are forbidden")
    if info.file_size > MAX_ENTRY_BYTES:
        raise JobError("ZIP member exceeds the size limit")
    if info.file_size and info.compress_size and info.file_size / info.compress_size > 200:
        raise JobError("ZIP member has an unsafe compression ratio")


def extract_job_zip(archive_path: Path, destination: Path) -> dict:
    """Validate and stream-extract a data-only job archive into an empty directory."""
    if not archive_path.is_file() or archive_path.is_symlink() or archive_path.stat().st_size > MAX_ZIP_BYTES:
        raise JobError("Downloaded ZIP is missing or exceeds the size limit")
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile):
        raise JobError("Drive input is not a valid ZIP archive") from None
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise JobError("ZIP entry count exceeds the limit")
        files: dict[str, zipfile.ZipInfo] = {}
        seen_casefold: set[str] = set()
        total = 0
        for info in infos:
            name = _zip_member_path(info)
            folded = name.casefold()
            if folded in seen_casefold:
                raise JobError("ZIP contains duplicate or case-colliding paths")
            seen_casefold.add(folded)
            if info.is_dir():
                mode = (info.external_attr >> 16) & 0xFFFF
                kind = stat.S_IFMT(mode)
                if (info.file_size != 0 or info.compress_size != 0 or stat.S_ISLNK(mode)
                        or (kind and kind != stat.S_IFDIR) or info.flag_bits & 0x1):
                    raise JobError("ZIP links, encrypted entries and special files are forbidden")
                continue
            _assert_plain_zip_file(info)
            files[name] = info
            total += info.file_size
        folded_files = {name.casefold() for name in files}
        for name in files:
            parts = PurePosixPath(name).parts
            if any(PurePosixPath(*parts[:index]).as_posix().casefold() in folded_files
                   for index in range(1, len(parts))):
                raise JobError("ZIP contains a file-as-parent path collision")
        if len(files) > MAX_FILES or total > MAX_EXPANDED_BYTES:
            raise JobError("ZIP expanded size or file count exceeds the limit")
        spec_info = files.get("video-spec.json")
        if spec_info is None or spec_info.file_size > MAX_SPEC_BYTES:
            raise JobError("ZIP must contain a small root video-spec.json")
        try:
            raw_spec = archive.read(spec_info)
            spec = json.loads(raw_spec.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise JobError("video-spec.json is not valid UTF-8 JSON") from None
        spec = validate_and_normalize_spec(spec)
        expected = {"video-spec.json", *referenced_media(spec)}
        if set(files) != expected:
            missing = expected - set(files)
            raise JobError("ZIP media does not exactly match video-spec.json" + (" (missing media)" if missing else " (unneeded data present)"))

        if destination.exists():
            raise JobError("Job staging directory already exists")
        destination.mkdir(parents=True, mode=0o700)
        for name in sorted(expected - {"video-spec.json"}):
            target = destination / Path(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            written = 0
            with archive.open(files[name]) as source, target.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    written += len(chunk)
                    if written > files[name].file_size or written > MAX_ENTRY_BYTES:
                        raise JobError("ZIP member exceeded its declared safe size")
                    output.write(chunk)
            if written != files[name].file_size:
                raise JobError("ZIP member size changed while extracting")
            target.chmod(0o600)
        spec_path = destination / "video-spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        spec_path.chmod(0o600)
        return spec


def marker_name(source_zip_file_id: str) -> str:
    validate_drive_id(source_zip_file_id)
    digest = hashlib.sha256(source_zip_file_id.encode("ascii")).hexdigest()[:32]
    return f".simba-video-paid-attempt-{digest}.json"


def marker_decision(matches: list[dict]) -> str:
    if len(matches) == 1:
        raise ReplayBlocked("A paid-attempt marker already exists; this input must not be retried")
    if len(matches) > 1:
        raise ReplayBlocked("Multiple paid-attempt markers exist; manual Drive inspection is required")
    return "create"


def _escape_drive_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _drive_list_all(drive, query: str) -> list[dict]:
    """Read every user-Drive result page; incomplete duplicate checks fail closed."""
    rows: list[dict] = []
    token = None
    try:
        for _ in range(100):
            request = drive.files().list(
                q=query, pageSize=100, pageToken=token, spaces="drive", corpora="user",
                fields=("nextPageToken,files(id,name,size,mimeType,parents,trashed,driveId,"
                        "appProperties,permissions(id,type,role,deleted))"),
            )
            response = request.execute(num_retries=0)
            rows.extend(response.get("files") or [])
            token = response.get("nextPageToken")
            if not token:
                return rows
    except Exception:
        raise JobError("Google Drive marker/output lookup failed") from None
    raise JobError("Google Drive lookup exceeded the safe pagination limit")


def _drive_matches(drive, folder_id: str, name: str) -> list[dict]:
    query = f"'{_escape_drive_query(folder_id)}' in parents and name = '{_escape_drive_query(name)}' and trashed = false"
    return _drive_list_all(drive, query)


def _global_marker_matches(drive, source_zip_file_id: str) -> list[dict]:
    """Find replay guards everywhere in the OAuth user's Drive, not one folder."""
    validate_drive_id(source_zip_file_id)
    digest = hashlib.sha256(source_zip_file_id.encode("ascii")).hexdigest()
    query = (
        "appProperties has { key='simba_paid_render_guard' and value='v1' } and "
        f"appProperties has {{ key='source_id_sha256' and value='{digest}' }}"
    )
    return _drive_list_all(drive, query)


def ensure_no_global_marker(drive, source_zip_file_id: str) -> None:
    matches = _global_marker_matches(drive, source_zip_file_id)
    for match in matches:
        try:
            observed = _get_drive_item(drive, match.get("id", ""))
            _assert_private(observed)
        except JobError:
            raise ReplayBlocked(
                "A paid-attempt marker exists but its privacy/read-back is uncertain; do not retry"
            ) from None
    marker_decision(matches)


def _assert_private(item: dict, *, expected_parent: str | None = None, folder: bool = False) -> None:
    if item.get("trashed") is True or item.get("driveId"):
        raise JobError("Drive destination/object is trashed or belongs to a shared drive")
    if folder and item.get("mimeType") != "application/vnd.google-apps.folder":
        raise JobError("Drive destination ID is not a folder")
    if expected_parent is not None and expected_parent not in (item.get("parents") or []):
        raise JobError("Drive object is outside the requested private destination")
    permissions = item.get("permissions")
    if not isinstance(permissions, list) or not permissions:
        raise JobError("Drive privacy permissions could not be verified")
    if any(p.get("deleted") is True or p.get("type") != "user" or p.get("role") != "owner" for p in permissions):
        raise JobError("Drive destination/object is shared; a private owner-only folder is required")


def _get_drive_item(drive, file_id: str) -> dict:
    try:
        return drive.files().get(
            fileId=file_id,
            fields="id,name,size,mimeType,parents,trashed,driveId,capabilities(canAddChildren,canDownload),permissions(id,type,role,deleted)",
        ).execute(num_retries=0)
    except Exception:
        raise JobError("Google Drive metadata read failed") from None


def validate_destination(drive, folder_id: str) -> dict:
    item = _get_drive_item(drive, folder_id)
    _assert_private(item, folder=True)
    if (item.get("capabilities") or {}).get("canAddChildren") is not True:
        raise JobError("Drive destination does not allow uploads")
    return item


def download_source_zip(drive, file_id: str, destination: Path) -> None:
    item = _get_drive_item(drive, file_id)
    _assert_private(item)
    size = item.get("size")
    if not isinstance(size, str) or not size.isdigit() or not 0 < int(size) <= MAX_ZIP_BYTES:
        raise JobError("Drive ZIP size is missing or exceeds the limit")
    if (item.get("capabilities") or {}).get("canDownload") is not True:
        raise JobError("Drive ZIP cannot be downloaded")
    try:
        from googleapiclient.http import MediaIoBaseDownload
        request = drive.files().get_media(fileId=file_id)
        with destination.open("xb") as output:
            downloader = MediaIoBaseDownload(output, request, chunksize=4 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk(num_retries=0)
                if output.tell() > MAX_ZIP_BYTES:
                    raise JobError("Drive ZIP download exceeded the limit")
    except JobError:
        raise
    except Exception:
        raise JobError("Google Drive ZIP download failed") from None
    if destination.stat().st_size != int(size):
        raise JobError("Drive ZIP size did not match metadata")


def create_attempt_marker(drive, folder_id: str, source_zip_file_id: str, env: Mapping[str, str],
                          media_upload_factory=None) -> dict:
    name = marker_name(source_zip_file_id)
    ensure_no_global_marker(drive, source_zip_file_id)
    payload = {
        "state": "attempt_started_no_automatic_retry",
        "source_zip_file_id": source_zip_file_id,
        "repository": env.get("GITHUB_REPOSITORY", ""),
        "workflow_run_id": env.get("GITHUB_RUN_ID", ""),
        "workflow_run_attempt": env.get("GITHUB_RUN_ATTEMPT", ""),
        "actor": env.get("GITHUB_ACTOR", ""),
        "trusted_checkout_sha": env.get("GITHUB_SHA", ""),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "notice": "Marker is permanent. Inspect this attempt before any manual retry.",
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    metadata = {
        "name": name, "parents": [folder_id], "mimeType": "application/json",
        "description": "Simba paid-render replay guard. Permanent even after failure or uncertain completion.",
        "appProperties": {
            "simba_paid_render_guard": "v1",
            "source_id_sha256": hashlib.sha256(source_zip_file_id.encode("ascii")).hexdigest(),
            "run_id": str(env.get("GITHUB_RUN_ID", ""))[:100],
        },
    }
    try:
        if media_upload_factory is None:
            from googleapiclient.http import MediaIoBaseUpload
            media_upload_factory = MediaIoBaseUpload
        created = drive.files().create(
            body=metadata,
            media_body=media_upload_factory(io.BytesIO(body), mimetype="application/json", resumable=False),
            fields="id",
        ).execute(num_retries=0)
    except Exception:
        # Creation may have succeeded despite a lost response. Either way, never synthesize.
        try:
            matches = _global_marker_matches(drive, source_zip_file_id)
        except JobError:
            matches = []
        if matches:
            raise ReplayBlocked("Paid-attempt marker creation was ambiguous; inspect Drive and do not retry") from None
        raise ReplayBlocked("Paid-attempt marker creation was uncertain; do not retry without manual Drive inspection") from None
    try:
        observed = _get_drive_item(drive, created.get("id", ""))
        _assert_private(observed, expected_parent=folder_id)
        if observed.get("name") != name or observed.get("size") != str(len(body)):
            raise JobError("marker mismatch")
    except JobError:
        raise ReplayBlocked("Paid-attempt marker read-back failed; do not start synthesis") from None
    return observed


def collect_outputs(job_dir: Path, package_id: str) -> list[Path]:
    if not PACKAGE_ID.fullmatch(package_id) or ".." in package_id:
        raise JobError("Unsafe packageId cannot select render outputs")
    root = job_dir.resolve()
    names = [f"{package_id}.mp4", f"{package_id}.srt", "qa-report.md", "cover.jpg"]
    outputs: list[Path] = []
    for name in names:
        path = job_dir / name
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or path.is_symlink() or not path.is_file():
            raise JobError(f"Expected render output is missing or unsafe: {name}")
        size = path.stat().st_size
        if not 0 < size <= MAX_OUTPUT_BYTES:
            raise JobError(f"Expected render output has an invalid size: {name}")
        outputs.append(path)
    return outputs


def _load_renderer_module():
    video_dir = Path(__file__).resolve().parent
    if str(video_dir) not in sys.path:
        sys.path.insert(0, str(video_dir))
    try:
        import make_video
        return make_video
    except Exception:
        raise JobError("Trusted renderer validation module could not be loaded") from None


def validate_renderer_preflight(repo_root: Path, job_dir: Path) -> dict:
    """Run the renderer's complete static gates before creating the paid marker.

    This deliberately stops before clip decoding, TTS, ASR, browser rendering,
    or any provider/network operation.
    """
    renderer = _load_renderer_module()
    if Path(renderer.REPO).resolve() != repo_root.resolve():
        raise JobError("Renderer repository identity differs from the trusted checkout")
    try:
        spec = renderer.load_spec(job_dir)
        source, approved = renderer.approved_text(spec, draft=False)
        if not approved:
            raise JobError("Renderer source approval gate failed")
        renderer.fact_gate(spec, source)
        if renderer.voice_provider(spec) != "simba":
            raise JobError("Renderer voice gate did not resolve to Simba")
        validate_tts_budget(spec)
    except JobError:
        raise
    except Exception:
        raise JobError("Renderer static preflight rejected the job before any paid request") from None
    return spec


def validate_tts_budget(spec: dict) -> tuple[int, int]:
    """Mirror Simba's new-request caps before the permanent replay marker.

    Lines spoken by a clip scene (``voice: clip``) are subtitles for existing
    media and are excluded. User-supplied ``fromClip`` flags do not bypass caps.
    """
    voice = _load_voice_module()
    spoken: list[str] = []

    def add_lines(lines: object, *, excluded: bool = False) -> None:
        if lines is None:
            return
        if not isinstance(lines, list):
            raise JobError("Narration lines must be a list")
        for line in lines:
            if not isinstance(line, dict):
                raise JobError("Every narration line must be an object")
            if excluded:
                continue
            text = line.get("say", line.get("text"))
            if not isinstance(text, str) or not text.strip() or len(text) > 450:
                raise JobError("Each new Simba TTS line must contain 1-450 characters")
            spoken.append(text)

    for scene in spec.get("scenes", []):
        clip_voice = bool(scene.get("clip")) and scene.get("voice", "tts") == "clip"
        add_lines(scene.get("lines", []), excluded=clip_voice)
    add_lines((spec.get("offer") or {}).get("lines", []))
    add_lines((spec.get("end") or {}).get("lines", []))
    count, characters = len(spoken), sum(len(text) for text in spoken)
    if count > voice.MAX_NEW_LINES or characters > voice.MAX_NEW_CHARACTERS:
        raise JobError("Simba TTS request exceeds the approved line/character cap")
    return count, characters


def invoke_renderer_privately(repo_root: Path, job_dir: Path, env: Mapping[str, str]) -> int:
    """Run the trusted renderer while keeping script/provider output out of public logs."""
    renderer = repo_root / "integrations/video/make_video.py"
    try:
        completed = subprocess.run(
            [sys.executable, str(renderer), str(job_dir)], cwd=repo_root, env=dict(env),
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
    except OSError:
        raise JobError("Trusted renderer process could not start") from None
    if completed.returncode and job_dir.is_dir():
        # Persist only allowlisted categories, never raw stderr/stdout or keys.
        raw = completed.stderr or ""
        category = "renderer_failed"
        for phrase, tag in (
            ("Gemini request rejected", "google_http_rejection"),
            ("Gemini unavailable", "google_unavailable"),
            ("audio response missing or ambiguous", "google_audio_schema"),
            ("Gemini audio payload", "google_audio_payload"),
            ("Earlier Gemini attempt", "previous_uncertain_attempt"),
            ("private Simba voice", "private_voice_metadata"),
            ("Simba TTS request cap", "tts_budget_guard"),
            ("Simba approved voice", "approved_voice_stage"),
        ):
            if phrase in raw:
                category = tag
                break
        status = re.search(r"HTTP[ _](\d{3})", raw)
        diagnostic = {"returncode": completed.returncode, "category": category,
                      "http_status": int(status.group(1)) if status else None}
        (job_dir / "render-diagnostic.json").write_text(json.dumps(diagnostic), encoding="utf-8")
    return completed.returncode


def preserve_failed_render(drive, folder_id: str, job_dir: Path, stage: Path,
                           marker_id: str, run_id: str) -> dict:
    """Archive existing WAVs and sanitized attempt receipts without more TTS."""
    if not re.fullmatch(r"[0-9]{1,30}", run_id):
        raise JobError("Invalid run ID for private recovery archive")
    bundle = stage / ("simba-recovery-" + run_id + ".zip")
    cache = job_dir / "voice" / ".cache"
    total = 0
    count = 0
    with zipfile.ZipFile(bundle, "x", zipfile.ZIP_DEFLATED) as archive:
        diagnostic = job_dir / "render-diagnostic.json"
        if diagnostic.is_file() and not diagnostic.is_symlink():
            data = json.loads(diagnostic.read_text(encoding="utf-8"))
            archive.writestr("render-diagnostic.json", json.dumps({
                key: data.get(key) for key in ("returncode", "category", "http_status")}))
        if cache.is_dir() and not cache.is_symlink():
            for item in sorted(cache.iterdir()):
                if not re.fullmatch(r"[0-9a-f]{64}(?:\.wav|\.attempt\.json|\.attempt\.response\.json)", item.name):
                    continue
                if item.is_symlink() or not item.is_file():
                    raise JobError("Unsafe recovery cache entry")
                total += item.stat().st_size
                count += 1
                if total > 128 * 1024 * 1024 or count > 32:
                    raise JobError("Recovery cache exceeds bounded archive size")
                name = "voice/.cache/" + item.name
                if item.name.endswith(".wav") or item.name.endswith(".response.json"):
                    archive.write(item, name)
                else:
                    receipt = json.loads(item.read_text(encoding="utf-8"))
                    # Do not archive arbitrary exception details or provider JSON.
                    allowed = {key: receipt[key] for key in (
                        "state", "provider", "model", "profile", "text_sha256",
                        "cache_name", "reason", "may_have_been_billed") if key in receipt}
                    archive.writestr(name, json.dumps(allowed))
        archive.writestr("README.txt", "Existing audio and attempt receipts only. No new synthesis. "
                         "Keep private. Preserve the permanent replay guard.\n")
    return upload_verified_output(drive, folder_id, bundle, marker_id)


def _mime_for(path: Path) -> str:
    return {".mp4": "video/mp4", ".srt": "application/x-subrip", ".md": "text/markdown", ".jpg": "image/jpeg", ".zip": "application/zip"}[path.suffix.lower()]


def upload_verified_output(drive, folder_id: str, path: Path, marker_id: str) -> dict:
    if _drive_matches(drive, folder_id, path.name):
        raise JobError(f"Drive output already exists; nothing was overwritten: {path.name}")
    size = path.stat().st_size
    metadata = {
        "name": path.name, "parents": [folder_id], "mimeType": _mime_for(path),
        "description": "Private Simba render output; publication/sharing is a separate explicit action.",
        "appProperties": {"simba_render_marker_id": marker_id},
    }
    try:
        from googleapiclient.http import MediaFileUpload
        request = drive.files().create(
            body=metadata,
            media_body=MediaFileUpload(str(path), mimetype=_mime_for(path), chunksize=4 * 1024 * 1024, resumable=True),
            fields="id",
        )
        created = None
        while created is None:
            _, created = request.next_chunk(num_retries=0)
    except Exception:
        raise JobError(f"Drive upload was uncertain for {path.name}; marker prevents automatic retry") from None
    observed = _get_drive_item(drive, created.get("id", ""))
    _assert_private(observed, expected_parent=folder_id)
    if observed.get("name") != path.name or observed.get("size") != str(size):
        raise JobError(f"Drive read-back failed for {path.name}; marker prevents automatic retry")
    return {"name": path.name, "id": observed["id"], "size": size}


def ensure_output_names_available(drive, folder_id: str, package_id: str) -> None:
    """Fail before the paid marker/TTS when any exact output name already exists."""
    if not PACKAGE_ID.fullmatch(package_id) or ".." in package_id:
        raise JobError("Unsafe packageId cannot select Drive output names")
    for name in (f"{package_id}.mp4", f"{package_id}.srt", "qa-report.md", "cover.jpg"):
        if _drive_matches(drive, folder_id, name):
            raise JobError(f"Drive output already exists; existing media will not be overwritten: {name}")


def oauth_drive_client(env: Mapping[str, str]):
    require_secret_environment(env)
    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        credentials = Credentials(
            token=None, refresh_token=env["GDRIVE_OAUTH_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=env["GDRIVE_OAUTH_CLIENT_ID"], client_secret=env["GDRIVE_OAUTH_CLIENT_SECRET"],
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        credentials.refresh(GoogleRequest())
        return build("drive", "v3", credentials=credentials, cache_discovery=False)
    except Exception:
        raise JobError("Google Drive OAuth from GitHub Secrets failed") from None


def run(source_zip_file_id: str, destination_folder_id: str, repo_root: Path,
        runner_temp: Path, env: Mapping[str, str] | None = None, drive=None) -> list[dict]:
    env = os.environ if env is None else env
    validate_runtime(env)
    source_zip_file_id = validate_drive_id(source_zip_file_id)
    destination_folder_id = validate_drive_id(destination_folder_id)
    repo_root = repo_root.resolve()
    runner_temp = runner_temp.resolve()
    if not (repo_root / ".git").exists() or not (repo_root / "integrations/video/make_video.py").is_file():
        raise JobError("Trusted Simba checkout is incomplete")
    validate_checkout_identity(repo_root, env)
    validate_common_voice_guard()
    require_secret_environment(env)
    if not runner_temp.is_dir():
        raise JobError("Runner temporary directory is unavailable")
    for tool in ("ffmpeg", "node"):
        if shutil.which(tool) is None:
            raise JobError(f"Required trusted renderer tool is missing: {tool}")

    drive = oauth_drive_client(env) if drive is None else drive
    validate_destination(drive, destination_folder_id)
    stage = Path(tempfile.mkdtemp(prefix="simba-video-", dir=runner_temp))
    stage.chmod(0o700)
    archive = stage / "input.zip"
    job_dir = stage / "job"
    try:
        download_source_zip(drive, source_zip_file_id, archive)
        spec = extract_job_zip(archive, job_dir)
        archive.unlink(missing_ok=True)
        validate_source_post(repo_root, spec)
        spec = validate_renderer_preflight(repo_root, job_dir)
        ensure_output_names_available(drive, destination_folder_id, spec["packageId"])

        # The marker blocks a new workflow run for this Drive input. The user's
        # approved primary->fallback model behavior inside this one run is governed
        # separately by simba_voice's per-model attempt journals.
        marker = create_attempt_marker(drive, destination_folder_id, source_zip_file_id, env)
        try:
            if invoke_renderer_privately(repo_root, job_dir, env) != 0:
                raise JobError("Renderer failed after the permanent marker was created; inspect before any retry")
            (job_dir / "render-diagnostic.json").write_text(json.dumps({
                "returncode": 0, "category": "output_validation_or_upload", "http_status": None}), encoding="utf-8")
            outputs = collect_outputs(job_dir, spec["packageId"])
            return [upload_verified_output(drive, destination_folder_id, path, marker["id"]) for path in outputs]
        except Exception:
            preserve_failed_render(drive, destination_folder_id, job_dir, stage,
                                   marker["id"], str(env.get("GITHUB_RUN_ID", "")))
            print("Private audio recovery archive verified. No synthesis retry was submitted.")
            raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one private GitHub-Secrets-backed Simba render")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("run")
    command.add_argument("--source-zip-file-id", required=True)
    command.add_argument("--destination-folder-id", required=True)
    command.add_argument("--repo-root", type=Path, required=True)
    command.add_argument("--runner-temp", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        uploaded = run(args.source_zip_file_id, args.destination_folder_id, args.repo_root, args.runner_temp)
    except ReplayBlocked:
        print("ERROR: replay guard stopped this private render; inspect Drive before any manual action", file=sys.stderr)
        return 2
    except JobError:
        print("ERROR: private render validation or processing failed; private details were suppressed", file=sys.stderr)
        return 2
    except Exception:
        # The repository and Actions logs are public. Unexpected library/provider
        # exceptions must not emit tracebacks, private paths, response bodies or secrets.
        print("ERROR: unexpected private render failure; all private details were suppressed", file=sys.stderr)
        return 2
    print(f"Verified {len(uploaded)} private Drive outputs ({sum(item['size'] for item in uploaded)} bytes total).")
    print("Drive file IDs and private filenames were verified by read-back but suppressed from this public log.")
    print("No files were shared or published. The permanent attempt marker remains in Drive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

