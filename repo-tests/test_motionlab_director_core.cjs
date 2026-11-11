'use strict';
const assert=require('node:assert/strict');
const path=require('node:path');
const core=require(path.join(__dirname,'..','integrations','materials','motionlab','director_core.js'));
const flat=new Uint8ClampedArray(4*4*4);
for(let i=0;i<16;i++){flat[i*4]=120;flat[i*4+1]=120;flat[i*4+2]=120;flat[i*4+3]=255;}
const s=core.signature({width:4,height:4,data:flat});
assert.equal(s.mean,120);
assert.equal(s.contrast,0);
assert.equal(core.frameDifference(s.grid,new Uint8Array(16).fill(200)),80);
const rows=[
 {scene_id:'01',asset_id:'asset-a',type:'image',signal:{brightness:120,edge:28,motion:0}},
 {scene_id:'02',asset_id:'asset-b',type:'video',signal:{brightness:180,edge:12,motion:45}}
];
const result=core.buildPlans(rows);
assert.equal(result.plans.length,3);
assert.equal(result.recommended,2);
for(const plan of result.plans){
 assert.equal(plan.scenes.length,2);
 assert.equal(plan.scenes[0].transition,'none');
 assert.equal(plan.scenes[1].asset_id,'asset-b');
 assert.ok(['crossfade','push','lightleak'].includes(plan.scenes[1].transition));
}
assert.throws(()=>core.buildPlans([rows[0],rows[0]]),/Повторяются/);
assert.throws(()=>core.frameDifference(new Uint8Array(1),new Uint8Array(2)),/разного размера/);
assert.throws(()=>core.buildPlans([{scene_id:'01'}]),/реального/);
console.log('Motion Lab director core: PASS');
