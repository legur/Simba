// Cartoon Simba drawn in code: a flat-vector lion in a linen shirt, six Mediterranean cruise sets, lip-sync from the voice.
// Every pose is a function of t; nothing carries over between frames.
import { clamp, lerp, seg, ss, eo, eio, hash } from '/engine/lib.js';

const P = {
  ink: '#3B2416', fur: '#E6B064', furD: '#C98C45', muzzle: '#F7DDB0', mane: '#B5642A', maneD: '#8E4A1E', maneL: '#D0823A',
  nose: '#5A3322', mouth: '#5B1F22', tongue: '#E07A7A', iris: '#E9A53B',
  shirt: '#FBF6EC', shirtD: '#E6DDCB', pants: '#1E3A55', pantsD: '#152B40', glasses: '#2B1D16',
  skyT: '#6DB6EA', skyB: '#D3EEFB', sea: '#2F7DB5', seaD: '#23649A', hill: '#7FAE8A', hillD: '#5D8C6C',
  white: '#F8F8F3', whiteD: '#DCE3E8', wood: '#C99A63', woodD: '#A47744', rail: '#8A5A33', pool: '#4FC7DD', poolD: '#2EA5C2',
  roof: '#C8643C', houses: ['#F2D7B6', '#EBC29A', '#F5E6C8', '#E9B48F', '#F3CFA4'],
};
const TAU = Math.PI * 2;

// ---------------------------------------------------------------- shape helpers
function blob(g, pts, fill, stroke = P.ink, lw = 6) {        // closed smooth shape through points
  g.beginPath();
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const a = pts[i], b = pts[(i + 1) % n], m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    if (i === 0) g.moveTo((pts[n - 1][0] + a[0]) / 2, (pts[n - 1][1] + a[1]) / 2);
    g.quadraticCurveTo(a[0], a[1], m[0], m[1]);
  }
  g.closePath();
  if (fill) { g.fillStyle = fill; g.fill(); }
  if (stroke) { g.strokeStyle = stroke; g.lineWidth = lw; g.lineJoin = 'round'; g.stroke(); }
}
function ell(g, x, y, rx, ry, fill, stroke = P.ink, lw = 6, rot = 0) {
  g.beginPath(); g.ellipse(x, y, rx, ry, rot, 0, TAU);
  if (fill) { g.fillStyle = fill; g.fill(); }
  if (stroke) { g.strokeStyle = stroke; g.lineWidth = lw; g.stroke(); }
}
function limb(g, a, b, w, fill) {                          // a thick rounded segment with an ink outline
  g.lineCap = 'round';
  g.strokeStyle = P.ink; g.lineWidth = w + 12; g.beginPath(); g.moveTo(...a); g.lineTo(...b); g.stroke();
  g.strokeStyle = fill; g.lineWidth = w; g.beginPath(); g.moveTo(...a); g.lineTo(...b); g.stroke();
}
const polar = (o, len, ang) => [o[0] + Math.sin(ang) * len, o[1] + Math.cos(ang) * len];   // angle 0 = straight down

