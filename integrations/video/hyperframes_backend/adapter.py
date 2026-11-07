"""Render a Simba timeline through the installed HyperFrames CLI.

This adapter deliberately renders video only.  The owning pipeline keeps its
existing ``audio.mix`` and final ffmpeg mux stages, so narration, clip audio,
ducking, loudness checks, and final-ASR checks stay authoritative.
"""

from __future__ import annotations

import copy
import json
import math
import os
import shutil
import subprocess
import uuid
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit


VIDEO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIRNAME = ".simba-hyperframes"
COMPOSITION = f"{PROJECT_DIRNAME}/index.html"
MARKER = "generated-by-simba-hyperframes-adapter-v1\n"


class HyperFramesRenderError(RuntimeError):
    """A clear, user-actionable HyperFrames adapter failure."""


def render(
    job: Path,
    plan: dict,
    fps: int,
    output: Path,
    ffmpeg: Path | None = None,
) -> None:
    """Render *plan* to an MP4 at *output* using HyperFrames.

    Success returns ``None`` and guarantees that ``output`` exists and is not
    empty.  Validation, setup, CLI, and output failures raise
    :class:`HyperFramesRenderError` (a ``RuntimeError`` subclass).

    The generated composition registers a deterministic root timeline (with
    ``hf-seek`` as a fallback) and drives Simba's existing pure
    ``window.render(time)`` implementation.
    Static images, code-drawn inserts, and extracted-frame clip scenes are
    supported.  For clips, ``window.__hfWaitForSeekCompletion`` exposes the
    pending ``window.prepare(time)`` promise to HyperFrames before capture.
    ``ffmpeg`` is optional for backward compatibility; when supplied, its path
    and an existing sibling ffprobe are passed only to the sanitized child
    environment.
    """

    job = Path(job).resolve()
    output = Path(output).resolve()
    checked = _validated_plan(job, plan, fps, output)
    project = _build_project(job, checked, fps)
    cli = _find_cli()
    node = _find_node()
    ffmpeg_path, ffprobe_path = _media_tool_paths(ffmpeg)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not output.is_file():
        raise HyperFramesRenderError(f"HyperFrames output is not a file: {output}")
    temporary_output = output.parent / f".{output.name}.hyperframes-{uuid.uuid4().hex}.mp4"

    command = [
        node,
        str(cli),
        "render",
        str(job),
        "--composition",
        COMPOSITION,
        "--output",
        str(temporary_output),
        "--format",
        "mp4",
        "--quality",
        "looks",
        "--fps",
        str(fps),
        "--workers",
        "1",
        "--no-best-effort",
        "--strict",
    ]
    env = _subprocess_environment(ffmpeg_path, ffprobe_path)
    try:
        try:
            result = subprocess.run(
                command,
                cwd=VIDEO_ROOT,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
        except OSError as exc:
            raise HyperFramesRenderError(f"could not start HyperFrames CLI: {exc}") from exc
        if result.returncode:
            tail = (result.stdout or "").strip()[-5000:]
            detail = f"\n{tail}" if tail else ""
            raise HyperFramesRenderError(
                f"HyperFrames render failed with exit code {result.returncode}.{detail}"
            )
        if not temporary_output.is_file() or temporary_output.stat().st_size <= 0:
            raise HyperFramesRenderError(
                "HyperFrames reported success but did not create a non-empty temporary output: "
                f"{temporary_output}"
            )
        _probe_video(temporary_output, float(checked["dur"]), fps, ffprobe_path)
        os.replace(temporary_output, output)
    finally:
        # This is the only path the adapter may delete.  A previous good output
        # remains untouched unless the new render reached the atomic replace.
        if temporary_output.is_file():
            temporary_output.unlink()
    # Keep the generated project beside the job for reproducibility/debugging.
    if not project.is_dir():  # defensive: the CLI must not remove our source project
        raise HyperFramesRenderError("HyperFrames removed the generated composition unexpectedly")


def _validated_plan(job: Path, plan: dict, fps: int, output: Path) -> dict:
    if not job.is_dir():
        raise HyperFramesRenderError(f"job directory does not exist: {job}")
    if not isinstance(plan, dict):
        raise HyperFramesRenderError("timeline plan must be a dictionary")
    if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 240:
        raise HyperFramesRenderError("fps must be an integer from 1 to 240")
    if output.suffix.lower() != ".mp4":
        raise HyperFramesRenderError("HyperFrames backend currently supports only .mp4 output")

    size = plan.get("size")
    if (
        not isinstance(size, (list, tuple))
        or len(size) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) for value in size)
        or any(value < 16 or value > 8192 or value % 2 for value in size)
    ):
        raise HyperFramesRenderError("plan.size must contain two even integers from 16 to 8192")
    duration = plan.get("dur")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or duration <= 0:
        raise HyperFramesRenderError("plan.dur must be a positive finite number")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise HyperFramesRenderError("plan.scenes must be a non-empty list")
    if plan.get("motion", "anime") not in {"anime", "classic"}:
        raise HyperFramesRenderError("plan.motion must be 'anime' or 'classic'")
    try:
        checked = copy.deepcopy(plan)
        json.dumps(checked, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise HyperFramesRenderError(f"timeline plan is not valid JSON: {exc}") from exc

    for scene_index, scene in enumerate(checked["scenes"]):
        if not isinstance(scene, dict):
            raise HyperFramesRenderError(f"plan.scenes[{scene_index}] must be an object")
        if scene.get("frames"):
            count = scene.get("count")
            scene_fps = scene.get("fps")
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                raise HyperFramesRenderError(f"plan.scenes[{scene_index}].count must be a positive integer")
            if not isinstance(scene_fps, (int, float)) or isinstance(scene_fps, bool) or not math.isfinite(scene_fps) or scene_fps <= 0:
                raise HyperFramesRenderError(f"plan.scenes[{scene_index}].fps must be positive")
            scene["frames"] = _asset_directory_url(
                job,
                scene["frames"],
                f"scenes[{scene_index}].frames",
                count,
            )
        elif not scene.get("insert"):
            if not scene.get("image"):
                raise HyperFramesRenderError(
                    f"plan.scenes[{scene_index}] needs image or insert"
                )
            scene["image"] = _asset_url(job, scene["image"], f"scenes[{scene_index}].image")

    offer = checked.get("offer")
    if offer is not None and not isinstance(offer, dict):
        raise HyperFramesRenderError("plan.offer must be an object or null")
    if offer and offer.get("bg"):
        offer["bg"] = _asset_url(job, offer["bg"], "offer.bg")

    end = checked.get("end")
    if not isinstance(end, dict):
        raise HyperFramesRenderError("plan.end must be an object")
    for field in ("poster", "bg"):
        if end.get(field):
            end[field] = _asset_url(job, end[field], f"end.{field}")
    return checked


def _asset_url(job: Path, raw: object, field: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise HyperFramesRenderError(f"plan.{field} must be a non-empty local path")
    value = raw.replace("\\", "/")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or value.startswith("/"):
        raise HyperFramesRenderError(f"plan.{field} must be a job-relative local path: {raw}")
    relative = Path(*PurePosixPath(value).parts)
    resolved = (job / relative).resolve()
    try:
        safe_relative = resolved.relative_to(job)
    except ValueError as exc:
        raise HyperFramesRenderError(f"plan.{field} points outside the job: {raw}") from exc
    if not resolved.is_file():
        raise HyperFramesRenderError(f"plan.{field} asset does not exist: {raw}")
    return "/" + quote(safe_relative.as_posix(), safe="/")


def _asset_directory_url(job: Path, raw: object, field: str, count: int) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise HyperFramesRenderError(f"plan.{field} must be a non-empty local directory")
    value = raw.replace("\\", "/").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or value.startswith("/"):
        raise HyperFramesRenderError(f"plan.{field} must be a job-relative local directory: {raw}")
    relative = Path(*PurePosixPath(value).parts)
    resolved = (job / relative).resolve()
    try:
        safe_relative = resolved.relative_to(job)
    except ValueError as exc:
        raise HyperFramesRenderError(f"plan.{field} points outside the job: {raw}") from exc
    if not resolved.is_dir():
        raise HyperFramesRenderError(f"plan.{field} directory does not exist: {raw}")
    first = resolved / "00001.jpg"
    last = resolved / f"{count:05d}.jpg"
    if not first.is_file() or not last.is_file():
        raise HyperFramesRenderError(
            f"plan.{field} must contain 00001.jpg through {count:05d}.jpg"
        )
    return "/" + quote(safe_relative.as_posix(), safe="/") + "/"


def _build_project(job: Path, plan: dict, fps: int) -> Path:
    project = job / PROJECT_DIRNAME
    marker = project / ".simba-generated"
    if project.exists():
        if not project.is_dir() or not marker.is_file() or marker.read_text(encoding="utf-8") != MARKER:
            raise HyperFramesRenderError(
                f"refusing to replace unrecognized project directory: {project}"
            )
        shutil.rmtree(project)
    runtime = project / "runtime"
    (runtime / "template").mkdir(parents=True)
    (runtime / "engine").mkdir(parents=True)
    (runtime / "fonts").mkdir(parents=True)
    project.mkdir(parents=True, exist_ok=True)
    marker.write_text(MARKER, encoding="utf-8")

    sources = {
        VIDEO_ROOT / "template" / "film.js": runtime / "template" / "film.js",
        VIDEO_ROOT / "template" / "inserts.js": runtime / "template" / "inserts.js",
        VIDEO_ROOT / "template" / "cartoon.js": runtime / "template" / "cartoon.js",
        VIDEO_ROOT / "engine" / "lib.js": runtime / "engine" / "lib.js",
        VIDEO_ROOT / "fonts" / "Montserrat.ttf": runtime / "fonts" / "Montserrat.ttf",
        VIDEO_ROOT / "fonts" / "PlayfairDisplay.ttf": runtime / "fonts" / "PlayfairDisplay.ttf",
    }
    missing = [str(source) for source in sources if not source.is_file()]
    anime_source = VIDEO_ROOT / "node_modules" / "animejs" / "dist" / "modules"
    if not anime_source.is_dir():
        missing.append(str(anime_source))
    if missing:
        raise HyperFramesRenderError(
            "HyperFrames project dependencies are missing; run npm install in "
            f"{VIDEO_ROOT}: " + ", ".join(missing)
        )

    replacements = {
        "fetch('timeline.json')": f"fetch('/{PROJECT_DIRNAME}/timeline.json')",
        "/engine/lib.js": f"/{PROJECT_DIRNAME}/runtime/engine/lib.js",
        "/node_modules/animejs/dist/modules/index.js": (
            f"/{PROJECT_DIRNAME}/runtime/node_modules/animejs/dist/modules/index.js"
        ),
        "/template/inserts.js": f"/{PROJECT_DIRNAME}/runtime/template/inserts.js",
        "/template/cartoon.js": f"/{PROJECT_DIRNAME}/runtime/template/cartoon.js",
    }
    for source, destination in sources.items():
        if source.suffix == ".js":
            text = source.read_text(encoding="utf-8")
            for old, new in replacements.items():
                text = text.replace(old, new)
            destination.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(source, destination)
    anime_destination = runtime / "node_modules" / "animejs" / "dist" / "modules"
    shutil.copytree(anime_source, anime_destination)

    (project / "timeline.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    width, height = plan["size"]
    duration = format(float(plan["dur"]), ".15g")
    html = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Simba HyperFrames render</title>
<style>
@font-face {{ font-family: "Montserrat"; src: url("/{PROJECT_DIRNAME}/runtime/fonts/Montserrat.ttf") format("truetype"); font-weight: 100 900; }}
@font-face {{ font-family: "Playfair Display"; src: url("/{PROJECT_DIRNAME}/runtime/fonts/PlayfairDisplay.ttf") format("truetype"); font-weight: 400 900; }}
html, body, main {{ width: 100%; height: 100%; margin: 0; overflow: hidden; background: #0E1B30; }}
canvas {{ display: block; }}
</style>
</head>
<body>
<main id="main" data-composition-id="simba-main" data-start="0" data-duration="{duration}" data-width="{width}" data-height="{height}" data-fps="{fps}">
  <canvas id="c"></canvas>
</main>
<script type="module">
  await import("/{PROJECT_DIRNAME}/runtime/template/film.js");
  if (window.READY !== true || typeof window.render !== "function") {{
    throw new Error("Simba film renderer did not become ready");
  }}
  let currentTime = 0;
  let seekGeneration = 0;
  const scheduleFrame = time => {{
    time = Number(time);
    if (!Number.isFinite(time)) throw new Error("HyperFrames supplied a non-finite seek time");
    currentTime = time;
    const generation = ++seekGeneration;
    window.__simbaPendingFrame = (async () => {{
      await window.prepare(time);
      if (generation === seekGeneration) window.render(time);
    }})();
    return window.__simbaPendingFrame;
  }};
  await scheduleFrame(0);
  const timeline = {{
    pause() {{ return this; }},
    play() {{ return this; }},
    seek(time) {{ scheduleFrame(time); return this; }},
    time(time) {{ if (arguments.length) {{ scheduleFrame(time); return this; }} return currentTime; }},
    totalTime(time) {{ if (arguments.length) {{ scheduleFrame(time); return this; }} return currentTime; }},
    progress(value) {{ if (arguments.length) {{ scheduleFrame(value * {duration}); return this; }} return currentTime / {duration}; }},
    duration() {{ return {duration}; }},
    totalDuration() {{ return {duration}; }},
    timeScale(value) {{ return arguments.length ? this : 1; }},
    repeat() {{ return 0; }},
    getChildren() {{ return []; }},
  }};
  window.__timelines = window.__timelines || {{}};
  window.__timelines["simba-main"] = timeline;
  window.addEventListener("hf-seek", event => {{
    const time = Number(event.detail?.time ?? 0);
    const pending = scheduleFrame(time);
    event.detail?.waitUntil?.(pending);
  }});
  let hyperframesRuntimeWaiter = null;
  const combinedSeekWaiter = async barrier => {{
    if (typeof hyperframesRuntimeWaiter === "function") {{
      await hyperframesRuntimeWaiter.call(window, barrier);
    }}
    await window.__simbaPendingFrame;
  }};
  Object.defineProperty(window, "__hfWaitForSeekCompletion", {{
    configurable: true,
    get() {{ return combinedSeekWaiter; }},
    set(waiter) {{ if (waiter !== combinedSeekWaiter) hyperframesRuntimeWaiter = waiter; }},
  }});
  window.__renderReady = true;
</script>
</body>
</html>
"""
    (project / "index.html").write_text(html, encoding="utf-8")
    return project


def _find_cli() -> Path:
    configured = os.environ.get("HYPERFRAMES_CLI")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.append(VIDEO_ROOT / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs")
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    raise HyperFramesRenderError(
        f"HyperFrames CLI is not installed; run npm install in {VIDEO_ROOT} "
        "or set HYPERFRAMES_CLI to hyperframes.mjs"
    )


def _find_node() -> str:
    configured = os.environ.get("NODE_BINARY")
    if configured:
        resolved = Path(configured).expanduser().resolve()
        if resolved.is_file():
            return str(resolved)
        raise HyperFramesRenderError(f"NODE_BINARY does not exist: {resolved}")
    node = shutil.which("node")
    if not node:
        raise HyperFramesRenderError("Node.js is required to run HyperFrames")
    return node


def _media_tool_paths(ffmpeg: Path | None) -> tuple[Path | None, Path | None]:
    if ffmpeg is None:
        return None, None
    ffmpeg_path = Path(ffmpeg).expanduser().resolve()
    if not ffmpeg_path.is_file():
        raise HyperFramesRenderError(f"explicit ffmpeg path does not exist: {ffmpeg_path}")
    ffprobe_name = "ffprobe.exe" if ffmpeg_path.suffix.lower() == ".exe" else "ffprobe"
    sibling_probe = ffmpeg_path.with_name(ffprobe_name)
    return ffmpeg_path, sibling_probe if sibling_probe.is_file() else None


def _probe_video(
    path: Path,
    expected_duration: float,
    fps: int,
    explicit_ffprobe: Path | None = None,
) -> None:
    """Validate the temporary MP4 when ffprobe is locally available."""

    configured = os.environ.get("HYPERFRAMES_FFPROBE_PATH")
    if explicit_ffprobe is not None:
        executable = str(explicit_ffprobe)
    elif configured:
        ffprobe = Path(configured).expanduser().resolve()
        if not ffprobe.is_file():
            raise HyperFramesRenderError(f"HYPERFRAMES_FFPROBE_PATH does not exist: {ffprobe}")
        executable = str(ffprobe)
    else:
        executable = shutil.which("ffprobe") or ""
    if not executable:
        return
    command = [
        executable,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_type:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            env=_subprocess_environment(),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise HyperFramesRenderError(f"could not start ffprobe: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "unknown ffprobe error").strip()[-1500:]
        raise HyperFramesRenderError(f"ffprobe rejected HyperFrames temporary output: {detail}")
    try:
        probe = json.loads(result.stdout)
        streams = probe.get("streams", [])
        duration = float(probe.get("format", {}).get("duration"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HyperFramesRenderError("ffprobe returned invalid metadata for HyperFrames output") from exc
    if not any(stream.get("codec_type") == "video" for stream in streams if isinstance(stream, dict)):
        raise HyperFramesRenderError("ffprobe found no video stream in HyperFrames output")
    tolerance = max(0.1, 1 / fps + 0.02)
    if not math.isfinite(duration) or duration <= 0 or abs(duration - expected_duration) > tolerance:
        raise HyperFramesRenderError(
            f"ffprobe duration mismatch: got {duration:.3f}s, expected {expected_duration:.3f}s "
            f"(tolerance {tolerance:.3f}s)"
        )


def _subprocess_environment(
    ffmpeg: Path | None = None,
    ffprobe: Path | None = None,
) -> dict[str, str]:
    """Build the minimum practical Node/Chrome environment without secrets."""

    system_names = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "HOME",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "COMMONPROGRAMFILES",
        "COMMONPROGRAMFILES(X86)",
        "NUMBER_OF_PROCESSORS",
        "PROCESSOR_ARCHITECTURE",
        "LD_LIBRARY_PATH",
        "XDG_CACHE_HOME",
    }
    tool_names = {
        "HYPERFRAMES_FFMPEG_PATH",
        "HYPERFRAMES_FFPROBE_PATH",
        "HYPERFRAMES_BROWSER_PATH",
        "HYPERFRAMES_EXTRACT_CACHE_DIR",
    }
    allowed = system_names | tool_names
    env = {name: value for name, value in os.environ.items() if name.upper() in allowed}
    env.update(
        {
            "HYPERFRAMES_NO_TELEMETRY": "1",
            "DO_NOT_TRACK": "1",
            "NO_COLOR": "1",
        }
    )
    if ffmpeg is not None:
        env["HYPERFRAMES_FFMPEG_PATH"] = str(ffmpeg)
    if ffprobe is not None:
        env["HYPERFRAMES_FFPROBE_PATH"] = str(ffprobe)
    return env
