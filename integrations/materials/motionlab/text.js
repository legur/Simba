/* Motion Lab · Type Studio — 15 deterministic Anime.js-driven title/offer effects.
   All user text stays in the browser. No image/video rendering is implied. */
'use strict';
const FOTO={
  city:'https://static.wixstatic.com/media/7fd7b8_e8133d694a8f4f5a82b665901e9e41f4~mv2.jpg',
  sea:'https://static.wixstatic.com/media/7fd7b8_7b6a1a4a5ae14b1d96e6b79750665aac~mv2.jpg',
  mountains:'https://static.wixstatic.com/media/7fd7b8_b53b4bdba4c14271a663450044559b09~mv2.jpg'
};
const GROUP={cinematic:'Титры',dynamic:'Динамичные',offers:'Цены и даты'};
const SAMPLES={
  cinematic:['Новый год в Баварии','Шесть ночей, экскурсии и атмосфера праздника'],
  dynamic:['Европа ждет!','Выбирайте свое путешествие'],
  offers:['599 €','15–21 ноября · осталось 2 места']
};
const FX=[
  {id:'fade-rise',en:'Fade Rise',ru:'Появление снизу',group:'cinematic',use:'Начало рилса',description:'Мягкое появление титра снизу с нарастанием прозрачности.'},
  {id:'soft-zoom',en:'Soft Zoom',ru:'Плавное приближение',group:'cinematic',use:'Название тура',description:'Текст увеличивается до нормального размера без дрожания и рывков.'},
  {id:'blur-focus',en:'Focus Reveal',ru:'Выход из размытия',group:'cinematic',use:'Атмосферные кадры',description:'Буквы постепенно обретают резкость, сохраняя читаемость.'},
  {id:'mask-up',en:'Mask Curtain',ru:'Раскрытие маской',group:'cinematic',use:'Заголовок города',description:'Заголовок открывается снизу вверх внутри невидимой маски.'},
  {id:'light-sweep',en:'Light Sweep',ru:'Световой акцент',group:'cinematic',use:'Премиальные туры',description:'Над текстом проходит световой отблеск, одновременно проявляя титр.'},
  {id:'slide-left',en:'Slide In',ru:'Выезд справа',group:'dynamic',use:'Смена темпа',description:'Текст уверенно въезжает справа и мягко останавливается.'},
  {id:'bounce-pop',en:'Bounce Pop',ru:'Пружинное появление',group:'dynamic',use:'Короткий рекламный акцент',description:'Титр быстро вырастает, слегка превышает размер и возвращается.'},
  {id:'punch-zoom',en:'Punch Zoom',ru:'Ударный масштаб',group:'dynamic',use:'Сильный хук',description:'Крупный текст уменьшается до рабочего размера с коротким ударным акцентом.'},
  {id:'rotate-in',en:'Rotate In',ru:'Поворот и вход',group:'dynamic',use:'Энергичный монтаж',description:'Надпись появляется с небольшим поворотом и выравнивается.'},
  {id:'word-cascade',en:'Word Cascade',ru:'Каскад слов',group:'dynamic',use:'Перечисление преимуществ',description:'Каждое слово появляется отдельно в заданной последовательности.'},
  {id:'counter',en:'Count Up',ru:'Счетчик цены',group:'offers',use:'Цена тура',description:'Число увеличивается от нуля до указанной цены с сохранением валюты.'},
  {id:'date-flip',en:'Date Flip',ru:'Переключение даты',group:'offers',use:'Даты поездки',description:'Отдельные элементы даты последовательно переворачиваются и фиксируются.'},
  {id:'line-draw',en:'Underline Draw',ru:'Линия под текстом',group:'offers',use:'Стоимость и включения',description:'Текст проявляется, и под ним плавно вырастает акцентная линия.'},
  {id:'badge-reveal',en:'Badge Reveal',ru:'Выход плашки',group:'offers',use:'Акции и спецпредложения',description:'Компактная плашка открывается и удерживает цену без перекрытия кадра.'},
  {id:'letter-wave',en:'Letter Wave',ru:'Волна по буквам',group:'offers',use:'Названия и цифры',description:'Буквы появляются с последовательным вертикальным движением.'}
];
const $=id=>document.getElementById(id);
const cl=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const lerp=(a,b,x)=>a+(b-a)*x;
const out=x=>1-Math.pow(1-cl(x),3);
const io=x=>x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;
const back=x=>{const t=cl(x);return 1+2.70158*Math.pow(t-1,3)+1.70158*Math.pow(t-1,2)};
const piece=(p,at=.0,len=.75)=>cl((p-at)/len);
const splitWords=txt=>txt.trim().split(/\s+/u).filter(Boolean).slice(0,30);
const splitLetters=txt=>[...txt].slice(0,80);
const css=(el,v)=>Object.assign(el.style,v);
const escapeText=txt=>String(txt||'').slice(0,120);
let filter='all',selected=FX[0].id,background='city',accent='lime',position='middle',duration=1800,scale=100;
let favorites=new Set(),userEdited=false,composition=null,anim=null,raf=0,loopTimeout=0,sequence=0;
let previousCategory='cinematic';
function current(){return FX.find(x=>x.id===selected)||FX[0]}
function defaultCopy(group){return SAMPLES[group]||SAMPLES.cinematic}
function resetCopy(){const [a,b]=defaultCopy(current().group);$('mainText').value=a;$('secondText').value=b;userEdited=false;rebuild();toast('Демонстрационный текст восстановлен')}
function make(cls,txt='',parent=null){const el=document.createElement('div');el.className=cls;if(txt)el.textContent=txt;if(parent)parent.append(el);return el}
function buildTokens(text,mode='word'){
  const row=make('type-main', '', composition);
  const values=mode==='letter'?splitLetters(text):splitWords(text);
  const nodes=values.map((value,i)=>{
    const sp=document.createElement('span');sp.className=mode==='letter'?'glyph':'token';sp.textContent=value;
    if(i&&mode!=='letter')row.append(document.createTextNode(' '));
    row.append(sp);return sp;
  });
  return {row,nodes};
}
function buildStage(){
  const fx=current();const isOffer=fx.group==='offers';
  const top=$('typeLayer');top.replaceChildren();top.className=`type-layer kind-${fx.group} place-${position}`;
  top.style.setProperty('--main-scale',String(scale/100));
  const main=escapeText($('mainText').value.trim()||defaultCopy(fx.group)[0]);
  const second=escapeText($('secondText').value.trim());
  composition=make('type-composition', '', top);
  // Subtitle word effects moved to the unified Subtitle Studio.
  const data={id:fx.id,main,second,node:null,sub:null,tokens:[],accent:null,extra:null,parts:[]};
  if(['word-cascade','karaoke','active-pop','highlight-strip','word-reveal'].includes(fx.id)){
    const built=buildTokens(main,'word');data.node=built.row;data.tokens=built.nodes;
  }else if(fx.id==='letter-wave'){
    const built=buildTokens(main,'letter');data.node=built.row;data.tokens=built.nodes;
  }else if(fx.id==='date-flip'){
    data.node=make('type-main','',composition);
    const parts=main.split(/\s*[–—-]\s*|\s+/u).filter(Boolean).slice(0,5);
    data.parts=parts.map(token=>{const el=document.createElement('span');el.className='date-part';el.textContent=token;data.node.append(el);return el});
  }else{data.node=make('type-main',main,composition)}
  if(fx.id==='badge-reveal')data.node.classList.add('badge-main');
  if(['line-draw','light-sweep'].includes(fx.id))data.accent=make('effect-underline','',composition);
  if(fx.id==='light-sweep')data.extra=make('effect-sheen','',top);
  if(second){data.sub=make('type-sub',second,composition)}
  // Subtitle blocks are pinned above the lower UI safe area, never across the final contacts.
  composition.dataset.effect=fx.id;
  return data;
}
function safeSet(el,opacity=1,transform='none',filter='none'){
  if(!el)return;el.style.opacity=String(cl(opacity));el.style.transform=transform;el.style.filter=filter;
}
function draw(p){
  if(!composition)return;
  const d=composition,p0=cl(p),start=piece(p0,0,.72),e=out(start),last=piece(p0,.34,.58);
  const n=d.tokens.length,words=d.tokens,main=d.node,sub=d.sub;
  // Reset local token styles; deterministic seeking must give identical frames regardless of history.
  for(const el of words){el.style.opacity='1';el.style.transform='none';el.style.filter='none';el.classList.remove('on','highlight-token','muted-token')}
  d.node.style.clipPath='none';
  if(d.accent)css(d.accent,{opacity:'1',transform:'scaleX(1)'});
  if(d.extra)css(d.extra,{opacity:'0',transform:'translateX(-80%)'});
  switch(d.id){
    case 'fade-rise':safeSet(main,e,`translateY(${Math.round((1-e)*45)}px)`);break;
    case 'soft-zoom':safeSet(main,e,`scale(${lerp(.76,1,e).toFixed(4)})`);break;
    case 'blur-focus':safeSet(main,e,`scale(${lerp(1.08,1,e).toFixed(4)})`,`blur(${((1-e)*17).toFixed(2)}px)`);break;
    case 'mask-up':safeSet(main,1,`translateY(${(1-e)*18}px)`);main.style.clipPath=`inset(${(1-e)*100}% 0 0 0)`;break;
    case 'light-sweep':
      safeSet(main,out(piece(p0,0,.61)));
      d.accent.style.transform=`scaleX(${out(piece(p0,.16,.65))})`;
      d.extra.style.opacity=String(Math.sin(Math.PI*cl(piece(p0,.1,.82)))*.84);
      d.extra.style.transform=`translateX(${lerp(-115,140,piece(p0,.06,.92))}%)`;
      break;
    case 'slide-left':safeSet(main,e,`translateX(${(1-e)*125}px)`);break;
    case 'bounce-pop':{const x=piece(p0,0,.76),k=back(x);safeSet(main,x,`scale(${lerp(.35,1,k)})`);break}
    case 'punch-zoom':safeSet(main,e,`scale(${lerp(1.75,1,e)})`);break;
    case 'rotate-in':safeSet(main,e,`rotate(${(1-e)*-19}deg) translateY(${(1-e)*20}px)`);break;
    case 'word-cascade':words.forEach((el,i)=>{const q=out(piece(p0,i/Math.max(1,n)*.50,.35));safeSet(el,q,`translateY(${(1-q)*32}px) rotate(${(1-q)*4}deg)`)});break;
    case 'karaoke':{
      safeSet(main,1);const active=Math.min(n-1,Math.floor(p0*n));
      words.forEach((el,i)=>{el.classList.toggle('on',i===active);el.classList.toggle('muted-token',i>active);css(el,{opacity: i>active?'.62':'1',transform:i===active?'translateY(-2px) scale(1.07)':'none'})});break;
    }
    case 'active-pop':{
      const a=Math.min(n-1,Math.floor(p0*n));words.forEach((el,i)=>{const frac=(p0*n-i);el.classList.toggle('on',i===a);safeSet(el,1,i===a?`scale(${1+.16*Math.sin(Math.PI*cl(frac))})`:'scale(1)')});break;
    }
    case 'caption-swap':{
      const toks=splitWords(d.main);const size=Math.max(2,Math.ceil(toks.length/3));const groups=[];
      for(let i=0;i<toks.length;i+=size)groups.push(toks.slice(i,i+size).join(' '));
      const idx=Math.min(groups.length-1,Math.floor(p0*groups.length));
      const q=cl((p0*groups.length-idx)*4);main.textContent=groups[idx]||d.main;
      safeSet(main,Math.min(q,1),`translateY(${(1-out(q))*17}px)`);break;
    }
    case 'highlight-strip':{
      const active=Math.min(n-1,Math.floor(p0*n));words.forEach((el,i)=>{el.classList.toggle('highlight-token',i===active);el.classList.toggle('muted-token',i>active)});break;
    }
    case 'word-reveal':words.forEach((el,i)=>{const q=out(piece(p0,i/Math.max(n,1)*.7,.25));safeSet(el,q,`translateY(${(1-q)*15}px)`)});break;
    case 'counter':{
      const matched=d.main.match(/\d[\d\s.,]*/u);let count=Math.min(1,out(piece(p0,0,.9)));
      if(matched){const raw=matched[0].replace(/[\s.,]/gu,'');const num=Number(raw);
        if(Number.isFinite(num)&&num<=10000000){const display=Math.round(num*count).toLocaleString('ru-RU');main.textContent=d.main.slice(0,matched.index)+display+d.main.slice(matched.index+matched[0].length)}
      }
      safeSet(main,.45+.55*count,`scale(${lerp(.92,1,count)})`);break;
    }
    case 'date-flip':d.parts.forEach((el,i)=>{const q=out(piece(p0,i/Math.max(d.parts.length,1)*.51,.45));safeSet(el,q,`perspective(380px) rotateX(${(1-q)*-88}deg) translateY(${(1-q)*9}px)`)});break;
    case 'line-draw':safeSet(main,e,`translateY(${(1-e)*16}px)`);css(d.accent,{opacity:String(cl(piece(p0,.16,.5))),transform:`scaleX(${out(piece(p0,.2,.66))})`});break;
    case 'badge-reveal':{const q=out(piece(p0,0,.78));safeSet(main,q,`scaleX(${lerp(.05,1,q)}) scaleY(${lerp(.8,1,q)})`);break}
    case 'letter-wave':words.forEach((el,i)=>{const q=out(piece(p0,i/Math.max(n,1)*.56,.3));const bump=(1-q)*33;safeSet(el,q,`translateY(${bump}px) rotate(${(1-q)*10}deg)`)});break;
  }
  if(sub)safeSet(sub,out(last),`translateY(${(1-out(last))*10}px)`);
  $('progressBar').style.width=(p0*100).toFixed(2)+'%';
  $('stageTime').textContent=((duration*p0)/1000).toFixed(2)+' с';
}
function stop(){sequence++;if(anim){try{anim.pause()}catch{}anim=null}if(raf){cancelAnimationFrame(raf);raf=0}if(loopTimeout){clearTimeout(loopTimeout);loopTimeout=0}$('playButton').disabled=false}
function play(){stop();const currentSequence=sequence;draw(0);$('playButton').disabled=true;
  const finished=()=>{if(currentSequence!==sequence)return;anim=null;raf=0;$('playButton').disabled=false;draw(1);if($('loopPreview').checked)loopTimeout=setTimeout(play,600)};
  const model={progress:0};
  if(window.anime&&typeof window.anime.animate==='function'){
    try{anim=window.anime.animate(model,{progress:1,duration,ease:'linear',onUpdate:()=>{if(sequence===currentSequence)draw(model.progress)},onComplete:finished});return}catch(err){console.warn('Anime.js unavailable, fallback to requestAnimationFrame',err)}
  }
  const start=performance.now();const frame=now=>{if(sequence!==currentSequence)return;const p=cl((now-start)/duration);draw(p);if(p<1)raf=requestAnimationFrame(frame);else finished()};raf=requestAnimationFrame(frame);
}
function rebuild(){stop();composition=buildStage();draw(0)}
function choice(id){const fx=FX.find(x=>x.id===id);if(!fx)return;
  const oldGroup=current().group;selected=id;
  if(!userEdited&&fx.group!==oldGroup){const [a,b]=defaultCopy(fx.group);$('mainText').value=a;$('secondText').value=b}
  $('activeName').textContent=fx.en;$('activeDescription').textContent=fx.description;
  $('effectIndex').textContent=`${String(FX.indexOf(fx)+1).padStart(2,'0')} / ${FX.length}`;
  $('typeLabel').textContent=GROUP[fx.group];$('usageLabel').textContent=fx.use;
  $('favButton').classList.toggle('selected',favorites.has(selected));$('favButton').textContent=favorites.has(selected)?'★':'☆';
  $('favButton').setAttribute('aria-pressed',String(favorites.has(selected)));
  // Default subtitle positioning is within safe zone, independent of title preference.
  renderCards();rebuild();play();
}
function renderCards(){const cards=FX.filter(fx=>filter==='all'||fx.group===filter);$('visibleCount').textContent=String(cards.length);
  const grid=$('effectGrid');grid.replaceChildren();
  cards.forEach(fx=>{
    const article=make('effect-card'+(fx.id===selected?' active':'') );article.dataset.effect=fx.id;
    const trigger=document.createElement('button');trigger.type='button';trigger.className='effect-click';trigger.setAttribute('aria-label','Предпросмотр: '+fx.ru);trigger.setAttribute('aria-pressed',String(fx.id===selected));
    const visual=make('card-visual','',trigger);
    make('card-number',String(FX.indexOf(fx)+1).padStart(2,'0'),visual);
    make('card-text',fx.group==='offers'?'599 €':'ТИТР',visual);
    make('mini-accent','',visual);
    const details=make('card-details','',article);const labels=make('','',details);
    make('',fx.en,labels).className='card-title';make('',fx.ru,labels);
    const fav=document.createElement('button');fav.className='card-fav'+(favorites.has(fx.id)?' selected':'');fav.type='button';fav.textContent=favorites.has(fx.id)?'★':'☆';fav.dataset.favorite=fx.id;fav.title='Добавить или убрать из подборки';fav.setAttribute('aria-label',favorites.has(fx.id)?'Убрать из подборки':'Добавить в подборку');fav.setAttribute('aria-pressed',String(favorites.has(fx.id)));
    details.append(fav);article.prepend(trigger);grid.append(article);
  });
}
function persist(){try{localStorage.setItem('motionlab:text:favorites',JSON.stringify([...favorites]))}catch{}}
function updateFavorites(){persist();const list=$('favoriteList');list.replaceChildren();const picked=FX.filter(fx=>favorites.has(fx.id));$('favoritesCount').textContent=String(picked.length);
  if(!picked.length)make('empty','Пока ничего не выбрано. Отметьте звездочкой интересные эффекты.',list);
  picked.forEach(fx=>{const tag=make('favorite-chip','',list);make('',fx.en,tag);const rem=document.createElement('button');rem.type='button';rem.textContent='×';rem.dataset.remove=fx.id;rem.setAttribute('aria-label','Убрать '+fx.en);tag.append(rem)});
  $('favButton').classList.toggle('selected',favorites.has(selected));$('favButton').textContent=favorites.has(selected)?'★':'☆';
  renderCards();
}
function toggleFavorite(id){if(!FX.some(x=>x.id===id))return;if(favorites.has(id))favorites.delete(id);else favorites.add(id);updateFavorites()}
let toastTimer=null;function toast(message){const box=$('toast');box.textContent=message;box.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>box.classList.remove('show'),2300)}
function exportPayload(){return {schema:'bontours.motionlab.text-effects/v1',module:'titles-and-text',stage:'editorial-handoff',notes:'Демонстрационный выбор. Нужна интеграция в видео-рендерер и привязка субтитров к реальной речи.',selected_effect:{id:selected,name:current().en,category:current().group},favorite_effects:FX.filter(x=>favorites.has(x.id)).map(x=>({id:x.id,name:x.en,category:x.group})),preview:{main_text:$('mainText').value,second_text:$('secondText').value,duration_ms:duration,scale_percent:scale,position,color:accent,background},total_effects:FX.length};}
function downloadJSON(obj,filename){const blob=new Blob([JSON.stringify(obj,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),7000)}
async function copyBrief(){const picked=FX.filter(x=>favorites.has(x.id));const name=picked.length?picked.map(x=>x.en+' ('+GROUP[x.group]+')').join(', '):current().en;const s=`Motion Lab — Титры и текст\nЭффекты: ${name}\nТекст: ${$('mainText').value.trim()}\nДополнительная строка: ${$('secondText').value.trim()}\nДлительность: ${(duration/1000).toFixed(1)} с\nРазмер: ${scale}%\nРасположение: ${position}\nЦвет: ${accent}\nВАЖНО: В этой версии это монтажное ТЗ, автоматического рендера субтитров нет. Таймкоды слов нужно получать из аудио.`;
  try{await navigator.clipboard.writeText(s);toast('ТЗ скопировано')}catch{toast('Копирование недоступно. Используйте экспорт JSON')}
}
function updatePreviewBackground(){const img=FOTO[background];$('stageBackdrop').style.backgroundImage=`url("${img}")`;$('textStage').setAttribute('aria-label','Анимированный титр. Фон: '+({city:'город',sea:'море',mountains:'горы'}[background]));}
function init(){try{const prev=JSON.parse(localStorage.getItem('motionlab:text:favorites')||'[]');if(Array.isArray(prev))favorites=new Set(prev.filter(x=>FX.some(y=>y.id===x)))}catch{}
  updatePreviewBackground();renderCards();updateFavorites();composition=buildStage();draw(0);
  $('effectGrid').addEventListener('click',ev=>{const fav=ev.target.closest('[data-favorite]');if(fav){toggleFavorite(fav.dataset.favorite);return}const trigger=ev.target.closest('.effect-click');if(trigger){const item=trigger.closest('[data-effect]');if(item)choice(item.dataset.effect)}});
  document.querySelectorAll('[data-filter]').forEach(btn=>btn.addEventListener('click',()=>{filter=btn.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('selected',b===btn));renderCards()}));
  document.querySelectorAll('[data-bg]').forEach(btn=>btn.addEventListener('click',()=>{background=btn.dataset.bg;document.querySelectorAll('[data-bg]').forEach(b=>b.classList.toggle('selected',b===btn));updatePreviewBackground();play()}));
  document.querySelectorAll('[data-position]').forEach(btn=>btn.addEventListener('click',()=>{position=btn.dataset.position;document.querySelectorAll('[data-position]').forEach(b=>b.classList.toggle('selected',b===btn));rebuild();play()}));
  const colors={lime:'#cbf37b',gold:'#e8bd65',white:'#f6f9f3'};
  document.querySelectorAll('[data-color]').forEach(btn=>btn.addEventListener('click',()=>{accent=btn.dataset.color;document.querySelectorAll('[data-color]').forEach(b=>{const on=b===btn;b.classList.toggle('selected',on);b.setAttribute('aria-pressed',String(on))});$('textStage').style.setProperty('--highlight',colors[accent]);play()}));
  ['mainText','secondText'].forEach(id=>$(id).addEventListener('input',()=>{userEdited=true;rebuild();play()}));
  $('durationRange').addEventListener('input',ev=>{duration=Number(ev.target.value);$('durationLabel').textContent=(duration/1000).toFixed(1)+' с'});
  $('durationRange').addEventListener('change',play);
  $('scaleRange').addEventListener('input',ev=>{scale=Number(ev.target.value);$('scaleLabel').textContent=scale+'%';$('typeLayer').style.setProperty('--main-scale',String(scale/100))});
  $('scaleRange').addEventListener('change',play);
  $('safeZone').addEventListener('change',ev=>{$('safeGuides').hidden=!ev.target.checked});
  $('playButton').addEventListener('click',play);$('resetButton').addEventListener('click',()=>{resetCopy();play()});
  $('favButton').addEventListener('click',()=>toggleFavorite(selected));
  $('copyBrief').addEventListener('click',copyBrief);$('exportJson').addEventListener('click',()=>{downloadJSON(exportPayload(),'motion-lab-text-effects.json');toast('Подборка JSON сохранена')});
  $('clearFavorites').addEventListener('click',()=>{favorites.clear();updateFavorites();toast('Подборка очищена')});
  $('favoriteList').addEventListener('click',ev=>{const rem=ev.target.closest('[data-remove]');if(rem)toggleFavorite(rem.dataset.remove)});
  window.addEventListener('pagehide',stop);
  if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches)setTimeout(play,550);
}
window.__textStudio={ids:FX.map(fx=>fx.id),groups:GROUP,select:choice,drawAt:p=>{stop();draw(cl(p))},payload:exportPayload,reset:resetCopy};
document.addEventListener('DOMContentLoaded',init);
