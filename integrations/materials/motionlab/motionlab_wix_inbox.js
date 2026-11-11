/* MotionLab Wix inbox: browser-owned site-member OAuth PKCE and create-only CMS approvals.
 * No GitHub API key, Wix admin key, private media, automated render or paid action.
 * Public Wix OAuth client id is not a secret.
 */
'use strict';
(function (root) {
  const CLIENT_ID = '2771b8ab-4ba7-4438-a6f1-5a37a7bc665a';
  const COLLECTION = 'SimbaMotionLabInboxV1';
  const API = 'https://www.wixapis.com';
  const REDIRECT = 'https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com/storyboard.html';
  const AUTH_KEY = 'simba:motionlab:wix-member-access:v1';
  const LOGIN_KEY = 'simba:motionlab:wix-oauth-pkce:v1';
  const RECEIPT_KEY = 'simba:motionlab:last-wix-delivery:v1';
  const MAX_SELECTION_BYTES = 140000;
  let retry = null;

  const bytes = value => new TextEncoder().encode(value);
  const b64url = bytesValue => {
    let binary = '';
    for (const b of bytesValue) binary += String.fromCharCode(b);
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
  };
  const random = n => b64url(crypto.getRandomValues(new Uint8Array(n)));
  const sorted = value => {
    if (Array.isArray(value)) return value.map(sorted);
    if (value && typeof value === 'object') {
      const out = {};
      for (const key of Object.keys(value).sort()) out[key] = sorted(value[key]);
      return out;
    }
    return value;
  };
  const canonical = value => JSON.stringify(sorted(value));
  const hash = async value => {
    const digest = await crypto.subtle.digest('SHA-256', bytes(canonical(value)));
    return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
  };
  const safeRead = (key) => {
    try { return JSON.parse(sessionStorage.getItem(key) || 'null'); } catch { return null; }
  };
  const auth = () => {
    const stored = safeRead(AUTH_KEY);
    return stored && typeof stored.access_token === 'string' &&
      Number(stored.expires_at) > Date.now() + 30000 ? stored : null;
  };
  const isLoggedIn = () => Boolean(auth());
  const request = async (url, options) => {
    let response;
    try {
      response = await fetch(url, {...options, cache: 'no-store'});
    } catch {
      throw new Error('Нет связи с Wix. Выбор не сохранен.');
    }
    let data;
    try { data = await response.json(); } catch { data = {}; }
    if (!response.ok) {
      const kind = response.status === 401 || response.status === 403
        ? 'Требуется вход участника Wix или разрешение на запись.'
        : 'Wix отклонил запрос (' + response.status + ').';
      throw new Error(kind);
    }
    return data;
  };
  const jsonPost = (url, data, bearer) => request(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', ...(bearer ? {'Authorization': bearer} : {})},
    body: JSON.stringify(data)
  });
  const saveToken = response => {
    if (!response || typeof response.access_token !== 'string') throw new Error('Wix не выдал токен участника');
    sessionStorage.setItem(AUTH_KEY, JSON.stringify({
      access_token: response.access_token,
      expires_at: Date.now() + Math.max(60, Number(response.expires_in) || 0) * 1000
    }));
  };

  async function startLogin() {
    if (location.origin + location.pathname !== REDIRECT) {
      throw new Error('Вход разрешен только на опубликованной странице MotionLab.');
    }
    if (!crypto?.subtle || !crypto?.getRandomValues) throw new Error('Для входа нужен защищенный HTTPS.');
    const verifier = random(48);
    const challenge = b64url(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes(verifier))));
    const state = random(24);
    sessionStorage.setItem(LOGIN_KEY, JSON.stringify({verifier, state, created: Date.now()}));
    const visitor = await jsonPost(API + '/oauth2/token', {clientId: CLIENT_ID, grantType: 'anonymous'});
    const login = await jsonPost(API + '/_api/redirects-api/v1/redirect-session', {
      auth: {authRequest: {
        redirectUri: REDIRECT, clientId: CLIENT_ID, codeChallenge: challenge,
        codeChallengeMethod: 'S256', responseMode: 'fragment',
        responseType: 'code', scope: 'offline_access', state
      }},
      preferences: {additionalQueryParameters: {lang: 'ru'}}
    }, visitor.access_token);
    const url = login?.redirectSession?.fullUrl;
    if (typeof url !== 'string' || !url.startsWith('https://')) {
      throw new Error('Wix не вернул допустимую ссылку входа.');
    }
    location.assign(url);
  }

  async function completeLogin() {
    const fragment = new URLSearchParams(location.hash.replace(/^#\??/, ''));
    if (!fragment.has('code') && !fragment.has('error')) return false;
    const pending = safeRead(LOGIN_KEY);
    history.replaceState(null, '', REDIRECT + location.search);
    sessionStorage.removeItem(LOGIN_KEY);
    if (fragment.has('error')) throw new Error('Wix отклонил вход.');
    if (!pending || Date.now() - pending.created > 600000 ||
        fragment.get('state') !== pending.state) {
      throw new Error('Неверное подтверждение входа Wix.');
    }
    const tokens = await jsonPost(API + '/oauth2/token', {
      clientId: CLIENT_ID, grantType: 'authorization_code', redirectUri: REDIRECT,
      code: fragment.get('code'), codeVerifier: pending.verifier
    });
    saveToken(tokens);
    return true;
  }

  async function getStatus(deliveryId) {
    if (!/^[a-f0-9-]{36}$/.test(deliveryId)) throw new Error('Неверный ID доставки.');
    const login = auth();
    if (!login) throw new Error('Сначала войдите в Wix для проверки статуса.');
    const item = await request(API + '/wix-data/v2/items/' + encodeURIComponent(deliveryId) +
      '?dataCollectionId=' + encodeURIComponent(COLLECTION) + '&consistentRead=true', {
      headers: {'Authorization': login.access_token}
    });
    if (item?.dataItem?.id !== deliveryId || typeof item?.dataItem?.data?.state !== 'string') {
      throw new Error('Wix не подтвердил запись выбора.');
    }
    return item.dataItem.data;
  }
  function receipt() {
    try {
      const data = JSON.parse(localStorage.getItem(RECEIPT_KEY) || 'null');
      return data && /^[a-f0-9-]{36}$/.test(data.deliveryId) ? data : null;
    } catch { return null; }
  }
  async function submit(selection) {
    const token = auth();
    if (!token) throw new Error('Для сохранения нужно войти в Wix.');
    if (!selection || typeof selection !== 'object' ||
        !selection.request_id || !selection.project_id ||
        !/^[a-f0-9]{64}$/.test(selection.expected_input_fingerprint || '')) {
      throw new Error('Нужно проверенное задание с исходной версией проекта.');
    }
    const size = bytes(canonical(selection)).length;
    if (size > MAX_SELECTION_BYTES) throw new Error('Решение превышает допустимый размер.');
    const signature = await hash(selection);
    if (retry && retry.hash !== signature) retry = null;
    if (!retry) retry = {deliveryId: crypto.randomUUID(), hash: signature, selection};
    const current = retry;
    const data = {
      projectId: selection.project_id,
      sessionId: selection.request_id,
      deliveryId: current.deliveryId,
      selectionSha256: current.hash,
      sourceFingerprint: selection.expected_input_fingerprint,
      selection: current.selection,
      state: 'PENDING'
    };
    try {
      const inserted = await jsonPost(API + '/wix-data/v2/items', {
        dataCollectionId: COLLECTION,
        dataItem: {id: current.deliveryId, data}
      }, token.access_token);
      if (inserted?.dataItem?.id !== current.deliveryId) {
        throw new Error('Wix не вернул квитанцию записи. Проверьте статус.');
      }
    } catch (error) {
      // A timeout/duplicate create can mean Wix already persisted a record.
      // Only a matching ID + hash + source proves delivery.
      let stored;
      try { stored = await getStatus(current.deliveryId); } catch {}
      if (!stored || stored.selectionSha256 !== current.hash ||
          stored.sourceFingerprint !== selection.expected_input_fingerprint) throw error;
    }
    const saved = {
      deliveryId: current.deliveryId, projectId: selection.project_id,
      sourceFingerprint: selection.expected_input_fingerprint
    };
    localStorage.setItem(RECEIPT_KEY, JSON.stringify(saved));
    return {deliveryId: current.deliveryId, state: 'PENDING'};
  }

  const clearRetry = () => { retry = null; };
  root.MotionLabInbox = {
    startLogin, completeLogin, isLoggedIn, submit, getStatus, receipt, clearRetry
  };
})(window);
