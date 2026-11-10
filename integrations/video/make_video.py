"""Simba video: approved post + Rafael frames + Scenarist lines → a vertical photo-story video of up to 60 s.

    python integrations/video/make_video.py <job_dir> [--fps 24] [--no-final-asr]

<job_dir> holds video-spec.json (see README.md) and the images it names. Results go to <job_dir>:
<packageId>.mp4, <packageId>.srt, cover.jpg, qa-report.md (and the working files in voice/ and out/).
Every gate stops the build with a reason: unapproved source, a number on screen that is not in the approved
text, a line the speech check cannot hear back, text on screen too short to read, a film over the limit.
"""
import argparse, asyncio, difflib, glob, hashlib, json, os, re, shutil, subprocess, sys, unicodedata
from pathlib import Path

for _s in (sys.stdout, sys.stderr): _s.reconfigure(encoding='utf-8', errors='replace')   # Windows consoles default to a code page
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MAX_DUR = 60.0
CROSSFADE = .6


class Stop(Exception):
    pass


def log(*a): print('·', *a, flush=True)


# ---------------------------------------------------------------- tools
def find_ffmpeg():
    exe = shutil.which('ffmpeg')
    if exe: return exe
    local = os.environ.get('LOCALAPPDATA', '')
    for pat in (r'Microsoft\WinGet\Links\ffmpeg.exe', r'Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe'):
        hits = glob.glob(os.path.join(local, pat))
        if hits: return hits[0]
    raise Stop('ffmpeg not found: install it (winget install Gyan.FFmpeg) or put it on PATH')