// ---------------------------------------------------------------- the lion
// pose: {tilt, lookX, lookY, blink, brow, mouth, smile, armL:{sh, el, paw}, armR:{…}, walk, seated, shrug, breathe, mane}
function paw(g, at, kind, side) {
  const [x, y] = at;
  if (kind === 'hidden') return;
  if (kind === 'open') {                                     // palm toward the viewer: pads visible
    ell(g, x, y, 50, 46, P.fur);
    ell(g, x, y + 10, 24, 18, P.furD, null);
    for (let k = -1.5; k <= 1.5; k++) ell(g, x + k * 19, y - 26, 10, 9, P.furD, null);
    return;
  }
  ell(g, x, y, 46, 42, P.fur);                               // back of the paw, toes
  g.strokeStyle = P.ink; g.lineWidth = 4; g.beginPath();
  for (const k of [-14, 0, 14]) { g.moveTo(x + k, y + 10 * side * 0 + 20); g.lineTo(x + k, y + 36); }
  g.stroke();
}
function arm(g, sh, a, side) {
  const elbow = polar(sh, 210, a.sh * side), hand = polar(elbow, 200, (a.sh + a.el) * side);
  limb(g, sh, elbow, 86, P.shirt);
  // rolled cuff
  const cuff = polar(sh, 190, a.sh * side);
  limb(g, cuff, elbow, 92, P.shirtD);
  if (a.paw !== 'pocket') {
    limb(g, elbow, polar(elbow, 175, (a.sh + a.el) * side), 64, P.fur);
    paw(g, hand, a.paw, side);
  }
  return hand;
}
function maneTufts(g, r, n, wob, col, t, seed) {
  g.beginPath();
  for (let i = 0; i <= n * 2; i++) {
    const a = i / (n * 2) * TAU, out = i % 2 === 0;
    const sway = Math.sin(t * 2.1 + i * 1.7 + seed) * wob;
    const rr = out ? r * (1.06 + .08 * hash(i + seed)) + sway : r * .86;
    const x = Math.cos(a) * rr, y = Math.sin(a) * rr * 1.04;
    if (i === 0) g.moveTo(x, y); else g.quadraticCurveTo(Math.cos(a - Math.PI / (n * 2)) * r * 1.02, Math.sin(a - Math.PI / (n * 2)) * r * 1.06, x, y);
  }
  g.closePath(); g.fillStyle = col; g.fill(); g.strokeStyle = P.ink; g.lineWidth = 6; g.stroke();
}
function head(g, p, t) {
  g.save(); g.rotate(p.tilt || 0);
  maneTufts(g, 245, 14, 6 + (p.wind || 0) * 8, P.maneD, t, 3);
  maneTufts(g, 215, 13, 4 + (p.wind || 0) * 6, P.mane, t * 1.1, 7);
  maneTufts(g, 178, 11, 3, P.maneL, t * .9, 11);
  // ears
  for (const s of [-1, 1]) { ell(g, s * 112, -118, 42, 40, P.fur); ell(g, s * 112, -114, 22, 20, P.furD, null); }
  // face
  const lx = (p.lookX || 0) * 14, ly = (p.lookY || 0) * 10;
  blob(g, [[0, -165], [118, -120], [150, -10], [118, 105], [0, 150], [-118, 105], [-150, -10], [-118, -120]], P.fur);
  // eyes
  for (const s of [-1, 1]) {
    const ex = s * 56 + lx, ey = -22 + ly;
    ell(g, ex, ey, 26, 30, '#FFFDF6', P.ink, 5);
    ell(g, ex + lx * .5, ey + ly * .6 + 4, 16, 19, P.iris, null);
    ell(g, ex + lx * .5, ey + ly * .6 + 5, 8, 11, '#20140C', null);
    ell(g, ex + lx * .5 - 5, ey + ly * .6 - 3, 4.5, 4.5, '#FFFFFF', null);
    const shut = clamp(p.blink || 0) * .95 + (p.lid || 0);   // upper lid
    if (shut > 0) {
      g.save(); g.beginPath(); g.ellipse(ex, ey, 27, 31, 0, 0, TAU); g.clip();
      g.fillStyle = P.fur; g.fillRect(ex - 30, ey - 34, 60, 64 * clamp(shut)); g.restore();
      g.strokeStyle = P.ink; g.lineWidth = 5; g.beginPath(); g.moveTo(ex - 26, ey - 31 + 62 * clamp(shut)); g.lineTo(ex + 26, ey - 31 + 62 * clamp(shut)); g.stroke();
    }
    // brow: positive = raised (question), negative = knitted
    const b = p.brow || 0;
    g.strokeStyle = P.maneD; g.lineWidth = 12; g.lineCap = 'round'; g.beginPath();
    g.moveTo(ex - s * 26, ey - 46 - b * 10 + (s > 0 ? 0 : 0)); g.quadraticCurveTo(ex, ey - 62 - b * 16, ex + s * 24, ey - 50 - b * 6 - (p.browTilt || 0) * s * 8); g.stroke();
  }
  // muzzle
  ell(g, -34 + lx * .3, 62, 50, 40, P.muzzle, P.ink, 5); ell(g, 34 + lx * .3, 62, 50, 40, P.muzzle, P.ink, 5);
  // mouth: opens with the voice
  const o = clamp(p.mouth || 0), sm = p.smile ?? .6;
  if (o > .04) {
    g.save(); g.beginPath(); g.ellipse(lx * .3, 100 + o * 10, 30 + o * 8, 6 + o * 30, 0, 0, TAU);
    g.fillStyle = P.mouth; g.fill(); g.clip(); ell(g, lx * .3, 112 + o * 34, 24, 16, P.tongue, null); g.restore();
    g.strokeStyle = P.ink; g.lineWidth = 5; g.beginPath(); g.ellipse(lx * .3, 100 + o * 10, 30 + o * 8, 6 + o * 30, 0, 0, TAU); g.stroke();
  }
  g.strokeStyle = P.ink; g.lineWidth = 5; g.lineCap = 'round'; g.beginPath();
  g.moveTo(-40 + lx * .3, 92 - sm * 8); g.quadraticCurveTo(-16 + lx * .3, 104 + sm * 6, lx * .3, 92); g.quadraticCurveTo(16 + lx * .3, 104 + sm * 6, 40 + lx * .3, 92 - sm * 8); g.stroke();
  // whisker dots
  g.fillStyle = P.furD; for (const s of [-1, 1]) for (let k = 0; k < 3; k++) { g.beginPath(); g.arc(s * (30 + k * 14) + lx * .3, 58 + (k % 2) * 12, 3.5, 0, TAU); g.fill(); }
  // nose
  blob(g, [[-30 + lx * .3, 28], [30 + lx * .3, 28], [0 + lx * .3, 62]], P.nose, P.ink, 5);
  ell(g, -8 + lx * .3, 34, 8, 5, 'rgba(255,255,255,.35)', null);
  g.restore();
}
export function lion(g, x, y, k, p, t) {
  g.save(); g.translate(x, y); g.scale(k, k);
  const br = 1 + Math.sin(t * 2.2) * .008 * (p.breathe ?? 1), shrug = (p.shrug || 0) * 26;
  const wp = p.walk != null ? Math.sin(p.walk * TAU) : 0, bob = p.walk != null ? -Math.abs(Math.cos(p.walk * TAU)) * 10 : 0;
  g.translate(0, bob);
  // legs
  if (!p.seated) {
    if (p.tail) {                                             // tail with a tuft, behind the legs
      g.strokeStyle = P.ink; g.lineWidth = 34; g.lineCap = 'round'; g.beginPath(); g.moveTo(-60, 40);
      g.quadraticCurveTo(-260, 200 + wp * 30, -230, 380); g.stroke();
      g.strokeStyle = P.fur; g.lineWidth = 22; g.stroke(); ell(g, -228, 400 + wp * 6, 34, 46, P.maneD);
    }
    for (const s of [-1, 1]) {
      const sw = p.walk != null ? s * wp * .22 : 0, hip = [s * 70, 10], knee = polar(hip, 280, -sw), foot = polar(knee, 260, -sw * .4);
      limb(g, hip, knee, 120, P.pants); limb(g, knee, foot, 108, P.pants);
      ell(g, foot[0] + s * 6, foot[1] + 30, 68, 34, P.fur);
    }
  }
  // torso: linen shirt, untucked, open collar
  g.save(); g.translate(0, -215); g.scale(br, br); g.translate(0, 215);
  const top = -425 - shrug;
  blob(g, [[-190, top + 20], [-60, top - 8], [60, top - 8], [190, top + 20], [205, -160], [178, 40], [0, 58], [-178, 40], [-205, -160]], P.shirt);
  g.fillStyle = P.fur; g.beginPath(); g.moveTo(-58, top - 4); g.lineTo(58, top - 4); g.lineTo(0, top + 170); g.closePath(); g.fill();
  g.strokeStyle = P.ink; g.lineWidth = 5; g.beginPath(); g.moveTo(-58, top - 4); g.lineTo(0, top + 170); g.lineTo(58, top - 4); g.stroke();
  g.strokeStyle = P.shirtD; g.lineWidth = 4; g.beginPath(); g.moveTo(0, top + 170); g.lineTo(0, 40); g.stroke();
  for (const yy of [top + 230, top + 330]) ell(g, 8, yy, 7, 7, P.shirtD, P.ink, 3);
  g.strokeStyle = P.ink; g.lineWidth = 4; g.strokeRect(70, top + 120, 70, 60);                       // pocket
  // sunglasses hanging in the collar
  g.save(); g.translate(0, top + 120); g.rotate(-.12);
  ell(g, -22, 0, 22, 18, P.glasses, P.ink, 4); ell(g, -22, 46, 22, 18, P.glasses, P.ink, 4);
  g.strokeStyle = P.ink; g.lineWidth = 4; g.beginPath(); g.moveTo(-22, 18); g.lineTo(-22, 28); g.stroke(); g.restore();
  g.restore();
  // arms (the far one first)
  const shL = [-180, top + 30], shR = [180, top + 30];
  const hands = {};
  for (const [side, sh, a] of [[-1, shL, p.armL], [1, shR, p.armR]]) hands[side] = arm(g, sh, a ?? { sh: .1, el: .05, paw: 'back' }, side);
  // head on the neck
  g.save(); g.translate(0, top - 160 - shrug * .3); head(g, p, t); g.restore();
  g.restore();
  const w = h => [x + k * h[0], y + k * (h[1] + bob)];        // paw positions in frame coordinates, for props
  return { L: w(hands[-1]), R: w(hands[1]) };
}

