/* Motion Lab transitions for the production Simba/HyperFrames 2D renderer.
 * Pure seekable Canvas2D functions; no DOM, network, time or random state.
 * Stylized approximations for effects requiring scene segmentation/optical flow.
 */
export const TRANSITION_IDS = Object.freeze([
  'crossfade','push','zoom','whip','circle','diagonal','flash','blur','flip',
  'parallax','shutter','glitch','split','rotate','tiles','portal','textmask',
  'lightleak','speedramp','particles','ripple','map','postcard','filmstrip',
  'pagecurl','luma','foreground','mask','morph','match'
]);
const clamp = v => Math.min(1,Math.max(0,v));
const mix = (a,b,t) => a+(b-a)*t;
const ease = t => t*t*(3-2*t);
const sin = Math.sin;

export function renderTransition(ctx, from, to, progress, id, paint, toLabel='') {
  const p=clamp(progress), w=ctx.canvas.width,h=ctx.canvas.height,cx=w/2,cy=h/2;
  if (!TRANSITION_IDS.includes(id)) throw new Error('Unknown Motion Lab transition: '+id);
  const draw=(s,alpha=1,fn)=>{ctx.save(); if(fn)fn();paint(s,alpha);ctx.restore();};
  const overlay=(color,alpha)=>{ctx.save();ctx.globalAlpha=clamp(alpha);ctx.fillStyle=color;ctx.fillRect(0,0,w,h);ctx.restore();};
  const rect=(x,y,ww,hh)=>{ctx.beginPath();ctx.rect(x,y,ww,hh);ctx.clip()};
  const circle=(x,y,r)=>{ctx.beginPath();ctx.arc(x,y,Math.max(.001,r),0,Math.PI*2);ctx.clip()};
  const polygon=points=>{ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.clip()};
  const advance=(fromPos,toPos)=>{draw(from,1,()=>ctx.translate(fromPos,0));draw(to,1,()=>ctx.translate(toPos,0))};
  if(p===0){draw(from);return;}if(p===1){draw(to);return;}
  const e=ease(p);
  switch(id){
    case 'crossfade':draw(from);draw(to,e);break;
    case 'push':advance(-w*e,w*(1-e));break;
    case 'zoom':
      draw(from,1-e,()=>{ctx.translate(cx,cy);ctx.scale(1+.55*p,1+.55*p);ctx.translate(-cx,-cy)});
      draw(to,e,()=>{ctx.translate(cx,cy);ctx.scale(1.35-.35*e,1.35-.35*e);ctx.translate(-cx,-cy)});break;
    case 'whip':
      draw(from,1,()=>{ctx.translate(-w*e,0);ctx.filter=`blur(${sin(Math.PI*p)*Math.max(4,w*.018)}px)`});
      draw(to,1,()=>{ctx.translate(w*(1-e),0);ctx.filter=`blur(${sin(Math.PI*p)*Math.max(4,w*.018)}px)`});break;
    case 'circle':draw(from);draw(to,1,()=>circle(cx,cy,Math.hypot(w,h)*e));break;
    case 'diagonal':draw(from);draw(to,1,()=>polygon([[0,0],[w*(1.8*e-.65),0],[w*(1.8*e-.05),h],[0,h]]));break;
    case 'flash':draw(p<.5?from:to);overlay('#fff',Math.max(0,1-Math.abs(p-.5)/.23));break;
    case 'blur':draw(from,1-e,()=>{ctx.filter=`blur(${20*p}px)`});draw(to,e,()=>{ctx.filter=`blur(${20*(1-p)}px)`});break;
    case 'flip':
      draw(to);draw(from,1-p,()=>{ctx.translate(cx,0);ctx.scale(Math.max(.01,Math.abs(Math.cos(Math.PI*p))),1);ctx.translate(-cx,0)});break;
    case 'parallax':
      draw(from,1-e,()=>ctx.translate(-w*.16*p,0));draw(to,e,()=>ctx.translate(w*.22*(1-p),0));break;
    case 'shutter': {
      draw(from);draw(to,1,()=>{ctx.beginPath();const cols=9;for(let i=0;i<cols;i++){const q=clamp((p-i*.035)/.69);ctx.rect(w*i/cols,0,w/cols+.5,h*q);}ctx.clip()});break;
    }
    case 'glitch': {
      draw(from);draw(to,1,()=>{ctx.beginPath();for(let i=0;i<9;i++){if(p>.75||sin(p*59+i*4)>-.35)ctx.rect(0,h*i/9,w,h/9+.5)}ctx.clip();ctx.translate(sin(p*39)*w*.022,0)});
      overlay('#b7e8ff',Math.max(0,sin(43*p))*.10*(1-p));break;
    }
    case 'split':draw(to);draw(from,1,()=>{rect(0,0,w/2,h);ctx.translate(-w*e,0)});draw(from,1,()=>{rect(w/2,0,w/2,h);ctx.translate(w*e,0)});break;
    case 'rotate':
      draw(from,1-e,()=>{ctx.translate(cx,cy);ctx.rotate(-.65*p);ctx.scale(1+.3*p,1+.3*p);ctx.translate(-cx,-cy)});
      draw(to,e,()=>{ctx.translate(cx,cy);ctx.rotate(.45*(1-p));ctx.translate(-cx,-cy)});break;
    case 'tiles': {
      draw(from);draw(to,1,()=>{ctx.beginPath();const cols=5,rows=6;for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){const q=clamp((p-(r+c)*.047)/.45);const x=(c+.5)*w/cols,y=(r+.5)*h/rows;ctx.rect(x-q*w/cols/2,y-q*h/rows/2,q*w/cols+.5,q*h/rows+.5)}ctx.clip()});break;
    }
    case 'portal': {
      draw(from);draw(to,1,()=>{const q=.08+.95*e;ctx.beginPath();const rw=w*q,rh=h*q,x=cx-rw/2,y=cy-rh/2;ctx.moveTo(x,y+rh);ctx.lineTo(x,y+rh*.36);ctx.quadraticCurveTo(x,y,x+rw/2,y);ctx.quadraticCurveTo(x+rw,y,x+rw,y+rh*.36);ctx.lineTo(x+rw,y+rh);ctx.closePath();ctx.clip()});break;
    }
    case 'textmask': {
      draw(from);draw(to,e);
      const label=(toLabel||'ПУТЕШЕСТВИЕ').replace(/\s+/g,' ').slice(0,18).toUpperCase();
      ctx.save();ctx.globalAlpha=Math.max(0,1-e);ctx.translate(cx,cy);ctx.scale(.5+p*3,.5+p*3);ctx.fillStyle='#fff';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`900 ${Math.max(24,w*.095)}px sans-serif`;ctx.fillText(label,0,0,w*.85);ctx.restore();break;
    }
    case 'lightleak': {
      draw(from);draw(to,e);ctx.save();const q=mix(-.5,1.3,p)*w,g=ctx.createLinearGradient(q-w*.35,0,q+w*.35,0);g.addColorStop(0,'rgba(255,180,50,0)');g.addColorStop(.5,`rgba(255,224,150,${.9*sin(Math.PI*p)})`);g.addColorStop(1,'rgba(255,100,42,0)');ctx.fillStyle=g;ctx.fillRect(0,0,w,h);ctx.restore();break;
    }
    case 'speedramp': {const s=p<.5?Math.pow(2*p,4)/2:1-Math.pow(2*(1-p),3)/2;advance(-w*s,w*(1-s));break;}
    case 'particles': {
      draw(to);draw(from,1-e,()=>{ctx.beginPath();const cols=8,rows=14;for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){const n=((r*83+c*47)%31)/31,q=clamp((p-n*.42)/.58);if(q<1)ctx.rect(c*w/cols-q*w*.035,r*h/rows-q*h*.025,w/cols*(1-q*.65),h/rows*(1-q*.75))}ctx.clip()});break;
    }
    case 'ripple':{
      draw(from);draw(to,1,()=>circle(cx,cy,Math.hypot(w,h)*e));ctx.save();ctx.strokeStyle=`rgba(226,245,255,${.45*(1-e)})`;ctx.lineWidth=w*.004;for(let i=0;i<3;i++){ctx.beginPath();ctx.arc(cx,cy,Math.hypot(w,h)*Math.max(0,e-i*.08),0,2*Math.PI);ctx.stroke()}ctx.restore();break;
    }
    case 'map':{
      draw(from,1-e);draw(to,e);ctx.save();ctx.globalAlpha=Math.sin(Math.PI*p);ctx.strokeStyle='#d1f98a';ctx.lineWidth=w*.008;ctx.setLineDash([w*.014,w*.014]);ctx.beginPath();ctx.moveTo(w*.2,h*.77);ctx.quadraticCurveTo(w*.32,h*.29,w*.8,h*.27);ctx.stroke();ctx.setLineDash([]);for(const [x,y] of [[.2,.77],[.8,.27]]){ctx.beginPath();ctx.arc(w*x,h*y,w*.019,0,2*Math.PI);ctx.fillStyle='#d1f98a';ctx.fill()}ctx.restore();break;
    }
    case 'postcard':{
      draw(to);draw(from,1-e,()=>{ctx.translate(-w*e,h*.11*e);ctx.translate(cx,cy);ctx.rotate(-p*.22);ctx.scale(1-.15*p,1-.15*p);ctx.translate(-cx,-cy)});
      ctx.save();ctx.strokeStyle=`rgba(255,255,255,${.5*(1-p)})`;ctx.lineWidth=w*.02;ctx.strokeRect(w*.05-w*e,h*.05+h*.11*e,w*.9,h*.9);ctx.restore();break;
    }
    case 'filmstrip':{
      advance(-w*e,w*(1-e));ctx.save();ctx.fillStyle='#131313';for(let i=1;i<5;i++){const x=(i/4-p)*w*1.4;ctx.fillRect(x-w*.022,0,w*.044,h);for(let j=0;j<12;j++){ctx.clearRect(x-w*.01,j*h/12+h*.015,w*.02,h*.028)}}ctx.restore();break;
    }
    case 'pagecurl':{
      draw(to);draw(from,1-p,()=>{ctx.translate(w*(e*.5),0);ctx.scale(Math.max(.03,1-e),1)});ctx.save();ctx.fillStyle=`rgba(255,255,255,${.15*sin(Math.PI*p)})`;ctx.fillRect(w*(1-e),0,w*.03,h);ctx.restore();break;
    }
    case 'luma':{
      draw(from);draw(to,1,()=>{ctx.beginPath();for(const [x,y,k] of [[.2,.2,1],[.78,.31,.9],[.48,.7,1.1],[.19,.86,.8]]){ctx.moveTo(w*x+w*e*k,h*y);ctx.arc(w*x,h*y,Math.hypot(w,h)*e*k,0,2*Math.PI)}ctx.clip()});break;
    }
    case 'foreground':{
      draw(from);draw(to,1,()=>rect(0,0,w*e,h));ctx.save();const gx=mix(-w*.3,w*1.2,p);const g=ctx.createLinearGradient(gx-w*.09,0,gx+w*.09,0);g.addColorStop(0,'rgba(0,0,0,0)');g.addColorStop(.5,'rgba(0,0,0,.96)');g.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=g;ctx.fillRect(0,0,w,h);ctx.restore();break;
    }
    case 'mask':{
      draw(from);draw(to,1,()=>{const v=[];for(let i=0;i<10;i++){const a=-Math.PI/2+i*Math.PI/5,r=Math.hypot(w,h)*e*(i%2?.43:1);v.push([cx+Math.cos(a)*r,cy+sin(a)*r])}polygon(v)});break;
    }
    case 'morph':{
      draw(from);draw(to,1,()=>{const v=[];for(let i=0;i<12;i++){const a=-Math.PI/2+i*Math.PI/6,r=Math.hypot(w,h)*(i%2?.4:1)*e;v.push([cx+Math.cos(a)*r,cy+sin(a)*r])}polygon(v)});break;
    }
    case 'match': {
      draw(from,1-clamp((p-.42)/.16),()=>{ctx.translate(cx,cy);ctx.scale(1+p*.1,1+p*.1);ctx.translate(-cx,-cy)});
      draw(to,clamp((p-.42)/.16),()=>{ctx.translate(cx,cy);ctx.scale(1+(1-p)*.1,1+(1-p)*.1);ctx.translate(-cx,-cy)});break;
    }
    default:draw(from);draw(to,e);
  }
}
