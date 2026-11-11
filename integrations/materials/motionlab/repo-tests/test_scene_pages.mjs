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
 for(const marker of ['#scene/','#cut/','#style','openScene:index','openCut:index']){
  assert.ok(pages.includes(marker),marker);
 }
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
