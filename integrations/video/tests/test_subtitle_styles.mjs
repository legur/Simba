import test from 'node:test';
import assert from 'node:assert/strict';
import {STYLE_IDS,MOTION_IDS,drawStyledSubtitle} from '../template/subtitle_styles.js';

class CanvasRecorder {
  constructor() {this.draws=[];this.globalAlpha=1;this.font='';this.fillStyle='#fff';}
  save(){this.draws.push('save');}
  restore(){this.draws.push('restore');}
  beginPath(){}
  rect(){}
  roundRect(){}
  fill(){this.draws.push('fill');}
  stroke(){this.draws.push('stroke');}
  fillRect(x,y,w,h){this.draws.push(['rect',Number(x.toFixed(2)),Number(y.toFixed(2)),Number(w.toFixed(2)),Number(h.toFixed(2))]);}
  fillText(v,x,y){this.draws.push(['text',v,Number(x.toFixed(2)),Number(y.toFixed(2))]);}
  strokeText(v,x,y){this.draws.push(['outline',v]);}
  setLineDash(){}
  translate(){}
  scale(){}
  measureText(text){const n=Number(this.font.match(/(\d+)px/)?.[1]||50);return {width:String(text).length*n*.52};}
  createLinearGradient(){return {addColorStop(){}};}
}
const line={t0:.5,t1:4.2,y:1420,words:[
  ['Новый',.5],['год',1.1],['в',1.6],['Баварии',2.1]
]};

test('all 120 combined styles draw deterministic word-timed subtitles',()=>{
  assert.equal(STYLE_IDS.length,24);
  assert.equal(MOTION_IDS.length,5);
  for(const style of STYLE_IDS)for(const motion of MOTION_IDS){
    const options={style,motion,color:'gold',scale_percent:100,position:'bottom'};
    const canvasA=new CanvasRecorder(),canvasB=new CanvasRecorder();
    drawStyledSubtitle(canvasA,line,2.28,options,1080,1920);
    drawStyledSubtitle(canvasB,line,2.28,options,1080,1920);
    assert.deepEqual(canvasA.draws,canvasB.draws,`${style}/${motion}: deterministic`);
    assert.ok(canvasA.draws.some(v=>Array.isArray(v)&&v[0]==='text'),`${style}/${motion}: no text`);
  }
});
test('word-reveal hides future words and uses actual word starts',()=>{
 const ctx=new CanvasRecorder();
 drawStyledSubtitle(ctx,line,1.23,{style:'clean',motion:'word-reveal',color:'lime',scale_percent:100,position:'bottom'},1080,1920);
 const visible=ctx.draws.filter(d=>Array.isArray(d)&&d[0]==='text').map(d=>d[1]);
 assert.deepEqual(visible,['Новый','год']);
});
test('outside of subtitle interval no content is painted',()=>{
 const ctx=new CanvasRecorder();
 drawStyledSubtitle(ctx,line,7,{style:'clean',motion:'karaoke'},1080,1920);
 assert.equal(ctx.draws.length,0);
});
