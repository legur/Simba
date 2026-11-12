// Simba photo-story: Rafael frames with camera moves, karaoke subtitles, an offer card and an end card.
// The page reads timeline.json (written by make_video.py) from the job folder; render(t) is a pure function of t.
import { clamp, lerp, seg, ss, eo, eio } from '/engine/lib.js';
import { animate } from '/node_modules/animejs/dist/modules/index.js';
import { makeRoute } from '/template/inserts.js';
import { makeCartoon } from '/template/cartoon.js';
import { renderTransition } from '/template/transitions.js';
import { drawStyledSubtitle } from '/template/subtitle_styles.js';

const TL = await (await fetch('timeline.json')).json();
const W = innerWidth, H = innerHeight;
const cv = document.getElementById('c'); cv.width = W; cv.height = H;
const ctx = cv.getContext('2d');
const C = { navy: '#0E1B30', cream: '#F4EBDD', gold: '#E2B65B', dim: 'rgba(244,235,221,.55)' };
const TITLE = '"Playfair Display"', SANS = 'Montserrat';
const XF = TL.crossfade;                                  // scene crossfade, seconds
const TRANSITION_PAD = Math.max(XF, ...TL.scenes.slice(1).map(s => (s.transition?.duration_ms ?? 0) / 2000));
const MOTION = TL.motion ?? 'anime';                       // old timelines default to the editor-approved Anime.js style
if (!['anime', 'classic'].includes(MOTION)) throw new Error(`unknown motion style: ${MOTION}`);

// ---------------------------------------------------------------- assets
const load = src => new Promise((ok, bad) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => bad(new Error('image missing: ' + src)); i.src = src; });
const IMG = {};
for (const s of TL.scenes) if (!s.frames && !s.insert) IMG[s.image] ??= await load(s.image);
// video-clip scenes: frames were extracted to JPEGs by make_video.py; prepare(t) loads the ones frame t needs
const FR = new Map();
const frameOf = (s, t) => {
  // Loop only when the user-approved source explicitly opts in. v1 and
  // existing v2 scenes retain the last-frame hold, without discontinuities
  // from an implicit video repeat.
  const index = Math.max(0, Math.floor((t - s.t0) * s.fps));
  // Alaska v1's actual owner-approved 10-scene footage was FFmpeg
  // setpts-scaled: sample the WHOLE original clip across each scene's
  // narration duration instead of freezing or jumping to a new loop.
  const frame = s.clipPlayback === 'stretch'
    ? clamp(Math.floor((Math.max(0, t - s.t0) / Math.max(1e-3, s.t1 - s.t0))
                       * s.count), 0, s.count - 1)
    : s.clipPlayback === 'loop'
      ? index % s.count : clamp(index, 0, s.count - 1);
  return `${s.frames}${String(frame + 1).padStart(5, '0')}.jpg`;
};
const live = t => TL.scenes.filter(s => t >= s.t0 - TRANSITION_PAD && t <= s.t1 + TRANSITION_PAD);
window.prepare = async t => {
  const want = live(t).filter(s => s.frames).map(s => frameOf(s, t));
  for (const k of FR.keys()) if (!want.includes(k)) FR.delete(k);
  await Promise.all(want.filter(k => !FR.has(k)).map(async k => FR.set(k, await load(k))));
};
for (const k of [TL.end.poster, TL.end.bg, TL.offer?.bg]) if (k) IMG[k] ??= await load(k);
function blurred(img, px, dark) {                           // made once: a soft, darkened backdrop for the cards
  const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
  if (!img) {                                                 // no picture to blur (a drawn first scene): a navy gradient
    const gr = g.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#1A2E4E'); gr.addColorStop(1, C.navy);
    g.fillStyle = gr; g.fillRect(0, 0, W, H); return c;
  }
  g.filter = `blur(${px}px)`; cover(g, img, W / 2, H / 2, 1.15); g.filter = 'none';
  g.fillStyle = `rgba(14,27,48,${dark})`; g.fillRect(0, 0, W, H); return c;
}
function cover(g, img, cx, cy, zoom) {                      // draw img covering the frame, centred on (cx, cy) in frame px
  const k = Math.max(W / img.width, H / img.height) * zoom, w = img.width * k, h = img.height * k;
  g.drawImage(img, cx - w / 2, cy - h / 2, w, h);
}
const stillOf = s => s.frames ? `${s.frames}${String(s.count).padStart(5, '0')}.jpg` : s.image;   // a clip scene → its last frame
for (const s of [TL.scenes[0], TL.scenes.at(-1)]) if (!s.insert) IMG[stillOf(s)] ??= await load(stillOf(s));
const OFFER_BG = TL.offer ? blurred(IMG[TL.offer.bg ?? stillOf(TL.scenes.at(-1))], 28, .62) : null;
const END_BG = blurred(IMG[TL.end.bg ?? TL.end.poster ?? stillOf(TL.scenes[0])], 34, .7);
const POSTER_W = 640, SHADOW = 60;                          // the poster with its soft shadow, made once (a live shadowBlur is slow)
const POSTER = (() => {
  if (!TL.end.poster) return null;
  const img = IMG[TL.end.poster], ph = POSTER_W * img.height / img.width, c = document.createElement('canvas');
  c.width = POSTER_W + SHADOW * 2; c.height = ph + SHADOW * 2 + 18; const g = c.getContext('2d');
  g.shadowColor = 'rgba(0,0,0,.55)'; g.shadowBlur = 50; g.shadowOffsetY = 18; g.drawImage(img, SHADOW, SHADOW, POSTER_W, ph);
  return { c, ph };
})();

