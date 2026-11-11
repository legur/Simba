import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';

const source=readFileSync(resolve(dirname(fileURLToPath(import.meta.url)),'../motionlab_v2_ui.js'),'utf8');
const origin='https://private-studio.example';
const fixtures=()=>{
 const media=[
   {scene_id:'scene-01',asset_id:'asset-01',media:{kind:'video',asset_sha256:'a'.repeat(64),duration_s:5,width:1080,height:1920,has_audio:false},locked:{title_text:'Рим',subtitle_preview:'Текст',read_only:true}},
   {scene_id:'scene-02',asset_id:'asset-02',media:{kind:'video',asset_sha256:'b'.repeat(64),duration_s:6,width:1080,height:1920,has_audio:false},locked:{title_text:'Венеция',subtitle_preview:'Текст',read_only:true}},
 ];
 const scenes=(camera,transition)=>media.map((s,i)=>({
   scene_id:s.scene_id,camera:{id:camera,intensity_percent:30},
   transition:i?{id:transition,duration_ms:900}:null,title_fx:'fade-rise',
   subtitle:{style_id:'clean',word_motion_id:'karaoke'},
 }));
 const materials={
   schema:'bontours.motionlab.materials.launch/v2',request_id:'request-1234',
   project_id:'project-1234',expected_input_fingerprint:'f'.repeat(64),
   scenes:media,renderer_capabilities:{
     camera:{renderable:['cinematic-zoom','push-through','float']},
     title_fx:{renderable:['fade-rise','none']},
     transition:{renderable:['crossfade','whip','postcard']},
     subtitle:{styles:['clean'],motions:['karaoke']},
     typography:{native_families_ready:['Arial','Georgia']},
   },
 };
 const proposals={
   schema:'bontours.motionlab.proposals/v2',
   request_id:materials.request_id,project_id:materials.project_id,
   expected_input_fingerprint:materials.expected_input_fingerprint,
   materials_sha256:'c'.repeat(64),
   proposals:[
     {option:1,title:'Первая рекомендация',recommended:true,
      rationale:'Реальные сцены требуют плавного темпа',scenes:scenes('cinematic-zoom','crossfade')},
     {option:2,title:'Вторая рекомендация',recommended:false,
      rationale:'Другой ритм подачи материалов',scenes:scenes('push-through','whip')},
     {option:3,title:'Третья рекомендация',recommended:false,
      rationale:'Более спокойная композиция кадров',scenes:scenes('float','postcard')},
   ],
 };
 return {materials,proposals,materials_sha256:'c'.repeat(64),proposals_sha256:'d'.repeat(64)};
};
function harness(){
 const payload=fixtures(), messages=[], listeners={}, toast=[];
 const parent={postMessage(data,target){messages.push({data,target});}};
 const state={scenes:[],confirmed:false,sending:false,selectedOption:1};
 const files=new Map();
 const theme={title:{family:'Georgia',color:'#ffffff',size:100},
              subtitle:{family:'Arial',color:'#ffffff',size:100}};
 const visual={
   get:(scene,kind)=>scene.visualLayout?.[kind]||({title:{x:50,y:47,scale:100},
     subtitle:{x:50,y:82,scale:100}})[kind],
   theme:kind=>({...theme[kind]}),
   typography:(scene,kind)=>scene.visualTypography?.[kind]||theme[kind],
   resetForProject(){},
 };
 const context={
   state,globalThis:null,
   window:{parent,opener:null,addEventListener(name,fn){listeners[name]=fn;}},
   expectedHostOrigin:()=>origin,goodSource:e=>e.source===parent,
   makeScene:(x)=>({
     id:x.scene_id,asset:x.asset_id,title:x.title_text,subtitle:x.subtitle_preview,
     name:x.name,duration:x.duration_s,media:x.media,camera:'cinematic-zoom',
   }),
   previewFor:s=>files.get(s.id),
   filmTotal:()=>state.scenes.reduce((sum,s)=>sum+s.duration,0),
   stopFilm(){},clearPreviews(){files.clear();},setConnection(){},
   resetAck(){state.confirmed=false;state.sending=false;state.lastAck=null;},
   render(){},renderSummary(){},say:m=>toast.push(m),
   clearTimeout(){},setTimeout(){return 1;},
   Date,Math,JSON,Number,String,Array,Object,Map,Set,Error,RegExp,
 };
 context.globalThis=context;context.globalThis.MotionLabVisual=visual;
 runInNewContext(source,context,{timeout:1500});
 function send(type,data,from=origin){
   listeners.message({source:parent,origin:from,data:{
     type,protocol:'bontours.motionlab.bridge/v2',
     request_id:payload.materials.request_id,
     project_id:payload.materials.project_id,
     payload:data,
   }});
 }
 function prepare(){
   send('SIMBA_MOTIONLAB_V2_START',payload);
   for(const s of state.scenes){
     files.set(s.id,{assetId:s.asset,type:'video',shaVerified:true,
                     duration:s.duration});
   }
 }
 return {state,files,toast,messages,send,prepare,bridge:context.MotionLabV2,
         theme,payload};
}

