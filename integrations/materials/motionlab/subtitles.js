'use strict';
/* Motion Lab subtitle style library. Text and selections remain in the visitor's browser.
   Without an imported Whisper timeline, the word cadence is a visual demo. No audio transcription runs here. */
const STYLES = Object.freeze([
  {id:'clean', name:'Clean White', group:'universal', desc:'Четкие белые субтитры без лишних деталей.', use:'Речь и пояснения'},
  {id:'soft-shadow',name:'Soft Shadow',group:'universal',desc:'Объемная тень сохраняет контраст на светлом фоне.',use:'Прогулки и экскурсии'},
  {id:'capsule',name:'Dark Capsule',group:'universal',desc:'Полупрозрачная капсула вокруг фразы.',use:'Разговорные рилсы'},
  {id:'bar',name:'Solid Bar',group:'universal',desc:'Широкая темная плашка с цветной линией.',use:'Информационные видео'},
  {id:'outline',name:'Outline Text',group:'universal',desc:'Контурные буквы с подсветкой активного слова.',use:'Короткие заголовки'},
  {id:'two-line',name:'Editorial Left',group:'universal',desc:'Левое выравнивание и фирменная вертикальная черта.',use:'Экспертные комментарии'},
  {id:'cinema',name:'Cinematic Caps',group:'cinema',desc:'Крупные прописные буквы в киноэстетике.',use:'Начало ролика'},
  {id:'letterbox',name:'Letterbox',group:'cinema',desc:'Контрастная полоса в стиле кинотитров.',use:'Документальная подача'},
  {id:'editorial',name:'Editorial Serif',group:'cinema',desc:'Курсивный антиквенный шрифт для атмосферных сцен.',use:'История города'},
  {id:'spotlight',name:'Spotlight Word',group:'cinema',desc:'Главное слово светится на фоне остальных.',use:'Эмоциональный акцент'},
  {id:'glow',name:'Soft Glow',group:'cinema',desc:'Мягкое свечение белого текста.',use:'Ночной город'},
  {id:'price-tag',name:'Price Tag',group:'advertising',desc:'Светлая ценовая карточка с контрастными буквами.',use:'Стоимость тура'},
  {id:'offer-pill',name:'Offer Pill',group:'advertising',desc:'Шильдик «Спецпредложение» и читаемая фраза.',use:'Горящие предложения'},
  {id:'gold-card',name:'Gold Card',group:'advertising',desc:'Благородная темно-золотая карточка.',use:'Круизы и премиум'},
  {id:'gradient-bar',name:'Gradient Bar',group:'advertising',desc:'Цветная градиентная полоска под оффер.',use:'Рекламный блок'},
  {id:'countdown',name:'Limited Offer',group:'advertising',desc:'Рамка с меткой специального предложения.',use:'Акционная цена'},
  {id:'word-focus',name:'Word Focus',group:'kinetic',desc:'Произносимое слово становится крупнее остальных.',use:'Эмоциональная речь'},
  {id:'karaoke',name:'Karaoke Block',group:'kinetic',desc:'Цветная подсветка текущего слова в темной капсуле.',use:'Динамичные субтитры'},
  {id:'pop',name:'Active Word Pop',group:'kinetic',desc:'Активное слово подпрыгивает и увеличивается.',use:'Быстрые рилсы'},
  {id:'marker',name:'Highlight Marker',group:'kinetic',desc:'Маркер подчеркивает ключевое слово.',use:'Факты и аргументы'},
  {id:'luxury',name:'Luxury Gold',group:'premium',desc:'Тонкие золотые линии и классический шрифт.',use:'Премиальные маршруты'},
  {id:'glass',name:'Frosted Glass',group:'premium',desc:'Полупрозрачное матовое стекло с мягким размытием.',use:'Современная эстетика'},
  {id:'neon',name:'Neon Travel',group:'premium',desc:'Неоновое голубое свечение на темном фоне.',use:'Вечерние города'},
  {id:'travel-stamp',name:'Travel Stamp',group:'premium',desc:'Туристический штамп с пунктирной рамкой.',use:'Приключения и маршруты'},
]);
// Five original word animations, migrated from Motion Lab Type Studio.
// The motion layer is independent of all 24 visual presets.
const MOTIONS = Object.freeze([
  {id:'karaoke', name:'Karaoke Follow', ru:'Подсветка по словам', desc:'Текущее слово выделяется, остальные остаются видимыми.', preview:'СЛОВО  СЛОВО'},
  {id:'active-pop', name:'Active Word Pop', ru:'Пульс активного слова', desc:'Текущее слово увеличивается и приподнимается.', preview:'ПУНКТ  АКЦЕНТ'},
  {id:'caption-swap', name:'Caption Swap', ru:'Смена групп слов', desc:'Одна короткая группа слов заменяется следующей.', preview:'РАЗ  /  ДВА'},
  {id:'highlight-strip', name:'Highlight Strip', ru:'Цветная плашка', desc:'Под активным словом движется яркое выделение.', preview:'ЦВЕТ  +  ТЕКСТ'},
  {id:'word-reveal', name:'Word Reveal', ru:'Слова по одному', desc:'Каждое новое слово появляется, предыдущие остаются.', preview:'РАЗ  ДВА  ТРИ'}
]);
const BACKGROUNDS = Object.freeze({
  city:'https://static.wixstatic.com/media/7fd7b8_e8133d694a8f4f5a82b665901e9e41f4~mv2.jpg',
  sea:'https://static.wixstatic.com/media/7fd7b8_ac85605a20f74c278e350dede74234a2~mv2.jpg',
  mountains:'https://static.wixstatic.com/media/7fd7b8_b53b4bdba4c14271a663450044559b09~mv2.jpg'
});
const COLORS = Object.freeze({lime:'#c9f47d',gold:'#f0be6b',sky:'#8cd9ff',white:'#ffffff'});
const KNOWN = new Set(STYLES.map(s=>s.id));
const KNOWN_MOTIONS = new Set(MOTIONS.map(m=>m.id));
const favoriteKey = (style,motion) => style+'|'+motion;
const validCombo = value => typeof value==='string' && value.split('|').length===2 && KNOWN.has(value.split('|')[0]) && KNOWN_MOTIONS.has(value.split('|')[1]);
const $ = id => document.getElementById(id);
const all = selector => [...document.querySelectorAll(selector)];
function readFavorites(){
  try{
    const stored=JSON.parse(localStorage.getItem('motionlab:subtitle-combos:v2')||'null');
    if(Array.isArray(stored))return [...new Set(stored.filter(validCombo))].slice(0,120);
    // Migrate favorites from both of the separate editors without losing the old data.
    const oldStyles=JSON.parse(localStorage.getItem('motionlab-subtitle-style-favorites-v1')||'[]');
    const oldWords=JSON.parse(localStorage.getItem('motionlab:text:favorites')||'[]');
    const migrated=[...(Array.isArray(oldStyles)?oldStyles:[]).filter(id=>KNOWN.has(id)).map(id=>favoriteKey(id,'karaoke')),
                    ...(Array.isArray(oldWords)?oldWords:[]).filter(id=>KNOWN_MOTIONS.has(id)).map(id=>favoriteKey('clean',id))];
    return [...new Set(migrated)];
  }catch(_){return [];}
}

