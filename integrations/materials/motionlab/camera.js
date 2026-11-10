'use strict';
// Motion Lab camera moves: preparation-only 2D previews, no render or API calls.
const EFFECTS=[
 {id:'cinematic-zoom',name:'Cinematic Zoom',ru:'Плавное приближение',group:'cinematic',about:'Плавное приближение с мягким началом и завершением. Для городов, архитектуры и атмосферы.',use:'Элегантное вступление, городской вид, премиальная реклама.',sim:false},
 {id:'dolly-zoom',name:'Dolly Zoom',ru:'Имитация оптического зума',group:'cinematic',about:'Условная 2D-имитация изменения перспективы. Не настоящий Dolly Zoom: для него нужна глубина сцены.',use:'Выразительный момент, крупная архитектура.',sim:true},
 {id:'orbit',name:'Orbit',ru:'Поворот вокруг центра',group:'cinematic',about:'2D-имитация движения вокруг точки: поворот изображения и сдвиг, без реального 3D-облета.',use:'Крупный объект или центральная достопримечательность.',sim:true},
 {id:'focus-pull',name:'Focus Pull',ru:'Проявление из размытия',group:'cinematic',about:'Переход от мягкого размытия к четкости. Не имитирует настоящий перевод фокуса между разными планами.',use:'Первый кадр, смена внимания, акцент на объекте.',sim:true},
 {id:'pan',name:'Pan',ru:'Горизонтальный проезд',group:'motion',about:'Равномерный горизонтальный сдвиг по широкому изображению, без дрожания.',use:'Панорама набережной, улица, площадь.',sim:false},
 {id:'tilt',name:'Tilt',ru:'Вертикальный проезд',group:'motion',about:'Движение снизу вверх по фасаду, башне или горному пейзажу.',use:'Собор, замок, горы, монумент.',sim:false},
 {id:'parallax',name:'Parallax 3D',ru:'Имитация параллакса',group:'motion',about:'Условная глубина: слои двигаются с разной скоростью. Настоящий параллакс требует разделенных планов.',use:'Пейзажи, горы, море, рекламные акценты.',sim:true},
 {id:'push-through',name:'Push Through',ru:'Проезд внутрь кадра',group:'motion',about:'Энергичный проезд вперед со стабилизированным ускорением.',use:'Динамическое открытие следующей сцены.',sim:false},
 {id:'roll',name:'Camera Roll',ru:'Наклон горизонта',group:'creative',about:'Легкий диагональный поворот без резких скачков.',use:'Энергичные клипы и праздничная атмосфера.',sim:false},
 {id:'float',name:'Floating Camera',ru:'Плавное парение',group:'creative',about:'Небольшое движение по мягкой дуге. Прием избегает дрожания.',use:'Круизы, море, спокойные пейзажи.',sim:false},
 {id:'reveal',name:'Dramatic Reveal',ru:'Постепенное раскрытие',group:'creative',about:'Кадр проявляется через мягкую маску и масштабирование. Эффектное вступление.',use:'Кульминация маршрута, главная достопримечательность.',sim:false},
 {id:'speed-ramp',name:'Speed Ramp',ru:'Ускорение / замедление',group:'creative',about:'Имитация ускорения движения изображения с плавной остановкой. Видео time-remap не выполняется.',use:'Акцент на музыке, смена городов, рекламные блоки.',sim:true}
];
const IMAGE_URLS={city:'https://images.unsplash.com/photo-1523906834658-6e24ef2386f9?w=1200&q=82',sea:'https://images.unsplash.com/photo-1500534623283-312aade485b7?w=1200&q=82',mountains:'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1200&q=82'};
const $=id=>document.getElementById(id),qsa=(s)=>[...document.querySelectorAll(s)],clamp=(v,min=0,max=1)=>Math.min(max,Math.max(min,v));
const ease=t=>t*t*(3-2*t),smooth=t=>.5-.5*Math.cos(Math.PI*t);
const storageKey='motionlab-camera-favorites-v1';
let favorites=new Set(),current=EFFECTS[0],filter='all',duration=3000,intensity=.5,direction=1,ratio='9:16';
let running=false,start=0,frameId=0,progress=0,uploadUrl=null,activeBackground='city';
const templates=['Вступление / общий вид','Город / улицы','Архитектура / детали','Маршрут / пейзаж','Главный объект','Финал / приглашение'];
let shots=templates.map((name,i)=>({name,effect:EFFECTS[Math.min(i,EFFECTS.length-1)].id,seconds:3}));
function notify(message){const el=$('toast');el.textContent=message;el.classList.add('shown');clearTimeout(notify.id);notify.id=setTimeout(()=>el.classList.remove('shown'),2600)}
function saveFavorites(){try{localStorage.setItem(storageKey,JSON.stringify([...favorites]));}catch{}}
try{const f=JSON.parse(localStorage.getItem(storageKey)||'[]');if(Array.isArray(f))favorites=new Set(f.filter(id=>EFFECTS.some(e=>e.id===id)));}catch{}
function cardIcon(group,id){const common='viewBox="0 0 96 70" aria-hidden="true"';
 if(group==='cinematic')return `<svg ${common}><rect x="18" y="12" width="60" height="47" rx="6"/><circle cx="48" cy="35" r="15"/><circle cx="48" cy="35" r="5"/><path d="M34 35h28M48 21v28"/></svg>`;
 if(group==='motion')return `<svg ${common}><rect x="22" y="14" width="52" height="42" rx="5"/><path d="M6 35h14m-6-6 6 6-6 6M90 35H76m6-6-6 6 6 6"/><path d="M37 40l9-10 7 7 7-11"/></svg>`;
 return `<svg ${common}><rect x="20" y="12" width="56" height="47" rx="5"/><path d="M35 41l13-13 13 13M48 21v28"/><path d="M10 13l6-6m-6 0 6 6M80 60l6 6m0-6-6 6"/></svg>`;}
