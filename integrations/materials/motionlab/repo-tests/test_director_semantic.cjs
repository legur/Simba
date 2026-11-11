'use strict';
const assert=require('node:assert/strict');
const path=require('node:path');
const core=require(path.join(__dirname,'..','director_core.js'));
const semantic=require(path.join(__dirname,'..','director_semantic.js'));
const scenes=[
 {id:'scene-01',asset:'sha-bavaria-a'},
 {id:'scene-02',asset:'sha-bavaria-b'},
 {id:'scene-03',asset:'sha-bavaria-c'}
];
const inputs=[
 {scene_id:'scene-01',asset_id:'sha-bavaria-a',type:'video',signal:{motion:39,brightness:93,edge:25}},
 {scene_id:'scene-02',asset_id:'sha-bavaria-b',type:'video',signal:{motion:47,brightness:101,edge:25}},
 {scene_id:'scene-03',asset_id:'sha-bavaria-c',type:'video',signal:{motion:16,brightness:125,edge:16}}
];
const annotation={schema:'bontours.motionlab.editorial-annotations/v1',source:'human-reviewed',scenes:[
 {scene_id:'scene-01',asset_id:'sha-bavaria-a',kind:'landmark',text_burned_in:true,must_remain_readable:false,description:'historic cathedral'},
 {scene_id:'scene-02',asset_id:'sha-bavaria-b',kind:'ambience',text_burned_in:true,must_remain_readable:false},
 {scene_id:'scene-03',asset_id:'sha-bavaria-c',kind:'cta',text_burned_in:true,must_remain_readable:true,speech_cue:'Позвоните'}
]};
const data=semantic.enrich(core.buildPlans(inputs),annotation,scenes);
assert.equal(data.plans.length,3);
assert.equal(data.recommended,2);
for(const plan of data.plans){
 const end=plan.scenes[2];
 assert.equal(end.camera,'cinematic-zoom');
 assert.equal(end.intensity,0);
 assert.equal(end.transition,'crossfade');
 assert.equal(end.titleFx,'none');
 assert.equal(end.editorial_review_required,true);
 assert.equal(plan.scenes[0].titleFx,'none');
 assert.equal(plan.scenes[0].protected,false);
 assert.equal(plan.scenes[0].scene_id,'scene-01');
}
assert.throws(()=>semantic.validate({...annotation,source:'auto-detected'},scenes),/источник/);
assert.throws(()=>semantic.validate({...annotation,scenes:annotation.scenes.map(x=>({...x,asset_id:'wrong'}))},scenes),/не совпадает/);
assert.throws(()=>semantic.validate({...annotation,scenes:annotation.scenes.slice(1)},scenes),/Количество/);
assert.throws(()=>semantic.validate({...annotation,scenes:[annotation.scenes[0],annotation.scenes[0],annotation.scenes[2]]},scenes),/Повтор/);
console.log('Motion Lab semantic editor guard test: PASS');