const state={active:'clean',motion:'karaoke',category:'all',bg:'city',text:'Путешествие начинается здесь',detail:'Откройте для себя новые города',scale:100,duration:3000,pos:'bottom',color:'lime',safe:false,loop:false,favorites:readFavorites()};
let raf=0, timer=0, toastTimer=0;
const sync={lines:[],lineIndex:0,audioUrl:null,spec:null,specName:null,active:false,sourceName:null};
function selected(){return STYLES.find(s=>s.id===state.active) || STYLES[0];}
function selectedMotion(){return MOTIONS.find(m=>m.id===state.motion)||MOTIONS[0];}
function currentCombo(){return favoriteKey(state.active,state.motion);}
function toast(message){const node=$('toast');node.textContent=message;node.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.classList.remove('show'),2200);}
function updateButtons(selector,attr,value){all(selector).forEach(b=>{const on=b.dataset[attr]===value;b.classList.toggle('current',on);b.setAttribute('aria-pressed',String(on));});}
function captionBlock(style,text,detail,mini=false){
  const cap=document.createElement('div');
  cap.className='caption tone-'+style.id+' motion-'+state.motion+(mini?' mini':'');
  cap.style.setProperty('--cap-scale',mini?'1':String(state.scale/100));
  const head=document.createElement('div');head.className='caption-main';
  const words=(text.trim()||'Путешествие начинается здесь').split(/\s+/u).slice(0,24);
  words.forEach((word,index)=>{const el=document.createElement('span');el.className='word';el.textContent=word;el.dataset.wordIndex=index;if(mini&&index===0)el.classList.add('active');head.append(el);if(index<words.length-1)head.append(document.createTextNode(' '));});
  cap.append(head);
  if(detail.trim()) {const line=document.createElement('div');line.className='caption-sub';line.textContent=detail;cap.append(line);}
  return cap;
}
function renderMotionCards(){
  const grid=$('motionGrid');grid.replaceChildren();
  for(const motion of MOTIONS){
    const b=document.createElement('button');b.type='button';
    b.className='motion-card'+(motion.id===state.motion?' current':'');
    b.dataset.motion=motion.id;
    b.setAttribute('aria-pressed',String(motion.id===state.motion));
    b.setAttribute('aria-label',motion.name+': '+motion.ru);
    const name=document.createElement('strong');name.textContent=motion.name;
    const description=document.createElement('span');description.textContent=motion.ru;
    const sample=document.createElement('i');sample.textContent=motion.preview;
    b.append(sample,name,description);
    b.addEventListener('click',()=>activateMotion(motion.id));
    grid.append(b);
  }
}
function activateMotion(id){
  if(!KNOWN_MOTIONS.has(id))return;
  stopDemo();state.motion=id;renderMotionCards();renderCards();renderFrame();renderFavorites();
  if(!matchMedia('(prefers-reduced-motion: reduce)').matches)runDemo();
}
function renderCards(){
  const grid=$('styleGrid');grid.replaceChildren();
  const visible=STYLES.filter(s=>state.category==='all'||s.group===state.category);
  $('visibleCount').textContent=String(visible.length);
  for(const style of visible){
    const card=document.createElement('article');card.className='style-card'+(state.active===style.id?' active':'');
    const choose=document.createElement('button');choose.type='button';choose.className='card-select';choose.setAttribute('aria-label','Выбрать стиль '+style.name);choose.setAttribute('aria-pressed',String(state.active===style.id));
    const box=document.createElement('div');box.className='style-card-preview';
    const number=document.createElement('span');number.className='card-no';number.textContent=String(STYLES.indexOf(style)+1).padStart(2,'0');
    const frame=document.createElement('div');frame.className='mini-container';frame.append(captionBlock(style,'НОВАЯ СТРАНА','BON TOURS',true));
    box.append(number,frame);choose.append(box);choose.addEventListener('click',()=>activate(style.id));
    const footer=document.createElement('div');footer.className='card-footer';
    const words=document.createElement('div');const title=document.createElement('strong');title.textContent=style.name;const desc=document.createElement('small');desc.textContent=style.desc;words.append(title,desc);
    const fav=document.createElement('button');fav.type='button';const saved=state.favorites.includes(favoriteKey(style.id,state.motion));fav.className='card-favorite'+(saved?' active':'');fav.textContent=saved?'★':'☆';fav.setAttribute('aria-label',(saved?'Убрать сочетание из избранного: ':'Добавить сочетание в избранное: ')+selectedMotion().name+' + '+style.name);fav.setAttribute('aria-pressed',String(saved));fav.addEventListener('click',()=>toggleFavorite(style.id,state.motion));
    footer.append(words,fav);card.append(choose,footer);grid.append(card);
  }
}
function renderFrame(){
  const style=selected();
  $('previewTitle').textContent=style.name;
  $('styleDescription').textContent=style.desc;
  $('styleUsage').textContent=style.use;
  $('activeStyleName').textContent=style.name;
  $('activeMotionName').textContent=selectedMotion().name;
  $('styleNumber').textContent=String(STYLES.indexOf(style)+1).padStart(2,'0')+' / 24';
  $('captionTarget').className='caption-wrap pos-'+state.pos;
  $('captionTarget').replaceChildren(captionBlock(style,state.text,state.detail));
  $('previewStage').style.setProperty('--style-accent',COLORS[state.color]);
  $('stageBackground').style.backgroundImage='url("'+BACKGROUNDS[state.bg]+'")';
  $('safeGuides').hidden=!state.safe;
  updateButtons('.background-button','bg',state.bg);
  updateButtons('.pos-options button','pos',state.pos);
  updateButtons('.swatch','color',state.color);
  $('sizeValue').textContent=state.scale+'%';
  $('durationValue').textContent=(state.duration/1000).toFixed(1)+' с';
  $('favBtn').textContent=state.favorites.includes(currentCombo())?'★':'☆';
  $('favBtn').classList.toggle('chosen',state.favorites.includes(currentCombo()));
  $('favBtn').setAttribute('aria-pressed',String(state.favorites.includes(currentCombo())));
  $('lineText').value=state.text;$('detailText').value=state.detail;
  accessibilityCheck();
  paintWords(0);
}
function accessibilityCheck(){
  const length=state.text.trim().length;
  const output=$('readability');
  const lowContrast=['outline','neon','glow'].includes(state.active);
  if(length>55){output.textContent='Длинная строка — сократить';output.style.color='#f0be6b';}
  else if(state.scale<90){output.textContent='Мелкий текст — увеличить';output.style.color='#f0be6b';}
  else if(lowContrast){output.textContent='Проверьте контраст';output.style.color='#f0be6b';}
  else{output.textContent='Размер и длина: в норме';output.style.color='#c9f47d';}
}
function activate(id){if(!KNOWN.has(id))return;stopDemo();state.active=id;renderCards();renderFrame();if(!matchMedia('(prefers-reduced-motion: reduce)').matches)runDemo();}
function saveFavorites(){try{localStorage.setItem('motionlab:subtitle-combos:v2',JSON.stringify(state.favorites));}catch(_){} }
function toggleFavorite(styleId,motionId=state.motion){
  if(!KNOWN.has(styleId)||!KNOWN_MOTIONS.has(motionId))return;
  const key=favoriteKey(styleId,motionId);
  state.favorites=state.favorites.includes(key)?state.favorites.filter(s=>s!==key):[...state.favorites,key];
  saveFavorites();renderCards();renderFavorites();renderFrame();
  toast(state.favorites.includes(key)?'Сочетание добавлено':'Сочетание удалено');
}

