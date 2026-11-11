/**
 * Trust boundary: owner HTTPS Studio host ↔ future connected Motion Lab v2 UI.
 *
 * NOT an alternative Motion Lab editor. The existing Wix PR118 v1 storyboard
 * does not yet emit this v2 bridge contract. We must NOT send a fabricated ACK
 * or translate its DRAFT_NOT_DELIVERED visual export into user approval.
 */
import { MOTION_LAB_ORIGIN, storyboardUrl } from './motionlab_host_adapter.js';

export const BRIDGE_V2 = 'bontours.motionlab.bridge/v2';
const MATERIALS_V2 = 'bontours.motionlab.materials.launch/v2';
const PROPOSALS_V2 = 'bontours.motionlab.proposals/v2';
const SELECTION_V2 = 'bontours.motionlab.selection/v2';

function valid(session) {
  if (!session || !/^[a-f0-9]{32}$/.test(session.session_id ?? '') ||
      !/^[A-Za-z0-9_-]{32,128}$/.test(session.capability ?? '') ||
      session.launch?.schema !== MATERIALS_V2 ||
      session.proposals?.schema !== PROPOSALS_V2 ||
      session.launch.request_id !== session.proposals.request_id ||
      session.launch.project_id !== session.proposals.project_id ||
      !Number.isFinite(session.expires_at_epoch) ||
      Date.now() >= session.expires_at_epoch * 1000) {
    throw new Error('Authenticated fully prepared Motion Lab v2 session required');
  }
}

export function connectV2LiveMotionLab({
  targetWindow, session, onStatus = () => {}, fetchImpl = fetch,
  hostWindow = window,
}) {
  valid(session);
  if (!targetWindow || typeof targetWindow.postMessage !== 'function')
    throw new Error('Motion Lab v2 iframe window required');
  let stopped = false;
  let receivedReady = false;
  let busy = false;
  const headers = {'Content-Type': 'application/json',
                   'X-Simba-Capability': session.capability};
  const notify = (type, data = {}) => onStatus({type, ...data});
  const send = (type, payload = {}) => targetWindow.postMessage({
    protocol: BRIDGE_V2, type,
    request_id: session.launch.request_id,
    project_id: session.launch.project_id,
    payload,
  }, MOTION_LAB_ORIGIN);

  async function deliver(selection) {
    if (busy || stopped) return;
    busy = true;
    try {
      if (!selection || selection.schema !== SELECTION_V2 ||
          selection.request_id !== session.launch.request_id ||
          selection.project_id !== session.launch.project_id ||
          selection.expected_input_fingerprint !==
            session.launch.expected_input_fingerprint ||
          selection.proposals_sha256 !== session.proposals_sha256 ||
          selection.materials_sha256 !== session.proposals.materials_sha256 ||
          selection.decision?.explicit_approval !== true ||
          selection.decision?.state !== 'USER_SELECTED_IN_CONNECTED_SESSION' ||
          selection.decision?.visual_layout_edited !== false &&
          selection.decision?.visual_layout_edited !== true ||
          (selection.decision?.visual_layout_edited === true &&
            !Array.isArray(selection.scene_layout)) ||
          selection.guards?.run_render !== false ||
          selection.guards?.run_tts !== false ||
          selection.guards?.run_a2e !== false ||
          selection.guards?.run_paid_operations !== false ||
          selection.guards?.auto_publish !== false)
        throw new Error('Unapproved or incomplete connected v2 selection');
      const response = await fetchImpl('/api/motionlab/v2/selection', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', headers,
        body: JSON.stringify({session_id:session.session_id, selection}),
      });
      if (!response.ok) throw new Error('Receiver rejected v2 selection');
      const result = await response.json();
      if (result.persisted !== true || typeof result.receipt_id !== 'string' ||
          !result.receipt_id) throw new Error('Durable receipt not confirmed');
      send('SIMBA_MOTIONLAB_V2_ACK', {
        accepted: true, receipt_id:result.receipt_id,
        state:'SELECTION_DURABLY_QUEUED_NOT_APPLIED',
      });
      notify('saved',{receipt_id:result.receipt_id});
    } catch {
      send('SIMBA_MOTIONLAB_V2_ACK', {
        accepted:false, state:'RECEIVER_REJECTED_OR_UNAVAILABLE',
      });
      notify('save_failed');
    } finally {
      busy = false;
    }
  }

  function onMessage(event) {
    if (stopped || event.origin !== MOTION_LAB_ORIGIN ||
        event.source !== targetWindow) return;
    const data=event.data;
    if (!data || data.protocol !== BRIDGE_V2) return;
    if (data.type === 'SIMBA_MOTIONLAB_V2_READY') {
      // Before START, the iframe has not received private project identifiers.
      // Only the verified iframe Window + exact origin may announce readiness.
      if (receivedReady ||
          (data.request_id != null && data.request_id !== session.launch.request_id) ||
          (data.project_id != null && data.project_id !== session.launch.project_id)) return;
      receivedReady=true;
      send('SIMBA_MOTIONLAB_V2_START',{
        materials:session.launch, proposals:session.proposals,
        materials_sha256:session.proposals.materials_sha256,
        proposals_sha256:session.proposals_sha256,
      });
      notify('editing',{ready:true});
    } else if (receivedReady &&
        data.request_id === session.launch.request_id &&
        data.project_id === session.launch.project_id &&
        data.type === 'SIMBA_MOTIONLAB_V2_SELECTION') {
      void deliver(data.payload?.selection);
    }
  }
  hostWindow.addEventListener('message',onMessage);

  return {
    motionLabUrl:storyboardUrl(),
    start() {
      // Host never fakes READY: the internal Motion Lab v2 UI must first
      // explicitly announce that it understands this full contract.
      if (!receivedReady) notify('awaiting_v2_motionlab_ui');
    },
    stop() { stopped=true; hostWindow.removeEventListener('message',onMessage); },
    async status() {
      if (stopped) throw new Error('Connection already closed');
      const res=await fetchImpl('/api/motionlab/status/'+session.session_id, {
        method:'GET', credentials:'same-origin', cache:'no-store',
        headers:{'X-Simba-Capability':session.capability},
      });
      if (!res.ok) throw new Error('Protected status unavailable');
      const status=await res.json();
      if (status.project_applied === true) notify('montage_handoff_applied');
      else if (status.status === 'BLOCKED') notify('montage_handoff_blocked');
      else notify('montage_handoff_pending',{state:status.status});
      return status;
    },
  };
}
