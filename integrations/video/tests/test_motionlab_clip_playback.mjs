/* Verify the ACTUAL film.js frame sampler, no paid calls/no rendering.
 * Alaska's approved legacy FFmpeg footage uses setpts stretching, not
 * automatically invented repeated A2E footage or frozen last frames.
 */
import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import vm from 'node:vm';
const src=fs.readFileSync(new URL('../template/film.js',import.meta.url),'utf8');
const start=src.indexOf('const frameOf = (s, t) => {');
const end=src.indexOf('\n};',start);
assert.ok(start>0 && end>start,'real frameOf found in production template');
const statement=src.slice(start,end+3)+'\nframeOf;';
const ctx=vm.createContext({
  Math,String,
  clamp:(n,lo,hi)=>Math.min(hi,Math.max(lo,n)),
});
const frame=vm.runInContext(statement,ctx);
const clip={
 frames:'out/frames/s01/', count:120,fps:24,
 t0:0,t1:8.1,clipPlayback:'stretch',
};
const num=(s,t)=>Number(frame(s,t).slice(-9,-4));
test('Alaska 5-second clip is uniformly stretched across approved 8.1s scene',()=>{
 assert.equal(num(clip,0),1);
 assert.ok(num(clip,2)<55);
 assert.ok(num(clip,4.05)>=59 && num(clip,4.05)<=62);
 assert.equal(num(clip,8.1),120);
 assert.equal(num(clip,20),120);
});
test('Repeat-loop is opt-in and different from source time stretch',()=>{
 const loop={...clip,clipPlayback:'loop'};
 assert.equal(num(loop,0),1);
 assert.equal(num(loop,5),1);
 assert.equal(num(loop,8.1),75);
});
test('Unchanged legacy freeze holds last frame, not a newly introduced loop',()=>{
 const hold={...clip,clipPlayback:'freeze'};
 assert.equal(num(hold,0),1);
 assert.equal(num(hold,5),120);
 assert.equal(num(hold,8),120);
});
