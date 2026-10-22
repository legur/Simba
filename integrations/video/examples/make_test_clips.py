"""Stand-in "Grok clips" for testing: python make_test_clips.py <job_dir> <clips.json>
clips.json = [{"image": "6.webp", "out": "c1.mp4", "say": "…", "dur": 4}, …], images in <job_dir>.
Each clip is 720×1280 with a slow push-in, the line spoken by edge-tts and a quiet hum standing in for the clip's own
music, marked «ТЕСТОВЫЙ КЛИП». They only exercise the pipeline; never publish them."""
import asyncio, json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE)); sys.argv = sys.argv[:3]
import make_video as mv  # noqa: E402


def main(job, spec):
    import edge_tts
    job = Path(job); mv.FFMPEG = mv.find_ffmpeg(); f = ImageFont.truetype(str(HERE / 'fonts' / 'Montserrat.ttf'), 30)
    for c in json.loads(Path(spec).read_text(encoding='utf-8')):
        im = Image.open(job / c['image']).convert('RGB').resize((720, 1280)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([20, 1200, 330, 1250], 10, fill=(180, 30, 30)); d.text((34, 1208), 'ТЕСТОВЫЙ КЛИП', font=f, fill=(255, 255, 255))
        png = job / f'_{c["out"]}.png'; im.save(png)
        mp3 = job / f'_{c["out"]}.mp3'; asyncio.run(edge_tts.Communicate(c['say'], 'ru-RU-DmitryNeural', rate='-2%').save(str(mp3)))
        fr = int(c['dur'] * 24)
        mv.ff('-y', '-loglevel', 'error', '-loop', '1', '-i', str(png), '-i', str(mp3), '-f', 'lavfi', '-i', f'sine=f=220:d={c["dur"]}',
              '-filter_complex', f"[0:v]zoompan=z='min(zoom+0.0007,1.08)':d=1:s=720x1280:fps=24,format=yuv420p[v];"
              f"[1:a]adelay=400|400,apad[sp];[2:a]volume=0.02[hum];[sp][hum]amix=inputs=2:normalize=0[a]",
              '-map', '[v]', '-map', '[a]', '-frames:v', str(fr), '-t', str(c['dur']), '-c:v', 'libx264', '-crf', '20', '-c:a', 'aac', str(job / c['out']))
        png.unlink(); mp3.unlink(); print('clip ->', c['out'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