// ---------------------------------------------------------------- sets
function sky(g, W, H, horizon) {
  const gr = g.createLinearGradient(0, 0, 0, horizon); gr.addColorStop(0, P.skyT); gr.addColorStop(1, P.skyB);
  g.fillStyle = gr; g.fillRect(0, 0, W, horizon + 2);
  g.fillStyle = 'rgba(255,255,255,.85)';
  for (const [cx, cy, s] of [[180, 260, 1], [820, 180, .8], [560, 420, .6]]) {
    g.beginPath(); for (const [dx, dy, r] of [[0, 0, 60], [55, -20, 50], [110, 0, 55], [55, 15, 50]]) g.arc(cx + dx * s, cy + dy * s, r * s, 0, TAU); g.fill();
  }
}
function coast(g, W, horizon, x0, seed, scale = 1) {         // hills with a pastel town
  g.fillStyle = P.hill; g.beginPath(); g.moveTo(x0, horizon);
  for (let x = x0; x <= W + 40; x += 40) g.lineTo(x, horizon - (120 + 140 * Math.sin((x - x0) / 260 + seed) ** 2) * scale);
  g.lineTo(W + 40, horizon); g.closePath(); g.fill();
  g.fillStyle = P.hillD; g.beginPath(); g.moveTo(x0 + 120, horizon);
  for (let x = x0 + 120; x <= W + 40; x += 40) g.lineTo(x, horizon - (60 + 80 * Math.sin((x - x0) / 180 + seed * 2) ** 2) * scale);
  g.lineTo(W + 40, horizon); g.closePath(); g.fill();
  for (let i = 0; i < 26; i++) {
    const hx = x0 + 60 + hash(i + seed * 10) * (W - x0 - 40), hy = horizon - (10 + hash(i * 7 + seed) * 120) * scale, w = (26 + hash(i * 3) * 22) * scale, h = (22 + hash(i * 5) * 26) * scale;
    g.fillStyle = P.houses[i % P.houses.length]; g.fillRect(hx, hy - h, w, h);
    g.fillStyle = P.roof; g.fillRect(hx - 2, hy - h - 6 * scale, w + 4, 7 * scale);
  }
}
function sea(g, W, top, bottom, t) {
  const gr = g.createLinearGradient(0, top, 0, bottom); gr.addColorStop(0, P.sea); gr.addColorStop(1, P.seaD);
  g.fillStyle = gr; g.fillRect(0, top, W, bottom - top);
  g.strokeStyle = 'rgba(255,255,255,.55)'; g.lineWidth = 3; g.lineCap = 'round';
  for (let i = 0; i < 40; i++) {
    const y = top + 12 + hash(i) * (bottom - top - 20), x = (hash(i * 3) * W + t * (12 + hash(i) * 20)) % (W + 80) - 40, w = 12 + hash(i * 9) * 26;
    g.globalAlpha = .4 + .5 * Math.abs(Math.sin(t * 2 + i)); g.beginPath(); g.moveTo(x, y); g.lineTo(x + w, y); g.stroke();
  }
  g.globalAlpha = 1;
}
function boat(g, x, y, s, t) {
  const b = Math.sin(t * 1.6 + x) * 4;
  g.save(); g.translate(x, y + b); g.scale(s, s);
  blob(g, [[-60, 0], [60, 0], [44, 26], [-44, 26]], P.white, P.ink, 4);
  g.fillStyle = '#2F5E86'; g.fillRect(-30, -24, 40, 24); g.strokeStyle = P.ink; g.lineWidth = 3; g.strokeRect(-30, -24, 40, 24);
  g.restore();
}
function railing(g, W, y, h) {
  g.fillStyle = 'rgba(205,232,242,.38)'; g.fillRect(0, y, W, h);
  g.fillStyle = P.white; for (let x = 40; x < W; x += 200) { g.fillRect(x, y, 16, h); }
  g.strokeStyle = P.ink; g.lineWidth = 4; for (let x = 40; x < W; x += 200) g.strokeRect(x, y, 16, h);
  g.fillStyle = P.rail; g.fillRect(0, y - 22, W, 26); g.strokeRect(-10, y - 22, W + 20, 26);
}
function deckFloor(g, W, H, top) {
  g.fillStyle = P.wood; g.fillRect(0, top, W, H - top);
  g.strokeStyle = P.woodD; g.lineWidth = 3;
  for (let i = -12; i <= 12; i++) { g.beginPath(); g.moveTo(W / 2 + i * 30, top); g.lineTo(W / 2 + i * 150, H); g.stroke(); }
}
function superstructure(g, x, w, top, bottom, side) {
  g.fillStyle = P.white; g.fillRect(x, top, w, bottom - top); g.strokeStyle = P.ink; g.lineWidth = 5; g.strokeRect(x, top, w, bottom - top);
  for (let y = top + 60; y < bottom - 60; y += 150) {
    g.fillStyle = P.whiteD; g.fillRect(x, y + 70, w, 18);
    g.fillStyle = '#7FB6D6'; for (let k = 0; k < Math.floor(w / 70); k++) { g.fillRect(x + 20 + k * 70, y, 46, 50); g.strokeStyle = P.ink; g.lineWidth = 3; g.strokeRect(x + 20 + k * 70, y, 46, 50); }
  }
}

