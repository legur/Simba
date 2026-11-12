/* Simba Motion Lab: local, zero-upload, exact SHA word review helper.
 * It DOES NOT listen for you, invent timings, mark rendering approved or
 * generate a verified alignment receipt. The owner must actually listen and
 * explicitly check every original WAV word before downloading a QA statement.
 */
'use strict';
(function(root){
 const SHA=/^[a-f0-9]{64}$/;
 const OWNER=/^owner:[A-Za-z0-9_-]{3,80}$/;
 const MAX_BYTES=160000;
 const norm=s=>String(s).normalize('NFKC').toLocaleLowerCase('ru').replace(/ё/g,'е');
 const words=s=>norm(s).match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu)||[];
 const hex=async bytes=>{
  const h=await crypto.subtle.digest('SHA-256',bytes);
  return Array.from(new Uint8Array(h)).map(x=>x.toString(16).padStart(2,'0')).join('');
 };
 const fail=code=>{throw Error(code);};
 const check=(ok,code)=>{if(!ok)fail(code);};
 const typedInt=x=>Number.isInteger(x) && !Object.is(x,true);
 async function inspect(sourceBytes,wavBytes,draftBytes){
  check(sourceBytes instanceof Uint8Array && wavBytes instanceof Uint8Array
   && draftBytes instanceof Uint8Array && sourceBytes.length>0
   && sourceBytes.length<=100000 && draftBytes.length>0
   && draftBytes.length<=MAX_BYTES && wavBytes.length>1024,
   'Нужны три подлинных локальных файла: текст, WAV и черновик.');
  let source,draft;
  try{
   source=new TextDecoder('utf-8',{fatal:true}).decode(sourceBytes);
   draft=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(draftBytes));
  }catch{fail('Исходный текст или JSON не читается.');}
  check(draft && typeof draft==='object' && !Array.isArray(draft)
   && draft.schema==='bontours.montage.audio-alignment-draft/v1'
   && draft.status==='DRAFT_ACOUSTIC_TIMINGS_REQUIRE_INDEPENDENT_LISTENING_QA'
   && draft.audio_alignment_verified===false
   && draft.render_authorized===false && draft.publication_authorized===false
   && typeof draft.project_id==='string' && draft.project_id.length>=3
   && SHA.test(draft.source_sha256||'') && SHA.test(draft.narration_sha256||'')
   && SHA.test(draft.audio_revision_sha256||''),
   'Нужен исходный непринятый акустический черновик.');
  check(await hex(sourceBytes)===draft.source_sha256,
   'Текст не совпадает с утвержденным SHA-256.');
  check(await hex(wavBytes)===draft.narration_sha256,
   'WAV не совпадает с утвержденным SHA-256.');
  const lines=source.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  check(Array.isArray(draft.lines) && draft.lines.length===lines.length
   && lines.length>0 && lines.length<=120,
   'Количество строк в WAV-черновике и тексте различается.');
  let previousEnd=0,wordCount=0;
  for(let i=0;i<lines.length;i++){
   const line=draft.lines[i],expected=words(lines[i]);
   check(line && line.line_id==='line-'+String(i+1).padStart(2,'0')
    && expected.length>0 && Array.isArray(line.words)
    && line.words.length===expected.length,
    'Не совпадают строки или слова утвержденного текста.');
   for(let j=0;j<expected.length;j++){
    const w=line.words[j];
    check(w && w.text===expected[j]
     && Number.isInteger(w.word_start_ms) && Number.isInteger(w.word_end_ms)
     && previousEnd<=w.word_start_ms && w.word_start_ms<w.word_end_ms
     && w.word_end_ms<=120000,
     'Слово или таймкод черновика не соответствует исходному тексту.');
    previousEnd=w.word_end_ms;wordCount++;
   }
  }
  check(draft.word_count===wordCount,
   'Число слов в черновике не совпадает с утвержденным текстом.');
  return {draft,source,draftSha:await hex(draftBytes),lines:lines.map((text,i)=>({
   line_id:draft.lines[i].line_id,text,words:draft.lines[i].words
  })),wordCount};
 }
 function prepareReview(context,reviewer,reviewNotes,entries,now=new Date()){
  check(context && context.draft && Array.isArray(context.lines)
    && SHA.test(context.draftSha||''), 'Сначала проверьте оригиналы.');
  check(typeof reviewer==='string' && OWNER.test(reviewer),
    'Укажите проверяющего как owner:ID.');
  check(typeof reviewNotes==='string' && reviewNotes.trim().length>=30,
    'Опишите действительное прослушивание в 30 символах.');
  check(Array.isArray(entries)&&entries.length===context.lines.length,
    'Не все строки проверены.');
  let previousEnd=0;
  const line_reviews=entries.map((entry,i)=>{
   const src=context.lines[i];
   check(entry && entry.line_id===src.line_id
    && typeof entry.listening_notes==='string'
    && entry.listening_notes.trim().length>=15
    && Array.isArray(entry.words)
    && entry.words.length===src.words.length,
    'Добавьте заметку о прослушивании каждой строки.');
   const out=entry.words.map((w,j)=>{
    const original=src.words[j];
    const start=Number(w.word_start_ms),end=Number(w.word_end_ms);
    check(w.text===original.text && w.listened===true
     && Number.isInteger(start) && Number.isInteger(end)
     && previousEnd<=start && start<end && end<=120000,
     'Каждое слово нужно прослушать, затем проверить его время.');
    const changed=start!==original.word_start_ms || end!==original.word_end_ms;
    if(changed)check(typeof w.correction_note==='string'
     && w.correction_note.trim().length>=10,
      'Объясните исправленные таймкоды слова.');
    previousEnd=end;
    return {text:w.text,word_start_ms:start,word_end_ms:end,listened:true,
     ...(changed?{correction_note:w.correction_note.trim()}:{})};
   });
   return {line_id:src.line_id,listening_notes:entry.listening_notes.trim(),words:out};
  });
  check(now instanceof Date && Number.isFinite(now.getTime()), 'Недействительное время проверки.');
  return {schema:'bontours.montage.audio-listening-review/v1',
   project_id:context.draft.project_id,
   source_sha256:context.draft.source_sha256,
   audio_revision_sha256:context.draft.audio_revision_sha256,
   narration_sha256:context.draft.narration_sha256,
   draft_sha256:context.draftSha,
   reviewer,reviewed_at_utc:now.toISOString(),
   method:'independent_manual_listening_against_original_wav',
   every_word_listened:true,no_missing_spoken_words:true,
   no_render_or_publication_authorized:true,
   review_notes:reviewNotes.trim(),line_reviews};
 }
 root.MotionLabAudioReview={inspect,prepareReview,words};
})(globalThis);
