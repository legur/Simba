import test from 'node:test';
import assert from 'node:assert/strict';
import {connectV2LiveMotionLab, BRIDGE_V2} from '../motionlab_v2_live_host.js';
import {MOTION_LAB_ORIGIN} from '../motionlab_host_adapter.js';

const session = {
  session_id:'f'.repeat(32),
  capability:'a'.repeat(48),
  expires_at_epoch:Math.ceil(Date.now()/1000)+1000,
  launch:{
    schema:'bontours.motionlab.materials.launch/v2',
    project_id:'example-project',
    request_id:'studio-'+'f'.repeat(32),
    expected_input_fingerprint:'b'.repeat(64),
  },
  proposals:{
    schema:'bontours.motionlab.proposals/v2',
    project_id:'example-project',
    request_id:'studio-'+'f'.repeat(32),
    materials_sha256:'c'.repeat(64),
  },
  proposals_sha256:'d'.repeat(64),
};
const selection={
  schema:'bontours.motionlab.selection/v2',
  project_id:session.launch.project_id,
  request_id:session.launch.request_id,
  expected_input_fingerprint:session.launch.expected_input_fingerprint,
  materials_sha256:session.proposals.materials_sha256,
  proposals_sha256:session.proposals_sha256,
  decision:{
    state:'USER_SELECTED_IN_CONNECTED_SESSION',
    explicit_approval:true,
    visual_layout_edited:true,
  },
  scene_layout:[{
    scene_id:'clip-01',asset_id:'f2u-approved',
    layout:{title:{x:55,y:42,scale:110},subtitle:{x:45,y:80,scale:90}},
  }],
  guards:{
    run_render:false,run_tts:false,run_a2e:false,
    run_paid_operations:false,auto_publish:false,
  },
};

function harness(fetchImpl) {
  globalThis.window={location:{origin:'https://studio-owner.example'}};
  const listeners=new Map(),sent=[],events=[];
  const parent={
    addEventListener(name,fn){listeners.set(name,fn);},
    removeEventListener(name){listeners.delete(name);},
  };
  const iframe={
    postMessage(data,origin){sent.push({data,origin});},
  };
  const bridge=connectV2LiveMotionLab({
    targetWindow:iframe,session,
    hostWindow:parent,fetchImpl,
    onStatus:row=>events.push(row),
  });
  const msg=(type,sel=selection,origin=MOTION_LAB_ORIGIN,source=iframe,protocol=BRIDGE_V2)=>{
    listeners.get('message')?.({
      origin,source,data:{
        protocol,type,
        request_id:session.launch.request_id,
        project_id:session.launch.project_id,
        payload:{selection:sel},
      },
    });
  };
  return {msg,iframe,sent,events,bridge};
}
const done=()=>new Promise(resolve=>setImmediate(resolve));

test('v1 UI READY cannot fool the v2 connected bridge into START or ACK',async()=>{
  const h=harness(async()=>{throw Error('should not fetch')});
  h.bridge.start();
  h.msg('SIMBA_MOTIONLAB_READY');
  h.msg('SIMBA_MOTIONLAB_V2_READY',selection,
    'https://foreign.example');
  h.msg('SIMBA_MOTIONLAB_V2_READY',selection,MOTION_LAB_ORIGIN,{});
  assert.equal(h.sent.length,0);
  assert.ok(h.events.some(e=>e.type==='awaiting_v2_motionlab_ui'));
  h.bridge.stop();
});

test('v2 READY sends exact source-pinned materials + Motion Lab authored proposals only to trusted origin',()=>{
  const h=harness(async()=>{throw Error('no selection yet')});
  h.msg('SIMBA_MOTIONLAB_V2_READY');
  const sent=h.sent.at(-1);
  assert.equal(sent.data.type,'SIMBA_MOTIONLAB_V2_START');
  assert.equal(sent.origin,MOTION_LAB_ORIGIN);
  assert.deepEqual(sent.data.payload.materials,session.launch);
  assert.deepEqual(sent.data.payload.proposals,session.proposals);
  h.bridge.stop();
});

test('v2 connected explicit approval -> durable receiver ACK, not fake APPLIED',async()=>{
  const calls=[];
  const h=harness(async(url,opts)=>{
    calls.push({url,opts});
    return {ok:true,json:async()=>({
      persisted:true,receipt_id:'motionlab:v2:'+'e'.repeat(64),stage_status:'QUEUED',
    })};
  });
  h.msg('SIMBA_MOTIONLAB_V2_READY');
  h.msg('SIMBA_MOTIONLAB_V2_SELECTION');
  await done();
  assert.equal(calls.length,1);
  assert.equal(calls[0].url,'/api/motionlab/v2/selection');
  assert.equal(calls[0].opts.headers['X-Simba-Capability'],session.capability);
  assert.deepEqual(JSON.parse(calls[0].opts.body).selection.scene_layout,
                   selection.scene_layout);
  const ack=h.sent.find(x=>x.data.type==='SIMBA_MOTIONLAB_V2_ACK');
  assert.equal(ack.data.payload.accepted,true);
  assert.equal(ack.data.payload.state,'SELECTION_DURABLY_QUEUED_NOT_APPLIED');
  assert.equal(ack.origin,MOTION_LAB_ORIGIN);
  assert.ok(!h.sent.some(x=>x.data.type==='SIMBA_MOTIONLAB_ACK'));
  h.bridge.stop();
});

test('unapproved or layout-losing choice yields a negative ACK with NO request',async()=>{
  const calls=[];
  const h=harness(async()=>{calls.push(1);return {ok:true}});
  h.msg('SIMBA_MOTIONLAB_V2_SELECTION',{
    ...selection,decision:{...selection.decision,explicit_approval:false},
  });
  await done();
  assert.equal(calls.length,0);
  assert.equal(h.sent.at(-1).data.payload.accepted,false);
  h.msg('SIMBA_MOTIONLAB_V2_SELECTION',{
    ...selection,scene_layout:undefined,
  });
  await done();
  assert.equal(calls.length,0);
  assert.equal(h.sent.at(-1).data.payload.accepted,false);
  h.bridge.stop();
});

test('server failure or missing persisted=true NEVER produces accepted ACK',async()=>{
  const h=harness(async()=>({ok:true,json:async()=>({
    persisted:false,receipt_id:'not-actually-saved',
  })}));
  h.msg('SIMBA_MOTIONLAB_V2_SELECTION');
  await done();
  assert.equal(h.sent.at(-1).data.payload.accepted,false);
  h.bridge.stop();
});

test('browser shows status only when server confirms canonical project commit',async()=>{
  const h=harness(async()=>({ok:true,json:async()=>({
    status:'QUEUED',project_applied:false,receipt_id:'queued',
  })}));
  const s=await h.bridge.status();
  assert.equal(s.project_applied,false);
  assert.ok(!h.events.some(x=>x.type==='montage_handoff_applied'));
  h.bridge.stop();
});
