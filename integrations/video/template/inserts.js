// Code-drawn insert scenes for the photo-story: an animated route map. Brand palette, data only from the approved post.
import { clamp, lerp, seg, eo, eio } from '/engine/lib.js';

// Hand-simplified coastlines of the western Mediterranean (lon, lat). A stylized drawing, not a survey map.
const COASTS = [
  [[3.2, 41.9], [3.17, 42.4], [3.05, 43.0], [3.5, 43.3], [4.5, 43.45], [5.37, 43.3], [6.0, 43.1], [6.6, 43.2], [7.27, 43.7], [8.0, 43.9], [8.93, 44.41], [9.8, 44.07], [10.3, 43.5], [10.5, 42.95], [11.1, 42.4], [11.8, 42.1], [12.5, 41.6], [13.0, 41.25], [13.7, 41.22], [14.05, 40.85], [14.25, 40.82], [14.45, 40.66], [14.34, 40.59], [14.6, 40.63], [14.8, 40.66], [14.95, 40.42], [15.05, 40.2], [15.6, 40.0], [15.8, 39.5], [16.1, 38.9], [15.65, 38.25], [15.9, 37.95], [16.4, 38.4]],
  [[12.4, 37.8], [13.36, 38.12], [14.5, 38.05], [15.55, 38.25], [15.1, 37.5], [15.1, 36.7], [14.3, 37.0], [12.6, 37.6], [12.4, 37.8]],
  [[9.2, 41.25], [9.8, 40.9], [9.7, 40.0], [9.6, 39.2], [9.0, 39.0], [8.4, 39.0], [8.4, 39.9], [8.2, 40.6], [8.6, 40.9], [9.2, 41.25]],
  [[9.4, 43.0], [9.55, 42.6], [9.4, 41.6], [9.2, 41.4], [8.8, 41.6], [8.6, 42.1], [8.7, 42.6], [9.3, 43.0], [9.4, 43.0]],
];

function catmull(pts, n = 8) {
  const out = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
    for (let k = 0; k < n; k++) {
      const t = k / n, t2 = t * t, t3 = t2 * t;
      out.push([0, 1].map(j => .5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)));
    }
  }
  out.push(pts.at(-1)); return out;
}
const cum = pts => { const L = [0]; for (let i = 1; i < pts.length; i++) L.push(L[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])); return L; };

