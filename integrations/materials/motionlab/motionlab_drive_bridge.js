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
  function projectCapability(fragment) {
    const match=/^#project=([A-Za-z0-9_-]{15,100})\.([0-9a-f]{64})$/.exec(fragment||'');
    return match ? {schema:'bontours.motionlab.drive-handoff/v1',ticket_id:match[1],ticket_token:match[2]} : null;
  }
  async function readProjectPart(handoff,operation,asset_id) {
    if(!ready(handoff))throw Error('Загрузка закрытого проекта не настроена.');
    const nonce=crypto.randomUUID(),frame=document.createElement('iframe'),form=document.createElement('form');
    frame.name='motionlab-project-'+nonce;frame.hidden=true;frame.tabIndex=-1;
    form.method='POST';form.action=SCRIPT;form.target=frame.name;form.hidden=true;
    const params={nonce,operation,ticket_id:handoff.ticket_id,ticket_token:handoff.ticket_token};
    if(asset_id)params.asset_id=asset_id;
    Object.entries(params).forEach(([name,value])=>{const input=document.createElement('input');input.type='hidden';input.name=name;input.value=value;form.append(input);});
    document.body.append(frame,form);
    return await new Promise((resolve,reject)=>{
      const cleanup=()=>{clearTimeout(timer);window.removeEventListener('message',receive);frame.remove();form.remove();};
      const receive=e=>{
        if(!allowedReply(e.origin)||e.data?.type!=='SIMBA_DRIVE_PROJECT_REPLY'||e.data?.nonce!==nonce)return;
        const data=e.data;cleanup();
        const valid=operation==='render_status'?['RENDER_READY','RENDER_PENDING'].includes(data.status):data.status===(operation==='load_project'?'PROJECT_READY':'ASSET_READY');
        if(!valid)reject(Error('Drive: '+String(data.error_code||'INVALID_PROJECT_REPLY').slice(0,65)));
        else resolve(data);
      };
      const timer=setTimeout(()=>{cleanup();reject(Error('Нет ответа загрузчика проекта. Передача выбора не выполнялась.'));},60000);
      window.addEventListener('message',receive);
      try{form.submit();}catch{cleanup();reject(Error('Не удалось запросить проект.'));}
    });
  }
  async function openProjectLink(api) {
    const fromLink=projectCapability(location.hash);
    if(location.hash.startsWith('#project=')&&!fromLink){api.status('Неверная ссылка проекта. Запросите новую ссылку у Киностудии.');return;}
    let handoff=fromLink;
    if(!handoff && !location.hash){try{handoff=projectCapability(sessionStorage.getItem('simba:motionlab:project-link:v1'));}catch{}}
    if(!handoff)return;
    // Fragment capabilities are never sent in an HTTP URL/referrer or saved
    // in localStorage. Same-tab reload uses sessionStorage; server checks TTL.
    if(fromLink){try{sessionStorage.setItem('simba:motionlab:project-link:v1',location.hash);}catch{}history.replaceState(null,'',location.pathname+location.search);}
    api.busy?.(true);
    try {
      api.status('Открываю закрытый проект…');
      const data=await readProjectPart(handoff,'load_project');
      const assets=data.assets;
      if(!Array.isArray(assets)||!assets.length||assets.length>24)throw Error('Неверный список клипов проекта.');
      const seen=new Set();let total=0;
      for(const a of assets){
        if(!a||typeof a.asset_id!=='string'||seen.has(a.asset_id)||!/^[0-9a-f]{64}$/.test(a.sha256||'')
          ||!Number.isInteger(a.size_bytes)||a.size_bytes<1024||a.size_bytes>20*1024*1024||a.mime_type!=='video/mp4')throw Error('Неверный исходный клип.');
        seen.add(a.asset_id);total+=a.size_bytes;
      }
      if(total>120*1024*1024)throw Error('Проект превышает лимит просмотра.');
      api.load({...data.launch,handoff});
      for(let i=0;i<assets.length;i++){
        const a=assets[i];api.status('Загружаю клип '+(i+1)+' из '+assets.length+'…');
        const media=await readProjectPart(handoff,'load_asset',a.asset_id);
        if(media.asset_id!==a.asset_id||media.sha256!==a.sha256||media.size_bytes!==a.size_bytes
          ||media.mime_type!=='video/mp4'||typeof media.base64!=='string'||media.base64.length!==4*Math.ceil(a.size_bytes/3))throw Error('Ответ клипа не совпал с заданием.');
        const bytes=Uint8Array.from(atob(media.base64),c=>c.charCodeAt(0));
        const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(b=>b.toString(16).padStart(2,'0')).join('');
        if(bytes.length!==a.size_bytes||hash!==a.sha256)throw Error('SHA-256 клипа не совпал.');
        await api.asset(a.asset_id,new File([bytes],'project-'+i+'.mp4',{type:'video/mp4'}));
      }
      api.status('Проект открыт. Все клипы проверены. Выбор еще не передан в Montage.');
      // Read-only owner render status; no rendering is initiated by this call.
      if(root.motionlabRenderPollStop)root.motionlabRenderPollStop();
      let stopped=false,timer=null;
      root.motionlabRenderPollStop=()=>{stopped=true;clearTimeout(timer);};
      const poll=async()=>{
        if(stopped)return;
        try{
          const reply=await readProjectPart(handoff,'render_status');
          if(stopped)return;
          api.result?.(reply);
          if(reply.status==='RENDER_READY')return;
        }catch(err){
          // Older un-deployed Apps Script may reject status requests.
          // Never claim a confirmed render without its private Drive receipt.
          api.result?.({status:'RENDER_STATUS_UNAVAILABLE',project_id:data.launch.project_id});
          return;
        }
        timer=setTimeout(poll,120000);
      };
      poll();
    } catch(error){api.status('Проект не открыт полностью: '+String(error.message||error));}
    finally{api.busy?.(false);}
  }
  root.MotionLabDrive = {ready,send,receipt,clearReceipt,openProjectLink,projectCapability};
})(window);
