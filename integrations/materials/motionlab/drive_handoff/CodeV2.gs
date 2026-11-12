/**
 * Simba MotionLab v2 owner-only selection inbox, additive to Code.gs.
 * Deploy this AS A SECOND Apps Script file CodeV2.gs in the SAME project.
 *
 * This does not run v1 FFmpeg. It only stores an idempotent one-use, private
 * v2 receipt for independent Python source media replay + canonical CAS.
 * Existing v1 ticket and inbox functions retain their original behavior.
 */
'use strict';
const V2 = Object.freeze({
  sourceSchema:'bontours.motionlab.owner-launch/v2',
  ticketSchema:'bontours.motionlab.drive-ticket/v2',
  receiptSchema:'bontours.motionlab.drive-inbox/v2',
  materialsSchema:'bontours.motionlab.materials.launch/v2',
  proposalsSchema:'bontours.motionlab.proposals/v2',
  selectionSchema:'bontours.motionlab.selection/v2',
  replyType:'SIMBA_DRIVE_V2_RECEIPT',
  maxBytes:140000,
  maxScenes:12
});
function checkV2Ticket(id,token) {
  if(typeof id!=='string'||!/^[A-Za-z0-9_-]{15,100}$/.test(id)
      ||typeof token!=='string'||!/^[a-f0-9]{64}$/.test(token))
    fail('INVALID_V2_TICKET');
  let file;
  try{file=DriveApp.getFileById(id);}catch(_){fail('V2_TICKET_NOT_FOUND');}
  onlyFolder(file,ML.ticketFolder);
  let ticket;
  try{ticket=JSON.parse(file.getBlob().getDataAsString('UTF-8'));}
  catch(_){fail('INVALID_V2_TICKET_FILE');}
  if(ticket.schema!==V2.ticketSchema||ticket.state!=='ISSUED'
      ||!validIdentifier(ticket.project_id)||!validIdentifier(ticket.session_id)
      ||!/^[a-f0-9]{64}$/.test(ticket.source_fingerprint||'')
      ||!/^[a-f0-9]{64}$/.test(ticket.materials_sha256||'')
      ||!/^[a-f0-9]{64}$/.test(ticket.proposals_sha256||'')
      ||!/^[a-f0-9]{64}$/.test(ticket.source_launch_sha256||'')
      ||!ticket.source_launch_file_id
      ||ticket.token_sha256!==hexSha256(token))
    fail('V2_TICKET_REJECTED');
  const expiry=Date.parse(ticket.expires_utc);
  if(!Number.isFinite(expiry)||expiry<Date.now()-ML.skewMs
      ||expiry>Date.now()+24*3600*1000)fail('V2_TICKET_EXPIRED');
  return {file,ticket};
}
function v2Source(ticket) {
  const file=DriveApp.getFileById(ticket.source_launch_file_id);
  onlyFolder(file,ML.launchFolder);
  if(file.getSharingAccess()!==DriveApp.Access.PRIVATE||file.getSize()>300000)
    fail('V2_SOURCE_NOT_PRIVATE');
  const raw=file.getBlob().getDataAsString('UTF-8');
  if(hexSha256(raw)!==ticket.source_launch_sha256)
    fail('V2_SOURCE_CHANGED');
  let source;
  try{source=JSON.parse(raw);}catch(_){fail('V2_SOURCE_JSON_INVALID');}
  const materials=source.materials,proposals=source.proposals;
  const scenes=materials&&materials.scenes;
  const options=proposals&&proposals.proposals;
  if(source.schema!==V2.sourceSchema
    ||source.project_id!==ticket.project_id
    ||source.request_id!==ticket.session_id
    ||source.expected_input_fingerprint!==ticket.source_fingerprint
    ||materials?.schema!==V2.materialsSchema
    ||materials?.project_id!==ticket.project_id
    ||materials?.request_id!==ticket.session_id
    ||materials?.expected_input_fingerprint!==ticket.source_fingerprint
    ||materials?.stage!=='edit_choice'
    ||materials?.audio_alignment_status!=='AUDIO_ALIGNMENT_VERIFIED_AUTO'
    ||proposals?.schema!==V2.proposalsSchema
    ||proposals?.project_id!==ticket.project_id
    ||proposals?.request_id!==ticket.session_id
    ||proposals?.expected_input_fingerprint!==ticket.source_fingerprint
    ||proposals?.materials_sha256!==ticket.materials_sha256
    ||proposals?.renderer_revision_sha256!==materials?.renderer_capabilities?.revision_sha256
    ||proposals?.analysis?.status!=='REAL_VIDEO_AUTOMATICALLY_ANALYZED'
    ||proposals?.analysis?.analysis_method!=='full_timeline_sampled_pixels_ffmpeg_v1'
    ||hexSha256(canonical(materials))!==ticket.materials_sha256
    ||hexSha256(canonical(proposals))!==ticket.proposals_sha256
    ||!Array.isArray(scenes)||!scenes.length||scenes.length>V2.maxScenes
    ||!Array.isArray(options)||options.length!==3
    ||options.filter(o=>o&&o.recommended===true).length!==1)
    fail('V2_SOURCE_CONTRACT_MISMATCH');
  const ids=new Set(),signatures=new Set(),mediaHashes=new Set();
  for(const scene of scenes){
    if(!scene||!validIdentifier(scene.scene_id)||!validIdentifier(scene.asset_id)
       ||ids.has(scene.scene_id)
       ||!/^[a-f0-9]{64}$/.test(scene.media?.asset_sha256||'')
       ||scene.media?.kind!=='video'
       ||scene.locked?.read_only!==true)
      fail('V2_SOURCE_SCENE_INVALID');
    ids.add(scene.scene_id);mediaHashes.add(scene.asset_id);
  }
  const inspected=proposals.analysis?.inspected_assets;
  const evidence=proposals.analysis?.pixel_evidence;
  if(!Array.isArray(inspected)||inspected.length!==scenes.length
    ||!Array.isArray(evidence)||evidence.length!==scenes.length)
    fail('V2_SOURCE_VIDEO_EVIDENCE_INVALID');
  for(let i=0;i<scenes.length;i++){
    if(inspected[i]?.scene_id!==scenes[i].scene_id
       ||inspected[i]?.asset_sha256!==scenes[i].media.asset_sha256
       ||inspected[i]?.evidence_kind!=='full_original_mp4'
       ||evidence[i]?.scene_id!==scenes[i].scene_id
       ||evidence[i]?.asset_sha256!==scenes[i].media.asset_sha256
       ||!/^[a-f0-9]{64}$/.test(evidence[i]?.sampled_frame_sha256||''))
      fail('V2_SOURCE_VIDEO_EVIDENCE_INVALID');
  }
  for(let i=0;i<3;i++){
    const option=options[i];
    if(!option||option.option!==i+1
       ||!Array.isArray(option.scenes)
       ||option.scenes.length!==scenes.length
       ||signatures.has(canonical(option.scenes)))
      fail('V2_SOURCE_PROPOSALS_INVALID');
    signatures.add(canonical(option.scenes));
    verifyV2Scenes(option.scenes,materials);
  }
  // Preview assets are UNIQUE video files, not the number of scenes.
  // Reusing an original clip never sends it twice or requires new A2E.
  const previews=source.preview_assets||[];
  if(!Array.isArray(previews)||!previews.length||previews.length>scenes.length)
    fail('V2_PREVIEW_MANIFEST_INVALID');
  let total=0;const files=new Map();
  for(const a of previews){
    if(!a||!validIdentifier(a.asset_id)||files.has(a.asset_id)
      ||!/^[a-f0-9]{64}$/.test(a.sha256||'')
      ||!validIdentifier(a.file_id)||a.file_id.length<15
      ||a.mime_type!=='video/mp4'
      ||!Number.isInteger(a.size_bytes)||a.size_bytes<1024
      ||a.size_bytes>20*1024*1024)
      fail('V2_PREVIEW_MANIFEST_INVALID');
    files.set(a.asset_id,a);total+=a.size_bytes;
  }
  if(total>120*1024*1024||files.size!==mediaHashes.size)
    fail('V2_PREVIEW_MANIFEST_INVALID');
  for(const s of scenes){
    const a=files.get(s.asset_id);
    if(!a||a.sha256!==s.media.asset_sha256)
      fail('V2_PREVIEW_MANIFEST_INVALID');
  }
  return source;
}
function verifyV2Scenes(scenes,materials) {
  const originals=materials.scenes;
  const caps=materials.renderer_capabilities;
  if(!Array.isArray(scenes)||scenes.length!==originals.length
     ||!caps||typeof caps!=='object')fail('V2_SCENE_BINDING_MISMATCH');
  let globalStyle=null;
  for(let i=0;i<scenes.length;i++){
    const row=scenes[i],src=originals[i];
    if(!row||Object.keys(row).sort().join(',')!=='camera,scene_id,subtitle,title_fx,transition'
       ||row.scene_id!==src.scene_id)fail('V2_SCENE_BINDING_MISMATCH');
    const cam=row.camera,sub=row.subtitle,tran=row.transition;
    if(!cam||Object.keys(cam).sort().join(',')!=='id,intensity_percent'
       ||!caps.camera?.renderable?.includes(cam.id)
       ||typeof cam.intensity_percent!=='number'
       ||!Number.isFinite(cam.intensity_percent)
       ||cam.intensity_percent<0||cam.intensity_percent>100
       ||!caps.title_fx?.renderable?.includes(row.title_fx)
       ||(row.title_fx==='none'&&src.locked.title_text))
      fail('V2_UNSUPPORTED_EFFECT');
    if(i===0){if(tran!==null)fail('V2_UNSUPPORTED_TRANSITION');}
    else if(!tran||Object.keys(tran).sort().join(',')!=='duration_ms,id'
       ||!caps.transition?.renderable?.includes(tran.id)
       ||!Number.isInteger(tran.duration_ms)
       ||tran.duration_ms<400||tran.duration_ms>2400)
      fail('V2_UNSUPPORTED_TRANSITION');
    if(!sub||Object.keys(sub).sort().join(',')!=='style_id,word_motion_id'
       ||!caps.subtitle?.styles?.includes(sub.style_id)
       ||!caps.subtitle?.motions?.includes(sub.word_motion_id))
      fail('V2_UNSUPPORTED_SUBTITLE');
    const signature=sub.style_id+'|'+sub.word_motion_id;
    if(globalStyle!==null && globalStyle!==signature)
      fail('V2_SUBTITLE_MUST_BE_GLOBAL');
    globalStyle=signature;
  }
}
function verifyV2Selection(selection,source,ticket) {
  const materials=source.materials,proposals=source.proposals,decision=selection&&selection.decision;
  if(!selection||selection.schema!==V2.selectionSchema
     ||Object.keys(selection).sort().join(',')!==
       'decision,expected_input_fingerprint,format,guards,materials_sha256,next_stage,project_id,proposals_sha256,request_id,scenes,schema'
     ||selection.project_id!==ticket.project_id
     ||selection.request_id!==ticket.session_id
     ||selection.expected_input_fingerprint!==ticket.source_fingerprint
     ||selection.materials_sha256!==ticket.materials_sha256
     ||selection.proposals_sha256!==ticket.proposals_sha256
     ||selection.format!=='9:16'
     ||selection.next_stage!=='MONTAGE_PLANNING_REVIEW')
    fail('V2_SELECTION_SOURCE_MISMATCH');
  if(!decision||Object.keys(decision).sort().join(',')!==
      'explicit_approval,options_presented,selected_option,state,user_selected_at,visual_layout_edited'
     ||![1,2,3].includes(decision.selected_option)
     ||decision.options_presented!==3
     ||decision.state!=='USER_SELECTED_IN_CONNECTED_SESSION'
     ||decision.explicit_approval!==true
     ||decision.visual_layout_edited!==false
     ||!Number.isFinite(Date.parse(decision.user_selected_at))
     ||Date.parse(decision.user_selected_at)>Date.now()+300000
     ||Date.parse(decision.user_selected_at)<Date.now()-7*86400000)
    fail('V2_EXPLICIT_OWNER_APPROVAL_MISSING');
  const guards=selection.guards;
  if(!guards||Object.keys(guards).sort().join(',')!==
     'auto_publish,preserve_approved_music,preserve_approved_narration,preserve_approved_voice,run_a2e,run_paid_operations,run_render,run_tts'
     ||['auto_publish','run_a2e','run_paid_operations','run_render','run_tts'].some(k=>guards[k]!==false)
     ||['preserve_approved_music','preserve_approved_narration','preserve_approved_voice'].some(k=>guards[k]!==true))
    fail('V2_EXECUTION_GUARDS_INVALID');
  verifyV2Scenes(selection.scenes,materials);
  noSecrets(selection,0);
}
function readV2Project(params) {
  const {ticket}=checkV2Ticket(params.ticket_id,params.ticket_token);
  const source=v2Source(ticket);
  if(params.operation==='v2_load'){
    return {status:'V2_PROJECT_READY',
      project_id:ticket.project_id,
      materials:source.materials,
      proposals:source.proposals,
      assets:source.preview_assets.map(a=>({
        asset_id:a.asset_id,sha256:a.sha256,
        size_bytes:a.size_bytes,mime_type:a.mime_type
      }))};
  }
  if(params.operation!=='v2_asset')fail('V2_OPERATION_NOT_ALLOWED');
  const matches=source.preview_assets.filter(a=>a.asset_id===params.asset_id);
  if(matches.length!==1)fail('V2_ASSET_NOT_IN_PROJECT');
  const a=matches[0];
  const media=DriveApp.getFileById(a.file_id);
  onlyFolder(media,ML.mediaFolder);
  if(media.getSharingAccess()!==DriveApp.Access.PRIVATE
     ||media.getMimeType()!=='video/mp4'||media.getSize()!==a.size_bytes)
    fail('V2_ASSET_NOT_PRIVATE');
  const bytes=media.getBlob().getBytes();
  const sha=Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,bytes)
    .map(b=>('0'+(b<0?b+256:b).toString(16)).slice(-2)).join('');
  if(sha!==a.sha256)fail('V2_ASSET_BYTES_CHANGED');
  return {status:'V2_ASSET_READY',asset_id:a.asset_id,
          sha256:sha,size_bytes:bytes.length,
          mime_type:'video/mp4',base64:Utilities.base64Encode(bytes)};
}
function ingestV2(params) {
  const {file,ticket}=checkV2Ticket(params.ticket_id,params.ticket_token);
  if(typeof params.selection_json!=='string'
     ||params.selection_json.length>V2.maxBytes
     ||Utilities.newBlob(params.selection_json).getBytes().length>V2.maxBytes)
    fail('V2_SELECTION_TOO_LARGE');
  const source=v2Source(ticket);
  let selection;
  try{selection=JSON.parse(params.selection_json);}catch(_){fail('V2_SELECTION_JSON_INVALID');}
  verifyV2Selection(selection,source,ticket);
  const sha=hexSha256(canonical(selection));
  if(sha!==params.selection_sha256)fail('V2_SELECTION_HASH_MISMATCH');
  const folder=DriveApp.getFolderById(ML.inboxFolder);
  const name='motionlab-v2-'+params.ticket_id+'.json';
  const matches=folder.getFilesByName(name);
  if(matches.hasNext()){
    const previous=matches.next();
    if(matches.hasNext())fail('V2_DUPLICATE_RECEIPTS');
    onlyFolder(previous,ML.inboxFolder);
    const row=JSON.parse(previous.getBlob().getDataAsString('UTF-8'));
    if(row.schema!==V2.receiptSchema
       ||row.ticket_id!==params.ticket_id
       ||row.selection_sha256!==sha
       ||row.materials_sha256!==ticket.materials_sha256
       ||row.proposals_sha256!==ticket.proposals_sha256)
      fail('V2_TICKET_ALREADY_USED');
    return {status:'V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS',
            receipt_id:row.receipt_id,selection_sha256:sha};
  }
  if(ticket.consumed_receipt_id)fail('V2_TICKET_ALREADY_CONSUMED');
  const saved=new Date().toISOString();
  const receipt={
    schema:V2.receiptSchema,
    receipt_id:Utilities.getUuid(),ticket_id:params.ticket_id,
    project_id:ticket.project_id,session_id:ticket.session_id,
    source_fingerprint:ticket.source_fingerprint,
    materials_sha256:ticket.materials_sha256,
    proposals_sha256:ticket.proposals_sha256,
    source_launch_sha256:ticket.source_launch_sha256,
    selection_sha256:sha,selection,saved_utc:saved,
    status:'V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS',
    canonical_applied:false,render_authorized:false,
    paid_operations_authorized:false,published:false
  };
  folder.createFile(name,JSON.stringify(receipt),MimeType.PLAIN_TEXT);
  ticket.consumed_receipt_id=receipt.receipt_id;
  ticket.consumed_sha256=sha;
  ticket.consumed_utc=saved;
  file.setContent(JSON.stringify(ticket));
  // CRITICAL: unlike Code.gs v1, this function MUST NEVER call
  // motionlabRegisterQueue. Canonical v2 source replay/CAS comes first.
  return {status:receipt.status,receipt_id:receipt.receipt_id,
          selection_sha256:sha};
}