test('v2 announces readiness without inventing a project or faking ACK',()=>{
 const h=harness();
 assert.equal(h.messages[0].data.type,'SIMBA_MOTIONLAB_V2_READY');
 assert.equal(h.messages[0].data.request_id,null);
 assert.equal(h.state.v2,undefined);
});
test('reject a foreign origin, unavailable private media and changed scene ID',()=>{
 const h=harness();
 h.send('SIMBA_MOTIONLAB_V2_START',h.payload,'https://evil.example');
 assert.equal(h.state.v2,undefined);
 h.send('SIMBA_MOTIONLAB_V2_START',h.payload);
 assert.match(h.bridge.reviewIssue(),/Загрузите и проверьте исходный MP4/);
 h.state.scenes[0].asset='forged';
 assert.match(h.bridge.reviewIssue(),/Изменен порядок или источник/);
});
test('three genuine proposals and owner approval transfer exact scene typography',()=>{
 const h=harness();h.prepare();
 assert.equal(h.state.selectedOption,1);
 assert.equal(h.bridge.reviewIssue(),null);
 h.bridge.choose(2);
 assert.equal(h.state.scenes[1].transition,'whip');
 assert.equal(h.state.confirmed,false);
 h.state.scenes[1].visualTypography={
   title:{family:'Arial',color:'#123456',size:110},
 };
 h.state.scenes[1].visualLayout={
   title:{x:55,y:42,scale:110},
   subtitle:{x:45,y:80,scale:90},
 };
 h.state.confirmed=true;
 h.bridge.sendSelection();
 const emitted=h.messages.at(-1);
 assert.equal(emitted.data.type,'SIMBA_MOTIONLAB_V2_SELECTION');
 const sel=emitted.data.payload.selection;
 assert.equal(sel.schema,'bontours.motionlab.selection/v2');
 assert.equal(sel.proposals_sha256,h.payload.proposals_sha256);
 assert.equal(sel.materials_sha256,h.payload.materials_sha256);
 assert.equal(sel.decision.options_presented,3);
 assert.equal(sel.decision.visual_layout_edited,true);
 assert.deepEqual(JSON.parse(JSON.stringify(sel.scene_typography[1].typography)),
                  {title:{family:'Arial',color:'#123456',size:110}});
 assert.equal(sel.global_theme.typography.title.family,'Georgia');
 assert.equal(sel.scene_layout[1].layout.title.x,55);
 assert.equal(sel.guards.run_render,false);
 assert.equal(sel.guards.auto_publish,false);
 h.send('SIMBA_MOTIONLAB_V2_ACK',{
   accepted:true,delivery_id:emitted.data.payload.delivery_id,
   receipt_id:'motionlab:v2:'+'1'.repeat(64),
 });
 assert.ok(h.state.lastAck?.startsWith('motionlab:v2:'));
});
test('no approval cannot be transmitted; unedited layout is precisely flagged',()=>{
 const h=harness();h.prepare();
 h.bridge.sendSelection();
 assert.equal(h.messages.filter(x=>x.data.type==='SIMBA_MOTIONLAB_V2_SELECTION').length,0);
 h.state.confirmed=true;
 h.bridge.sendSelection();
 const selection=h.messages.at(-1).data.payload.selection;
 assert.equal(selection.decision.visual_layout_edited,false);
 assert.equal(selection.decision.explicit_approval,true);
});

test('stale ACK cannot approve a visual choice changed after submission',()=>{
 const h=harness();h.prepare();
 h.state.confirmed=true;
 h.bridge.sendSelection();
 const first=h.messages.at(-1).data.payload.delivery_id;
 h.bridge.cancelPending();
 h.state.sending=false;h.state.confirmed=false;
 h.send('SIMBA_MOTIONLAB_V2_ACK',{
   accepted:true,delivery_id:first,receipt_id:'motionlab:v2:'+'2'.repeat(64),
 });
 assert.equal(h.state.lastAck??null,null,
   'previous approval must not be attributed to a newer edit');
 h.state.confirmed=true;
 h.bridge.sendSelection();
 const second=h.messages.at(-1).data.payload.delivery_id;
 assert.notEqual(second,first);
 h.send('SIMBA_MOTIONLAB_V2_ACK',{
   accepted:true,delivery_id:first,receipt_id:'motionlab:v2:'+'2'.repeat(64),
 });
 assert.equal(h.state.lastAck??null,null);
 h.send('SIMBA_MOTIONLAB_V2_ACK',{
   accepted:true,delivery_id:second,receipt_id:'motionlab:v2:'+'3'.repeat(64),
 });
 assert.ok(h.state.lastAck?.endsWith('3'.repeat(64)));
});

test('uninstalled custom typeface cannot be approved even if browser preview draws it',()=>{
 const h=harness();h.prepare();
 h.state.scenes[0].visualTypography={
   title:{family:'Unbounded',color:'#ffffff',size:100},
 };
 assert.match(h.bridge.reviewIssue(),/шрифт title требует установки/);
 h.state.confirmed=true;
 h.bridge.sendSelection();
 assert.equal(h.messages.filter(x=>x.data.type==='SIMBA_MOTIONLAB_V2_SELECTION').length,0);
});
