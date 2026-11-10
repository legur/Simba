/* Motion Lab — Anime.js 4 transition showcase, 30 interactive demonstrations */
'use strict';
const PHOTO = {
  cruise: 'https://static.wixstatic.com/media/7fd7b8_7b6a1a4a5ae14b1d96e6b79750665aac~mv2.jpg',
  venice: 'https://static.wixstatic.com/media/7fd7b8_e8133d694a8f4f5a82b665901e9e41f4~mv2.jpg',
  mountains: 'https://static.wixstatic.com/media/7fd7b8_b53b4bdba4c14271a663450044559b09~mv2.jpg',
  landscape: 'https://static.wixstatic.com/media/7fd7b8_ac85605a20f74c278e350dede74234a2~mv2.jpg',
  paris: 'https://static.wixstatic.com/media/7fd7b8_9fcd4555ad3d441cbc681ad231c59520~mv2.jpg',
  coast: 'https://static.wixstatic.com/media/7fd7b8_c354cdd6941b4f2f896960c1ab57d543~mv2.jpg'
};
const PRESETS = {
  alps: { photos: [PHOTO.mountains, PHOTO.landscape], labels: [['01 / NATURE','Мир за<br>горизонтом','ALPINE JOURNEY'],['02 / ESCAPE','Время<br>открывать','TRAVEL MOMENTS']] },
  sea: { photos: [PHOTO.cruise, PHOTO.coast], labels: [['01 / CRUISE','Навстречу<br>морю','SEA JOURNEY'],['02 / COAST','Новые<br>берега','MEDITERRANEAN']] },
  city: { photos: [PHOTO.venice, PHOTO.paris], labels: [['01 / ITALY','Города<br>и истории','EUROPEAN ROUTES'],['02 / FRANCE','Новые<br>впечатления','DISCOVER EUROPE']] }
};
const GROUPS = {all:'Все',cinematic:'Кинематографичные',dynamic:'Динамичные',elegant:'Элегантные',creative:'Креативные',travel:'Для путешествий'};
const EFFECTS = [
  {id:'crossfade',en:'Crossfade',ru:'Плавное растворение',category:'elegant',kind:'Спокойный',difficulty:'Простой',use:'Пейзажи, природа',description:'Первый кадр плавно растворяется, раскрывая второй без резких движений.'},
  {id:'push',en:'Slide / Push',ru:'Сдвиг кадров',category:'dynamic',kind:'Энергичный',difficulty:'Простой',use:'Маршрут по городам',description:'Следующий кадр вытесняет предыдущий в едином направлении.'},
  {id:'zoom',en:'Zoom Through',ru:'Переход через зум',category:'dynamic',kind:'Динамичный',difficulty:'Средний',use:'Анонсы туров',description:'Первый кадр резко увеличивается, второй раскрывается из увеличения.'},
  {id:'whip',en:'Whip Pan',ru:'Быстрая панорама',category:'dynamic',kind:'Энергичный',difficulty:'Средний',use:'Города, экскурсии',description:'Стремительный боковой поворот с размытием направления движения.'},
  {id:'circle',en:'Circle Reveal',ru:'Круговое раскрытие',category:'creative',kind:'Выразительный',difficulty:'Средний',use:'Новая локация',description:'Следующая сцена появляется через расширяющийся круг.'},
  {id:'diagonal',en:'Diagonal Wipe',ru:'Диагональное открытие',category:'elegant',kind:'Графичный',difficulty:'Простой',use:'Подборки путешествий',description:'Диагональная плоскость открывает следующий кадр.'},
  {id:'flash',en:'Light Flash',ru:'Световая вспышка',category:'dynamic',kind:'Яркий',difficulty:'Простой',use:'Праздники, события',description:'Короткий световой импульс маскирует смену кадра.'},
  {id:'blur',en:'Blur Dissolve',ru:'Размытие и фокус',category:'elegant',kind:'Мягкий',difficulty:'Средний',use:'Атмосферные сцены',description:'Первый кадр теряет резкость, а второй выходит в фокус.'},
  {id:'flip',en:'3D Flip',ru:'Трехмерный разворот',category:'creative',kind:'Игривый',difficulty:'Средний',use:'Сравнения мест',description:'Один кадр переворачивается и открывает другой.'},
  {id:'parallax',en:'Parallax Drift',ru:'Многоплановый сдвиг',category:'cinematic',kind:'Кинематографичный',difficulty:'Средний',use:'Премиальные путешествия',description:'Изображения движутся с разной скоростью и создают ощущение глубины.'},
  {id:'shutter',en:'Vertical Shutters',ru:'Вертикальные створки',category:'creative',kind:'Ритмичный',difficulty:'Сложный',use:'Монтаж под музыку',description:'Новая сцена поэтапно появляется через вертикальные полосы.'},
  {id:'glitch',en:'Glitch Cut',ru:'Цифровой сбой',category:'creative',kind:'Резкий',difficulty:'Сложный',use:'Современная реклама',description:'Цветовые и геометрические сдвиги создают короткую цифровую помеху.'},
  {id:'split',en:'Split Doors',ru:'Раздвижные створки',category:'creative',kind:'Театральный',difficulty:'Средний',use:'Открытие сюжета',description:'Предыдущий кадр раскрывается двумя половинами, словно двери.'},
  {id:'rotate',en:'Spin Transition',ru:'Вращение сцены',category:'dynamic',kind:'Активный',difficulty:'Средний',use:'Смена ритма',description:'Сцены поворачиваются навстречу друг другу и сменяются.'},
  {id:'tiles',en:'Mosaic Tiles',ru:'Мозаика кадров',category:'creative',kind:'Декоративный',difficulty:'Сложный',use:'Праздничные рилсы',description:'Следующая сцена собирается из квадратных плиток.'},
  {id:'portal',en:'Portal Transition',ru:'Переход через портал',category:'cinematic',kind:'Кинематографичный',difficulty:'Средний',use:'Арки, окна, двери',description:'Следующий кадр открывается в арочном портале, затем занимает весь экран. Имитация перехода через архитектурный проем.'},
  {id:'textmask',en:'Text Mask',ru:'Переход через надпись',category:'creative',kind:'Титульный',difficulty:'Средний',use:'Названия направлений',description:'Сквозь огромную надпись видно следующий кадр; масштаб текста увеличивается, открывая сцену.'},
  {id:'lightleak',en:'Light Leak',ru:'Солнечный засвет',category:'cinematic',kind:'Теплый',difficulty:'Средний',use:'Круизы, солнце, море',description:'Теплая полоса света скользит по сцене, одновременно открывая второй кадр.'},
  {id:'speedramp',en:'Speed Ramp',ru:'Разгон и торможение',category:'dynamic',kind:'Скоростной',difficulty:'Средний',use:'Динамичный маршрут',description:'Движение ускоряется к смене кадра и плавно замедляется после нее. Это имитация монтажного приема с неподвижными фото.'},
  {id:'particles',en:'Particle Dissolve',ru:'Рассыпание на частицы',category:'creative',kind:'Праздничный',difficulty:'Сложный',use:'Новый год, впечатления',description:'Старый кадр разбивается на небольшие фрагменты, которые разлетаются и открывают следующий.'},
  {id:'ripple',en:'Water Ripple',ru:'Водная рябь',category:'elegant',kind:'Мягкий',difficulty:'Средний',use:'Морские путешествия',description:'Концентрические волны расходятся от центра и раскрывают новую сцену. Художественная имитация ряби.'},
  {id:'map',en:'Map Journey',ru:'Путешествие по карте',category:'travel',kind:'Маршрутный',difficulty:'Средний',use:'Туры по городам',description:'Условная карта появляется между сценами; линия маршрута соединяет две точки и раскрывает место прибытия.'},
  {id:'postcard',en:'Postcard Transition',ru:'Живые открытки',category:'travel',kind:'Ностальгический',difficulty:'Средний',use:'Экскурсионные туры',description:'Две фотографии оформлены как открытки и перелистываются в кадре.'},
  {id:'filmstrip',en:'Filmstrip',ru:'Кинопленка',category:'travel',kind:'Ретро',difficulty:'Средний',use:'История, архитектура',description:'Пленка с кадрами путешествия прокручивается перед камерой.'},
  {id:'pagecurl',en:'Page Curl',ru:'Перелистывание страницы',category:'elegant',kind:'Альбомный',difficulty:'Средний',use:'Туристические истории',description:'Первый кадр поворачивается как страница фотокниги, открывая следующий.'},
  {id:'luma',en:'Luma Reveal',ru:'Проявление через свет',category:'cinematic',kind:'Световой',difficulty:'Сложный',use:'Красивые пейзажи',description:'Следующий кадр проявляется из нескольких световых областей. Демонстрация стилизованного светового раскрытия, не попиксельного luma key.'},
  {id:'foreground',en:'Foreground Wipe',ru:'Проход перед камерой',category:'cinematic',kind:'Натуральный',difficulty:'Средний',use:'Улицы, колонны, транспорт',description:'Темный объект проходит по переднему плану и скрывает момент смены сцены.'},
  {id:'mask',en:'Shape Mask Reveal',ru:'Фигурная маска',category:'travel',kind:'Тематический',difficulty:'Средний',use:'Праздники, зимние туры',description:'Второй кадр появляется внутри расширяющейся звезды. Форму можно заменить символом направления.'},
  {id:'morph',en:'Polygon Morph',ru:'Превращение формы',category:'creative',kind:'Графический',difficulty:'Сложный',use:'Креативные анонсы',description:'Геометрическая маска плавно меняет форму и раскрывает весь следующий кадр.'},
  {id:'match',en:'Match Cut',ru:'Совпадение движения',category:'cinematic',kind:'Кинематографичный',difficulty:'Средний',use:'Похожие композиции',description:'Быстрая склейка с единым масштабом и направлением движения. Лучший результат требует двух похожих по композиции кадров.'}
];
const $ = id => document.getElementById(id);
const stage = $('previewStage'), sceneA = $('sceneA'), sceneB = $('sceneB');
const overlay = $('overlayLayers'), flash = $('flashFx'), glitch = $('glitchFx');
const DEFAULT_DURATION = 900;
let selected = EFFECTS[0].id, category = 'all', preset = 'alps', swapped = false, duration = DEFAULT_DURATION;
let favorites = new Set(), tween = null, rafId = 0, loopTimer = null, lastObjectURLs = {};
let custom = {A:null,B:null};
let importedSpec=null, seamEffects=[];
const clamp = (v,min=0,max=1)=>Math.max(min,Math.min(max,v));
const lerp = (a,b,t)=>a+(b-a)*t;
const pcent = v=>`${(v*100).toFixed(3)}%`;
const setPhoto = (node,url)=>{node.style.backgroundImage=`url("${url.replace(/"/g,'%22')}")`;};
const effect = ()=>EFFECTS.find(e=>e.id===selected);
const ordered = ()=>{const p=PRESETS[preset], src=[custom.A||p.photos[0],custom.B||p.photos[1]],labels=p.labels;return swapped?{src:[src[1],src[0]],labels:[labels[1],labels[0]]}:{src,labels};};
function currentImages(){const d=ordered();setPhoto(sceneA,d.src[0]);setPhoto(sceneB,d.src[1]);
  [['A',d.labels[0]],['B',d.labels[1]]].forEach(([k,label])=>{ $(`kicker${k}`).textContent=label[0]; $(`head${k}`).innerHTML=label[1]; $(`caption${k}`).textContent=label[2]; });
  document.documentElement.style.setProperty('--photoA',`url("${d.src[0]}")`);document.documentElement.style.setProperty('--photoB',`url("${d.src[1]}")`);
  return d.src;
}
function piece(className, background, html='') {
  const el=document.createElement('div'); el.className='overlay-piece '+className;
  if (background) setPhoto(el,background);
  if (html) el.innerHTML=html;
  overlay.append(el);
  return el;
}
function makeTiles(source,cols,rows,extraClass=''){
  for(let i=0;i<cols*rows;i++){
    const col=i%cols,row=Math.floor(i/cols),x=100*col/cols,y=100*row/rows;
    const el=piece(extraClass,source);
    el.style.clipPath=`polygon(${x}% ${y}%,${x+100/cols+.15}% ${y}%,${x+100/cols+.15}% ${y+100/rows+.15}%,${x}% ${y+100/rows+.15}%)`;
    el.dataset.piece=i;
  }
}
function buildLayers(id){overlay.replaceChildren();const src=ordered().src;
  if(id==='split')for(let i=0;i<2;i++){const el=piece('',src[0]);el.style.clipPath=i===0?'inset(0 50% 0 0)':'inset(0 0 0 50%)'}
  if(id==='shutter')for(let i=0;i<8;i++){const x=i*12.5,el=piece('',src[1]);el.style.clipPath=`polygon(${x}% 0,${x+12.6}% 0,${x+12.6}% 100%,${x}% 100%)`}
  if(id==='tiles')makeTiles(src[1],5,4);
  if(id==='particles')makeTiles(src[0],6,9,'particle-tile');
  if(id==='glitch')for(let i=0;i<7;i++){const y=i*14.3,el=piece('',src[1]);el.style.clipPath=`inset(${y}% 0 ${Math.max(0,100-y-14.5)}% 0)`}
  if(id==='portal')piece('portal-arch',null);
  if(id==='textmask'){
    const el=piece('text-window',src[1]);
    el.textContent= preset==='city'?'ЕВРОПА':preset==='sea'?'МОРЕ':'ГОРЫ';
  }
  if(id==='lightleak')piece('light-leak',null);
  if(id==='ripple')piece('water-rings',null);
  if(id==='map'){
    const dest=preset==='city'?['ИТАЛИЯ','ФРАНЦИЯ']:preset==='sea'?['ПОРТ','ОСТРОВ']:['ГОРОД A','ГОРОД B'];
    piece('route-map',null,`<div class="map-grid"></div><span class="route-title">ПУТЬ ПУТЕШЕСТВИЯ</span><svg class="route-line" viewBox="0 0 300 420" preserveAspectRatio="none" aria-hidden="true"><path class="route-trace" d="M 68 325 Q 72 218 155 235 T 238 105" fill="none" stroke="#c9f46b" stroke-width="5" stroke-linecap="round" stroke-dasharray="450" stroke-dashoffset="450"/><circle cx="68" cy="325" r="8" fill="#c9f46b"/><circle cx="238" cy="105" r="8" fill="#c9f46b"/></svg><span class="map-point map-point-a">${dest[0]}</span><span class="map-point map-point-b">${dest[1]}</span>`);
  }
  if(id==='postcard'){
    const a=piece('postcard postcard-a',src[0],'<span>ПРИВЕТ ИЗ ПУТЕШЕСТВИЯ</span>');
    const b=piece('postcard postcard-b',src[1],'<span>СЛЕДУЮЩАЯ ОСТАНОВКА</span>');
    a.style.zIndex='2';b.style.zIndex='1';
  }
  if(id==='filmstrip'){
    const a=piece('film-frame film-frame-a',src[0]);const b=piece('film-frame film-frame-b',src[1]);
    a.style.zIndex='2';b.style.zIndex='1';
  }
  if(id==='pagecurl')piece('curl-page',src[0]);
  if(id==='foreground')piece('foreground-bar',null);
  if(id==='luma'){
    for(let i=0;i<5;i++)piece('luma-glow glow-'+i,null);
  }
}
function starPolygon(r,twist=0){
  const pts=[];
  for(let i=0;i<10;i++){
    const a=-Math.PI/2+Math.PI*i/5+twist;
    const mag=r*(i%2?.47:1);
    pts.push(`${50+Math.cos(a)*mag}% ${50+Math.sin(a)*mag}%`);
  }
  return `polygon(${pts.join(',')})`;
}
function morphPolygon(t){
  const pts=[];
  for(let i=0;i<12;i++){
    const a=Math.PI*2*i/12-Math.PI/2;
    const shape0=i%2===0?12:23;
    const shape1=i%3===0?35:18;
    const mag=lerp(lerp(shape0,shape1,clamp(t*2)),215,clamp((t-.45)/.55))*clamp(t/.06);
    pts.push(`${50+Math.cos(a)*mag}% ${50+Math.sin(a)*mag}%`);
  }
  return `polygon(${pts.join(',')})`;
}

