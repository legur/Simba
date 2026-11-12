/**
 * Simba MotionLab - one-use, no-login Drive ingress.
 * Deploy as Google Apps Script WEB APP:
 *   Execute as: Me (owner of private MotionLab_Handoff folders).
 *   Who has access: Anyone.
 *
 * "Anyone" does NOT grant access to Drive: every request must present an
 * unpredictable, short-lived, one-use ticket from a PRIVATE Drive file that
 * was issued server-side by the existing GitHub Actions Drive OAuth.
 * No Github/Google/Wix secrets appear in frontend, form payload or logs.
 *
 * This code is intentionally self-contained and requires one-time Apps Script
 * owner authorization/deployment. It MUST NOT be copied into a Wix static page.
 */
'use strict';
const ML = Object.freeze({
  origin: 'https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com',
  ticketFolder: '1lHQS4Pfl3OhDoxeWEL768C-XkBIcCxjs',
  inboxFolder: '1gYNUU3HUeWnu2jEcs1gEf4cu9LJEEPoD',
  launchFolder: '10IdAl9pS-YSqLEYFbfTIKNEoho7bWGWA',
  mediaFolder: '1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj',
  renderFolder: '1GMoSVogs0SKuTAXCdMVcG-U7bTn-IuCt',
  appliedFolder: '1Ya87Y6FUUmstpSs8jG0mKvEVLRqTvwxH',
  maxBytes: 140000,
  maxScenes: 24,
  skewMs: 60 * 1000
});
function hexSha256(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text,
      Utilities.Charset.UTF_8)
      .map(b => ('0' + (b < 0 ? b + 256 : b).toString(16)).slice(-2)).join('');
}
function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value !== null && typeof value === 'object') {
    return '{' + Object.keys(value).sort().map(
      k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
  }
  return JSON.stringify(value);
}
function fail(code) { throw Error(code); }
function validIdentifier(value) {
  return typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value);
}
function noSecrets(value, depth) {
  if (depth > 12) fail('SELECTION_TOO_DEEP');
  if (Array.isArray(value)) return value.forEach(v => noSecrets(v, depth + 1));
  if (value !== null && typeof value === 'object') {
    Object.keys(value).forEach(k => {
      if (/^(token|secret|password|api[-_]?key|authorization|cookie|bearer|credential|private[-_]?url|download[-_]?url|dataurl|base64)$/i.test(k))
        fail('FORBIDDEN_FIELD');
      noSecrets(value[k], depth + 1);
    });
  } else if (typeof value === 'string' && value.length > 12000) {
    fail('SELECTION_STRING_TOO_LONG');
  }
}
function verifySelection(selection, ticket) {
  if (!selection || typeof selection !== 'object' || Array.isArray(selection))
    fail('INVALID_SELECTION');
  // The active Drive ingress and FFmpeg worker implement ONLY storyboard
  // selection/v1. A v2 creative decision requires a separate, source-pinned
  // materials+proposals+audio-alignment+CAS protocol; never treat v2 as v1
  // and accidentally dispatch a render. Enable v2 only after its own QA.
  if (selection.schema === 'bontours.motionlab.selection/v2')
    fail('V2_ROUTE_NOT_ACTIVATED');
  if (selection.schema !== 'bontours.motionlab.storyboard.selection/v1')
    fail('UNSUPPORTED_SCHEMA');
  if (selection.request_id !== ticket.session_id
      || selection.project_id !== ticket.project_id
      || selection.expected_input_fingerprint !== ticket.source_fingerprint)
    fail('SOURCE_FINGERPRINT_MISMATCH');
  const decision = selection.decision || {};
  if (![1,2,3].includes(decision.selected_option) || decision.options_presented !== 3
      || !['DRAFT_NOT_DELIVERED','USER_SELECTED_IN_CONNECTED_SESSION'].includes(decision.state)
      || decision.confirmation_scope !== 'EDIT_CHOICES_ONLY')
    fail('USER_SELECTION_NOT_APPROVED_FOR_INBOX');
  if (!Array.isArray(selection.scenes) || !selection.scenes.length
      || selection.scenes.length > ML.maxScenes)
    fail('INVALID_SCENE_COUNT');
  const guards = selection.guards || {};
  if (['run_render','run_tts','run_a2e','run_paid_operations','auto_publish']
      .some(k => guards[k] !== false)
      || ['preserve_approved_voice','preserve_approved_music',
          'preserve_approved_narration'].some(k => guards[k] !== true))
    fail('PAID_OR_SOURCE_GUARD_VIOLATION');
  noSecrets(selection, 0);
}
function onlyFolder(file, expectedId) {
  const parents = file.getParents();
  if (!parents.hasNext() || parents.next().getId() !== expectedId || parents.hasNext())
    fail('FILE_OUTSIDE_PRIVATE_FOLDER');
}
function checkTicket(id, token, readRenderOnly) {
  if (typeof id !== 'string' || !/^[A-Za-z0-9_-]{15,100}$/.test(id)
      || typeof token !== 'string' || !/^[0-9a-f]{64}$/.test(token))
    fail('INVALID_TICKET');
  let file;
  try { file = DriveApp.getFileById(id); } catch (_) { fail('TICKET_NOT_FOUND'); }
  onlyFolder(file, ML.ticketFolder);
  let data;
  try { data = JSON.parse(file.getBlob().getDataAsString('UTF-8')); }
  catch (_) { fail('INVALID_TICKET_FILE'); }
  if (data.schema !== 'bontours.motionlab.drive-ticket/v1'
      || !validIdentifier(data.project_id) || !validIdentifier(data.session_id)
      || typeof data.source_fingerprint !== 'string'
      || !/^[a-f0-9]{64}$/.test(data.source_fingerprint)
      || typeof data.token_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(data.token_sha256)
      || data.token_sha256 !== hexSha256(token)
      || data.state !== 'ISSUED')
    fail('TICKET_REJECTED');
  const expires = Date.parse(data.expires_utc);
  // Render-result status is read-only and may arrive after a two-hour
  // scheduled job. The extra 24h access applies ONLY to an already consumed
  // ticket; it never extends authority to write or read original MP4s.
  const grace=readRenderOnly===true && data.consumed_receipt_id
      ? 24*3600*1000 : ML.skewMs;
  if (!Number.isFinite(expires) || expires < Date.now() - grace
      || expires > Date.now() + 24 * 3600 * 1000)
    fail('TICKET_EXPIRED');
  return {file, data};
}
function ingest(params) {
  const token = params.ticket_token;
  const tid = params.ticket_id;
  const {file, data:ticket} = checkTicket(tid, token);
  const raw = params.selection_json;
  if (typeof raw !== 'string' || raw.length > ML.maxBytes
      || Utilities.newBlob(raw).getBytes().length > ML.maxBytes)
    fail('SELECTION_TOO_LARGE');
  let selection;
  try { selection = JSON.parse(raw); } catch (_) { fail('INVALID_SELECTION_JSON'); }
  verifySelection(selection, ticket);
  const hash = hexSha256(canonical(selection));
  if (hash !== params.selection_sha256) fail('SELECTION_HASH_MISMATCH');
  const folder = DriveApp.getFolderById(ML.inboxFolder);
  const filename = 'motionlab-' + tid + '.json';
  // Under the script lock, a repeated valid request returns the existing
  // receipt and NEVER spawns a new job, even if the previous request timed out.
  const iter = folder.getFilesByName(filename);
  if (iter.hasNext()) {
    const already = iter.next();
    if (iter.hasNext()) fail('DUPLICATE_RECEIPTS');
    const record = JSON.parse(already.getBlob().getDataAsString('UTF-8'));
    if (record.selection_sha256 !== hash || record.ticket_id !== tid)
      fail('TICKET_ALREADY_USED_FOR_DIFFERENT_SELECTION');
    return {status:'SAVED_IN_DRIVE_PENDING_MONTAGE',
            receipt_id:record.receipt_id, selection_sha256:hash,
            private_receipt_file_id:already.getId()};
  }
  if (ticket.consumed_receipt_id) fail('TICKET_ALREADY_CONSUMED');
  const receiptId = Utilities.getUuid();
  const item = {
    schema:'bontours.motionlab.drive-inbox/v1',
    receipt_id:receiptId, ticket_id:tid, selection_sha256:hash,
    project_id:ticket.project_id, session_id:ticket.session_id,
    source_fingerprint:ticket.source_fingerprint,
    saved_utc:new Date().toISOString(), status:'SAVED_IN_DRIVE_PENDING_MONTAGE',
    render_authorized:false, paid_operations_authorized:false,
    selection
  };
  const created = folder.createFile(filename, JSON.stringify(item), MimeType.PLAIN_TEXT);
  // On a crash between the Drive write and ticket update, retry can recover
  // from the already-created immutable receipt. Avoid removing that receipt.
  ticket.consumed_receipt_id = receiptId;
  ticket.consumed_sha256 = hash;
  ticket.consumed_utc = item.saved_utc;
  file.setContent(JSON.stringify(ticket));
  return {status:'SAVED_IN_DRIVE_PENDING_MONTAGE',
          receipt_id:receiptId, selection_sha256:hash,
          private_receipt_file_id:created.getId()};
}
function output(message) {
  // The Google-hosted HTML reply communicates only with the *exact* Wix origin.
  // Receipts contain no bearer secrets. Project replies return only the
  // ticket-authorized launch/MP4 bytes to the exact editor origin.
  const serialized = JSON.stringify(message).replace(/</g,'\\u003c');
  // HtmlService wraps user HTML in multiple Google-owned nested iframes.
  // window.parent is usually another Google iframe, NOT our Wix editor.
  // Walk the ancestor chain and post using the exact Wix origin: only the
  // Wix document receives the message, never the intervening Google frames.
  const html = '<!doctype html><meta charset="utf-8"><script>'
    + '(function(){var msg=' + serialized + ';var origin='
    + JSON.stringify(ML.origin) + ';'
    + 'var target=window;for(var i=0;i<8;i++){'
    + 'var next;try{next=target.parent;}catch(e){break;}'
    + 'if(!next||next===target)break;'
    + 'try{next.postMessage(msg,origin);}catch(e){}'
    + 'target=next;}'
    + '})();</script>';
  return HtmlService.createHtmlOutput(html)
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
// Read only the exact pinned launch and its explicitly listed A2E originals.
// No caller-supplied Drive file ID or public sharing is accepted.
function readProject(params) {
  const ticket=checkTicket(params.ticket_id,params.ticket_token,params.operation==='render_status').data;
  if(ticket.project_read_enabled!==true || !/^[a-f0-9]{64}$/.test(ticket.source_launch_sha256||''))
    fail('PROJECT_READ_NOT_AUTHORIZED');
  const source=DriveApp.getFileById(ticket.source_launch_file_id);
  onlyFolder(source,ML.launchFolder);
  if(source.getSharingAccess()!==DriveApp.Access.PRIVATE || source.getSize()>300000)
    fail('PROJECT_SOURCE_NOT_PRIVATE');
  const raw=source.getBlob().getDataAsString('UTF-8');
  if(hexSha256(raw)!==ticket.source_launch_sha256)fail('PROJECT_SOURCE_CHANGED');
  const launch=JSON.parse(raw);
  if(launch.schema!=='bontours.motionlab.storyboard.launch/v1'
    ||launch.project_id!==ticket.project_id||launch.request_id!==ticket.session_id
    ||launch.expected_input_fingerprint!==ticket.source_fingerprint
    ||!Array.isArray(launch.options)||launch.options.length!==3
    ||!Array.isArray(launch.scenes)||!launch.scenes.length||launch.scenes.length>24
    ||!Array.isArray(launch.preview_assets)||!launch.preview_assets.length||launch.preview_assets.length>24)
    fail('PROJECT_SOURCE_MISMATCH');
  const assets=launch.preview_assets;
  if(params.operation==='render_status')return readRenderStatus(params,ticket);
  if(params.operation==='load_project') {
    delete launch.preview_assets;
    return {status:'PROJECT_READY',launch,
      assets:assets.map(a=>({asset_id:a.asset_id,sha256:a.sha256,size_bytes:a.size_bytes,mime_type:a.mime_type}))};
  }
  const matches=assets.filter(a=>a.asset_id===params.asset_id);
  if(matches.length!==1)fail('ASSET_NOT_IN_PROJECT');
  const a=matches[0];
  if(a.mime_type!=='video/mp4'||!Number.isInteger(a.size_bytes)||a.size_bytes<1024||a.size_bytes>20*1024*1024
    ||!/^[a-f0-9]{64}$/.test(a.sha256||''))fail('INVALID_PREVIEW_ASSET');
  const media=DriveApp.getFileById(a.file_id);onlyFolder(media,ML.mediaFolder);
  if(media.getSharingAccess()!==DriveApp.Access.PRIVATE||media.getSize()!==a.size_bytes||media.getMimeType()!=='video/mp4')
    fail('ASSET_METADATA_MISMATCH');
  const bytes=media.getBlob().getBytes();
  const sha=Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,bytes)
    .map(b=>('0'+(b<0?b+256:b).toString(16)).slice(-2)).join('');
  if(sha!==a.sha256)fail('ASSET_HASH_MISMATCH');
  return {status:'ASSET_READY',asset_id:a.asset_id,sha256:sha,size_bytes:bytes.length,
    mime_type:'video/mp4',base64:Utilities.base64Encode(bytes)};
}

