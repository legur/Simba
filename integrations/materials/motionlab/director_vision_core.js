'use strict';
/* Browser-only candidate classifications. No credentials, network or ChatGPT
 * are used by this pure module. Two exact-SHA examples are derived from the
 * previously reviewed Bavaria/Prague contact sheets, not live model inference.
 */
(function(root,factory){
 const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;
 root.MotionLabVisionCore=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 const KINDS=['landmark','ambience','character','route','offer','cta'];
 const LABELS={
  landmark:'Архитектура / достопримечательность',
  ambience:'Атмосфера / праздничные виды',
  character:'Человек / персонаж',
  route:'Маршрут / транспорт / пейзаж',
  offer:'Цена / рекламное предложение',
  cta:'Контакты / призыв к действию'
 };
 const PROMPTS=[
  {kind:'landmark',label:'a photograph of an old European cathedral, castle or historic landmark'},
  {kind:'ambience',label:'a festive European city street with Christmas lights and decoration'},
  {kind:'character',label:'a human presenter or an animal mascot in a travel advertisement'},
  {kind:'route',label:'a tram, train, airplane, road, scenic landscape or travel route'},
  {kind:'offer',label:'a tourism promotional advertisement showing a large price, dates and discount'},
  {kind:'cta',label:'a commercial end card with a phone number, WhatsApp contact and booking invitation'}
 ];
 // Time bounds (seconds) and labels only. Never embed user's original media,
 // text, phone number, captions or local Blob URLs in the public Wix bundle.
 const ARCHIVED={
  ab4635b8398adfe6fda91126d68a6c6b708024f9be7bd9074e742fdf7c56e32b:{
   bounds:[0,3,5.5,8.5,11,14,17,19.5,22.5,25,28,33.5,36.5,42,54.62],
   kinds:['landmark','landmark','ambience','ambience','ambience','landmark','landmark','route','landmark','landmark','offer','offer','offer','cta'],
   readable:[11,12,13,14]
  },
  a77cc034f957dec224bc5345bfdd818e8c2f6453f592cd356a3e195d1b11ed13:{
   bounds:[0,5,10,15,20,25.5,30.38],
   kinds:['offer','offer','character','offer','route','cta'],
   readable:[1,2,3,4,6]
  }
 };
 const cents=n=>Math.round(n*100),millis=n=>Math.round(n*1000);
 const isHash=x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x);
 function matchArchived(sha,scenes){
  if(!isHash(sha)||!Array.isArray(scenes))return null;
  const item=ARCHIVED[sha];if(!item||scenes.length!==item.kinds.length)return null;
  for(let i=0;i<scenes.length;i++){
   const s=scenes[i],start=item.bounds[i],end=item.bounds[i+1],p=String(i+1).padStart(2,'0');
   if(s?.id!==`shot-${p}-${cents(start)}`||
    s.asset!==`local-sha256:${sha}:${millis(s.clipRange?.start)}-${millis(s.clipRange?.end)}`||
    !s.clipRange||Math.abs(s.clipRange.start-start)>.025||Math.abs(s.clipRange.end-end)>.025)return null;
  }
  return scenes.map((s,i)=>({
   scene_id:s.id,asset_id:s.asset,kind:item.kinds[i],
   text_burned_in:true,must_remain_readable:item.readable.includes(i+1),
   evidence:'previously reviewed still-frame contact sheet',relative_score:null,
   needs_review:true
  }));
 }
 function rankedVision(outputs,index,total){
  if(!Array.isArray(outputs)||!outputs.length||!Number.isInteger(index)||index<0||index>=total||total<1)throw Error('Некорректные результаты визуальной модели');
  const scores=new Map();
  for(const pred of outputs){
   const candidate=PROMPTS.find(x=>x.label===pred?.label);
   if(candidate&&Number.isFinite(pred.score)&&pred.score>=0){
    const old=scores.get(candidate.kind)||0;
    scores.set(candidate.kind,old+pred.score);
   }
  }
  if(!scores.size)throw Error('Модель не вернула известных категорий');
  const ranked=[...scores.entries()].sort((a,b)=>b[1]-a[1]);
  const top=ranked[0],runner=ranked[1]?.[1]||0;
  const uncertain=top[1]<.35||(top[1]-runner)<.08;
  // With low separation keep a conservative generic visual category;
  // always protect the final scene from distracting CTA effects.
  const kind=uncertain?'ambience':top[0];
  const protect=kind==='offer'||kind==='cta'||index===total-1;
  return {kind,relative_score:Math.round(top[1]*1000)/1000,
   runner_up:Math.round(runner*1000)/1000,uncertain,needs_review:true,
   text_burned_in:true,must_remain_readable:protect,
   evidence:'local-CLIP-relative-label-ranking'};
 }
 function toReviewedDocument(rows,scenes){
  if(!Array.isArray(rows)||rows.length!==scenes.length||!rows.length)throw Error('Полный разбор сцен не выполнен');
  const seen=new Set();
  return {schema:'bontours.motionlab.editorial-annotations/v1',source:'human-reviewed',
   review_method:'Operator confirmed local visual model candidates; not live ChatGPT',
   scenes:rows.map((row,i)=>{
    if(row.scene_id!==scenes[i].id||row.asset_id!==scenes[i].asset||seen.has(row.scene_id)||!KINDS.includes(row.kind))throw Error('Сцены или категории изменились: повторите анализ');
    seen.add(row.scene_id);
    if(typeof row.text_burned_in!=='boolean'||typeof row.must_remain_readable!=='boolean')throw Error('Нужно проверить видимость текста');
    return {scene_id:row.scene_id,asset_id:row.asset_id,kind:row.kind,
     text_burned_in:row.text_burned_in,
     must_remain_readable:row.must_remain_readable||row.kind==='offer'||row.kind==='cta'};
   })};
 }
 return {KINDS,LABELS,PROMPTS,matchArchived,rankedVision,toReviewedDocument};
});