function render(t,id){ t=clamp(t);const a=sceneA.style,b=sceneB.style; a.opacity='1';a.transform='none';a.filter='none';a.clipPath='none';a.transformOrigin='center center';b.opacity='1';b.transform='none';b.filter='none';b.clipPath='none';b.maskImage='none';b.transformOrigin='center center';overlay.style.opacity='1';flash.style.opacity='0';glitch.style.opacity='0';stage.style.perspective='1200px';
  sceneA.querySelector('.scene-content').style.opacity=String(1-clamp((t-.19)/.31));
  sceneB.querySelector('.scene-content').style.opacity=String(clamp((t-.51)/.32));
  switch(id){
    case 'crossfade': b.opacity=t;break;
    case 'push': a.transform=`translate3d(${-100*t}%,0,0)`;b.transform=`translate3d(${100*(1-t)}%,0,0)`;break;
    case 'zoom': a.transform=`scale(${lerp(1,1.85,t)})`;a.opacity=1-clamp((t-.55)/.45);b.transform=`scale(${lerp(1.32,1,t)})`;b.opacity=clamp((t-.3)/.65);break;
    case 'whip': a.transform=`translate3d(${-110*t}%,0,0) scale(1.10)`;b.transform=`translate3d(${110*(1-t)}%,0,0) scale(1.10)`;a.filter=`blur(${Math.sin(Math.PI*t)*16}px)`;b.filter=a.filter;break;
    case 'circle': b.clipPath=`circle(${pcent(150*t)} at 50% 50%)`;break;
    case 'diagonal': b.clipPath=`polygon(0 0,${pcent(-.7+1.7*t)} 0,${pcent(-.1+1.7*t)} 100%,0 100%)`;break;
    case 'flash': b.opacity=t>=.52?1:0;flash.style.opacity=String(clamp(1-Math.abs(t-.51)/.20));break;
    case 'blur': a.opacity=1-t;b.opacity=t;a.filter=`blur(${Math.sin(Math.PI*t)*12}px)`;b.filter=`blur(${12*(1-t)}px)`;break;
    case 'flip': if(t<.5){a.transform=`rotateY(${90*(t*2)}deg)`;b.opacity=0;}else{a.opacity=0;b.transform=`rotateY(${lerp(-90,0,(t-.5)*2)}deg)`;}break;
    case 'parallax': a.opacity=1-clamp((t-.35)*1.7);b.opacity=clamp((t-.08)*1.75);a.transform=`translate3d(${-14*t}%,0,0) scale(${lerp(1,1.12,t)})`;b.transform=`translate3d(${12*(1-t)}%,0,0) scale(${lerp(1.14,1,t)})`;break;
    case 'shutter': b.opacity=0;[...overlay.children].forEach((el,i)=>{el.style.opacity=String(clamp((t-(i*.065))/.42))});break;
    case 'glitch': {const burst=Math.sin(t*20*Math.PI),flicker=burst>.1?1:0;b.opacity=t>.82?1:0;a.transform=`translate3d(${Math.sin(t*48*Math.PI)*Math.min(t,.7)*7}px,0,0)`;[...overlay.children].forEach((el,i)=>{const on=clamp((t-.12-(i%3)*.08)/.18);el.style.opacity=String(t>.83?0:on*(.5+.5*flicker));el.style.transform=`translate3d(${Math.sin(t*58+i*3)*19*(1-t)}px,0,0)`});glitch.style.opacity=String(t>.18&&t<.83?(.15+.23*Math.abs(burst)):0);break;}
    case 'split':a.opacity=0;[...overlay.children].forEach((el,i)=>{el.style.opacity='1';el.style.transform=`translate3d(${(i===0?-100:100)*t}%,0,0)`;});break;
    case 'rotate':a.transform=`rotate(${-36*t}deg) scale(${lerp(1,1.4,t)})`;a.opacity=1-clamp((t-.28)/.42);b.transform=`rotate(${23*(1-t)}deg) scale(${lerp(1.3,1,t)})`;b.opacity=clamp((t-.20)/.55);break;
    case 'tiles':b.opacity=0;[...overlay.children].forEach((el,i)=>{const c=i%5,r=Math.floor(i/5),delay=(c+r)*.085;el.style.opacity=String(clamp((t-delay)/.35));el.style.transform=`scale(${lerp(1.12,1,clamp((t-delay)/.35))})`;});break;
    case 'portal': {
      const open=clamp((t-.04)/.93);
      b.clipPath=`inset(${50*(1-open)}% ${50*(1-open)}% ${50*(1-open)}% ${50*(1-open)}% round ${60*(1-open)}% ${60*(1-open)}% ${4*(1-open)}% ${4*(1-open)}%)`;
      b.transform=`scale(${lerp(1.18,1,open)})`;
      const arch=overlay.firstChild;
      arch.style.opacity=String(Math.sin(Math.PI*t)*.75);
      arch.style.transform=`translate(-50%,-50%) scale(${lerp(.34,3.5,open)})`;
      break;
    }
    case 'textmask': {
      b.opacity=clamp((t-.75)/.20);
      a.opacity=1-clamp((t-.68)/.25);
      const el=overlay.firstChild;
      el.style.opacity=String(clamp((t-.03)/.15)*(1-clamp((t-.78)/.2)));
      el.style.transform=`translate(-50%,-50%) scale(${lerp(.46,12,Math.pow(t,1.6))})`;
      break;
    }
    case 'lightleak': {
      b.opacity=clamp((t-.23)/.55);
      a.transform=`scale(${1+.055*t})`;
      const el=overlay.firstChild;
      el.style.opacity=String(.88*Math.sin(Math.PI*t));
      el.style.transform=`translateX(${lerp(-140,160,t)}%) rotate(13deg)`;
      break;
    }
    case 'speedramp': {
      const quick=t<.5?Math.pow(t*2,4)*.5:1-Math.pow((1-t)*2,3)*.5;
      a.transform=`translate3d(${-98*quick}%,0,0) scale(${1+.19*Math.sin(Math.PI*t)})`;
      b.transform=`translate3d(${98*(1-quick)}%,0,0) scale(${1+.13*(1-quick)})`;
      a.filter=b.filter=`blur(${Math.sin(Math.PI*t)*10}px)`;
      break;
    }
    case 'particles': {
      a.opacity=0;
      [...overlay.children].forEach((el,i)=>{
        const c=i%6,r=Math.floor(i/6),delay=(c*.024+r*.016);
        const k=clamp((t-delay)/.69);
        const dx=(Math.sin(i*14.31)*70+Math.cos(i*3.47)*25)*k;
        const dy=(-55+Math.cos(i*5.29)*80)*k;
        el.style.opacity=String(1-clamp((k-.2)/.76));
        el.style.transform=`translate(${dx}%,${dy}%) rotate(${Math.sin(i*2.3)*65*k}deg) scale(${1-.22*k})`;
      });
      break;
    }
    case 'ripple': {
      b.clipPath=`circle(${150*t}% at 50% 47%)`;
      a.transform=`scale(${1+.045*Math.sin(t*Math.PI*5)*Math.sin(Math.PI*t)})`;
      a.filter=`blur(${3*Math.sin(Math.PI*t)}px)`;
      const el=overlay.firstChild;
      el.style.opacity=String(Math.sin(Math.PI*t)*.75);
      el.style.transform=`translate(-50%,-50%) scale(${.3+t*3.7})`;
      break;
    }
    case 'map': {
      a.opacity=1-clamp((t-.02)/.33);
      b.opacity=clamp((t-.69)/.27);
      const el=overlay.firstChild;
      el.style.opacity=String(clamp(t/.24)*(1-clamp((t-.73)/.25)));
      el.style.transform=`scale(${lerp(1.3,.98,t)})`;
      el.querySelector('.route-trace').style.strokeDashoffset=String(450-450*clamp((t-.25)/.48));
      break;
    }
    case 'postcard': {
      a.filter='brightness(.55)';b.opacity=clamp((t-.8)/.15);
      const [p1,p2]=overlay.children;
      const x=clamp((t-.08)/.77);
      p1.style.transform=`translate(${lerp(-50,-180,x)}%,${lerp(-50,-80,x)}%) rotate(${lerp(-8,-35,x)}deg) scale(${lerp(.84,.57,x)})`;
      p1.style.opacity=String(1-clamp((t-.55)/.35));
      p2.style.transform=`translate(${lerp(30,-50,clamp((t-.1)/.76))}%,${lerp(-15,-50,clamp((t-.1)/.76))}%) rotate(${lerp(18,0,clamp((t-.1)/.76))}deg) scale(${lerp(.66,.94,clamp((t-.1)/.76))})`;
      p2.style.opacity=String(clamp((t-.12)/.21)*(1-clamp((t-.85)/.13)));
      break;
    }
    case 'filmstrip': {
      a.opacity=clamp((.20-t)/.2); b.opacity=clamp((t-.83)/.14);
      const [p1,p2]=overlay.children;
      p1.style.transform=`translate3d(${lerp(14,-150,t)}%,0,0) rotate(-6deg)`;
      p2.style.transform=`translate3d(${lerp(122,-15,t)}%,0,0) rotate(-6deg)`;
      p1.style.opacity=String(1-clamp((t-.64)/.3));
      p2.style.opacity=String(clamp((t-.16)/.22)*(1-clamp((t-.83)/.16)));
      break;
    }
    case 'pagecurl': {
      a.opacity=0;
      const pg=overlay.firstChild;
      pg.style.transform=`rotateY(${-176*t}deg)`;
      pg.style.filter=`brightness(${1-.25*Math.sin(Math.PI*t)})`;
      pg.style.opacity=String(1-clamp((t-.94)/.06));
      break;
    }
    case 'luma': {
      const positions=[[17,18],[78,35],[45,68],[17,88],[90,81]];
      b.opacity=1;
      const gradient=positions.map(([x,y],i)=>{
        const progress=clamp((t-i*.09)/(.8-i*.05));
        return `radial-gradient(circle at ${x}% ${y}%,#000 ${progress*132}%,transparent ${Math.min(155,progress*132+17)}%)`;
      });
      b.maskImage=gradient.join(',');
      [...overlay.children].forEach((el,i)=>{
        const phase=clamp((t-i*.09)/.76);
        el.style.opacity=String(Math.sin(Math.PI*phase)*.38);
        el.style.left=positions[i][0]+'%';el.style.top=positions[i][1]+'%';
        el.style.transform=`translate(-50%,-50%) scale(${.2+phase*2.5})`;
      });
      break;
    }
    case 'foreground': {
      const front=overlay.firstChild;
      const seam=clamp((t-.25)/.50);
      b.clipPath=`inset(0 ${100*(1-seam)}% 0 0)`;
      front.style.opacity=String(Math.sin(Math.PI*t)*.98);
      front.style.transform=`translateX(${lerp(-140,150,t)}%) rotate(-6deg)`;
      a.transform=`translateX(${-7*t}%) scale(1.05)`;
      b.transform=`translateX(${5*(1-t)}%) scale(1.05)`;
      break;
    }
    case 'mask': b.clipPath=starPolygon(210*t);break;
    case 'morph': b.clipPath=morphPolygon(t);break;
    case 'match': {
      const cut=clamp((t-.475)/.05);
      a.transform=`scale(${lerp(1,1.2,t)}) translateX(${-2*t}%)`;
      b.transform=`scale(${lerp(1.2,1,t)}) translateX(${2*(1-t)}%)`;
      b.opacity=cut;
      break;
    }
    default:b.opacity=t;
  }
  $('progressFill').style.width=pcent(t);$('previewTimer').textContent=(duration*t/1000).toFixed(2)+'s';
}
function cancelPlay(){if(tween){try{tween.pause()}catch(e){}tween=null;}if(rafId){cancelAnimationFrame(rafId);rafId=0;}if(loopTimer){clearTimeout(loopTimer);loopTimer=null;}$('playButton').disabled=false;}
function play(){cancelPlay();buildLayers(selected);render(0,selected);const obj={progress:0};$('playButton').disabled=true;
  const finished=()=>{tween=null;rafId=0;$('playButton').disabled=false;render(1,selected);if($('loopToggle').checked)loopTimer=setTimeout(play,420)};
  if(window.anime&&typeof window.anime.animate==='function'){
    try{tween=window.anime.animate(obj,{progress:1,duration,ease:'inOut(3)',onUpdate:()=>render(obj.progress,selected),onComplete:finished});return;}catch(err){console.warn('Anime.js is unavailable, using animation fallback',err)}
  }
  const started=performance.now(); const frame=now=>{const x=clamp((now-started)/duration);const eased=x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;render(eased,selected);if(x<1)rafId=requestAnimationFrame(frame);else finished()};rafId=requestAnimationFrame(frame);
}
function resetStage(){cancelPlay();buildLayers(selected);render(0,selected)}
function filterCards(){const cards=EFFECTS.filter(e=>category==='all'||e.category===category);$('visibleCount').textContent=cards.length;const bg=ordered().src;
  $('effectGrid').innerHTML=cards.map((e,i)=>{
    const n=EFFECTS.indexOf(e)+1,fav=favorites.has(e.id),active=e.id===selected;
    return `<article class="effect-card ${active?'active':''}" data-effect="${e.id}" role="button" tabindex="0" aria-label="Посмотреть переход ${e.ru}" aria-pressed="${active}" style="--photoA:url('${bg[0]}');--photoB:url('${bg[1]}')"><div class="card-preview"><span class="card-index">${String(n).padStart(2,'0')}</span><span class="card-lines">A <span>→</span> B</span><button class="card-favorite" type="button" aria-label="${fav?'Убрать из подборки':'Добавить в подборку'}" aria-pressed="${fav}" data-favorite="${e.id}">${fav?'★':'☆'}</button></div><div class="card-body"><div class="card-title">${e.en}</div><div class="card-group">${GROUPS[e.category]}</div><div class="card-meta"><span>${e.ru}</span><b>${e.difficulty}</b></div></div></article>`;
  }).join('')}