FFMPEG = None
def ff(*args, capture=False):
    r = subprocess.run([FFMPEG, '-hide_banner', *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0: raise Stop('ffmpeg failed: ' + (r.stderr.strip().splitlines() or ['?'])[-1])
    return r.stderr if capture else None


def node(script, *args):
    env = dict(os.environ, PATH=os.path.dirname(FFMPEG) + os.pathsep + os.environ.get('PATH', ''))
    r = subprocess.run(['node', str(HERE / 'engine' / 'render' / script), *map(str, args)], cwd=HERE, env=env,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout + r.stderr).strip()


# ---------------------------------------------------------------- spec
MOVES = {'push', 'pull', 'pan-left', 'pan-right', 'rise', 'hold', 'none'}
MOTIONS = {'anime', 'classic'}
RENDERERS = {'simba', 'hyperframes'}
# Motion Lab transition ids are mirrored in template/transitions.js.
TRANSITIONS = {'crossfade', 'push', 'zoom', 'whip', 'circle', 'diagonal', 'flash',
               'blur', 'flip', 'parallax', 'shutter', 'glitch', 'split', 'rotate',
               'tiles', 'portal', 'textmask', 'lightleak', 'speedramp', 'particles',
               'ripple', 'map', 'postcard', 'filmstrip', 'pagecurl', 'luma',
               'foreground', 'mask', 'morph', 'match'}
VIDEO_EXT = ('.mp4', '.mov', '.m4v', '.webm')
INSERTS = {'route', 'cartoon'}   # code-drawn scenes in template/inserts.js

def load_spec(job: Path):
    p = job / 'video-spec.json'
    if not p.is_file(): raise Stop(f'no video-spec.json in {job}')
    s = json.loads(p.read_text(encoding='utf-8'))
    need = lambda c, m: None if c else (_ for _ in ()).throw(Stop('video-spec.json: ' + m))
    need(isinstance(s.get('packageId'), str) and re.fullmatch(r'[\w.-]+', s['packageId']), 'packageId: letters, digits, . _ - only')
    need(isinstance(s.get('sourcePost'), str), 'sourcePost: path of the APPROVED post, relative to the repository root')
    need(isinstance(s.get('renderer', 'simba'), str) and s.get('renderer', 'simba') in RENDERERS,
         f'renderer must be one of {sorted(RENDERERS)}')
    s.setdefault('renderer', 'simba')
    if s['renderer'] == 'hyperframes':
        need((HERE / 'node_modules' / 'hyperframes' / 'bin' / 'hyperframes.mjs').is_file(),
             'HyperFrames is not installed; run npm ci in integrations/video before rendering')
    need(isinstance(s.get('motion', 'anime'), str) and s.get('motion', 'anime') in MOTIONS,
         f'motion must be one of {sorted(MOTIONS)}')
    s.setdefault('motion', 'anime')
    need(isinstance(s.get('scenes'), list) and 1 <= len(s['scenes']) <= 8, 'scenes: 1–8 scenes')
    for i, sc in enumerate(s['scenes']):
        transition = sc.get('transition')
        if transition is not None:
            need(i > 0, 'scene 1: transition is only valid on an incoming scene')
            need(isinstance(transition, dict), f'scene {i + 1}: transition must be an object')
            need(isinstance(transition.get('id'), str) and transition['id'] in TRANSITIONS,
                 f'scene {i + 1}: transition.id must be one of {sorted(TRANSITIONS)}')
            ms = transition.get('duration_ms', 900)
            need(type(ms) is int and 400 <= ms <= 2400,
                 f'scene {i + 1}: transition.duration_ms must be an integer from 400 to 2400')
            sc['transition'] = {'id': transition['id'], 'duration_ms': ms}
        src = sc.get('clip') or sc.get('image') or ''
        if sc.get('insert'):
            need(sc['insert'].get('type') in INSERTS, f'scene {i + 1}: insert type must be one of {sorted(INSERTS)}')
            sc.setdefault('move', 'none'); continue
        need((job / src).is_file(), f'scene {i + 1}: "clip" or "image" file not found in the job folder: {src!r}')
        if sc.get('clip'):
            need(sc['clip'].lower().endswith(VIDEO_EXT), f'scene {i + 1}: clip must be one of {VIDEO_EXT}')
            sc.setdefault('move', 'none'); sc.setdefault('voice', 'tts')
            need(sc['voice'] in ('tts', 'clip'), f'scene {i + 1}: voice must be "tts" or explicit "clip"')
        need(sc.get('move', 'push') in MOVES, f'scene {i + 1}: move must be one of {sorted(MOVES)}')
        need(all(isinstance(l.get('text'), str) and l['text'].strip() for l in sc.get('lines', [])), f'scene {i + 1}: every line needs "text"')
    o = s.get('offer')
    if o: need(isinstance(o.get('title'), str) and isinstance(o.get('price'), str), 'offer: needs "title" and "price"')
    e = s.setdefault('end', {})
    if e.get('poster'): need((job / e['poster']).is_file(), f'end.poster not found: {e["poster"]!r}')
    e.setdefault('brand', 'Simba by Bon Tours')
    w, h = map(int, s.get('size', '1080x1920').split('x')); s['size'] = f'{w}x{h}'
    need(w % 2 == 0 and h % 2 == 0, 'size: even numbers')
    # Fail before rendering when the chosen local soundtrack is absent, unsafe or
    # lacks an explicit rights attestation from the Music Editor.
    import music_input
    try:
        music_input.validate_music(job, s.get('music'))
    except ValueError as exc:
        raise Stop('video-spec.json: ' + str(exc)) from exc
    return s


def all_lines(s):
    for sc in s['scenes']: yield from sc.get('lines', [])
    yield from (s.get('offer') or {}).get('lines', [])
    yield from s['end'].get('lines', [])


def screen_texts(s):
    for sc in s['scenes']:
        if sc.get('title'): yield sc['title']
        ins = sc.get('insert') or {}
        yield from [ins.get('title', ''), *ins.get('rows', []), *(k[2] for k in ins.get('path', []) if len(k) > 2)]
    o = s.get('offer')
    if o: yield from [o['title'], *o.get('rows', []), o['price'], o.get('note', '')]
    yield from [s['end'].get('cta', ''), s['end'].get('contact', ''), s['end']['brand']]
    tb = s['end'].get('table') or {}
    yield from [tb.get('title', ''), tb.get('sub', ''), tb.get('note', ''), *(x for r in tb.get('rows', []) for x in r)]
    for l in all_lines(s): yield l['text']


# ---------------------------------------------------------------- gates on the approved source
APPROVAL_LINE = re.compile(r'^(?:STATUS|Статус):\s*APPROVED(?:\s*$|\s*[·,])', re.M)


def parse_approved_source(md):
    """Return (approved body, approval state) for current and legacy posts.

    Current posts delimit the approved copy with ``## APPROVED_TEXT`` (or the
    older ``## TEXT`` alias). Legacy Content Library posts put an explicit
    approval line in their metadata block and start the copy after the next
    blank line. Free-form mentions of APPROVED elsewhere are not accepted.
    """
    approved_match = APPROVAL_LINE.search(md)
    approved = approved_match is not None
    section = re.search(r'^## (?:APPROVED_TEXT|TEXT)\s*$(.*?)(?=^## |\Z)', md, re.M | re.S)
    if section:
        return section.group(1), approved
    if not approved_match:
        return None, False

    tail = md[approved_match.end():]
    separator = re.search(r'(?:\r?\n)[ \t]*(?:\r?\n)', tail)
    if not separator:
        return None, True
    body = tail[separator.end():]
    return (body if body.strip() else None), True


def approved_text(spec, draft=False):
    """The approved post text. With --draft a not-yet-approved text is accepted (a preview for Leo, never for publication)."""
    p = REPO / spec['sourcePost']
    if not p.is_file(): raise Stop(f'sourcePost not found: {spec["sourcePost"]}')
    md = p.read_text(encoding='utf-8')
    source, approved = parse_approved_source(md)
    if not approved and not draft: raise Stop(f'{spec["sourcePost"]} is not STATUS: APPROVED; a video is made only from an approved post (--draft makes a preview that is not for publication)')
    if source is None: raise Stop(f'{spec["sourcePost"]} has no approved text body')
    return source, approved


NUM = re.compile(r'[$€₪]?\s?\d[\d\s.,:/\-–]*\d|[$€₪]?\d')
def squash(s): return re.sub(r'[\s\u00a0]', '', s).replace('–', '-')

def fact_gate(spec, source):
    """Every number on screen or in the subtitles must appear, as written, in the approved text."""
    src, bad = squash(source), []
    for txt in screen_texts(spec):
        for m in NUM.finditer(txt or ''):
            tok = squash(m.group()).strip('.,:-/')
            if tok and tok not in src: bad.append(f'{tok!r} in {txt!r}')
    if bad: raise Stop('numbers not found in the approved text (prices, dates and contacts are copied, never derived):\n  ' + '\n  '.join(bad))
    return 'PASS'


# ---------------------------------------------------------------- voice: approved Simba Gemini by default; Edge only explicit
def voice_provider(spec):
    setting = spec.get('voice') or {}
    if not isinstance(setting, dict):
        raise Stop('video-spec.json: voice must be an object')
    provider = setting.get('provider', 'simba')
    if provider not in ('simba', 'edge'):
        raise Stop('video-spec.json: voice.provider must be "simba" or explicit "edge"')
    return provider


def tts(spec, job):
    import numpy as np, soundfile as sf
    vdir = job / 'voice'; (vdir / '.cache').mkdir(parents=True, exist_ok=True)
    lines = list(all_lines(spec))
    for i, L in enumerate(lines):
        L['id'] = f'l{i + 1:02d}'
    spoken = [L for L in lines if not L.get('fromClip')]
    if not spoken:
        return
    provider = voice_provider(spec)
    voice_setting = spec.get('voice') or {}

    if provider == 'simba':
        import simba_voice
        try:
            voices = simba_voice.synthesize_lines(spoken, vdir / '.cache',
                                                 allow_fallback=voice_setting.get('allow_fallback', True),
                                                 selected_model=voice_setting.get('model'))
        except simba_voice.VoiceError as exc:
            raise Stop('Simba approved voice: ' + str(exc)) from None
        for L in spoken:
            wav = vdir / f'{L["id"]}.wav'
            ff('-y', '-loglevel', 'error', '-i', str(voices[L['id']]),
               '-ar', '24000', '-ac', '1', str(wav))
    else:
        import edge_tts
        voice = voice_setting.get('name', 'ru-RU-DmitryNeural')
        rate = voice_setting.get('rate', '-4%')
        for L in spoken:
            say = L.get('say', L['text']); line_rate = L.get('rate', rate)
            key = hashlib.sha1(json.dumps([voice, line_rate, say], ensure_ascii=False).encode()).hexdigest()[:16]
            mp3 = vdir / '.cache' / f'{key}.mp3'
            if not mp3.is_file() or mp3.stat().st_size == 0:
                part = mp3.with_suffix('.part')
                for attempt in range(6):
                    try:
                        asyncio.run(edge_tts.Communicate(say, voice, rate=line_rate).save(str(part)))
                        part.replace(mp3)
                        break
                    except Exception as e:
                        part.unlink(missing_ok=True)
                        if attempt == 5:
                            raise Stop(f'edge-tts failed for line {L["id"]} ({type(e).__name__}: {str(e)[:160]}); it needs an internet connection')
                        import time
                        time.sleep(3 * (attempt + 1))
            wav = vdir / f'{L["id"]}.wav'
            ff('-y', '-loglevel', 'error', '-i', str(mp3),
               '-ar', '24000', '-ac', '1', str(wav))

    for L in spoken:
        wav = vdir / f'{L["id"]}.wav'
        y, sr = sf.read(wav, dtype='float32')
        if y.ndim > 1: y = y.mean(axis=1)
        peak = np.max(np.abs(y)) if len(y) else 0
        if peak < 1e-6:
            raise Stop(f'silent speech audio on line {L["id"]}: do not substitute a different voice')
        nz = np.flatnonzero(np.abs(y) > peak * .02)
        if len(nz) == 0:
            raise Stop(f'no audible speech on line {L["id"]}')
        y = y[max(0, nz[0] - int(.03 * sr)):nz[-1] + int(.1 * sr)]
        sf.write(wav, y, sr)
        L['dur'] = round(len(y) / sr, 3)
        hop = sr // 30
        rms = np.array([np.sqrt(np.mean(y[k:k + hop] ** 2)) for k in range(0, len(y), hop)])
        rms = np.convolve(rms / (np.percentile(rms, 90) + 1e-9), [.25, .5, .25], 'same')
        L['env'] = [round(float(v), 2) for v in np.clip((rms - .12) * 1.25, 0, 1)]
        log(L['id'], f'{L["dur"]:.2f}s', L['text'])



def norm_chars(s):
    s = unicodedata.normalize('NFKC', s).lower().replace('ё', 'е')
    return ''.join(c for c in s if unicodedata.category(c)[0] in 'LN')

_W = None
def whisper():
    global _W
    if _W is None:
        from faster_whisper import WhisperModel
        _W = WhisperModel('small', compute_type='int8')
    return _W

def transcribe(wav):
    """→ (heard text, [(word, start, end)], [(segment text, start, end)]); 0.6 s of silence is padded on both sides first."""
    import numpy as np, soundfile as sf
    y, sr = sf.read(wav, dtype='float32')
    if y.ndim > 1: y = y.mean(1)
    pad = np.zeros(int(.6 * 16000), np.float32); y16 = np.interp(np.arange(0, len(y), sr / 16000), np.arange(len(y)), y).astype(np.float32)
    segs, _ = whisper().transcribe(np.concatenate([pad, y16, pad]), language='ru', beam_size=5, word_timestamps=True)
    words, heard, sents = [], '', []
    for sg in segs:
        heard += sg.text; sents.append((sg.text.strip(), max(0.0, sg.start - .6), max(0.0, sg.end - .6)))
        words += [(w.word.strip(), max(0.0, w.start - .6), max(0.0, w.end - .6)) for w in (sg.words or [])]
    return heard.strip(), words, sents

def asr_check(spec, job, threshold=.9):
    """Whisper hears every synthesized line back; also gives word timings for the karaoke subtitles."""
    rows, bad = [], 0
    for L in all_lines(spec):
        if L.get('fromClip'): continue
        heard, words, _ = transcribe(job / 'voice' / f'{L["id"]}.wav')
        want = L.get('asr', L['text'])
        r = difflib.SequenceMatcher(None, norm_chars(want), norm_chars(heard), autojunk=False).ratio()
        ok = r >= threshold; bad += not ok
        L['heard'], L['asrRatio'], L['asrWords'] = heard.strip(), round(r, 3), words
        rows.append(f'{"OK  " if ok else "DIFF"} {L["id"]} {r:.2f} | {want} → {heard.strip()}')
        log(rows[-1])
    if bad: raise Stop(f'speech check: {bad} line(s) do not sound like their text (fix "say", or put the right transcription in "asr" after listening)')
    return rows


def karaoke(L, t0):
    """Subtitle words with start times: whisper word timings mapped onto the subtitle's own words by character position."""
    toks = L['text'].split()
    aw = L.get('asrWords') or []
    if not aw: return [[w, t0 + L['dur'] * i / len(toks)] for i, w in enumerate(toks)]
    tot = sum(len(norm_chars(w[0])) or 1 for w in aw); acc, marks = 0, []
    for w, s, e in aw:
        n = len(norm_chars(w)) or 1; marks.append((acc / tot, s)); acc += n
    stot = sum(len(norm_chars(w)) or 1 for w in toks); acc, out = 0, []
    for w in toks:
        f = acc / stot; acc += len(norm_chars(w)) or 1
        j = max(i for i, (mf, _) in enumerate(marks) if mf <= f + 1e-9)
        out.append([w, round(t0 + marks[j][1], 3)])
    return out


# ---------------------------------------------------------------- video clips (Grok and the like)
def clip_info(path):
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', str(path)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', r.stderr)
    if not m: raise Stop(f'cannot read the clip {path.name} (ffmpeg found no duration)')
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]), bool(re.search(r'Stream #.*Audio:', r.stderr))


