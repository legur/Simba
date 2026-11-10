import { connectLiveMotionLab } from '/assets/motionlab_live_host.js';

const el = id => document.getElementById(id);
const status = text => { el('status').textContent = text; };
const sessionFragment = /^#([a-f0-9]{32})\.([A-Za-z0-9_-]{32,128})$/;

function error(text) {
  el('studio').hidden = true;
  el('warning').hidden = false;
  el('errorText').textContent = text;
  status('Требуется новая сессия');
}

async function start() {
  const match = location.hash.match(sessionFragment);
  // The short-lived capability is in the URL fragment, never in HTTP logs.
  // Remove it from browser history as soon as the module reads it.
  history.replaceState(null, '', location.pathname);
  if (!match) { error('Ссылка на проект отсутствует или некорректна.'); return; }
  const sid = match[1], capability = match[2];
  let result;
  try {
    const request = await fetch('/api/motionlab/session/' + sid, {
      cache: 'no-store', credentials: 'same-origin',
      headers: { 'X-Simba-Capability': capability },
    });
    if (!request.ok) throw new Error('Сессия недоступна');
    result = await request.json();
  } catch {
    error('Не удалось проверить сессию. Возможно, ссылка уже просрочена.');
    return;
  }
  if (result?.session_id !== sid || !result.launch) {
    error('Сервер вернул некорректную сессию.');
    return;
  }
  const ownerSession = { ...result, capability };
  const frame = el('editor');
  let connection;
  let polling = false;
  let closed = false;
  async function checkStatus() {
    if (!connection || closed) return;
    try {
      const s = await connection.status();
      if (s.status === 'APPLIED') {
        status('Выбор записан в проект Киностудии. Диспетчер получит задание на монтаж.');
        polling = false;
      } else if (s.status === 'BLOCKED') {
        status('Выбор сохранен, но запись в проект требует проверки.');
        polling = false;
      } else if (s.status === 'QUEUED' || s.status === 'PROCESSING') {
        status('Выбор сохранен. Передача монтажеру выполняется.');
      }
    } catch {
      status('Связь с сервером прервана. Выбор мог сохраниться. Проверьте передачу повторно.');
      polling = false;
    }
  }
  async function poll() {
    if (polling) return;
    polling = true;
    for (let i = 0; i < 30 && polling && !closed; i++) {
      await checkStatus();
      if (!polling) break;
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    polling = false;
  }
  connection = connectLiveMotionLab({
    targetWindow: frame.contentWindow,
    session: ownerSession,
    onStatus(event) {
      if (event.type === 'saved') {
        status('Выбор получен и сохранен. Проверяем передачу монтажеру.');
        void poll();
      } else if (event.type === 'save_failed' || event.type === 'invalid_selection') {
        status('Выбор не подтвержден. Можно отправить его повторно.');
      } else if (event.type === 'editing') {
        status('Сессия подключена. Выберите оформление в Motion Lab.');
      } else if (event.type === 'montage_handoff_applied') {
        status('Выбор записан в проект. Запуск задания монтажеру проверяется отдельно.');
      }
    },
  });
  el('project').textContent = 'Проект: ' + result.launch.project_id;
  el('warning').hidden = true;
  el('studio').hidden = false;
  frame.addEventListener('load', () => connection.start());
  frame.src = connection.motionLabUrl;
  el('check').addEventListener('click', () => { void checkStatus(); });
  window.addEventListener('pagehide', () => { closed = true; connection.stop(); });
}

void start();