function updateSelected(){const e=effect();const n=EFFECTS.indexOf(e)+1;$('currentTitle').textContent=e.en;$('currentDescription').textContent=e.description;$('currentNumber').textContent=`${String(n).padStart(2,'0')} / ${EFFECTS.length}`;
 $('characterValue').textContent=e.kind;$('complexityValue').textContent=e.difficulty;$('usageValue').textContent=e.use;
 $('favoriteButton').classList.toggle('selected',favorites.has(selected));$('favoriteButton').title=favorites.has(selected)?'Убрать из подборки':'Добавить в подборку';$('favoriteButton').setAttribute('aria-pressed',String(favorites.has(selected)));
 filterCards();resetStage();}
function choose(id){if(!EFFECTS.some(e=>e.id===id))return;selected=id;updateSelected();play();}
function persistFavorites(){try{localStorage.setItem('motionlab:favorites',JSON.stringify([...favorites]))}catch(e){}}
function showFavorites(){const chosen=EFFECTS.filter(e=>favorites.has(e.id));$('chosenCount').textContent=chosen.length;$('navFavs').textContent=chosen.length;
 $('chosenItems').innerHTML=chosen.length?chosen.map(e=>`<div class="chosen-tag"><span>${e.en}</span><button type="button" data-remove="${e.id}" aria-label="Убрать ${e.en}">×</button></div>`).join(''):'<p class="empty-state">Пока ничего не выбрано. Нажмите звездочку рядом с понравившимся эффектом.</p>';
 $('favoriteButton').classList.toggle('selected',favorites.has(selected));$('favoriteButton').setAttribute('aria-pressed',String(favorites.has(selected)));filterCards();persistFavorites();}