function setDeck(g, W, H, t, mirror) {
  sky(g, W, H, 900); coast(g, W, 900, mirror ? 0 : 300, 1.3); sea(g, W, 900, 1260, t);
  boat(g, 760, 1040, .7, t); boat(g, 920, 1110, .5, t);
  railing(g, W, 1260, 260); deckFloor(g, W, H, 1520);
  if (mirror) superstructure(g, W - 240, 300, 120, 1520, 1); else superstructure(g, -60, 300, 120, 1520, -1);
}
function setPool(g, W, H, t) {
  sky(g, W, H, 760); coast(g, W, 760, 0, 2.1, .7); sea(g, W, 760, 900, t);
  superstructure(g, 720, 420, 160, 980, 1);
  deckFloor(g, W, H, 900);
  g.save(); g.beginPath(); g.moveTo(160, 1080); g.lineTo(1000, 1080); g.lineTo(1140, 1560); g.lineTo(40, 1560); g.closePath();
  g.fillStyle = P.pool; g.fill(); g.strokeStyle = P.white; g.lineWidth = 18; g.stroke(); g.clip();
  g.strokeStyle = 'rgba(255,255,255,.6)'; g.lineWidth = 4;
  for (let i = 0; i < 26; i++) { const y = 1100 + hash(i) * 440, x = 80 + hash(i * 3) * 980 + Math.sin(t * 1.5 + i) * 18; g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + 20, y - 8, x + 44, y); g.stroke(); }
  g.restore();
  for (const [lx, ly] of [[60, 960], [300, 960]]) { g.fillStyle = P.shirt; g.fillRect(lx, ly, 170, 50); g.strokeStyle = P.ink; g.lineWidth = 4; g.strokeRect(lx, ly, 170, 50); g.fillStyle = '#2F5E86'; g.fillRect(lx + 120, ly, 50, 50); }
  g.fillStyle = P.shirt; g.beginPath(); g.moveTo(560, 760); g.quadraticCurveTo(700, 690, 840, 760); g.closePath(); g.fill(); g.stroke();
  g.fillStyle = P.ink; g.fillRect(696, 760, 8, 200);
}
function mapPaper(g, x, y, w, h, t, prog) {
  g.save(); g.translate(x, y); g.rotate(-.06);
  g.fillStyle = '#F4EFE2'; g.fillRect(0, 0, w, h); g.strokeStyle = P.ink; g.lineWidth = 4; g.strokeRect(0, 0, w, h);
  g.fillStyle = '#BFE0F0'; g.fillRect(14, 14, w - 28, h - 28);
  g.fillStyle = '#CFE3B8'; g.strokeStyle = '#8DAA77'; g.lineWidth = 3;
  blob(g, [[w * .3, 14], [w * .55, 14], [w * .62, h * .35], [w * .8, h * .62], [w * .74, h * .74], [w * .58, h * .5], [w * .42, h * .3]], '#CFE3B8', '#8DAA77', 3);
  blob(g, [[w * .66, h * .8], [w * .8, h * .78], [w * .78, h * .88], [w * .64, h * .9]], '#CFE3B8', '#8DAA77', 3);
  g.strokeStyle = '#C8643C'; g.lineWidth = 5; g.setLineDash([12, 9]); g.beginPath();
  const pts = [[w * .52, h * .36], [w * .62, h * .52], [w * .76, h * .76], [w * .45, h * .62], [w * .2, h * .3], [w * .4, h * .2], [w * .52, h * .36]];
  const n = Math.max(1, Math.floor(prog * (pts.length - 1) * 10));
  for (let i = 0; i <= n; i++) { const f = i / 10, k = Math.min(pts.length - 2, Math.floor(f)), u = f - k, q = [lerp(pts[k][0], pts[k + 1][0], u), lerp(pts[k][1], pts[k + 1][1], u)]; i ? g.lineTo(...q) : g.moveTo(...q); }
  g.stroke(); g.setLineDash([]);
  g.fillStyle = '#2F5E86'; for (const q of pts.slice(0, -1)) { g.beginPath(); g.arc(q[0], q[1], 9, 0, TAU); g.fill(); }
  g.restore();
}
function cup(g, x, y, s = 1) {
  g.save(); g.translate(x, y); g.scale(s, s);
  ell(g, 0, 40, 80, 18, P.white); blob(g, [[-48, -30], [48, -30], [40, 30], [-40, 30]], P.white); ell(g, 0, -30, 48, 12, '#5A3322', P.ink, 4);
  g.strokeStyle = P.ink; g.lineWidth = 5; g.beginPath(); g.arc(56, 0, 18, -1.2, 1.2); g.stroke();
  g.restore();
}
function setMap(g, W, H, t) {
  sky(g, W, H, 820); coast(g, W, 820, 200, 3.1, .9); sea(g, W, 820, 1140, t);
  railing(g, W, 1140, 220);
  g.fillStyle = '#7A4B2A'; g.fillRect(0, 1360, W, H - 1360);
}
function tableTop(g, W, y) {
  ell(g, W / 2, y + 160, 640, 230, '#8E5A33'); ell(g, W / 2, y + 130, 640, 230, '#B07443');
}
function setCafe(g, W, H, t) {
  sky(g, W, H, 700);
  g.fillStyle = '#F0D9AE'; g.fillRect(-20, 120, W + 40, 1060); g.strokeStyle = P.ink; g.lineWidth = 5; g.strokeRect(-20, 120, W + 40, 1060);
  ell(g, 760, 140, 120, 90, '#D9B25E'); g.fillStyle = '#E9CB86'; g.fillRect(660, 140, 200, 120);
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) {
    const x = 70 + c * 250, y = 330 + r * 260;
    g.fillStyle = '#3E7A5A'; g.fillRect(x, y, 64, 150); g.fillRect(x + 86, y, 64, 150);
    g.strokeStyle = P.ink; g.lineWidth = 4; g.strokeRect(x, y, 64, 150); g.strokeRect(x + 86, y, 64, 150);
    g.fillStyle = '#C8643C'; g.fillRect(x - 10, y + 150, 170, 14);
  }
  g.fillStyle = '#D9C4A0'; g.fillRect(0, 1180, W, H - 1180);
  g.strokeStyle = '#BFA782'; g.lineWidth = 3; for (let i = 0; i < 18; i++) { g.beginPath(); g.moveTo(0, 1200 + i * 42); g.lineTo(W, 1200 + i * 42); g.stroke(); }
  ell(g, 860, 1180, 150, 40, '#EDEBE4'); g.fillStyle = '#EDEBE4'; g.fillRect(820, 980, 80, 200); g.strokeRect(820, 980, 80, 200); ell(g, 860, 980, 90, 26, '#EDEBE4');
  g.strokeStyle = 'rgba(130,200,240,.9)'; g.lineWidth = 6; for (const s of [-1, 1]) { g.beginPath(); g.moveTo(860, 960); g.quadraticCurveTo(860 + s * 60, 900 + Math.sin(t * 6) * 4, 860 + s * 90, 1000); g.stroke(); }
  g.fillStyle = '#4E8C4A'; ell(g, 90, 900, 120, 150, '#5E9A55'); for (let i = 0; i < 7; i++) ell(g, 40 + hash(i) * 120, 820 + hash(i * 3) * 180, 14, 16, '#F2D24A', P.ink, 3);
}
function listPaper(g, x0, y0, x1, y1, t) {                // a long folded paper plan with doodle icons
  const n = 11, dy = (y1 - y0) / n;
  for (let i = 0; i < n; i++) {
    const sway = Math.sin(t * 2 + i * .6) * (i / n) * 10, xa = lerp(x0, x1, i / n) + sway, ya = y0 + i * dy;
    g.fillStyle = i % 2 ? '#FBF8F0' : '#F2EEE4'; g.strokeStyle = P.ink; g.lineWidth = 3;
    g.beginPath(); g.moveTo(xa - 60, ya); g.lineTo(xa + 60, ya + (i % 2 ? 6 : -6)); g.lineTo(xa + 62 + sway * .2, ya + dy); g.lineTo(xa - 58 + sway * .2, ya + dy - (i % 2 ? 6 : -6)); g.closePath(); g.fill(); g.stroke();
    const cx = xa + 10, cy = ya + dy / 2, kind = i % 6;
    ell(g, xa - 36, cy, 9, 9, ['#E07A3A', '#3A8FD0', '#6AAA5A'][i % 3], null);
    g.lineWidth = 3; g.strokeStyle = P.ink;
    if (kind === 0) { g.fillStyle = '#2F5E86'; g.fillRect(cx - 18, cy - 4, 40, 12); g.fillRect(cx - 6, cy - 14, 20, 10); }
    else if (kind === 1) { g.fillStyle = '#E8C89A'; g.fillRect(cx - 16, cy - 10, 32, 22); g.fillStyle = P.roof; g.fillRect(cx - 18, cy - 14, 36, 6); }
    else if (kind === 2) { ell(g, cx, cy, 18, 18, '#E8A04A', P.ink, 3); }
    else if (kind === 3) { g.fillStyle = '#5E9A55'; g.fillRect(cx - 2, cy - 10, 4, 22); ell(g, cx, cy - 12, 16, 7, '#5E9A55', null); }
    else if (kind === 4) { g.beginPath(); g.moveTo(cx - 10, cy - 14); g.lineTo(cx + 10, cy - 14); g.lineTo(cx, cy + 2); g.closePath(); g.fillStyle = '#C24A4A'; g.fill(); g.stroke(); }
    else { g.beginPath(); g.moveTo(cx - 20, cy + 12); g.lineTo(cx, cy - 14); g.lineTo(cx + 20, cy + 12); g.closePath(); g.fillStyle = '#7FAE8A'; g.fill(); g.stroke(); }
  }
}
function setPromenade(g, W, H, t, scroll) {
  sky(g, W, H, 760); coast(g, W, 760, 260, 4.2, 1.6); sea(g, W, 760, 1050, t);
  boat(g, 780, 900, .9, t); boat(g, 960, 980, .7, t); boat(g, 640, 1000, .5, t);
  g.fillStyle = '#CDB993'; g.fillRect(0, 1000, W, H - 1000);
  g.fillStyle = '#E2CDA8'; g.beginPath(); g.moveTo(-100, H); g.lineTo(380, 1000); g.lineTo(760, 1000); g.lineTo(W + 260, H); g.closePath(); g.fill();
  g.strokeStyle = '#C7AF86'; g.lineWidth = 3;
  for (let i = 0; i < 14; i++) { const f = ((i / 14) + scroll) % 1, y = 1000 + (H - 1000) * f * f; g.beginPath(); g.moveTo(380 - 480 * f * f, y); g.lineTo(760 + 500 * f * f, y); g.stroke(); }
  g.fillStyle = '#E9DEC9'; g.fillRect(-20, 640, 300, 420); g.strokeStyle = P.ink; g.lineWidth = 4; g.strokeRect(-20, 640, 300, 420);
  for (const [x, y] of [[20, 700], [150, 700], [20, 860], [150, 860]]) { g.fillStyle = '#3E7A5A'; g.fillRect(x, y, 70, 110); g.strokeRect(x, y, 70, 110); }
  for (const [x, s] of [[880, .8], [1010, 1.1]]) {
    const y = 1000 + 260 * s; g.fillStyle = '#C97A4A'; g.beginPath(); g.moveTo(x - 50 * s, y); g.lineTo(x + 50 * s, y); g.lineTo(x + 38 * s, y + 80 * s); g.lineTo(x - 38 * s, y + 80 * s); g.closePath(); g.fill(); g.stroke();
    for (let k = 0; k < 6; k++) ell(g, x + (hash(k + x) - .5) * 80 * s, y - 20 * s - hash(k * 7 + x) * 40 * s, 16 * s, 16 * s, ['#FFFFFF', '#F4A9C0', '#FFFFFF'][k % 3], P.ink, 3);
  }
}

