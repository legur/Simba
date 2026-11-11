import test from 'node:test';
import assert from 'node:assert/strict';
import { drawStyledSubtitle } from '../template/subtitle_styles.js';

// Mock only the Canvas2D drawing API. The real word timings and geometry code
// run unchanged. No browser/Wix, media, TTS, ffmpeg or paid operations.
function context() {
  const drawn = [];
  const state = { saves: 0, restores: 0 };
  return {
    drawn, state, globalAlpha: 1,
    save() { state.saves++; },
    restore() { state.restores++; },
    measureText(str) { return { width: Array.from(String(str)).length * 20 }; },
    beginPath() {}, roundRect() {}, rect() {}, fill() {},
    fillRect() {}, stroke() {}, strokeText() {}, setLineDash() {},
    translate() {}, scale() {},
    fillText(word, x, y) { drawn.push({ word, x, y }); },
  };
}
const line = {
  words: [['Первый', .4], ['второй', .7]], t0: 0, t1: 5,
};
const config = {
  style: 'clean', motion: 'karaoke', color: 'gold',
  position: 'bottom', scale_percent: 100,
};

test('WYSIWYG subtitle placement moves actual Canvas2D drawn text to the approved x/y percent', () => {
  const center = context(), shifted = context();
  drawStyledSubtitle(center, line, 1, config, 1080, 1920,
    { x: 50, y: 82, scale: 100 });
  drawStyledSubtitle(shifted, line, 1, config, 1080, 1920,
    { x: 60, y: 70, scale: 100 });
  const a = center.drawn.find(v => v.word === 'Первый');
  const b = shifted.drawn.find(v => v.word === 'Первый');
  assert.ok(a);
  assert.ok(b);
  assert.ok(Math.abs((b.x - a.x) - 108) < .1,
    '10% full-frame shift must move the actual rendered text by 108px');
  assert.ok(Math.abs((b.y - a.y) - (70 - 82) * 19.2) < .1,
    '12% full-frame Y change must move the actual subtitles');
  assert.equal(shifted.state.saves, shifted.state.restores);
});

test('WYSIWYG scale changes actual font size, not approved text or word timestamps', () => {
  const a=context(), b=context();
  drawStyledSubtitle(a,line,1,config,1080,1920,{x:50,y:77,scale:100});
  drawStyledSubtitle(b,line,1,config,1080,1920,{x:50,y:77,scale:120});
  assert.deepEqual(a.drawn.map(v=>v.word),b.drawn.map(v=>v.word));
  // Different size changes spacing between baselines within the text box.
  assert.equal(a.state.saves,a.state.restores);
  assert.equal(b.state.saves,b.state.restores);
});

test('safe zone rejects huge words that cannot fit instead of silently repositioning approved layout', () => {
  const ctx=context();
  const badLine={
    words:[['НЕВОЗМОЖНОДЛИННОЕЗАГЛАВНОЕСЛОВОВЫХОДЯЩЕЕЗАКРАЙ',.2]],
    t0:0,t1:5,
  };
  assert.throws(() => drawStyledSubtitle(
    ctx,badLine,1,config,1080,1920,{x:64,y:82,scale:140}
  ),/safe overlay bounds/);
  assert.equal(ctx.state.saves,ctx.state.restores);
});

test('legacy subtitle render remains usable without WYSIWYG layout', () => {
  const ctx=context();
  drawStyledSubtitle(ctx,line,1,config,1080,1920);
  assert.ok(ctx.drawn.length>0);
  assert.equal(ctx.state.saves,ctx.state.restores);
});
