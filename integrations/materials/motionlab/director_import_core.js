'use strict';
/* Scene-boundary suggestions from true sampled frames of one local MP4.
 * Cuts are VISUAL CHANGE CANDIDATES, not original A2E source boundaries.
 * No recognition of people, places, speech, text, or musical beats.
 */
(function(root,factory){
 const api=factory(root.MotionLabDirectorCore||(typeof require==='function'?require('./director_core.js'):null));
 if(typeof module==='object'&&module.exports)module.exports=api;
 root.MotionLabVideoCuts=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(core){
 const round=x=>Math.round(x*100)/100;
 function median(v){if(!v.length)return 0;const a=[...v].sort((x,y)=>x-y);return a.length%2?a[(a.length-1)/2]:(a[a.length/2-1]+a[a.length/2])/2;}
 function segmentVideo(samples,duration,options={}){
  if(!core||!Array.isArray(samples)||samples.length<4||!Number.isFinite(duration)||duration<2||duration>60)throw Error('Для разбиения нужны реальные кадры видео до 60 секунд');
  const minGap=Math.max(1.25,Number(options.minGap)||2.15);
  const maxScenes=Math.min(24,Math.max(2,Number(options.maxScenes)||24));
  let last=-1;
  for(const sample of samples){
   if(!Number.isFinite(sample?.time)||sample.time<=last||sample.time<0||sample.time>duration||!sample.grid)throw Error('Некорректная последовательность кадров');
   last=sample.time;
  }
  const diffs=[];
  for(let i=1;i<samples.length;i++){
   const score=core.frameDifference(samples[i-1].grid,samples[i].grid);
   diffs.push({score,time:round((samples[i-1].time+samples[i].time)/2)});
  }
  const baseline=median(diffs.map(d=>d.score));
  const threshold=Math.max(32,baseline*2.3);
  const candidates=diffs.filter((d,i)=>d.score>=threshold&&
   (i===0||d.score>=diffs[i-1].score)&&(i===diffs.length-1||d.score>=diffs[i+1].score)&&
   d.time>=minGap&&duration-d.time>=minGap);
  const selected=[];
  for(const c of [...candidates].sort((a,b)=>b.score-a.score)){
   if(selected.length>=maxScenes-1)break;
   if(selected.every(x=>Math.abs(x.time-c.time)>=minGap))selected.push({...c,method:'visual-change'});
  }
  let cuts=[0,...selected.map(s=>s.time).sort((a,b)=>a-b),round(duration)];
  // Very long low-motion intervals must remain editable, yet scene duration
  // may not exceed the storyboard 20-second per-scene contract.
  let changed=true;
  while(changed&&cuts.length<=maxScenes){
   changed=false;
   for(let i=1;i<cuts.length;i++){
    const gap=cuts[i]-cuts[i-1];
    if(gap>20&&cuts.length<=maxScenes){cuts.splice(i,0,round((cuts[i]+cuts[i-1])/2));changed=true;break;}
   }
  }
  const accepted=new Map(selected.map(s=>[s.time,s]));
  const scenes=cuts.slice(1).map((end,i)=>({
   start:cuts[i],end,seconds:round(end-cuts[i]),boundary:accepted.has(cuts[i])?'visual-change':i?'duration-split':'start',
   confidence:accepted.has(cuts[i])?round(accepted.get(cuts[i]).score):null
  }));
  if(scenes.some(s=>s.seconds<1||s.seconds>20.01))throw Error('Невозможно уложить сцены в безопасные интервалы');
  return {scenes,sample_count:samples.length,median_difference:round(baseline),
   threshold:round(threshold),candidate_count:candidates.length,
   method:'sampled-luma-change-v1',sampled_times:samples.map(s=>s.time)};
 }
 // SRT metadata is a synchronization reference, never a substitute for ASR.
 function parseSrt(input){
  if(typeof input!=='string'||input.length>200000)throw Error('SRT отсутствует или слишком большой');
  const stamp=s=>{const m=String(s).trim().match(/^(\d{1,2}):(\d\d):(\d\d)[,.](\d{1,3})$/);
   return m?Number(m[1])*3600+Number(m[2])*60+Number(m[3])+Number(m[4].padEnd(3,'0'))/1000:NaN;};
  const cues=[];
  for(const part of input.replace(/\r/g,'').trim().split(/\n\s*\n/)){
   const lines=part.split('\n').map(x=>x.trim()).filter(Boolean);
   const index=lines.findIndex(x=>x.includes('-->'));if(index<0)continue;
   const times=lines[index].split(/\s*-->\s*/);if(times.length!==2)continue;
   const start=stamp(times[0]),end=stamp(times[1].split(' ')[0]);
   const text=lines.slice(index+1).join(' ').replace(/<[^>]*>/g,'').slice(0,600);
   if(Number.isFinite(start)&&Number.isFinite(end)&&start<end&&text)cues.push({start,end,text});
   if(cues.length>500)throw Error('В SRT слишком много строк');
  }
  if(!cues.length)throw Error('В SRT не найдены правильные временные отметки');
  return cues;
 }
 function alignCues(scenes,cues){
  return scenes.map(s=>({start:s.start,end:s.end,phrases:cues.filter(c=>c.end>s.start&&c.start<s.end)
   .map(c=>c.text).join(' ').slice(0,600)}));
 }
 return {segmentVideo,parseSrt,alignCues};
});
