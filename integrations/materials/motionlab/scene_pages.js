'use strict';
/* Page-like views stay inside the same browser document so private File API blobs,
 * consent state and the original Montage bridge are not lost on navigation.
 * Pages are user-visible route hashes, not independent Wix uploads. */
(() => {
 const root=()=>document.getElementById('overviewWorkspace');
 const detail=()=>document.getElementById('detailView');
 const $=id=>document.getElementById(id);
 // Exactly one preview player: move the real DOM node between overview and
 // focused editor so local browser-only video Blob URLs and playhead survive.
 const scenePanel=()=>document.querySelector('.preview-panel');
 function placePreview(inDetail){
  const panel=scenePanel();
  const destination=inDetail?$('detailSlot'):root();
  if(panel&&panel.parentElement!==destination)destination.appendChild(panel);
 }
 let kind='overview',activeIndex=0,rerendering=false;
 const fmt=i=>String(i+1).padStart(2,'0');
 function thumb(scene) {
  const source=previewFor(scene);
  return source?.poster||(source?.type==='image'?source.url:scenePhoto(scene));
 }
 function route(view,index) {
  if(view==='style')return '#style';
  if(view==='scene'||view==='cut')return '#'+view+'/'+index;
  return '#overview';
 }
 function goto(view,index) {
  const dest=route(view,index);
  if(location.hash===dest)show();else location.hash=dest;
 }
 function parse(){
  const hash=decodeURIComponent(location.hash||'#overview');
  if(hash==='#style')return {view:'style',index:0};
  const match=/^#(scene|cut)\/(\d+)$/.exec(hash);
  if(match){
   const index=Number(match[2]),view=match[1];
   const valid=view==='scene'?index>=0&&index<state.scenes.length:index>=1&&index<state.scenes.length;
   if(valid)return {view,index};
  }
  return {view:'overview',index:0};
 }
 function refreshCutCards(index){
  const before=state.scenes[index-1],after=state.scenes[index];
  if(!before||!after)return;
  $('cutHeading').textContent='Переход '+fmt(index-1)+' → '+fmt(index);
  $('cutFromImage').src=thumb(before);$('cutToImage').src=thumb(after);
  $('cutFromLabel').textContent=fmt(index-1)+' / '+before.name;
  $('cutToLabel').textContent=fmt(index)+' / '+after.name;
  const cards=$('allTransitions');cards.replaceChildren();
  for(const [id,name] of CATALOG.transitions){
   const btn=document.createElement('button');btn.type='button';btn.dataset.transitionId=id;
   btn.textContent=name;
   const selected=after.transition===id;
   btn.classList.toggle('selected',selected);
   btn.setAttribute('aria-pressed',String(selected));
   btn.addEventListener('click',()=>{
    if(state.scenes[index]!==after)return;
    if(after.transition!==id){
     after.transition=id;state.dirty=true;state.selectedIndex=index;resetAck();render();
    }
    // Populate first, then select the edited boundary once before previewing.
    globalThis.MotionLabVisual?.populateCuts();
    $('cutScene').value=String(index);
    $('previewCut').click();
   });
   cards.append(btn);
  }
  globalThis.MotionLabVisual?.populateCuts();
  $('cutScene').value=String(index);
 }
 function refreshTheme(){
  const editor=globalThis.MotionLabVisual;
  if(!editor?.theme)return;
  for(const kind of ['title','subtitle']){
   const token=kind==='title'?'Title':'Subtitle',t=editor.theme(kind);
   $('theme'+token+'Font').value=t.family;
   $('theme'+token+'Color').value=t.color;
   $('theme'+token+'Size').value=String(t.size);
   $('theme'+token+'SizeOut').textContent=t.size+'%';
  }
  const first=state.scenes[0];
  if(first){
   $('globalSubtitleStyle').value=first.subtitleStyle;
   $('globalSubtitleMotion').value=first.wordMotion;
  }
 }
 function syncSceneTypography(){
  const editor=globalThis.MotionLabVisual,s=state.scenes[state.selectedIndex];if(!s||!editor?.typography)return;
  const selected=editor.selectedKind(),current=editor.typography(s,selected);
  $('sceneFont').value=current.family;$('sceneFontColor').value=current.color;
  $('scopeState').textContent=editor.isOverride(s,selected)?
   'В этой сцене есть индивидуальное оформление '+(selected==='title'?'титра.':'субтитров.'):
   'Элемент использует единый стиль всего ролика.';
 }
 function show(){
  const result=parse();kind=result.view;activeIndex=result.index;
  const editing=kind!=='overview';
  document.body.classList.toggle('detail-open',editing);
  // Restore the full film player on the storyboard, not just in an editor.
  // Reparent before showing either view so the player is never left hidden.
  stopFilm(false);
  placePreview(editing);
  detail().hidden=!editing;root().hidden=editing;
  if(!editing){
   // Overview has the scene list on the left and the whole-montage preview
   // on the right, just as it did before the dedicated page navigation.
   renderEditor();
   return;
  }
  state.selectedIndex=kind==='cut'?Math.max(1,activeIndex):kind==='style'?0:activeIndex;
  renderEditor();renderSceneList();
  detail().classList.remove('mode-scene','mode-cut','mode-style');
  detail().classList.add('mode-'+kind);
  $('sceneScopePanel').hidden=kind!=='scene';
  $('themePanel').hidden=kind!=='style';
  $('cutPanel').hidden=kind!=='cut';
  $('detailKicker').textContent=kind==='scene'?'РЕДАКТОР ОДНОЙ СЦЕНЫ':kind==='cut'?'РЕДАКТОР ПЕРЕХОДА':'СТИЛЬ ВСЕГО РОЛИКА';
  const s=state.scenes[state.selectedIndex];
  $('detailHeading').textContent=kind==='scene'?fmt(state.selectedIndex)+' / '+s.name:
   kind==='cut'?'Монтажный стык '+fmt(activeIndex-1)+' → '+fmt(activeIndex):'Общее оформление ролика';
  $('detailDescription').textContent=kind==='scene'?'Изменения действуют только в выбранной сцене, если не нажать «Для всех».':
   kind==='cut'?'Меняйте только переход между этими двумя сценами.':'Единые шрифты и цвета применяются во всех сценах без индивидуального исключения.';
  $('detailGlobalStyle').hidden=kind==='style';
  $('detailSceneNavigation').hidden=kind!=='scene';
  $('previousScene').disabled=kind!=='scene'||activeIndex<=0;
  $('nextScene').disabled=kind!=='scene'||activeIndex>=state.scenes.length-1;
  if(kind==='cut')refreshCutCards(activeIndex);
  if(kind==='style')refreshTheme();
  if(kind==='scene')syncSceneTypography();
  window.scrollTo({top:0,behavior:'instant'});
 }
 function init(){
  const aside=document.querySelector('#overviewWorkspace .preview-panel');
  if(!aside)return;
  // Do NOT detach the preview at startup: the user must see it immediately.
  root().classList.remove('overview-only');
  $('backToStoryboard').addEventListener('click',()=>goto('overview',0));
  $('editGlobalTheme').addEventListener('click',()=>goto('style',0));
  $('detailGlobalStyle').addEventListener('click',()=>goto('style',0));
  $('previousScene').addEventListener('click',()=>{if(kind==='scene'&&activeIndex>0)goto('scene',activeIndex-1);});
  $('nextScene').addEventListener('click',()=>{if(kind==='scene'&&activeIndex+1<state.scenes.length)goto('scene',activeIndex+1);});
  const sceneList=$('sceneList');
  sceneList.addEventListener('click',event=>{
   const scene=event.target.closest('[data-edit-scene]');
   const cut=event.target.closest('[data-edit-cut]');
   if(scene){event.preventDefault();goto('scene',Number(scene.dataset.editScene));}
   else if(cut){event.preventDefault();goto('cut',Number(cut.dataset.editCut));}
  });
  const editor=globalThis.MotionLabVisual;
  if(editor){
   $('applyFontChanges').addEventListener('click',()=>{
    const scope=$('fontApplyScope').value,kind=editor.selectedKind();
    const changes={family:$('sceneFont').value,color:$('sceneFontColor').value};
    if(scope==='all')editor.applyTypographyAll(kind,changes);
    else editor.setSceneTypography(kind,changes);
    syncSceneTypography();
   });
   $('applyLayoutAll').addEventListener('click',()=>{
    editor.applyLayoutToAll(editor.selectedKind());
    syncSceneTypography();
   });
   $('inheritLayout').addEventListener('click',()=>editor.inheritLayout(editor.selectedKind()));
   $('inheritFont').addEventListener('click',()=>{editor.inheritTypography(editor.selectedKind());syncSceneTypography();});
   for(const token of ['Title','Subtitle']){
    const kind=token.toLowerCase();
    const handler=()=>editor.setTheme(kind,{
     family:$('theme'+token+'Font').value,
     color:$('theme'+token+'Color').value,
     size:Number($('theme'+token+'Size').value)
    });
    for(const suffix of ['Font','Color','Size'])$('theme'+token+suffix).addEventListener('change',()=>{handler();refreshTheme();});
   }
   $('resetTheme').addEventListener('click',()=>{editor.resetTheme();refreshTheme();});
  }
  for(const [id,prop] of [['globalSubtitleStyle','subtitleStyle'],['globalSubtitleMotion','wordMotion']]){
   const sel=$(id),catalog=prop==='subtitleStyle'?CATALOG.subtitle:CATALOG.motion;
   sel.replaceChildren(...catalog.map(([v,label])=>{const o=document.createElement('option');o.value=v;o.textContent=label;return o;}));
   sel.addEventListener('change',()=>{
    for(const s of state.scenes)s[prop]=sel.value;
    state.dirty=true;resetAck();render();refreshTheme();
   });
  }
  window.addEventListener('hashchange',show);
  // Deep links remain a visual navigator only. Real A2E local files stay attached
  // to scene IDs in the live document and are not exposed through the URL.
  show();
 }
 globalThis.MotionLabPages={
  openScene:index=>goto('scene',index),
  openCut:index=>goto('cut',index),
  openStyle:()=>goto('style',0),
  sync:()=>{if(kind!=='overview'&&!rerendering){rerendering=true;try{
   if(kind==='cut')refreshCutCards(activeIndex);
   if(kind==='scene')syncSceneTypography();
  }finally{rerendering=false;}}},
  syncSceneTypography
 };
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