function toggleFavorite(id){favorites.has(id)?favorites.delete(id):favorites.add(id);showFavorites();toast(favorites.has(id)?'Добавлено в подборку':'Удалено из подборки')}
let toastTimer=null;function toast(message){const node=$('toast');node.textContent=message;node.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.classList.remove('show'),2400)}
function loadPhoto(input,side){const file=input.files?.[0];if(!file)return;if(!file.type.startsWith('image/')){toast('Выберите файл изображения');return;}if(file.size>20*1024*1024){toast('Файл больше 20 МБ');return;}if(lastObjectURLs[side])URL.revokeObjectURL(lastObjectURLs[side]);const url=URL.createObjectURL(file);lastObjectURLs[side]=url;custom[side]=url;currentImages();updateSelected();toast(`Кадр ${side} загружен`)}
function createBrief(){const chosen=EFFECTS.filter(e=>favorites.has(e.id));return ['MOTION LAB / КИНОСТУДИЯ BON TOURS','Выбранные переходы Anime.js',`Количество: ${chosen.length}`,`Демонстрационная длительность: ${(duration/1000).toFixed(1)} с`,'',...chosen.map((e,i)=>`${i+1}. ${e.en} — ${e.ru}\n   Группа: ${GROUPS[e.category]}. Стиль: ${e.kind}. Сложность: ${e.difficulty}. Применение: ${e.use}.`),'','Важно: это концепты переходов, а не готовые видеофайлы. Для рилса нужны исходные кадры, тайминг и последующий видеорендер.'].join('\n')}
async function copyBrief(){if(!favorites.size){toast('Сначала выберите хотя бы один переход');return;}const text=createBrief();try{await navigator.clipboard.writeText(text)}catch(e){const area=document.createElement('textarea');area.value=text;document.body.append(area);area.select();try{document.execCommand('copy')}catch(er){}area.remove()}toast('Монтажное ТЗ скопировано');$('copyStatus').textContent=`Готово: ${favorites.size} ${favorites.size===1?'эффект':(favorites.size>=2&&favorites.size<=4?'эффекта':'эффектов')} в монтажном ТЗ.`}
/* Production handoff: update only transitions on an existing validated scene list.
 * No upload, credentials, narration edits or paid job triggers in this browser.
 */
