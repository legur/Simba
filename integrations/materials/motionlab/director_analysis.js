'use strict';
/* Real browser-local frame sampling. No upload, OCR, speech or semantic AI claims.
 * Proposals are session-only and cannot authorize Montage or MP4 rendering.
 */
(() => {
 const core=globalThis.MotionLabDirectorCore;
 const $=id=>document.getElementById(id);
 let plans=null,snapshot=null,busy=false;
 let editorial=null;
 const panel=()=> $('directorReport');
 const btn=()=> $('analyzeLocalAssets');
 function status(message,isError=false){
  const el=$('directorStatus');if(!el)return;
  el.textContent=message;el.classList.toggle('director-error',isError);
 }
 function fingerprint(){
  return JSON.stringify(state.scenes.map(s=>{
   const source=previewFor(s);
   return [s.id,s.asset,source?.url||null,source?.type||null,source?.shaVerified||false];
  }));
 }
 function invalidate(){
  const hadPlans=Boolean(plans);
  editorial=null;
  const editorialStatus=$('editorialStatus');if(editorialStatus)editorialStatus.textContent='Нет загруженной редакторской аннотации.';
  plans=null;snapshot=null;
  if(panel())panel().hidden=true;
  if(hadPlans && !state.request){
   state.concepts=PRESETS.map(c=>({...c}));
   state.selectedOption=0;
   resetAck();renderConcepts();renderSummary();
  }
  status('После изменения исходников нужно заново выполнить анализ. Материалы остаются в браузере.');
 }
 function frame(node){
  const c=document.createElement('canvas');c.width=48;c.height=84;
  const context=c.getContext('2d',{willReadFrequently:true});
  if(!context)throw Error('Canvas недоступен');
  context.drawImage(node,0,0,c.width,c.height);
  return core.signature(context.getImageData(0,0,c.width,c.height));
 }
 function imageSignal(url){
  return new Promise((resolve,reject)=>{
   const img=new Image();const timeout=setTimeout(()=>fail(Error('Тайм-аут изображения')),9000);
   function clean(){clearTimeout(timeout);img.onload=null;img.onerror=null;}
   function fail(err){clean();reject(err);}
   img.onload=()=>{try{const s=frame(img);clean();resolve(s);}catch(err){fail(err);}};
   img.onerror=()=>fail(Error('Не удалось открыть изображение'));
   img.src=url;
  });
 }
 function seekFrame(video,time){
  return new Promise((resolve,reject)=>{
   const timeout=setTimeout(()=>end(Error('Не удалось прочитать кадр видео')),8000);
   function cleanup(){clearTimeout(timeout);video.removeEventListener('seeked',done);video.removeEventListener('error',error);}
   function end(err,signal){cleanup();err?reject(err):resolve(signal);}
   function done(){try{end(null,frame(video));}catch(err){end(err);}}
   function error(){end(Error('Ошибка декодирования видео'));}
   video.addEventListener('seeked',done,{once:true});
   video.addEventListener('error',error,{once:true});
   try{video.currentTime=time;}catch(err){end(err);}
  });
 }
 function videoSignal(url,start=0,end=null){
  return new Promise((resolve,reject)=>{
   const video=document.createElement('video');
   video.preload='auto';video.muted=true;video.playsInline=true;
   const timeout=setTimeout(()=>finish(Error('Видео не открылось')),10000);
   function finish(err,result){
    clearTimeout(timeout);video.pause();video.removeAttribute('src');video.load();
    err?reject(err):resolve(result);
   }
   video.onerror=()=>finish(Error('Видеофайл нельзя декодировать'));
   video.onloadedmetadata=async()=>{
    video.onerror=null;
    try{
     const duration=video.duration;
     if(!Number.isFinite(duration)||duration<=0)throw Error('Неизвестная длительность');
     const from=Math.max(0,start),to=Math.min(duration,end==null?duration:end);
     if(to-from<.25)throw Error('Слишком короткий видеофрагмент для анализа');
     const times=[.1,.5,.9].map(f=>Math.min(Math.max(.05,from+(to-from)*f),Math.max(.05,duration-.05)));
     const frames=[];
     for(const time of times)frames.push(await seekFrame(video,time));
     const diffs=[core.frameDifference(frames[0].grid,frames[1].grid),core.frameDifference(frames[1].grid,frames[2].grid)];
     finish(null,{brightness:Math.round(frames.reduce((v,x)=>v+x.mean,0)/3),
      edge:Math.round(frames.reduce((v,x)=>v+x.edge,0)/3),motion:Math.round((diffs[0]+diffs[1])/2),
      contrast:Math.round(frames.reduce((v,x)=>v+x.contrast,0)/3),samples:3});
    }catch(err){finish(err);}
   };
   video.src=url;
  });
 }
 async function analyze(){
  if(busy)return;
  busy=true;btn().disabled=true;panel().hidden=true;
  const initial=fingerprint();
  try{
   if(state.request)throw Error('Подключенное задание v1 имеет утвержденные варианты. Для замены требуется согласованный контракт Montage v2.');
   if(!state.scenes.length)throw Error('В раскадровке нет сцен');
   const missing=state.scenes.map((scene,index)=>previewFor(scene)?null:index+1).filter(Boolean);
   if(missing.length)throw Error('Не загружены реальные файлы для сцен: '+missing.join(', ')+'. Демонстрационные картинки не анализируются.');
   const results=[];
   for(let i=0;i<state.scenes.length;i++){
    const scene=state.scenes[i],source=previewFor(scene);
    status('Измеряются реальные кадры: '+(i+1)+' / '+state.scenes.length+'…');
    const signal=source.type==='video'?await videoSignal(source.url,source.start||0,source.end??null):await imageSignal(source.url);
    if(initial!==fingerprint())throw Error('Исходные материалы изменились. Повторите анализ.');
    results.push({scene_id:scene.id,asset_id:scene.asset,type:source.type,shaVerified:Boolean(source.shaVerified),signal});
   }
   const pixelPlans=core.buildPlans(results);
   const generated=editorial?globalThis.MotionLabSemantic.enrich(pixelPlans,editorial,state.scenes):pixelPlans;
   if(initial!==fingerprint())throw Error('Состав сцен изменился. Повторите анализ.');
   plans={...generated,results};snapshot=initial;
   state.concepts=generated.plans.map(p=>({
    id:p.id,name:p.name,tag:p.tag,desc:p.description,
    camera:p.scenes[0].camera,transition:p.transition,titleFx:p.titleFx,
    subtitleStyle:p.subtitleStyle,wordMotion:p.wordMotion,intensity:p.scenes[0].intensity
   }));
   state.selectedOption=0;resetAck();renderConcepts();renderSummary();
   const recommended=generated.plans.find(p=>p.recommended);
   const title=document.createElement('strong');
   title.textContent='Рекомендация: вариант '+recommended.id+' — '+recommended.name;
   const explanation=document.createElement('p');
   explanation.textContent=generated.meaning+' Выбор не заменяет содержательный просмотр материалов в ChatGPT.';
   const list=document.createElement('div');list.className='director-scene-results';
   for(let i=0;i<results.length;i++){
    const r=results[i],scene=state.scenes[i],s=r.signal;
    const row=document.createElement('p');
    row.textContent=(i+1)+'. '+scene.name+' · '+(r.type==='video'?'Видео':'Фото')+
     ' · свет '+s.brightness+'/255 · детали '+s.edge+'/255'+
     (r.type==='video'?' · разница кадров '+s.motion+'/255':'')+
     (r.shaVerified?' · SHA подтвержден':' · SHA не подтвержден')+'. '+recommended.scenes[i].reason;
    list.append(row);
   }
   panel().replaceChildren(title,explanation,list);panel().hidden=false;
   status('Готовы три предложения по измеренным кадрам. Выберите вариант выше для предпросмотра.');
  }catch(error){
   plans=null;snapshot=null;status('Анализ не выполнен: '+String(error.message||error),true);
  }finally{busy=false;btn().disabled=false;}
 }
 function applyConcept(id){
  if(!plans)return false; // preserve original behavior for launch/v1/demo presets
  if(snapshot!==fingerprint()){invalidate();status('Исходники изменились. Повторите анализ.',true);return true;}
  const plan=plans.plans.find(p=>p.id===id);
  if(!plan)return true;
  const byId=new Map(plan.scenes.map(s=>[s.scene_id,s]));
  if(byId.size!==state.scenes.length||state.scenes.some(s=>!byId.has(s.id)||byId.get(s.id).asset_id!==s.asset)){
   invalidate();status('Изменился состав сцен. Предложения больше не актуальны.',true);return true;
  }
  stopFilm(false);
  for(let i=0;i<state.scenes.length;i++){
   const scene=state.scenes[i],s=byId.get(scene.id);
   Object.assign(scene,{camera:s.camera,transition:i===0?'none':s.transition,
    titleFx:s.titleFx,subtitleStyle:s.subtitleStyle,wordMotion:s.wordMotion,intensity:s.intensity});
  }
  state.selectedOption=id;state.dirty=true;resetAck();render();
  status('Вариант '+id+' применен. Просмотрите весь ролик и исправьте сцены перед утверждением.');
  return true;
 }
 function init(){
  if(!core||!btn()||!panel())return;
  btn().addEventListener('click',analyze);
  const picker=$('editorialManifest');
  if(picker)picker.addEventListener('change',async()=>{
   const file=picker.files?.[0];if(!file)return;
   try{
    if(file.size>100000)throw Error('Файл аннотаций слишком велик');
    if(state.request)throw Error('Редакторские аннотации нельзя подменять внутри подключенного задания v1');
    const data=JSON.parse(await file.text());
    if(!globalThis.MotionLabSemantic)throw Error('Модуль редакторской проверки недоступен');
    globalThis.MotionLabSemantic.validate(data,state.scenes);
    editorial=data;
    plans=null;snapshot=null;resetAck();
    $('editorialStatus').textContent='Редакторские метки загружены и сверены с ID сцен и исходников: '+data.scenes.length+'. Перезапустите анализ кадров.';
    status('Аннотации проверены; теперь выполните анализ реальных локальных файлов.');
    if(panel())panel().hidden=true;
   }catch(e){editorial=null;$('editorialStatus').textContent='Отклонено: '+String(e.message||e);}
   picker.value='';
  });
  status('Загрузите локальные файлы для каждой сцены. Файлы остаются в браузере.');
 }
 globalThis.MotionLabDirector={analyze,applyConcept,invalidate};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
