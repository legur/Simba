'use strict';
/* Connected Motion Lab v2 UI. This augments the existing storyboard, not a
 * second editor. Only authentic host-origin START plus source-pinned Motion Lab
 * proposals can enable sending. No local draft becomes an approval.
 */
(() => {
 const PROTOCOL='bontours.motionlab.bridge/v2';
 const MATERIALS='bontours.motionlab.materials.launch/v2';
 const PROPOSALS='bontours.motionlab.proposals/v2';
 const SELECTION='bontours.motionlab.selection/v2';
 const SHA=/^[a-f0-9]{64}$/;
 let active=null;
 let timer=null;
 const clone=x=>JSON.parse(JSON.stringify(x));
 function fail(msg){throw new Error(msg);}
 function assert(condition,message){if(!condition)fail(message);}
 function same(a,b){return JSON.stringify(a)===JSON.stringify(b);}
 function approvedAssets(){
   assert(active && state.v2===active,'Нет подтвержденного задания v2');
   const source=active.materials.scenes;
   assert(state.scenes.length===source.length,'Изменено число утвержденных сцен');
   return source.map((s,i)=>{
     const row=state.scenes[i],file=previewFor(row);
     assert(row.id===s.scene_id&&row.asset===s.asset_id,
       'Изменен порядок или источник сцены '+(i+1));
     assert(row.title===s.locked.title_text&&row.subtitle===s.locked.subtitle_preview,
       'Изменен утвержденный текст сцены '+(i+1));
     assert(row.media?.asset_sha256===s.media.asset_sha256&&
       Math.abs(row.duration-s.media.duration_s)<.0001,
       'Изменены исходные данные сцены '+(i+1));
     assert(file&&file.assetId===row.asset&&file.type==='video'&&
       file.shaVerified===true&&Math.abs(file.duration-s.media.duration_s)<=.45,
       'Загрузите и проверьте исходный MP4 сцены '+(i+1));
     return row;
   });
 }
 function rendererIssues(rows){
   if(!active)return ['Нет исходного v2 задания'];
   const caps=active.materials.renderer_capabilities;
   const issues=[];
   const permitted=(path,value)=>Array.isArray(path)&&path.includes(value);
   rows.forEach((s,i)=>{
     const src=active.materials.scenes[i];
     if(!src||s.id!==src.scene_id||s.asset!==src.asset_id)
       issues.push('Сцена '+(i+1)+': изменен источник');
     if(!permitted(caps.camera?.renderable,s.camera))
       issues.push('Сцена '+(i+1)+': камера недоступна рендереру');
     if(!permitted(caps.title_fx?.renderable,s.titleFx) ||
       (s.titleFx==='none'&&src?.locked?.title_text))
       issues.push('Сцена '+(i+1)+': титр не поддерживается');
     if(i>0&&!permitted(caps.transition?.renderable,s.transition))
       issues.push('Сцена '+(i+1)+': переход недоступен');
     if(!permitted(caps.subtitle?.styles,s.subtitleStyle)||
       !permitted(caps.subtitle?.motions,s.wordMotion))
       issues.push('Сцена '+(i+1)+': стиль/анимация субтитров недоступны');
   });
   const ui=globalThis.MotionLabVisual;
   const loaded=caps.typography?.native_families_ready||[];
   if(ui?.typography){
     for(const [i,s] of rows.entries())for(const kind of ['title','subtitle']){
       if(!loaded.includes(ui.typography(s,kind)?.family))
         issues.push('Сцена '+(i+1)+': шрифт '+kind+' требует установки в рендерере');
     }
   }
   if(new Set(rows.map(s=>s.subtitleStyle+'|'+s.wordMotion)).size!==1)
     issues.push('Субтитры должны иметь единый стиль и движение слов');
   if(rows.length!==active.materials.scenes.length)issues.push('Число сцен изменено');
   return issues;
 }
 function reviewIssue(){
   try{
     approvedAssets();
     const errors=rendererIssues(state.scenes);
     assert(!errors.length,errors[0]||'Неподдерживаемый эффект');
     assert(filmTotal()<=60,'Длительность ролика превышает 60 секунд');
     return null;
   }catch(error){return error.message;}
 }
 function choose(id){
   if(!active||!Number.isInteger(id)||id<1||id>3)return;
   const proposal=active.proposals.proposals[id-1];
   assert(proposal?.option===id,'Неверный номер режиссерской рекомендации');
   assert(proposal.scenes.length===state.scenes.length,'Изменилось число сцен');
   const layouts=proposal.scene_layout;
   state.scenes.forEach((s,i)=>{
     const fx=proposal.scenes[i];
     assert(fx.scene_id===s.id,'Подмена ID сцены');
     s.camera=fx.camera.id;
     s.intensity=fx.camera.intensity_percent;
     s.transition=i===0?'none':fx.transition.id;
     s.titleFx=fx.title_fx;
     s.subtitleStyle=fx.subtitle.style_id;
     s.wordMotion=fx.subtitle.word_motion_id;
     if(layouts){
       assert(layouts[i]?.scene_id===s.id&&layouts[i]?.asset_id===s.asset,
         'Неверный исходник разметки');
       s.visualLayout=clone(layouts[i].layout);
     }else delete s.visualLayout;
   });
   state.selectedOption=id;
   state.dirty=true;
   resetAck();
   render();
   say('Вариант '+id+' загружен. Проверьте реальные MP4 перед утверждением.');
 }
 function layoutSelection(){
   const editor=globalThis.MotionLabVisual;
   assert(editor&&typeof editor.get==='function','Визуальный редактор не готов');
   return state.scenes.map(s=>({
     scene_id:s.id,asset_id:s.asset,
     layout:{
       title:clone(editor.get(s,'title')),
       subtitle:clone(editor.get(s,'subtitle')),
     },
   }));
 }
 function buildSelection(){
   assert(state.v2===active&&active,'Нет связанного задания');
   assert(state.confirmed,'Монтаж еще не утвержден');
   const issue=reviewIssue();assert(!issue,issue||'Не пройдена проверка');
   const chosen=active.proposals.proposals[state.selectedOption-1];
   const layouts=layoutSelection();
   const expected=chosen.scene_layout||active.materials.scenes.map(s=>({
     scene_id:s.scene_id,asset_id:s.asset_id,
     layout:{title:{x:50,y:47,scale:100},subtitle:{x:50,y:82,scale:100}},
   }));
   const editor=globalThis.MotionLabVisual;
   assert(typeof editor.theme==='function','Глобальный стиль не готов');
   return {
     schema:SELECTION,
     project_id:active.materials.project_id,
     request_id:active.materials.request_id,
     expected_input_fingerprint:active.materials.expected_input_fingerprint,
     materials_sha256:active.materialsSha,
     proposals_sha256:active.proposalsSha,
     format:'9:16',
     decision:{
       selected_option:state.selectedOption,options_presented:3,
       state:'USER_SELECTED_IN_CONNECTED_SESSION',explicit_approval:true,
       user_selected_at:new Date().toISOString(),
       visual_layout_edited:!same(layouts,expected),
     },
     guards:{
       run_render:false,run_tts:false,run_a2e:false,
       run_paid_operations:false,auto_publish:false,
       preserve_approved_voice:true,preserve_approved_music:true,
       preserve_approved_narration:true,
     },
     scenes:state.scenes.map((s,i)=>({
       scene_id:s.id,
       camera:{id:s.camera,intensity_percent:s.intensity},
       transition:i===0?null:{id:s.transition,duration_ms:900},
       title_fx:s.titleFx,
       subtitle:{style_id:s.subtitleStyle,word_motion_id:s.wordMotion},
     })),
     scene_layout:layouts,
     global_theme:{
       typography:{title:editor.theme('title'),subtitle:editor.theme('subtitle')},
     },
     scene_typography:state.scenes.map(s=>({
       scene_id:s.id,asset_id:s.asset,
       typography:clone(s.visualTypography||{}),
     })),
     next_stage:'MONTAGE_PLANNING_REVIEW',
   };
 }
 function sendSelection(){
   if(state.sending)return;
   if(state.lastAck){say('Выбор уже сохранен. Измените настройки для нового согласования.');return;}
   let selection;
   try{selection=buildSelection();}
   catch(error){say('Передача запрещена: '+error.message);return;}
   state.sending=true;state.lastAck=null;renderSummary();
   try{
     active.channel.source.postMessage({
       type:'SIMBA_MOTIONLAB_V2_SELECTION',protocol:PROTOCOL,
       request_id:active.materials.request_id,
       project_id:active.materials.project_id,
       payload:{selection},
     },active.channel.origin);
   }catch{
     state.sending=false;renderSummary();say('Не удалось отправить v2 выбор');
     return;
   }
   clearTimeout(timer);
   timer=setTimeout(()=>{
     if(!state.sending)return;
     state.sending=false;renderSummary();
     say('Нет серверного ACK. Решение не считается переданным.');
   },9000);
 }
 function start(msg,event){
   const payload=msg.payload;
   assert(payload&&payload.materials?.schema===MATERIALS&&
      payload.proposals?.schema===PROPOSALS,'Неверная v2 схема');
   const m=payload.materials,p=payload.proposals;
   assert(m.request_id===msg.request_id&&m.project_id===msg.project_id&&
      p.request_id===m.request_id&&p.project_id===m.project_id&&
      p.expected_input_fingerprint===m.expected_input_fingerprint,
      'Источник и рекомендации не связаны');
   assert(SHA.test(payload.materials_sha256||'')&&
      SHA.test(payload.proposals_sha256||'')&&
      p.materials_sha256===payload.materials_sha256,
      'Отсутствуют серверные SHA-256 материалов и предложений');
   assert(Array.isArray(m.scenes)&&m.scenes.length>=1&&m.scenes.length<=8&&
      Array.isArray(p.proposals)&&p.proposals.length===3,
      'Требуется 3 рекомендации по реальным сценам');
   assert(p.proposals.filter(x=>x.recommended===true).length===1,
      'Нет единственной рекомендованной концепции');
   const sourceIds=new Set();
   for(const s of m.scenes){
     assert(s.locked?.read_only===true&&typeof s.locked.title_text==='string'&&
       typeof s.locked.subtitle_preview==='string'&&s.media?.kind==='video'&&
       SHA.test(s.media.asset_sha256||'')&&
       !sourceIds.has(s.scene_id),'Нет проверенных исходных MP4');
     sourceIds.add(s.scene_id);
   }
   for(let i=0;i<3;i++){
     const q=p.proposals[i];
     assert(q.option===i+1&&Array.isArray(q.scenes)&&q.scenes.length===m.scenes.length,
       'Недостаточно сцен в концепции '+(i+1));
   }
   stopFilm(false);clearPreviews();
   globalThis.MotionLabVisual?.resetForProject?.();
   active={materials:m,proposals:p,materialsSha:payload.materials_sha256,
       proposalsSha:payload.proposals_sha256,channel:{source:event.source,origin:event.origin}};
   state.v2=active;
   state.project={id:m.project_id};
   state.request={id:m.request_id,projectId:m.project_id,
     fingerprint:m.expected_input_fingerprint,stage:'edit_choice'};
   state.concepts=p.proposals.map((q,i)=>({
     id:i+1,name:q.title,desc:q.rationale,tag:q.recommended?'РЕКОМЕНДУЕТСЯ':'ВАРИАНТ',
     camera:q.scenes[0].camera.id,titleFx:q.scenes[0].title_fx,
   }));
   state.scenes=m.scenes.map((s,i)=>makeScene({
     scene_id:s.scene_id,asset_id:s.asset_id,
     name:'Сцена '+String(i+1).padStart(2,'0'),
     duration_s:s.media.duration_s,
     title_text:s.locked.title_text,
     subtitle_preview:s.locked.subtitle_preview,
     media:s.media,
   },i));
   state.selectedIndex=0;state.dirty=false;state.confirmed=false;
   state.bridge=active.channel;state.lastAck=null;state.sending=false;
   const selected=p.proposals.findIndex(q=>q.recommended===true)+1;
   setConnection('connected');
   choose(selected);
   say('Загружены 3 предложения Motion Lab. Для просмотра проверьте исходные MP4.');
 }
 function incoming(event){
   if(!goodSource(event)||event.origin!==expectedHostOrigin())return;
   const msg=event.data;
   if(!msg||msg.protocol!==PROTOCOL)return;
   if(msg.type==='SIMBA_MOTIONLAB_V2_START'){
     if(state.sending)return;
     try{start(msg,event);}
     catch(error){say('Задание v2 отклонено: '+error.message);}
   }else if(msg.type==='SIMBA_MOTIONLAB_V2_ACK'&&active&&
     event.source===active.channel.source&&event.origin===active.channel.origin&&
     msg.project_id===active.materials.project_id&&
     msg.request_id===active.materials.request_id){
     clearTimeout(timer);state.sending=false;
     const receipt=msg.payload?.receipt_id;
     if(msg.payload?.accepted===true&&typeof receipt==='string'&&
       receipt.startsWith('motionlab:v2:')&&receipt.length<=180){
       state.lastAck=receipt;
       say('Монтажное решение сохранено сервером. Рендер еще не запущен.');
     }else say('Сервер не подтвердил сохранение v2 выбора.');
     renderSummary();
   }
 }
 function ready(){
   const target=window.parent!==window?window.parent:window.opener;
   const origin=expectedHostOrigin();
   if(!target||!origin)return;
   target.postMessage({
     protocol:PROTOCOL,type:'SIMBA_MOTIONLAB_V2_READY',
     request_id:null,project_id:null,
     capabilities:['three_source_pinned_proposals','verified_local_mp4',
       'per_scene_layout','global_typography','scene_typography','durable_ack'],
   },origin);
 }
 globalThis.MotionLabV2={choose,rendererIssues,reviewIssue,sendSelection};
 window.addEventListener('message',incoming);
 window.addEventListener('pagehide',()=>clearTimeout(timer));
 ready();
})();