function renderFavorites(){
  const node=$('favoritesList');node.replaceChildren();
  $('favoriteCount').textContent=String(state.favorites.length);
  if(!state.favorites.length){const p=document.createElement('p');p.className='empty';p.textContent='Подборка пока пуста. Сначала выберите анимацию и стиль, затем нажмите звездочку.';node.append(p);return;}
  for(const key of state.favorites){
    const [styleId,motionId]=key.split('|');
    const style=STYLES.find(s=>s.id===styleId),motion=MOTIONS.find(m=>m.id===motionId);
    if(!style||!motion)continue;
    const item=document.createElement('div');item.className='favorite-combination';
    const b=document.createElement('button');b.type='button';b.className='favorite-chip';b.textContent=motion.name+' + '+style.name+' ↗';
    b.addEventListener('click',()=>{stopDemo();state.category='all';state.motion=motionId;state.active=styleId;updateButtons('.filter','category','all');renderMotionCards();renderCards();renderFrame();$('preview').scrollIntoView({behavior:'smooth',block:'start'});runDemo();});
    const remove=document.createElement('button');remove.type='button';remove.className='favorite-remove';remove.textContent='×';remove.setAttribute('aria-label','Удалить '+motion.name+' + '+style.name);
    remove.addEventListener('click',()=>toggleFavorite(styleId,motionId));
    item.append(b,remove);node.append(item);
  }
}

