import { animate } from './node_modules/animejs/dist/modules/index.js';
import { writeFileSync } from 'node:fs';
const fps=24,duration=54.625;
const cuts=[0,5.625,14.083333,19.458333,22.458333,27.666667,35.458333,42,49.208333,54.625];
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
function tween(from,to,ms,ease='outCubic'){
 const state={...from};const a=animate(state,{...Object.fromEntries(Object.entries(to).map(([k,v])=>[k,[from[k],v]])),duration:ms,ease,autoplay:false});
 return t=>{a.seek(clamp(t/ms)*ms,true);return {...state};};
}
const reveals=Array.from({length:7},()=>tween({opacity:0,y:24,scale:.985},{opacity:1,y:0,scale:1},750));
const blend=tween({v:0},{v:1},900,'inOutSine');
const backgrounds=cuts.slice(0,-1).map((t,i)=>tween({zoom:1.015,x:-4,y:3},{zoom:1.055,x:4,y:-3},(cuts[i+1]-t)*1000,'inOutSine'));
const frames=[];
for(let n=0;n<Math.round(duration*fps);n++){
 const t=n/fps;let i=cuts.findIndex((v,k)=>k<9&&t>=v&&t<cuts[k+1]);if(i<0)i=8;
 let layers=[{i,opacity:1,...backgrounds[i]((t-cuts[i])*1000)}],glow=0;
 for(let k=1;k<9;k++)if(Math.abs(t-cuts[k])<.45){
  const q=blend((t-cuts[k]+.45)*1000).v;
  layers=[{i:k-1,opacity:1,...backgrounds[k-1]((t-cuts[k-1])*1000)},{i:k,opacity:q,...backgrounds[k]((t-cuts[k])*1000)}];
  glow=Math.sin(q*Math.PI)*.27;
 }
 let titleStart=cuts[i];if(i===3)titleStart=cuts[2];
 const title=reveals[0]((t-titleStart-.1)*1000);
 const card=reveals.slice(1).map((r,k)=>r((t-cuts[i]-.12-k*.18)*1000));
 frames.push({t,i,layers,glow,title,card});
}
writeFileSync(new URL('./motion.json',import.meta.url),JSON.stringify({engine:'Anime.js',version:'4.2.2',variant:3,fps,duration,cuts,frames}));
console.log(`Anime.js 4.2.2: ${frames.length} deterministic frame states`);
process.exit(0);
