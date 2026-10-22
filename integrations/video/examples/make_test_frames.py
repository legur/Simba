"""Stand-in frames for testing the pipeline without Rafael: python make_test_frames.py <job_dir>
Draws four 1080×1920 landscape scenes and a 1:1 poster, each marked as a test frame. Never publish them."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = Path(__file__).resolve().parents[1] / 'fonts' / 'Montserrat.ttf'
rng = np.random.default_rng(3)


def ridge(w, base, amp, rough, seed):
    r = np.random.default_rng(seed); x = np.arange(w); y = np.zeros(w)
    for k in range(1, 7):
        y += amp / k ** rough * np.sin(x / w * np.pi * (k + r.random() * 2) + r.random() * 6)
    return base - np.abs(y)


def landscape(w, h, sky, water, seed, ship=None, falls=None, town=None):
    im = Image.new('RGB', (w, h)); px = np.zeros((h, w, 3))
    t = np.linspace(0, 1, h)[:, None]
    px[:] = (np.array(sky[0]) * (1 - t) + np.array(sky[1]) * t)[:, None, :][:, 0, None, :]
    im = Image.fromarray(px.astype(np.uint8)); d = ImageDraw.Draw(im)
    horizon = int(h * .58)
    for i, (col, base, amp) in enumerate([((70, 96, 110), .30, .22), ((46, 70, 78), .40, .26), ((30, 50, 52), .50, .2)]):
        y = ridge(w, h * base + horizon * .25, h * amp, 1.2, seed + i)
        d.polygon([(0, horizon)] + [(x, min(horizon, y[x])) for x in range(0, w, 6)] + [(w, horizon)], fill=col)
    if falls:
        for fx in falls: d.rectangle([fx, horizon - 520, fx + 14, horizon], fill=(225, 235, 240))
    if town:
        for k in range(26):
            x0 = 60 + k * 38; hh = 60 + (k * 37 % 70)
            d.rectangle([x0, horizon - hh, x0 + 30, horizon], fill=[(196, 70, 52), (230, 210, 170), (180, 130, 70), (240, 240, 230)][k % 4])
    d.rectangle([0, horizon, w, h], fill=water)
    refl = im.crop((0, horizon - 400, w, horizon)).transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(6))
    im.paste(Image.blend(Image.new('RGB', refl.size, water), refl, .45), (0, horizon))
    if ship:
        sx, sy, s = ship
        d.polygon([(sx, sy), (sx + 300 * s, sy), (sx + 270 * s, sy + 40 * s), (sx + 20 * s, sy + 40 * s)], fill=(245, 245, 245))
        d.rectangle([sx + 60 * s, sy - 60 * s, sx + 220 * s, sy], fill=(240, 240, 240))
        d.rectangle([sx + 140 * s, sy - 100 * s, sx + 175 * s, sy - 60 * s], fill=(230, 190, 40))
    return im


def mark(im, text='ТЕСТОВЫЙ КАДР · заменить кадром Рафаэля'):
    d = ImageDraw.Draw(im); f = ImageFont.truetype(str(FONT), 26)
    d.rounded_rectangle([24, 24, 24 + d.textlength(text, font=f) + 28, 70], 10, fill=(180, 30, 30))
    d.text((38, 30), text, font=f, fill=(255, 255, 255))
    return im


def main(job):
    job = Path(job); job.mkdir(parents=True, exist_ok=True); W, H = 1080, 1920
    mark(landscape(W, H, [(250, 214, 160), (150, 190, 215)], (40, 80, 100), 1, ship=(560, 1090, 1.0))).save(job / 's1.png')
    mark(landscape(W, H, [(200, 220, 235), (120, 160, 180)], (30, 70, 80), 7, falls=[300, 690])).save(job / 's2.png')
    mark(landscape(W, H, [(120, 170, 220), (220, 230, 240)], (30, 80, 120), 11, ship=(140, 1060, 2.4))).save(job / 's3.png')
    mark(landscape(W, H, [(240, 190, 140), (160, 180, 210)], (50, 80, 110), 17, town=True)).save(job / 's4.png')
    p = landscape(1080, 1080, [(250, 214, 160), (120, 160, 190)], (30, 70, 90), 23, ship=(600, 640, .8))
    d = ImageDraw.Draw(p); f = ImageFont.truetype(str(FONT), 64); f.set_variation_by_axes([800])
    d.text((540, 180), 'ТЕСТОВЫЙ ПОСТЕР', font=f, fill=(255, 255, 255), anchor='mm')
    mark(p).save(job / 'final.png')
    print('test frames ->', job)


if __name__ == '__main__':
    main(sys.argv[1])