function paintWords(progress,forcedIndex=null){
  const words=all('#captionTarget .word');if(!words.length)return;
  const count=words.length,p=Math.max(0,Math.min(1,progress));
  const active=forcedIndex===null?(p>=1?count-1:Math.min(count-1,Math.floor(p*count))):Math.max(0,Math.min(count-1,forcedIndex));
  const groupSize=Math.max(2,Math.ceil(count/3));
  const groupCount=Math.ceil(count/groupSize);
  const group=Math.min(groupCount-1,Math.floor(active/groupSize));
  words.forEach((word,index)=>{
    word.classList.remove('active','pending','spoken','revealed');
    if(state.motion==='caption-swap'){
      if(Math.floor(index/groupSize)===group){word.classList.add('revealed');if(index===active)word.classList.add('active');}
    } else if(state.motion==='word-reveal'){
      if(index<=active)word.classList.add('revealed');
      if(index===active)word.classList.add('active');
    } else {
      if(index===active)word.classList.add('active');
      if(index>active)word.classList.add('pending');
      if(index<active)word.classList.add('spoken');
    }
  });
}
function stopDemo(){
  cancelAnimationFrame(raf);raf=0;clearTimeout(timer);timer=0;
  $('progressFill').style.width='0%';$('timeStatus').textContent='0.0 с';
  const audio=$('syncAudio');if(audio&&!audio.paused)audio.pause();
  $('playLabel').textContent='Воспроизвести сочетание';$('playIcon').textContent='▶';
  paintWords(0);
}

