/* Real GAS v2 Code.gs+CodeV2.gs evaluated against synthetic owner-private Drive.
 * No real Drive, credentials, user-approval forgery, render dispatch or A2E.
 */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import crypto from 'node:crypto';
import fs from 'node:fs';
import vm from 'node:vm';

const code=fs.readFileSync(new URL('../drive_handoff/Code.gs',import.meta.url),'utf8')+
  '\n'+fs.readFileSync(new URL('../drive_handoff/CodeV2.gs',import.meta.url),'utf8');
const ui=fs.readFileSync(new URL('../studio-v2.js',import.meta.url),'utf8');
const html=fs.readFileSync(new URL('../studio-v2.html',import.meta.url),'utf8');
const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
const sort=o=>Array.isArray(o)?o.map(sort):o&&typeof o==='object'
  ?Object.fromEntries(Object.keys(o).sort().map(k=>[k,sort(o[k])])):o;
const canonical=o=>JSON.stringify(sort(o));
const ticketId='T'.repeat(27),token='d'.repeat(64),fileId='F'.repeat(24);
const folders={ticket:'1lHQS4Pfl3OhDoxeWEL768C-XkBIcCxjs',
 source:'10IdAl9pS-YSqLEYFbfTIKNEoho7bWGWA',
 media:'1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj',
 inbox:'1gYNUU3HUeWnu2jEcs1gEf4cu9bEf4cu9LJEEPoD'};
folders.inbox='1gYNUU3HUeWnu2jEcs1gEf4cu9LJEEPoD';
const mp4=Buffer.concat([Buffer.from('synthetic-MP4-source'),Buffer.alloc(2048,7)]);
const assets=[{asset_id:'asset-01',file_id:fileId,sha256:sha(mp4),size_bytes:mp4.length,mime_type:'video/mp4'}];
const scene={
 scene_id:'scene-01',asset_id:'asset-01',name:'Сцена 1',
 media:{kind:'video',asset_sha256:sha(mp4),duration_s:4,width:240,height:426,has_audio:false},
 locked:{title_text:'Бавария',title_sha256:sha('Бавария'),
 subtitle_preview:'Путешествие',subtitle_sha256:sha('Путешествие'),read_only:true}
};
const caps={revision_sha256:'a'.repeat(64),
  camera:{renderable:['cinematic-zoom','push-through','float']},
  title_fx:{renderable:['none','fade-rise']},
  transition:{renderable:['crossfade','whip']},
  subtitle:{styles:['clean','luxury'],motions:['karaoke','active-pop','word-reveal']}};
const materials={
 schema:'bontours.motionlab.materials.launch/v2',
 project_id:'bavaria-test',request_id:'session-v2-01',
 expected_input_fingerprint:'b'.repeat(64),stage:'edit_choice',
 audio_alignment_status:'AUDIO_ALIGNMENT_VERIFIED_AUTO',
 scenes:[scene],renderer_capabilities:caps};