def prepare_clips(spec, job, fps):
    """Clip scenes: frames → out/frames/sNN/%05d.jpg at the film's size and fps (cover-cropped), audio → voice/clipNN.wav."""
    w, h = map(int, spec['size'].split('x'))
    for i, sc in enumerate(spec['scenes']):
        if not sc.get('clip'): continue
        src = job / sc['clip']; full, has_audio = clip_info(src)
        a = float(sc.get('in', 0)); b = min(float(sc.get('out', full)), full)
        if b - a < .5: raise Stop(f'scene {i + 1}: clip {sc["clip"]} is shorter than 0.5 s after in/out')
        d = job / 'out' / 'frames' / f's{i + 1:02d}'; shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
        ff('-y', '-loglevel', 'error', '-ss', f'{a:.3f}', '-t', f'{b - a:.3f}', '-i', str(src),
           '-vf', f'fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}', '-q:v', '3', str(d / '%05d.jpg'))
        n = len(list(d.glob('*.jpg')))
        sc['_clip'] = {'frames': f'out/frames/s{i + 1:02d}/', 'count': n, 'fps': fps, 'dur': round(n / fps, 3), 'audio': None}
        if sc['voice'] == 'clip':
            if not has_audio: raise Stop(f'scene {i + 1}: clip {sc["clip"]} has no sound, but "voice" is "clip" (set "voice": "tts" to speak its lines)')
            wav = job / 'voice' / f'clip{i + 1:02d}.wav'; wav.parent.mkdir(exist_ok=True)
            ff('-y', '-loglevel', 'error', '-ss', f'{a:.3f}', '-t', f'{b - a:.3f}', '-i', str(src), '-vn', '-ac', '1', '-ar', '24000', str(wav))
            sc['_clip']['audio'] = f'voice/{wav.name}'
            for L in sc.get('lines', []): L['fromClip'] = True
        log(f'clip s{i + 1:02d}', sc['clip'], f'{n} frames, {n / fps:.2f}s', 'voice from clip' if sc['_clip']['audio'] else 'no clip voice')


