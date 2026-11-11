/* Motion Lab / Bon Tours: reproducible Canvas2D subtitle styling, driven by real Whisper word timestamps.
 * Shared by Simba and HyperFrames. Does not transcribe or modify narration.
 * This is a render-time approximation of the browser-based 24 CSS styles.
 */
export const STYLE_IDS = Object.freeze([
  'clean','soft-shadow','capsule','bar','outline','two-line',
  'cinema','letterbox','editorial','spotlight','glow',
  'price-tag','offer-pill','gold-card','gradient-bar','countdown',
  'word-focus','karaoke','pop','marker','luxury','glass','neon','travel-stamp'
]);
export const MOTION_IDS = Object.freeze(['karaoke','active-pop','caption-swap','highlight-strip','word-reveal']);
export const COLOR_MAP = Object.freeze({lime:'#c9f47d',gold:'#f0be6b',sky:'#8cd9ff',white:'#ffffff'});
const limit = (x,lo,hi) => Math.min(hi,Math.max(lo,x));
const rounded = (g,x,y,w,h,r=12) => {
  g.beginPath();
  if(typeof g.roundRect === 'function') g.roundRect(x,y,w,h,Math.min(r,w/2,h/2));
  else g.rect(x,y,w,h);
};
const textFont = (style,size) =>
  ['editorial','luxury'].includes(style) ? `italic 700 ${size}px Georgia, serif` :
  ['cinema','countdown'].includes(style) ? `800 ${size}px Montserrat, sans-serif` :
  `700 ${size}px Montserrat, sans-serif`;
const uppercase = style => ['cinema','countdown','letterbox','travel-stamp'].includes(style);

function background(g,style,box,accent,w,h,scale){
  const {x,y,width,height}=box;
  if(['clean','soft-shadow','outline','spotlight','glow','word-focus','pop','marker','editorial'].includes(style))return;
  g.save();
  if(['bar','letterbox','gradient-bar'].includes(style)){
    const bx=Math.max(0,x-(style==='bar'?w*.07:18));
    const bw=Math.min(w-bx,width+(style==='bar'?w*.14:36));
    g.fillStyle=style==='gradient-bar'?gradient(g,x,y,width,height):style==='letterbox'?'rgba(4,8,13,.94)':'rgba(8,18,26,.82)';
    rounded(g,bx,y,bw,height,style==='letterbox'?0:15);g.fill();
    if(style==='bar'){g.fillStyle=accent;g.fillRect(bx,y,Math.max(4,scale*5),height);}
    if(style==='letterbox'){g.fillStyle='rgba(244,246,248,.45)';g.fillRect(bx,y,bw,2);g.fillRect(bx,y+height-2,bw,2);}
  }else{
    const fills={
      capsule:'rgba(7,20,32,.83)', 'two-line':'rgba(6,17,25,.75)',
      'price-tag':'rgba(248,252,244,.97)','offer-pill':'rgba(12,35,28,.9)',
      'gold-card':'rgba(43,29,15,.94)',countdown:'rgba(7,18,30,.94)',
      karaoke:'rgba(6,20,32,.88)',luxury:'rgba(14,20,28,.86)',
      glass:'rgba(166,214,223,.24)',neon:'rgba(4,20,34,.92)',
      'travel-stamp':'rgba(10,27,34,.9)'
    };
    g.fillStyle=fills[style]||'rgba(7,18,27,.78)';
    rounded(g,x,y,width,height,style==='travel-stamp'?2:12);g.fill();
    if(['gold-card','countdown','luxury','glass','neon','travel-stamp'].includes(style)){
      g.lineWidth=style==='travel-stamp'?3:2;
      g.strokeStyle=style==='gold-card'||style==='luxury'?'#d9b374':style==='glass'?'rgba(231,249,243,.55)':style==='neon'?'#4adffa':accent;
      g.setLineDash(style==='travel-stamp'?[10,6]:[]);rounded(g,x+1,y+1,width-2,height-2,style==='travel-stamp'?2:12);g.stroke();g.setLineDash([]);
    }
    if(style==='two-line'){g.fillStyle=accent;g.fillRect(x,y,5,height);}
    if(style==='luxury'){g.fillStyle='#d9b374';g.fillRect(x+12,y+8,width-24,2);g.fillRect(x+12,y+height-10,width-24,2);}
  }
  g.restore();
}
function gradient(g,x,y,w,h){
  const gradient=g.createLinearGradient(x,y,x+w,y+h);
  gradient.addColorStop(0,'rgba(23,48,68,.95)');
  gradient.addColorStop(.5,'rgba(42,93,92,.94)');
  gradient.addColorStop(1,'rgba(31,48,38,.95)');
  return gradient;
}
function rowsForWords(g,visibleWords,maxWidth){
  const space=g.measureText(' ').width,lines=[[]];let width=0;
  visibleWords.forEach(item=>{
    const wordWidth=g.measureText(item.text).width;
    if(lines.at(-1).length && width+space+wordWidth>maxWidth){lines.push([]);width=0;}
    width += (lines.at(-1).length?space:0)+wordWidth;
    lines.at(-1).push({...item,width:wordWidth});
  });
  return lines;
}
/**
 * Render an already aligned subtitle line with validated Motion Lab style.
 * line.words: [[displayWord, absoluteStartSeconds], ...] (from Whisper).
 */
