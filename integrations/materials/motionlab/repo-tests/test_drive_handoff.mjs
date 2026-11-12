/* No network: actual Code.gs webhook contract against a fake private Drive. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import crypto from 'node:crypto';
import fs from 'node:fs';
import vm from 'node:vm';

const src=fs.readFileSync(new URL('../drive_handoff/Code.gs',import.meta.url),'utf8');
const client=fs.readFileSync(new URL('../motionlab_drive_bridge.js',import.meta.url),'utf8');
const ui=fs.readFileSync(new URL('../storyboard.js',import.meta.url),'utf8');
const html=fs.readFileSync(new URL('../storyboard.html',import.meta.url),'utf8');
const ticketId='1A'.repeat(20),token='b'.repeat(64);
const digest=value=>crypto.createHash('sha256').update(value).digest('hex');
const canonical=o=>JSON.stringify(sort(o));
const sort=o=>Array.isArray(o)?o.map(sort):o&&typeof o==='object'?
    Object.fromEntries(Object.keys(o).sort().map(k=>[k,sort(o[k])])):o;
const chosen={
 schema:'bontours.motionlab.storyboard.selection/v1',request_id:'studio-prague',
 project_id:'prague',expected_input_fingerprint:'a'.repeat(64),
 decision:{selected_option:2,options_presented:3,state:'DRAFT_NOT_DELIVERED',confirmation_scope:'EDIT_CHOICES_ONLY'},
 scenes:[{scene_id:'s1',order:1,name:'Prague',duration_seconds:3}],
 guards:{run_render:false,run_tts:false,run_a2e:false,run_paid_operations:false,auto_publish:false,
         preserve_approved_voice:true,preserve_approved_music:true,preserve_approved_narration:true}
};
function environment(){
 const ticket={schema:'bontours.motionlab.drive-ticket/v1',state:'ISSUED',
    project_id:'prague',session_id:'studio-prague',source_fingerprint:'a'.repeat(64),
    token_sha256:digest(token),
    expires_utc:new Date(Date.now()+45*60000).toISOString()};
 const files=new Map();
 const itemFile={
    getParents(){let count=0;return {hasNext(){return count===0},next(){count++;return {getId(){return '1lHQS4Pfl3OhDoxeWEL768C-XkBIcCxjs'}}}}},
    getBlob(){return {getDataAsString:()=>JSON.stringify(ticket)}},
    setContent(value){Object.assign(ticket,JSON.parse(value))}
 };
 const inbox={
    getFilesByName(name){
      const item=files.get(name);let gone=false;
      return {hasNext(){return Boolean(item&&!gone)},next(){gone=true;return {getBlob(){return {getDataAsString:()=>JSON.stringify(item)}}}}}
    },
    createFile(name,data){files.set(name,JSON.parse(data));return {}}
 };
 const sandbox={
   Date,JSON,Error,Object,String,Array,Number,Boolean,RegExp,MimeType:{PLAIN_TEXT:'text/plain'},
   Utilities:{
     DigestAlgorithm:{SHA_256:'sha256'},Charset:{UTF_8:'UTF-8'},
     computeDigest(_a,value){return Array.from(crypto.createHash('sha256').update(value).digest()).map(v=>v>=128?v-256:v)},
     newBlob(value){return {getBytes(){return Array.from(Buffer.from(value))}}},
     getUuid(){return '22222222-2222-4222-8222-222222222222'}
   },
   HtmlService:{
     XFrameOptionsMode:{ALLOWALL:'ALLOWALL'},
     createHtmlOutput(html){return {html,setXFrameOptionsMode(){return this}}}
   },
   LockService:{getScriptLock(){return {tryLock(){return true},releaseLock(){}}}},
   DriveApp:{
     getFileById(id){if(id!==ticketId)throw Error('not found');return itemFile},
     getFolderById(id){if(id!=='1gYNUU3HUeWnu2jEcs1gEf4cu9LJEEPoD')throw Error('folder mismatch');return inbox}
   }
 };
 const ctx=vm.createContext(sandbox);
 vm.runInContext(src,ctx);
 const request=(choice=chosen,t=token)=>({parameter:{
     nonce:'44444444-4444-4444-8444-444444444444',
     ticket_id:ticketId,ticket_token:t,selection_json:JSON.stringify(choice),
     selection_sha256:digest(canonical(choice))}});
 return {ctx,files,ticket,request};
}
test('No Wix login, bearer token in bundled JS, or public Drive writer scope',()=>{
 assert.doesNotMatch(html,/wixLogin|motionlab_wix_inbox\.js/);
 assert.doesNotMatch(client,/GDRIVE_OAUTH_REFRESH_TOKEN|GITHUB_TOKEN|WIX_API_KEY/);
 assert.match(client,/SAVED_IN_DRIVE_PENDING_MONTAGE/);
 assert.match(ui,/state\.request\.handoff/);
 assert.match(ui,/request:\{id:state\.request\.id,projectId:state\.request\.projectId/);
});
test('One-use ticket creates a private receipt and never authorizes render',()=>{
 const e=environment(),res=vm.runInContext('doPost',e.ctx)(e.request());
 assert.match(res.html,/SAVED_IN_DRIVE_PENDING_MONTAGE/);
 assert.equal(e.files.size,1);
 const item=[...e.files.values()][0];
 assert.equal(item.selection.decision.selected_option,2);
 assert.equal(item.render_authorized,false);
 assert.equal(item.paid_operations_authorized,false);
 assert.equal(item.ticket_id,ticketId);
 assert.equal(e.ticket.consumed_receipt_id,item.receipt_id);
 assert.doesNotMatch(res.html,new RegExp(token));
});
test('Retry with same selection is idempotent, different selection rejects',()=>{
 const e=environment(),post=vm.runInContext('doPost',e.ctx);
 const first=post(e.request());
 const second=post(e.request());
 assert.equal(e.files.size,1);
 assert.match(first.html,/SAVED_IN_DRIVE_PENDING_MONTAGE/);
 assert.match(second.html,/SAVED_IN_DRIVE_PENDING_MONTAGE/);
 const other=JSON.parse(JSON.stringify(chosen));
 other.decision.selected_option=3;
 const rejected=post(e.request(other));
 assert.match(rejected.html,/TICKET_ALREADY_USED_FOR_DIFFERENT_SELECTION/);
 assert.equal(e.files.size,1);
});
test('Forged ticket and paid actions fail closed',()=>{
 const e=environment(),post=vm.runInContext('doPost',e.ctx);
 assert.match(post(e.request(chosen,'0'.repeat(64))).html,/TICKET_REJECTED/);
 const other=JSON.parse(JSON.stringify(chosen));other.guards.run_render=true;
 assert.match(post(e.request(other)).html,/PAID_OR_SOURCE_GUARD_VIOLATION/);
 assert.equal(e.files.size,0);
});
test('Expiration or stale fingerprint rejected with no data written',()=>{
 const e=environment(),post=vm.runInContext('doPost',e.ctx);
 e.ticket.expires_utc=new Date(Date.now()-4*60000).toISOString();
 assert.match(post(e.request()).html,/TICKET_EXPIRED/);
 assert.equal(e.files.size,0);
 e.ticket.expires_utc=new Date(Date.now()+4*60000).toISOString();
 const other=JSON.parse(JSON.stringify(chosen));
 other.expected_input_fingerprint='f'.repeat(64);
 assert.match(post(e.request(other)).html,/SOURCE_FINGERPRINT_MISMATCH/);
 assert.equal(e.files.size,0);
});

test('HtmlService reply reaches the Wix ancestor across nested Google frames',()=>{
 const e=environment();
 const response=vm.runInContext('doPost',e.ctx)(e.request());
 const scriptText=response.html.match(/<script>([\\s\\S]*?)<\\/script>/)?.[1];
 assert.ok(scriptText,'Apps Script must return executable receipt script');
 const deliveries=[];
 const wix={postMessage(data,origin){deliveries.push({data,origin})}};
 wix.parent=wix;
 const googleOuter={parent:wix,postMessage(){}};
 const googleSandbox={parent:googleOuter,postMessage(){}};
 const htmlServiceUser={parent:googleSandbox};
 vm.runInNewContext(scriptText,{window:htmlServiceUser});
 assert.equal(deliveries.length,1);
 assert.equal(deliveries[0].origin,
   'https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com');
 assert.equal(deliveries[0].data.status,'SAVED_IN_DRIVE_PENDING_MONTAGE');
 assert.equal(deliveries[0].data.selection_sha256,digest(canonical(chosen)));
 assert.equal(deliveries[0].data.nonce,'44444444-4444-4444-8444-444444444444');
 assert.doesNotMatch(JSON.stringify(deliveries),new RegExp(token));
});
test('MotionLab permits nested Google messages but verifies origin nonce and hash',()=>{
 assert.doesNotMatch(client,/e\\.source!==frame\\.contentWindow/);
 assert.match(client,/!allowedReply\\(e\\.origin\\)/);
 assert.match(client,/e\\.data\\?\\.nonce!==nonce/);
 assert.match(client,/data\\.selection_sha256!==hash/);
});