// ---------------------------------------------------------------- Asia sets: Ha Long Bay, Angkor, a Hanoi street, rice terraces, the airport
function karst(g, x, base, w, h, col) {                    // a limestone tower rising from the sea
  blob(g, [[x - w * .5, base], [x - w * .55, base - h * .55], [x - w * .32, base - h * .95], [x + w * .05, base - h], [x + w * .4, base - h * .8], [x + w * .52, base - h * .4], [x + w * .5, base]], col, P.ink, 4);
  for (let k = 0; k < 4; k++) ell(g, x + (hash(x + k) - .5) * w * .6, base - h * (.3 + hash(k + x) * .6), w * .18, h * .06, 'rgba(70,120,80,.55)', null);
}
function setHalong(g, W, H, t, mirror) {
  sky(g, W, H, 900);
  for (const [x, w, h] of [[140, 150, 330], [330, 120, 250], [700, 180, 380], [930, 140, 280]]) karst(g, mirror ? W - x : x, 905, w, h, '#9DB8A6');
  sea(g, W, 900, 1260, t);
  for (const [x, w, h] of [[60, 200, 460], [960, 230, 520]]) karst(g, mirror ? W - x : x, 1000, w, h, '#7E9E86');
  const bx = mirror ? 300 : 780, b = Math.sin(t * 1.4) * 4;          // a junk with ribbed sails
  g.save(); g.translate(bx, 1060 + b);
  blob(g, [[-90, 0], [90, 0], [70, 30], [-70, 30]], '#8A5A33', P.ink, 4);
  for (const [sx, sh] of [[-30, 120], [30, 150]]) {
    blob(g, [[sx - 34, -10], [sx + 34, -10], [sx + 26, -sh], [sx - 26, -sh + 10]], '#C2703A', P.ink, 4);
    g.strokeStyle = P.ink; g.lineWidth = 2;
    for (let k = 1; k < 5; k++) { g.beginPath(); g.moveTo(sx - 32, -10 - k * sh / 5); g.lineTo(sx + 30, -10 - k * sh / 5); g.stroke(); }
  }
  g.restore();
  g.fillStyle = '#8A5A33'; g.fillRect(0, 1250, W, 24); g.strokeStyle = P.ink; g.lineWidth = 4; g.strokeRect(-10, 1250, W + 20, 24);
  for (let x = 30; x < W; x += 120) { g.fillStyle = '#9B6A40'; g.fillRect(x, 1274, 18, 250); g.strokeRect(x, 1274, 18, 250); }
  deckFloor(g, W, H, 1520);
}
function setAngkor(g, W, H, t) {
  const gr = g.createLinearGradient(0, 0, 0, 1000); gr.addColorStop(0, '#F3B66B'); gr.addColorStop(1, '#FBE3B8'); g.fillStyle = gr; g.fillRect(0, 0, W, 1002);
  ell(g, 820, 330, 90, 90, '#FFE9B0', null);
  const stone = '#9A8670', dark = '#7D6B57';
  const tower = (x, base, w, h) => {
    for (let k = 0; k < 6; k++) { const f = k / 6, ww = w * (1 - f * .8); g.fillStyle = k % 2 ? stone : dark; g.fillRect(x - ww / 2, base - h * (f + 1 / 6), ww, h / 6 + 1); }
    ell(g, x, base - h - 10, w * .12, 22, stone, null);
  };
  g.fillStyle = dark; g.fillRect(80, 820, 920, 180);
  for (let k = 0; k < 12; k++) { g.fillStyle = stone; g.fillRect(100 + k * 76, 860, 40, 60); }
  tower(220, 830, 160, 300); tower(860, 830, 160, 300); tower(540, 820, 230, 480); tower(380, 830, 130, 220); tower(700, 830, 130, 220);
  g.fillStyle = '#7FB8C8'; g.fillRect(0, 1000, W, 180);
  g.save(); g.globalAlpha = .3; g.translate(0, 2000); g.scale(1, -1); g.fillStyle = dark; g.fillRect(80, 820, 920, 180); g.restore();
  g.fillStyle = '#D9B98A'; g.fillRect(0, 1180, W, H - 1180);
  for (const [px, s] of [[80, 1.2], [1000, 1]]) {                       // palms
    const top = 900 - 260 * s;
    g.strokeStyle = '#6B4A2C'; g.lineWidth = 26 * s; g.beginPath(); g.moveTo(px, 1260); g.quadraticCurveTo(px + 30 * s, 1000, px + 10, top); g.stroke();
    for (let k = 0; k < 7; k++) { const a = -Math.PI + k * Math.PI / 6 + Math.sin(t + k) * .05; g.fillStyle = '#4E8C4A'; g.beginPath(); g.ellipse(px + 10 + Math.cos(a) * 110 * s, top + Math.sin(a) * 50 * s, 110 * s, 22 * s, a, 0, TAU); g.fill(); }
  }
}
function lantern(g, x, y, s, t) {
  const sw = Math.sin(t * 1.8 + x) * 4;
  g.strokeStyle = P.ink; g.lineWidth = 2; g.beginPath(); g.moveTo(x, y - 40 * s); g.lineTo(x + sw, y - 20 * s); g.stroke();
  const gl = g.createRadialGradient(x + sw, y, 0, x + sw, y, 70 * s); gl.addColorStop(0, 'rgba(255,170,90,.45)'); gl.addColorStop(1, 'rgba(255,170,90,0)');
  g.fillStyle = gl; g.fillRect(x + sw - 70 * s, y - 70 * s, 140 * s, 140 * s);
  ell(g, x + sw, y, 28 * s, 34 * s, '#D93A2E', P.ink, 3);
  g.fillStyle = '#F2C14E'; g.fillRect(x + sw - 12 * s, y - 38 * s, 24 * s, 7 * s); g.fillRect(x + sw - 12 * s, y + 31 * s, 24 * s, 7 * s);
}
function setStreet(g, W, H, t) {
  sky(g, W, H, 500);
  const fronts = [['#E8C15A', 0, 260], ['#D98E5A', 250, 230], ['#E9D7A0', 470, 230], ['#C9A45A', 690, 220], ['#E8B87A', 900, 200]];
  fronts.forEach(([c, x, w], i) => {
    const top = 120 + (i % 2) * 90; g.fillStyle = c; g.fillRect(x, top, w, 1240 - top); g.strokeStyle = P.ink; g.lineWidth = 4; g.strokeRect(x, top, w, 1240 - top);
    for (let y = top + 60; y < 1050; y += 210) {
      g.fillStyle = '#3E7A5A'; g.fillRect(x + 30, y, w * .3, 120); g.fillRect(x + w * .55, y, w * .3, 120);
      g.strokeRect(x + 30, y, w * .3, 120); g.strokeRect(x + w * .55, y, w * .3, 120); g.fillStyle = P.ink; g.fillRect(x + 20, y + 130, w - 40, 8);
    }
  });
  for (const [y0, y1] of [[330, 420], [560, 640]]) {                     // strings of lanterns across the street
    g.strokeStyle = P.ink; g.lineWidth = 2; g.beginPath(); g.moveTo(0, y0); g.quadraticCurveTo(W / 2, y1, W, y0); g.stroke();
    for (let k = 1; k < 8; k++) { const f = k / 8, x = f * W, y = (1 - f) * (1 - f) * y0 + 2 * (1 - f) * f * y1 + f * f * y0; lantern(g, x, y + 40, .9, t); }
  }
  g.fillStyle = '#A9A39A'; g.fillRect(0, 1240, W, H - 1240);
}
function setRice(g, W, H, t) {
  sky(g, W, H, 620);
  g.fillStyle = '#7FA88A'; g.beginPath(); g.moveTo(0, 620); for (let x = 0; x <= W; x += 30) g.lineTo(x, 520 + 60 * Math.sin(x / 170)); g.lineTo(W, 640); g.closePath(); g.fill();
  for (let k = 0; k < 9; k++) {                                          // terraces, each a shiny water step
    const y = 640 + k * 70 + k * k * 6;
    g.fillStyle = k % 2 ? '#8DC26A' : '#A3D07A'; g.beginPath(); g.moveTo(-20, y + 30);
    for (let x = -20; x <= W + 20; x += 30) g.lineTo(x, y + 26 * Math.sin(x / 140 + k * .7));
    g.lineTo(W + 20, H); g.lineTo(-20, H); g.closePath(); g.fill(); g.strokeStyle = '#5E8C46'; g.lineWidth = 4; g.stroke();
    g.strokeStyle = 'rgba(255,255,255,.35)'; g.lineWidth = 3;
    for (let i = 0; i < 4; i++) { const x = (hash(k * 9 + i) * W + t * 10) % W; g.beginPath(); g.moveTo(x, y + 40); g.lineTo(x + 40, y + 40); g.stroke(); }
  }
  g.fillStyle = '#C9A877'; g.beginPath(); g.moveTo(-100, H); g.lineTo(420, 1180); g.lineTo(640, 1180); g.lineTo(W + 200, H); g.closePath(); g.fill(); g.strokeStyle = P.ink; g.lineWidth = 3; g.stroke();
}
function setAirport(g, W, H, t) {
  g.fillStyle = '#E7ECF0'; g.fillRect(0, 0, W, H);
  g.fillStyle = '#9FD3F0'; g.fillRect(0, 160, W, 900);                   // the big window
  g.fillStyle = '#7FB3CE'; g.fillRect(0, 860, W, 200);
  const px = (t * 40) % (W + 600) - 300;                                  // a plane taxiing past
  g.save(); g.translate(px, 820);
  blob(g, [[-200, 0], [180, -10], [230, 10], [180, 30], [-200, 30]], '#FFFFFF', P.ink, 4);
  blob(g, [[-40, 10], [60, 10], [-20, 110], [-80, 110]], '#E3E8EC', P.ink, 4);
  blob(g, [[-200, 0], [-160, 0], [-190, -90], [-215, -90]], '#E3E8EC', P.ink, 4);
  g.fillStyle = '#2F5E86'; for (let k = 0; k < 9; k++) g.fillRect(-120 + k * 30, 2, 14, 10);
  g.restore();
  g.fillStyle = '#B9C4CC'; for (let x = 0; x < W; x += 270) g.fillRect(x - 10, 160, 20, 900);
  g.fillStyle = '#C9D2D8'; g.fillRect(0, 1060, W, H - 1060);
  g.strokeStyle = '#B4BEC5'; g.lineWidth = 3; for (let i = 0; i < 12; i++) { g.beginPath(); g.moveTo(0, 1100 + i * 70); g.lineTo(W, 1100 + i * 70); g.stroke(); }
}
// the route board he presents: dots and an arc that draws itself, labels from the spec (fact-checked)
function routeBoard(g, x, y, w, h, stops, u, rise) {
  g.fillStyle = '#16304F'; g.fillRect(x, y, w, h); g.strokeStyle = P.ink; g.lineWidth = 6; g.strokeRect(x, y, w, h);
  g.fillStyle = '#E2B65B'; g.fillRect(x, y, w, 10);
  const pts = stops.map((s, i) => [x + 140 + (w - 280) * i / (stops.length - 1), y + h * (.38 + (i % 2) * .16)]);
  const prog = eio(seg(u, .6, 3.2)), n = 60;
  g.strokeStyle = '#E2B65B'; g.lineWidth = 6; g.setLineDash([16, 12]); g.beginPath();
  for (let i = 0; i <= n * prog; i++) {
    const f = i / n * (pts.length - 1), k = Math.min(pts.length - 2, Math.floor(f)), v = f - k;
    const a = pts[k], b = pts[k + 1], mx = (a[0] + b[0]) / 2, my = Math.min(a[1], b[1]) - 90;
    const q = [(1 - v) ** 2 * a[0] + 2 * (1 - v) * v * mx + v * v * b[0], (1 - v) ** 2 * a[1] + 2 * (1 - v) * v * my + v * v * b[1]];
    i ? g.lineTo(...q) : g.moveTo(...q);
  }
  g.stroke(); g.setLineDash([]);
  stops.forEach((s, i) => {
    const reach = prog * (pts.length - 1) >= i - .02, a = reach ? 1 : 0;
    if (!a) return;
    ell(g, pts[i][0], pts[i][1], 16, 16, '#E2B65B', '#F4EBDD', 4);
    rise(s.name, pts[i][0], pts[i][1] + 60, '700 36px Montserrat', '#F4EBDD', seg(u, .6 + i * .9, 1.2 + i * .9), 'center', `board-${i}`);
    if (s.date) rise(s.date, pts[i][0], pts[i][1] + 104, '500 30px Montserrat', '#E2B65B', seg(u, .8 + i * .9, 1.4 + i * .9), 'center', `board-d${i}`);
  });
}
function bowl(g, x, y, s, t) {                              // pho with chopsticks and a curl of steam
  g.save(); g.translate(x, y); g.scale(s, s);
  for (let k = 0; k < 3; k++) { g.strokeStyle = `rgba(255,255,255,${.5 - k * .12})`; g.lineWidth = 6; g.beginPath(); const dx = (k - 1) * 30; g.moveTo(dx, -40); g.quadraticCurveTo(dx + 20 * Math.sin(t * 2 + k), -100, dx, -150 - k * 10); g.stroke(); }
  blob(g, [[-110, 0], [110, 0], [70, 80], [-70, 80]], '#FFFFFF'); ell(g, 0, 0, 108, 22, '#E9B36A', P.ink, 4);
  for (const dx of [-40, 10, 50]) ell(g, dx, -2, 14, 6, '#5E9A55', null);
  g.strokeStyle = '#8A5A33'; g.lineWidth = 9; g.beginPath(); g.moveTo(30, -10); g.lineTo(150, -120); g.moveTo(50, -6); g.lineTo(165, -105); g.stroke();
  g.restore();
}
const SETS = {
  deck: (g, W, H, t) => setDeck(g, W, H, t, false), deck2: (g, W, H, t) => setDeck(g, W, H, t, true), pool: setPool, map: setMap, cafe: setCafe,
  promenade: (g, W, H, t, u) => setPromenade(g, W, H, t, u * .12), halong: (g, W, H, t) => setHalong(g, W, H, t, false), halong2: (g, W, H, t) => setHalong(g, W, H, t, true),
  angkor: setAngkor, street: setStreet, rice: setRice, airport: setAirport,
};

