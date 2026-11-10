import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
function parseJs(file, exposure, cutMarker){
  let source=readFileSync(resolve(root,file),'utf8');
  if(cutMarker)source=source.slice(0,source.lastIndexOf(cutMarker));
  const sandbox={document:{readyState:'loading',addEventListener(){}}};
  runInNewContext(source+'\n;globalThis.__tested={'+exposure+'};',sandbox,{timeout:1200});
  return sandbox.__tested;
}
test('the four creative libraries have advertised counts and unique IDs',()=>{
 const {OBJECTS,ROUTES,MUSIC,TEMPLATES}=parseJs('creative.js','OBJECTS,ROUTES,MUSIC,TEMPLATES');
 for(const [list,expected] of [[OBJECTS,15],[ROUTES,10],[MUSIC,8],[TEMPLATES,5]]){
  assert.equal(list.length,expected);
  assert.equal(new Set(list.map(e=>e.id)).size,expected);
 }
});
test('each object effect is backed by a real CSS animation class',()=>{
 const {OBJECTS}=parseJs('creative.js','OBJECTS');
 const css=readFileSync(resolve(root,'creative.css'),'utf8');
 for(const x of OBJECTS)assert.ok(css.includes('.object-target.fx-'+x.id),x.id);
});
test('all template references exist in the existing four libraries',()=>{
 const {TEMPLATES}=parseJs('creative.js','TEMPLATES');
 const {CATALOG}=parseJs('storyboard.js','CATALOG','\nwire();');
 for(const t of TEMPLATES){
  for(const [key,source] of [['camera','camera'],['transition','transitions'],['title','title'],['subtitle','subtitle']]){
   assert.ok(CATALOG[source].some(([id])=>id===t[key]),t.id+' has unknown '+key+': '+t[key]);
  }
 }
});
test('music cues are bounded and derived from manually selected BPM',()=>{
 const {makeCues}=parseJs('creative.js','makeCues');
 // draw input values through minimal fake DOM by applying same pure function manually
 const sandbox={document:{readyState:'loading',addEventListener(){},getElementById(id){return {value:id==='bpm'?'110':id==='musicLength'?'24':''}}}};
 let s=readFileSync(resolve(root,'creative.js'),'utf8');
 runInNewContext(s+'\n;globalThis.cueTest=()=>{chosen.music="double-time";return makeCues()};',sandbox,{timeout:1200});
 const times=sandbox.cueTest();
 assert.ok(times.length>=10&&times.length<=180);
 assert.ok(times.every((v,i)=>i===0||v.time_s>times[i-1].time_s));
});
test('draft export never claims a render or agent ACK',()=>{
 const src=readFileSync(resolve(root,'creative.js'),'utf8');
 for(const marker of ["DRAFT_NOT_DELIVERED","rendering_authorized:false","publishing_authorized:false","paid_services_authorized:false"])
  assert.ok(src.includes(marker));
 assert.ok(!src.includes("SIMBA_MOTIONLAB_ACK"));
});
