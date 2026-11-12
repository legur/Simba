/* Offline browser QA: original bytes match and no auto-approval or upload. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {webcrypto,createHash} from 'node:crypto';
import fs from 'node:fs';
import vm from 'node:vm';

const src=fs.readFileSync(new URL('../audio_review_core.js',import.meta.url),'utf8');
const html=fs.readFileSync(new URL('../audio-review.html',import.meta.url),'utf8');
const context=vm.createContext({crypto:webcrypto,Uint8Array,TextDecoder,Date,Number,Error,
  Object,String,Array,JSON});
vm.runInContext(src,context);
const core=context.MotionLabAudioReview;
const textBytes=Uint8Array.from(Buffer.from('Sample narration 2','utf8'));
const wavBytes=Uint8Array.from(Buffer.alloc(2048,8)); // synthetic, not real client WAV
const sha=data=>createHash('sha256').update(data).digest('hex');
const draft={
  schema:'bontours.montage.audio-alignment-draft/v1',
  status:'DRAFT_ACOUSTIC_TIMINGS_REQUIRE_INDEPENDENT_LISTENING_QA',
  project_id:'test-reel',
  source_sha256:sha(textBytes),narration_sha256:sha(wavBytes),
  audio_revision_sha256:'a'.repeat(64),
  method:'whisperx-ctc-local',language:'ru',
  lines:[{
    line_id:'line-01',phrase_start_ms:50,phrase_end_ms:850,
    words:[
      {text:'sample',word_start_ms:50,word_end_ms:280,acoustic_score:.9},
      {text:'narration',word_start_ms:300,word_end_ms:600,acoustic_score:.9},
      {text:'2',word_start_ms:610,word_end_ms:850,acoustic_score:.9}
    ]
  }],
  word_count:3,
  independent_audio_qa_completed:false,
  audio_alignment_verified:false,render_authorized:false,publication_authorized:false
};
const bytes=x=>Uint8Array.from(Buffer.from(JSON.stringify(x),'utf8'));
async function inspected(){return core.inspect(textBytes,wavBytes,bytes(draft));}
function rows(c){return c.lines.map(line=>({
  line_id:line.line_id,
  listening_notes:'Explicit synthetic QA unit-test line, not a real listening session.',
  words:line.words.map(w=>({
    text:w.text,word_start_ms:w.word_start_ms,word_end_ms:w.word_end_ms,
    listened:true
  }))
}));}
const reviewer='owner:legur';
const overall='Synthetic CI contract only. NO HUMAN AUDIO WAS LISTENED TO HERE.';

test('Local reviewer page has strict no-network CSP and original audio controls',()=>{
  assert.match(html,/<audio id="player" controls/);
  assert.match(html,/connect-src 'none'/);
  assert.match(html,/form-action 'none'/);
  assert.match(html,/audio_review_core\.js/);
  assert.match(html,/id="sourceFile"/);
  assert.match(html,/id="draftFile"/);
  assert.match(html,/id="wavFile"/);
  assert.doesNotMatch(src+html, /(?:\bfetch\s*\(|XMLHttpRequest|\.sendBeacon\s*\()/);
  assert.match(html,/type='checkbox'/);
  assert.match(html,/Скачать отчет проверки JSON/);
});
test('Source text/WAV sha and actual acoustic text tokens are bound to the draft',async()=>{
  const c=await inspected();
  assert.equal(c.wordCount,3);
  assert.equal(c.draftSha,sha(bytes(draft)));
  assert.equal(c.lines[0].words[1].text,'narration');
  await assert.rejects(core.inspect(textBytes,Uint8Array.from(Buffer.alloc(2048,9)),bytes(draft)),/WAV/);
  await assert.rejects(core.inspect(Uint8Array.from(Buffer.from('wrong text')),wavBytes,bytes(draft)),/Текст/);
  await assert.rejects(core.inspect(textBytes,wavBytes,bytes({...draft,status:'AUDIO_ALIGNMENT_VERIFIED'})),/черновик/);
  const changed=structuredClone(draft);
  changed.lines[0].words[1].text='wrong';
  await assert.rejects(core.inspect(textBytes,wavBytes,bytes(changed)),/Слово или таймкод/);
});
test('Review is explicit per-word, bound to original draft SHA, not render authorization',async()=>{
  const c=await inspected();
  const obj=core.prepareReview(c,reviewer,overall,rows(c),new Date('2026-11-12T16:00:00Z'));
  assert.equal(obj.draft_sha256,sha(bytes(draft)));
  assert.equal(obj.schema,'bontours.montage.audio-listening-review/v1');
  assert.equal(obj.no_render_or_publication_authorized,true);
  assert.equal(obj.every_word_listened,true);
  assert.equal(obj.line_reviews[0].words.length,3);
  assert.equal(obj.reviewed_at_utc,'2026-11-12T16:00:00.000Z');
  assert.equal(obj.line_reviews[0].words[0].listened,true);
  assert.equal(obj.status,undefined);
  assert.equal(obj.render_authorized,undefined);
});
test('Unlistened words, generic notes and inferred approval are rejected',async()=>{
  const c=await inspected(),a=rows(c);
  a[0].words[1].listened=false;
  assert.throws(()=>core.prepareReview(c,reviewer,overall,a),/каждое слово/i);
  a[0].words[1].listened=true;
  assert.throws(()=>core.prepareReview(c,reviewer,'OK',a),/30 символах/);
  assert.throws(()=>core.prepareReview(c,'employee:anonymous',overall,a),/owner:ID/);
});
test('Time corrections need actual notes; overlap is blocked',async()=>{
  const c=await inspected(),a=rows(c);
  a[0].words[1].word_start_ms=320;
  assert.throws(()=>core.prepareReview(c,reviewer,overall,a),/исправленные/);
  a[0].words[1].correction_note='Reviewed this exact word onset against original audio.';
  assert.equal(core.prepareReview(c,reviewer,overall,a).line_reviews[0].words[1].word_start_ms,320);
  a[0].words[1].word_start_ms=200;
  assert.throws(()=>core.prepareReview(c,reviewer,overall,a),/время/);
});