function renderCards(){const visible=EFFECTS.filter(e=>filter==='all'||e.group===filter);$('visibleCount').textContent=visible.length;$('effectGrid').innerHTML=visible.map((e)=>`<article class="effect-card ${current.id===e.id?'active':''}"><button type="button" class="effect-main" data-effect="${e.id}"><div class="card-viz"><span class="card-num">${String(EFFECTS.indexOf(e)+1).padStart(2,'0')}</span>${cardIcon(e.group,e.id)}<i class="sim-marker"></i></div><div class="card-details"><span><b>${e.name}</b><span>${e.ru}${e.sim?' · 2D':''}</span></span><span class="fav-card ${favorites.has(e.id)?'marked':''}" data-fav="${e.id}" role="button" tabindex="-1" title="Отметить эффект">${favorites.has(e.id)?'★':'☆'}</span></div></button></article>`).join('');
 qsa('[data-effect]').forEach(btn=>btn.addEventListener('click',e=>{const f=e.target.closest('[data-fav]');if(f){toggleFavorite(f.dataset.fav);return;}chooseEffect(btn.dataset.effect)}));}
function chooseEffect(id){current=EFFECTS.find(e=>e.id===id)||EFFECTS[0];$('effectTitle').textContent=current.name;$('effectNumber').textContent=`${String(EFFECTS.indexOf(current)+1).padStart(2,'0')} / 12`;$('effectDescription').textContent=current.about;$('previewNote').innerHTML=`<strong>${current.sim?'2D-ИМИТАЦИЯ':'ПРИМЕНЕНИЕ'}</strong> · ${current.use}`;$('favoriteButton').textContent=favorites.has(current.id)?'★':'☆';$('favoriteButton').classList.toggle('marked',favorites.has(current.id));renderCards();restart();}
function toggleFavorite(id){if(favorites.has(id))favorites.delete(id);else favorites.add(id);saveFavorites();renderCards();renderFavoriteList();$('favoriteButton').textContent=favorites.has(current.id)?'★':'☆';$('favoriteButton').classList.toggle('marked',favorites.has(current.id));notify(favorites.has(id)?'Движение добавлено в подборку':'Движение убрано из подборки')}
function renderFavoriteList(){$('favoriteCount').textContent=favorites.size;$('favoriteList').innerHTML=favorites.size?[...favorites].map(id=>{const e=EFFECTS.find(e=>e.id===id);return `<button type="button" class="fav-pill" data-open="${id}">${e.name} ↗</button>`}).join(''):'<span class="empty">Пока ничего не выбрано.</span>';qsa('[data-open]').forEach(b=>b.onclick=()=>{chooseEffect(b.dataset.open);$('preview').scrollIntoView({behavior:'smooth',block:'nearest'})})}
function applyFrame(p){
 const u=direction===1?p:1-p,z=clamp(intensity,.1,1),amt=.7+z*.7;let x=0,y=0,rot=0,scale=1.08,blur=0,clip='none',far=0,light=0;
 const s=ease(u),sine=Math.sin(Math.PI*u),d=amt;
 switch(current.id){
  case 'cinematic-zoom':scale=1.04+.16*d*s;break;
  case 'dolly-zoom':scale=1.17+.23*d*s;x=3*d*(u-.5);y=-3*d*(u-.5);far=.13+.3*s;break;
  case 'orbit':scale=1.18;rot=(u-.5)*5*d;x=(u-.5)*13*d;y=3*Math.sin(u*Math.PI)*d;break;
  case 'focus-pull':scale=1.13+.04*s;blur=7*d*(1-s);light=.14*s;break;
  case 'pan':scale=1.22;x=(.5-u)*14*d;break;
  case 'tilt':scale=1.22;y=(.5-u)*14*d;break;
  case 'parallax':scale=1.14+.09*s;x=(.5-u)*7*d;y=(.5-u)*3*d;far=.12+.32*Math.sin(Math.PI*u);break;
  case 'push-through':scale=1.06+.32*d*s;break;
  case 'roll':scale=1.18;rot=(u-.5)*9*d;x=(u-.5)*6*d;break;
  case 'float':scale=1.12;x=Math.sin(u*Math.PI*2)*2.5*d;y=(.5-u)*4*d;rot=Math.sin(u*Math.PI*2)*.6*d;break;
  case 'reveal':scale=1.22-.11*s;clip=`inset(0 ${100*(1-s)*.5}% 0 ${100*(1-s)*.5}% round ${24*(1-s)}px)`;light=.30*(1-s);break;
  case 'speed-ramp':{const r=u<.25?u*.36:u<.72?.09+(u-.25)*1.75:.9125+(u-.72)*.3125;scale=1.05+.24*d*clamp(r);x=(.5-r)*5*d;break;}
 }
 const image=$('frameImage');image.style.transform=`translate3d(${x}%,${y}%,0) scale(${scale}) rotate(${rot}deg)`;image.style.filter=`brightness(.91) saturate(.96) blur(${blur.toFixed(2)}px)`;image.style.clipPath=clip;
 $('farLayer').style.opacity=far;$('farLayer').style.transform=`translate3d(${(-x*.6).toFixed(2)}%,${(-y*.3).toFixed(2)}%,0)`;$('lightLayer').style.opacity=light;
 $('timer').textContent=(p*duration/1000).toFixed(2)+' c';$('progressFill').style.width=(p*100)+'%';
}
function pause(){running=false;cancelAnimationFrame(frameId);$('playButton').textContent='▶  Воспроизвести'}
function frame(now){if(!running)return;const elapsed=now-start;progress=clamp(elapsed/duration);applyFrame(progress);if(progress>=1){pause();return;}frameId=requestAnimationFrame(frame)}
function play(){if(running){pause();return;}if(progress>=1)progress=0;running=true;start=performance.now()-progress*duration;$('playButton').textContent='Ⅱ  Пауза';frameId=requestAnimationFrame(frame)}
function restart(){pause();progress=0;applyFrame(0);play()}
function setBackground(which){activeBackground=which;if(uploadUrl){URL.revokeObjectURL(uploadUrl);uploadUrl=null;}$('frameImage').src=IMAGE_URLS[which]||IMAGE_URLS.city;qsa('[data-image]').forEach(btn=>btn.classList.toggle('selected',btn.dataset.image===which));restart()}
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function renderShots(){const options=EFFECTS.map(e=>`<option value="${e.id}">${e.name}${e.sim?' (2D)':''}</option>`).join('');$('shotRows').innerHTML=shots.map((shot,i)=>`<div class="shot-row" data-shot="${i}"><span class="shot-index">${String(i+1).padStart(2,'0')}</span><label>НАЗВАНИЕ КАДРА<input data-field="name" value="${esc(shot.name)}" maxlength="90"></label><label>ДВИЖЕНИЕ<select data-field="effect">${options}</select></label><label>ДЛИТЕЛЬНОСТЬ, СЕК<input data-field="seconds" type="number" min="1" max="15" step=".25" value="${shot.seconds}"></label><button type="button" class="remove-shot" data-remove="${i}" title="Удалить кадр">×</button></div>`).join('');qsa('.shot-row').forEach((row,i)=>{row.querySelector('select').value=shots[i].effect;row.querySelectorAll('[data-field]').forEach(input=>{input.addEventListener('change',()=>{const field=input.dataset.field;shots[i][field]=field==='seconds'?clamp(Number(input.value)||3,1,15):input.value;storeShots();updateSummary()})});row.querySelector('[data-remove]').onclick=()=>{if(shots.length===1){notify('Нужен хотя бы один кадр');return;}shots.splice(i,1);storeShots();renderShots()}});updateSummary()}
function storeShots(){try{localStorage.setItem('motionlab-camera-shotlist-v1',JSON.stringify(shots))}catch{}}
try{const stored=JSON.parse(localStorage.getItem('motionlab-camera-shotlist-v1'));if(Array.isArray(stored)&&stored.length>0&&stored.length<=30)shots=stored.filter(s=>s&&typeof s.name==='string'&&EFFECTS.some(e=>e.id===s.effect)&&Number.isFinite(Number(s.seconds))).map(s=>({name:s.name.slice(0,90),effect:s.effect,seconds:clamp(Number(s.seconds),1,15)}));}catch{}
function updateSummary(){$('shotSummary').textContent=`${shots.length} кадров · ${shots.reduce((a,s)=>a+(Number(s.seconds)||0),0).toFixed(1)} с · план без рендера`}
function plan(){return {schema:'motion-lab-preproduction-camera-v1',created_at:new Date().toISOString(),production_state:'PREPRODUCTION_ONLY',no_render:true,approved:false,format:ratio,preview_settings:{duration_ms:duration,intensity_percent:Math.round(intensity*100),direction:direction===1?'forward':'reverse'},favorites:[...favorites],shots:shots.map((s,i)=>({shot:i+1,name:s.name,duration_seconds:Number(s.seconds),camera_motion:{id:s.effect,name:EFFECTS.find(e=>e.id===s.effect).name,simulated_2d:EFFECTS.find(e=>e.id===s.effect).sim}})),notes:['План не является video-spec.json и не запускает MP4.','Движение камерой и имитации 3D должны быть согласованы с фактическим исходным материалом.','Текст, озвучка, музыка, переходы и субтитры задаются отдельными утвержденными этапами.']}}
function download(){const blob=new Blob([JSON.stringify(plan(),null,2)],{type:'application/json;charset=utf-8'});const href=URL.createObjectURL(blob);const a=document.createElement('a');a.href=href;a.download='bon-tours-camera-shotlist.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(href),3000);notify('Монтажный план сохранен в JSON')}
async function copy(){const lines=['BON TOURS / MOTION LAB — ПОДГОТОВКА ДВИЖЕНИЯ КАМЕРЫ','',...shots.map((s,i)=>`${i+1}. ${s.name} — ${EFFECTS.find(e=>e.id===s.effect).name}, ${s.seconds} с${EFFECTS.find(e=>e.id===s.effect).sim?' (2D-имитация)':''}`),'','Движение: только план; монтаж и озвучка не запускаются.'];try{await navigator.clipboard.writeText(lines.join('\n'));notify('Монтажное ТЗ скопировано')}catch{notify('Копирование недоступно в браузере')}}
qsa('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;qsa('[data-filter]').forEach(x=>x.classList.toggle('selected',x===b));renderCards()});
qsa('[data-image]').forEach(b=>b.onclick=()=>setBackground(b.dataset.image));
qsa('[data-direction]').forEach(b=>b.onclick=()=>{direction=b.dataset.direction==='reverse'?-1:1;qsa('[data-direction]').forEach(x=>x.classList.toggle('selected',x===b));restart()});
qsa('[data-ratio]').forEach(b=>b.onclick=()=>{ratio=b.dataset.ratio;$('screen').classList.toggle('square',ratio==='1:1');$('screen').classList.toggle('wide',ratio==='16:9');qsa('[data-ratio]').forEach(x=>x.classList.toggle('selected',x===b));restart()});
$('playButton').onclick=play;$('replayButton').onclick=restart;$('favoriteButton').onclick=()=>toggleFavorite(current.id);
$('duration').oninput=e=>{duration=Number(e.target.value);$('durationLabel').textContent=(duration/1000).toFixed(2)+' с';restart()};
$('intensity').oninput=e=>{intensity=Number(e.target.value)/100;$('intensityLabel').textContent=Math.round(intensity*100)+'%';restart()};
$('imageUpload').onchange=e=>{const file=e.target.files?.[0];if(!file)return;if(file.size>12*1024*1024){notify('Максимум 12 МБ');e.target.value='';return;}if(!['image/jpeg','image/png','image/webp'].includes(file.type)){notify('Нужен JPG, PNG или WEBP');return;}if(uploadUrl)URL.revokeObjectURL(uploadUrl);uploadUrl=URL.createObjectURL(file);$('frameImage').src=uploadUrl;qsa('[data-image]').forEach(x=>x.classList.remove('selected'));restart();notify('Фото загружено локально')};
$('addShot').onclick=()=>{if(shots.length>=30){notify('Максимум 30 кадров');return;}shots.push({name:`Кадр ${shots.length+1}`,effect:current.id,seconds:3});storeShots();renderShots();notify('Кадр добавлен')};
$('fillShots').onclick=()=>{const list=[...favorites];if(!list.length){notify('Сначала отметьте хотя бы одно движение звездочкой');return;}shots.forEach((s,i)=>s.effect=list[i%list.length]);storeShots();renderShots();notify('Выбранные движения распределены по кадрам')};
$('savePlan').onclick=download;$('copyPlan').onclick=copy;
// Locally generated SVG fallback keeps the *moving image* visible even without Unsplash access.
function demoFallback(which){
 const mountain=which==='mountains',sea=which==='sea';
 const sky=mountain?['#284c7a','#a3bdc5']:sea?['#135b8a','#ffc89a']:['#235773','#eed0ad'];
 const scenery=mountain?`<path d="M-120 930L160 390 385 780 620 250 930 760 1200 350 1400 940V2000H-120Z" fill="#486777"/><path d="M-100 1100L270 630 460 850 770 500 1160 950 1350 670V2000H-100Z" fill="#1e4b59"/><path d="M0 1420Q470 1170 1080 1420V2000H0Z" fill="#1e443b"/>`:
 sea?`<path d="M0 770Q200 730 480 772T1080 754V2000H0Z" fill="#246c8c"/><path d="M0 1000Q340 930 600 1000T1080 960" stroke="#f2ebcb" opacity=".6" stroke-width="17" fill="none"/><path d="M-10 1640Q400 1500 1080 1700V2000H0Z" fill="#234e67"/><path d="M270 1350L520 1350 445 1420H300Z" fill="#e8d9b9"/><path d="M385 1350L385 990 490 1290H385Z" fill="#f4ecd1"/>`:
 `<path d="M0 960L145 810V520H340V750L480 660V390H700V795L880 660V480H1080V2000H0Z" fill="#bd886c"/><path d="M125 850V640H315V820M495 695V490H684V745M905 760V590H1040V770" fill="#455c69"/><path d="M0 1180Q530 940 1080 1200V2000H0Z" fill="#36556b"/><path d="M180 1570L320 1410 430 1510 500 1290 610 1530 850 1330 960 1680" stroke="#bfc7b7" stroke-width="18" opacity=".5" fill="none"/>`;
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="sky" x1="0" y1="0" x2="0.8" y2="1"><stop offset="0" stop-color="${sky[0]}"/><stop offset="1" stop-color="${sky[1]}"/></linearGradient></defs><rect width="1080" height="1920" fill="url(#sky)"/><circle cx="760" cy="470" r="140" fill="#fff1c9" opacity=".68"/>${scenery}<rect width="1080" height="1920" fill="#061b2e" opacity=".10"/></svg>`;
 return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);
}
$('frameImage').onerror=()=>{if($('frameImage').src.startsWith('data:'))return;$('frameImage').src=demoFallback(activeBackground);};
$('frameImage').src=IMAGE_URLS.city;
renderFavoriteList();renderShots();chooseEffect(current.id);
