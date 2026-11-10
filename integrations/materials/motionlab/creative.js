'use strict';
/* Motion Lab / Bon Tours: visual PREPRODUCTION only. No paid APIs or MP4 render. */
const $=id=>document.getElementById(id);
const $$=s=>[...document.querySelectorAll(s)];
const NS='http://www.w3.org/2000/svg';
const STORE='motionlab:creative:selections:v1';
const BG={
 city:'https://static.wixstatic.com/media/7fd7b8_e8133d694a8f4f5a82b665901e9e41f4~mv2.jpg',
 sea:'https://static.wixstatic.com/media/7fd7b8_7b6a1a4a5ae14b1d96e6b79750665aac~mv2.jpg',
 mountains:'https://static.wixstatic.com/media/7fd7b8_b53b4bdba4c14271a663450044559b09~mv2.jpg'
};
const OBJECTS=[
 ['fade-up','Fade Up','Мягкое появление снизу','Спокойное вступление'],
 ['scale-pop','Scale Pop','Масштабирование','Цена / цифра'],
 ['left','Slide Left','Выезд слева','Информационная карточка'],
 ['right','Slide Right','Выезд справа','Дата / город'],
 ['drop','Drop In','Появление сверху','Наклейка / предложение'],
 ['flip','3D Flip','Разворот карточки','Преимущества'],
 ['swivel','Swivel','Поворот и масштаб','Маркер / значок'],
 ['wipe','Mask Wipe','Открытие маской','Логотип / оффер'],
 ['bounce','Bounce In','Упругое появление','Рекламный акцент'],
 ['spin','Spin In','Поворот в кадре','Стикер / значок'],
 ['glow','Soft Glow','Световое проявление','Праздничная акция'],
 ['underline','Line Draw','Рисование линии','Контакты'],
 ['stagger','Layer Cascade','Элементы по очереди','Карточка с ценой'],
 ['float','Gentle Float','Плавное парение','Премиальная сцена'],
 ['marker','Marker Highlight','Подсветка главного','Цена и призыв']
].map(([id,name,ru,use])=>({id,name,ru,use}));
const ROUTES=[
 ['trace','Draw Path','Линия по маршруту','Общий путь'],
 ['dashed','Dotted Route','Пунктир по городам','Много остановок'],
 ['flight','Flight Path','Движение самолета','Перелет'],
 ['sailing','Ship Route','Движение лайнера','Круиз'],
 ['stepping','City by City','Остановки по очереди','Экскурсионный тур'],
 ['highlight','Destination Pulse','Акцент конечного пункта','Главный город'],
 ['arc','Route Arc','Плавные дуги','Длинный путь'],
 ['ribbon','Route Ribbon','Объемная линия','Большой маршрут'],
 ['loop','Round Trip','Возврат к началу','Круговой тур'],
 ['stops','Stop Labels','Появление названий','Список городов']
].map(([id,name,ru,use])=>({id,name,ru,use}));
const MUSIC=[
 ['beat-cut','Beat Cut','Смена на каждый удар','Динамичная нарезка',1,'Смена кадра'],
 ['half-time','Half Time','Через два удара','Спокойная подача',2,'Смена кадра'],
 ['double-time','Double Time','На полударах','Быстрая реклама',.5,'Смена кадра'],
 ['intro-rise','Intro Build','Нарастание во вступлении','Старт ролика',2,'Титр'],
 ['drop-hit','Drop Hit','Акцент каждые восемь долей','Важное сообщение',8,'Акцент'],
 ['phrase-end','Phrase End','Конец музыкальной фразы','Между городами',4,'Переход'],
 ['title-sync','Title Sync','Титр каждые четыре доли','Названия',4,'Титр'],
 ['price-hit','Price Accent','Главный акцент на цене','Финал рекламы',8,'Цена']
].map(([id,name,ru,use,beats,action])=>({id,name,ru,use,beats,action}));
const TEMPLATES=[
 ['new-year','Новогодний тур','Праздничный и динамичный','Свет и яркая цена','cinematic-zoom','lightleak','light-sweep','capsule','glow','stepping','intro-rise'],
 ['cruise','Круиз','Плавный кинематографичный','Лайнер и порты','pan','crossfade','fade-rise','clean','fade-up','sailing','half-time'],
 ['excursion','Экскурсионный тур','Города и маршрут','География и подписи','reveal','match','word-cascade','soft-shadow','stagger','stops','phrase-end'],
 ['flash-deal','Горящее предложение','Быстрый коммерческий ритм','Цена на первом плане','push-through','whip','punch-zoom','bar','scale-pop','trace','price-hit'],
 ['premium','Премиальный отдых','Сдержанный и элегантный','Меньше эффектов','float','crossfade','soft-zoom','luxury','float','arc','half-time']
].map(([id,name,ru,use,camera,transition,title,subtitle,object,route,music])=>({id,name,ru,use,camera,transition,title,subtitle,object,route,music}));
const CATALOG={objects:OBJECTS,routes:ROUTES,music:MUSIC,templates:TEMPLATES};
const LABELS={objects:'06 / ОБЪЕКТЫ',routes:'07 / МАРШРУТЫ',music:'08 / РИТМ',templates:'09 / ШАБЛОНЫ'};
const TITLES={objects:'Анимации объектов',routes:'Анимация маршрута',music:'Музыкальные акценты',templates:'Режиссерские шаблоны'};
const INFO={
 objects:'Плашки, даты, цены, значки, графика и фирменные элементы.',
 routes:'Стилизованные линии, условные остановки и движение символов.',
 music:'Восемь вариантов расстановки монтажных акцентов вручную.',
 templates:'Готовые примеры сочетания визуальных приемов для разных туристических продуктов.'
};
let mode='objects',chosen={objects:'fade-up',routes:'trace',music:'beat-cut',templates:'new-year'};
let saved=[],favorites={objects:[],routes:[],music:[],templates:[]},raf=0,timer=0,active=false,t0=0,hit=-1,taps=[],audioUrl=null,toastTimer=0,cues=[];
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const clean=(s,n=100)=>String(s??'').trim().slice(0,n);
const item=()=>CATALOG[mode].find(x=>x.id===chosen[mode])||CATALOG[mode][0];
const create=(tag,cls,value)=>{const node=document.createElement(tag);node.className=cls||'';if(value!==undefined)node.textContent=value;return node;};
function flash(msg){$('toast').textContent=msg;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),2500);}
function persist(){try{localStorage.setItem(STORE,JSON.stringify({saved,favorites}));}catch{}}
function loadSaved(){try{const v=JSON.parse(localStorage.getItem(STORE)||'{}');if(Array.isArray(v.saved))saved=v.saved.filter(x=>x&&CATALOG[x.module]?.some(y=>y.id===x.effect)).slice(0,60);if(v.favorites&&typeof v.favorites==='object')for(const k of Object.keys(CATALOG))favorites[k]=Array.isArray(v.favorites[k])?v.favorites[k].filter(x=>CATALOG[k].some(y=>y.id===x)).slice(0,40):[];}catch{}}
function stop(){cancelAnimationFrame(raf);clearTimeout(timer);raf=0;active=false;$('play').textContent='▶ Воспроизвести';if(!$('audioPlayer').paused)$('audioPlayer').pause();}
function selectTab(next){
 if(!CATALOG[next])return;
 stop();mode=next;$('search').value='';
 $$('.tab').forEach(b=>{const on=b.dataset.tab===mode;b.classList.toggle('active',on);b.setAttribute('aria-selected',String(on));});
 $('sectionCaption').textContent=LABELS[mode];$('catalogTitle').textContent=TITLES[mode];$('catalogIntro').textContent=INFO[mode];$('catalogCount').textContent=CATALOG[mode].length;
 $('catalogFoot').textContent=mode==='routes'?'Схема условная: реальное географическое положение не проверено.':mode==='music'?'BPM измеряется вручную. Аудиофайл остается в браузере.':'Это только подготовка к монтажу, без экспорта MP4.';
 ['objects','routes','music','templates'].forEach(k=>$(k==='objects'?'objectControls':k==='routes'?'routeControls':k==='music'?'musicControls':'templateControls').hidden=k!==mode);
 $('stage').className='stage mode-'+mode;
 renderCatalog();renderSelection();play();
}
function renderCatalog(){
 const root=$('catalog');root.replaceChildren();const query=$('search').value.toLocaleLowerCase('ru').trim();
 CATALOG[mode].forEach((fx,index)=>{
  if(query&&!(fx.name+' '+fx.ru+' '+fx.use).toLocaleLowerCase('ru').includes(query))return;
  const btn=create('button','effect-card'+(fx.id===chosen[mode]?' current':''));btn.type='button';btn.dataset.id=fx.id;
  btn.append(create('span','num',String(index+1).padStart(2,'0')+' / '+mode.toUpperCase()),create('strong','',fx.name),create('small','',fx.ru));
  if(favorites[mode].includes(fx.id))btn.append(create('span','fav-marker','★'));
  btn.addEventListener('click',()=>{chosen[mode]=fx.id;renderCatalog();renderSelection();play();});
  root.append(btn);
 });
 if(!root.children.length)root.append(create('p','warning','Ничего не найдено.'));
}
function settings(){
 return {duration_s:+$('duration').value,intensity_percent:+$('intensity').value,accent:$('accent').value,background:$('background').value};
}
function renderSelection(){
 const fx=item();$('selectedName').textContent=fx.name;$('selectedDesc').textContent=fx.ru+' · '+fx.use;
 $('selectedCount').textContent=String(CATALOG[mode].indexOf(fx)+1).padStart(2,'0')+' / '+CATALOG[mode].length;
 $('favorite').textContent=favorites[mode].includes(fx.id)?'★':'☆';
 $('durationValue').textContent=(+$('duration').value).toFixed(1)+' с';$('intensityValue').textContent=$('intensity').value+'%';
 $('stage').style.setProperty('--dur',$('duration').value+'s');$('stage').style.setProperty('--dist',Math.round(25+$('intensity').value*.8)+'px');
 $('stage').style.setProperty('--accent',$('accent').value);
 $('stageArt').style.backgroundImage='url("'+BG[$('background').value]+'")';
 const obj=$('objectTarget');obj.className='object-target kind-'+$('objectKind').value;
 $('objectCaption').textContent=$('objectKind').value==='date'?'ДАТЫ ПУТЕШЕСТВИЯ':$('objectKind').value==='logo'?'ТУРИСТИЧЕСКАЯ КОМПАНИЯ':'СПЕЦПРЕДЛОЖЕНИЕ';
 $('objectText').textContent=clean($('objectInput').value,48)||'1399 €';$('objectSub').textContent=clean($('objectSubInput').value,65);
 if(mode==='routes')renderRoute(0);
 if(mode==='music')updateCues();
 if(mode==='templates')renderTemplate();
 renderSaved();
}
function renderSaved(){
 $('choiceCount').textContent=saved.length;
 const root=$('choiceList');root.replaceChildren();
 if(!saved.length){root.append(create('p','','Пока ничего не выбрано.'));return;}
 saved.forEach((s,i)=>{const row=create('div','choice-item');row.append(create('strong','',s.name+' / '+TITLES[s.module]));const del=create('button','','×');del.type='button';del.setAttribute('aria-label','Удалить '+s.name);del.addEventListener('click',()=>{saved.splice(i,1);persist();renderSaved()});row.append(del);root.append(row);});
}
function addSaved(){
 const fx=item();if(saved.length>=60){flash('Максимум 60 выбранных приемов');return;}
 const entry={module:mode,effect:fx.id,name:fx.name,settings:settings()};
 if(mode==='objects')entry.settings.object={kind:$('objectKind').value,text:clean($('objectInput').value,48),subtitle:clean($('objectSubInput').value,65)};
 if(mode==='routes')entry.settings.route_stops=getStops();
 if(mode==='music'){entry.settings.bpm=+clamp(+$('bpm').value||110,50,200);entry.settings.length_s=clamp(+$('musicLength').value||24,5,90);entry.settings.cues=makeCues().slice(0,180);}
 if(mode==='templates')entry.settings.library_preset={...fx};
 saved.push(entry);persist();renderSaved();flash('Добавлено в монтажную подборку');
}
function frame(now){
 if(!active)return;const t=(now-t0)/1000;
 if(mode==='routes')renderRoute((t%clamp(+$('duration').value,.6,6))/clamp(+$('duration').value,.6,6));
 if(mode==='music'){const audio=$('audioPlayer');const position=audio.src&&!audio.paused?audio.currentTime:t;renderBeat(position);if(t>=clamp(+$('musicLength').value||24,5,90)){stop();return;}}
 raf=requestAnimationFrame(frame);
}
function play(){
 stop();
 if(matchMedia('(prefers-reduced-motion: reduce)').matches){if(mode==='routes')renderRoute(1);return;}
 if(mode==='objects'){
  const o=$('objectTarget');o.className='object-target kind-'+$('objectKind').value;
  void o.offsetWidth;o.classList.add('fx-'+chosen.objects);active=true;
  timer=setTimeout(()=>{active=false;$('play').textContent='▶ Повторить';},+$('duration').value*1000+120);
 }else{
  if(mode==='routes')renderRoute(0);
  if(mode==='music'){renderBeat(0);if($('audioPlayer').src){$('audioPlayer').currentTime=0;const p=$('audioPlayer').play();if(p?.catch)p.catch(()=>{});}}
  if(mode==='templates')renderTemplate();
  active=true;t0=performance.now();raf=requestAnimationFrame(frame);
 }
 $('play').textContent='■ Остановить';
}
function svg(tag,attrs,parent,value){
 const node=document.createElementNS(NS,tag);
 for(const [name,val] of Object.entries(attrs||{}))node.setAttribute(name,String(val));
 if(value!==undefined)node.textContent=value;
 if(parent)parent.append(node);return node;
}
function getStops(){
 const out=clean($('routeInput').value,180).split(',').map(s=>clean(s,32)).filter(Boolean).slice(0,6);
 return out.length>=2?out:['Начало','Конец'];
}
function routeGeometry(){
 const names=getStops();
 let pts=names.map((name,i)=>({name,x:30+(i*93)%250,y:458-335*i/(names.length-1)}));
 const effect=chosen.routes;
 let d='M'+pts[0].x+' '+pts[0].y;
 for(let i=1;i<pts.length;i++){
  const a=pts[i-1],b=pts[i];
  if(effect==='arc'||effect==='ribbon'||effect==='flight')d+=' Q'+((a.x+b.x)/2+35)+' '+((a.y+b.y)/2-44)+' '+b.x+' '+b.y;
  else d+=' L'+b.x+' '+b.y;
 }
 if(effect==='loop'){const a=pts.at(-1),b=pts[0];d+=' Q'+(a.x+b.x)/2+' 514 '+b.x+' '+b.y;}
 return {names,pts,d};
}
function renderRoute(progress){
 const g=routeGeometry(),p=clamp(progress,0,1),effect=chosen.routes;
 const trail=$('routeTrail');trail.setAttribute('d',g.d);trail.setAttribute('stroke',$('accent').value);
 trail.setAttribute('stroke-width',effect==='ribbon'?8:3);
 trail.setAttribute('stroke-dasharray',effect==='dashed'?'6 9':'');
 const len=trail.getTotalLength();
 if(effect!=='dashed'){
  trail.setAttribute('stroke-dasharray',String(len));
  trail.setAttribute('stroke-dashoffset',String(len*(1-p)));
 }else{trail.setAttribute('stroke-dashoffset','0');}
 const stops=$('routeStops');stops.replaceChildren();
 g.pts.forEach((point,i)=>{
  const visible=effect==='stepping'||effect==='stops'?p>=i/Math.max(1,g.pts.length-1):true;
  if(!visible)return;
  const activePoint=(effect==='highlight'&&i===g.pts.length-1&&p>.72)||(effect==='stops'&&Math.abs(i/(g.pts.length-1)-p)<.16);
  svg('circle',{cx:point.x,cy:point.y,r:activePoint?10:5,fill:activePoint?$('accent').value:'#e6f1eb',stroke:'#163035','stroke-width':2},stops);
  const right=point.x>200;const tx=right?point.x-7:point.x+7;
  svg('text',{x:tx,y:point.y-13,'font-size':'12','font-weight':'700','text-anchor':right?'end':'start',fill:'#fff',stroke:'#0c2029','stroke-width':'.35','paint-order':'stroke'},stops,point.name);
 });
 const vehicle=$('routeVehicle');vehicle.replaceChildren();
 if(effect==='flight'||effect==='sailing'||effect==='trace'||effect==='loop'||effect==='arc'||effect==='ribbon'){
  const point=trail.getPointAtLength(len*p);
  svg('circle',{cx:point.x,cy:point.y,r:effect==='sailing'?10:7,fill:$('accent').value,opacity:.27},vehicle);
  svg('text',{x:point.x,y:point.y+3,'font-size':'16','text-anchor':'middle'},vehicle,effect==='sailing'?'⛴':effect==='flight'?'✈':'●');
 }
}
function makeCues(){
 const bpm=clamp(+$('bpm').value||110,50,200),length=clamp(+$('musicLength').value||24,5,90);
 const fx=CATALOG.music.find(x=>x.id===chosen.music),beat=60/bpm;
 let times=[];
 if(fx.id==='price-hit'){const t=Math.max(0,length-2*beat);times=[Math.floor(t/(beat*fx.beats))*(beat*fx.beats)];}
 else{
  const step=beat*fx.beats;
  for(let t=0;t<length&&times.length<180;t+=step)times.push(t);
  if(fx.id==='intro-rise'){
   times=times.filter((t,i)=>i<=4);
   const last=times.at(-1)||0;
   for(let t=last+beat;t<Math.min(length,last+4*beat);t+=beat)times.push(t);
  }
 }
 return times.map((t,i)=>({time_s:+t.toFixed(3),action:fx.action,beat_index:i+1}));
}
function updateCues(){
 cues=makeCues();
 const list=$('cueList');list.replaceChildren();
 cues.slice(0,30).forEach(c=>list.append(create('span','',c.time_s.toFixed(2)+' c · '+c.action)));
 if(cues.length>30)list.append(create('span','','+ '+(cues.length-30)));
}
function renderBeat(seconds){
 const t=clamp(seconds,0,clamp(+$('musicLength').value||24,5,90));
 $('beatTime').textContent=String(Math.floor(t/60)).padStart(2,'0')+':'+String(Math.floor(t%60)).padStart(2,'0')+'.'+String(Math.floor(t%1*10));
 $('beatAction').textContent=CATALOG.music.find(x=>x.id===chosen.music).ru;
 const nearest=cues.findIndex(c=>Math.abs(c.time_s-t)<.12);
 if(nearest!==hit){hit=nearest;$('beatVisual').classList.toggle('hit',hit>=0);}
}
function renderTemplate(){
 const v=CATALOG.templates.find(x=>x.id===chosen.templates);
 $('templateCategory').textContent=v.name.toUpperCase();$('templateHeading').textContent=v.ru;
 $('templateCamera').textContent='Камера: '+v.camera;$('templateTransition').textContent='Переход: '+v.transition;
 $('templateTitle').textContent='Титр: '+v.title;
}
function payload(){
 return {
  schema:'bontours.motionlab.creative-plan/v1',status:'DRAFT_NOT_DELIVERED',
  created_at:new Date().toISOString(),
  purpose:'preproduction_only',
  rendering_authorized:false,paid_services_authorized:false,publishing_authorized:false,
  active_selection:{module:mode,effect:item().id,settings:settings()},
  choices:saved.map(x=>structuredClone(x)),
  disclaimers:['Route geometry is schematic, not verified against real coordinates.',
   'Music cues are manual BPM-based suggestions, not analyzed or synchronized source audio.',
   'Host/agent acceptance is NOT established by this browser JSON export.']
 };
}
function download(){
 const blob=new Blob([JSON.stringify(payload(),null,2)],{type:'application/json'});
 const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='motion-lab-creative-plan.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);flash('Черновик ТЗ сохранен на компьютер');
}
async function copy(){
 try{await navigator.clipboard.writeText(JSON.stringify(payload(),null,2));flash('JSON скопирован');}
 catch{flash('Копирование недоступно. Используйте скачивание.');}
}
function onTap(){
 const now=performance.now();if(taps.length&&now-taps.at(-1)>2300)taps=[];
 taps.push(now);taps=taps.slice(-9);
 if(taps.length>=4){
  const intervals=taps.slice(1).map((v,i)=>v-taps[i]).filter(n=>n>275&&n<1300).sort((a,b)=>a-b);
  if(intervals.length>=3){
   const median=intervals[Math.floor(intervals.length/2)];
   $('bpm').value=clamp(Math.round(60000/median),50,200);renderSelection();flash('BPM по нажатиям: '+$('bpm').value);
  }
 }else flash('Нажмите кнопку еще несколько раз в такт');
}
function onAudio(e){
 if(audioUrl)URL.revokeObjectURL(audioUrl);audioUrl=null;
 const file=e.target.files?.[0];if(!file)return;
 if(!file.type.startsWith('audio/')){flash('Выберите аудиофайл');return;}
 if(file.size>40*1024*1024){flash('Файл слишком большой (максимум 40 МБ)');return;}
 audioUrl=URL.createObjectURL(file);$('audioPlayer').src=audioUrl;flash('Аудио открыто локально. Ритм задается вручную.');
}
function init(){
 loadSaved();renderSaved();
 $$('.tab').forEach(b=>b.addEventListener('click',()=>selectTab(b.dataset.tab)));
 $('search').addEventListener('input',renderCatalog);
 $('play').addEventListener('click',()=>active?stop():play());
 $('favorite').addEventListener('click',()=>{
  const id=chosen[mode],arr=favorites[mode],idx=arr.indexOf(id);
  if(idx>=0)arr.splice(idx,1);else arr.push(id);persist();renderCatalog();renderSelection();
 });
 ['duration','intensity','accent','background','objectKind','objectInput','objectSubInput','routeInput','bpm','musicLength'].forEach(id=>{
  $(id).addEventListener('input',()=>{renderSelection();if(mode==='objects')play();});
 });
 $('saveChoice').addEventListener('click',addSaved);$('downloadPlan').addEventListener('click',download);
 $('copyPlan').addEventListener('click',copy);$('tapBeat').addEventListener('click',onTap);
 $('localAudio').addEventListener('change',onAudio);
 window.addEventListener('pagehide',()=>{if(audioUrl)URL.revokeObjectURL(audioUrl);stop();});
 selectTab('objects');
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
