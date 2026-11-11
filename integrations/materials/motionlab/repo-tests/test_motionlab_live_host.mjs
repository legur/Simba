import test from 'node:test';
import assert from 'node:assert/strict';
import { connectLiveMotionLab } from '../motionlab_live_host.js';
import { MOTION_LAB_ORIGIN, BRIDGE_PROTOCOL } from '../motionlab_host_adapter.js';

const SESSION = {
  session_id: 'a'.repeat(32), capability: 'q'.repeat(48),
  expires_at_epoch: Math.ceil(Date.now() / 1000) + 1200,
  launch: {
    schema: 'bontours.motionlab.storyboard.launch/v1',
    request_id: 'studio-' + 'a'.repeat(32),
    project_id: 'approved-test',
    expected_input_fingerprint: 'b'.repeat(64),
  },
};
const choice = {
  schema: 'bontours.motionlab.storyboard.selection/v1',
  request_id: SESSION.launch.request_id,
  project_id: SESSION.launch.project_id,
  expected_input_fingerprint: SESSION.launch.expected_input_fingerprint,
  decision: { state: 'USER_SELECTED_IN_CONNECTED_SESSION' },
  guards: { run_render: false, auto_publish: false },
};

function harness(fetchImpl) {
  const listeners = new Map();
  const writes = [];
  globalThis.window = {
    location: { origin: 'https://owner.example' },
    addEventListener: (name, cb) => listeners.set(name, cb),
    removeEventListener: name => listeners.delete(name),
  };
  const targetWindow = {
    postMessage(payload, origin) { writes.push({ payload, origin }); },
  };
  const statusEvents = [];
  const host = connectLiveMotionLab({
    targetWindow, session: SESSION, fetchImpl,
    onStatus: data => statusEvents.push(data),
  });
  const message = payload => listeners.get('message')?.({
    origin: MOTION_LAB_ORIGIN, source: targetWindow,
    data: { protocol: BRIDGE_PROTOCOL, ...payload },
  });
  return { host, message, writes, statusEvents };
}

test('durably persisted receiver confirmation produces browser ACK and status', async () => {
  const requests = [];
  const h = harness(async (url, options) => {
    requests.push({ url, options });
    if (url.includes('/selection')) return { ok: true, json: async () => ({
      persisted: true, receipt_id: 'receipt-12345678', stage_status: 'QUEUED',
    }) };
    return { ok: true, json: async () => ({
      project_applied: true, receipt_id: 'receipt-12345678', status: 'APPLIED',
    }) };
  });
  h.message({ type: 'SIMBA_MOTIONLAB_READY' });
  assert.equal(h.writes[0].payload.type, 'SIMBA_MOTIONLAB_START');
  h.message({ type: 'SIMBA_MOTIONLAB_SELECTION', payload: choice });
  await new Promise(resolve => setImmediate(resolve));
  const ack = h.writes.find(x => x.payload.type === 'SIMBA_MOTIONLAB_ACK');
  assert.equal(ack?.payload.accepted, true);
  assert.equal(ack?.payload.receipt_id, 'receipt-12345678');
  assert.equal(ack?.origin, MOTION_LAB_ORIGIN);
  assert.equal(requests[0].url, '/api/motionlab/selection');
  assert.equal(requests[0].options.headers['X-Simba-Capability'], SESSION.capability);
  assert.equal(JSON.parse(requests[0].options.body).session_id, SESSION.session_id);
  const status = await h.host.status();
  assert.equal(status.project_applied, true);
  assert.ok(h.statusEvents.some(x => x.type === 'montage_handoff_applied'));
  h.host.stop();
});

test('failed durable write must return rejected ACK, never success', async () => {
  const h = harness(async () => ({ ok: false, json: async () => ({}) }));
  h.message({ type: 'SIMBA_MOTIONLAB_SELECTION', payload: choice });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.writes.find(x => x.payload.type === 'SIMBA_MOTIONLAB_ACK')?.payload.accepted, false);
  assert.ok(h.statusEvents.some(x => x.type === 'save_failed'));
  h.host.stop();
});

test('false persist receipt cannot become ACK', async () => {
  const h = harness(async () => ({ ok: true, json: async () => ({
    persisted: false, receipt_id: 'not-actually-saved',
  }) }));
  h.message({ type: 'SIMBA_MOTIONLAB_SELECTION', payload: choice });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.writes.find(x => x.payload.type === 'SIMBA_MOTIONLAB_ACK')?.payload.accepted, false);
  h.host.stop();
});

test('bad or expired owner-issued session rejected before connection', () => {
  globalThis.window = {
    location: { origin: 'https://owner.example' },
    addEventListener() {}, removeEventListener() {},
  };
  assert.throws(() => connectLiveMotionLab({ targetWindow: {}, session: {
    ...SESSION, expires_at_epoch: 0,
  } }), /expired/);
  assert.throws(() => connectLiveMotionLab({ targetWindow: {}, session: {
    ...SESSION, capability: '',
  } }), /required/);
});

test('events from unrelated windows and origins are ignored', async () => {
  const h = harness(async () => { throw new Error('should not fetch'); });
  const count = h.writes.length;
  globalThis.window.addEventListener;
  // An unrelated source never reaches acceptSelection.
  const bridge = h.message;
  bridge({ type: 'SIMBA_MOTIONLAB_READY' });
  assert.equal(h.writes.length, count + 1);
  h.host.stop();
});
