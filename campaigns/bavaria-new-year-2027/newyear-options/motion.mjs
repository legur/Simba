import {writeFileSync,existsSync} from 'node:fs';
let library=new URL('../anime-festive/node_modules/animejs/dist/modules/index.js',import.meta.url);
if(!existsSync(library))library=new URL('../anime_edit/node_modules/animejs/dist/modules/index.js',import.meta.url);
const {animate}=await import(library.href);
const fps=24,duration=14,clamp=x=>Math.max(0,Math.min(1,x));
function tween(a,b,ms,ease='outCubic'){
 const o={...a};const m=animate(o,{...Object.fromEntries(Object.entries(b).map(([k,v])=>[k,[a[k],v]])),duration:ms,ease,autoplay:false});
 return t=>{m.seek(clamp(t/ms)*ms,true);return {...o};};
}
const reveal=tween({a:0,z:.78,y:60},{a:1,z:1,y:0},850,'outBack');
const enter=tween({x:850,y:80,r:14,a:0},{x:0,y:0,r:-3,a:1},1100,'outQuart');
const leave=tween({x:0,r:-3,a:1},{x:-720,r:-16,a:.5},1100,'inOutCubic');
const wipe=tween({p:0},{p:1},650,'inOutQuart');
const drift=tween({z:1,x:0},{z:1.07,x:16},14000,'inOutSine');
const states=[];
for(let n=0;n<fps*duration;n++){
 const t=n/fps;const scene=t<5.625?1:2;
 states.push({t,scene,hero:reveal((t-1.35)*1000),cardA:enter(t*1000),cardExit:leave((t-5.15)*1000),cardB:enter((t-5.45)*1000),wipe:wipe((t%2.8)*1000),drift:drift(t*1000)});
}
writeFileSync(new URL('./motion.json',import.meta.url),JSON.stringify({engine:'Anime.js',version:'4.2.2',fps,duration,states}));
console.log('Anime.js: three preview compositions, 336 frame states');process.exit(0);