def asr_clips(spec, job, threshold=.9):
    """Whisper hears each clip's own speech: it must say the scene's lines; word timings place the subtitles.
    A clip scene without "lines" gets subtitles from the transcript, marked for Leo to check."""
    rows, bad, notes = [], 0, []
    for i, sc in enumerate(spec['scenes']):
        c = sc.get('_clip')
        if not c or not c['audio']: continue
        heard, words, sents = transcribe(job / c['audio'])
        if not sc.get('lines'):
            sc['lines'] = [{'id': f'c{i + 1:02d}{k}', 'text': s, 'fromClip': True} for k, (s, _, _) in enumerate(x for x in sents if x[0])]
            notes.append(f'scene {i + 1}: subtitles taken from the transcript, check them: ' + ' / '.join(l['text'] for l in sc['lines']))
        want = ' '.join(L.get('asr') or L['text'] for L in sc['lines'])
        r = difflib.SequenceMatcher(None, norm_chars(want), norm_chars(heard), autojunk=False).ratio()
        ok = r >= threshold
        # a clip cut mid-phrase still scores high overall: its last spoken word must be the scene's last word,
        # and the speech must not run into the clip's last frames
        last_want = norm_chars(want.split()[-1]) if want.split() else ''
        last_heard = norm_chars(words[-1][0]) if words else ''
        cut = (difflib.SequenceMatcher(None, last_want, last_heard).ratio() < .7) or (words and words[-1][2] > c['dur'] - .12)
        if cut: ok = False
        bad += not ok
        rows.append(f'{"OK  " if ok else "DIFF"} clip s{i + 1:02d} {r:.2f}{" CUT: speech runs to the clip end or stops early" if cut else ""} | {want} → {heard}'); log(rows[-1])
        # spread the clip's word timings over the scene's lines by character position
        toks = [(k, w) for k, L in enumerate(sc['lines']) for w in L['text'].split()]
        joined = {'text': ' '.join(w for _, w in toks), 'asrWords': words, 'dur': c['dur']}
        timed = karaoke(joined, 0.0)
        end_all = words[-1][2] if words else c['dur']
        for k, L in enumerate(sc['lines']):
            mine = [tw for (j, _), tw in zip(toks, timed) if j == k]
            nxt = next((tw[1] for (j, _), tw in zip(toks, timed) if j > k), end_all)
            L['rel0'] = mine[0][1]; L['dur'] = round(max(.4, nxt - mine[0][1] - .05), 3)
            L['relWords'] = [[w, round(t - L['rel0'], 3)] for w, t in mine]
    if bad: raise Stop(f'speech check: {bad} clip(s) do not say their scene lines (check the clip, or correct "lines"/"asr" to what is really said)')
    return rows, notes


