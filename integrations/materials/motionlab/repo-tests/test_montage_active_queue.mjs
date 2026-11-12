/* Offline validation for on-demand Apps Script -> GitHub dispatch queue.
 * No real GitHub, Apps Script, Drive credentials or external network.
 */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import crypto from 'node:crypto';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync(new URL('../drive_handoff/Code.gs',import.meta.url),'utf8');
const hash=raw=>crypto.createHash('sha256').update(raw).digest('hex');
const select={schema:'bontours.motionlab.storyboard.selection/v1',
  request_id:'studio-qa',project_id:'test-project',
  expected_input_fingerprint:'a'.repeat(64),
  decision:{selected_option:1,options_presented:3,state:'DRAFT_NOT_DELIVERED',
    confirmation_scope:'EDIT_CHOICES_ONLY'},
  scenes:[{scene_id:'qa-1',duration_seconds:4}],
  guards:{run_render:false,run_tts:false,run_a2e:false,run_paid_operations:false,
    auto_publish:false,preserve_approved_voice:true,preserve_approved_music:true,
    preserve_approved_narration:true}};
const sorted=v=>Array.isArray(v)?v.map(sorted):v&&typeof v==='object'
  ?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])):v;
const receiptId='a8cf7bca-0241-45bd-9c4e-85394de6fab1';
const ticketId='T'.repeat(28),receiptFileId='R'.repeat(29);
const bearer='b'.repeat(64),ghpat='github_pat_'+ 'x'.repeat(60);
const folders={
  ticket:'1lHQS4Pfl3OhDoxeWEL768C-XkBIcCxjs',
  inbox:'1gYNUU3HUeWnu2jEcs1gEf4cu9LJEEPoD',
  applied:'1Ya87Y6FUUmstpSs8jG0mKvEVLRqTvwxH'
};
function mock(){
 const ticket={
   schema:'bontours.motionlab.drive-ticket/v1',
   state:'ISSUED',project_id:'test-project',session_id:'studio-qa',
   source_fingerprint:'a'.repeat(64),token_sha256:hash(bearer),
   expires_utc:new Date(Date.now()+3*3600000).toISOString()
 };
 const state={queueProps:new Map([['MOTIONLAB_GITHUB_ACTIONS_TOKEN',ghpat]]),
   files:new Map(),actions:[],triggers:[],finished:false,privateFileRead:0};
 const props={getProperty:k=>state.queueProps.get(k)||null,
   setProperty:(k,v)=>state.queueProps.set(k,v),
   deleteProperty:k=>state.queueProps.delete(k)};
 function file(parent,body,id,mime='text/plain'){
   return {
     getId(){return id},
     getParents(){let n=0;return {hasNext(){return n===0},next(){n++;return {getId(){return parent}}}}},
     getSharingAccess(){return 'PRIVATE'},
     getSize(){return JSON.stringify(body).length},
     getMimeType(){return mime},
     getBlob(){return {getDataAsString(){return JSON.stringify(body)}}},
     setContent(raw){Object.assign(body,JSON.parse(raw))}
   };
 }
 const ticketFile=file(folders.ticket,ticket,ticketId);
 const inbox={getFilesByName(n){const item=state.files.get(n);let done=false;return {
   hasNext(){return Boolean(item&&!done)},next(){done=true;return item}}},
   createFile(n,raw){const item=file(folders.inbox,JSON.parse(raw),receiptFileId);
     state.files.set(n,item);return item}};
 const applied={getFilesByName(n){const item=state.finished&&n===
    'motionlab-'+receiptId+'-render.json'?file(folders.applied,{
       schema:'bontours.motionlab.drive-render-receipt/v1',
       status:'RENDERED_PENDING_OWNER_REVIEW',
       published:false,receipt_id:receiptId,project_id:'test-project',
       selection_sha256:hash(JSON.stringify(sorted(select))),
       video_sha256:'f'.repeat(64)
     },'result_file_123456789'):null;
   let done=false;return {hasNext(){return Boolean(item&&!done)},
     next(){done=true;return item}}}};
 const sandbox={
  Date,JSON,Error,Object,String,Array,Number,Boolean,RegExp,
  MimeType:{PLAIN_TEXT:'text/plain'},
  PropertiesService:{getScriptProperties(){return props}},
  Utilities:{DigestAlgorithm:{SHA_256:'sha256'},Charset:{UTF_8:'UTF-8'},
    computeDigest(_alg,raw){return [...crypto.createHash('sha256').update(raw).digest()]
      .map(v=>v>=128?v-256:v)},
    getUuid(){return receiptId},
    newBlob(raw){return {getBytes(){return [...Buffer.from(raw)]}}}
  },
  DriveApp:{Access:{PRIVATE:'PRIVATE'},getFileById(id){
     if(id===ticketId)return ticketFile;
     if(id===receiptFileId){state.privateFileRead++;return [...state.files.values()][0]}
     throw Error('No such private Drive file');
   },getFolderById(id){if(id===folders.inbox)return inbox;
      if(id===folders.applied)return applied;throw Error('Unknown folder')}},
  LockService:{getScriptLock(){return {tryLock(){return true},releaseLock(){}}}},
  HtmlService:{XFrameOptionsMode:{ALLOWALL:'ALLOWALL'},
    createHtmlOutput(html){return{html,setXFrameOptionsMode(){return this}}}},
  ScriptApp:{
    getProjectTriggers(){return state.triggers},
    newTrigger(name){return {timeBased(){return this},everyMinutes(minutes){
       assert.equal(minutes,10);return this},create(){
       const t={getHandlerFunction(){return name}};
       state.triggers.push(t);return t
    }}},
    deleteTrigger(t){const i=state.triggers.indexOf(t);if(i>=0)state.triggers.splice(i,1)}
  },
  UrlFetchApp:{fetch(url,options){
    assert.equal(url,'https://api.github.com/repos/legur/Simba/actions/workflows/motionlab-drive-inbox.yml/dispatches');
    assert.equal(options.headers.Authorization,'Bearer '+ghpat);
    const payload=JSON.parse(options.payload);
    assert.deepEqual(payload,{ref:'main',
      inputs:{dry_run:'false',receipt_file_id:receiptFileId}});
    state.actions.push(payload);
    return {getResponseCode(){return 204}};
  }}
 };
 const ctx=vm.createContext(sandbox);
 vm.runInContext(source,ctx);
 const request={parameter:{
   nonce:'44444444-4444-4444-8444-444444444444',
   ticket_id:ticketId,ticket_token:bearer,
   selection_sha256:hash(JSON.stringify(sorted(select))),
   selection_json:JSON.stringify(sorted(select))
 }};
 return {state,ctx,ticket,request};
}
test('Exact validated private receipt immediately dispatches one GitHub workflow and sets ACTIVE',()=>{
 const e=mock(),result=vm.runInContext('doPost',e.ctx)(e.request);
 assert.match(result.html,/GITHUB_DISPATCHED/);
 assert.match(result.html,/SAVED_IN_DRIVE_PENDING_MONTAGE/);
 assert.equal(e.state.files.size,1);
 assert.equal(e.state.actions.length,1);
 assert.equal(e.state.triggers.length,1);
 const jobs=JSON.parse(e.state.queueProps.get('MOTIONLAB_QUEUE_ACTIVE_V1'));
 assert.equal(Object.keys(jobs).length,1);
 assert.equal(jobs[receiptId].attempts,1);
 assert.doesNotMatch(result.html,new RegExp(ghpat));
 assert.doesNotMatch(result.html,new RegExp(bearer));
});
test('No GitHub PAT: Drive still saves genuine receipt but does not claim job started',()=>{
 const e=mock();e.state.queueProps.delete('MOTIONLAB_GITHUB_ACTIONS_TOKEN');
 const result=vm.runInContext('doPost',e.ctx)(e.request);
 assert.match(result.html,/SETUP_REQUIRED/);
 assert.equal(e.state.files.size,1);
 assert.equal(e.state.actions.length,0);
 assert.equal(e.state.triggers.length,0);
});
test('Invalid ticket or render guard never starts the queue',()=>{
 const e=mock();
 const forged={parameter:{...e.request.parameter,ticket_token:'0'.repeat(64)}};
 assert.match(vm.runInContext('doPost',e.ctx)(forged).html,/TICKET_REJECTED/);
 assert.equal(e.state.files.size,0);
 assert.equal(e.state.actions.length,0);
 const chosen={...select,guards:{...select.guards,run_render:true}};
 const wrong={parameter:{...e.request.parameter,selection_json:JSON.stringify(chosen),
     selection_sha256:hash(JSON.stringify(sorted(chosen)))}};
 assert.match(vm.runInContext('doPost',e.ctx)(wrong).html,/PAID_OR_SOURCE_GUARD_VIOLATION/);
 assert.equal(e.state.files.size,0);
 assert.equal(e.state.actions.length,0);
});
test('10-min retry wakes only for ACTIVE, then clears the flag after private verified result',()=>{
 const e=mock(),post=vm.runInContext('doPost',e.ctx),tick=vm.runInContext('motionlabQueueTick',e.ctx);
 post(e.request);
 assert.equal(e.state.actions.length,1);
 tick();assert.equal(e.state.actions.length,1);
 const q=JSON.parse(e.state.queueProps.get('MOTIONLAB_QUEUE_ACTIVE_V1'));
 q[receiptId].last_dispatch_ms=Date.now()-11*60000;
 e.state.queueProps.set('MOTIONLAB_QUEUE_ACTIVE_V1',JSON.stringify(q));
 tick();assert.equal(e.state.actions.length,2);
 e.state.finished=true;
 tick();
 assert.equal(e.state.queueProps.has('MOTIONLAB_QUEUE_ACTIVE_V1'),false);
 assert.equal(e.state.triggers.length,0);
 tick();assert.equal(e.state.actions.length,2);
 const history=JSON.parse(e.state.queueProps.get('MOTIONLAB_QUEUE_LAST_RESULTS_V1'));
 assert.equal(history[receiptId].status,'RENDERED_PENDING_OWNER_REVIEW');
});
test('Duplicate Studio submission never re-dispatches or duplicates a receipt',()=>{
 const e=mock(),post=vm.runInContext('doPost',e.ctx);
 post(e.request);post(e.request);
 assert.equal(e.state.files.size,1);
 assert.equal(e.state.actions.length,1);
});
test('Bounded retry stops after 10 attempts; never loops forever',()=>{
 const e=mock(),post=vm.runInContext('doPost',e.ctx),tick=vm.runInContext('motionlabQueueTick',e.ctx);
 post(e.request);
 const q=JSON.parse(e.state.queueProps.get('MOTIONLAB_QUEUE_ACTIVE_V1'));
 q[receiptId].attempts=10;
 e.state.queueProps.set('MOTIONLAB_QUEUE_ACTIVE_V1',JSON.stringify(q));
 tick();
 assert.equal(e.state.triggers.length,0);
 assert.equal(e.state.queueProps.has('MOTIONLAB_QUEUE_ACTIVE_V1'),false);
 const history=JSON.parse(e.state.queueProps.get('MOTIONLAB_QUEUE_LAST_RESULTS_V1'));
 assert.equal(history[receiptId].status,'NEEDS_REVIEW_TIMEOUT');
});
