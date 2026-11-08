"""Local, offline-by-default rea-video adapter for Simba's Кадр."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
LAB = REPO.parent / 'video-lab'
PYTHON = LAB / '.venv-rea' / 'Scripts' / 'python.exe'


def environment():
    env = os.environ.copy()
    bins = sorted((LAB / 'tools').glob('ffmpeg*/bin'))
    if bins:
        env['PATH'] = str(bins[0]) + os.pathsep + env.get('PATH', '')
    env['PYTHONUTF8'] = '1'
    env['REA_VIDEO_HOME'] = str(LAB / '.cache' / 'kadr')
    env['REA_VIDEO_MODELS'] = str(LAB / '.cache' / 'kadr-models')
    # Do not pick up provider credentials or a user's paid-model preferences.
    for key in list(env):
        if key.startswith('REA_VLM_'):
            del env[key]
    return env


def run(args, env):
    subprocess.run([str(a) for a in args], env=env, check=True)


def new_job(path):
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


def resolve_source(source, job, env):
    url = urlparse(source)
    if url.scheme in ('http', 'https'):
        if url.hostname not in ('instagram.com', 'www.instagram.com') or not url.path.startswith(('/reel/', '/reels/', '/p/')):
            raise ValueError('Expected an Instagram Reel URL or a local video file.')
        run([PYTHON, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
             '--retries', '0', '--fragment-retries', '0', '--no-overwrites',
             '-f', 'b[ext=mp4]/b', '-o', job / 'reference.%(ext)s', '--', source], env)
        videos = list(job.glob('reference.*'))
        videos = [p for p in videos if p.suffix in ('.mp4', '.mkv', '.webm', '.mov')]
        if len(videos) != 1:
            raise RuntimeError('Download did not produce one video. Supply a local MP4.')
        return videos[0]
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def decompose(source, job, env, quick=False):
    args = [PYTHON, '-m', 'rea_video', 'decompose', source, '-o', job / 'analysis',
            '--no-vlm', '--lang', 'en']
    if quick:
        args += ['--no-stems', '--no-ocr']
    run(args, env)


def main():
    parser = argparse.ArgumentParser(description='Кадр: разбор рилса для Монтажера Клода')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    analyze = sub.add_parser('analyze')
    analyze.add_argument('source', help='Local MP4 or public Instagram Reel URL')
    analyze.add_argument('--output', required=True, type=Path, help='New job directory')
    analyze.add_argument('--quick', action='store_true', help='Skip OCR and stem separation')
    args = parser.parse_args()
    env = environment()
    try:
        if not PYTHON.is_file():
            raise RuntimeError(f'Python environment missing: {PYTHON}')
        for tool in ('ffmpeg', 'ffprobe'):
            if not shutil.which(tool, path=env['PATH']):
                raise RuntimeError(f'{tool} missing')
        if args.command == 'doctor':
            run([PYTHON, '-c', 'import rea_video, cv2, numpy, PIL, yaml, onnxruntime, yt_dlp, rapidocr_onnxruntime; print("KADR_TOOLS_READY")'], env)
            run([PYTHON, '-m', 'rea_video', '--help'], env)
            return 0
        job = new_job(args.output)
        source = resolve_source(args.source, job, env)
        (job / 'source.json').write_text(json.dumps({'source': args.source, 'file': str(source),
            'vlm': False, 'quick': args.quick, 'status': 'ANALYSIS_STARTED'}, ensure_ascii=False, indent=2), encoding='utf-8')
        decompose(source, job, env, args.quick)
        run([PYTHON, '-m', 'rea_video', 'summary', job / 'analysis' / 'breakdown.json'], env)
        run([PYTHON, '-m', 'rea_video', 'review', job / 'analysis'], env)
        print(f'KADR_ANALYSIS_READY_FOR_REVIEW: {job}')
        print('Next: inspect storyboard/shot images, apply review, then write Russian editor-advice.md using Кадр/KADR_v1.0.md.')
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'KADR_BLOCKED: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