// ---------------------------------------------------------------- text helpers
let texts = [];
const REVEAL_MS = 1000;
const revealState = { opacity: 0, lift: 1, scale: .985 };
const revealMotion = MOTION === 'anime' ? animate(revealState, {
  opacity: 1,
  lift: 0,
  scale: 1,
  duration: REVEAL_MS,
  ease: 'outQuint',
  autoplay: false,
}) : null;
function revealAt(p) {
  revealMotion.seek(clamp(p) * REVEAL_MS, true);
  return { ...revealState };
}
const revealProgress = p => MOTION === 'classic' ? eo(clamp(p)) : revealAt(p).opacity;
function wrap(g, words, maxW) {
  const lines = [[]]; let w = 0; const sp = g.measureText(' ').width;
  for (const word of words) {
    const ww = g.measureText(word).width;
    if (lines.at(-1).length && w + sp + ww > maxW) { lines.push([]); w = 0; }
    w += (lines.at(-1).length ? sp : 0) + ww; lines.at(-1).push(word);
  }
  return lines;
}
function rise(g, txt, x, y, font, color, p, align = 'center', id) {   // deterministic editor-selected reveal, derived only from timeline progress
  if (p <= 0) return;
  g.save(); g.font = font; g.textAlign = align; g.textBaseline = 'alphabetic';
  const m = g.measureText(txt), h = m.actualBoundingBoxAscent + m.actualBoundingBoxDescent;
  const x0 = align === 'center' ? x - m.width / 2 : align === 'right' ? x - m.width : x;
  if (MOTION === 'classic') {
    g.beginPath(); g.rect(x0 - 20, y - m.actualBoundingBoxAscent - 12, m.width + 40, h + 28); g.clip();
    g.globalAlpha *= clamp(p * 1.6); g.fillStyle = color;
    g.fillText(txt, x, y + (1 - eo(p)) * h * 1.1);
  } else {
    const motion = revealAt(p), top = y - m.actualBoundingBoxAscent - 12, clipH = h + 28;
    g.beginPath(); g.rect(x0 - 20, top + clipH * (1 - motion.opacity), m.width + 40, clipH * motion.opacity); g.clip();
    g.globalAlpha *= clamp(motion.opacity * 1.15); g.fillStyle = color;
    g.translate(x, y); g.scale(motion.scale, motion.scale); g.fillText(txt, 0, motion.lift * h * .48);
  }
  g.restore();
  texts.push({ id: id ?? txt, text: txt, x0, y0: y - m.actualBoundingBoxAscent, x1: x0 + m.width, y1: y + m.actualBoundingBoxDescent });
}

