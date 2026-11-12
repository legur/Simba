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
  if (!['bontours.motionlab.storyboard.selection/v1',
        'bontours.motionlab.selection/v2'].includes(selection.schema))
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
function checkTicket(id, token) {
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
  if (!Number.isFinite(expires) || expires < Date.now() - ML.skewMs
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
            receipt_id:record.receipt_id, selection_sha256:hash};
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
          receipt_id:receiptId, selection_sha256:hash};
}
function output(message) {
  // The Google-hosted HTML reply communicates only with the *exact* Wix origin.
  // No access tokens, user identity, source media or JSON selections are echoed.
  const serialized = JSON.stringify(message).replace(/</g,'\\u003c');
  const html = '<!doctype html><meta charset="utf-8"><script>'
    + 'window.parent.postMessage(' + serialized + ','
    + JSON.stringify(ML.origin) + ');</script>';
  return HtmlService.createHtmlOutput(html)
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
function doPost(e) {
  const p = e && e.parameter || {};
  const nonce = typeof p.nonce === 'string' && /^[0-9a-f-]{36}$/.test(p.nonce)
        ? p.nonce : '';
  let lock;
  try {
    lock = LockService.getScriptLock();
    if (!lock.tryLock(9000)) fail('RECEIVER_BUSY_RETRY');
    const result = ingest(p);
    return output({type:'SIMBA_DRIVE_INGRESS_RECEIPT', nonce, ...result});
  } catch (err) {
    // Return only a bounded allowlisted error code. Never log ticket/selection.
    const code = String(err && err.message || 'INGRESS_FAILED');
    return output({type:'SIMBA_DRIVE_INGRESS_RECEIPT', nonce,
      status:'REJECTED', error_code:/^[A-Z_]{4,64}$/.test(code)?code:'INGRESS_FAILED'});
  } finally {
    if (lock) { try { lock.releaseLock(); } catch (_) {} }
  }
}
function doGet() {
  return HtmlService.createHtmlOutput('Simba MotionLab secure Drive ingress. POST only.');
}
