import {readFileSync,writeFileSync,existsSync} from 'node:fs';
let lib=new URL('../anime-festive/node_modules/animejs/dist/modules/index.js',import.meta.url);
if(!existsSync(lib))lib=new URL('../anime_edit/node_modules/animejs/dist/modules/index.js',import.meta.url);
const {animate}=await import(lib.href);
let full=new URL('../newyear-full/motion.json',import.meta.url);
if(!existsSync(full))full=new URL('../newyear_full/motion.json',import.meta.url);
const source=JSON.parse(readFileSync(full));
function tween(a,b,ms,ease){const o={...a};const m=animate(o,{...Object.fromEntries(Object.entries(b).map(([k,v])=>[k,[a[k],v]])),duration:ms,ease,autoplay:false});return t=>{m.seek(Math.max(0,Math.min(ms,t)),true);return {...o};};}
const wipe=tween({p:0},{p:1},650,'inOutQuart');
const pop=tween({scale:.88},{scale:1},900,'outBack');
const frames=source.frames.map(s=>({...s,cycle:Math.floor(s.t/2.8),wipe:wipe((s.t%2.8)*1000),price:pop((s.local-.25)*1000)}));
writeFileSync(new URL('./motion.json',import.meta.url),JSON.stringify({...source,selected:[3],engine:'Anime.js',version:'4.2.2',frames}));
console.log('Full trailer: 1311 Anime.js motion states');process.exit(0);
