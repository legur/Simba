'use strict';
/* Motion Lab storyboard / planning only. Inbound data never triggers media generation.
 * Host bridge: SIMBA_MOTIONLAB_READY -> SIMBA_MOTIONLAB_START ->
 * SIMBA_MOTIONLAB_SELECTION -> SIMBA_MOTIONLAB_ACK. ACK is mandatory for delivery.
 */
const $ = id => document.getElementById(id);
const LIMIT = 24;
const CATALOG = {
  camera: [
    ['cinematic-zoom','Плавное приближение'],['dolly-zoom','Dolly Zoom / имитация'],['orbit','Orbit / имитация'],['focus-pull','Фокус'],
    ['pan','Панорама'],['tilt','Вертикальный проезд'],['parallax','Параллакс'],['push-through','Проезд вперед'],
    ['roll','Поворот'],['float','Плавное парение'],['reveal','Открытие сцены'],['speed-ramp','Ускорение']
  ],
  transitions: [
    ['crossfade','Растворение'],['push','Сдвиг'],['zoom','Zoom'],['whip','Whip Pan'],['circle','Круг'],['diagonal','Диагональ'],
    ['flash','Вспышка'],['blur','Размытие'],['flip','3D разворот'],['parallax','Параллакс'],['shutter','Шторки'],
    ['glitch','Glitch'],['split','Разделение экрана'],['rotate','Поворот'],['tiles','Мозаика'],['portal','Портал'],
    ['textmask','Через текст'],['lightleak','Солнечный блик'],['speedramp','Ускорение'],['particles','Частицы'],['ripple','Рябь'],
    ['map','Маршрут'],['postcard','Открытки'],['filmstrip','Кинопленка'],['pagecurl','Страница'],['luma','Через свет'],
    ['foreground','Передний план'],['mask','Маска'],['morph','Морфинг'],['match','Совпадение кадров']
  ],
  title: [
    ['none','Без титра'],['fade-rise','Появление снизу'],['soft-zoom','Плавный зум'],['blur-focus','Из размытия'],
    ['mask-up','Снизу через маску'],['light-sweep','Световой акцент'],['slide-left','Выезд справа'],['bounce-pop','Пружинное появление'],
    ['punch-zoom','Ударный масштаб'],['rotate-in','С поворотом'],['word-cascade','По словам'],['counter','Счетчик'],
    ['date-flip','Перелистывание дат'],['line-draw','Подчеркивание'],['badge-reveal','Плашка'],['letter-wave','Волна букв']
  ],
  subtitle: [
    ['none','Без субтитров'],['clean','Clean White'],['soft-shadow','Soft Shadow'],['capsule','Dark Capsule'],['bar','Solid Bar'],
    ['outline','Outline Text'],['two-line','Editorial Left'],['cinema','Cinematic Caps'],['letterbox','Letterbox'],
    ['editorial','Editorial Serif'],['spotlight','Spotlight Word'],['glow','Soft Glow'],['price-tag','Price Tag'],
    ['offer-pill','Offer Pill'],['gold-card','Gold Card'],['gradient-bar','Gradient Bar'],['countdown','Limited Offer'],
    ['word-focus','Word Focus'],['karaoke','Karaoke Block'],['pop','Active Word Pop'],['marker','Highlight Marker'],
    ['luxury','Luxury Gold'],['glass','Frosted Glass'],['neon','Neon Travel'],['travel-stamp','Travel Stamp']
  ],
  motion: [
    ['karaoke','Подсветка слов'],['active-pop','Пульс слова'],['caption-swap','Смена групп'],
    ['highlight-strip','Подвижная плашка'],['word-reveal','Слова по одному']
  ]
};
const IMAGES = {
 mountains: 'https://static.wixstatic.com/media/7fd7b8_b53b4bdba4c14271a663450044559b09~mv2.jpg',
 city: 'https://static.wixstatic.com/media/7fd7b8_e8133d694a8f4f5a82b665901e9e41f4~mv2.jpg',
 sea: 'https://static.wixstatic.com/media/7fd7b8_7b6a1a4a5ae14b1d96e6b79750665aac~mv2.jpg',
 coast: 'https://static.wixstatic.com/media/7fd7b8_ac85605a20f74c278e350dede74234a2~mv2.jpg'
};
const PRESETS = Object.freeze([
 {id:1,name:'Элегантный',tag:'СПОКОЙНЫЙ',desc:'Плавная камера, деликатные титры и мягкие переходы.',camera:'cinematic-zoom',transition:'crossfade',titleFx:'fade-rise',subtitleStyle:'clean',wordMotion:'karaoke',intensity:30},
 {id:2,name:'Динамичный',tag:'ЭНЕРГИЧНЫЙ',desc:'Проезды, ритм и крупные акценты в важных сценах.',camera:'push-through',transition:'whip',titleFx:'punch-zoom',subtitleStyle:'outline',wordMotion:'active-pop',intensity:70},
 {id:3,name:'Премиальный',tag:'АТМОСФЕРНЫЙ',desc:'Параллакс, свет и выдержанное золотое оформление.',camera:'float',transition:'lightleak',titleFx:'light-sweep',subtitleStyle:'luxury',wordMotion:'highlight-strip',intensity:35}
]);
const DEMO = [
 ['Вступление / атмосфера','Новый год в Баварии','Зимняя сказка начинается здесь','mountains'],
 ['Город / улицы','Мюнхен','Праздничный Мюнхен','city'],
 ['Архитектура / детали','Старинные площади','Города с историей','city'],
 ['Маршрут / пейзаж','Баварские Альпы','Пейзажи и приключения','mountains'],
 ['Кульминация','Праздничная атмосфера','Волшебство зимней Европы','coast'],
 ['Финал / приглашение','Bon Tours','Выбирайте путешествие','sea']
];
const known = (kind,value) => CATALOG[kind].some(([id])=>id===value);
const clamp = (x,min,max) => Math.min(max,Math.max(min,x));
const safeText = (s,max=140) => typeof s==='string'?s.slice(0,max):'';
const esc = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nameFor = (type,id)=> CATALOG[type].find(e=>e[0]===id)?.[1]||id;
const state = {project:null, request:null, scenes:[],selectedIndex:0,selectedOption:1,concepts:PRESETS.map(x=>({...x})),bridge:null,dirty:false,sending:false,lastAck:null,confirmed:false};
// Actual make_video.py capability IDs. The 12 demonstration camera IDs and
// title transitions are not the same as production renderer options.
const RENDER_MOVES = new Set(['none','hold','push','pull','pan-left','pan-right','rise']);
const RENDER_TRANSITIONS = new Set(CATALOG.transitions.map(x=>x[0]));
const RENDER_STYLES = new Set(CATALOG.subtitle.filter(x=>x[0]!=='none').map(x=>x[0]));
const RENDER_WORD_MOTIONS = new Set(CATALOG.motion.map(x=>x[0]));
function rendererIssues(scenes){
 const issues=[];
 scenes.forEach((s,i)=>{
  if(!RENDER_MOVES.has(s.camera))issues.push('Сцена '+(i+1)+': камера — только предпросмотр');
  if(s.title)issues.push('Сцена '+(i+1)+': анимация титра пока не поддержана в MP4');
  if(i>0&&!RENDER_TRANSITIONS.has(s.transition))issues.push('Сцена '+(i+1)+': переход не поддержан');
  if(!RENDER_STYLES.has(s.subtitleStyle))issues.push('Сцена '+(i+1)+': стиль субтитров не поддержан');
  if(!RENDER_WORD_MOTIONS.has(s.wordMotion))issues.push('Сцена '+(i+1)+': анимация слов не поддержана');
 });
 if(new Set(scenes.map(s=>s.subtitleStyle+'|'+s.wordMotion)).size>1)issues.push('Рендерер допускает только один стиль субтитров на весь ролик');
 if(scenes.length>8)issues.push('Рендерер сейчас ограничен восемью сценами');
 return issues;
}
// Local previews bind to scene + approved asset ID and never enter returned JSON.
const localPreviews=new Map();
function clearPreviews(){
 for(const p of localPreviews.values())URL.revokeObjectURL(p.url);
 localPreviews.clear();const v=$('previewVideo');if(v){v.pause();v.removeAttribute('src');}
}
function previewFor(s){const p=localPreviews.get(s.id);return p&&p.assetId===s.asset?p:null;}
async function localFileChosen(file){
 if(!file)return;const scene=state.scenes[state.selectedIndex];if(!scene)return;
 const ext=file.name.toLowerCase().split('.').pop();
 const type=['mp4','mov','m4v','webm'].includes(ext)?'video':['jpg','jpeg','png','webp'].includes(ext)?'image':null;
 if(!type||file.size<1||file.size>(type==='video'?200:30)*1024*1024)throw Error('Разрешены JPG/PNG/WebP до 30 МБ и MP4/MOV/WebM до 200 МБ');
 const expected=scene.media||null;
 if(expected?.kind&&expected.kind!==type)throw Error('Тип файла не совпадает с утвержденным');
 const url=URL.createObjectURL(file);let added=false;
 try{
  let shaVerified=false,duration=null;
  if(expected?.asset_sha256){
   if(!globalThis.crypto?.subtle)throw Error('Для SHA-256 нужен защищенный HTTPS');
   const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))).map(n=>n.toString(16).padStart(2,'0')).join('');
   if(hash!==expected.asset_sha256.toLowerCase())throw Error('SHA-256 локального файла отличается от задания');
   shaVerified=true;
  }
  if(type==='video'){
   duration=await new Promise((ok,bad)=>{
    const v=document.createElement('video');v.preload='metadata';v.muted=true;const timer=setTimeout(()=>bad(Error('Метаданные видео не загрузились')),9000);
    v.onloadedmetadata=()=>{clearTimeout(timer);ok(v.duration);v.removeAttribute('src');v.load();};
    v.onerror=()=>{clearTimeout(timer);bad(Error('Видеофайл не читается браузером'));};v.src=url;
   });
   if(!Number.isFinite(duration)||duration<=0)throw Error('Нет правильной длительности');
   if(expected?.duration_s&&Math.abs(expected.duration_s-duration)>.45)throw Error('Длительность отличается от утвержденного ассета');
  }
  if(!state.scenes.includes(scene)||state.scenes[state.selectedIndex]!==scene)throw Error('Сцена изменилась: выберите файл снова');
  const old=localPreviews.get(scene.id);if(old)URL.revokeObjectURL(old.url);
  localPreviews.set(scene.id,{url,assetId:scene.asset,type,duration,shaVerified});added=true;
  renderEditor();say(shaVerified?'Локальный файл совпал по SHA-256':'Локальный файл открыт. SHA-256 не подтвержден');
 }finally{if(!added)URL.revokeObjectURL(url);}
}
let toastTimer, previewTimers=[], pendingAckTimer;
function say(message){const el=$('toast');el.textContent=message;el.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),2500)}
function choicesFromPreset(id){const p=state.concepts.find(v=>v.id===id)||state.concepts[0];state.scenes=state.scenes.map((s,i)=>({...s,camera:p.camera,transition:i===0?'none':p.transition,titleFx:p.titleFx,subtitleStyle:p.subtitleStyle,wordMotion:p.wordMotion,intensity:p.intensity}));state.selectedOption=id;state.dirty=true;resetAck();render();}
function makeScene(row,index,chosenPreset=PRESETS[0]){
 const source = row && typeof row==='object' ? row : {};
 const image=Object.prototype.hasOwnProperty.call(IMAGES,source.image)?source.image:['mountains','city','sea','city','coast','mountains'][index%6];
 const src={
   id:safeText(source.scene_id||source.id||`scene-${String(index+1).padStart(2,'0')}`,64),
   name:safeText(source.name||DEMO[index%DEMO.length][0],90),
   duration:clamp(Number(source.duration_s||source.seconds||3)||3,1,20),
   image,
   asset:safeText(source.asset_id||source.asset_ref||'',240),
   // Optional read-only preview metadata; never exported in selection/v1.
   media:source.media&&typeof source.media==='object'&&!Array.isArray(source.media)?{
    kind:['image','video'].includes(source.media.kind)?source.media.kind:null,
    asset_sha256:typeof source.media.asset_sha256==='string'&&/^[0-9a-f]{64}$/i.test(source.media.asset_sha256)?source.media.asset_sha256.toLowerCase():null,
    duration_s:typeof source.media.duration_s==='number'&&Number.isFinite(source.media.duration_s)&&source.media.duration_s>0?source.media.duration_s:null
   }:null,
   previewUrl:(typeof source.preview_url==='string' && /^https:\/\//i.test(source.preview_url) && source.preview_url.length<700)?source.preview_url:null,
   title:safeText(source.title_text??source.title??DEMO[index%DEMO.length][1],140),
   subtitle:safeText(source.subtitle_preview??source.subtitle??DEMO[index%DEMO.length][2],300),
   camera:known('camera',source.camera)?source.camera:chosenPreset.camera,
   transition:index===0?'none':known('transitions',source.transition)?source.transition:chosenPreset.transition,
   titleFx:known('title',source.title_effect)?source.title_effect:chosenPreset.titleFx,
   subtitleStyle:known('subtitle',source.subtitle_style)?source.subtitle_style:chosenPreset.subtitleStyle,
   wordMotion:known('motion',source.subtitle_motion)?source.subtitle_motion:chosenPreset.wordMotion,
   intensity:clamp(Number(source.intensity_percent??chosenPreset.intensity),0,100)
 };
 return src;
}
function prepareDemo(){stopFilm(false);clearPreviews();state.confirmed=false;state.project=null;state.request=null;state.bridge=null;state.concepts=PRESETS.map(x=>({...x}));state.selectedOption=1;state.scenes=DEMO.map((x,i)=>makeScene({name:x[0],title_text:x[1],subtitle_preview:x[2],image:x[3]},i));state.selectedIndex=0;state.dirty=false;state.lastAck=null;state.sending=false;clearTimeout(pendingAckTimer);setConnection('demo');render();}
function populateSelect(id,items){$(id).replaceChildren(...items.map(([value,label])=>{const o=document.createElement('option');o.value=value;o.textContent=label;return o}));}
function titleChoice(index){if(film.active)stopFilm(false);let s=state.scenes[index];state.selectedIndex=index;resetPreview();render();}
function renderConcepts(){ $('conceptList').innerHTML=state.concepts.map(c=>`<button class="concept ${state.selectedOption===c.id?'selected':''}" data-option="${c.id}" aria-pressed="${state.selectedOption===c.id}"><span class="number">ВАРИАНТ 0${c.id} / ${esc(c.tag||'')}</span><strong>${esc(c.name)}</strong><p>${esc(c.desc)}</p><span class="concept-support">${!RENDER_MOVES.has(c.camera)||c.titleFx!=='none'?'Есть эффекты только для предпросмотра':'Нужна проверка рендерера'}</span><span class="pick">${state.selectedOption===c.id?'✓ Выбран':'Выбрать вариант'} →</span></button>`).join(''); }
function scenePhoto(scene){return scene.previewUrl||IMAGES[scene.image]||IMAGES.mountains;}
function renderSceneList(){ $('sceneCount').textContent=String(state.scenes.length);$('metricScenes').textContent=String(state.scenes.length);$('sceneList').innerHTML=state.scenes.map((s,i)=>`<div role="listitem" class="scene-card ${i===state.selectedIndex?'selected':''}"><img class="thumb" src="${esc(scenePhoto(s))}" alt="" loading="lazy" referrerpolicy="no-referrer"><div class="scene-info"><button type="button" class="scene-open" data-open="${i}" aria-label="Редактировать сцену ${i+1}"><strong>${String(i+1).padStart(2,'0')} / ${esc(s.name)}</strong><p>${s.duration.toFixed(1)} с · ${esc(nameFor('camera',s.camera))}</p></button><div class="chips"><span class="tag">${esc(i===0?'Без входа':nameFor('transitions',s.transition))}</span><span class="tag">${esc(nameFor('title',s.titleFx))}</span></div></div><div class="scene-control"><button data-up="${i}" type="button" title="Выше" ${i===0?'disabled':''}>↑</button><button data-down="${i}" type="button" title="Ниже" ${i===state.scenes.length-1?'disabled':''}>↓</button><button data-remove="${i}" type="button" title="Удалить" ${state.scenes.length<=1||state.request?'disabled':''}>×</button></div></div>`).join(''); }
function setField(id,value){const n=$(id);if(n)n.value=value;}
function renderEditor(){const s=state.scenes[state.selectedIndex];if(!s)return;
 $('previewHeading').textContent='Сцена '+String(state.selectedIndex+1).padStart(2,'0');$('activeCounter').textContent=`${String(state.selectedIndex+1).padStart(2,'0')} / ${String(state.scenes.length).padStart(2,'0')}`;
 setField('sceneName',s.name);setField('sceneDuration',s.duration);setField('sceneImage',s.image);setField('sceneAsset',s.asset);setField('sceneCamera',s.camera);setField('sceneTransition',s.transition);setField('sceneTitleFx',s.titleFx);setField('sceneSubtitleStyle',s.subtitleStyle);setField('sceneWordMotion',s.wordMotion);setField('sceneIntensity',s.intensity);setField('sceneTitle',s.title);setField('sceneSubtitle',s.subtitle);
 $('intensityValue').textContent=s.intensity+'%';$('sceneTransition').disabled=state.selectedIndex===0;
 const lock=Boolean(state.request);
 ['sceneName','sceneDuration','sceneAsset','sceneTitle','sceneSubtitle'].forEach(id=>{$(id).readOnly=lock;});
 $('sceneImage').disabled=lock;$('approvedSourceLock').hidden=!lock;
 const issues=rendererIssues(state.scenes);
 $('renderSupport').classList.toggle('ready',issues.length===0);
 $('renderSupport').textContent=issues.length?'ЭФФЕКТЫ ТОЛЬКО ДЛЯ ПРЕДПРОСМОТРА: '+issues.slice(0,4).join('; ')+(issues.length>4?' и еще '+(issues.length-4):'')+'. Нельзя передавать на автоматический рендер.':'Для этих параметров нет известных блокировок; приемник Montage все равно выполняет техническую проверку.';
 $('addScene').disabled=Boolean(state.request);
 const p=$('previewPhoto'),v=$('previewVideo'),local=previewFor(s);
 if(local?.type==='video'){
  p.hidden=true;v.hidden=false;if(v.src!==local.url){v.pause();v.src=local.url;v.load();}
 }else{
  v.pause();v.hidden=true;p.hidden=false;p.src=local?.type==='image'?local.url:scenePhoto(s);
 }
 $('mediaProvenance').textContent=local?local.shaVerified?'Локальная копия сверена по SHA-256. Финальная проверка остается у Montage.':'Локальный предпросмотр. SHA-256 не подтвержден. Файл не загружен в Wix.':'Демонстрационное изображение. Реальный исходник не проверен.';
 $('localMediaStatus').textContent=local?'Локальный '+(local.type==='video'?'MP4/видео':'кадр')+' · '+(local.duration?local.duration.toFixed(2)+' с · ':'')+(local.shaVerified?'SHA совпадает':'SHA не подтвержден'):'Можно выбрать локальную копию '+(s.asset||s.id)+' для предпросмотра. Она останется в браузере.';
 $('localMediaStatus').classList.toggle('verified',Boolean(local?.shaVerified));
 $('frameTitle').textContent=s.titleFx==='none'?'':s.title;$('frameSubtitle').textContent=s.subtitleStyle==='none'?'':s.subtitle;
 $('frameSubtitle').className='frame-subtitle '+(s.subtitleStyle==='luxury'||s.subtitleStyle==='gold-card'?'gold':'');
}
function renderSummary(){const total=state.scenes.reduce((t,s)=>t+s.duration,0);$('summary').innerHTML=[`Сцен: ${state.scenes.length}`,`Длительность: ${total.toFixed(1)} с`,`Вариант: ${state.selectedOption}`,state.project?`Проект: ${esc(state.project.id)}`:'Демо без проекта'].map(s=>`<span>${s}</span>`).join('');
 let warns=[];
 if(!state.request) warns.push('Только предпросмотр. Для передачи автоматической среде нужно получить задание с ID и fingerprint.');
 if(state.scenes.some(s=>!s.name.trim()))warns.push('У каждой сцены должно быть название.');
 if(state.scenes.some(s=>s.image==='custom'&&!s.asset.trim()))warns.push('Для собственных кадров нужен ID исходного материала.');
 if(state.bridge && state.scenes.some(s=>!s.asset.trim()))warns.push('Для передачи агенту нужен ID ассета каждой сцены.');
 if(total>60)warns.push('План превышает 60 секунд: перед монтажом потребуется уточнение длительности.');
 const unsupported=rendererIssues(state.scenes);
 if(unsupported.length)warns.push('Есть '+unsupported.length+' несовместимых с текущим MP4 эффектов; сохраните черновик или выберите поддерживаемый вариант.');
 const v=$('validation');v.textContent=warns.length?warns.join(' '):'Структура готова. Возврат выбора не запускает рендер, TTS, A2E или публикацию.';v.classList.toggle('warning',warns.length>0);
 $('sendToAgent').disabled=!(state.bridge&&state.request)||!state.confirmed||state.sending||unsupported.length>0||warns.some(x=>/название|ID исходного|ID ассета/.test(x));
 const approval=$('approvalStatus');if(approval){approval.textContent=state.confirmed?'Вариант утвержден вами, но не передан монтажеру':'Еще не утверждено';approval.classList.toggle('approved',state.confirmed);}
 const badge=$('handoffBadge');badge.textContent=state.lastAck?'ПРИНЯТО АГЕНТОМ':state.sending?'ОЖИДАНИЕ ACK':state.bridge?'ПОДКЛЮЧЕНО':'ЧЕРНОВИК';
 $('deliveryHint').textContent=state.lastAck?`Принято средой. Квитанция: ${state.lastAck}`:state.sending?'Решение отправлено. Подтверждение принимающей стороны пока не получено.':state.bridge?'Канал ответа подключен. После выбора нажмите «Передать выбор агенту».':'Канала ответа нет. Экспортируйте JSON, чтобы продолжить работу в агенте.';
}
function render(){renderConcepts();renderSceneList();renderEditor();renderSummary();}
function updateKey(key,value){if(state.request&&['name','duration','image','asset','title','subtitle'].includes(key))return;const s=state.scenes[state.selectedIndex];s[key]=value;state.dirty=true;resetAck();renderSceneList();renderSummary();if(['title','subtitle','subtitleStyle','titleFx','image'].includes(key))renderEditor();}
function editChange(id,key,fn){$(id).addEventListener('change',()=>{const v=fn?fn($(id).value):$(id).value;updateKey(key,v);});}
function liveChange(id,key){$(id).addEventListener('input',()=>{if(state.request&&['title','subtitle'].includes(key))return;const v=$(id).value;const s=state.scenes[state.selectedIndex];s[key]=v;state.dirty=true;resetAck();renderSummary();if(key==='title')$('frameTitle').textContent=v;if(key==='subtitle')$('frameSubtitle').textContent=v;});$(id).addEventListener('change',renderSceneList);}
function resetAck(){if(film.active)stopFilm();state.confirmed=false;state.sending=false;state.lastAck=null;clearTimeout(pendingAckTimer);}
// Whole-film editor review: a browser approximation on verified/locally selected assets.
// Does not generate MP4, analyze speech/music, or silently authorize Montage.
const film={active:false,raf:0,started:0,index:-1,nextIndex:-1,total:0};
function filmClock(seconds){const t=Math.max(0,Math.floor(seconds));return String(Math.floor(t/60)).padStart(2,'0')+':'+String(t%60).padStart(2,'0');}
function filmTotal(){return state.scenes.reduce((sum,s)=>sum+Number(s.duration||0),0);}
function hideNext(){
 const layer=$('montageNext'),nextVideo=$('nextVideo');
 layer.hidden=true;layer.style.opacity='0';layer.style.transform='none';layer.style.clipPath='none';layer.style.filter='none';
 nextVideo.pause();$('montageFlash').hidden=true;$('montageFlash').style.opacity='0';film.nextIndex=-1;
}
function stopFilm(restore=true,complete=false){
 cancelAnimationFrame(film.raf);film.raf=0;film.active=false;film.index=-1;film.nextIndex=-1;
 const video=$('previewVideo');if(video)video.pause();
 if($('montageNext'))hideNext();
 if($('playFilm'))$('playFilm').textContent='▶ Просмотреть весь ролик';
 if($('filmNow'))$('filmNow').textContent=complete?'Предпросмотр завершен':'Предпросмотр остановлен';
 if($('filmClock'))$('filmClock').textContent=filmClock(complete?film.total:0)+' / '+filmClock(film.total);
 if($('filmProgress'))$('filmProgress').value=complete?100:0;
 if(restore&&state.scenes.length)renderEditor();
}
function filmMedia(scene,photo,video){
 const source=previewFor(scene);
 if(source?.type==='video'){
  photo.hidden=true;video.hidden=false;
  if(video.src!==source.url){video.pause();video.src=source.url;video.load();}
 }else{
  video.pause();video.hidden=true;photo.hidden=false;
  photo.src=source?.type==='image'?source.url:scenePhoto(scene);
 }
 return Boolean(source);
}
function safePlayVideo(v,seek=0){
 if(v.hidden)return;
 const attempt=()=>{
  try{if(Number.isFinite(seek)&&seek>0&&v.readyState>0&&Number.isFinite(v.duration))v.currentTime=Math.min(seek,Math.max(0,v.duration-.1));}catch{}
  const p=v.play();if(p?.catch)p.catch(()=>{});
 };
 if(v.readyState>=1)attempt();
 else v.addEventListener('loadedmetadata',attempt,{once:true});
}
function filmEnterScene(index){
 if(index<0||index>=state.scenes.length)return;
 hideNext();
 const s=state.scenes[index],local=filmMedia(s,$('previewPhoto'),$('previewVideo'));
 $('previewPhoto').getAnimations().forEach(a=>a.cancel());
 $('previewPhoto').style.transform='none';
 if(!s.media?.kind||!local){
  $('mediaProvenance').textContent=local?'Локальная копия для предпросмотра':'Демонстрационный фон: не представлен оригинальный кадр этой сцены.';
 }else $('mediaProvenance').textContent='Локальная копия источника для предпросмотра. Полный QA выполняет Montage.';
 const carry=index>0?Math.min(.85,state.scenes[index-1].duration*.35):0;
 safePlayVideo($('previewVideo'),carry);
 $('frameTitle').textContent=s.titleFx==='none'?'':s.title;
 $('frameSubtitle').textContent=s.subtitleStyle==='none'?'':s.subtitle;
 $('frameTitle').style.opacity=s.titleFx==='none'?'0':'1';
 $('frameSubtitle').style.opacity=s.subtitleStyle==='none'?'0':'1';
 $('frameSubtitle').className='frame-subtitle '+(s.subtitleStyle==='luxury'||s.subtitleStyle==='gold-card'?'gold':'');
 $('filmNow').textContent='Сцена '+(index+1)+' / '+state.scenes.length+': '+s.name;
 const n=state.scenes.filter(scene=>!previewFor(scene)).length;
 $('filmAccuracy').textContent='Предпросмотр без отдельной озвучки и музыкального микса. '+(n?'Оригиналы не загружены для '+n+' сцен; там используются макеты. ':'')+'Сложные переходы показаны приближенно; точный MP4 создается в Montage.';
 film.index=index;
}
function filmIncoming(index){
 if(film.nextIndex===index)return;
 const s=state.scenes[index],layer=$('montageNext');
 filmMedia(s,$('nextPhoto'),$('nextVideo'));film.nextIndex=index;layer.hidden=false;
 layer.style.opacity='0';layer.style.transform='none';layer.style.clipPath='none';layer.style.filter='none';
 safePlayVideo($('nextVideo'));
}
function filmTransitionFrame(id,progress){
 const layer=$('montageNext'),flash=$('montageFlash'),p=clamp(progress,0,1);
 layer.style.transform='none';layer.style.filter='none';layer.style.clipPath='none';flash.hidden=true;flash.style.opacity='0';
 if(id==='none'){layer.style.opacity=p>=1?'1':'0';return;}
 if(id==='push'||id==='whip'){
  layer.style.opacity='1';layer.style.transform='translateX('+Math.round((1-p)*100)+'%)';
  if(id==='whip')layer.style.filter='blur('+Math.round((1-p)*7)+'px)';
 }else if(id==='zoom'){
  layer.style.opacity=String(p);layer.style.transform='scale('+(1.16-.16*p)+')';
 }else if(id==='circle'){
  layer.style.opacity='1';layer.style.clipPath='circle('+(p*78).toFixed(2)+'% at 50% 50%)';
 }else if(id==='diagonal'){
  layer.style.opacity='1';layer.style.clipPath='polygon(0 0,'+(p*200-100)+'% 0,'+(p*200)+'% 100%,0 100%)';
 }else if(id==='blur'){
  layer.style.opacity=String(p);layer.style.filter='blur('+(1-p)*12+'px)';
 }else if(id==='flash'){
  layer.style.opacity=String(p);flash.hidden=false;flash.style.opacity=String(Math.sin(Math.PI*p)*.85);
 }else{
  // Honest approximation for Canvas2D transition algorithms not simulated exactly in this browser.
  layer.style.opacity=String(p);
 }
}
function filmFrame(now){
 if(!film.active)return;
 const t=(now-film.started)/1000;
 if(t>=film.total){stopFilm(true,true);return;}
 let position=0,index=0;
 for(let i=0;i<state.scenes.length;i++){const d=state.scenes[i].duration;if(t<position+d||i===state.scenes.length-1){index=i;break;}position+=d;}
 if(index!==film.index)filmEnterScene(index);
 const length=state.scenes[index].duration,into=t-position;
 const next=index+1;
 const transition=next<state.scenes.length?state.scenes[next].transition:'none';
 const span=next<state.scenes.length&&transition!=='none'?Math.min(.9,length*.35):0;
 if(span>0&&into>=length-span){
  filmIncoming(next);filmTransitionFrame(transition,(into-(length-span))/span);
 }else if(film.nextIndex!==-1)hideNext();
 $('filmClock').textContent=filmClock(t)+' / '+filmClock(film.total);
 $('filmProgress').value=100*t/film.total;
 film.raf=requestAnimationFrame(filmFrame);
}
function startFilm(){
 if(film.active)return;
 resetPreview();
 const total=filmTotal();
 if(!Number.isFinite(total)||total<=0||!state.scenes.length){say('Нет сцен для просмотра');return;}
 film.active=true;film.index=-1;film.nextIndex=-1;film.total=total;film.started=performance.now();
 $('playFilm').textContent='■ Остановить просмотр';
 $('filmClock').textContent='00:00 / '+filmClock(total);
 film.raf=requestAnimationFrame(filmFrame);
}
function approveReview(){
 if(film.active)stopFilm();
 const error=validationError();
 if(error){say(error);return;}
 state.confirmed=true;renderSummary();
 const count=rendererIssues(state.scenes).length;
 say(count?'Монтаж визуально утвержден, но '+count+' параметров еще не поддержаны рендерером':'Вариант утвержден. Передача возможна только через подключенный Montage.');
}

function resetPreview(){previewTimers.forEach(t=>clearTimeout(t));previewTimers=[];$('previewPhoto').getAnimations().forEach(a=>a.cancel());$('frameTitle').getAnimations().forEach(a=>a.cancel());$('frameSubtitle').getAnimations().forEach(a=>a.cancel());$('previewPhoto').style.transform='scale(1.06)';const v=$('previewVideo');if(!v.hidden){v.pause();try{v.currentTime=0;}catch{}}$('frameTitle').style.opacity='1';$('frameSubtitle').style.opacity='1';}
function play(){if(film.active)stopFilm();resetPreview();const s=state.scenes[state.selectedIndex];if(matchMedia('(prefers-reduced-motion: reduce)').matches){say('Анимация ограничена настройками доступности');return;}
 const img=$('previewPhoto'),title=$('frameTitle'),sub=$('frameSubtitle');if(!$('previewVideo').hidden){const p=$('previewVideo').play();if(p?.catch)p.catch(()=>say('Локальное видео не воспроизводится'));}const amount=s.intensity/100,dur=clamp(s.duration*1000,750,5000);
 const x=s.camera==='pan'?18*amount:s.camera==='roll'?5*amount:s.camera==='float'?8*amount:s.camera==='tilt'?0:0;
 const y=s.camera==='tilt'?22*amount:s.camera==='float'?9*amount:0;
 const scale=s.camera==='push-through'?1.05+.32*amount:s.camera==='cinematic-zoom'?1.05+.18*amount:s.camera==='dolly-zoom'?1.08+.14*amount:s.camera==='speed-ramp'?1.05+.22*amount:1.08+.08*amount;
 const rotate=s.camera==='roll'?5*amount:s.camera==='orbit'?2*amount:0;
 img.animate([{transform:'translate(0,0) scale(1.06)',filter:s.camera==='focus-pull'?'blur(6px)':'none'},{transform:`translate(${x}px,${y}px) scale(${scale}) rotate(${rotate}deg)`,filter:'none'}],{duration:dur,easing:'ease-in-out',fill:'forwards'});
 if(s.titleFx!=='none')title.animate([{opacity:0,transform:s.titleFx==='slide-left'?'translateX(20px)':'translateY(16px)'},{opacity:1,transform:'translate(0,0)'}],{duration:Math.min(dur*.45,950),easing:'ease-out',fill:'forwards'});
 if(s.subtitleStyle!=='none')sub.animate([{opacity:0,transform:'translateY(10px)'},{opacity:1,transform:'translateY(0)'}],{duration:Math.min(dur*.55,1100),delay:Math.min(dur*.25,500),fill:'forwards'});
}
function reorder(i,delta){const j=i+delta;if(j<0||j>=state.scenes.length)return;const a=state.scenes;[a[i],a[j]]=[a[j],a[i]];state.selectedIndex=j;a[0].transition='none';if(a.length>1&&a[1].transition==='none')a[1].transition=state.concepts.find(p=>p.id===state.selectedOption).transition;state.dirty=true;resetAck();render();}
function addScene(){if(state.request){say('Утвержденные сцены изменяет Киностудия, не этот редактор.');return;}if(state.scenes.length>=LIMIT){say('Максимум 24 сцены');return;}const n=state.scenes.length,p=state.concepts.find(c=>c.id===state.selectedOption);const s=makeScene({name:`Сцена ${n+1}`,image:'city',title_text:'',subtitle_preview:''},n,p);state.scenes.push(s);state.selectedIndex=n;state.dirty=true;resetAck();render();}
function fromSaved(){const read=key=>{try{const v=JSON.parse(localStorage.getItem(key)||'[]');return Array.isArray(v)?v:[]}catch{return[]}};
 const camera=read('motionlab-camera-favorites-v1').filter(id=>known('camera',id)),transition=read('motionlab:favorites').filter(id=>known('transitions',id)),title=read('motionlab:text:favorites').filter(id=>known('title',id)),subtitle=read('motionlab:subtitle-combos:v2').filter(id=>typeof id==='string'&&id.includes('|'));
 const has=Boolean(camera.length||transition.length||title.length||subtitle.length);if(!has){say('В библиотеках пока нет избранных эффектов');return;}
 state.scenes.forEach((s,i)=>{if(camera.length)s.camera=camera[i%camera.length];if(transition.length&&i>0)s.transition=transition[(i-1)%transition.length];if(title.length)s.titleFx=title[i%title.length];if(subtitle.length){const [style,motion]=subtitle[i%subtitle.length].split('|');if(known('subtitle',style)&&known('motion',motion)){s.subtitleStyle=style;s.wordMotion=motion;}}});state.dirty=true;resetAck();render();say('Подборка из библиотек применена');}
function normalizeConcept(row,i){if(!row||typeof row!=='object')return null;const settings=row.settings&&typeof row.settings==='object'?row.settings:row;const def=PRESETS[i];const get=(catalog,key,fallback)=>known(catalog,settings[key])?settings[key]:fallback;
 return {id:i+1,name:safeText(row.name||def.name,60),desc:safeText(row.description||row.desc||def.desc,220),tag:safeText(row.label||def.tag,36),camera:get('camera','camera',def.camera),transition:get('transitions','transition',def.transition),titleFx:get('title','titleFx',def.titleFx),subtitleStyle:get('subtitle','subtitleStyle',def.subtitleStyle),wordMotion:get('motion','wordMotion',def.wordMotion),intensity:clamp(Number(settings.intensity??def.intensity),0,100)};
}
function parseLaunch(raw,strict){if(!raw||typeof raw!=='object'||Array.isArray(raw))throw Error('Формат задания: нужен объект JSON');
 if(raw.schema!=='bontours.motionlab.storyboard.launch/v1')throw Error('Неверная версия протокола задания');
 if(raw.stage!=='edit_choice')throw Error('Допустимый этап: edit_choice');
 const request_id=safeText(raw.request_id,90),project_id=safeText(raw.project_id,120),fp=raw.expected_input_fingerprint;
 if(!/^[A-Za-z0-9_:.\-]{4,90}$/.test(request_id))throw Error('Некорректный request_id');
 if(!/^[A-Za-z0-9_\-]{3,120}$/.test(project_id))throw Error('Некорректный project_id');
 if(!/^[0-9a-f]{64}$/i.test(fp))throw Error('Нужен 64-символьный SHA-256 expected_input_fingerprint');
 if(!Array.isArray(raw.scenes)||!raw.scenes.length||raw.scenes.length>LIMIT)throw Error('Задание должно содержать от 1 до 24 сцен');
 if(!Array.isArray(raw.options)||raw.options.length!==3)throw Error('Для этапа должны быть три режиссерских варианта');
 const concepts=raw.options.map((x,i)=>normalizeConcept(x,i));
 if(concepts.some(x=>!x||!x.name))throw Error('Неполные режиссерские варианты');
 const selected=raw.selected_option===1||raw.selected_option===2||raw.selected_option===3?raw.selected_option:1;
 const scenes=raw.scenes.map((x,i)=>makeScene(x,i,concepts[selected-1]));
 const ids=scenes.map(s=>s.id);if(ids.some(id=>!id)||new Set(ids).size!==ids.length)throw Error('scene_id должны быть уникальными');
 return {request:{id:request_id,projectId:project_id,fingerprint:fp,stage:'edit_choice'},concepts,scenes,selected};
}
function loadLaunch(raw,channel){const parsed=parseLaunch(raw,true);stopFilm(false);clearPreviews();state.confirmed=false;state.request=parsed.request;state.project={id:parsed.request.projectId};state.concepts=parsed.concepts;state.scenes=parsed.scenes;state.selectedOption=parsed.selected;state.selectedIndex=0;state.dirty=false;resetAck();state.bridge=channel||null;setConnection(channel?'connected':'offline');render();say('Задание Киностудии загружено');}
function buildResult(){const req=state.request,bridge=Boolean(state.bridge),timestamp=new Date().toISOString();return {
 schema:'bontours.motionlab.storyboard.selection/v1',request_id:req?.id||null,project_id:req?.projectId||null,stage:'edit_choice',expected_input_fingerprint:req?.fingerprint||null,
 decision:{selected_option:state.selectedOption,options_presented:3,user_selected_at:timestamp,state:bridge?'USER_SELECTED_IN_CONNECTED_SESSION':'DRAFT_NOT_DELIVERED',confirmation_scope:'EDIT_CHOICES_ONLY'},
 format:'9:16',scenes:state.scenes.map((s,i)=>({scene_id:s.id,order:i+1,name:s.name,duration_seconds:s.duration,asset_id:s.asset||null,preview_image_key:s.image,
 camera:{id:s.camera,intensity_percent:s.intensity,approximate_3d:['dolly-zoom','orbit','parallax','focus-pull','speed-ramp'].includes(s.camera)},
 transition:i===0?null:{id:s.transition,duration_ms:900},title:{effect_id:s.titleFx,display_text:s.title},subtitles:{style_id:s.subtitleStyle,word_motion_id:s.wordMotion,preview_text:s.subtitle,timing_source:'NOT_PROVIDED_IN_STORYBOARD'}})),
 provenance:{origin:'motion-lab-storyboard',mode:bridge?'embedded-bridge':'local-export',requires_trusted_agent_validation:true},
 guards:{production_state:'PREPRODUCTION',run_render:false,run_tts:false,run_a2e:false,run_paid_operations:false,auto_publish:false,preserve_approved_voice:true,preserve_approved_music:true,preserve_approved_narration:true},
 next_stage:'MONTAGE_PLANNING_REVIEW'
 };
}
function validationError(){if(filmTotal()>60)return 'Сумма длительностей сцен превышает 60 секунд';if(state.scenes.some(s=>!s.name.trim()))return 'Названия сцен не могут быть пустыми';if(state.scenes.some(s=>s.image==='custom'&&!s.asset.trim()))return 'Для своего кадра необходим ID исходного файла';if(!state.scenes.length)return 'Добавьте сцену';return null;}
function jsonDownload(){const error=validationError();if(error){say(error);return;}const obj=buildResult();const blob=new Blob([JSON.stringify(obj,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`motionlab-${obj.project_id||'demo'}-edit-choice.json`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);say('JSON сохранен');}
async function copyBrief(){const lines=[`BON TOURS / MOTION LAB — РЕЖИССЕРСКОЕ РЕШЕНИЕ`,`Проект: ${state.project?.id||'демонстрация'}`,`Вариант: ${state.selectedOption}`,`Сцен: ${state.scenes.length}`,'',...state.scenes.map((s,i)=>`${i+1}. ${s.name} (${s.duration} с): камера ${nameFor('camera',s.camera)}, переход ${i?nameFor('transitions',s.transition):'нет'}, титр ${nameFor('title',s.titleFx)}, субтитры ${nameFor('subtitle',s.subtitleStyle)} / ${nameFor('motion',s.wordMotion)}`),'','Решение только для подготовки. Рендер, TTS, A2E и публикация не разрешены.'];try{await navigator.clipboard.writeText(lines.join('\n'));say('Монтажное ТЗ скопировано')}catch{say('Копирование недоступно. Скачайте JSON')}}
function setConnection(mode){$('connLed').className='conn-led '+(mode==='connected'?'connected':'waiting');$('connectionTitle').textContent=mode==='connected'?'Агент подключен / выбор ожидается':mode==='offline'?'Задание импортировано / офлайн':'Демонстрационный режим';$('connectionText').textContent=mode==='connected'?`Сессия ${state.request?.id||''}. После выбора отправим настройки строго инициировавшей среде и дождемся ACK.`:mode==='offline'?'Задание открыто из файла. Для возврата результата скачайте JSON и передайте его агенту.':'Вы можете проверить редактор и экспортировать JSON. Для прямого возврата агент должен запустить модуль через подтвержденный канал сообщений.';renderSummary();}
function sendSelection(){if(!state.confirmed){say('Сначала утвердите выбранный монтаж');return;}const error=validationError();if(error){say(error);return;}if(!state.bridge||!state.request){say('Нет подключенного агентского канала. Используйте экспорт JSON.');return;}
 const b=state.bridge,packet=buildResult();state.sending=true;state.lastAck=null;renderSummary();try{b.source.postMessage({type:'SIMBA_MOTIONLAB_SELECTION',protocol:'bontours.motionlab.bridge/v1',payload:packet},b.origin)}catch(err){state.sending=false;renderSummary();say('Не удалось отправить. Скачайте JSON.');return;}
 pendingAckTimer=setTimeout(()=>{if(!state.sending)return;state.sending=false;renderSummary();say('Подтверждение не пришло. Используйте JSON.');},9000);
}
function goodSource(event){return event.source===window.parent && window.parent!==window || event.source===window.opener && !!window.opener;}
function expectedHostOrigin(){const param=new URLSearchParams(location.search).get('host_origin');if(!param)return null;try{const uri=new URL(param);if(uri.protocol==='https:'||uri.hostname==='localhost')return uri.origin;}catch{}return null;}
function onMessage(e){if(!goodSource(e))return;const host=expectedHostOrigin();if(host&&e.origin!==host)return;const msg=e.data;if(!msg||typeof msg!=='object'||msg.protocol!=='bontours.motionlab.bridge/v1')return;
 if(msg.type==='SIMBA_MOTIONLAB_START'){
   if(state.sending)return;
   try{loadLaunch(msg.payload,{source:e.source,origin:e.origin});e.source.postMessage({type:'SIMBA_MOTIONLAB_STARTED',protocol:'bontours.motionlab.bridge/v1',request_id:state.request.id},e.origin);}
   catch(err){e.source.postMessage({type:'SIMBA_MOTIONLAB_ERROR',protocol:'bontours.motionlab.bridge/v1',message:safeText(err.message,210)},e.origin);say('Некорректное задание: '+err.message);}
 }else if(msg.type==='SIMBA_MOTIONLAB_ACK'&&state.bridge&&e.origin===state.bridge.origin&&e.source===state.bridge.source&&state.request?.id===msg.request_id){
   clearTimeout(pendingAckTimer);state.sending=false;
   if(msg.accepted===true&&typeof msg.receipt_id==='string'&&msg.receipt_id.length>0&&msg.receipt_id.length<=160){state.lastAck=safeText(msg.receipt_id,160);say('Агент подтвердил получение выбора');}
   else say('Среда отклонила выбор. Проверьте данные или экспортируйте JSON.');renderSummary();
 }
}
function announceReady(){const target=window.parent!==window?window.parent:window.opener;const host=expectedHostOrigin();if(!target||!host)return;target.postMessage({type:'SIMBA_MOTIONLAB_READY',protocol:'bontours.motionlab.bridge/v1',capabilities:['three_edit_options','per_scene_settings','json_export','explicit_user_selection','ack_required'],module_version:'1.0'},host);}
function wire(){populateSelect('sceneCamera',CATALOG.camera);populateSelect('sceneTransition',[['none','Без перехода (первая сцена)'],...CATALOG.transitions]);populateSelect('sceneTitleFx',CATALOG.title);populateSelect('sceneSubtitleStyle',CATALOG.subtitle);populateSelect('sceneWordMotion',CATALOG.motion);
 $('conceptList').addEventListener('click',ev=>{const btn=ev.target.closest('[data-option]');if(btn)choicesFromPreset(Number(btn.dataset.option));});
 $('sceneList').addEventListener('click',ev=>{const up=ev.target.closest('[data-up]'),down=ev.target.closest('[data-down]'),rem=ev.target.closest('[data-remove]'),open=ev.target.closest('[data-open]');
 if(up){reorder(Number(up.dataset.up),-1);return;}if(down){reorder(Number(down.dataset.down),1);return;}if(rem){const i=Number(rem.dataset.remove);if(state.request||state.scenes.length===1)return;state.scenes.splice(i,1);state.selectedIndex=clamp(state.selectedIndex,0,state.scenes.length-1);state.scenes[0].transition='none';resetAck();render();return;}if(open){titleChoice(Number(open.dataset.open));return;}
 });
 $('addScene').addEventListener('click',addScene);$('applyFavorites').addEventListener('click',fromSaved);
 editChange('sceneName','name');editChange('sceneDuration','duration',v=>clamp(Number(v)||3,1,20));editChange('sceneImage','image');editChange('sceneAsset','asset');editChange('sceneCamera','camera');editChange('sceneTransition','transition');editChange('sceneTitleFx','titleFx');editChange('sceneSubtitleStyle','subtitleStyle');editChange('sceneWordMotion','wordMotion');editChange('sceneIntensity','intensity',v=>clamp(Number(v),0,100));
 $('sceneIntensity').addEventListener('input',e=>{$('intensityValue').textContent=e.target.value+'%';});liveChange('sceneTitle','title');liveChange('sceneSubtitle','subtitle');
 $('playPreview').addEventListener('click',play);$('stopPreview').addEventListener('click',resetPreview);
 $('playFilm').addEventListener('click',()=>film.active?stopFilm():startFilm());
 $('stopFilm').addEventListener('click',()=>stopFilm());
 $('approveChoice').addEventListener('click',approveReview);
 $('localSceneFile').addEventListener('change',async e=>{
  const file=e.target.files?.[0];e.target.value='';if(!file)return;
  $('localMediaStatus').textContent='Проверка файла в браузере...';
  try{await localFileChosen(file);}catch(error){$('localMediaStatus').textContent='Не принят: '+error.message;say(error.message);}
 });
 $('resetDemo').addEventListener('click',()=>{if(state.bridge){say('Активное задание агента. Демо не заменяет его.');return;}prepareDemo();say('Открыт демонстрационный проект');});
 $('requestFile').addEventListener('change',async e=>{const file=e.target.files?.[0];e.target.value='';if(!file)return;if(file.size>300_000){say('Максимальный размер задания 300 КБ');return;}try{const source=JSON.parse(await file.text());if(state.bridge){say('Задание от агента активно. Импорт недоступен.');return;}loadLaunch(source,null);}catch(err){say('Ошибка JSON: '+err.message);}});
 $('downloadJson').addEventListener('click',jsonDownload);$('copyBrief').addEventListener('click',copyBrief);$('sendToAgent').addEventListener('click',sendSelection);
 window.addEventListener('message',onMessage);window.addEventListener('pagehide',()=>{clearTimeout(pendingAckTimer);stopFilm(false);clearPreviews();});prepareDemo();
 // Creative templates apply ONLY to the local demo. Agent launch with three options remains authoritative.
 const creativeId=new URLSearchParams(location.search).get('creativePreset');
 const creativeSuggestions={
   'new-year':['Новогодний','cinematic-zoom','lightleak','light-sweep','capsule'],
   'cruise':['Круиз','pan','crossfade','fade-rise','clean'],
   'excursion':['Экскурсионный','reveal','match','word-cascade','soft-shadow'],
   'flash-deal':['Горящее предложение','push-through','whip','punch-zoom','bar'],
   'premium':['Премиальный','float','crossfade','soft-zoom','luxury']
 };
 if(creativeId && Object.prototype.hasOwnProperty.call(creativeSuggestions,creativeId)){
   const [name,camera,transition,titleFx,subtitleStyle]=creativeSuggestions[creativeId];
   state.concepts[0]={...state.concepts[0],name,tag:'ШАБЛОН',camera,transition,titleFx,subtitleStyle};
   choicesFromPreset(1);say('Шаблон применен только к демонстрации. Для проекта нужен выбор трех предложений агента.');
 }
 announceReady();
}
wire();
