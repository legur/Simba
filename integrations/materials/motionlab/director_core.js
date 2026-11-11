'use strict';
/* Browser-only visual signals for local assets; NOT semantic AI video understanding.
 * This module is deliberately pure and can run in Node tests.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 root.MotionLabDirectorCore=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 function signature(imageData){
  if(!imageData||!Number.isInteger(imageData.width)||!Number.isInteger(imageData.height)||!imageData.data)throw Error('Пиксели отсутствуют');
  const {width:w,height:h,data}=imageData;
  if(w<2||h<2||data.length<w*h*4)throw Error('Некорректный кадр');
  let total=0,squares=0,edges=0,center=0,outer=0,cn=0,on=0;
  const grid=new Uint8Array(w*h);
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
   const i=(y*w+x)*4;
   const lum=Math.round(.2126*data[i]+.7152*data[i+1]+.0722*data[i+2]);
   grid[y*w+x]=lum;total+=lum;squares+=lum*lum;
   if(x>=w*.25&&x<w*.75&&y>=h*.25&&y<h*.75){center+=lum;cn++;}else{outer+=lum;on++;}
   if(x>0)edges+=Math.abs(lum-grid[y*w+x-1]);
   if(y>0)edges+=Math.abs(lum-grid[(y-1)*w+x]);
  }
  const n=w*h,mean=total/n;
  return {grid,mean:Math.round(mean),contrast:Math.round(Math.sqrt(Math.max(0,squares/n-mean*mean))),
   edge:Math.round(edges/((w-1)*h+(h-1)*w)),center:Math.round(center/Math.max(1,cn)),outer:Math.round(outer/Math.max(1,on))};
 }
 function frameDifference(a,b){
  if(!a||!b||a.length!==b.length||!a.length)throw Error('Нельзя сравнить кадры разного размера');
  let sum=0;for(let i=0;i<a.length;i++)sum+=Math.abs(a[i]-b[i]);
  return Math.round(sum/a.length);
 }
 function interpret(row){
  const signal=row?.signal||{};
  const m=clamp(Number(signal.motion)||0,0,255),brightness=clamp(Number(signal.brightness)||0,0,255);
  return {motion:m,brightness,details:clamp(Number(signal.edge)||0,0,255),type:row?.type==='video'?'video':'image'};
 }
 function buildPlans(rows){
  if(!Array.isArray(rows)||!rows.length||rows.some(r=>!r||!r.scene_id||!r.signal))throw Error('Нужен анализ каждого реального исходника');
  if(new Set(rows.map(r=>r.scene_id)).size!==rows.length)throw Error('Повторяются ID сцен');
  const avg=rows.reduce((s,r)=>s+interpret(r).motion,0)/rows.length;
  const bright=rows.reduce((s,r)=>s+interpret(r).brightness,0)/rows.length;
  const recommended=avg>=19?2:bright>=170?3:1;
  const presets=[
   {id:1,name:'Плавный',tag:'СПОКОЙНЫЙ',description:'Мягкие стыки и умеренная камера. Приоритет — читаемость и неспешная подача.',
    transition:'crossfade',titleFx:'fade-rise',subtitleStyle:'clean',wordMotion:'karaoke'},
   {id:2,name:'Ритмичный',tag:'ДИНАМИЧНЫЙ',description:'Более энергичные переходы там, где в исходниках заметно движение.',
    transition:'push',titleFx:'punch-zoom',subtitleStyle:'outline',wordMotion:'active-pop'},
   {id:3,name:'Атмосферный',tag:'ПРЕМИУМ',description:'Плавный монтаж с акцентами света и спокойными титрами.',
    transition:'lightleak',titleFx:'light-sweep',subtitleStyle:'luxury',wordMotion:'highlight-strip'}
  ];
  const plans=presets.map(p=>({
   ...p,recommended:p.id===recommended,scenes:rows.map((r,i)=>{
    const s=interpret(r),moving=s.motion>=17,highDetail=s.details>=22;
    const camera=p.id===1?(r.type==='video'?(moving?'pan':'float'):'cinematic-zoom'):
     p.id===2?(moving?'push-through':highDetail?'pan':'cinematic-zoom'):
     (r.type==='video'?(moving?'float':'pan'):'float');
    const transition=i===0?'none':(p.id===2&&!moving&&s.motion<8?'crossfade':p.transition);
    return {scene_id:r.scene_id,asset_id:r.asset_id,camera,transition,titleFx:p.titleFx,
     subtitleStyle:p.subtitleStyle,wordMotion:p.wordMotion,intensity:p.id===2?(moving?65:45):p.id===3?35:25,
     reason:r.type==='video'?
      (moving?'В измеренных кадрах заметны изменения.':'Измеренные кадры почти не отличаются.') :
      (highDetail?'Статичный кадр с большим количеством визуальных деталей.':'Статичный кадр с умеренной детализацией.')
    };
   })
  }));
  return {recommended,plans,mode:'local-pixel-metrics',meaning:'Измерены свет, контраст, детали и разница видеокадров. Содержание изображения, речь и музыку алгоритм не распознает.'};
 }
 return {signature,frameDifference,buildPlans};
});
