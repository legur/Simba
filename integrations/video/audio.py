"""Score, foley and narration mix for a Simba photo-story → out/mix.wav (48 kHz stereo).
The score is synthesized (warm pad, harp arpeggios, soft bass); nothing is sampled, so there is nothing to license."""
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
import soxr

sys.path.insert(0, str(Path(__file__).resolve().parent / 'engine'))
import sfx  # noqa: E402
from sfx import SR, t_, noise, lp, hp, bp, norm  # noqa: E402

rng = np.random.default_rng(5)


def mtof(m): return 440 * 2 ** ((m - 69) / 12)


def place(buf, x, at, gain=1.0, pan=0.0): sfx.add(buf, x, at, gain, pan)


def pad(m, dur, v=1.0):
    f = mtof(m); tt = t_(dur + 1.2); x = np.zeros_like(tt)
    for det in (-.06, 0, .07):                                  # three detuned voices, soft saw (8 partials)
        for k in range(1, 9): x += np.sin(2 * np.pi * f * k * (1 + det / 100) * tt + rng.random() * 6) / k
    env = np.minimum(1, tt / .9) * np.where(tt < dur, 1, np.exp(-(tt - dur) / .45))
    return norm(lp(x, 1400)) * env * v


def harp(m, v=1.0, d=1.8):
    f = mtof(m); tt = t_(d); x = np.zeros_like(tt)
    for k in range(1, 7): x += np.sin(2 * np.pi * f * k * tt) / k ** 1.6 * np.exp(-tt * (1.2 + .7 * k))
    x[:144] *= np.linspace(0, 1, 144)
    return norm(x) * v


def bass(m, d, v=1.0):
    f = mtof(m); tt = t_(d + .3); x = np.zeros_like(tt)
    for k in range(1, 4): x += np.sin(2 * np.pi * f * k * tt) / k ** 1.4         # 2nd/3rd harmonics for small speakers
    env = np.minimum(1, tt / .03) * np.exp(-tt / 1.4) * np.where(tt < d, 1, np.exp(-(tt - d) / .1))
    return norm(lp(x, 500)) * env * v


def bell(m, v=1.0, d=2.2):
    f = mtof(m); tt = t_(d)
    x = np.sin(2 * np.pi * f * tt) * np.exp(-tt / 1.0) + .3 * np.sin(2 * np.pi * 4 * f * tt) * np.exp(-tt / .15) + .12 * np.sin(2 * np.pi * 2.76 * f * tt) * np.exp(-tt / .4)
    x[:96] *= np.linspace(0, 1, 96)
    return norm(x) * v


def score(tl, n):
    """84 bpm, D major, I–vi–IV–V per bar; harp enters after the hook, a brighter lift on the offer, resolution on the end card."""
    out = np.zeros((n, 2)); beat = 60 / 84; bar = 4 * beat; dur = tl['dur']
    chords = [(50, [62, 66, 69]), (47, [59, 62, 66]), (43, [55, 59, 62]), (45, [57, 61, 64])]   # D, Bm, G, A
    harp_from = tl['scenes'][0]['t1'] - .2 if len(tl['scenes']) > 1 else 2.0
    offer_t0 = tl['offer']['t0'] if tl.get('offer') else dur
    end_t0 = tl['end']['t0']
    k, t = 0, 0.0
    while t < end_t0 - .1:
        root, tones = chords[k % 4]; d = min(bar, end_t0 - t)
        for m in tones: place(out, pad(m, d, .16), t, 1, -.2 + .2 * tones.index(m))
        place(out, bass(root, d, .5), t)
        if t >= harp_from - 1e-6:
            pattern = [tones[0], tones[1], tones[2], tones[0] + 12, tones[2], tones[1], tones[0] + 12, tones[2] + 12]
            lift = 12 if t >= offer_t0 - 1e-6 else 0
            for i, m in enumerate(pattern):
                if t + i * beat / 2 < end_t0 - .05: place(out, harp(m + lift, .3 if i else .4), t + i * beat / 2, 1, -.4 + .1 * i)
        t += bar; k += 1
    # resolution on the end card: D major held to the end
    hold = dur - end_t0
    for m in (50, 57, 62, 66, 69, 74): place(out, pad(m, max(.5, hold - .8), .16), end_t0, 1, (m - 62) / 24)
    for i, m in enumerate((62, 66, 69, 74, 78)): place(out, harp(m, .35, 2.6), end_t0 + i * .11, 1, -.3 + .15 * i)
    place(out, bass(38, max(.5, hold - .5), .55), end_t0)
    return out


def guitar(m, v=1.0, d=1.2):
    """nylon-ish pluck: bright attack, quick upper-partial decay"""
    f = mtof(m); tt = t_(d); x = np.zeros_like(tt)
    for k in range(1, 9): x += np.sin(2 * np.pi * f * k * tt * (1 + .0007 * k)) / k ** 1.2 * np.exp(-tt * (2.2 + 1.6 * k))
    x[:72] *= np.linspace(0, 1, 72)
    return norm(lp(x, 4500)) * v