// ---------------------------------------------------------------- scenes
const MOVES = {   // [zoom0, zoom1, dx0, dx1, dy0, dy1] in frame fractions
  push: [1.04, 1.16, 0, 0, 0, 0], pull: [1.18, 1.04, 0, 0, 0, 0],
  'pan-left': [1.16, 1.16, .045, -.045, 0, 0], 'pan-right': [1.16, 1.16, -.045, .045, 0, 0],
  rise: [1.14, 1.14, 0, 0, .035, -.035], hold: [1.03, 1.07, 0, 0, 0, 0], none: [1, 1, 0, 0, 0, 0],
};
const INSERT = new Map();
const CT = {                                                 // what drawn scenes may read: their lines and the voice's mouth openness
  lines: s => TL.lines.filter(l => l.t0 >= s.t0 - .01 && l.t0 < s.t1),
  mouth: t => { const L = TL.lines.find(l => l.env && t >= l.t0 && t < l.end); if (!L) return 0; const i = Math.floor((t - L.t0) * 30); return L.env[Math.min(i, L.env.length - 1)] ?? 0; },
};                                    // code-drawn scenes (inserts.js)
const riseT = (txt, x, y, font, color, p, align, id) => rise(ctx, txt, x, y, font, color, p, align, id);
function drawScene(s, t, alpha) {
  if (s.insert) {
    if (!INSERT.has(s)) INSERT.set(s, s.insert.type === 'cartoon' ? makeCartoon(s.insert, W, H, ctx) : makeRoute(s.insert, W, ctx, C, TITLE, SANS));
    return INSERT.get(s)(s, t, alpha, riseT, CT);
  }
  const [z0, z1, x0, x1, y0, y1] = MOVES[s.move] ?? MOVES.push;
  const u = ss(seg(t, s.t0 - XF, s.t1 + XF)), [fx, fy] = s.focus ?? [.5, .5];
  const img = s.frames ? FR.get(frameOf(s, t)) : IMG[s.image];
  if (!img) return;                                          // a clip frame not prepared (readcheck draws no pictures)
  // Motion Lab effects are explicit, bounded and opt-in. For ready A2E clips
  // legacy move=none remains unchanged unless an approved cameraEffect exists.
  let z = lerp(z0, z1, u);
  let offsetX = lerp(x0, x1, u), offsetY = lerp(y0, y1, u);
  if (s.cameraEffect) {
    const amount = s.cameraEffect.intensity_percent / 100;
    switch (s.cameraEffect.id) {
      case 'cinematic-zoom':
        z = lerp(1.06, 1.05 + .18 * amount, u); break;
      case 'push-through':
        z = lerp(1.06, 1.05 + .32 * amount, u); break;
      case 'float':
        z = lerp(1.06, 1.08 + .08 * amount, u);
        offsetX += (8 * amount * u) / W;
        offsetY += (9 * amount * u) / H;
        break;
      default: throw new Error('Unverified Motion Lab camera: ' + s.cameraEffect.id);
    }
  }
  const k = z - 1;
  ctx.save(); ctx.globalAlpha = alpha;
  cover(ctx, img,
    W * (.5 + (.5 - fx) * Math.min(.25, k * 2) + offsetX),
    H * (.5 + (.5 - fy) * Math.min(.25, k * 2) + offsetY), z);
  ctx.restore();
}
function grade() {
  let g = ctx.createLinearGradient(0, H * .5, 0, H); g.addColorStop(0, 'rgba(14,27,48,0)'); g.addColorStop(1, 'rgba(14,27,48,.72)');
  ctx.fillStyle = g; ctx.fillRect(0, H * .5, W, H * .5);
  g = ctx.createLinearGradient(0, 0, 0, H * .32); g.addColorStop(0, 'rgba(14,27,48,.55)'); g.addColorStop(1, 'rgba(14,27,48,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H * .32);
  g = ctx.createRadialGradient(W / 2, H / 2, H * .3, W / 2, H / 2, H * .75); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.35)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
}
function drawTitle(s, i, t) {
  if (!s.title || s.titleEffect === 'none') return;
  if (s.titleEffect && s.titleEffect !== 'fade-rise') throw new Error('Unverified Motion Lab title effect: '+s.titleEffect);
  const a = 1 - seg(t, s.t1 - .3, s.t1 + XF * .5);
  if (a <= 0) return;
  // A v2 layout changes ONLY geometry, not the approved title or its timing.
  // Preserve the historical title position when no layout was approved.
  const layer = s.visualLayout?.title;
  const size = layer ? Math.round(92 * layer.scale / 100) : 92;
  const step = Math.round(108 * size / 92);
  const centerX = layer ? W * layer.x / 100 : W / 2;
  const centerY = layer ? H * layer.y / 100 : 300;
  const usableWidth = layer
    ? Math.min(W * .72, 2 * Math.min(centerX - W * .06, W * .94 - centerX))
    : W - 160;
  if (layer && usableWidth <= 0) throw new Error('Unsafe Motion Lab title X');
  ctx.save(); ctx.globalAlpha = a; ctx.font = `700 ${size}px ${TITLE}`;
  const lines = wrap(ctx, s.title.split(/\s+/), usableWidth);
  const firstY = layer ? centerY - (lines.length - 1) * step / 2 : 300;
  if (layer) {
    if (firstY - size * .9 < H * .06 ||
        firstY + (lines.length - 1) * step + size * .3 > H * .94 ||
        lines.some(ln => ctx.measureText(ln.join(' ')).width > usableWidth)) {
      ctx.restore();
      throw new Error('Motion Lab title exceeds safe overlay bounds');
    }
  }
  lines.forEach((ln, k) => rise(ctx, ln.join(' '), centerX, firstY + k * step,
    `700 ${size}px ${TITLE}`, C.cream,
    seg(t, s.t0 + .15 + k * .18, s.t0 + .85 + k * .18),
    'center', `title${i}-${k}`));
  const rp = revealProgress(seg(t, s.t0 + .5, s.t0 + 1.1));
  const ry = firstY + lines.length * step - 50 * size / 92;
  ctx.fillStyle = C.gold;
  ctx.fillRect(centerX - 70 * rp, ry, 140 * rp, 4);
  ctx.restore();
}

