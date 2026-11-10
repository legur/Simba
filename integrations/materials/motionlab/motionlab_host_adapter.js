/**
 * Drop-in browser-side caller adapter for Motion Lab Storyboard Studio.
 * This module only transfers a selection to an authenticated callback supplied
 * by the actual Simba host. It cannot save decisions in the engine by itself.
 */
export const MOTION_LAB_ORIGIN = 'https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com';
export const BRIDGE_PROTOCOL = 'bontours.motionlab.bridge/v1';

export function storyboardUrl() {
  const url = new URL(`${MOTION_LAB_ORIGIN}/storyboard.html`);
  url.searchParams.set('host_origin', window.location.origin);
  return url.href;
}

/**
 * @param {Object} options
 * @param {Window} options.targetWindow - iframe.contentWindow or opened popup
 * @param {Object} options.launch - source-verified launch object
 * @param {Function} options.acceptSelection - async: persist and validate, return {receipt_id}
 * @param {Function} [options.onStatus] - UI status callback
 * @returns {{start: Function, stop: Function}}
 */
export function connectStoryboard({ targetWindow, launch, acceptSelection, onStatus = () => {} }) {
  if (!targetWindow || typeof targetWindow.postMessage !== 'function') throw new Error('Target window required');
  if (!launch || launch.schema !== 'bontours.motionlab.storyboard.launch/v1') throw new Error('Verified launch required');
  if (typeof acceptSelection !== 'function') throw new Error('Authenticated selection receiver required');
  let closed = false;
  let processing = false;
  const notify = (type, extras = {}) => onStatus({ type, ...extras });
  const send = message => targetWindow.postMessage({ protocol: BRIDGE_PROTOCOL, ...message }, MOTION_LAB_ORIGIN);
  const start = () => {
    if (closed) return;
    send({ type: 'SIMBA_MOTIONLAB_START', payload: launch });
    notify('start_requested');
  };
  const stop = () => {
    closed = true;
    window.removeEventListener('message', onMessage);
  };
  async function onMessage(event) {
    if (closed || event.origin !== MOTION_LAB_ORIGIN || event.source !== targetWindow) return;
    const msg = event.data;
    if (!msg || msg.protocol !== BRIDGE_PROTOCOL) return;
    if (msg.type === 'SIMBA_MOTIONLAB_READY') { start(); return; }
    if (msg.type === 'SIMBA_MOTIONLAB_STARTED') { notify('editing', { request_id: msg.request_id }); return; }
    if (msg.type === 'SIMBA_MOTIONLAB_ERROR') { notify('error', { message: String(msg.message || '') }); return; }
    if (msg.type !== 'SIMBA_MOTIONLAB_SELECTION' || processing) return;
    const choice = msg.payload;
    const valid = choice && choice.schema === 'bontours.motionlab.storyboard.selection/v1' &&
      choice.request_id === launch.request_id && choice.project_id === launch.project_id &&
      choice.expected_input_fingerprint === launch.expected_input_fingerprint &&
      choice.decision?.state === 'USER_SELECTED_IN_CONNECTED_SESSION' &&
      choice.guards?.run_render === false && choice.guards?.auto_publish === false;
    if (!valid) { send({ type: 'SIMBA_MOTIONLAB_ACK', request_id: launch.request_id, accepted: false }); notify('invalid_selection'); return; }
    processing = true;
    try {
      // acceptSelection MUST perform authoritative validation and durable save.
      const accepted = await acceptSelection(choice);
      if (typeof accepted?.receipt_id !== 'string' || !accepted.receipt_id) throw new Error('Receiver did not provide a durable receipt');
      send({ type: 'SIMBA_MOTIONLAB_ACK', request_id: launch.request_id, accepted: true, receipt_id: accepted.receipt_id });
      notify('saved', { receipt_id: accepted.receipt_id });
    } catch (e) {
      send({ type: 'SIMBA_MOTIONLAB_ACK', request_id: launch.request_id, accepted: false });
      notify('save_failed', { message: String(e?.message || 'rejected') });
    } finally { processing = false; }
  }
  window.addEventListener('message', onMessage);
  return { start, stop };
}