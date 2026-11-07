"""Build a safe, manual-edit handoff from a rendered Simba job to OpenCut.

OpenCut Classic does not publish a supported project-import format or API.  This
module therefore copies only explicit, useful source files and writes honest
instructions; it never invents an OpenCut project file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
from collections import OrderedDict
from pathlib import Path


MAX_JSON_BYTES = 5 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024
MAX_FILES = 128
PACKAGE_ID = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9_-])?")
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".webm"})
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".avif"})
AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"})
RESERVED_OUTPUT_PATHS = frozenset({"OPEN_IN_OPENCUT.md", "opencut-handoff.json"})
CREDENTIAL_KEYS = frozenset({
    "apikey", "token", "password", "secret", "refreshtoken", "privatekey",
    "serviceaccount", "credentials", "authorization",
})


class HandoffError(ValueError):
    """The requested handoff is incomplete or unsafe."""


def _read_json(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise HandoffError(f"{label} must be a regular file, not a symlink")
    size = path.stat().st_size
    if not 0 < size <= MAX_JSON_BYTES:
        raise HandoffError(f"{label} must be nonempty and at most {MAX_JSON_BYTES} bytes")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise HandoffError(f"{label} must contain one JSON object")
    _reject_credentials(value, label)
    return value


def _reject_credentials(value: object, label: str) -> None:
    """Reject credential-shaped JSON keys recursively without exposing values."""
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if normalized in CREDENTIAL_KEYS or normalized.endswith(
                ("apikey", "token", "password", "secret", "privatekey", "serviceaccount", "credentials", "authorization")
            ):
                raise HandoffError(f"{label} contains credential field {key!r} and cannot be packaged")
            _reject_credentials(child, label)
    elif isinstance(value, list):
        for child in value:
            _reject_credentials(child, label)


def _path_key(relative: str) -> str:
    """Portable comparison key for output paths (Unicode + case insensitive)."""
    return unicodedata.normalize("NFKC", relative.replace("\\", "/")).casefold()


def _relative_file(
    job: Path,
    value: str,
    label: str,
    *,
    required: bool = True,
    extensions: frozenset[str] | None = None,
) -> tuple[Path, str] | None:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise HandoffError(f"{label} must be a nonempty relative filename")
    rel = Path(value)
    if rel.is_absolute() or rel.drive or ".." in rel.parts:
        raise HandoffError(f"{label} must stay inside the job folder")
    if any(part in ("", ".") for part in rel.parts):
        raise HandoffError(f"{label} must be a normalized relative filename")
    if any(part.startswith(".") for part in rel.parts):
        raise HandoffError(f"{label} cannot use hidden files or directories")
    key = _path_key(rel.as_posix())
    for reserved in RESERVED_OUTPUT_PATHS:
        reserved_key = _path_key(reserved)
        if key == reserved_key or key.startswith(reserved_key + "/") or reserved_key.startswith(key + "/"):
            raise HandoffError(f"{label} collides with reserved output path {reserved}")
    if extensions is not None and rel.suffix.casefold() not in extensions:
        allowed = ", ".join(sorted(extensions))
        raise HandoffError(f"{label} must use one of these safe extensions: {allowed}")

    current = job
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise HandoffError(f"{label} cannot use a symlink")
    resolved = current.resolve(strict=False)
    if not resolved.is_relative_to(job):
        raise HandoffError(f"{label} resolves outside the job folder")
    if not resolved.exists():
        if required:
            raise HandoffError(f"{label} was not found: {rel.as_posix()}")
        return None
    if not resolved.is_file():
        raise HandoffError(f"{label} must name one regular file")
    size = resolved.stat().st_size
    if not 0 < size <= MAX_FILE_BYTES:
        raise HandoffError(f"{label} must be nonempty and at most {MAX_FILE_BYTES} bytes")
    return resolved, rel.as_posix()


def _add_source(
    sources: "OrderedDict[str, tuple[Path, set[str]]]",
    job: Path,
    value: str,
    role: str,
    *,
    required: bool = True,
    extensions: frozenset[str] | None = None,
) -> None:
    found = _relative_file(job, value, role, required=required, extensions=extensions)
    if found is None:
        return
    source, rel = found
    key = _path_key(rel)
    for existing_rel in sources:
        existing_key = _path_key(existing_rel)
        if key == existing_key and rel != existing_rel:
            raise HandoffError(f"portable path collision: {existing_rel!r} and {rel!r}")
        if key.startswith(existing_key + "/") or existing_key.startswith(key + "/"):
            raise HandoffError(f"portable file/directory collision: {existing_rel!r} and {rel!r}")
    if rel in sources:
        sources[rel][1].add(role)
    else:
        sources[rel] = (source, {role})


def _collect_sources(job: Path, spec: dict, timeline: dict) -> "OrderedDict[str, tuple[Path, set[str]]]":
    package_id = spec.get("packageId")
    if not isinstance(package_id, str) or not PACKAGE_ID.fullmatch(package_id) or ".." in package_id:
        raise HandoffError("video-spec.json packageId is unsafe")

    sources: "OrderedDict[str, tuple[Path, set[str]]]" = OrderedDict()
    _add_source(sources, job, "video-spec.json", "video specification")
    _add_source(sources, job, "timeline.json", "Simba timeline")
    _add_source(sources, job, f"{package_id}.mp4", "flattened final video")

    for filename, role in (
        (f"{package_id}.srt", "subtitles reference"),
        ("cover.jpg", "cover"),
        ("qa-report.md", "Simba QA report"),
    ):
        _add_source(sources, job, filename, role, required=False)

    scenes = spec.get("scenes", [])
    if not isinstance(scenes, list):
        raise HandoffError("video-spec.json scenes must be an array")
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            raise HandoffError(f"scene {index} must be an object")
        for field in ("clip", "image"):
            if field in scene:
                extensions = VIDEO_EXTENSIONS if field == "clip" else IMAGE_EXTENSIONS
                _add_source(sources, job, scene[field], f"scene {index} {field}", extensions=extensions)

    for section_name in ("offer", "end"):
        section = spec.get(section_name) or {}
        if not isinstance(section, dict):
            raise HandoffError(f"video-spec.json {section_name} must be an object")
        for field in ("bg", "poster"):
            if section.get(field):
                extensions = IMAGE_EXTENSIONS if field == "poster" else IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
                _add_source(sources, job, section[field], f"{section_name} {field}", extensions=extensions)

    music = spec.get("music") or {}
    if not isinstance(music, dict):
        raise HandoffError("video-spec.json music must be an object")
    if music.get("file"):
        _add_source(sources, job, music["file"], "original music", extensions=AUDIO_EXTENSIONS)

    lines = timeline.get("lines", [])
    if not isinstance(lines, list):
        raise HandoffError("timeline.json lines must be an array")
    for index, line in enumerate(lines, 1):
        if not isinstance(line, dict):
            raise HandoffError(f"timeline line {index} must be an object")
        line_id = line.get("id")
        if line_id is not None:
            if not isinstance(line_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", line_id):
                raise HandoffError(f"timeline line {index} has an unsafe id")
            _add_source(
                sources, job, f"voice/{line_id}.wav", f"voice line {line_id}",
                required=False, extensions=frozenset({".wav"}),
            )

    clip_audio = timeline.get("clipAudio", [])
    if not isinstance(clip_audio, list):
        raise HandoffError("timeline.json clipAudio must be an array")
    for index, item in enumerate(clip_audio, 1):
        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
            raise HandoffError(f"timeline clipAudio {index} must name a file")
        _add_source(
            sources, job, item["file"], f"clip voice {index}",
            required=False, extensions=frozenset({".wav"}),
        )

    if len(sources) > MAX_FILES:
        raise HandoffError(f"handoff exceeds the {MAX_FILES}-file safety limit")
    total = sum(source.stat().st_size for source, _roles in sources.values())
    if total > MAX_TOTAL_BYTES:
        raise HandoffError(f"handoff exceeds the {MAX_TOTAL_BYTES}-byte safety limit")
    return sources


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _publish_without_overwrite(stage: Path, output: Path) -> None:
    """Reserve output and copy staged files using fail-if-exists operations."""
    try:
        output.mkdir()
    except FileExistsError as exc:
        raise HandoffError("output directory appeared during build; refusing to overwrite it") from exc

    directories = sorted((path for path in stage.rglob("*") if path.is_dir()), key=lambda path: len(path.parts))
    for source in directories:
        destination = output / source.relative_to(stage)
        try:
            destination.mkdir()
        except FileExistsError as exc:
            raise HandoffError(f"output path appeared during build: {destination.relative_to(output).as_posix()}") from exc

    for source in sorted(path for path in stage.rglob("*") if path.is_file()):
        destination = output / source.relative_to(stage)
        try:
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise HandoffError(f"output file appeared during build: {destination.relative_to(output).as_posix()}") from exc
        with os.fdopen(descriptor, "wb") as target, source.open("rb") as origin:
            shutil.copyfileobj(origin, target, length=1024 * 1024)


def _instructions(package_id: str, included: list[str]) -> str:
    listed = "\n".join(f"- `{path}`" for path in included)
    return f"""# Редактирование ролика {package_id} в OpenCut