function eff(cam,motion){
 return {scene_id:'scene-01',camera:{id:cam,intensity_percent:35},
 transition:null,title_fx:'fade-rise',subtitle:{style_id:'clean',word_motion_id:motion}};
}
const proposals={
 schema:'bontours.motionlab.proposals/v2',project_id:materials.project_id,
 request_id:materials.request_id,
 expected_input_fingerprint:materials.expected_input_fingerprint,
 materials_sha256:sha(canonical(materials)),
 renderer_revision_sha256:caps.revision_sha256,
 analysis:{
  status:'REAL_VIDEO_AUTOMATICALLY_ANALYZED',
  analysis_method:'full_timeline_sampled_pixels_ffmpeg_v1',
  inspected_assets:[{scene_id:scene.scene_id,asset_sha256:scene.media.asset_sha256,
                     evidence_kind:'full_original_mp4'}],
  pixel_evidence:[{scene_id:scene.scene_id,asset_sha256:scene.media.asset_sha256,
                   sampled_frame_sha256:'c'.repeat(64)}],
 },
 proposals:[
  {option:1,title:'Элегантный',recommended:true,scenes:[eff('cinematic-zoom','karaoke')]},
  {option:2,title:'Энергичный',recommended:false,scenes:[eff('push-through','active-pop')]},
  {option:3,title:'Информационный',recommended:false,scenes:[eff('float','word-reveal')]}
 ]
};
const source={
 schema:'bontours.motionlab.owner-launch/v2',
 project_id:materials.project_id,
 request_id:materials.request_id,
 expected_input_fingerprint:materials.expected_input_fingerprint,
 materials,proposals,preview_assets:assets
};
const selection=()=>({
 schema:'bontours.motionlab.selection/v2',project_id:materials.project_id,
 request_id:materials.request_id,
 expected_input_fingerprint:materials.expected_input_fingerprint,
 materials_sha256:sha(canonical(materials)),
 proposals_sha256:sha(canonical(proposals)),
 format:'9:16',next_stage:'MONTAGE_PLANNING_REVIEW',
 decision:{
  selected_option:1,options_presented:3,
  state:'USER_SELECTED_IN_CONNECTED_SESSION',explicit_approval:true,
  visual_layout_edited:false,user_selected_at:new Date().toISOString()
 },
 guards:{
  run_render:false,run_tts:false,run_a2e:false,
  run_paid_operations:false,auto_publish:false,
  preserve_approved_voice:true,preserve_approved_music:true,
  preserve_approved_narration:true
 },
 scenes:[eff('cinematic-zoom','karaoke')]
});
function file(folder,raw,mime='application/json'){
 return {
  getParents(){let n=0;return{hasNext:()=>n===0,next:()=>{n++;return {getId:()=>folder}}}},
  getSharingAccess(){return 'PRIVATE'},
  getSize(){return Buffer.from(raw()).length},
  getMimeType(){return mime},
  getBlob(){return {getDataAsString:()=>String(raw()),getBytes:()=>Array.from(Buffer.from(raw()))}}
 };
}
function run(){
 const raw=()=>JSON.stringify(source);
 const ticket={
  schema:'bontours.motionlab.drive-ticket/v2',state:'ISSUED',
  project_id:materials.project_id,session_id:materials.request_id,
  source_fingerprint:materials.expected_input_fingerprint,
  materials_sha256:sha(canonical(materials)),
  proposals_sha256:sha(canonical(proposals)),
  source_launch_sha256:sha(raw()),source_launch_file_id:'L'.repeat(27),
  token_sha256:sha(token),expires_utc:new Date(Date.now()+3600000).toISOString()
 };
 const ticketFile=file(folders.ticket,()=>JSON.stringify(ticket));
 ticketFile.setContent=s=>Object.assign(ticket,JSON.parse(s));
 const src=file(folders.source,raw);
 const original=file(folders.media,()=>mp4,'video/mp4');
 const inboxFiles=new Map(),dispatches=[];
 const inbox={
  getFilesByName(name){
   let count=0;
   const entry=inboxFiles.get(name);
   return {hasNext:()=>!!entry&&count===0,next:()=>{
    count++;return Object.assign(file(folders.inbox,()=>JSON.stringify(entry)),{
      getId(){return 'I'.repeat(26)}
    })}}
  },
  createFile(name,text){inboxFiles.set(name,JSON.parse(text));return {getId:()=> 'I'.repeat(26)}}
 };
 const sandbox={
  Date,JSON,Error,Object,String,Array,Number,RegExp,Math,Boolean,Set,
  MimeType:{PLAIN_TEXT:'text/plain'},
  Utilities:{DigestAlgorithm:{SHA_256:'sha256'},Charset:{UTF_8:'UTF-8'},
    computeDigest(_a,value){return [...crypto.createHash('sha256')
      .update(Array.isArray(value)?Buffer.from(value):value).digest()]
      .map(n=>n>127?n-256:n)},
    newBlob:s=>({getBytes:()=>Array.from(Buffer.from(s))}),
    getUuid:()=> 'ed103ff4-9987-44cc-aea3-b17be140086d',
    base64Encode:bytes=>Buffer.from(bytes).toString('base64')},
  HtmlService:{
    XFrameOptionsMode:{ALLOWALL:'ALLOWALL'},
    createHtmlOutput:html=>({html,setXFrameOptionsMode(){return this}})
  },
  LockService:{getScriptLock:()=>({tryLock(){return true},releaseLock(){}})},
  DriveApp:{
    Access:{PRIVATE:'PRIVATE'},
    getFileById(id){
      if(id===ticketId)return ticketFile;
      if(id==='L'.repeat(27))return src;
      if(id===fileId)return original;
      throw Error('No arbitrary Drive reads');
    },
    getFolderById(id){
      if(id===folders.inbox)return inbox;
      throw Error('No arbitrary Drive folders');
    }
  },
 };
 const ctx=vm.createContext(sandbox);
 vm.runInContext(code,ctx);
 // The real v1 dispatch must NEVER be called for a v2 selection.
 ctx.motionlabRegisterQueue=v=>{dispatches.push(v);throw Error('v1 dispatch forbidden')};
 const post=vm.runInContext('doPost',ctx);
 const request=(operation,settings={})=>({
  parameter:{
   operation,nonce:'22222222-2222-4222-8222-222222222222',
   ticket_id:ticketId,ticket_token:token,...settings
  }
 });
 const submit=(pick=selection())=>post(request('v2_submit',{
  selection_json:JSON.stringify(pick),selection_sha256:sha(canonical(pick))
 }));
 return {ctx,post,request,submit,ticket,source,inboxFiles,dispatches};
}
test('Separate standalone v2 Studio requires private fragment and no demo/auto publish',()=>{
 assert.match(html,/id="options"/);
 assert.match(html,/id="ownerConfirm"/);
 assert.match(ui,/#project_v2=/);
 assert.match(ui,/ownerConfirm/);
 assert.match(ui,/SIMBA_DRIVE_V2_RECEIPT/);
 assert.match(ui,/v2_submit/);
 assert.match(ui,/V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS/);
 assert.doesNotMatch(ui,/GDRIVE_OAUTH_CLIENT_SECRET|MOTIONLAB_GITHUB_ACTIONS_TOKEN/);
});
test('v2 project read includes three options and omits raw Drive file IDs',()=>{
 const e=run(),ret=e.post(e.request('v2_load')).html;
 assert.match(ret,/V2_PROJECT_READY/);
 assert.match(ret,/Энергичный/);
 assert.doesNotMatch(ret,new RegExp(fileId));
 assert.doesNotMatch(ret,new RegExp(token));
});
test('v2 asset read gives only exact owner-private matching MP4 bytes',()=>{
 const e=run(),ret=e.post(e.request('v2_asset',{asset_id:'asset-01'})).html;
 assert.match(ret,/V2_ASSET_READY/);
 assert.match(ret,new RegExp(sha(mp4)));
 assert.match(e.post(e.request('v2_asset',{asset_id:'other'})).html,/V2_ASSET_NOT_IN_PROJECT/);
});
test('One owner-approved v2 selection is saved once, never sent to v1 queue',()=>{
 const e=run(),ownerChoice=selection(),ret=e.submit(ownerChoice).html;
 assert.match(ret,/V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS/);
 assert.equal(e.inboxFiles.size,1);
 const item=[...e.inboxFiles.values()][0];
 assert.equal(item.schema,'bontours.motionlab.drive-inbox/v2');
 assert.equal(item.selection.decision.selected_option,1);
 assert.equal(item.render_authorized,false);
 assert.equal(item.canonical_applied,false);
 assert.equal(item.published,false);
 assert.equal(e.ticket.consumed_receipt_id,item.receipt_id);
 assert.equal(e.dispatches.length,0);
 // An idempotent retry must be byte-identical, including approval time.
 assert.match(e.submit(ownerChoice).html,/V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS/);
 assert.equal(e.inboxFiles.size,1);
});
test('Tampering project, option hashes, approval or paid guards fails closed',()=>{
 const scenarios=[
  ['source',p=>p.project_id='wrong','V2_SELECTION_SOURCE_MISMATCH'],
  ['hash',p=>p.proposals_sha256='f'.repeat(64),'V2_SELECTION_SOURCE_MISMATCH'],
  ['approve',p=>p.decision.explicit_approval=false,'V2_EXPLICIT_OWNER_APPROVAL_MISSING'],
  ['paid',p=>p.guards.run_tts=true,'V2_EXECUTION_GUARDS_INVALID'],
  ['foreign',p=>p.scenes[0].scene_id='wrong','V2_SCENE_BINDING_MISMATCH'],
  ['unknown-camera',p=>p.scenes[0].camera.id='orbit','V2_UNSUPPORTED_EFFECT'],
  ['unknown-title',p=>p.scenes[0].title_fx='punch-zoom','V2_UNSUPPORTED_EFFECT'],
  ['unknown-style',p=>p.scenes[0].subtitle.style_id='glitch','V2_UNSUPPORTED_SUBTITLE'],
  ['wrong-transition',p=>p.scenes[0].transition={id:'crossfade',duration_ms:900},'V2_UNSUPPORTED_TRANSITION'],
  ['extra-source',p=>p.scenes[0].media_url='https://example.com/a','V2_SCENE_BINDING_MISMATCH']
 ];
 for(const [name,mutate,code] of scenarios){
  const e=run(),p=selection();mutate(p);
  assert.match(e.submit(p).html,new RegExp(code),name);
  assert.equal(e.inboxFiles.size,0,name);
  assert.equal(e.dispatches.length,0,name);
 }
});
test('Reject expired tickets, changed launch bytes, forged requests and replay',()=>{
 const e=run();
 e.ticket.expires_utc=new Date(Date.now()-3600000).toISOString();
 assert.match(e.submit().html,/V2_TICKET_EXPIRED/);
 assert.equal(e.inboxFiles.size,0);
 e.ticket.expires_utc=new Date(Date.now()+3600000).toISOString();
 e.ticket.source_launch_sha256='f'.repeat(64);
 assert.match(e.post(e.request('v2_load')).html,/V2_SOURCE_CHANGED/);
 assert.equal(e.inboxFiles.size,0);
 e.ticket.source_launch_sha256=sha(JSON.stringify(source));
 const pick=selection();
 assert.match(e.post(e.request('v2_submit',{
  selection_json:JSON.stringify(pick),selection_sha256:'0'.repeat(64)
 })).html,/V2_SELECTION_HASH_MISMATCH/);
 assert.equal(e.inboxFiles.size,0);
 assert.match(e.submit().html,/V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS/);
 const other=selection();other.decision.selected_option=3;
 assert.match(e.submit(other).html,/V2_TICKET_ALREADY_USED/);
 assert.equal(e.inboxFiles.size,1);
 assert.equal(e.dispatches.length,0);
});
