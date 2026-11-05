"""External music importer for Simba videos.

The Music Editor clears the music rights; this module only decodes and mixes it.
Never downloads third-party tracks, validates licenses by itself, or spends credits.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'}
AUDIO_SR = 48000


def validate_music(job: Path, music: dict | None) -> Path | None:
    """Validate relative source file and numeric mix controls before rendering."""
    if music is None:
        return None
    if not isinstance(music, dict):
        raise ValueError('music must be an object')
    if 'file' not in music:
        return None  # existing synthesized score is the default
    value = music['file']
    if not isinstance(value, str) or not value.strip():
        raise ValueError('music.file must be a nonempty relative audio filename')
    if music.get('rights_confirmed') is not True:
        raise ValueError('music.rights_confirmed=true is required after Music Editor license review')
    rel = Path(value)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('music.file must stay inside the job folder')
    if rel.suffix.lower() not in AUDIO_EXTENSIONS:
        raise ValueError('music.file must be MP3, WAV, M4A, AAC, FLAC or OGG')
    root = job.resolve()
    source = (root / rel).resolve()
    if not source.is_relative_to(root):
        raise ValueError('music.file cannot point outside the job folder')
    if not source.is_file():
        raise ValueError(f'music.file not found in job: {value}')
    if source.stat().st_size == 0:
        raise ValueError('music.file is empty')
    if source.stat().st_size > 200 * 1024 * 1024:
        raise ValueError('music.file exceeds the 200 MB limit')
    for field, default, lo, hi in (
        ('start_s', 0, 0, 3600), ('gain_db', -8, -36, 6),
        ('fade_in_s', 0.35, 0, 10), ('fade_out_s', 0.8, 0, 10),
    ):
        val = music.get(field, default)
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or not lo <= val <= hi:
            raise ValueError(f'music.{field} must be a finite number from {lo} to {hi}')
    if not isinstance(music.get('loop', False), bool):
        raise ValueError('music.loop must be true or false')
    return source


def prepare_music(job: Path, music: dict, duration: float, ffmpeg: str) -> Path:
    """Transcode an in-job audio file to a 48 kHz stereo WAV of film length.

    Short tracks are not repeated without an explicit loop=true.
    """
    source = validate_music(job, music)
    if source is None:
        raise ValueError('music.file is required for external music')
    if not 0 < duration <= 60:
        raise ValueError('video duration must be 0–60 seconds')
    target = job / 'out' / 'external-music.wav'
    target.parent.mkdir(exist_ok=True, parents=True)
    cmd = [ffmpeg, '-hide_banner', '-nostdin', '-y', '-loglevel', 'error']
    if music.get('loop', False):
        cmd += ['-stream_loop', '-1']
    cmd += ['-ss', f'{music.get("start_s", 0):.3f}', '-i', str(source), '-vn']
    if music.get('loop', False):
        cmd += ['-af', 'asetpts=N/SR/TB,apad']  # fix small MP3 loop timestamp gaps
    cmd += ['-t', f'{duration:.3f}', '-ar', str(AUDIO_SR), '-ac', '2',
            '-c:a', 'pcm_f32le', str(target)]
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired as exc:
        raise ValueError('music decode timed out') from exc
    if process.returncode != 0 or not target.is_file():
        raise ValueError('music decode failed: ' + (process.stderr.strip().splitlines() or ['unknown ffmpeg error'])[-1])
    info = sf.info(target)
    if info.samplerate != AUDIO_SR or info.channels != 2 or info.frames < int(duration * AUDIO_SR) - 4096:
        raise ValueError('music is shorter than the video: choose a longer track or set music.loop=true')
    return target


def external_music_bed(job: Path, music: dict, duration: float, n: int, sr: int) -> np.ndarray:
    """Load predecoded WAV, applying segment fades and gain without normalization.

    The main audio.mix() adds clip voices/foley and applies speech ducking.
    """
    source = job / 'out' / 'external-music.wav'
    if not source.is_file():
        raise ValueError('external music WAV missing: prepare_music was not run')
    y, actual_sr = sf.read(source, dtype='float64', always_2d=True)
    needed = int(round(duration * sr))
    if actual_sr != sr or y.shape[1] != 2 or len(y) < needed - 4096:
        raise ValueError('external music WAV has wrong format or duration')
    result = np.zeros((n, 2), dtype=np.float64)
    count = min(len(y), needed, n)
    if count == 0:
        raise ValueError('external music WAV is empty')
    if not np.isfinite(y).all():
        raise ValueError('external music contains non-finite audio samples')
    result[:count] = y[:count]
    t = np.arange(count, dtype=np.float64) / sr
    fi, fo = music.get('fade_in_s', 0.35), music.get('fade_out_s', 0.8)
    if fi:
        result[:count] *= np.minimum(1.0, t / fi)[:, None]
    if fo:
        result[:count] *= np.minimum(1.0, np.maximum(0, duration - t) / fo)[:, None]
    result *= 10 ** (music.get('gain_db', -8) / 20)
    return result