export function makeRoute(ins, W, ctx, C, TITLE, SANS) {
  const b = ins.bounds ?? [4.6, 16.4, 37.6, 44.7];          // lon0, lon1, lat0, lat1
  const x0 = 60, kx = (W - 120) / (b[1] - b[0]), ky = kx * 1.32, y0 = 300;
  const P = ([lo, la]) => [x0 + (lo - b[0]) * kx, y0 + (b[3] - la) * ky];
  const mapH = (b[3] - b[2]) * ky;
  const coasts = COASTS.map(c => catmull(c.map(P), 6));
  // ins.path: [[lon, lat, "Port"?], …] in sailing order; a named point is a stop, the route reaches it at its own key
  const SEG = 10, path = catmull(ins.path.map(P), SEG), L = cum(path), tot = L.at(-1), seen = new Set();
  const ports = ins.path.flatMap((k, i) => {
    if (!k[2]) return [];
    const [x, y] = P(k), first = !seen.has(k[2]); seen.add(k[2]);
    return [{ name: k[2], ...(ins.ports?.[k[2]] ?? {}), x, y, f: L[i * SEG] / tot, i, first }];
  });
  const arrive = p => p.f;
  return function draw(s, t, alpha, rise, texts) {
    const dur = s.t1 - s.t0, u = t - s.t0, draw0 = .6, draw1 = Math.min(dur - 1.2, 6.2);
    const prog = eio(seg(u, draw0, draw1));
    ctx.save(); ctx.globalAlpha = alpha;
    const g = ctx.createLinearGradient(0, 0, 0, 1920); g.addColorStop(0, '#13243F'); g.addColorStop(1, C.navy);
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, 1920);
    // graticule
    ctx.strokeStyle = 'rgba(244,235,221,.08)'; ctx.lineWidth = 1.2; ctx.beginPath();
    for (let lo = Math.ceil(b[0]); lo <= b[1]; lo += 2) { const [x] = P([lo, 0]); ctx.moveTo(x, y0); ctx.lineTo(x, y0 + mapH); }
    for (let la = Math.ceil(b[2]); la <= b[3]; la += 1) { const [, y] = P([0, la]); ctx.moveTo(x0, y); ctx.lineTo(W - 60, y); }
    ctx.stroke();
    // land: the mainland closes over the top of the map, islands are closed outlines; filled a step lighter than the sea
    ctx.save(); ctx.beginPath(); ctx.rect(x0, y0, W - 120, mapH); ctx.clip();
    ctx.globalAlpha = alpha * eo(seg(u, 0, .8)); ctx.fillStyle = '#1F3658';
    const top = y0 - 200;
    ctx.beginPath(); coasts[0].forEach((q, i) => i ? ctx.lineTo(...q) : ctx.moveTo(...q));
    ctx.lineTo(W + 200, coasts[0].at(-1)[1]); ctx.lineTo(W + 200, top); ctx.lineTo(-200, top); ctx.lineTo(-200, coasts[0][0][1]); ctx.closePath(); ctx.fill();
    for (const c of coasts.slice(1)) { ctx.beginPath(); c.forEach((q, i) => i ? ctx.lineTo(...q) : ctx.moveTo(...q)); ctx.closePath(); ctx.fill(); }
    ctx.globalAlpha = alpha;
    // coastlines draw in during the first second (inside the same frame)
    const cp = eo(seg(u, 0, 1.0));
    ctx.strokeStyle = 'rgba(244,235,221,.55)'; ctx.lineWidth = 2.6; ctx.lineJoin = ctx.lineCap = 'round';
    for (const c of coasts) {
      const n = Math.max(2, Math.floor(c.length * cp)); ctx.beginPath(); ctx.moveTo(...c[0]);
      for (let i = 1; i < n; i++) ctx.lineTo(...c[i]); ctx.stroke();
    }
    ctx.restore(); ctx.globalAlpha = alpha;
    ctx.strokeStyle = 'rgba(226,182,91,.45)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.roundRect(x0, y0, W - 120, mapH, 6); ctx.stroke();
    // the route, dashed gold, drawn by arc length
    if (prog > 0) {
      const d = tot * prog; ctx.strokeStyle = C.gold; ctx.lineWidth = 4.5; ctx.setLineDash([16, 12]); ctx.beginPath(); ctx.moveTo(...path[0]);
      let hx = path[0][0], hy = path[0][1];
      for (let i = 1; i < path.length; i++) {
        if (L[i] <= d) { ctx.lineTo(...path[i]); hx = path[i][0]; hy = path[i][1]; }
        else { const f = (d - L[i - 1]) / (L[i] - L[i - 1]); hx = lerp(path[i - 1][0], path[i][0], f); hy = lerp(path[i - 1][1], path[i][1], f); ctx.lineTo(hx, hy); break; }
      }
      ctx.stroke(); ctx.setLineDash([]);
      if (prog < 1) {                                       // the ship marker at the head
        const r = ctx.createRadialGradient(hx, hy, 0, hx, hy, 26); r.addColorStop(0, 'rgba(226,182,91,.9)'); r.addColorStop(1, 'rgba(226,182,91,0)');
        ctx.fillStyle = r; ctx.fillRect(hx - 26, hy - 26, 52, 52); ctx.fillStyle = C.cream; ctx.beginPath(); ctx.arc(hx, hy, 7, 0, 7); ctx.fill();
      }
    }
    // ports light up when the route reaches them
    for (const p of ports) {
      const k = p.f === 0 ? u - draw0 : (prog - arrive(p)) * (draw1 - draw0); if (k < -1e-6) continue;
      const a = clamp((k + .05) / .25), pass = p.kind === 'pass';
      ctx.fillStyle = C.gold; ctx.strokeStyle = C.gold; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(p.x, p.y, (pass ? 9 : 11) * eo(a), 0, 7); pass ? ctx.stroke() : ctx.fill();
      if (!pass) { ctx.globalAlpha = alpha * .35 * (1 - clamp(k / .8)); ctx.beginPath(); ctx.arc(p.x, p.y, 11 + 30 * clamp(k / .8), 0, 7); ctx.stroke(); ctx.globalAlpha = alpha; }
      const [dx, dy, al] = p.label ?? [18, -16, 'left'];
      if (p.first) rise(p.name, p.x + dx, p.y + dy, `${pass ? 'italic 500 28px' : '600 32px'} ${SANS}`, pass ? 'rgba(244,235,221,.85)' : C.cream, a, al, `port-${p.name}`);
    }
    // title and the day list
    rise(ins.title, W / 2, 200, `700 68px ${TITLE}`, C.cream, seg(u, .1, .7), 'center', 'route-title');
    const ry = y0 + mapH + 70, step = ins.rows.length > 7 ? 60 : 68;
    ins.rows.forEach((row, i) => {
      const p = seg(u, .9 + i * .22, 1.5 + i * .22), y = ry + i * step;
      const [date, rest] = row.split(' · ');
      ctx.font = `700 32px ${SANS}`; const dw = ctx.measureText(date + '  ').width;
      rise(date, 80, y, `700 32px ${SANS}`, C.gold, p, 'left', `row-${i}-d`);
      rise(rest ?? '', 80 + dw, y, `500 32px ${SANS}`, C.cream, p, 'left', `row-${i}-r`);
    });
    ctx.restore();
  };
}
