'use strict';
/* Full MP4 to editable scene candidates in the USER'S browser.
 * The source, posters and sound remain local Blob URLs. This does not call
 * a remote VLM, transcribe audio, or deliver assets to Montage.
 */
(() => {
 const core=globalThis.MotionLabDirectorCore;
 const cuts=globalThis.MotionLabVideoCuts;
 const $=id=>document.getElementById(id);
 let active=null,busy=false;
 const status=(message,error=false)=>{const e=$('fullVideoStatus');if(e){e.textContent=message;e.classList.toggle('director-error',error);}};
 const short=n=>Math.round(n*100)/100;
 function resetMeta(){active=null;if($('fullVideoSummary'))$('fullVideoSummary').hidden=true;}
 function isOriginalTimeline(){
  if(!active||state.scenes.length!==active.segments.length)return false;
  return state.scenes.every((s,i)=>s.id===active.segments[i].id&&
   Math.abs(s.duration-(active.segments[i].end-active.segments[i].start))<.11);
 }
 const info=()=>active;
 function ready(video,url){
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>finish(Error('Браузер не открыл MP4')),12000);
   function finish(err){clearTimeout(timer);video.removeEventListener('loadedmetadata',onload);video.removeEventListener('error',onerror);
    err?reject(err):resolve(video.duration);}
   function onload(){const d=video.duration;if(!Number.isFinite(d)||d<2||d>60)finish(Error('Допускаются ролики длительностью от 2 до 60 секунд'));else finish();}
   function onerror(){finish(Error('Браузер не поддерживает кодек этого MP4'));}
   video.addEventListener('loadedmetadata',onload,{once:true});video.addEventListener('error',onerror,{once:true});
   video.src=url;video.load();
  });
 }
 function seek(video,time){
  return new Promise((resolve,reject)=>{
   const target=Math.min(Math.max(time,.05),Math.max(.05,video.duration-.04));
   const timer=setTimeout(()=>finish(Error('Не удалось декодировать кадр на '+short(target)+' с')),8000);
   function finish(err){clearTimeout(timer);video.removeEventListener('seeked',done);video.removeEventListener('error',error);
    err?reject(err):resolve();}
   function done(){finish();}
   function error(){finish(Error('Ошибка декодирования кадра'));}
   video.addEventListener('seeked',done,{once:true});video.addEventListener('error',error,{once:true});
   try{video.currentTime=target;}catch(e){finish(e);}
  });
 }
 function readGrid(video,canvas){
  const ctx=canvas.getContext('2d',{willReadFrequently:true});if(!ctx)throw Error('Canvas недоступен');
  ctx.drawImage(video,0,0,canvas.width,canvas.height);
  return core.signature(ctx.getImageData(0,0,canvas.width,canvas.height)).grid;
 }
 async function poster(video,start,end){
  await seek(video,start+Math.min((end-start)*.5,1.5));
  const canvas=document.createElement('canvas');canvas.width=180;canvas.height=320;
  const ctx=canvas.getContext('2d');ctx.drawImage(video,0,0,180,320);
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',.74));
  if(!blob)throw Error('Не удалось сохранить миниатюру');
  return URL.createObjectURL(blob);
 }
 async function importVideo(file){
  if(busy)return;
  if(state.bridge||state.request){status('Нельзя заменить сцены подключенного задания Киностудии.',true);return;}
  if(!/\.(mp4|m4v|webm)$/i.test(file.name)||file.size<1||file.size>200*1024*1024){status('Нужен локальный MP4/WebM до 200 МБ.',true);return;}
  if(!globalThis.crypto?.subtle){status('Для локальной контрольной суммы нужен HTTPS.',true);return;}
  busy=true;$('fullVideoFile').disabled=true;
  const url=URL.createObjectURL(file),thumbs=[];let committed=false;
  const video=document.createElement('video');video.preload='auto';video.muted=true;video.playsInline=true;
  try{
   status('Открывается видеоролик в вашем браузере...');
   const duration=await ready(video,url);
   const canvas=document.createElement('canvas');canvas.width=48;canvas.height=84;
   const samples=[];
   for(let time=.25;time<duration-.20;time+=.5){
    status('Поиск смены кадров: '+Math.min(100,Math.round(time/duration*100))+'% · без загрузки в интернет.');
    await seek(video,time);
    samples.push({time:short(time),grid:readGrid(video,canvas)});
   }
   const segments=cuts.segmentVideo(samples,duration);
   status('Выявлено '+segments.scenes.length+' визуальных фрагментов. Рассчитывается SHA-256 исходника.');
   const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer())))
    .map(x=>x.toString(16).padStart(2,'0')).join('');
   for(let i=0;i<segments.scenes.length;i++){
    const s=segments.scenes[i];
    status('Создание реальных кадров для раскадровки: '+(i+1)+' / '+segments.scenes.length);
    thumbs.push(await poster(video,s.start,s.end));
   }
   if(state.request||state.bridge)throw Error('Пока шло чтение, подключилось задание агента. Импорт остановлен.');
   stopFilm(false);clearPreviews();
   state.project={id:'local-video-'+sha.slice(0,12)};state.request=null;state.bridge=null;
   state.scenes=segments.scenes.map((s,i)=>{
    const id='shot-'+String(i+1).padStart(2,'0')+'-'+Math.round(s.start*100);
    const asset='local-sha256:'+sha+':'+Math.round(s.start*1000)+'-'+Math.round(s.end*1000);
    return makeScene({scene_id:id,name:'Фрагмент '+String(i+1).padStart(2,'0'),
     duration_s:s.seconds,image:'custom',asset_id:asset,title_text:'',subtitle_preview:'',
     media:{kind:'video',duration_s:s.seconds}},i);
   });
   for(let i=0;i<state.scenes.length;i++){
    const s=state.scenes[i],segment=segments.scenes[i];
    s.clipRange={start:segment.start,end:segment.end,method:segment.boundary};
    localPreviews.set(s.id,{url,assetId:s.asset,type:'video',poster:thumbs[i],
     duration:segment.seconds,start:segment.start,end:segment.end,sourceSha:sha,shaVerified:false});
   }
   active={url,sha,filename:file.name,duration:short(duration),segments:state.scenes.map(s=>({
    id:s.id,start:s.clipRange.start,end:s.clipRange.end})),stats:segments,srt:null};
   const audio=$('importedFilmAudio');if(audio){audio.src=url;audio.load();}
   state.concepts=PRESETS.map(p=>({...p}));state.selectedOption=0;state.selectedIndex=0;
   state.dirty=true;state.confirmed=false;state.lastAck=null;
   render();
   const panel=$('fullVideoSummary');panel.hidden=false;
   panel.textContent='Источник: '+file.name+' · '+short(duration)+' с · '+segments.scenes.length+
    ' кандидатных фрагментов · порог смены кадра '+segments.threshold+'/255. '+
    'Границы приблизительные: графика и титры могут имитировать смену сцены. '+
    'Проверьте каждый фрагмент. Оригинальный звук доступен при просмотре исходного порядка.';
   status('MP4 разобран локально. Скачайте кадры и карту сцен для смыслового разбора в ChatGPT; затем выберите монтажный вариант.');
   committed=true;
  }catch(e){status('Импорт не выполнен: '+String(e.message||e),true);}
  finally{
   video.pause();video.removeAttribute('src');video.load();
   if(!committed){URL.revokeObjectURL(url);for(const t of thumbs)URL.revokeObjectURL(t);}
   busy=false;$('fullVideoFile').disabled=false;
  }
 }
 function saveFile(blob,name){
  const url=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=url;link.download=name;document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1200);
 }
 function exportMap(){
  if(!active){status('Сначала импортируйте полный MP4.',true);return;}
  const manifest={schema:'bontours.motionlab.scene-map/v1',source:{
   filename:active.filename,sha256:active.sha,duration_seconds:active.duration,format:'local-mp4',
   source_is_approved:false},analysis:{method:active.stats.method,samples:active.stats.sample_count,
   threshold:active.stats.threshold,cut_candidates:active.stats.candidate_count,
   caveat:'Heuristic visual cuts; NOT source A2E scene boundaries, OCR or semantic AI'},
   scenes:state.scenes.map((s,i)=>({scene_id:s.id,asset_id:s.asset,order:i+1,
    start_seconds:s.clipRange?.start??null,end_seconds:s.clipRange?.end??null,
    storyboard_seconds:s.duration,description:s.name,reviewed_caption:s.title,
    speech_from_user_srt:s.speechCue||null})),
   guards:{render_enabled:false,publication_enabled:false,private_source_not_uploaded:true}};
  saveFile(new Blob([JSON.stringify(manifest,null,2)],{type:'application/json'}),
   'motionlab-'+active.sha.slice(0,10)+'-scene-map.json');
  status('Карта сцен сохранена. Она не является разрешением передавать MP4 монтажеру.');
 }
 async function contactSheet(){
  if(!active){status('Сначала импортируйте MP4.',true);return;}
  const rows=Math.ceil(state.scenes.length/4),w=960,cellW=240,cellH=425,canvas=document.createElement('canvas');
  canvas.width=w;canvas.height=rows*cellH;const ctx=canvas.getContext('2d');
  ctx.fillStyle='#0d1420';ctx.fillRect(0,0,canvas.width,canvas.height);
  for(let i=0;i<state.scenes.length;i++){
   const s=state.scenes[i],p=previewFor(s);if(!p?.poster)continue;
   const img=new Image();await new Promise((ok,bad)=>{img.onload=ok;img.onerror=bad;img.src=p.poster;});
   const x=(i%4)*cellW,y=Math.floor(i/4)*cellH;
   ctx.drawImage(img,x+17,y+10,206,366);
   ctx.fillStyle='#eef4f9';ctx.font='bold 16px Arial, sans-serif';
   ctx.fillText(String(i+1).padStart(2,'0')+' / '+p.start.toFixed(2)+'–'+p.end.toFixed(2)+' с',x+12,y+406);
  }
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.87));
  if(!blob){status('Не удалось сформировать контактный лист.',true);return;}
  saveFile(blob,'motionlab-'+active.sha.slice(0,10)+'-contact-sheet.jpg');
  status('Контактный лист сохранен. Его можно загрузить в ChatGPT вместе с картой сцен для содержательного разбора.');
 }
 async function acceptSrt(file){
  if(!active){status('Сначала импортируйте MP4.',true);return;}
  if(!file||file.size>200000){status('SRT должен быть не больше 200 КБ.',true);return;}
  try{
   const cues=cuts.parseSrt(await file.text());
   const mapped=cuts.alignCues(state.scenes.map(s=>s.clipRange),cues);
   state.scenes.forEach((s,i)=>{s.speechCue=mapped[i].phrases;});
   active.srt={name:file.name,cues:cues.length};
   renderSceneList();
   status('Время и фразы '+cues.length+' субтитров сопоставлены с '+state.scenes.length+
    ' сценами. Это предоставленный SRT, а не автоматически распознанная речь.');
  }catch(e){status('SRT отклонен: '+String(e.message||e),true);}
 }
 function init(){
  const input=$('fullVideoFile');if(!input||!core||!cuts)return;
  input.addEventListener('change',async e=>{const file=e.target.files?.[0];e.target.value='';if(file)await importVideo(file);});
  $('exportSceneMap').addEventListener('click',exportMap);
  $('exportContactSheet').addEventListener('click',()=>contactSheet().catch(e=>status(String(e.message||e),true)));
  $('fullVideoSrt').addEventListener('change',async e=>{const file=e.target.files?.[0];e.target.value='';if(file)await acceptSrt(file);});
 }
 globalThis.MotionLabVideoImport={isOriginalTimeline,info,resetMeta,importVideo,exportMap,contactSheet};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