Этот каталог — безопасный набор материалов для **ручного** импорта в OpenCut Classic. Это не файл проекта:
у OpenCut Classic нет документированного API или поддерживаемого формата автоматического импорта проекта.

## Как открыть

1. Откройте OpenCut Classic и создайте новый проект.
2. Импортируйте нужные файлы из этого каталога через Media / Import.
3. Для быстрой правки положите `{package_id}.mp4` на таймлайн. Это уже собранный (flattened) ролик:
   текст, анимация и переходы в нём запечены и не редактируются по отдельности.
4. Если нужно менять сцены, переходы, музыку или голос раздельно, импортируйте исходные клипы,
   изображения, музыку и дорожки из `voice/`, затем вручную пересоберите таймлайн по `timeline.json`
   и `video-spec.json`. SRT служит ориентиром для субтитров; возможность его прямого импорта зависит
   от текущей версии интерфейса OpenCut.
5. Не перезаписывайте исходный MP4. Экспортируйте результат как `{package_id}-opencut-edited.mp4`.
6. Экспорт из OpenCut ещё не готов к публикации. Отдельно вручную проверьте текст и факты по
   утверждённому источнику, звук, субтитры и качество изображения. Автоматического возврата ролика
   из OpenCut и запуска Simba QA сейчас нет.

