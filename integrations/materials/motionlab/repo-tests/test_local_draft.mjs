/* MotionLab local-only safety net. Real Wix/GitHub deliveries must never be
 * asserted by a browser-local draft. Offline, no network, no tokens. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync(new URL('../storyboard.js',import.meta.url),'utf8');
const page=fs.readFileSync(new URL('../storyboard.html',import.meta.url),'utf8');
const visual=fs.readFileSync(new URL('../visual_editor.js',import.meta.url),'utf8');
const start=source.indexOf('const LOCAL_DRAFT_KEY=');
const end=source.indexOf('function wire(){',start);
assert(start>0&&end>start,'Local draft functions must exist');
const snippet=source.slice(start,end);
const KEY='simba:motionlab:local-approved-draft:v1';
const request={id:'studio-001',projectId:'bavaria',fingerprint:'f'.repeat(64),stage:'edit_choice'};
function fixture(){
 const records=new Map(),messages=[];
 const state={request,project:{id:'bavaria'},scenes:[{id:'scene1',name:'Bavaria',duration:3}],
  concepts:[{id:1},{id:2},{id:3}],selectedOption:2,selectedIndex:0,
  confirmed:true,confirmedAt:'2026-11-11T18:00:00.000Z',bridge:null,deliveryStatus:null};
 const localStorage={getItem:k=>records.get(k)||null,setItem:(k,v)=>records.set(k,String(v)),removeItem:k=>records.delete(k)};
 const context=vm.createContext({state,localStorage,Date,JSON,
    globalThis:{MotionLabVideoImport:{info:()=>null},MotionLabVisual:{exportLocalDraft:()=>({schema:'test-safe',render_authorized:false}),importLocalDraft(){}}},
    buildResult:()=>({schema:'bontours.motionlab.storyboard.selection/v1',
                     guards:{run_render:false,run_paid_operations:false}}),
    setConnection:()=>{},render:()=>{},say:m=>messages.push(m)});
 vm.runInContext(snippet,context);
 return {context,records,state,messages};
}
test('No Wix login buttons or old OAuth frontend dependencies remain',()=>{
 assert.doesNotMatch(page,/id="wixLogin"|id="checkWixStatus"|motionlab_wix_inbox\.js/);
 assert.doesNotMatch(source,/MotionLabInbox|startLogin|completeLogin/);
 assert.match(page,/Сохранить черновик на устройстве/);
});
test('Local save is correctly NOT delivered to Wix/GitHub/Montage',()=>{
 const {context,records,state}=fixture();
 assert.equal(vm.runInContext('saveLocalDraft()',context),true);
 const item=JSON.parse(records.get(KEY));
 assert.equal(item.delivery_status,'LOCAL_ONLY');
 assert.equal(item.render_authorized,false);
 assert.equal(item.confirmedAt,'2026-11-11T18:00:00.000Z');
 assert.equal(state.deliveryStatus.status,'LOCAL_ONLY');
 assert.equal(Object.hasOwn(item,'githubReceipt'),false);
 assert.equal(Object.hasOwn(item,'wixReceipt'),false);
});
test('Reload restores editable scenes but demands fresh approval',()=>{
 const {context,records,state}=fixture();
 vm.runInContext('saveLocalDraft()',context);
 state.request=null;state.project=null;state.scenes=[];state.confirmed=true;
 vm.runInContext('restoreLocalDraft()',context);
 assert.equal(state.request.id,'studio-001');
 assert.equal(state.scenes[0].name,'Bavaria');
 assert.equal(state.confirmed,false);
 assert.equal(state.deliveryStatus.status,'LOCAL_ONLY');
});
test('Corrupt or production-authorized browser cache is rejected',()=>{
 const {context,records,state}=fixture();
 vm.runInContext('saveLocalDraft()',context);
 const row=JSON.parse(records.get(KEY));
 row.render_authorized=true;
 records.set(KEY,JSON.stringify(row));
 vm.runInContext('restoreLocalDraft()',context);
 assert.equal(records.has(KEY),false);
});
test('Private MP4 cannot be represented as persisted editable source',()=>{
 const {context,state}=fixture();
 context.globalThis.MotionLabVideoImport.info=()=>({name:'local.mp4'});
 assert.equal(vm.runInContext('saveLocalDraft()',context),false);
});
test('Visual theme and per-scene positions support local export/import',()=>{
 assert.match(visual,/function exportLocalDraft\(/);
 assert.match(visual,/function importLocalDraft\(/);
 assert.match(visual,/SCENE_IDS_CHANGED/);
 assert.match(visual,/render_authorized:false/);
});