export function drawStyledSubtitle(g,line,t,config,W,H,layout=null,typography=null){
  if(!line||!Array.isArray(line.words)||!line.words.length||!config)return;
  const style=STYLE_IDS.includes(config.style)?config.style:'clean';
  const motion=MOTION_IDS.includes(config.motion)?config.motion:'karaoke';
  const accent=COLOR_MAP[config.color]||COLOR_MAP.lime;
  const factor=limit(Number(config.scale_percent)||100,80,135)/100 * (layout ? layout.scale / 100 : 1) * (typography ? typography.size / 100 : 1);
  const size=Math.round(50*factor*W/1080);
  const words=line.words.map(([w,start],i)=>({
    index:i,text:uppercase(style)?String(w).toUpperCase():String(w),start:Number(start)
  }));
  let active=0;
  for(let i=0;i<words.length;i++)if(t>=words[i].start)active=i;
  const groupSize=Math.max(2,Math.ceil(words.length/3));
  const display=motion==='caption-swap'?
    words.filter(({index})=>Math.floor(index/groupSize)===Math.floor(active/groupSize)):
    words;
  const fullLength=words.length;
  const opacity=limit((t-line.t0)/.14,0,1)*limit((line.t1-t)/.14,0,1);
  if(opacity<=0)return;
  const top=H*.26,center=H*.52,bottom=Number.isFinite(line.y)?line.y:H*.74;
  const cy=layout ? H * layout.y / 100 : config.position==='top'?top:config.position==='middle'?center:bottom;
  const cx=layout ? W * layout.x / 100 : W / 2;
  const font=typography ? `700 ${size}px "${typography.family}"` : textFont(style,size);
  g.save();g.globalAlpha*=opacity;g.font=font;g.textAlign='left';g.textBaseline='middle';
  const lineHeight=Math.round(size*1.32),paddingY=Math.round(size*.43),paddingX=Math.round(size*.65);
  // Layout preview is 72% max wrap width, centered at an exact frame-% X.
  // Constrain actual width further as necessary for 6% safe horizontal inset.
  const maxWordsWidth = layout
    ? Math.min(W * .72,
      2 * Math.min(cx - W * .06, W * .94 - cx) - paddingX * 2)
    : W * .82;
  if (layout && maxWordsWidth <= 0) {
    g.restore();
    throw new Error('Unsafe Motion Lab subtitle X');
  }
  const rows=rowsForWords(g,display,maxWordsWidth);
  const widths=rows.map(row=>row.reduce((sum,item,i)=>sum+item.width+(i?g.measureText(' ').width:0),0));
  const bodyWidth=Math.max(1,...widths);
  const blockWidth=Math.min(W*.94,bodyWidth+paddingX*2);
  const blockHeight=rows.length*lineHeight+paddingY*2;
  const left=layout ? cx-blockWidth/2 : limit((W-blockWidth)/2,12,W-blockWidth-12);
  const y=layout ? cy-blockHeight/2 : limit(cy-blockHeight/2,H*.11,H*.83-blockHeight);
  if (layout && (left < W*.06 || left + blockWidth > W*.94 ||
                 y < H*.06 || y + blockHeight > H*.94 ||
                 bodyWidth > maxWordsWidth)) {
    g.restore();
    throw new Error('Motion Lab subtitle exceeds safe overlay bounds');
  }
  const box={x:left,y,width:blockWidth,height:blockHeight};
  background(g,style,box,accent,W,H,W/1080);

  if(['offer-pill','countdown','travel-stamp'].includes(style)){
    g.save();g.font=`800 ${Math.round(13*W/1080)}px Montserrat, sans-serif`;
    g.textAlign='left';g.textBaseline='middle';
    g.fillStyle=style==='countdown'?'#ffdc98':accent;
    g.fillText(style==='offer-pill'?'СПЕЦПРЕДЛОЖЕНИЕ':style==='countdown'?'ОГРАНИЧЕННОЕ ПРЕДЛОЖЕНИЕ':'BON TOURS • TRAVEL',left+paddingX,y+Math.min(22,paddingY*.6));
    g.restore();
  }
  const space=g.measureText(' ').width;
  const normalColor=['price-tag'].includes(style)?'#10251d':
    ['gold-card','luxury'].includes(style)?'#ffdc9a':
    style==='neon'?'#b7faff':'#f5f4ed';
  const inactiveColor=typography ? typography.color : (style==='spotlight'?'rgba(226,233,231,.55)':normalColor);
  rows.forEach((row,r)=>{
    const rowWidth=widths[r];
    let x=style==='two-line'?left+paddingX:Math.max(left+paddingX,(cx-rowWidth/2));
    const baseline=y+paddingY+lineHeight*(r+.5);
    row.forEach((word)=>{
      const current=word.index===active;
      const already=word.index<active;
      const hidden=motion==='word-reveal'&&word.index>active;
      if(hidden){x+=word.width+space;return;}
      g.save();
      if(style==='outline'){g.lineWidth=3;g.strokeStyle='rgba(1,12,25,.9)';g.strokeText(word.text,x,baseline);}
      const activeFill=style==='price-tag'?'#426f38':style==='neon'?'#63efff':accent;
      if(current && (motion==='highlight-strip'||style==='marker'||style==='karaoke'||style==='spotlight')){
        g.fillStyle=accent;
        const pad=motion==='highlight-strip'||style==='karaoke'?5:2;
        if(style==='marker'){g.fillRect(x-1,baseline+size*.15,word.width+2,Math.max(3,size*.17));}
        else{rounded(g,x-pad,baseline-size*.56,word.width+pad*2,size*1.12,5);g.fill();}
      }
      let fill=current?(style==='price-tag'?'#335d2a':accent):inactiveColor;
      if((motion==='highlight-strip'||style==='karaoke'||style==='spotlight')&&current)fill='#13251c';
      if(motion==='karaoke'&&!current&&!already)g.globalAlpha*=.58;
      if(style==='word-focus'&&!current)g.globalAlpha*=.55;
      if(style==='glow'||style==='neon'){g.shadowColor=style==='neon'?'#55e4ff':accent;g.shadowBlur=Math.max(5,size*.27);}
      else {g.shadowColor='rgba(0,0,0,.86)';g.shadowBlur=style==='soft-shadow'?15:6;g.shadowOffsetY=style==='soft-shadow'?5:2;}
      g.fillStyle=fill;
      const pop=current&&(motion==='active-pop'||style==='word-focus'||style==='pop');
      if(pop){const scale=1.12;g.translate(x+word.width/2,baseline);g.scale(scale,scale);g.fillText(word.text,-word.width/2,-size*.08);}
      else g.fillText(word.text,x,baseline);
      g.restore();
      x+=word.width+space;
    });
  });
  g.restore();
}