// ---------------------------------------------------------------- subtitles (karaoke: the spoken word turns gold)
function drawSub(t) {
  const L = TL.lines.find(l => t >= l.t0 && t < l.t1); if (!L) return;
  if (TL.subtitleStyle) {
    // Per-scene WYSIWYG position/scale; subtitle style and word timing remain
    // global and are not overridden by a scene's geometry.
    const active = TL.scenes.find(s => t >= s.t0 && t < s.t1);
    drawStyledSubtitle(ctx, L, t, TL.subtitleStyle, W, H,
      active?.visualLayout?.subtitle ?? null);
    return;
  }
  const a = Math.min(seg(t, L.t0, L.t0 + .15), 1 - seg(t, L.t1 - .15, L.t1));
  ctx.save(); ctx.font = `600 50px ${SANS}`; ctx.textBaseline = 'middle';
  const lines = wrap(ctx, L.words.map(w => w[0]), W - 200), lh = 66, padX = 34, padY = 26;
  const widths = lines.map(ln => ctx.measureText(ln.join(' ')).width), bw = Math.max(...widths) + padX * 2, bh = lines.length * lh + padY * 2;
  const cy = L.y ?? 1420, by = cy - bh / 2;
  ctx.globalAlpha = a; ctx.fillStyle = 'rgba(14,27,48,.74)'; ctx.beginPath(); ctx.roundRect(W / 2 - bw / 2, by, bw, bh, 26); ctx.fill();
  let k = 0; const sp = ctx.measureText(' ').width;
  lines.forEach((ln, r) => {
    let x = W / 2 - widths[r] / 2; const y = by + padY + lh * (r + .5);
    for (const word of ln) {
      const [, ws] = L.words[k++];
      ctx.fillStyle = t >= ws ? (t < (L.words[k]?.[1] ?? L.end) ? C.gold : C.cream) : C.dim;
      ctx.fillText(word, x, y); x += ctx.measureText(word).width + sp;
    }
  });
  ctx.restore();
}