// ---------------------------------------------------------------- acting: what the lion does, keyed to the scene's lines
const blinkAt = (u, seed) => { const ph = (u + hash(seed) * 3) % 3.4; return ph < .14 ? Math.sin(ph / .14 * Math.PI) : 0; };
const ACTS = {
  hook: (u, d, b, l) => {                                     // friendly; on the second line the head tilts and a paw opens
    const q = seg(u, l.l1 - .4, l.l1 + .3);
    return { cam: lerp(1, 1.08, ss(u / d)), X: 600, p: { ...b, tilt: -.12 * q, brow: .8 * q, armL: { sh: .15, el: .05 }, armR: { sh: lerp(.12, .9, eo(q)), el: lerp(.05, .9, eo(q)), paw: q > .4 ? 'open' : 'back' } } };
  },
  shrug: (u, d, b, l) => {
    const look = seg(u, 1.0, 1.8), sh = seg(u, l.l1 + .4, l.l1 + 1.0) * (1 - seg(u, d - .9, d - .3));
    return { cam: 1.04, cx: lerp(-30, 30, ss(u / d)), X: 470, Y: 1180, p: { ...b, lookX: lerp(-1, 0, look), lookY: lerp(.8, 0, look), shrug: sh, brow: .6 * sh, tilt: .05 * sh,
      armL: { sh: lerp(.2, .55, sh), el: lerp(1.6, 1.9, sh), paw: 'back' }, armR: { sh: lerp(.1, .6, sh), el: lerp(.05, .8, sh), paw: sh > .3 ? 'open' : 'back' } } };
  },
  present: (u, d, b, l) => {                                  // turns to show what is behind him, then back to us
    const show = seg(u, .3, 1.0) * (1 - seg(u, d - 2.2, d - 1.4)), back = seg(u, d - 2.2, d - 1.4);
    return { cam: lerp(1.04, 1, ss(u / d)), X: 330, Y: 1270, K: .9, p: { ...b, lookX: lerp(0, 1, show), tilt: .06 * show, smile: .9, brow: .3,
      armL: { sh: .12, el: .05 }, armR: { sh: lerp(.12, 1.45, eo(show)) + .1 * back, el: lerp(.05, .25, eo(show)), paw: show > .4 || back > .2 ? 'open' : 'back' } } };
  },
  seated: (u, d, b, l) => {                                   // looks down at the table, then up at us
    const up = seg(u, l.l0 + 1.2, l.l0 + 1.9);
    return { cam: lerp(1, 1.06, ss(u / d)), cy: 60, X: 540, Y: 1500, K: 1, p: { ...b, seated: true, lookY: lerp(1, 0, up), lookX: lerp(.3, 0, up), tilt: lerp(.1, 0, up), lid: lerp(.25, 0, up),
      armL: { sh: .55, el: 1.0, paw: 'back' }, armR: { sh: .5 + Math.sin(u * 3) * .02 * (1 - up), el: 1.15, paw: 'back' } } };
  },
  list: (u, d, b, l) => {
    const dream = 1 - seg(u, l.l1 - .6, l.l1 - .2), read = seg(u, l.l1 - .5, l.l1 + .6), ask = seg(u, l.l1 + .8, l.l1 + 1.3);
    return { X: 470, Y: 1500, K: .95, p: { ...b, seated: true, lid: .35 * dream, smile: lerp(.9, .4, read), lookX: dream > .5 ? -.8 : lerp(.9, 0, ask), lookY: dream > .5 ? .6 : lerp(-.6 + read * 1.4, 0, ask),
      tilt: lerp(-.06, .08, ask), brow: lerp(0, .9, ask), armR: { sh: 1.55, el: .6, paw: 'back' }, armL: { sh: lerp(.3, .9, ask), el: lerp(1.3, 1.0, ask), paw: ask > .3 ? 'open' : 'back' } } };
  },
  walk: (u, d, b, l) => {
    const turn = seg(u, 2.2, 3.0);
    return { cam: lerp(1.08, 1, ss(u / d)), X: 520, Y: 1080, K: .82, p: { ...b, walk: u * .55, tail: true, lookX: lerp(1, 0, turn), tilt: lerp(.06, 0, turn), wind: .8,
      armL: { sh: .08, el: .05, paw: 'pocket' }, armR: { sh: .08, el: .05, paw: 'pocket' } } };
  },
  invite: (u, d, b, l) => {
    const inv = seg(u, l.l0 - .2, l.l0 + .5), nod = Math.sin(clamp((u - (l.lEnd - .2)) / .6) * Math.PI) * .12;
    return { cam: lerp(1, 1.07, ss(u / d)), X: 480, p: { ...b, tilt: nod * .4, lookY: nod * 2, brow: .3, smile: .9,
      armL: { sh: lerp(.15, .95, eo(inv)), el: lerp(.05, .75, eo(inv)), paw: inv > .4 ? 'open' : 'back' }, armR: { sh: -.35, el: .55, paw: 'back' } } };
  },
};
const DEFAULT_ACT = { deck: 'hook', pool: 'shrug', map: 'seated', cafe: 'list', promenade: 'walk', deck2: 'invite', halong: 'hook', halong2: 'invite', angkor: 'present', street: 'seated', rice: 'walk', airport: 'present' };