function runDemo(){
  if(sync.active && sync.lines.length){runSyncedPreview();return;}
  stopDemo();const words=all('#captionTarget .word');if(!words.length)return;
  const start=performance.now();$('playLabel').textContent='Остановить';$('playIcon').textContent='Ⅱ';
  let prev=-1;
  function tick(now){
    const p=Math.max(0,Math.min(1,(now-start)/state.duration));
    const at=Math.min(words.length-1,Math.floor(p*words.length));
    const atGroup=Math.min(2,Math.floor(p*3));
    const index=state.motion==='caption-swap'?atGroup:at;
    if(index!==prev||p===1){paintWords(p);prev=index;}
    $('progressFill').style.width=(p*100).toFixed(1)+'%';
    $('timeStatus').textContent=(p*state.duration/1000).toFixed(1)+' с';
    if(p<1)raf=requestAnimationFrame(tick);
    else{raf=0;$('playLabel').textContent='Воспроизвести сочетание';$('playIcon').textContent='▶';if(state.loop)timer=setTimeout(runDemo,650);}
  }
  raf=requestAnimationFrame(tick);
}

function selectionPayload(){
  const parsed=key=>{const [style_id,animation_id]=key.split('|');return {style_id,animation_id};};
  return {schema:'motionlab.subtitle-combinations.v3',created_at:new Date().toISOString(),format:'9:16',
    selected_combination:{style_id:state.active,animation_id:state.motion},
    saved_combinations:(state.favorites.length?state.favorites:[currentCombo()]).map(parsed),
    text:state.text,secondary_text:state.detail,position:state.pos,size_percent:state.scale,
    accent:state.color,demonstration_word_duration_ms:state.duration,safe_guides:state.safe,
    alignment:snapshotAlignment(),
    note:sync.active?'Время слов взято из импортированного timeline.json, сформированного Киностудией.':'Нет таймкодов, используется демонстрационный ритм. Для MP4 нужен Whisper timeline.'};
}

function brief(){
  const selectedPairs=state.favorites.length?state.favorites:[currentCombo()];
  const descriptions=selectedPairs.map(key=>{const [style,motion]=key.split('|');return (MOTIONS.find(x=>x.id===motion)?.name||motion)+' + '+(STYLES.find(x=>x.id===style)?.name||style);});
  return 'MOTION LAB / ЕДИНЫЙ РЕДАКТОР СУБТИТРОВ\nТекущий вариант: '+selectedMotion().name+' + '+selected().name+'\nСохраненные сочетания: '+descriptions.join('; ')+'\nТекст: '+state.text+'\nПодпись: '+state.detail+'\nПоложение: '+state.pos+'; размер: '+state.scale+'%; акцент: '+state.color+'\nДемонстрационный темп: '+(state.duration/1000).toFixed(1)+' с\nДля точной синхронизации необходимы таймкоды речи и финальный QA MP4.';
}