// ---------------------------------------------------------------- offer card
function drawOffer(t) {
  const O = TL.offer; if (!O || t < O.t0 - XF || t > O.t1 + XF) return;
  const a = Math.min(seg(t, O.t0 - XF, O.t0), 1 - seg(t, O.t1, O.t1 + XF));
  ctx.save(); ctx.globalAlpha = a; ctx.drawImage(OFFER_BG, 0, 0);
  const st = k => seg(t, O.t0 + .2 + k * .28, O.t0 + .9 + k * .28);
  ctx.font = `700 84px ${TITLE}`;
  const tl = wrap(ctx, O.title.split(/\s+/), W - 160);
  tl.forEach((ln, k) => rise(ctx, ln.join(' '), W / 2, 470 + k * 98, `700 84px ${TITLE}`, C.cream, st(0), 'center', `offer-title-${k}`));
  let y = 470 + tl.length * 98 + 40;
  ctx.fillStyle = C.gold; const rp = revealProgress(st(1)); ctx.fillRect(W / 2 - 80 * rp, y - 30, 160 * rp, 4);
  O.rows.forEach((r, k) => { rise(ctx, r, W / 2, y + 40 + k * 66, `500 44px ${SANS}`, C.cream, st(1 + k * .5), 'center', `offer-row-${k}`); });
  y += 40 + O.rows.length * 66 + 150;
  const pp = st(1.5 + O.rows.length * .5);
  ctx.save(); ctx.translate(W / 2, y); const s = pp > 0 ? lerp(MOTION === 'classic' ? .86 : .92, 1, revealProgress(pp)) : 1; ctx.scale(s, s); ctx.translate(-W / 2, -y);
  rise(ctx, O.price, W / 2, y, `700 150px ${TITLE}`, C.gold, pp, 'center', 'offer-price'); ctx.restore();
  if (O.note) {
    ctx.font = `500 36px ${SANS}`;
    wrap(ctx, O.note.split(/\s+/), W - 220).forEach((ln, k) => rise(ctx, ln.join(' '), W / 2, y + 90 + k * 50, `500 36px ${SANS}`, 'rgba(244,235,221,.82)', st(2 + O.rows.length * .5), 'center', `offer-note-${k}`));
  }
  ctx.restore();
}

// ---------------------------------------------------------------- end card
function drawEnd(t) {
  const E = TL.end; if (t < E.t0 - XF) return;
  const a = seg(t, E.t0 - XF, E.t0);
  ctx.save(); ctx.globalAlpha = a; ctx.drawImage(END_BG, 0, 0);
  let y = 150;                                                // poster, CTA, contact and brand stay above the subtitle (y ≈ 1440)
  if (POSTER) {
    const { c, ph } = POSTER, p = eo(seg(t, E.t0 - .2, E.t0 + .7)), s = lerp(.94, 1, p);
    ctx.save(); ctx.globalAlpha = a * clamp(p * 1.5); ctx.translate(W / 2, y + ph / 2); ctx.scale(s, s);
    ctx.drawImage(c, -POSTER_W / 2 - SHADOW, -ph / 2 - SHADOW); ctx.restore();
    y += ph + 110;
  } else y = E.table ? 260 : 620;
  let st = k => seg(t, E.t0 + .5 + k * .3, E.t0 + 1.2 + k * .3);
  if (E.table) {                                              // price table: title, dates, cabin rows, note
    const T = E.table;
    rise(ctx, T.title, W / 2, y, `700 64px ${TITLE}`, C.cream, st(0), 'center', 'tbl-title');
    if (T.sub) rise(ctx, T.sub, W / 2, y + 70, `500 40px ${SANS}`, 'rgba(244,235,221,.85)', st(.5), 'center', 'tbl-sub');
    y += T.sub ? 150 : 100;
    ctx.fillStyle = C.gold; const rp = revealProgress(st(1)); ctx.fillRect(W / 2 - 400 * rp, y - 40, 800 * rp, 3);
    T.rows.forEach(([label, value], k) => {
      const p = st(1.3 + k * .6), yy = y + 50 + k * 112;
      rise(ctx, label, 120, yy, `500 44px ${SANS}`, C.cream, p, 'left', `tbl-l${k}`);
      rise(ctx, value, W - 120, yy + 6, `700 76px ${TITLE}`, C.gold, p, 'right', `tbl-v${k}`);
      ctx.fillStyle = 'rgba(244,235,221,.18)'; ctx.fillRect(120, yy + 40, (W - 240) * revealProgress(p), 1.5);
    });
    y += 50 + T.rows.length * 112;
    if (T.note) {
      ctx.font = `500 36px ${SANS}`;
      const nl = wrap(ctx, T.note.split(/\s+/), W - 220);
      nl.forEach((ln, k) => rise(ctx, ln.join(' '), W / 2, y + 20 + k * 48, `500 36px ${SANS}`, 'rgba(244,235,221,.82)', st(1.6 + T.rows.length * .6), 'center', `tbl-note-${k}`));
      y += nl.length * 48 + 20;
    }
    y += 110;
    const base = 2.2 + T.rows.length * .6;
    st = k => seg(t, E.t0 + .5 + (base + k) * .3, E.t0 + 1.2 + (base + k) * .3);
  }
  ctx.font = `600 48px ${SANS}`;
  const cl = E.cta ? wrap(ctx, E.cta.split(/\s+/), W - 180) : [];
  cl.forEach((ln, k) => rise(ctx, ln.join(' '), W / 2, y + k * 62, `600 48px ${SANS}`, C.cream, st(0), 'center', `end-cta-${k}`));
  y += cl.length * 62 + 30;
  if (E.contact) { rise(ctx, E.contact, W / 2, y + 30, `700 58px ${SANS}`, C.gold, st(1), 'center', 'end-contact'); y += 110; }
  rise(ctx, E.brand, W / 2, y + 40, `700 56px ${TITLE}`, C.cream, st(2), 'center', 'end-brand');
  ctx.restore();
}