# ---------------------------------------------------------------- timeline
def need_read(text):  # same rule as readcheck.mjs: Cyrillic/Latin 15 chars/s + 1.5 s
    return len(re.sub(r'\s', '', text)) / 15 + 1.5

def timeline(spec):
    w, h = map(int, spec['size'].split('x'))
    t, lines, scenes, plucks = 0.0, [], [], []
    def speak(ls, t, y):
        for L in ls:
            t += L.get('pauseBefore', 0)                    # a held beat before the line (the script's «короткая пауза»)
            if L.get('pluckBefore'): plucks.append({'t': round(t - .25, 3)})
            L['t0'] = round(t, 3); lines.append({'id': L['id'], 'text': L['text'], 'asr': L.get('asr'), 't0': L['t0'], 'y': y, 'dur': L['dur'], 'env': L.get('env'), 'words': karaoke(L, L['t0'])})
            t += L['dur'] + .35
        return t
    clip_audio = []
    for i, sc in enumerate(spec['scenes']):
        t0 = t; ls = sc.get('lines', []); c = sc.get('_clip')
        if c and c['audio']:                              # the clip speaks: its own timing places the subtitles
            for L in ls:
                L['t0'] = round(t0 + L['rel0'], 3)
                if L.get('pluckBefore'): plucks.append({'t': round(L['t0'] - .25, 3)})
                lines.append({'id': L['id'], 'text': L['text'], 'asr': L.get('asr'), 't0': L['t0'], 'y': 1420, 'dur': L['dur'],
                              'fromClip': True, 'words': [[w, round(L['t0'] + r, 3)] for w, r in L['relWords']]})
            clip_audio.append({'file': c['audio'], 't0': round(t0, 3)})
            t = t0 + c['dur']
        elif sc.get('insert') and ls:                     # a drawn scene that speaks: timed by its lines, like a picture
            end = speak(ls, t + (.5 if i == 0 else .35), 1420) - .35 + .5
            t = max(end, t0 + sc.get('minDur', 2.8))
        elif sc.get('insert'):                            # code-drawn: long enough to draw and to read every row
            ins = sc['insert']; rows = ins.get('rows', [])
            reveal = .9 + max(0, len(rows) - 1) * .22 + .6
            need = max([need_read(r) for r in rows] + [need_read(ins.get('title', ''))] + [0])
            t = t0 + max(sc.get('minDur', 0), reveal + need + .3, 7.4)
        else:
            end = speak(ls, t + (.5 if i == 0 else .35), 1420) - .35 + .5
            if sc.get('title'): end = max(end, t0 + 1.1 + need_read(sc['title']))
            t = max(end, t0 + (c['dur'] if c else sc.get('minDur', 2.8)))
        s = {'image': sc.get('image', sc.get('clip')), 'move': sc.get('move', 'push'), 'focus': sc.get('focus', [.5, .5]), 'title': sc.get('title'), 't0': round(t0, 3), 't1': round(t, 3), 'transition': sc.get('transition')}
        if c: s.update(frames=c['frames'], count=c['count'], fps=c['fps'])
        if sc.get('insert'): s['insert'] = sc['insert']
        scenes.append(s)
    def still_of(name):                                   # a clip used as a card background → its last frame
        for sc in spec['scenes']:
            if name and sc.get('clip') == name: return f'{sc["_clip"]["frames"]}{sc["_clip"]["count"]:05d}.jpg'
        return name
    offer = None
    if spec.get('offer'):
        o = spec['offer']; t0 = t; rows = o.get('rows', [])
        price_t = t0 + .2 + (1.5 + len(rows) * .5) * .28
        end = speak(o.get('lines', []), t + .6, 1560) - .35 + .5
        reveal = t0 + .2 + (2 + len(rows) * .5) * .28 + .7
        end = max(end, reveal + max(need_read(x) for x in [o['title'], *rows, o['price'], o.get('note', '')] if x))
        t = end
        offer = {'title': o['title'], 'rows': rows, 'price': o['price'], 'note': o.get('note'), 'bg': still_of(o.get('bg')), 't0': round(t0, 3), 't1': round(t, 3), 'price_t': round(price_t, 3)}
    e = spec['end']; t0 = t
    end = speak(e.get('lines', []), t + .7, 1460) - .35 + .6
    tb = e.get('table')
    base = (2.2 + len(tb['rows']) * .6) if tb else 0
    reveal = t0 + .5 + (base + 2) * .3 + .7
    texts = [e.get('cta', ''), e.get('contact', ''), e['brand']] + ([tb.get('title', ''), tb.get('sub', ''), tb.get('note', ''), *(x for r in tb['rows'] for x in r)] if tb else [])
    end = max(end, reveal + max(need_read(x) for x in texts if x), t0 + 4.0)
    dur = round(end + .3, 3)
    for k, L in enumerate(lines):                        # hold each subtitle ≥ max(1.8 s, speech + 0.6 s), never into the next line
        nxt = lines[k + 1]['t0'] - .05 if k + 1 < len(lines) else dur - .3
        L['t1'] = round(min(max(L['t0'] + 1.8, L['t0'] + L['dur'] + .6), nxt), 3); L['end'] = round(L['t0'] + L['dur'], 3)
    return {'size': [w, h], 'dur': dur, 'crossfade': CROSSFADE, 'motion': spec.get('motion', 'anime'), 'scenes': scenes, 'offer': offer, 'lines': lines,
            'music': spec.get('music', {'style': 'calm'}), 'plucks': plucks, 'clipAudio': clip_audio,
            'end': {'poster': e.get('poster'), 'bg': still_of(e.get('bg')), 'table': e.get('table'), 'cta': e.get('cta'), 'contact': e.get('contact'), 'brand': e['brand'], 't0': round(t0, 3)}}