async function copyBrief(){try{await navigator.clipboard.writeText(brief());toast('ТЗ скопировано');$('exportStatus').textContent='Монтажное ТЗ скопировано в буфер обмена.';}catch(_){const x=document.createElement('textarea');x.value=brief();document.body.append(x);x.select();try{document.execCommand('copy');toast('ТЗ скопировано');}catch(_2){toast('Не удалось скопировать. Используйте экспорт JSON.');}x.remove();}}
function downloadJSON(){const blob=new Blob([JSON.stringify(selectionPayload(),null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='motion-lab-subtitle-combinations.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),5000);$('exportStatus').textContent='JSON скачан: выбранная анимация + стиль и сохраненные сочетания. Видео не создавалось.';toast('JSON подготовлен');}
function bind(){
  all('.filter').forEach(b=>b.addEventListener('click',()=>{state.category=b.dataset.category;updateButtons('.filter','category',state.category);renderCards();}));
  all('.background-button').forEach(b=>b.addEventListener('click',()=>{state.bg=b.dataset.bg;renderFrame();}));
  all('.pos-options button').forEach(b=>b.addEventListener('click',()=>{state.pos=b.dataset.pos;renderFrame();}));
  all('.swatch').forEach(b=>b.addEventListener('click',()=>{state.color=b.dataset.color;renderFrame();}));
  $('lineText').addEventListener('input',e=>{state.text=e.target.value;stopDemo();renderFrame();});
  $('detailText').addEventListener('input',e=>{state.detail=e.target.value;stopDemo();renderFrame();});
  $('sizeRange').addEventListener('input',e=>{state.scale=Number(e.target.value);stopDemo();renderFrame();});
  $('durationRange').addEventListener('input',e=>{state.duration=Number(e.target.value);stopDemo();renderFrame();});
  $('safeToggle').addEventListener('change',e=>{state.safe=e.target.checked;renderFrame();});
  $('loopToggle').addEventListener('change',e=>{state.loop=e.target.checked;});
  $('playBtn').addEventListener('click',()=>raf||timer?stopDemo():runDemo());
  $('favBtn').addEventListener('click',()=>toggleFavorite(state.active,state.motion));
  $('resetBtn').addEventListener('click',()=>{stopDemo();Object.assign(state,{text:'Путешествие начинается здесь',detail:'Откройте для себя новые города',scale:100,duration:3000,pos:'bottom',color:'lime',safe:false,loop:false});$('sizeRange').value='100';$('durationRange').value='3000';$('safeToggle').checked=false;$('loopToggle').checked=false;renderFrame();toast('Настройки сброшены');});
  $('copyBrief').addEventListener('click',copyBrief);$('downloadJson').addEventListener('click',downloadJSON);
  $('timingFile').addEventListener('change',importAlignment);
  $('audioFile').addEventListener('change',importAudio);
  $('jobSpecFile').addEventListener('change',importSpec);
  $('syncLine').addEventListener('change',e=>selectTimedLine(Number(e.target.value)));
  $('syncSeek').addEventListener('input',seekTimedLine);
  $('downloadVideoSpec').addEventListener('click',exportVideoSpec);
  $('clearFavorites').addEventListener('click',()=>{state.favorites=[];saveFavorites();renderCards();renderFavorites();renderFrame();toast('Подборка очищена');});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stopDemo();});
}
bind();renderMotionCards();renderCards();renderFrame();renderFavorites();
window.__subtitleStudio={styles:STYLES.map(s=>s.id),motions:MOTIONS.map(m=>m.id),chooseStyle:activate,chooseMotion:activateMotion,payload:selectionPayload,paintWords};

// Browser-local handoff from an existing, word-aligned Simba timeline.
// Deliberately no speech-to-text guesses, network calls or automatic provider launches.
const markStatus = (id, message, kind='') => {
  const n=$(id); n.textContent=message; n.classList.remove('ok','error');
  if(kind)n.classList.add(kind);
};
function snapshotAlignment(){
  if(!sync.active)return {source:'demo',real_word_timing:false};
  const line=sync.lines[sync.lineIndex];
  return {source:'simba-timeline.json',real_word_timing:true,source_file:sync.sourceName,
    current_line:{text:line.text,t0:line.t0,t1:line.t1,words:line.words.map(([word,start])=>({word,start_s:start}))}};
}
function parseWordTimeline(data){
  if(!data||!Array.isArray(data.lines))throw Error('Ожидается timeline.json из Simba с массивом lines.');
  if(data.lines.length>200)throw Error('Слишком много строк таймлайна (максимум 200).');
  const parsed=[];
  data.lines.forEach((line,i)=>{
    if(!line||typeof line.text!=='string'||!Array.isArray(line.words)||!line.words.length)return;
    const t0=Number(line.t0),t1=Number(line.t1);
    if(!Number.isFinite(t0)||!Number.isFinite(t1)||t0<0||t1<=t0||t1>3600)throw Error('Неверные границы строки '+(i+1));
    const normalized=line.words.map((pair,j)=>{
      if(!Array.isArray(pair)||typeof pair[0]!=='string'||pair[0].length>150||typeof pair[1]!=='number'||!Number.isFinite(pair[1]))throw Error('Неверный таймкод слова '+(j+1));
      const at=pair[1];
      if(at<t0-.15||at>t1+.3)throw Error('Слово за пределами строки '+(i+1));
      return [pair[0],at];
    });
    if(normalized.some((pair,j)=>j&&pair[1]<normalized[j-1][1]))throw Error('Нарушен порядок слов в строке '+(i+1));
    if(normalized.length>80)throw Error('В одной строке слишком много слов.');
    parsed.push({text:line.text,t0,t1,words:normalized});
  });
  if(!parsed.length)throw Error('Нет строк с реальными временными метками слов.');
  return parsed;
}
async function importAlignment(event){
  const file=event.target.files?.[0];if(!file)return;
  stopDemo();
  try{
    if(file.size>3*1024*1024)throw Error('JSON превышает 3 МБ.');
    const parsed=parseWordTimeline(JSON.parse(await file.text()));
    sync.lines=parsed;sync.active=true;sync.lineIndex=0;sync.sourceName=file.name;
    const selector=$('syncLine');selector.replaceChildren();
    parsed.forEach((line,i)=>{const o=document.createElement('option');o.value=String(i);o.textContent=(i+1)+'. '+line.text.slice(0,65);selector.append(o);});
    selector.disabled=false;$('syncSeek').disabled=false;
    markStatus('syncStatus','Импортировано '+parsed.length+' фраз с таймкодами слов. Источник: '+file.name+'.','ok');
    selectTimedLine(0);
  }catch(e){sync.active=false;sync.lines=[];$('syncLine').disabled=true;$('syncSeek').disabled=true;markStatus('syncStatus','Ошибка таймлайна: '+e.message,'error');}
}
function matchesTranscript(){
  if(!sync.active||!sync.lines.length)return false;
  const target=sync.lines[sync.lineIndex];
  return state.text.trim().replace(/\s+/gu,' ')===target.text.trim().replace(/\s+/gu,' ')
      && state.text.trim().split(/\s+/u).length===target.words.length;
}
function selectTimedLine(index){
  if(!sync.active||index<0||index>=sync.lines.length)return;
  stopDemo();sync.lineIndex=index;const line=sync.lines[index];
  state.text=line.text;state.detail='';$('syncLine').value=String(index);
  $('syncSeek').value='0';renderFrame();
  if(sync.audioUrl && $('syncAudio').readyState){$('syncAudio').currentTime=line.t0;}
  paintSynchronizedLine(line.t0);
  markStatus('syncStatus','Синхронизация: настоящие таймкоды из '+sync.sourceName+' · '+line.words.length+' слов.','ok');
}
function updateWordTimes(active){
  all('#wordTimings .word-timing').forEach((el,i)=>el.classList.toggle('active',i===active));
}
function paintSynchronizedLine(time){
  if(!sync.active||!sync.lines.length)return;
  const line=sync.lines[sync.lineIndex];
  const length=Math.max(.1,line.t1-line.t0);
  const position=Math.max(0,Math.min(1,(time-line.t0)/length));
  let active=-1;
  line.words.forEach((word,i)=>{if(time>=word[1]-0.002)active=i;});
  if(active<0)active=0;
  $('syncSeek').value=String(Math.round(position*1000));
  $('progressFill').style.width=(position*100).toFixed(1)+'%';
  $('timeStatus').textContent=Math.max(0,time).toFixed(2)+' с';
  $('syncClock').textContent=Math.max(0,time).toFixed(2)+' с';
  if(matchesTranscript())paintWords(position,active);
  else{paintWords(position);markStatus('syncStatus','Текст отличается от импортированной фразы. Синхронизация слов отключена до выбора исходной фразы.','error');}
  const list=$('wordTimings');
  if(list.children.length!==line.words.length){
    list.replaceChildren();
    line.words.forEach(([word,start])=>{
      const token=document.createElement('span');token.className='word-timing';token.append(document.createTextNode(word+' '));
      const time=document.createElement('b');time.textContent=start.toFixed(2)+' c';token.append(time);list.append(token);
    });
  }
  updateWordTimes(active);
}
function seekTimedLine(event){
  if(!sync.active)return;stopDemo();
  const line=sync.lines[sync.lineIndex],time=line.t0+(line.t1-line.t0)*(Number(event.target.value)/1000);
  if(sync.audioUrl && $('syncAudio').readyState)$('syncAudio').currentTime=time;
  paintSynchronizedLine(time);
}
async function importAudio(event){
  const file=event.target.files?.[0];if(!file)return;
  if(file.size>100*1024*1024){markStatus('syncStatus','Аудио больше 100 МБ, файл не загружен.','error');return;}
  if(!file.type.startsWith('audio/')&&!/\.(wav|mp3|m4a|ogg|aac)$/i.test(file.name)){markStatus('syncStatus','Разрешены только аудиофайлы.','error');return;}
  stopDemo();const audio=$('syncAudio');
  if(sync.audioUrl)URL.revokeObjectURL(sync.audioUrl);
  sync.audioUrl=URL.createObjectURL(file);audio.src=sync.audioUrl;audio.hidden=false;
  audio.onloadedmetadata=()=>{
    const last=sync.lines.at(-1)?.t1;
    const warn=last!==undefined&&Math.abs(audio.duration-last)>2;
    markStatus('syncStatus','Аудио загружено локально ('+audio.duration.toFixed(1)+' с). '+(warn?'Продолжительность отличается от таймлайна. Проверьте соответствие записи.':'Для синхронизации нужны таймкоды timeline.json.'),warn?'error':'ok');
  };
  audio.onended=()=>{cancelAnimationFrame(raf);raf=0;$('playLabel').textContent='Воспроизвести сочетание';$('playIcon').textContent='▶';};
}
function runSyncedPreview(){
  stopDemo();const line=sync.lines[sync.lineIndex];if(!line)return;
  if(!matchesTranscript()){markStatus('syncStatus','Выберите исходную фразу таймлайна: текущий текст отличается.','error');return;}
  const audio=$('syncAudio');let base=line.t0;let start=performance.now();
  if(sync.audioUrl){
    if(audio.readyState<1){markStatus('syncStatus','Аудио еще не готово к воспроизведению.','error');return;}
    audio.currentTime=line.t0;
    audio.play().catch(()=>markStatus('syncStatus','Браузер не разрешил воспроизведение аудио.','error'));
  }
  $('playLabel').textContent='Остановить';$('playIcon').textContent='Ⅱ';
  function tick(now){
    const t=sync.audioUrl?audio.currentTime:base+(now-start)/1000;
    paintSynchronizedLine(Math.min(t,line.t1));
    if(t<line.t1){raf=requestAnimationFrame(tick);return;}
    raf=0;if(sync.audioUrl)audio.pause();
    $('playLabel').textContent='Воспроизвести сочетание';$('playIcon').textContent='▶';
    if(state.loop)timer=setTimeout(runSyncedPreview,600);
  }
  raf=requestAnimationFrame(tick);
}
async function importSpec(event){
  const file=event.target.files?.[0];if(!file)return;
  try{
    if(file.size>2*1024*1024)throw Error('Спецификация больше 2 МБ.');
    const data=JSON.parse(await file.text());
    if(!data||typeof data!=='object'||!Array.isArray(data.scenes)||data.scenes.length<1||data.scenes.length>8||typeof data.packageId!=='string')throw Error('Ожидается video-spec.json из Simba.');
    sync.spec=data;sync.specName=file.name;
    $('downloadVideoSpec').disabled=false;
    markStatus('specStatus','Загружено: '+data.packageId+', сцен: '+data.scenes.length+'. Остальные параметры сохраняются.','ok');
  }catch(e){sync.spec=null;$('downloadVideoSpec').disabled=true;markStatus('specStatus','Ошибка: '+e.message,'error');}
}
function exportVideoSpec(){
  if(!sync.spec)return;
  const spec=JSON.parse(JSON.stringify(sync.spec));
  spec.subtitleStyle={style:state.active,motion:state.motion,color:state.color,
    scale_percent:state.scale,position:state.pos};
  const filename=String(spec.packageId).replace(/[^a-zA-Z0-9_.-]/g,'-')+'-with-subtitles.video-spec.json';
  const blob=new Blob([JSON.stringify(spec,null,2)],{type:'application/json;charset=utf-8'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;
  document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),8000);
  markStatus('specStatus','Скачан '+filename+'. Выбор применится при следующем рендере. Видео не запускалось.','ok');
}