// Owner-only read of the technical Montage output after a consumed selection.
// Reuses the existing project ticket; does not issue Drive permissions, share,
// trigger rendering or accept arbitrary caller-provided file IDs.
function readRenderStatus(params, ticket) {
  const folder=DriveApp.getFolderById(ML.inboxFolder);
  const records=folder.getFilesByName('motionlab-'+params.ticket_id+'.json');
  if(!records.hasNext())return {status:'RENDER_PENDING',project_id:ticket.project_id,stage:'AWAITING_STUDIO_SELECTION'};
  const selected=records.next();
  if(records.hasNext())fail('DUPLICATE_SELECTION_RECEIPTS');
  onlyFolder(selected,ML.inboxFolder);
  if(selected.getSharingAccess()!==DriveApp.Access.PRIVATE || selected.getSize()>ML.maxBytes)
    fail('UNTRUSTED_SELECTION_RECEIPT');
  const item=JSON.parse(selected.getBlob().getDataAsString('UTF-8'));
  if(item.schema!=='bontours.motionlab.drive-inbox/v1'
    ||item.ticket_id!==params.ticket_id
    ||item.project_id!==ticket.project_id
    ||item.session_id!==ticket.session_id
    ||item.source_fingerprint!==ticket.source_fingerprint
    ||item.receipt_id!==ticket.consumed_receipt_id
    ||item.selection_sha256!==ticket.consumed_sha256)
    fail('INVALID_CONSUMED_RECEIPT');
  const applied=DriveApp.getFolderById(ML.appliedFolder);
  const outputs=applied.getFilesByName('motionlab-'+item.receipt_id+'-render.json');
  if(!outputs.hasNext())return {status:'RENDER_PENDING',project_id:ticket.project_id,stage:'SAVED_IN_DRIVE_PENDING_MONTAGE'};
  const receiptFile=outputs.next();
  if(outputs.hasNext())fail('DUPLICATE_RENDER_RECEIPTS');
  onlyFolder(receiptFile,ML.appliedFolder);
  if(receiptFile.getSharingAccess()!==DriveApp.Access.PRIVATE || receiptFile.getSize()>20000)
    fail('UNTRUSTED_RENDER_RECEIPT');
  const result=JSON.parse(receiptFile.getBlob().getDataAsString('UTF-8'));
  const idPattern=/^[A-Za-z0-9_-]{15,100}$/;
  if(result.schema!=='bontours.motionlab.drive-render-receipt/v1'
    ||result.status!=='RENDERED_PENDING_OWNER_REVIEW'
    ||result.published!==false
    ||result.receipt_id!==item.receipt_id
    ||result.project_id!==item.project_id
    ||result.selection_sha256!==item.selection_sha256
    ||!/^[a-f0-9]{64}$/.test(result.video_sha256||'')
    ||!idPattern.test(result.video_file_id||'')
    ||!idPattern.test(result.qa_file_id||''))
    fail('RENDER_RECEIPT_MISMATCH');
  const video=DriveApp.getFileById(result.video_file_id);
  onlyFolder(video,ML.renderFolder);
  if(video.getSharingAccess()!==DriveApp.Access.PRIVATE
     ||video.getMimeType()!=='video/mp4'
     ||video.getSize()<100000 || video.getSize()>180*1024*1024)
    fail('RENDER_VIDEO_NOT_PRIVATE');
  const report=DriveApp.getFileById(result.qa_file_id);
  onlyFolder(report,ML.renderFolder);
  if(report.getSharingAccess()!==DriveApp.Access.PRIVATE||report.getSize()>30000)
    fail('RENDER_QA_NOT_PRIVATE');
  const qa=JSON.parse(report.getBlob().getDataAsString('UTF-8'));
  if(qa.schema!=='bontours.motionlab.drive-automated-render/v1'
    ||qa.receipt_id!==item.receipt_id
    ||qa.selection_sha256!==item.selection_sha256
    ||qa.sha256!==result.video_sha256
    ||qa.drive_video_file_id!==result.video_file_id
    ||qa.technical_decode!=='PASS'||qa.published!==false)
    fail('RENDER_QA_MISMATCH');
  // A private file link does not grant read access; Google remains owner-only.
  return {status:'RENDER_READY',
    project_id:ticket.project_id,
    receipt_id:item.receipt_id,
    sha256:result.video_sha256,
    qa_status:qa.qa,
    duration_seconds:qa.duration_seconds,
    published:false,
    video_url:'https://drive.google.com/file/d/'+result.video_file_id+'/view',
    qa_url:'https://drive.google.com/file/d/'+result.qa_file_id+'/view'};
}

