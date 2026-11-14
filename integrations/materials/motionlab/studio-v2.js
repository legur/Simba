/* Simba Studio v2: private source-authenticated owner choice, NO rendering.
 * The receiving Apps Script never dispatches these v2 selections to v1.
 */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const S = {
    handoff:null,materials:null,proposals:null,assets:[],
    option:null,scenes:[],layout:null,busy:false,receipt:null,previewUrls:new Set()
  };
  const SCRIPT=String(window.MOTIONLAB_DRIVE_RECEIVER_URL||'');
  const TRUSTED_SCRIPT=/^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]{15,200}\/exec$/;
  const allowedReply=origin=>
    /^https:\/\/(?:[A-Za-z0-9-]+\.)*googleusercontent\.com$/.test(origin)
    ||origin==='https://script.google.com';
  const SHA=/^[a-f0-9]{64}$/;
  // Mirrors Python motionlab_scene_contract.MAX_SCENES; checked in CI.
  const MAX_SCENES=24;
  const sorted=v=>Array.isArray(v)?v.map(sorted)
    :v&&typeof v==='object'
      ?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])]))
      :v;
  const canonical=v=>JSON.stringify(sorted(v));
  async function digest(value){
    const raw=typeof value==='string'?value:canonical(value);
    const bytes=new TextEncoder().encode(raw);
    const hash=await crypto.subtle.digest('SHA-256',bytes);
    return [...new Uint8Array(hash)].map(n=>n.toString(16).padStart(2,'0')).join('');
  }
  function display(message,error=false){
    $('status').textContent=message;
    $('status').classList.toggle('error',error);
  }
  const element=(tag,text,className)=>{
    const node=document.createElement(tag);
    if(typeof text==='string')node.textContent=text;
    if(className)node.className=className;
    return node;
  };
  function cleanupPreviews(){
    for(const url of S.previewUrls)URL.revokeObjectURL(url);
    S.previewUrls.clear();
  }
  function requestCapability(){
    const match=/^#project_v2=([A-Za-z0-9_-]{15,100})\.([0-9a-f]{64})$/.exec(location.hash);
    let token=null;
    if(match){
      token={ticket_id:match[1],ticket_token:match[2]};
      try{sessionStorage.setItem('simba:studio:v2:link',location.hash);}catch{}
      history.replaceState(null,'',location.pathname+location.search);
    }else if(!location.hash){
      try{
        const last=sessionStorage.getItem('simba:studio:v2:link');
        const found=/^#project_v2=([A-Za-z0-9_-]{15,100})\.([0-9a-f]{64})$/.exec(last||'');
        if(found)token={ticket_id:found[1],ticket_token:found[2]};
      }catch{}
    }
    return token;
  }
  async function post(operation,extra={}){
    if(!TRUSTED_SCRIPT.test(SCRIPT)||!S.handoff||!crypto?.subtle)
      throw Error('Приватный приемник Google Drive недоступен.');
    if(S.busy)throw Error('Предыдущая операция еще выполняется.');
    const nonce=crypto.randomUUID();
    const frame=document.createElement('iframe');
    const form=document.createElement('form');
    frame.name='studio-v2-'+nonce;
    frame.style.cssText='position:absolute;left:-9999px;width:1px;height:1px;border:0';
    frame.setAttribute('aria-hidden','true');
    form.hidden=true;form.method='POST';form.action=SCRIPT;form.target=frame.name;
    const entries={nonce,operation,
      ticket_id:S.handoff.ticket_id,ticket_token:S.handoff.ticket_token,...extra};
    for(const [name,value] of Object.entries(entries)){
      const input=document.createElement('input');
      input.type='hidden';input.name=name;input.value=String(value);
      form.append(input);
    }
    document.body.append(frame,form);
    S.busy=true;
    try{
      return await new Promise((resolve,reject)=>{
        let done=false;
        const cleanup=()=>{done=true;clearTimeout(timeout);window.removeEventListener('message',receive);form.remove();frame.remove()};
        const timeout=setTimeout(()=>{cleanup();reject(Error('Сервер не подтвердил операцию. Перед повтором проверьте статус.'));},60000);
        const receive=e=>{
          const expected=operation==='v2_submit'?'SIMBA_DRIVE_V2_RECEIPT':'SIMBA_DRIVE_V2_PROJECT_REPLY';
          if(done||!allowedReply(e.origin)||e.data?.type!==expected||e.data?.nonce!==nonce)return;
          cleanup();
          if(e.data.status==='REJECTED')
            return reject(Error('Защищенный сервер отклонил запрос: '+String(e.data.error_code||'V2_REJECTED').slice(0,65)));
          resolve(e.data);
        };
        window.addEventListener('message',receive);
        try{form.submit()}catch{cleanup();reject(Error('Не удалось отправить форму через Google.'))}
      });
    }finally{S.busy=false}
  }
  async function verifyLaunch(reply){
    const m=reply.materials,p=reply.proposals,assets=reply.assets;
    if(reply.status!=='V2_PROJECT_READY'||!m||!p
      ||m.schema!=='bontours.motionlab.materials.launch/v2'
      ||p.schema!=='bontours.motionlab.proposals/v2'
      ||m.audio_alignment_status!=='AUDIO_ALIGNMENT_VERIFIED_AUTO'
      ||p.analysis?.status!=='REAL_VIDEO_AUTOMATICALLY_ANALYZED'
      ||!Array.isArray(m.scenes)||!m.scenes.length||m.scenes.length>MAX_SCENES
      ||!Array.isArray(p.proposals)||p.proposals.length!==3
      ||!Array.isArray(assets)||!assets.length||assets.length>m.scenes.length)
      throw Error('Не получен проверенный пакет v2 с тремя предложениями и автоматической проверкой озвучки.');
    if(p.materials_sha256!==await digest(m)
      ||p.renderer_revision_sha256!==m.renderer_capabilities?.revision_sha256
      ||p.project_id!==m.project_id||p.request_id!==m.request_id)
      throw Error('Изменены исходные материалы или версия рендерера.');
    const clipById=new Map();
    for(const a of assets){
      if(!a||typeof a.asset_id!=='string'||clipById.has(a.asset_id)
        ||!SHA.test(a.sha256)||a.mime_type!=='video/mp4'
        ||!Number.isInteger(a.size_bytes)||a.size_bytes<1024)
        throw Error('Повторная или недостоверная запись исходного MP4.');
      clipById.set(a.asset_id,a);
    }
    for(const scene of m.scenes){
      const a=clipById.get(scene.asset_id);
      if(!a||scene.media?.asset_sha256!==a.sha256)
        throw Error('Оригинальные клипы не соответствуют заданию.');
    }
    if(clipById.size!==new Set(m.scenes.map(s=>s.asset_id)).size)
      throw Error('Обнаружен посторонний MP4 без привязки к сцене.');
    return {materials:m,proposals:p,assets};
  }
  function selectMenu(values,selected,onChange){
    const menu=document.createElement('select');
    for(const value of values){
      const opt=document.createElement('option');
      opt.value=value;opt.textContent=value;
      menu.append(opt);
    }
    menu.value=selected;
    if(!values.includes(selected))throw Error('Вариант использует не поддерживаемый рендерером эффект.');
    menu.addEventListener('change',()=>{onChange(menu.value);invalidate()});
    return menu;
  }
  function selectField(label,choices,value,onChange){
    const wrap=element('label',label);
    wrap.append(selectMenu(choices,value,onChange));
    return wrap;
  }
  function invalidate(){
    S.receipt=null;
    $('ownerConfirm').checked=false;
    $('submit').disabled=true;
    $('receipt').hidden=true;
  }
  function choose(n){
    if(![1,2,3].includes(n)||S.receipt)return;
    S.option=n;
    const chosen=S.proposals.proposals[n-1];
    S.scenes=structuredClone(chosen.scenes);
    S.layout=structuredClone(chosen.scene_layout||S.materials.scenes.map(s=>({
      scene_id:s.scene_id,asset_id:s.asset_id,
      layout:{title:{x:50,y:47,scale:100},subtitle:{x:50,y:82,scale:100}}
    })));
    invalidate();render();
  }
  function card(option){
    const btn=element('button',null,'option'+(option.option===S.option?' selected':''));
    btn.type='button';btn.setAttribute('aria-pressed',String(option.option===S.option));
    btn.append(element('small','ВАРИАНТ '+option.option),
      element('strong',option.title));
    if(option.recommended)btn.append(element('span','Рекомендовано системой','tag'));
    btn.append(element('p',option.rationale));
    btn.addEventListener('click',()=>choose(option.option));
    return btn;
  }
  function applyGlobalSub(key,value){
    for(const row of S.scenes)row.subtitle[key]=value;
  }
  async function preview(scene,index,button,video){
    const original=S.assets.find(a=>a.asset_id===S.materials.scenes[index].asset_id);
    if(!original||scene.scene_id!==S.materials.scenes[index].scene_id)
      throw Error('Неверная сцена');
    button.disabled=true;
    display('Загружаю и проверяю оригинальный клип '+(index+1)+'...');
    try{
      const result=await post('v2_asset',{asset_id:original.asset_id});
      if(result.status!=='V2_ASSET_READY'
        ||result.asset_id!==original.asset_id||result.sha256!==original.sha256
        ||result.size_bytes!==original.size_bytes
        ||typeof result.base64!=='string'
        ||result.base64.length!==4*Math.ceil(original.size_bytes/3))
        throw Error('Получен несоответствующий клип.');
      const bytes=Uint8Array.from(atob(result.base64),x=>x.charCodeAt(0));
      const h=await crypto.subtle.digest('SHA-256',bytes);
      const sha=[...new Uint8Array(h)].map(n=>n.toString(16).padStart(2,'0')).join('');
      if(bytes.length!==original.size_bytes||sha!==original.sha256)
        throw Error('Контрольная сумма исходного MP4 не совпадает.');
      if(video.dataset.url){URL.revokeObjectURL(video.dataset.url);S.previewUrls.delete(video.dataset.url)}
      const url=URL.createObjectURL(new Blob([bytes],{type:'video/mp4'}));
      S.previewUrls.add(url);video.dataset.url=url;video.src=url;
      video.hidden=false;
      video.load();
      display('Исходный клип '+(index+1)+' подтвержден по SHA-256. Монтаж не запущен.');
    }catch(err){display(String(err.message||err),true)}
    finally{button.disabled=false}
  }
  function renderScenes(){
    const grid=$('scenes');grid.replaceChildren();
    const caps=S.materials.renderer_capabilities;
    S.scenes.forEach((row,i)=>{
      const source=S.materials.scenes[i];
      const box=element('article',null,'scene');
      box.append(element('h3',source.name||'Сцена '+(i+1)),
        element('p',source.locked?.title_text||'Без титра'));
      const prev=element('div',null,'preview');
      const video=document.createElement('video');video.hidden=true;
      video.controls=true;video.playsInline=true;video.preload='none';
      const actions=element('div',null);
      actions.append(element('p','Оригинал A2E · '+Math.round(source.media.duration_s*10)/10+' с'));
      const button=element('button','Открыть MP4','subtle');
      button.type='button';
      button.addEventListener('click',()=>preview(row,i,button,video));
      actions.append(button);
      const frame=element('div',null,'layout-frame');frame.append(video);
      const layout=S.layout[i].layout;
      for(const kind of ['title','subtitle']){
        const overlay=element('div',kind==='title'?source.locked.title_text:source.locked.subtitle_preview,'layout-overlay '+kind);
        const update=()=>{const v=layout[kind];overlay.style.left=v.x+'%';overlay.style.top=v.y+'%';overlay.style.fontSize=(kind==='title'?8.7:4.2)*v.scale/100+'cqw'};
        update();frame.append(overlay);
        if(caps.visual_layout?.schema==='bontours.montage.visual-layout/v1'){
          const group=element('fieldset',null,'layout-controls');
          group.append(element('legend',kind==='title'?'Расположение титра':'Расположение субтитров'));
          for(const [key,label,min,max,step] of [['x','По горизонтали',36,64,1],['y','По вертикали',13,87,1],['scale','Размер',70,140,5]]){
            const field=element('label',label+' (%)'),input=document.createElement('input');
            input.type='number';input.min=String(min);input.max=String(max);input.step=String(step);input.value=String(layout[kind][key]);
            input.addEventListener('change',()=>{const v=Number(input.value);if(!Number.isInteger(v)||v<min||v>max||(v-min)%step){input.value=String(layout[kind][key]);return}layout[kind][key]=v;update();invalidate()});
            field.append(input);group.append(field);
          }
          actions.append(group);
        }
      }
      actions.append(element('p','Положение показано приблизительно. Окончательный вид проверяется в готовом видео.','muted'));
      prev.append(frame,actions);
      box.append(prev);
      const controls=element('div',null,'controls');
      controls.append(
        selectField('Камера',caps.camera.renderable,row.camera.id,v=>row.camera.id=v),
        selectField('Анимация титра',caps.title_fx.renderable,row.title_fx,v=>row.title_fx=v)
      );
      const intensity=element('label','Сила движения (0–100)');
      const number=document.createElement('input');number.type='number';
      number.min='0';number.max='100';number.step='5';number.value=row.camera.intensity_percent;
      number.addEventListener('change',()=>{
        const val=Number(number.value);
        if(!Number.isFinite(val)||val<0||val>100){number.value=row.camera.intensity_percent;return}
        row.camera.intensity_percent=val;invalidate()
      });
      intensity.append(number);controls.append(intensity);
      if(i>0){
        controls.append(
          selectField('Переход',caps.transition.renderable,row.transition.id,v=>row.transition.id=v)
        );
        const transitionTime=element('label','Длительность перехода (мс)');
        const time=document.createElement('input');
        time.type='number';time.min='400';time.max='2400';time.step='100';
        time.value=row.transition.duration_ms;
        time.addEventListener('change',()=>{
          const val=Number(time.value);
          if(!Number.isInteger(val)||val<400||val>2400){time.value=row.transition.duration_ms;return}
          row.transition.duration_ms=val;invalidate()
        });
        transitionTime.append(time);controls.append(transitionTime);
      }
      if(i===0){
        controls.append(
          selectField('Общий стиль субтитров',caps.subtitle.styles,row.subtitle.style_id,
            v=>{applyGlobalSub('style_id',v);renderScenes()}),
          selectField('Общая анимация слов',caps.subtitle.motions,row.subtitle.word_motion_id,
            v=>{applyGlobalSub('word_motion_id',v);renderScenes()})
        );
      }
      box.append(controls);grid.append(box);
    });
  }
  function render(){
    $('options').replaceChildren(...S.proposals.proposals.map(card));
    renderScenes();
    $('submit').disabled=S.option===null||!$('ownerConfirm').checked||!!S.receipt||S.busy;
  }
  function buildSelection(){
    if(!S.option||!$('ownerConfirm').checked||S.receipt)
      throw Error('Нужны выбранный вариант и явное подтверждение.');
    const m=S.materials,p=S.proposals;
    const initial=p.proposals[S.option-1].scene_layout||m.scenes.map(s=>({scene_id:s.scene_id,asset_id:s.asset_id,
      layout:{title:{x:50,y:47,scale:100},subtitle:{x:50,y:82,scale:100}}}));
    const edited=canonical(S.layout)!==canonical(initial);
    if(edited&&m.renderer_capabilities?.visual_layout?.schema!=='bontours.montage.visual-layout/v1')
      throw Error('Рендерер этого проекта не поддерживает изменение положения текста.');
    const result={
      schema:'bontours.motionlab.selection/v2',
      project_id:m.project_id,
      request_id:m.request_id,
      expected_input_fingerprint:m.expected_input_fingerprint,
      materials_sha256:p.materials_sha256,
      proposals_sha256:null,
      format:'9:16',
      next_stage:'MONTAGE_PLANNING_REVIEW',
      decision:{
        selected_option:S.option,
        options_presented:3,
        state:'USER_SELECTED_IN_CONNECTED_SESSION',
        explicit_approval:true,
        visual_layout_edited:edited,
        user_selected_at:new Date().toISOString()
      },
      guards:{
        run_render:false,run_tts:false,run_a2e:false,
        run_paid_operations:false,auto_publish:false,
        preserve_approved_voice:true,preserve_approved_music:true,
        preserve_approved_narration:true
      },
      scenes:structuredClone(S.scenes)
    };
    if(edited||p.proposals[S.option-1].scene_layout)result.scene_layout=structuredClone(S.layout);
    return result;
  }
  async function load(){
    if(!TRUSTED_SCRIPT.test(SCRIPT)||!crypto?.subtle)
      throw Error('Нужен HTTPS и настроенный Google Apps Script.');
    S.handoff=requestCapability();
    if(!S.handoff)throw Error('Нет приватной ссылки проекта v2. Задания демонстрационного режима здесь не принимаются.');
    const reply=await post('v2_load');
    const {materials,proposals,assets}=await verifyLaunch(reply);
    S.materials=materials;S.proposals=proposals;S.assets=assets;
    $('projectName').textContent='Проект: '+materials.project_id;
    $('audioBadge').textContent='ОЗВУЧКА: ПРОВЕРЕНА АВТОМАТИЧЕСКИ';
    $('workspace').hidden=false;
    render();
    display('Три варианта сформированы из реальных MP4. Выберите основу и проверьте настройки.');
  }
  $('ownerConfirm').addEventListener('change',()=>{
    $('submit').disabled=S.option===null||!$('ownerConfirm').checked||!!S.receipt||S.busy;
  });
  $('submit').addEventListener('click',async()=>{
    const button=$('submit');button.disabled=true;
    display('Сохраняю только подтвержденный выбор в закрытый Drive...');
    try{
      const selection=buildSelection();
      selection.proposals_sha256=await digest(S.proposals);
      const json=canonical(selection),hash=await digest(json);
      const response=await post('v2_submit',{selection_json:json,selection_sha256:hash});
      if(response.status!=='V2_SELECTION_SAVED_AWAITING_CANONICAL_CAS'
        ||response.selection_sha256!==hash
        ||!/^[0-9a-f-]{36}$/.test(response.receipt_id||''))
        throw Error('Запись v2 не подтверждена. Рендер не запускался.');
      S.receipt={id:response.receipt_id,sha:hash};
      $('receipt').hidden=false;
      $('receipt').textContent='Решение сохранено в закрытом Drive. Код записи: '+
        response.receipt_id+'. Ожидается серверная проверка и применение. Публикации нет.';
      display('Выбор сохранен. Следующий этап — проверка канонического проекта, НЕ автоматическая публикация.');
      render();
    }catch(err){display(String(err.message||err),true);button.disabled=false;}
  });
  window.addEventListener('pagehide',()=>cleanupPreviews());
  load().catch(err=>display(String(err.message||err),true));
})();
