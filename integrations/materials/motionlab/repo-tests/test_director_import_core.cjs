'use strict';
const assert=require('node:assert/strict');
const core=require('../director_import_core.js');
function sampled(duration,cutMarks){
 const times=[];for(let t=.25;t<duration-.2;t+=.5)times.push(Math.round(t*100)/100);
 const samples=[];let level=78;
 for(const t of times){
  if(cutMarks.some(c=>Math.abs(t-(c+.25))<.02))level=level<110?170:78;
  samples.push({time:t,grid:new Uint8Array(48*84).fill(level+(Math.round(t*2)%2))});
 }
 return samples;
}
const prague=core.segmentVideo(sampled(30.375,[5,10,15,20,25.5]),30.375);
assert.equal(prague.scenes.length,6);
assert.deepEqual(prague.scenes.slice(1).map(x=>x.start),[5,10,15,20,25.5]);
assert.equal(prague.scenes[0].start,0);
assert.equal(prague.scenes.at(-1).end,30.38);
const bavaria=core.segmentVideo(sampled(54.625,[3,5.5,8.5,11,14,17,19.5,22.5,25,28,33.5,36.5,42]),54.625);
assert.equal(bavaria.scenes.length,14);
assert.equal(bavaria.scenes.at(-1).end,54.63);
assert.ok(bavaria.scenes.every(x=>x.seconds>=1&&x.seconds<=20));
const plain=core.segmentVideo(sampled(44.125,[]),44.125);
assert.ok(plain.scenes.every(x=>x.seconds<=20));
assert.throws(()=>core.segmentVideo(sampled(4,[]),61),/60 секунд/);
const srt=`1
00:00:00,800 --> 00:00:04,000
Представьте: утро в Праге.

2
00:00:04,800 --> 00:00:06,000
Старинные крыши
`;
const cues=core.parseSrt(srt);
assert.equal(cues.length,2);
assert.equal(core.alignCues([{start:0,end:5},{start:5,end:10}],cues)[0].phrases.includes('Представьте'),true);
assert.equal(core.alignCues([{start:0,end:5},{start:5,end:10}],cues)[1].phrases.includes('крыши'),true);
assert.throws(()=>core.parseSrt('0001 random text'),/SRT/);
console.log('Full MP4 visual cut candidate and optional SRT timeline tests: PASS');