function saveJson(filename, obj) {
  const text=JSON.stringify(obj,null,2)+'\n';
  const blob=new Blob([text],{type:'application/json;charset=utf-8'});
  const href=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=href;link.download=filename;document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(href),1000);
}
function validTransition(value){return typeof value==='string'&&EFFECTS.some(e=>e.id===value);}
function renderAssignments(){
  const area=$('sceneAssignments');
  if(!importedSpec){area.innerHTML='<p class="empty-state">Загрузите спецификацию ролика: появятся переходы между сценами.</p>';return;}
  const n=importedSpec.scenes.length;
  area.innerHTML=Array.from({length:n-1},(_,i)=>{
    const seam=i+1;
    return `<div class="scene-assignment"><span>СЦЕНА ${seam} → ${seam+1}</span><select data-seam="${seam}" aria-label="Переход между сценами ${seam} и ${seam+1}"><option value="">Обычное растворение</option>${EFFECTS.map(e=>`<option value="${e.id}" ${seamEffects[i]===e.id?'selected':''}>${e.en} / ${e.ru}</option>`).join('')}</select></div>`;
  }).join('');
  $('downloadSpec').disabled=false;
  $('specInfo').textContent=`${n} сцен · ${n-1} переходов · renderer: ${importedSpec.renderer||'simba'}`;
  $('handoffStatus').textContent=`Назначено ${seamEffects.filter(Boolean).length} из ${n-1} переходов. Длительность ${(duration/1000).toFixed(1)} с. Финальная сборка и QA выполняются отдельно в Киностудии.`;
}
function applyFavorites(){
  const ids=EFFECTS.filter(e=>favorites.has(e.id)).map(e=>e.id);
  if(!ids.length)ids.push(selected);
  if(!importedSpec){toast('Сначала загрузите video-spec.json');return;}
  seamEffects=seamEffects.map((_,i)=>ids[i%ids.length]);
  renderAssignments();toast('Подборка назначена переходам');
}
function buildUpdatedSpec(){
  if(!importedSpec)throw new Error('Сначала загрузите video-spec.json');
  const result=JSON.parse(JSON.stringify(importedSpec));
  for(let i=1;i<result.scenes.length;i++){
    if(seamEffects[i-1])result.scenes[i].transition={id:seamEffects[i-1],duration_ms:duration};
    else delete result.scenes[i].transition;
  }
  return result;
}
function exportPlan(){
  const chosen=EFFECTS.filter(e=>favorites.has(e.id)).map(e=>e.id);
  const items=importedSpec?seamEffects.map((id,i)=>({to_scene:i+2,id:id||'crossfade',duration_ms:duration})):[];
  saveJson('motion-lab-transition-plan.json',{
    schema:'simba.motionlab.transition-plan',version:1,
    generated_from:'Motion Lab',duration_ms:duration,selected_effects:chosen,
    scene_count:importedSpec?.scenes.length??null,transitions:items,
    note:'План не является готовым MP4. Для применения загрузите video-spec.json, сохраните измененную версию и запустите существующий рендерер.'
  });
  toast('План переходов сохранен');
}
async function importVideoSpec(event){
  const file=event.target.files?.[0];if(!file)return;
  if(file.size>1024*1024){toast('JSON больше 1 МБ');return;}
  try{
    const parsed=JSON.parse(await file.text());
    if(!parsed||!Array.isArray(parsed.scenes)||parsed.scenes.length<2||parsed.scenes.length>8||parsed.scenes.some(s=>!s||typeof s!=='object'||Array.isArray(s)))throw Error('Нужно от 2 до 8 сцен');
    if(typeof parsed.packageId!=='string'||typeof parsed.sourcePost!=='string')throw Error('Нужен настоящий Simba video-spec.json');
    if(parsed.renderer!=null&&!['simba','hyperframes'].includes(parsed.renderer))throw Error('Неизвестный рендерер');
    importedSpec=parsed;
    const picks=EFFECTS.filter(e=>favorites.has(e.id)).map(e=>e.id);
    seamEffects=parsed.scenes.slice(1).map((s,i)=>validTransition(s.transition?.id)?s.transition.id:(picks[i%picks.length]||selected));
    renderAssignments();toast('Спецификация загружена локально');
  }catch(err){importedSpec=null;seamEffects=[];renderAssignments();$('specInfo').textContent='Ошибка: '+err.message;toast('Не удалось открыть video-spec.json');}
}
function init(){try{const saved=JSON.parse(localStorage.getItem('motionlab:favorites')||'[]');favorites=new Set(saved.filter(id=>EFFECTS.some(e=>e.id===id)))}catch(e){favorites=new Set()}
  document.querySelectorAll('.filter').forEach(btn=>{const n=EFFECTS.filter(e=>btn.dataset.filter==='all'||e.category===btn.dataset.filter).length;const count=btn.querySelector('span');if(count)count.textContent=n;});
  currentImages();showFavorites();updateSelected();
  $('effectGrid').addEventListener('click',event=>{const fav=event.target.closest('[data-favorite]');if(fav){event.stopPropagation();toggleFavorite(fav.dataset.favorite);return;}const card=event.target.closest('[data-effect]');if(card)choose(card.dataset.effect)});
  $('effectGrid').addEventListener('keydown',event=>{if(event.target.closest('.card-favorite'))return;const card=event.target.closest('[data-effect]');if(card&&(event.key==='Enter'||event.key===' ')){event.preventDefault();choose(card.dataset.effect)}});
  document.querySelectorAll('.filter').forEach(btn=>btn.addEventListener('click',()=>{category=btn.dataset.filter;document.querySelectorAll('.filter').forEach(el=>el.classList.toggle('active',el===btn));filterCards()}));
  document.querySelectorAll('.preset').forEach(btn=>btn.addEventListener('click',()=>{preset=btn.dataset.preset;document.querySelectorAll('.preset').forEach(el=>el.classList.toggle('selected',el===btn));custom={A:null,B:null};currentImages();filterCards();play()}));
  document.querySelectorAll('.format').forEach(btn=>btn.addEventListener('click',()=>{stage.className='preview-stage '+btn.dataset.ratio;document.querySelectorAll('.format').forEach(el=>el.classList.toggle('active',el===btn));play()}));
  $('durationRange').addEventListener('input',event=>{duration=Number(event.target.value);$('durationOutput').textContent=(duration/1000).toFixed(1)+' с'});
  $('durationRange').addEventListener('change',()=>{play();if(importedSpec)renderAssignments()});
  $('playButton').addEventListener('click',play);$('favoriteButton').addEventListener('click',()=>toggleFavorite(selected));$('swapButton').addEventListener('click',()=>{swapped=!swapped;currentImages();play();filterCards()});
  $('photoA').addEventListener('change',event=>loadPhoto(event.target,'A'));$('photoB').addEventListener('change',event=>loadPhoto(event.target,'B'));
  $('resetPhotos').addEventListener('click',()=>{Object.values(lastObjectURLs).forEach(url=>URL.revokeObjectURL(url));lastObjectURLs={};custom={A:null,B:null};$('photoA').value='';$('photoB').value='';currentImages();filterCards();play();toast('Демонстрационные кадры восстановлены')});
  $('specFile').addEventListener('change',importVideoSpec);
  $('sceneAssignments').addEventListener('change',e=>{const idx=Number(e.target.dataset.seam);if(Number.isInteger(idx)&&idx>0&&idx<=seamEffects.length&&(!e.target.value||validTransition(e.target.value))){seamEffects[idx-1]=e.target.value;renderAssignments()}});
  $('assignFavorites').addEventListener('click',applyFavorites);
  $('downloadPlan').addEventListener('click',exportPlan);
  $('downloadSpec').addEventListener('click',()=>{try{const spec=buildUpdatedSpec();saveJson('video-spec.json',spec);toast('Спецификация для Киностудии сохранена')}catch(err){toast(err.message)}});
  $('chosenItems').addEventListener('click',event=>{const btn=event.target.closest('[data-remove]');if(btn)toggleFavorite(btn.dataset.remove)});
  $('copyBrief').addEventListener('click',copyBrief);$('clearFavorites').addEventListener('click',()=>{favorites.clear();showFavorites();toast('Подборка очищена')});
  window.addEventListener('pagehide',()=>Object.values(lastObjectURLs).forEach(url=>URL.revokeObjectURL(url)));
  if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches)setTimeout(play,650);
}
document.addEventListener('DOMContentLoaded',init);