# ---------------------------------------------------------------- master
def mux(video, wav, out, fps):
    meas = ff('-i', str(wav), '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-', capture=True)
    j = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
    ln = ('loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:'
          'measured_thresh={input_thresh}:offset={target_offset}:linear=true').format(**j)
    vf = (f'fps={fps},scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p,'
          'setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709')
    ff('-y', '-loglevel', 'error', '-i', str(video), '-i', str(wav), '-filter_complex', f'[0:v]{vf}[v];[1:a]{ln},aresample=48000[a]',
       '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-r', str(fps),
       '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
       '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', str(out))


def measure(path):
    r = ff('-i', str(path), '-af', 'ebur128=peak=true', '-f', 'null', '-', capture=True)
    tail = r[r.rfind('Summary:'):]
    I = float(re.search(r'I:\s+(-?[\d.]+) LUFS', tail).group(1)); P = float(re.search(r'Peak:\s+(-?[\d.]+) dBFS', tail).group(1))
    black = len(re.findall('black_start', ff('-i', str(path), '-vf', 'blackdetect=d=0.1:pix_th=0.05', '-an', '-f', 'null', '-', capture=True)))
    hh, mm, sec = re.search(r'Duration: (\d+):(\d+):([\d.]+)', r).groups()
    return I, P, black, int(hh) * 3600 + int(mm) * 60 + float(sec)