export function makeCartoon(ins, W, H, ctx) {
  const off = document.createElement('canvas'); off.width = W; off.height = H; const g = off.getContext('2d');
  const act = ACTS[ins.act ?? DEFAULT_ACT[ins.set]], set = SETS[ins.set];
  return function draw(s, t, alpha, rise, ctxt) {
    const u = t - s.t0, d = s.t1 - s.t0, L = ctxt.lines(s);
    const l = { l0: L[0] ? L[0].t0 - s.t0 : .5, l1: (L[1]?.t0 ?? s.t1) - s.t0, lEnd: L.at(-1) ? L.at(-1).end - s.t0 : d - .8 };
    const base = { blink: blinkAt(u, s.t0), mouth: ctxt.mouth(t), smile: .6, wind: .5, lookX: 0, lookY: 0, brow: 0 };
    const a = { cam: 1, cx: 0, cy: 0, X: 540, Y: 1240, K: .95, ...act(u, d, base, l) };
    if (ins.set === 'airport') Object.assign(a, { X: 470, Y: 1330, K: .86, cam: 1 });   // under the board, which hangs at the top
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, W, H);
    g.save(); set(g, W, H, t, u); g.restore();
    const hands = lion(g, a.X, a.Y, a.K, a.p, t);
    if (ins.set === 'pool') {                                  // booklet in the far paw
      const [hx, hy] = hands.L; g.save(); g.translate(hx + 10, hy - 30); g.rotate(-.25);
      g.fillStyle = '#5BA7D6'; g.fillRect(-40, -60, 80, 110); g.strokeStyle = P.ink; g.lineWidth = 4; g.strokeRect(-40, -60, 80, 110);
      g.fillStyle = '#7FAE8A'; g.fillRect(-40, 0, 80, 50); g.restore();
    }
    if (ins.set === 'map') { tableTop(g, W, 1320); mapPaper(g, 300, 1380, 520, 300, t, seg(u, .3, 3)); cup(g, 150, 1430, .9); }
    if (ins.set === 'street') { tableTop(g, W, 1320); bowl(g, 560, 1470, 1, t); cup(g, 170, 1440, .8); }
    if (ins.set === 'map' || ins.set === 'street') { const [hx] = hands.R; paw(g, [Math.min(hx, 760), 1500], 'back', 1); paw(g, [300, 1470], 'back', -1); }
    if (ins.set === 'cafe') { tableTop(g, W, 1420); cup(g, 260, 1500, .85); const [hx, hy] = hands.R; listPaper(g, hx, hy - 30, hx + 70, 1880, t); paw(g, [hx, hy - 20], 'back', 1); }
    if (ins.set === 'deck2' || ins.set === 'halong2') {
      g.fillStyle = ins.set === 'deck2' ? P.rail : '#8A5A33'; g.strokeStyle = P.ink; g.lineWidth = 4; g.fillRect(560, 1238, W, 26); g.strokeRect(560, 1238, W + 20, 26); paw(g, [hands.R[0], 1236], 'back', 1);
    }
    ctx.save(); ctx.globalAlpha = alpha;
    ctx.translate(W / 2 + a.cx, H / 2 + a.cy); ctx.scale(a.cam, a.cam); ctx.translate(-W / 2, -H / 2); ctx.drawImage(off, 0, 0);
    // the airport board is drawn on the frame, so its labels are real text the reading check sees
    if (ins.set === 'airport' && ins.stops) {
      ctx.restore(); ctx.save(); ctx.globalAlpha = alpha;
      routeBoard(ctx, 60, 110, W - 120, 400, ins.stops, u, (txt, x, y, f, c, p, al, id) => rise(txt, x, y, f, c, p, al, id));
    }
    ctx.restore();
  };
}
