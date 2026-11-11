'use strict';
/* Editorial annotations explicitly provided by an operator or reviewing model.
 * NEVER infer labels from pixel motion; no upload or backend handoff.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 root.MotionLabSemantic=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 const LABELS=new Set(['landmark','ambience','character','route','offer','cta']);
 const safe=s=>typeof s==='string'&&s.length>0&&s.length<=240;
 function validate(document,scenes){
  if(document?.schema!=='bontours.motionlab.editorial-annotations/v1')throw Error('Неизвестная схема редакторского разбора');
  if(document.source!=='human-reviewed'&&document.source!=='chatgpt-reviewed')throw Error('Укажите действительный источник проверки');
  if(!Array.isArray(document.scenes)||document.scenes.length!==scenes.length||!scenes.length)throw Error('Количество сцен не совпадает с раскадровкой');
  const references=new Map(scenes.map(s=>[s.id,s]));
  if(references.size!==scenes.length)throw Error('Повтор ID сцены в раскадровке');
  const used=new Set();
  for(const row of document.scenes){
   if(!safe(row?.scene_id)||used.has(row.scene_id))throw Error('Повтор или пустой ID в аннотациях');
   used.add(row.scene_id);
   const scene=references.get(row.scene_id);
   if(!scene||row.asset_id!==scene.asset)throw Error('ID сцены или исходника не совпадает: '+row.scene_id);
   if(!LABELS.has(row.kind))throw Error('Неизвестный тип сцены: '+row.scene_id);
   if(row.description!=null&&(!safe(row.description)||row.description.length>400))throw Error('Некорректное описание сцены');
   if(row.speech_cue!=null&&(typeof row.speech_cue!=='string'||row.speech_cue.length>160))throw Error('Некорректная речевая привязка');
   if(typeof row.text_burned_in!=='boolean'||typeof row.must_remain_readable!=='boolean')throw Error('Нужно указать статус текста и читаемости');
  }
  return document.scenes;
 }
 function enrich(plans,annotation,scenes){
  const rows=validate(annotation,scenes);
  const byId=new Map(rows.map(r=>[r.scene_id,r]));
  const results=plans.plans.map(p=>({
   ...p,scenes:p.scenes.map((s,i)=>{
    const row=byId.get(s.scene_id);
    const protectedText=['offer','cta'].includes(row.kind)||row.must_remain_readable;
    const isCharacter=row.kind==='character';
    const reason=[s.reason,'Редакторская метка: '+row.kind+'.',
     row.speech_cue?'Речь: '+row.speech_cue+'.':'',
     protectedText?'Приоритет — читаемость: без резких движений и закрывающих экран переходов.':'',
     row.text_burned_in?'Текст уже встроен в исходный файл.':''].filter(Boolean).join(' ');
    return {...s,
     camera:protectedText?'cinematic-zoom':isCharacter?'float':s.camera,
     transition:i===0?'none':protectedText?'crossfade':s.transition,
     titleFx:row.text_burned_in||protectedText?'none':s.titleFx,
     intensity:protectedText?0:isCharacter?Math.min(s.intensity,30):s.intensity,
     reason,semantic_kind:row.kind,protected:protectedText,
     // This flag blocks future automatic handoff, not a guarantee about rendering.
     editorial_review_required:protectedText
    };
   })
  }));
  const n=rows.filter(r=>['offer','cta'].includes(r.kind)||r.must_remain_readable).length;
  return {...plans,plans:results,mode:'human-annotated+local-pixel-metrics',
   meaning:plans.meaning+' Дополнительно учтены явные редакторские метки ('+n+' защищенных сцен). Это не автоматическое распознавание речи или текста.',
   semantic_verified_by:annotation.source};
 }
 return {validate,enrich};
});
