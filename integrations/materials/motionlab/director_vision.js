'use strict';
/* Optional browser-local zero-shot CLIP vision + previously ChatGPT-reviewed
 * exact-media examples. Images never leave this browser; only model weights
 * are requested from a pinned third-party package/model CDN on explicit click.
 * This does NOT connect to ChatGPT live and does NOT OCR/transcribe/audio-analyze.
 */
(() => {
 const core=globalThis.MotionLabVisionCore,$=id=>document.getElementById(id);
 const reviewPanel=()=> $('visionReview');
 let classifier=null,modelModule=null,rows=null,snapshot=null,mode=null,busy=false,epoch=0;
 const label=kind=>core.LABELS[kind]||kind;
 function status(message,error=false){
  const e=$('visionStatus');if(!e)return;
  e.textContent=message;e.classList.toggle('director-error',Boolean(error));
 }
 function fingerprint(){
  return JSON.stringify(state.scenes.map(s=>{
   const p=previewFor(s);
   return [s.id,s.asset,p?.url||null,p?.poster||null,p?.start??null,p?.end??null];
  }));
 }
 function valid(){return snapshot===fingerprint()&&!state.request&&!state.bridge;}
 function reset(message='Визуальные метки устарели после изменения сцен. Выполните анализ снова.'){
  epoch++;rows=null;snapshot=null;mode=null;
  if(reviewPanel())reviewPanel().hidden=true;
  if($('visionCommit'))$('visionCommit').disabled=true;
  status(message);
 }
 function makeRow(scene,i,source,pred){
  return {scene_id:scene.id,asset_id:scene.asset,kind:pred.kind,
   text_burned_in:source?.type==='video'||Boolean(pred.text_burned_in),
   must_remain_readable:Boolean(pred.must_remain_readable)||i===state.scenes.length-1,
   relative_score:pred.relative_score??null,uncertain:Boolean(pred.uncertain),
   evidence:pred.evidence||null,needs_review:true};
 }
 function drawReview(title){
  const box=$('visionRows');
  box.replaceChildren();
  rows.forEach((row,i)=>{
   const scene=state.scenes[i],source=previewFor(scene);
   const article=document.createElement('div');article.className='vision-review-row';
   const picture=document.createElement('img');
   picture.alt='Реальный локальный кадр '+String(i+1);picture.loading='lazy';
   picture.src=source?.poster||(source?.type==='image'?source.url:'');
   const form=document.createElement('div');form.className='vision-review-form';
   const heading=document.createElement('strong');
   heading.textContent=(i+1)+'. '+scene.name+' — '+(row.uncertain?'НУЖНА ПРОВЕРКА':'черновая категория');
   const kindLabel=document.createElement('label');kindLabel.textContent='Что показано в сцене? ';
   const select=document.createElement('select');select.setAttribute('aria-label','Категория сцены '+(i+1));
   for(const k of core.KINDS){const option=document.createElement('option');option.value=k;option.textContent=label(k);select.append(option);}
   select.value=row.kind;
   const textLabel=document.createElement('label');textLabel.className='vision-checkbox';
   const textBox=document.createElement('input');textBox.type='checkbox';textBox.checked=row.text_burned_in;
   textLabel.append(textBox,document.createTextNode('На изображении уже есть текст / титры'));
   const safeLabel=document.createElement('label');safeLabel.className='vision-checkbox';
   const safeBox=document.createElement('input');safeBox.type='checkbox';safeBox.checked=row.must_remain_readable;
   const alwaysSafe=()=>['offer','cta'].includes(row.kind)||i===rows.length-1;
   safeBox.disabled=alwaysSafe();
   safeLabel.append(safeBox,document.createTextNode('Не закрывать текст эффектами (приоритет читаемости)'));
   const score=document.createElement('small');
   score.textContent=row.relative_score==null?
    'Источник: предыдущий просмотр кадров в ChatGPT. Разметка требует подтверждения.':
    'Локальная модель · относительная оценка '+row.relative_score.toFixed(3)+' (не достоверность).';
   select.addEventListener('change',()=>{
    row.kind=select.value;
    if(alwaysSafe()){row.must_remain_readable=true;safeBox.checked=true;safeBox.disabled=true;}
    else{safeBox.disabled=false;row.must_remain_readable=safeBox.checked;}
   });
   textBox.addEventListener('change',()=>{row.text_burned_in=textBox.checked;});
   safeBox.addEventListener('change',()=>{row.must_remain_readable=safeBox.checked;});
   kindLabel.append(select);
   form.append(heading,kindLabel,textLabel,safeLabel,score);
   article.append(picture,form);box.append(article);
  });
  $('visionReviewHeading').textContent=title;
  reviewPanel().hidden=false;$('visionCommit').disabled=false;
  status('Просмотрите '+rows.length+' настоящих кадров и категории. Нажмите «Подтвердить», чтобы получить три варианта монтажа.');
 }
 function onImported(sha){
  reset('Видео загружено. Проверяется наличие ранее подготовленного анализа...');
  if(state.request)return;
  const archived=core.matchArchived(sha,state.scenes);
  if(archived){
   rows=archived.map((r,i)=>makeRow(state.scenes[i],i,previewFor(state.scenes[i]),r));
   mode='archived-chatgpt-contact-sheet';
   snapshot=fingerprint();
   drawReview('Найдена разметка этих точных кадров из прежней сессии ChatGPT — проверьте и подтвердите');
   status('Найдена разметка по точной SHA-256 видеозаписи и временным границам. Живой вызов ChatGPT НЕ производился. Подтвердите категории ниже.');
  }else status('Сохраненной разметки для этого ролика нет. Можно запустить локальное ML-распознавание (загрузка модели из Hugging Face, изображения остаются в браузере).');
 }
 async function recognize(){
  if(busy)return;
  if(state.request||state.bridge){status('Распознавание недоступно в подключенном задании v1.',true);return;}
  if(!state.scenes.length){status('Нет сцен для распознавания.',true);return;}
  const sources=state.scenes.map(s=>previewFor(s));
  if(sources.some(s=>!s||!((s.poster||s.type==='image'&&s.url)||'').startsWith('blob:'))){
   status('Для каждой сцены нужен настоящий локальный кадр. Импортируйте MP4 или собственные изображения.',true);return;
  }
  const initial=fingerprint(),token=++epoch;
  busy=true;$('recognizeScenes').disabled=true;$('visionCommit').disabled=true;
  rows=null;snapshot=null;mode=null;reviewPanel().hidden=true;
  try{
   if(!classifier){
    status('Загружается модель CLIP (8-bit, CPU/WASM). Первая загрузка может быть большой. Изображения не отправляются поставщику модели.');
    modelModule=await import('https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1');
    classifier=await modelModule.pipeline('zero-shot-image-classification','Xenova/clip-vit-base-patch32',
     {device:'wasm',dtype:'q8',progress_callback:evt=>{
      if(evt?.status==='progress'&&Number.isFinite(evt.progress))
       status('Загрузка локальной модели: '+Math.round(evt.progress)+'%. Исходные кадры не отправляются.');
     }});
   }
   const results=[];
   for(let i=0;i<state.scenes.length;i++){
    if(token!==epoch||fingerprint()!==initial)throw Error('Сцены изменились во время анализа');
    status('Локальная модель изучает кадр '+(i+1)+' из '+state.scenes.length+'. Для цены и контактов обязательна ручная проверка.');
    const source=sources[i],url=source.poster||(source.type==='image'?source.url:null);
    if(!url?.startsWith('blob:'))throw Error('Внешние изображения не разрешены для автоматического локального анализа');
    const response=await fetch(url);if(!response.ok)throw Error('Локальный кадр недоступен');
    const image=await modelModule.RawImage.read(await response.blob());
    const output=await classifier(image,core.PROMPTS.map(x=>x.label));
    const predicted=core.rankedVision(output,i,state.scenes.length);
    results.push(makeRow(state.scenes[i],i,source,predicted));
   }
   if(token!==epoch||fingerprint()!==initial)throw Error('Исходники изменились — результаты отброшены');
   rows=results;mode='local-clip';snapshot=initial;
   drawReview('Локальное ML-распознавание: черновые категории (не ChatGPT, требуется проверка)');
  }catch(e){
   if(token===epoch){reset();status('Локальное распознавание не выполнено: '+String(e.message||e)+'. Для разбора в ChatGPT используйте контактный лист и карту сцен.',true);}
  }finally{busy=false;if($('recognizeScenes'))$('recognizeScenes').disabled=false;}
 }
 async function confirm(){
  if(!rows||!valid()){reset();status('Состав, порядок или исходники изменились — повторите распознавание.',true);return;}
  try{
   const doc=core.toReviewedDocument(rows,state.scenes);
   globalThis.MotionLabDirector.setEditorial(doc);
   $('visionCommit').disabled=true;
   status('Редакторские категории подтверждены. Выполняется анализ реальных пикселей для трех монтажных предложений...');
   await globalThis.MotionLabDirector.analyze();
   status('Проверенные категории учтены. Из трех предложений выберите вариант и просмотрите его по сценам.');
  }catch(e){status('Метки не применены: '+String(e.message||e),true);}
 }
 function init(){
  if(!core||!$('recognizeScenes')||!$('visionCommit')||!$('visionRows'))return;
  $('recognizeScenes').addEventListener('click',recognize);
  $('visionCommit').addEventListener('click',confirm);
  $('visionCommit').disabled=true;
  status('Импортируйте полный MP4. Для известных исходников ранее проверенная разметка появится автоматически.');
 }
 globalThis.MotionLabVision={onImported,recognize,reset};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
