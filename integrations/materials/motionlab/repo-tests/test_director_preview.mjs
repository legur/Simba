import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const src=readFileSync(resolve(root,'storyboard.js'),'utf8');
const script=src.replace(/\bwire\(\);\s*$/,'');
assert.notEqual(script,src,'script did not isolate the browser bootstrap');

const dom=new Map();
const node=id=>{
 if(!dom.has(id)){
  dom.set(id,{style:{},textContent:'',value:0,disabled:false,hidden:false,src:'',
   classList:{add(){},remove(){},toggle(){}},
   pause(){},removeAttribute(){},getAnimations(){return []},load(){}});
 }
 return dom.get(id);
};
const sandbox={
 document:{readyState:'loading',addEventListener(){},getElementById:node},
 performance:{now(){return 0}},
 requestAnimationFrame(){return 1},cancelAnimationFrame(){},
 clearTimeout(){},setTimeout(){return 1},
 URL:{revokeObjectURL(){}}
};
runInNewContext(script+'\nglobalThis.review={state,film,filmTotal,filmClock,filmTransitionFrame,approveReview,resetAck,rendererIssues,sendSelection};',sandbox,{timeout:2000});
const v=sandbox.review;
const s=(overrides={})=>({
 id:'scene-01',name:'Начало',asset:'asset-01',duration:5,
 camera:'float',transition:'none',titleFx:'fade-rise',title:'Утвержденный текст',
 subtitleStyle:'clean',subtitle:'Утвержденная речь',wordMotion:'karaoke',intensity:30,image:'city',...overrides
});
test('film timeline duration uses actual scene durations',()=>{
 v.state.scenes=[s(),s({id:'scene-02',duration:7}),s({id:'scene-03',duration:12})];
 assert.equal(v.filmTotal(),24);
 assert.equal(v.filmClock(0),'00:00');
 assert.equal(v.filmClock(61.9),'01:01');
});
test('visual crossfade and push are an interactive browser approximation, not MP4',()=>{
 const next=node('montageNext'),flash=node('montageFlash');
 v.filmTransitionFrame('crossfade',.5);
 assert.equal(next.style.opacity,'0.5');
 v.filmTransitionFrame('push',.25);
 assert.ok(next.style.transform.includes('75%'));
 v.filmTransitionFrame('flash',.5);
 assert.equal(flash.hidden,false);
});
test('review approval is explicit and reset by change',()=>{
 v.state.scenes=[s()];v.state.request=null;v.state.confirmed=false;
 v.approveReview();
 assert.equal(v.state.confirmed,true);
 assert.equal(node('sendToAgent').disabled,true,'no connected Montage receiver');
 v.resetAck();
 assert.equal(v.state.confirmed,false);
});
test('a connected app cannot bypass review with sendSelection()',()=>{
 v.state.scenes=[s()];v.state.request={id:'approved-source',projectId:'test',fingerprint:'a'.repeat(64)};
 v.state.bridge={source:{postMessage(){throw Error('should not send');}},origin:'https://host.example'};
 v.state.confirmed=false;
 v.sendSelection();
 assert.equal(v.state.sending,false);
});
test('approval remains distinct from renderer capability and delivery',()=>{
 v.state.bridge=null;v.state.request=null;v.state.scenes=[s()];
 v.approveReview();
 assert.equal(v.state.confirmed,true);
 assert.ok(v.rendererIssues(v.state.scenes).length>0,'preview-only effect');
 assert.equal(node('sendToAgent').disabled,true);
 assert.equal(node('handoffBadge').textContent,'ЧЕРНОВИК');
});
