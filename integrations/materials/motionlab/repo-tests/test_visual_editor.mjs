import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createContext,runInContext} from 'node:vm';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const storyboard=readFileSync(resolve(root,'storyboard.js'),'utf8').replace(/\bwire\(\);\s*$/,'');
const visual=readFileSync(resolve(root,'visual_editor.js'),'utf8');
const registry=new Map();
const element=id=>{
 if(!registry.has(id)){
  registry.set(id,{
   id,style:{},className:'',value:'',textContent:'',innerHTML:'',disabled:false,hidden:false,checked:true,
   clientWidth:240,dataset:{},handlers:{},
   classList:{add(){},remove(){},toggle(){}},setAttribute(){},append(){},replaceChildren(){},
   addEventListener(event,cb){(this.handlers[event]??=[]).push(cb);},
   getBoundingClientRect(){return {left:0,top:0,width:240,height:426};},
   setPointerCapture(){},getAnimations(){return []},pause(){},load(){},removeAttribute(){}
  });
 }
 return registry.get(id);
};
const ctx=createContext({
 document:{readyState:'loading',getElementById:element,querySelectorAll(){return []},createElement(){return {value:'',textContent:''}}},
 window:{addEventListener(){}},
 performance:{now(){return 0}},
 cancelAnimationFrame(){},requestAnimationFrame(){return 1},
 clearTimeout(){},setTimeout(){return 1}
});
runInContext(storyboard,ctx,{timeout:2500});
runInContext(visual,ctx,{timeout:2500});
runInContext("state.scenes=[makeScene({scene_id:'s1',asset_id:'a1',title_text:'Рим',subtitle_preview:'Субтитр',camera:'cinematic-zoom',subtitle_style:'clean'},0)];state.selectedIndex=0;state.request=null;",ctx);
const api=ctx.MotionLabVisual;
api.init();
test('initial position remains at visual defaults',()=>{
 const scene=runInContext('state.scenes[0]',ctx);
 assert.equal(api.get(scene,'title').x,50);
 assert.equal(api.get(scene,'subtitle').y,82);
 assert.equal(api.changed(),false);
});
test('slider updates layout and blocks v1 data loss',()=>{
 const slider=element('overlayX');
 slider.value='64';
 for(const cb of slider.handlers.input)cb({target:slider});
 const scene=runInContext('state.scenes[0]',ctx);
 assert.equal(api.get(scene,'title').x,64);
 assert.equal(api.changed(),true);
 assert.equal(element('downloadJson').disabled,true);
 assert.equal(element('downloadVisual').disabled,false);
 assert.ok(runInContext('rendererIssues(state.scenes)',ctx).some(x=>x.includes('Montage v2')));
});
test('dragging overlay stays within safe percentage bounds',()=>{
 const title=element('frameTitle');
 const event={pointerId:2,button:0,clientX:240*1.4,clientY:426*.73,currentTarget:title,preventDefault(){}};
 for(const cb of title.handlers.pointerdown)cb(event);
 for(const cb of title.handlers.pointermove)cb(event);
 for(const cb of title.handlers.pointerup)cb(event);
 const scene=runInContext('state.scenes[0]',ctx);
 assert.equal(api.get(scene,'title').x,64);
 assert.equal(api.get(scene,'title').y,73);
 assert.equal(element('sendToAgent').disabled,true);
});
test('draft cannot run paid or render actions',()=>{
 for(const keyword of ['DRAFT_NOT_DELIVERED','run_render:false','MONTAGE_V2_LAYOUT_SUPPORT','asset_id:s.asset']){
  assert.ok(visual.includes(keyword),keyword);
 }
 assert.ok(!visual.includes('fetch('));
 assert.ok(!visual.includes('upload('));
});
