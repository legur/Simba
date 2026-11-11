/* Zero-network contract tests for frontend member-auth Wix selection receipt. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';

const frontend = fs.readFileSync(new URL('../motionlab_wix_inbox.js', import.meta.url), 'utf8');
const tokenKey = 'simba:motionlab:wix-member-access:v1';
const selected = {
  schema: 'bontours.motionlab.storyboard.selection/v1',
  request_id: 'prague-session-1',
  project_id: 'prague',
  expected_input_fingerprint: 'a'.repeat(64),
  decision: {selected_option: 2, options_presented: 3, state: 'DRAFT_NOT_DELIVERED'},
  guards: {run_render: false, run_tts: false, run_a2e: false,
    run_paid_operations: false, auto_publish: false,
    preserve_approved_voice: true, preserve_approved_music: true,
    preserve_approved_narration: true},
  scenes: [{scene_id: '1', duration_seconds: 3, subtitles: {preview_text: 'Прага'}}]
};
function storage() {
  const values = new Map();
  return {
    getItem: k => values.has(k) ? values.get(k) : null,
    setItem: (k, v) => values.set(k, String(v)),
    removeItem: k => values.delete(k)
  };
}
function rig({loggedIn = true, insertFails = false} = {}) {
  const sessionStorage = storage(), localStorage = storage(), calls = [];
  if (loggedIn) sessionStorage.setItem(tokenKey, JSON.stringify({
    access_token: 'WIX_FAKE_MEMBER_ACCESS_ONLY', expires_at: Date.now() + 900000
  }));
  let pending = null;
  const fetch = async (url, opts = {}) => {
    calls.push({url, opts});
    if (url.endsWith('/wix-data/v2/items') && opts.method === 'POST') {
      pending = JSON.parse(opts.body);
      if (insertFails) return {ok: false, status: 409, json: async () => ({})};
      return {ok: true, status: 200,
        json: async () => ({dataItem: {id: pending.dataItem.id}})};
    }
    if (url.includes('/wix-data/v2/items/') && opts.headers?.Authorization) {
      return {ok: true, status: 200, json: async () => ({
        dataItem: {id: pending?.dataItem?.id, data: {
          state: 'PENDING', selectionSha256: pending.dataItem.data.selectionSha256,
          sourceFingerprint: pending.dataItem.data.sourceFingerprint
        }}
      })};
    }
    throw Error('Unexpected network request: ' + url);
  };
  const window = {};
  const context = vm.createContext({window, crypto: crypto.webcrypto,
    sessionStorage, localStorage, TextEncoder, btoa, fetch,
    location: {origin: 'https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com',
               pathname: '/storyboard.html', hash: '', search: ''},
    history: {replaceState() {}},
    URLSearchParams, Date, console
  });
  vm.runInContext(frontend, context);
  return {api: window.MotionLabInbox, calls, localStorage, sessionStorage, getPending: () => pending};
}
const clean = val => JSON.parse(JSON.stringify(val));
test('Never embeds GitHub Secrets or admin Wix key in browser bundle', () => {
  assert.doesNotMatch(frontend, /ghp_[A-Za-z0-9]+|github_pat_|WIX_API_KEY|GITHUB_TOKEN/);
  assert.match(frontend, /clientId: CLIENT_ID/);
});
test('No member login refuses submit before doing any network I/O', async () => {
  const a = rig({loggedIn: false});
  await assert.rejects(a.api.submit(clean(selected)), /войти в Wix/);
  assert.equal(a.calls.length, 0);
});
test('Member submit create-only receipt, preserves selection, and never triggers rendering', async () => {
  const a = rig();
  const result = await a.api.submit(clean(selected));
  assert.match(result.deliveryId, /^[0-9a-f-]{36}$/);
  assert.equal(result.state, 'PENDING');
  assert.equal(a.calls.length, 1);
  const payload = a.getPending();
  assert.equal(payload.dataCollectionId, 'SimbaMotionLabInboxV1');
  assert.equal(payload.dataItem.id, result.deliveryId);
  assert.equal(payload.dataItem.data.projectId, 'prague');
  assert.equal(payload.dataItem.data.selection.decision.selected_option, 2);
  const source = payload.dataItem.data.selection;
  const canonical = v => JSON.stringify(Object.fromEntries(Object.entries(v).sort()));
  function sort(obj) {if(Array.isArray(obj))return obj.map(sort);if(obj&&typeof obj==='object')return Object.fromEntries(Object.entries(obj).sort().map(([k,v])=>[k,sort(v)]));return obj;}
  const digest = crypto.createHash('sha256').update(JSON.stringify(sort(source))).digest('hex');
  assert.equal(payload.dataItem.data.selectionSha256, digest);
  assert.equal(payload.dataItem.data.selection.guards.run_render, false);
  assert.equal(a.api.receipt().deliveryId, result.deliveryId);
  const status = await a.api.getStatus(result.deliveryId);
  assert.equal(status.state, 'PENDING');
  assert.equal(a.calls.length, 2);
});
test('Lost create response with an existing matching receipt is idempotently recovered', async () => {
  const a = rig({insertFails: true});
  const result = await a.api.submit(clean(selected));
  assert.equal(result.state, 'PENDING');
  assert.equal(a.calls.length, 2);
  assert.equal(a.calls[0].opts.method, 'POST');
  assert.equal(a.calls[1].opts.headers.Authorization, 'WIX_FAKE_MEMBER_ACCESS_ONLY');
});
test('Refuse unsourced or altered request fingerprints', async () => {
  const a = rig();
  const x = clean(selected);
  x.expected_input_fingerprint = 'wrong';
  await assert.rejects(a.api.submit(x), /исходной версией/);
  assert.equal(a.calls.length, 0);
});
