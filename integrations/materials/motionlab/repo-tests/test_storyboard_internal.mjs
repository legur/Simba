import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const content=readFileSync(resolve(root,'storyboard.js'),'utf8');
const script=content.replace(/\bwire\(\);\s*$/,'');
assert.notEqual(script,content,'remove browser bootstrap for pure contract tests');
const env={};
runInNewContext(script+'\nglobalThis.check={rendererIssues,makeScene,buildResult,updateKey,state,RENDER_MOVES,RENDER_TRANSITIONS};',env,{timeout:1500});
const {rendererIssues,makeScene,buildResult,updateKey,state,RENDER_MOVES,RENDER_TRANSITIONS}=env.check;
const base={camera:'none',title:'',titleFx:'none',transition:'none',subtitleStyle:'clean',wordMotion:'karaoke'};
test('production capability registry represents real make_video.py IDs',()=>{
 assert.equal(RENDER_MOVES.size,7);
 assert.equal(RENDER_TRANSITIONS.size,30);
 assert.equal(rendererIssues([base]).length,0);
 assert.equal(rendererIssues([base,{...base,transition:'crossfade'}]).length,0);
});
test('preview-only cameras and titles cannot be presented as renderer-ready',()=>{
 const problems=rendererIssues([{...base,camera:'float',title:'Мюнхен',titleFx:'light-sweep'}]);
 assert.ok(problems.length>=2);
 assert.ok(problems.some(x=>x.includes('камера')));
 assert.ok(problems.some(x=>x.includes('титра')));
});
test('missing transition and per-scene subtitle support is identified',()=>{
 const errs=rendererIssues([base,{...base,transition:'none',subtitleStyle:'luxury'}]);
 assert.ok(errs.some(x=>x.includes('переход')));
 assert.ok(errs.some(x=>x.includes('один стиль')));
});
test('approved scene asset and title cannot be overwritten in editor',()=>{
 const scene=makeScene({asset_id:'archive-clip-01',title_text:'Утвержденный титр'},0);
 state.scenes=[scene];state.selectedIndex=0;state.request={id:'confirmed'};
 updateKey('asset','replacement');updateKey('title','Подмена');updateKey('duration',20);
 assert.equal(scene.asset,'archive-clip-01');
 assert.equal(scene.title,'Утвержденный титр');
 assert.equal(scene.duration,3);
 state.request=null;
});
test('private preview information never leaves selection v1',()=>{
 const scene=makeScene({scene_id:'clip01',asset_id:'asset01',preview_url:'https://private.test/signed?token=no',media:{kind:'video',asset_sha256:'a'.repeat(64),duration_s:5}},0);
 state.scenes=[scene];state.selectedIndex=0;state.selectedOption=1;state.request={id:'request-abc',projectId:'demo',fingerprint:'b'.repeat(64)};state.bridge=null;
 const selection=buildResult();
 const raw=JSON.stringify(selection);
 assert.equal(selection.decision.state,'DRAFT_NOT_DELIVERED');
 assert.ok(!raw.includes('private.test'));
 assert.ok(!raw.includes('asset_sha256'));
 assert.ok(!raw.includes('token=no'));
 assert.equal(selection.scenes[0].asset_id,'asset01');
 assert.equal(selection.guards.run_render,false);
});
