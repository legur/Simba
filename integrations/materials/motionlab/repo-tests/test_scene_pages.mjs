import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const read=name=>readFileSync(resolve(root,name),'utf8');
const scenes=read('storyboard.js');
const pages=read('scene_pages.js');
const html=read('storyboard.html');
const visual=read('visual_editor.js');
test('overview gives every scene its edit control and every cut its own action',()=>{
 const dom=new Map();
 const mock=id=>{
  if(!dom.has(id))dom.set(id,{textContent:'',innerHTML:''});
  return dom.get(id);
 };
 const context={document:{getElementById:mock},location:{search:''}};
 const startup="\nstate.scenes=[makeScene({scene_id:'scene1',name:'Рим',asset_id:'a1'},0),makeScene({scene_id:'scene2',name:'Венеция',asset_id:'a2'},1),makeScene({scene_id:'scene3',name:'Милан',asset_id:'a3'},2)];renderSceneList();";
 runInNewContext(scenes.replace(/\bwire\(\);\s*$/,'')+startup,context,{timeout:1500});
 const out=mock('sceneList').innerHTML;
 assert.equal((out.match(/data-edit-scene="/g)||[]).length,3);
 assert.equal((out.match(/data-edit-cut="/g)||[]).length,2);
 assert.ok(out.includes('Переход 01 → 02'));
 assert.ok(out.includes('Переход 02 → 03'));
 assert.ok(!out.includes('data-edit-cut="0"'));
});
test('scene page, boundary page and common-style page exist',()=>{
 for(const marker of ['id="detailView"','id="detailSlot"','id="backToStoryboard"',
 'id="themePanel"','id="sceneScopePanel"','id="cutPanel"','id="allTransitions"',
 'id="applyLayoutAll"','id="inheritLayout"','id="applyFontChanges"']){
  assert.ok(html.includes(marker),marker);
 }
 for(const marker of ["return '#'+view+'/'+index", "if(view==='scene'||view==='cut')",'#style','openScene:index','openCut:index']){
  assert.ok(pages.includes(marker),marker);
 }
});
test('main storyboard displays the actual preview and restores it after leaving an editor',()=>{
 const overview={name:'overview',children:[],appendChild(child){child.parentElement=this;this.children.push(child);}};
 const detail={name:'detail',children:[],appendChild(child){child.parentElement=this;this.children.push(child);}};
 const panel={parentElement:overview};overview.children.push(panel);
 const context={document:{
  readyState:'loading',addEventListener(){},
  querySelector(sel){return sel==='.preview-panel'?panel:null;},
  getElementById(id){return id==='overviewWorkspace'?overview:id==='detailSlot'?detail:null;}
 }};
 const extra=pages.replace(/\}\)\(\);\s*$/,'globalThis.testMovePreview=placePreview;})();');
 assert.notEqual(extra,pages,'test must reach the page controller');
 runInNewContext(extra,context,{timeout:1500});
 context.testMovePreview(true);
 assert.equal(panel.parentElement,detail,'focused editor must get the player');
 context.testMovePreview(false);
 assert.equal(panel.parentElement,overview,'overview must get the real player back');
 assert.ok(pages.includes("root().classList.remove('overview-only')"),'two-column layout must be restored');
 assert.ok(!pages.includes("root().classList.add('overview-only')"),'do not hide the preview at startup');
});
test('global typography, scene overrides and v2 export guards exist',()=>{
 for(const marker of ['const shared=','function typography(scene,kind)','function setTheme(kind,patch)',
 'function setSceneTypography(kind,patch)','function applyLayoutToAll(kind)',
 'function inheritLayout(kind)','function inheritTypography(kind)','global_theme:', 'typography:{title:']){
  assert.ok(visual.includes(marker),marker);
 }
 assert.ok(visual.includes('DRAFT_NOT_DELIVERED'));
 assert.ok(!pages.includes('fetch('));
 assert.ok(!pages.includes('upload('));
});


test('connected A2E scenes never show stock art and bind the actual verified MP4 poster',()=>{
 const dom=new Map();
 const mock=id=>{if(!dom.has(id))dom.set(id,{innerHTML:'',textContent:''});return dom.get(id)};
 const ctx={document:{getElementById:mock},location:{search:''}};
 const extra="\nconst approved=makeScene({scene_id:'alaska-01',name:'Аляска',asset_id:'a2e:test',duration_s:5,media:{kind:'video',asset_sha256:'b'.repeat(64),duration_s:5}},0);state.scenes=[approved];state.request={id:'approved-source'};globalThis.before=scenePhoto(approved);renderSceneList();globalThis.beforeHtml=document.getElementById('sceneList').innerHTML;localPreviews.set('alaska-01',{assetId:'a2e:test',type:'video',shaVerified:true,url:'blob:original-a2e',poster:'data:image/jpeg;base64,A2EFRAME'});renderSceneList();globalThis.afterHtml=document.getElementById('sceneList').innerHTML;globalThis.after=previewFor(approved);";
 runInNewContext(scenes.replace(/\bwire\(\);\s*$/,'')+extra,ctx,{timeout:2000});
 assert.match(ctx.before,/^data:image\/svg\+xml/);
 assert.ok(!ctx.before.includes('static.wixstatic.com'));
 assert.ok(!ctx.beforeHtml.includes('static.wixstatic.com'));
 assert.ok(ctx.afterHtml.includes('data:image/jpeg;base64,A2EFRAME'));
 assert.equal(ctx.after.shaVerified,true);
 assert.ok(!ctx.afterHtml.includes('static.wixstatic.com'));
});


test('private A2E launch never falls back silently to Bavaria demo while loading or failing',()=>{
 const bridge=read('motionlab_drive_bridge.js');
 const css=read('storyboard.css');
 assert.match(html,/id="privateProjectGate"/);
 assert.match(html,/id="privateProjectGateText"/);
 assert.match(html,/private-a2e-gate-20261113/);
 assert.match(css,/body\.private-project-pending #overviewWorkspace/);
 assert.match(scenes,/document\.body\.classList\.add\('private-project-pending'\)/);
 assert.match(scenes,/complete:\(\)=>/);
 assert.match(scenes,/state\.scenes\.every\(s=>previewFor\(s\)\?\.shaVerified===true\)/);
 assert.match(scenes,/ДЕМО · /);
 assert.match(bridge,/api\.complete\?\.\(data\.launch\)/);
 assert.match(bridge,/api\.failed\?\./);
 assert.match(bridge,/safeEditorHash=.*scene\\\/\\d/);
 assert.match(bridge,/sessionStorage\.getItem\('simba:motionlab:project-link:v1'\)/);
});


test('universal storyboard dynamically builds 3, 10, 15 and 24 actual scene cards and transitions',()=>{
 const dom=new Map();
 const mock=id=>{
  if(!dom.has(id))dom.set(id,{textContent:'',innerHTML:''});
  return dom.get(id);
 };
 const context={document:{getElementById:mock},location:{search:''}};
 const setup=String.raw\`
globalThis.dynamicallyBuilt=[];
for (const count of [3,10,15,24]) {
 state.request={id:'verified-owner-project',projectId:'dynamic-test'};
 state.scenes=Array.from({length:count},(_,i)=>makeScene({
  scene_id:'source-'+String(i+1).padStart(2,'0'),
  asset_id:'a2e:'+String(i%2),
  duration_s:2.4,
  name:'A2E video scene '+(i+1),
  media:{kind:'video',asset_sha256:'b'.repeat(64),duration_s:5.0},
  title_text:'Approved scene title '+(i+1)
 },i));
 renderSceneList();
 dynamicallyBuilt.push({
  count,
  cards:(document.getElementById('sceneList').innerHTML.match(/data-edit-scene="/g)||[]).length,
  cuts:(document.getElementById('sceneList').innerHTML.match(/data-edit-cut="/g)||[]).length,
  first:document.getElementById('sceneList').innerHTML.includes('A2E video scene 1'),
  last:document.getElementById('sceneList').innerHTML.includes('A2E video scene '+count),
  stock:document.getElementById('sceneList').innerHTML.includes('static.wixstatic.com'),
  counter:document.getElementById('sceneCount').textContent
 });
}
\`;
 runInNewContext(scenes.replace(/\bwire\(\);\s*$/,'')+setup,context,{timeout:2000});
 for(const row of context.dynamicallyBuilt){
  assert.equal(row.cards,row.count);
  assert.equal(row.cuts,row.count-1);
  assert.equal(row.counter,String(row.count));
  assert.equal(row.first,true);
  assert.equal(row.last,true);
  assert.equal(row.stock,false);
 }
 assert.equal(context.dynamicallyBuilt.length,4);
});