## Файлы пакета

{listed}
"""


def build_handoff(job_dir: str | os.PathLike[str], output_dir: str | os.PathLike[str]) -> Path:
    """Create a new OpenCut handoff directory without overwriting existing paths."""
    original_job = Path(job_dir).expanduser().absolute()
    if original_job.is_symlink() or not original_job.is_dir():
        raise HandoffError("job must be an existing regular directory, not a symlink")
    job = original_job.resolve()

    output_arg = Path(output_dir).expanduser().absolute()
    if output_arg.exists() or output_arg.is_symlink():
        raise HandoffError("output directory already exists; refusing to overwrite it")
    output_parent = output_arg.parent.resolve()
    output = output_parent / output_arg.name
    if output == job or output.is_relative_to(job):
        raise HandoffError("output directory must be outside the source job")

    spec = _read_json(job / "video-spec.json", "video-spec.json")
    timeline = _read_json(job / "timeline.json", "timeline.json")
    sources = _collect_sources(job, spec, timeline)
    package_id = spec["packageId"]

    output_parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output_parent))
    try:
        manifest_files = []
        for rel, (source, roles) in sources.items():
            destination = stage / Path(rel)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            manifest_files.append({
                "path": rel,
                "roles": sorted(roles),
                "size": destination.stat().st_size,
                "sha256": _sha256(destination),
            })

        instructions_name = "OPEN_IN_OPENCUT.md"
        instructions = _instructions(package_id, [entry["path"] for entry in manifest_files])
        instructions_path = stage / instructions_name
        instructions_path.write_text(instructions, encoding="utf-8", newline="\n")
        manifest_files.append({
            "path": instructions_name,
            "roles": ["manual OpenCut instructions"],
            "size": instructions_path.stat().st_size,
            "sha256": _sha256(instructions_path),
        })
        manifest = {
            "schema": "simba-opencut-handoff/v1",
            "package_id": package_id,
            "project_import": "manual",
            "flattened_final": f"{package_id}.mp4",
            "post_edit_qa_required": True,
            "post_edit_check": "manual",
            "files": manifest_files,
        }
        (stage / "opencut-handoff.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _publish_without_overwrite(stage, output)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    shutil.rmtree(stage, ignore_errors=True)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package a rendered Simba job for manual editing in OpenCut")
    parser.add_argument("--job", required=True, help="rendered Simba job directory")
    parser.add_argument("--output-dir", required=True, help="new handoff directory (must not exist)")
    args = parser.parse_args(argv)
    try:
        output = build_handoff(args.job, args.output_dir)
    except HandoffError as exc:
        parser.error(str(exc))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