def lounge(tl, n, bpm=100):
    """light instrumental lounge: soft guitar comping, round bass, quiet shaker and rim; ends on a held chord"""
    out = np.zeros((n, 2)); beat = 60 / bpm; bar = 4 * beat; dur = tl['dur']
    chords = [(50, [61, 64, 66, 69]), (47, [57, 62, 66, 69]), (43, [59, 62, 66, 69]), (45, [55, 59, 64, 67])]   # Dmaj7 Bm7 Gmaj7 A7
    stop = dur - 2.4
    k, t = 0, 0.0
    while t < stop:
        root, tones = chords[k % 4]
        for hit in (0, 1.5, 2.5):                                   # bossa-ish comping, strummed
            if t + hit * beat < stop:
                for j, m in enumerate(tones): place(out, guitar(m, .32 - .03 * j), t + hit * beat + j * .012, 1, -.15 + .1 * j)
        for b, m in ((0, root), (2, root + 7)):
            if t + b * beat < stop: place(out, bass(m, beat * 1.6, .55), t + b * beat)
        for i in range(8):
            ts = t + i * beat / 2
            if ts < stop: place(out, norm(hp(noise(.05), 6000)) * np.exp(-t_(.05) / .012) * (.10 if i % 2 else .06), ts, 1, .35)
        for b in (1, 3):
            if t + b * beat < stop: place(out, sfx.click(1.3, .06), t + b * beat, 1, -.2)
        t += bar; k += 1
    for j, m in enumerate((50, 57, 61, 64, 66, 69)): place(out, guitar(m, .35, 3.0), stop + j * .03, 1, -.2 + .08 * j)
    place(out, bass(38, 2.0, .5), stop)
    for p in tl.get('plucks', []): place(out, guitar(p.get('note', 74), .45, .5), p['t'], 1, .3)   # comic string pluck cues
    return out


def foley(tl, n):
    out = np.zeros((n, 2))
    for s in tl['scenes'][1:]:
        place(out, lp(sfx.whoosh(.6, .35), 2500), s['t0'] - .35)
    if tl.get('offer'):
        place(out, lp(sfx.whoosh(.7, .4), 2500), tl['offer']['t0'] - .4)
        place(out, bell(86, .45), tl['offer']['price_t'], 1, .2)
    place(out, lp(sfx.whoosh(.7, .35), 2200), tl['end']['t0'] - .4)
    place(out, sfx.thump(.35, 60), tl['end']['t0'] + .1)
    return out


def mix(job: Path, tl: dict) -> Path:
    n = int(tl['dur'] * SR) + SR
    style = tl.get('music', {}).get('style', 'calm')
    music = lounge(tl, n, tl['music'].get('bpm', 100)) if style == 'lounge' else score(tl, n)
    fol, voice = foley(tl, n), np.zeros((n, 2))
    duck = np.zeros(n)
    def voiced(path):
        y, sr = sf.read(path, dtype='float64')
        if y.ndim > 1: y = y.mean(1)
        y = soxr.resample(y, sr, SR); y = hp(sfx.compress(norm(y), thr=.3, ratio=3.0), 90)
        return y / np.sqrt(np.mean(y[np.abs(y) > .02] ** 2))
    for L in tl['lines']:
        s = int((L['t0'] - .15) * SR)
        if L.get('fromClip'):                                    # spoken inside a clip: its sound is placed whole below
            duck[max(0, s):s + int((L['dur'] + .65) * SR)] = 1; continue
        y = voiced(job / 'voice' / f"{L['id']}.wav"); place(voice, y, L['t0'])
        duck[max(0, s):s + len(y) + int(.5 * SR)] = 1
    for c in tl.get('clipAudio', []):                            # a clip's own sound (its voice, lip-synced)
        place(voice, voiced(job / c['file']), c['t0'])
    k = int(.15 * SR); duck = np.convolve(duck, np.ones(k) / k, 'same')
    music *= (1 - .65 * duck)[:, None]; fol *= (1 - .4 * duck)[:, None]          # music ≈0.35× under the voice
    bed = music * .5 + fol * .5
    under = duck > .5
    ref = np.sqrt(np.mean(bed[under] ** 2)) if under.any() else .05
    out = bed + voice * max(ref, 1e-3) * 10 ** (10 / 20)                        # voice ≈10 dB above the bed under it
    tt = np.arange(n) / SR
    out *= np.clip((tl['dur'] - tt) / .5, 0, 1)[:, None]
    out = out[:int(tl['dur'] * SR)]
    out = np.stack([sfx.limit(out[:, c] / np.abs(out).max() * .9, .89) for c in (0, 1)], 1)
    path = job / 'out' / 'mix.wav'; path.parent.mkdir(exist_ok=True)
    sf.write(path, out.astype(np.float32), SR, subtype='PCM_24')
    return path