function doPost(e) {
  const p = e && e.parameter || {};
  const nonce = typeof p.nonce === 'string' && /^[0-9a-f-]{36}$/.test(p.nonce)
        ? p.nonce : '';
  let lock;
  try {
    if(['load_project','load_asset','render_status'].includes(p.operation)) {
      if(!nonce)fail('INVALID_NONCE');
      return output({type:'SIMBA_DRIVE_PROJECT_REPLY',nonce,...readProject(p)});
    }
    lock = LockService.getScriptLock();
    if (!lock.tryLock(9000)) fail('RECEIVER_BUSY_RETRY');
    const result = ingest(p);
    // The private receipt is durable before any optional GitHub dispatch.
    // Queue failure never rewrites a genuine saved-in-Drive ACK to REJECTED.
    let automation='SETUP_REQUIRED';
    try {
      automation=motionlabRegisterQueue({
        receipt_id:result.receipt_id,
        receipt_file_id:result.private_receipt_file_id,
        selection_sha256:result.selection_sha256
      });
    } catch (_) {
      automation='SETUP_REQUIRED';
    }
    delete result.private_receipt_file_id;
    return output({type:'SIMBA_DRIVE_INGRESS_RECEIPT', nonce,
      ...result, automation_status:automation});
  } catch (err) {
    // Return only a bounded allowlisted error code. Never log ticket/selection.
    const code = String(err && err.message || 'INGRESS_FAILED');
    return output({type:['load_project','load_asset','render_status'].includes(p.operation)?'SIMBA_DRIVE_PROJECT_REPLY':'SIMBA_DRIVE_INGRESS_RECEIPT', nonce,
      status:'REJECTED', error_code:/^[A-Z_]{4,64}$/.test(code)?code:'INGRESS_FAILED'});
  } finally {
    if (lock) { try { lock.releaseLock(); } catch (_) {} }
  }
}
function doGet() {
  return HtmlService.createHtmlOutput('Simba MotionLab secure Drive ingress. POST only.');
}


