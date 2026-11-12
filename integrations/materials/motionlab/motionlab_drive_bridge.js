/* MotionLab direct Google Drive handoff, no Wix login and no Google OAuth.
 * A browser uses only a short-lived one-project capability delivered in a
 * PRIVATE launch file. It cannot list/read/write arbitrary Drive contents.
 * This file does nothing unless the Apps Script web app URL is configured.
 */
'use strict';
(function(root) {
  const SCRIPT = String(root.MOTIONLAB_DRIVE_RECEIVER_URL || '');
  const TRUSTED_SCRIPT = /^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]{15,200}\/exec$/;
  const RECEIPT_KEY = 'simba:motionlab:drive-receipt:v1';
  const allowedReply = origin => /^https:\/\/(?:[A-Za-z0-9-]+\.)*googleusercontent\.com$/.test(origin)
      || origin === 'https://script.google.com';
  const sorted = v => Array.isArray(v) ? v.map(sorted)
      : v && typeof v === 'object' ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])) : v;
  const canonical = o => JSON.stringify(sorted(o));
  const sha256 = async text => {
    const h = await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
    return Array.from(new Uint8Array(h)).map(b=>b.toString(16).padStart(2,'0')).join('');
  };
  const ready = handoff => TRUSTED_SCRIPT.test(SCRIPT)
    && handoff && handoff.schema === 'bontours.motionlab.drive-handoff/v1'
    && /^[A-Za-z0-9_-]{15,100}$/.test(handoff.ticket_id || '')
    && /^[0-9a-f]{64}$/.test(handoff.ticket_token || '')
    && !!crypto?.subtle;
  const receipt = () => {
    try {
      const saved = JSON.parse(localStorage.getItem(RECEIPT_KEY) || 'null');
      return saved && saved.status === 'SAVED_IN_DRIVE_PENDING_MONTAGE'
        && typeof saved.receipt_id === 'string' ? saved : null;
    } catch {return null;}
  };
  const clearReceipt = () => {try {localStorage.removeItem(RECEIPT_KEY);} catch {}};
  async function send(selection,handoff) {
    if (!ready(handoff)) throw Error('Приемник Drive не настроен или отсутствует одноразовое разрешение проекта.');
    if (!selection?.decision || !selection?.scenes || selection?.guards?.run_render !== false)
      throw Error('Не утверждено безопасное режиссерское решение.');
    const payload=canonical(selection);
    if (new TextEncoder().encode(payload).length>140000) throw Error('Задание слишком велико.');
    const hash=await sha256(payload);
    const nonce=crypto.randomUUID();
    const frame=document.createElement('iframe');
    frame.name='motionlab-drive-reply-'+nonce;
    frame.setAttribute('aria-hidden','true');
    frame.tabIndex=-1;
    frame.style.cssText='position:absolute;width:1px;height:1px;left:-5000px;border:0;opacity:0';
    const form=document.createElement('form');
    form.method='POST';form.action=SCRIPT;form.target=frame.name;
    form.enctype='application/x-www-form-urlencoded';form.hidden=true;
    const params={nonce, ticket_id:handoff.ticket_id,ticket_token:handoff.ticket_token,
      selection_sha256:hash,selection_json:payload};
    Object.entries(params).forEach(([name,value])=>{
      const input=document.createElement('input');input.type='hidden';input.name=name;input.value=String(value);
      form.append(input);
    });
    document.body.append(frame,form);
    try {
      return await new Promise((resolve,reject)=>{
        let finished=false;
        const cleanup=()=>{finished=true;clearTimeout(timeout);window.removeEventListener('message',receive);form.remove();frame.remove();};
        const timeout=setTimeout(()=>{if(!finished){cleanup();reject(Error('Нет подтверждения записи от Drive. Проверьте статус перед повтором.'));}},35000);
        const receive=e=>{
          // Apps Script HtmlService sends from a nested Google-origin sandbox
          // window, not necessarily frame.contentWindow. We cannot rely on
          // e.source equality. A strict Google origin plus unpredictable 128-bit
          // per-request nonce, exact selection SHA-256 and server status are all
          // required before claiming any Drive ACK.
          if(!allowedReply(e.origin)
             || e.data?.type!=='SIMBA_DRIVE_INGRESS_RECEIPT' || e.data?.nonce!==nonce) return;
          const data=e.data;cleanup();
          if(data.status!=='SAVED_IN_DRIVE_PENDING_MONTAGE'
             || !/^[0-9a-f-]{36}$/.test(data.receipt_id||'')
             || data.selection_sha256!==hash) {
            reject(Error('Drive не принял задание: '+String(data.error_code||'INVALID_RECEIPT').slice(0,65)));
            return;
          }
          const r={status:data.status,receipt_id:data.receipt_id,
                   project_id:selection.project_id,selection_sha256:hash};
          try {localStorage.setItem(RECEIPT_KEY,JSON.stringify(r));} catch {}
          resolve(r);
        };
        window.addEventListener('message',receive);
        try {form.submit();}
        catch(e){cleanup();reject(Error('Браузер не смог отправить подтверждение.'));}
      });
    } catch(err) {
      throw err;
    }
  }
  root.MotionLabDrive = {ready,send,receipt,clearReceipt};
})(window);