// ---------------------------------------------------------------- frame
function render(t) {
  t = clamp(t, 0, TL.dur); texts = [];
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = C.navy; ctx.fillRect(0, 0, W, H);
  const n = TL.scenes.length;
  const boundary = TL.scenes.findIndex((s, i) => {
    const half = (s.transition?.duration_ms ?? 0) / 2000;
    return i > 0 && half > 0 && t >= s.t0 - half && t <= s.t0 + half;
  });
  if (boundary > 0) {
    const incoming = TL.scenes[boundary], half = incoming.transition.duration_ms / 2000;
    const progress = clamp((t - (incoming.t0 - half)) / (2 * half));
    renderTransition(ctx, TL.scenes[boundary - 1], incoming, progress,
      incoming.transition.id, (s, alpha) => drawScene(s, t, alpha), incoming.title ?? '');
  } else {
    // Legacy behavior is unchanged for jobs without selected transitions.
    TL.scenes.forEach((s, i) => {
      if (t < s.t0 - XF || t > s.t1 + XF) return;
      const fin = i === 0 ? 1 : seg(t, s.t0 - XF / 2, s.t0 + XF / 2);
      const fout = i === n - 1 && !TL.offer ? 1 : 1 - seg(t, s.t1 - XF / 2, s.t1 + XF / 2);
      drawScene(s, t, Math.min(fin, fout));
    });
  }
  grade();
  TL.scenes.forEach((s, i) => { if (t >= s.t0 - XF && t <= s.t1 + XF) drawTitle(s, i, t); });
  drawOffer(t); drawEnd(t); drawSub(t);
  const fade = 1 - seg(t, TL.dur - .5, TL.dur);              // to navy on the last frames
  if (fade < 1) { ctx.globalAlpha = 1 - fade; ctx.fillStyle = C.navy; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = 1; }
}
let last = null;
window.DUR = TL.dur; window.render = t => { last = t; render(t); };
window.TEXTS = t => { if (last !== t) window.render(t); return texts.filter(x => x.text.trim()); };
await Promise.all([`700 92px ${TITLE}`, `600 50px ${SANS}`, `500 44px ${SANS}`, `700 58px ${SANS}`].map(f => document.fonts.load(f, 'Ааё$')));
window.render(0);
window.READY = true;
