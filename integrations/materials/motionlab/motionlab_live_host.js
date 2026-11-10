/**
 * Owner-side host adapter for EXISTING Motion Lab PR #112 postMessage bridge.
 * The host backend provisions an ephemeral session after owner authentication.
 * Never send GitHub/Drive credentials or the long-lived owner key to browser.
 */
import { connectStoryboard, storyboardUrl } from './motionlab_host_adapter.js';

function checkSession(session) {
  if (!session || typeof session !== 'object' ||
      !/^[a-f0-9]{32}$/.test(session.session_id) ||
      typeof session.capability !== 'string' || session.capability.length < 32 ||
      session.launch?.schema !== 'bontours.motionlab.storyboard.launch/v1' ||
      !session.launch?.project_id || !session.launch?.request_id)
    throw new Error('Owner-provisioned Motion Lab session required');
  if (!Number.isFinite(session.expires_at_epoch) ||
      session.expires_at_epoch * 1000 <= Date.now())
    throw new Error('Motion Lab session expired');
}

/**
 * Called by an authenticated same-origin host with server-issued session.
 * The ACK means durable SQLite selection receipt, NOT finished video/render.
 */
export function connectLiveMotionLab({ targetWindow, session, onStatus = () => {}, fetchImpl = fetch }) {
  checkSession(session);
  const notify = (type, detail = {}) => onStatus({ type, ...detail });
  let stopped = false;
  const headers = {
    'Content-Type': 'application/json',
    'X-Simba-Capability': session.capability,
  };
  const connector = connectStoryboard({
    targetWindow, launch: session.launch, onStatus: notify,
    acceptSelection: async choice => {
      const response = await fetchImpl('/api/motionlab/selection', {
        method: 'POST', cache: 'no-store', credentials: 'same-origin', headers,
        body: JSON.stringify({ session_id: session.session_id, selection: choice }),
      });
      if (!response.ok) throw new Error('Сохранение выбора не подтверждено сервером');
      const data = await response.json();
      if (data.persisted !== true || typeof data.receipt_id !== 'string' || !data.receipt_id)
        throw new Error('Сервер не подтвердил долговечную запись');
      return { receipt_id: data.receipt_id };
    },
  });
  async function status() {
    if (stopped) throw new Error('Motion Lab connection is closed');
    const response = await fetchImpl('/api/motionlab/status/' + session.session_id, {
      cache: 'no-store', credentials: 'same-origin',
      headers: { 'X-Simba-Capability': session.capability },
    });
    if (!response.ok) throw new Error('Не удалось проверить передачу монтажеру');
    const data = await response.json();
    if (data.project_applied === true)
      notify('montage_handoff_applied', { receipt_id: data.receipt_id });
    else if (data.status === 'BLOCKED')
      notify('montage_handoff_blocked');
    else notify('montage_handoff_pending', { state: data.status });
    return data;
  }
  return {
    motionLabUrl: storyboardUrl(),
    start: connector.start,
    stop() { stopped = true; connector.stop(); },
    status,
  };
}
