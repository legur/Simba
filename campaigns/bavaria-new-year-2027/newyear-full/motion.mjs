import {writeFileSync,existsSync} from 'node:fs';
let library=new URL('../anime-festive/node_modules/animejs/dist/modules/index.js',import.meta.url);
if(!existsSync(library))library=new URL('../anime_edit/node_modules/animejs/dist/modules/index.js',import.meta.url);
const {animate}=await import(library.href);
const fps=24,duration=54.625,cuts=[0,5.625,14.083333,19.458333,22.458333,27.666667,35.458333,42,49.208333,54.625];
const clamp=x=>Math.max(0,Math.min(1,x));
function tween(a,b,ms,ease='outCubic'){
 const o={...a};const m=animate(o,{...Object.fromEntries(Object.entries(b).map(([k,v])=>[k,[a[k],v]])),duration:ms,ease,autoplay:false});
 return t=>{m.seek(clamp(t/ms)*ms,true);return {...o};};
}
const incoming=tween({x:850,y:60,r:12,a:0},{x:0,y:0,r:-3,a:1},1100,'outQuart');
const outgoing=tween({x:0,r:-3,a:1},{x:-820,r:-16,a:.3},1100,'inOutCubic');
const reveal=tween({a:0,y:30,z:.97},{a:1,y:0,z:1},700,'outCubic');
const moves=cuts.slice(0,-1).map((t,i)=>tween({z:1.015},{z:1.06},(cuts[i+1]-t)*1000,'inOutSine'));
const frames=[];
for(let n=0;n<Math.round(fps*duration);n++){
 const t=n/fps;let i=cuts.findIndex((v,k)=>k<9&&t>=v&&t<cuts[k+1]);if(i<0)i=8;
 const dt=t-cuts[i];
 frames.push({t,i,local:dt,incoming:incoming(dt*1000),outgoing:outgoing(dt*1000),title:reveal((t-cuts[i===3?2:i]-.12)*1000),reveal:Array.from({length:6},(_,k)=>reveal((dt-.12-k*.18)*1000)),move:moves[i](dt*1000)});
}
writeFileSync(new URL('./motion.json',import.meta.url),JSON.stringify({engine:'Anime.js',version:'4.2.2',selected:[1,2],fps,duration,cuts,frames}));
console.log('Two full New Year edits: 1311 Anime.js frame states');process.exit(0);
