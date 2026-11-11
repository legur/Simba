'use strict';
/* Motion Lab: direct, accessible, browser-only visual corrections.
 * Per-scene positions deliberately remain a separate v2 DRAFT.
 * They MUST NOT be lost or silently mapped into storyboard selection/v1.
 */
(() => {
 const defaults=Object.freeze({
  title:Object.freeze({x:50,y:47,scale:100}),
  subtitle:Object.freeze({x:50,y:82,scale:100})
 });
 const layer={kind:'title',drag:null,safe:true};
 const coord=(v,fallback,min,max)=>Number.isFinite(Number(v))?Math.round(Math.max(min,Math.min(max,Number(v)))):fallback;
 const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 const $$=s=>Array.from(document.querySelectorAll(s));
 const current=()=>state.scenes[state.selectedIndex];
 function get(scene,kind){return scene?.visualLayout?.[kind]||defaults[kind];}
 function dirty(scene,kind){const a=get(scene,kind),b=defaults[kind];return a.x!==b.x||a.y!==b.y||a.scale!==b.scale;}
 function changed(){return state.scenes.some(s=>dirty(s,'title')||dirty(s,'subtitle'));}
 function normalized(kind,v){
  return {x:coord(v.x,50,36,64),y:coord(v.y,defaults[kind].y,13,87),scale:Math.round(coord(v.scale,100,70,140)/5)*5};
 }
 function renderLayout(scene){
  if(!scene)return;
  const base=Math.max(150,Number($('screen').clientWidth)||240);
  for(const kind of ['title','subtitle']){
   const val=get(scene,kind),node=$(kind==='title'?'frameTitle':'frameSubtitle');
   node.style.left=val.x+'%';node.style.top=val.y+'%';
   node.style.bottom='auto';node.style.width='72%';
   node.style.transform='translate(-50%, -50%)';
   node.style.fontSize=(base*(kind==='title'?.087:.042)*val.scale/100).toFixed(1)+'px';
   node.classList.toggle('active-edit',layer.kind===kind);
   node.setAttribute('aria-label',(kind==='title'?'Титр':'Субтитры')+'. Перемещайте стрелками, удерживайте Shift для шага 5 процентов.');
  }
  $('safeFrame').hidden=!layer.safe;
 }
 function refresh(scene){
  if(!scene)return;
  renderLayout(scene);
  for(const button of $$('[data-edit-layer]')){
   const active=button.dataset.editLayer===layer.kind;
   button.classList.toggle('active',active);
   button.setAttribute('aria-pressed',String(active));
  }
  const val=get(scene,layer.kind);
  for(const [id,value] of [['overlayX',val.x],['overlayY',val.y],['overlayScale',val.scale]]){
   $(id).value=String(value);$(id+'Out').textContent=String(value)+'%';
  }
  $('visualEditStatus').textContent=(layer.kind==='title'?'Титр':'Субтитры')+': позиция '+val.x+'% / '+val.y+'%, размер '+val.scale+'%. Перетащите в кадре или используйте стрелки.';
  $('layoutDeliveryStatus').textContent=changed()?
   'Есть визуальные правки: это черновик v2. Позиции пока нельзя передать действующему Montage v1.':
   'Размещение стандартное. Визуальные изменения требуют отдельного согласованного Montage v2.';
  $('downloadVisual').disabled=!changed();
 }
 function edit(kind,fields,commit=true){
  const scene=current();if(!scene||!defaults[kind])return;
  const merged=normalized(kind,{...get(scene,kind),...fields});
  if(!scene.visualLayout)scene.visualLayout={title:{...defaults.title},subtitle:{...defaults.subtitle}};
  scene.visualLayout[kind]=merged;
  refresh(scene);
  if(commit){state.dirty=true;resetAck();renderSummary();}
 }
 function select(kind){
  if(!defaults[kind])return;
  layer.kind=kind;refresh(current());
 }
 function move(dx,dy,mult=1){
  const val=get(current(),layer.kind);
  edit(layer.kind,{x:val.x+dx*mult,y:val.y+dy*mult});
 }
 function begin(event,kind){
  if(event.button!==undefined&&event.button!==0)return;
  if(!current())return;
  if(film.active||film.paused){
   if(film.index>=0)state.selectedIndex=film.index;
   stopFilm();
  }
  resetPreview();
  select(kind);
  const rect=$('screen').getBoundingClientRect();
  if(rect.width<=0||rect.height<=0)return;
  event.preventDefault();
  layer.drag={kind,scene:current(),pointerId:event.pointerId,rect};
  event.currentTarget.setPointerCapture?.(event.pointerId);
 }
 function drag(event,kind){
  const d=layer.drag;
  if(!d||d.kind!==kind||d.pointerId!==event.pointerId||d.scene!==current())return;
  edit(kind,{
   x:100*(event.clientX-d.rect.left)/d.rect.width,
   y:100*(event.clientY-d.rect.top)/d.rect.height
  },false);
 }
 function finish(event){
  if(!layer.drag||layer.drag.pointerId!==event.pointerId)return;
  layer.drag=null;state.dirty=true;resetAck();renderSummary();
 }
 function saveDraft(){
  const out={
   schema:'bontours.motionlab.visual-layout-draft/v2',
   status:'DRAFT_NOT_DELIVERED',
   project_id:state.project?.id||null,request_id:state.request?.id||null,
   expected_input_fingerprint:state.request?.fingerprint||null,
   selected_option:state.selectedOption,
   user_confirmed:Boolean(state.confirmed),
   no_automated_visual_analysis:true,render_authorized:false,
   pending:'MONTAGE_V2_LAYOUT_SUPPORT',
   scene_layout:state.scenes.map(s=>({scene_id:s.id,asset_id:s.asset||null,layout:{
    title:{...get(s,'title')},subtitle:{...get(s,'subtitle')}
   }})),
   guards:{run_render:false,run_tts:false,run_a2e:false,run_paid_operations:false,auto_publish:false}
  };
  const blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json;charset=utf-8'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download='motionlab-visual-edits-v2-draft.json';document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1500);
  say('Позиции сохранены в черновик v2. Монтажеру ничего не отправлено.');
 }
 function populateCuts(){
  const select=$('cutScene');
  if(!select)return;
  const selected=Number(select.value)||Math.max(1,state.selectedIndex);
  select.replaceChildren();
  if(state.scenes.length<2){
   const o=document.createElement('option');o.textContent='Нет стыков';o.value='';select.append(o);
   select.disabled=true;$('previewCut').disabled=true;
   for(const b of $$('[data-cut-effect]'))b.disabled=true;
   return;
  }
  select.disabled=false;$('previewCut').disabled=false;
  const desired=clamp(selected,1,state.scenes.length-1);
  for(let i=1;i<state.scenes.length;i++){
   const o=document.createElement('option');o.value=String(i);
   o.textContent=String(i).padStart(2,'0')+' → '+String(i+1).padStart(2,'0')+' · '+state.scenes[i].name;
   select.append(o);
  }
  select.value=String(desired);
  refreshCut();
 }
 function refreshCut(){
  const idx=Number($('cutScene').value),scene=state.scenes[idx];
  for(const btn of $$('[data-cut-effect]')){
   const on=Boolean(scene&&scene.transition===btn.dataset.cutEffect);
   btn.classList.toggle('active',on);btn.setAttribute('aria-pressed',String(on));
   btn.disabled=!scene;
  }
 }
 function cutTime(index){
  let t=0;
  for(let i=0;i<index;i++)t+=state.scenes[i].duration;
  return Math.max(0,t-Math.min(.9,state.scenes[index-1].duration*.35)-.35);
 }
 let cutStopTimer=0;
 function previewCut(){
  const index=Number($('cutScene').value);
  if(!Number.isInteger(index)||index<1||index>=state.scenes.length)return;
  clearTimeout(cutStopTimer);
  const time=cutTime(index);
  seek(time);
  startFilm(); // continue at the chosen local cut
  cutStopTimer=setTimeout(()=>{if(film.active)pauseFilm();},2200);
 }
 function chooseCut(effect){
  const idx=Number($('cutScene').value);
  if(!Number.isInteger(idx)||idx<1||idx>=state.scenes.length)return;
  if(!CATALOG.transitions.some(([id])=>id===effect))return;
  state.selectedIndex=idx;
  state.scenes[idx].transition=effect;
  state.dirty=true;resetAck();render();
  $('cutScene').value=String(idx);refreshCut();previewCut();
 }
 function pauseFilm(){
  if(!film.active)return;
  const t=clamp((performance.now()-film.started)/1000,0,film.total);
  seek(t);
 }
 function seek(t){
  const total=filmTotal();
  if(!Number.isFinite(total)||total<=0)return;
  cancelAnimationFrame(film.raf);film.raf=0;
  film.total=total;
  film.playhead=clamp(Number(t)||0,0,Math.max(0,total-.03));
  film.started=performance.now()-film.playhead*1000;
  film.active=true;
  filmFrame(performance.now()); // paints exactly one frame before pausing
  cancelAnimationFrame(film.raf);film.raf=0;
  film.active=false;film.paused=true;
  $('previewVideo').pause();$('nextVideo').pause();
  $('playFilm').textContent='▶ Продолжить';
  $('filmNow').textContent+=' · пауза';
  $('filmSeek').value=String(film.playhead);
  if(film.index>=0){
   state.selectedIndex=film.index;
   // Do not re-render media; only update the selection indication.
   renderSceneList();
  }
 }
 function init(){
  for(const kind of ['title','subtitle']){
   const target=$(kind==='title'?'frameTitle':'frameSubtitle');
   target.addEventListener('pointerdown',e=>begin(e,kind));
   target.addEventListener('pointermove',e=>drag(e,kind));
   target.addEventListener('pointerup',finish);
   target.addEventListener('pointercancel',finish);
   target.addEventListener('click',()=>select(kind));
   target.addEventListener('keydown',e=>{
    const arrows={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
    if(!arrows[e.key])return;
    e.preventDefault();
    if(film.active||film.paused)stopFilm();
    select(kind);move(...arrows[e.key],e.shiftKey?5:1);
   });
  }
  for(const button of $$('[data-edit-layer]'))button.addEventListener('click',()=>select(button.dataset.editLayer));
  $('showSafeFrame').addEventListener('change',e=>{layer.safe=e.target.checked;$('safeFrame').hidden=!layer.safe;});
  for(const [id,key] of [['overlayX','x'],['overlayY','y'],['overlayScale','scale']])
   $(id).addEventListener('input',e=>edit(layer.kind,{[key]:Number(e.target.value)}));
  const directions={overlayUp:[0,-1],overlayDown:[0,1],overlayLeft:[-1,0],overlayRight:[1,0]};
  for(const [id,[dx,dy]] of Object.entries(directions))$(id).addEventListener('click',()=>move(dx,dy));
  $('resetOverlay').addEventListener('click',()=>edit(layer.kind,{...defaults[layer.kind]}));
  $('downloadVisual').addEventListener('click',saveDraft);
  $('cutScene').addEventListener('change',refreshCut);
  for(const button of $$('[data-cut-effect]'))button.addEventListener('click',()=>chooseCut(button.dataset.cutEffect));
  $('previewCut').addEventListener('click',previewCut);
  $('filmSeek').addEventListener('input',e=>{clearTimeout(cutStopTimer);seek(Number(e.target.value));});
  window.addEventListener('pagehide',()=>clearTimeout(cutStopTimer));
  refresh(current());populateCuts();
 }
 globalThis.MotionLabVisual={get,dirty,changed,render:refresh,renderStage:renderLayout,populateCuts,pauseFilm,init,seek,saveDraft};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
