'use strict';
const assert=require('node:assert/strict');
const core=require('../director_vision_core.js');
const hashes={
 bavaria:'ab4635b8398adfe6fda91126d68a6c6b708024f9be7bd9074e742fdf7c56e32b',
 prague:'a77cc034f957dec224bc5345bfdd818e8c2f6453f592cd356a3e195d1b11ed13'
};
const times={
 bavaria:[0,3,5.5,8.5,11,14,17,19.5,22.5,25,28,33.5,36.5,42,54.63],
 prague:[0,5,10,15,20,25.5,30.38]
};
function scenes(name){
 const bounds=times[name],sha=hashes[name];
 return bounds.slice(0,-1).map((start,i)=>{
  const end=bounds[i+1];
  return {
   id:'shot-'+String(i+1).padStart(2,'0')+'-'+Math.round(start*100),
   asset:'local-sha256:'+sha+':'+Math.round(start*1000)+'-'+Math.round(end*1000),
   clipRange:{start,end}
  };
 });
}
for(const name of ['bavaria','prague']){
 const list=scenes(name),result=core.matchArchived(hashes[name],list);
 assert.equal(result.length,list.length);
 assert.equal(result[0].scene_id,list[0].id);
 assert.equal(result.at(-1).kind,'cta');
 assert.equal(result.at(-1).must_remain_readable,true);
 const checked=core.toReviewedDocument(result,list);
 assert.equal(checked.source,'human-reviewed');
 assert.equal(checked.scenes.length,list.length);
 assert.equal(checked.scenes.at(-1).text_burned_in,true);
 const changed=scenes(name);changed[0]={...changed[0],asset:'tampered'};
 assert.equal(core.matchArchived(hashes[name],changed),null);
 const cutChanged=scenes(name);cutChanged[0].clipRange.start+=.1;
 assert.equal(core.matchArchived(hashes[name],cutChanged),null);
 assert.equal(core.matchArchived('0'.repeat(64),list),null);
}
const e=core.PROMPTS;
const confident=core.rankedVision([{label:e[3].label,score:.77},{label:e[0].label,score:.11}],0,3);
assert.equal(confident.kind,'route');
assert.equal(confident.uncertain,false);
const uncertain=core.rankedVision([{label:e[3].label,score:.44},{label:e[1].label,score:.42}],0,3);
assert.equal(uncertain.uncertain,true);
assert.equal(uncertain.kind,'ambience');
const final=core.rankedVision([{label:e[1].label,score:.7}],2,3);
assert.equal(final.must_remain_readable,true);
const offer=core.rankedVision([{label:e[4].label,score:.70}],0,3);
assert.equal(offer.kind,'offer');
assert.equal(offer.must_remain_readable,true);
const rows=core.matchArchived(hashes.prague,scenes('prague'));
const edited=[...rows];edited[2]={...edited[2],kind:'offer',must_remain_readable:false};
const doc=core.toReviewedDocument(edited,scenes('prague'));
assert.equal(doc.scenes[2].must_remain_readable,true);
assert.throws(()=>core.toReviewedDocument(edited,scenes('prague').slice(1)),/Полный разбор/);
console.log('Motion Lab exact-SHA ChatGPT archive and local CLIP review safeguards: PASS');