/**
 * On-demand Montage queue. Runs ONLY after an already-validated private
 * Apps Script receipt. No background GitHub cron when the queue is empty.
 *
 * Owner setup (NEVER put token into Wix/GitHub source):
 * Apps Script Project Settings > Script properties:
 * MOTIONLAB_GITHUB_ACTIONS_TOKEN = fine-grained PAT for ONLY legur/Simba,
 * Actions:write, issued by the repo owner.
 *
 * The owner must authorize ScriptApp triggers and UrlFetchApp once.
 * One active ClockTrigger (every 10 minutes) is created on demand and
 * deleted when all jobs are done or bounded retries have failed.
 */
const ML_QUEUE=Object.freeze({
  activeProperty:'MOTIONLAB_QUEUE_ACTIVE_V1',
  historyProperty:'MOTIONLAB_QUEUE_LAST_RESULTS_V1',
  githubTokenProperty:'MOTIONLAB_GITHUB_ACTIONS_TOKEN',
  githubWorkflowUrl:'https://api.github.com/repos/legur/Simba/actions/workflows/motionlab-drive-inbox.yml/dispatches',
  triggerFunction:'motionlabQueueTick',
  intervalMs:10*60*1000,
  maxAgeMs:2*60*60*1000,
  maxAttempts:10,
  maxJobs:12
});
function motionlabReadQueue() {
  const saved=PropertiesService.getScriptProperties().getProperty(ML_QUEUE.activeProperty);
  if(!saved)return {};
  let jobs;
  try{jobs=JSON.parse(saved);}catch(_){fail('QUEUE_STATE_CORRUPT');}
  if(!jobs||Array.isArray(jobs)||typeof jobs!=='object'
    ||Object.keys(jobs).length>ML_QUEUE.maxJobs)fail('QUEUE_STATE_INVALID');
  return jobs;
}
function motionlabWriteQueue(jobs) {
  if(Object.keys(jobs).length>ML_QUEUE.maxJobs)fail('QUEUE_TOO_MANY_JOBS');
  const p=PropertiesService.getScriptProperties();
  if(Object.keys(jobs).length)p.setProperty(ML_QUEUE.activeProperty,JSON.stringify(jobs));
  else p.deleteProperty(ML_QUEUE.activeProperty);
}
function motionlabRecordTerminal(job,status) {
  const p=PropertiesService.getScriptProperties();
  let history={};
  try{history=JSON.parse(p.getProperty(ML_QUEUE.historyProperty)||'{}');}
  catch(_){history={};}
  history[job.receipt_id]={status,at_utc:new Date().toISOString(),
    project_id:job.project_id};
  const ids=Object.keys(history);
  if(ids.length>15)ids.slice(0,ids.length-15).forEach(id=>delete history[id]);
  p.setProperty(ML_QUEUE.historyProperty,JSON.stringify(history));
}
function motionlabGithubToken() {
  const value=PropertiesService.getScriptProperties().getProperty(ML_QUEUE.githubTokenProperty);
  return typeof value==='string'&&value.length>24?value:null;
}
function motionlabQueueTriggers() {
  return ScriptApp.getProjectTriggers().filter(t=>
    t.getHandlerFunction()===ML_QUEUE.triggerFunction);
}
function motionlabEnsureTrigger() {
  if(!motionlabQueueTriggers().length)
    ScriptApp.newTrigger(ML_QUEUE.triggerFunction).timeBased().everyMinutes(10).create();
}
function motionlabStopTrigger() {
  motionlabQueueTriggers().forEach(t=>ScriptApp.deleteTrigger(t));
}
// Verify only an immutable owner-private result record for exactly this
// receipt/selection; do not mark a job complete after a bare HTTP 200.
function motionlabRenderComplete(job) {
  const results=DriveApp.getFolderById(ML.appliedFolder)
    .getFilesByName('motionlab-'+job.receipt_id+'-render.json');
  if(!results.hasNext())return false;
  const file=results.next();
  if(results.hasNext())fail('DUPLICATE_RENDER_RESULTS');
  onlyFolder(file,ML.appliedFolder);
  if(file.getSharingAccess()!==DriveApp.Access.PRIVATE || file.getSize()>20000)
    fail('UNTRUSTED_RENDER_RESULT');
  const data=JSON.parse(file.getBlob().getDataAsString('UTF-8'));
  if(data.schema!=='bontours.motionlab.drive-render-receipt/v1'
    ||data.status!=='RENDERED_PENDING_OWNER_REVIEW'
    ||data.published!==false ||data.receipt_id!==job.receipt_id
    ||data.selection_sha256!==job.selection_sha256
    ||data.project_id!==job.project_id
    ||!/^[0-9a-f]{64}$/.test(data.video_sha256||''))
    fail('RENDER_RESULT_MISMATCH');
  return true;
}
function motionlabDispatchGithub(job) {
  const token=motionlabGithubToken();
  if(!token)return 'SETUP_REQUIRED';
  if(!/^[A-Za-z0-9_-]{15,100}$/.test(job.receipt_file_id||''))
    fail('INVALID_PRIVATE_RECEIPT_ID');
  let status=0;
  try{
    const response=UrlFetchApp.fetch(ML_QUEUE.githubWorkflowUrl,{
      method:'post',contentType:'application/json',
      payload:JSON.stringify({ref:'main',inputs:{
        dry_run:'false',receipt_file_id:job.receipt_file_id}}),
      headers:{
        'Authorization':'Bearer '+token,
        'Accept':'application/vnd.github+json',
        'X-GitHub-Api-Version':'2022-11-28',
        'User-Agent':'Simba-MotionLab-Owner-Queue'
      },
      muteHttpExceptions:true,
      followRedirects:false
    });
    status=response.getResponseCode();
  }catch(_){return 'GITHUB_UNREACHABLE';}
  return status===204||status===200?'GITHUB_DISPATCHED':'GITHUB_REJECTED';
}
function motionlabRegisterQueue(value) {
  if(!value||!/^[0-9a-f-]{36}$/.test(value.receipt_id||'')
    ||!/^[0-9a-f]{64}$/.test(value.selection_sha256||'')
    ||!/^[A-Za-z0-9_-]{15,100}$/.test(value.receipt_file_id||''))
    fail('INVALID_QUEUE_RECEIPT');
  const file=DriveApp.getFileById(value.receipt_file_id);
  onlyFolder(file,ML.inboxFolder);
  if(file.getSharingAccess()!==DriveApp.Access.PRIVATE
    ||file.getSize()>ML.maxBytes)fail('UNTRUSTED_QUEUE_RECEIPT');
  const receipt=JSON.parse(file.getBlob().getDataAsString('UTF-8'));
  if(receipt.schema!=='bontours.motionlab.drive-inbox/v1'
    ||receipt.status!=='SAVED_IN_DRIVE_PENDING_MONTAGE'
    ||receipt.receipt_id!==value.receipt_id
    ||receipt.selection_sha256!==value.selection_sha256
    ||receipt.render_authorized!==false
    ||receipt.paid_operations_authorized!==false)
    fail('QUEUE_SOURCE_MISMATCH');
  const jobs=motionlabReadQueue();
  if(jobs[value.receipt_id])return jobs[value.receipt_id].status||'QUEUE_ACTIVE';
  const job={
    receipt_id:value.receipt_id,
    receipt_file_id:value.receipt_file_id,
    selection_sha256:value.selection_sha256,
    project_id:receipt.project_id,
    created_ms:Date.now(),last_dispatch_ms:0,
    attempts:0,status:'QUEUE_ACTIVE'
  };
  if(motionlabRenderComplete(job))return 'ALREADY_RENDERED';
  jobs[job.receipt_id]=job;
  motionlabWriteQueue(jobs);
  if(!motionlabGithubToken())return 'SETUP_REQUIRED';
  try{motionlabEnsureTrigger();}catch(_){return 'TRIGGER_PERMISSION_REQUIRED';}
  // Dispatch immediately, not after the first 10-minute clock trigger.
  const status=motionlabDispatchGithub(job);
  job.attempts=1;job.last_dispatch_ms=Date.now();job.status=status;
  motionlabWriteQueue(jobs);
  return status;
}
function motionlabProcessQueue() {
  const jobs=motionlabReadQueue(),now=Date.now();
  if(!Object.keys(jobs).length){
    motionlabStopTrigger();return {remaining:0,processed:0};
  }
  let processed=0;
  for(const [id,job] of Object.entries(jobs)){
    try{
      if(motionlabRenderComplete(job)){
        motionlabRecordTerminal(job,'RENDERED_PENDING_OWNER_REVIEW');
        delete jobs[id];processed++;continue;
      }
    }catch(_){
      motionlabRecordTerminal(job,'NEEDS_REVIEW_INVALID_RESULT');
      delete jobs[id];processed++;continue;
    }
    if(now-job.created_ms>=ML_QUEUE.maxAgeMs||job.attempts>=ML_QUEUE.maxAttempts){
      motionlabRecordTerminal(job,'NEEDS_REVIEW_TIMEOUT');
      delete jobs[id];processed++;continue;
    }
    if(now-job.last_dispatch_ms<ML_QUEUE.intervalMs)continue;
    if(!motionlabGithubToken()){
      job.status='SETUP_REQUIRED';
      continue;
    }
    const result=motionlabDispatchGithub(job);
    job.last_dispatch_ms=now;job.attempts++;
    job.status=result;
  }
  motionlabWriteQueue(jobs);
  if(!Object.keys(jobs).length)motionlabStopTrigger();
  return {remaining:Object.keys(jobs).length,processed};
}
function motionlabQueueTick() {
  // One lock shared with doPost to prevent duplicate queue edits.
  const lock=LockService.getScriptLock();
  if(!lock.tryLock(5000))return;
  try{return motionlabProcessQueue();}
  finally{lock.releaseLock();}
}
// Run once from Apps Script editor AFTER the owner has saved the repository-
// restricted Actions:write fine-grained token as a Script property.
function motionlabActivateQueue() {
  if(!motionlabGithubToken())return 'SETUP_REQUIRED';
  const lock=LockService.getScriptLock();
  if(!lock.tryLock(5000))return 'QUEUE_BUSY';
  try{
    if(!Object.keys(motionlabReadQueue()).length){
      motionlabStopTrigger();
      return 'QUEUE_EMPTY_READY';
    }
    motionlabEnsureTrigger();
    return motionlabProcessQueue();
  }finally{lock.releaseLock();}
}