def srt(lines, path):
    f = lambda s: '%02d:%02d:%02d,%03d' % (int(s // 3600), int(s // 60 % 60), int(s % 60), round(s % 1 * 1000) % 1000)
    path.write_text(''.join(f'{k + 1}\n{f(L["t0"])} --> {f(L["t1"])}\n{L["text"]}\n\n' for k, L in enumerate(lines)), encoding='utf-8')


def final_asr(path, lines):
    import numpy as np, soundfile as sf
    from faster_whisper import WhisperModel
    wav = path.with_suffix('.check16k.wav'); ff('-y', '-loglevel', 'error', '-i', str(path), '-ac', '1', '-ar', '16000', str(wav))
    a, _ = sf.read(wav, dtype='float32'); wav.unlink()
    segs, _ = WhisperModel('small', compute_type='int8').transcribe(a, language='ru', beam_size=5)
    heard = ' '.join(s.text for s in segs)
    want = ' '.join(L.get('asr') or L['text'] for L in lines)
    return round(difflib.SequenceMatcher(None, norm_chars(want), norm_chars(heard), autojunk=False).ratio(), 3), heard.strip()


# ---------------------------------------------------------------- main
def main():
    global FFMPEG
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('job'); ap.add_argument('--fps', type=int, default=24); ap.add_argument('--no-final-asr', action='store_true')
    ap.add_argument('--workers', type=int, default=2, help='parallel browsers for the render (2 suits integrated graphics)')
    ap.add_argument('--draft', action='store_true', help='accept a source post that is not approved yet; the video is marked as a draft, not for publication')
    ap.add_argument('--plan-only', action='store_true', help='stop after the timeline and the reading check (no render): for previewing stills')
    a = ap.parse_args(); job = Path(a.job).resolve(); qa = []
    try:
        FFMPEG = find_ffmpeg()
        if not (HERE / 'node_modules' / 'playwright-core').is_dir(): raise Stop(f'run "npm install" in {HERE} first (see README.md)')
        spec = load_spec(job); log('spec', spec['packageId'], f'{len(spec["scenes"])} scenes')
        source, approved = approved_text(spec, a.draft)
        qa.append(f'- Source: `{spec["sourcePost"]}` — ' + ('STATUS: APPROVED' if approved else 'NOT APPROVED (draft preview, not for publication)'))
        qa.append(f'- Fact gate (numbers on screen ⊂ approved text): {fact_gate(spec, source)}')
        prepare_clips(spec, job, a.fps)
        qa.append('- Narration: ' + ('Simba / Google Gemini Voice Design / WarmBaritone (approved)' if voice_provider(spec) == 'simba' else 'explicit Edge TTS legacy voice'))
        tts(spec, job)
        qa += ['- Speech check (Whisper small, per line):', *[f'  - {r}' for r in asr_check(spec, job)]]
        if any(sc.get('_clip', {}).get('audio') for sc in spec['scenes']):
            rows, notes = asr_clips(spec, job)
            qa += ["- Speech check of the clips' own voice:", *[f'  - {r}' for r in rows], *[f'- NOTE: {n}' for n in notes]]
            fact_gate(spec, source)                       # subtitles taken from a clip are checked too
        tl = timeline(spec)
        if tl['dur'] > MAX_DUR: raise Stop(f'the film would run {tl["dur"]:.1f} s, over the {MAX_DUR:.0f} s limit: cut lines or scenes')
        (job / 'timeline.json').write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding='utf-8')
        shutil.copy(HERE / 'template' / 'index.html', job / 'index.html')
        log('timeline', f'{tl["dur"]:.1f} s')
        code, out = node('readcheck.mjs', job, '--size', spec['size'])
        if code != 0: raise Stop('reading-time check failed:\n' + '\n'.join(l for l in out.splitlines() if not l.startswith('OK')))
        qa.append('- Reading-time check (readcheck.mjs): PASS')
        if a.plan_only:
            print('\n'.join(qa)); print(f'plan ready: {tl["dur"]:.1f} s; preview with engine/render/still.mjs'); return 0
        # Decode actual external MP3/WAV before expensive Chromium frame render.
        if tl['music'].get('file'):
            import music_input
            try:
                prepared = music_input.prepare_music(job, tl['music'], tl['dur'], FFMPEG)
            except ValueError as exc:
                raise Stop('external soundtrack: ' + str(exc)) from exc
            log('external music', prepared.name)
            qa.append(f'- Music: external recording `{tl["music"]["file"]}` (48 kHz stereo); rights_confirmed is a Music Editor attestation, not an automatic license check')
        else:
            qa.append('- Music: synthesized soundtrack (legacy default)')
        log('rendering frames…', spec['renderer'])
        if spec['renderer'] == 'hyperframes':
            from hyperframes_backend import render as hyperframes_render
            try:
                hyperframes_render(job, tl, a.fps, job / 'out' / 'video.mp4', ffmpeg=FFMPEG)
            except (RuntimeError, OSError) as exc:
                raise Stop('HyperFrames render failed: ' + str(exc)) from exc
        else:
            code, out = node('video.mjs', job, '--size', spec['size'], '--fps', a.fps, '--workers', a.workers, '--out', job / 'out' / 'video.mp4')
            if code != 0: raise Stop('render failed:\n' + out[-1500:])
        sys.path.insert(0, str(HERE)); import audio
        try:
            wav = audio.mix(job, tl)
        except ValueError as exc:
            raise Stop('audio mix: ' + str(exc)) from exc
        log('mix', wav.name)
        final = job / f'{spec["packageId"]}.mp4'; mux(job / 'out' / 'video.mp4', wav, final, a.fps)
        srt(tl['lines'], final.with_suffix('.srt'))
        cover_t = min(tl['scenes'][0]['t0'] + 1.6, tl['scenes'][0]['t1'])
        ff('-y', '-loglevel', 'error', '-ss', f'{cover_t:.2f}', '-i', str(final), '-frames:v', '1', '-q:v', '3', str(job / 'cover.jpg'))
        I, P, black, d = measure(final)
        qa += [f'- Duration: {d:.1f} s (limit {MAX_DUR:.0f} s)', f'- Loudness: {I:.1f} LUFS, true peak {P:.1f} dBFS (target −14 / ≤ −1.5)', f'- Black frames: {black}']
        heard_ok = True
        if not a.no_final_asr:
            r, heard = final_asr(final, tl['lines']); heard_ok = r >= .85
            qa.append(f'- Final mix speech check (voice over music, ≥ 0.85): {r:.2f} — «{heard}»')
        ok = d <= MAX_DUR + .05 and abs(I + 14) <= 1 and P <= -1 and black == 0 and heard_ok
        status = ('VIDEO_READY_FOR_LEO' if approved else 'VIDEO_DRAFT_SOURCE_NOT_APPROVED') if ok else 'VIDEO_QA_FAILED'
        report = [f'# Video QA — {spec["packageId"]}', '', f'STATUS: {status}', f'RENDERER: {spec["renderer"]}, narration={voice_provider(spec)}', '', *qa, '',
                  f'Files: `{final.name}`, `{final.with_suffix(".srt").name}`, `cover.jpg`.', 'Publication is a separate explicit command of Leo.']
        (job / 'qa-report.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
        print('\n'.join(report))
        return 0 if ok else 1
    except Stop as e:
        print(f'\nSTOPPED: {e}', file=sys.stderr); return 2


if __name__ == '__main__':
    sys.exit(main())

