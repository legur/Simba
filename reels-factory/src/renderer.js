import {spawnSync} from 'node:child_process';
import {existsSync, mkdtempSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {createStoryboard} from './core.js';

function run(binary, args) {
  const r = spawnSync(binary,args,{encoding:'utf8',maxBuffer:4*1024*1024});
  if (r.error) throw r.error;
  if (r.status !== 0) throw Error(`${binary} failed (${r.status}): ${r.stderr?.slice(-1800)}`);
  return r.stdout;
}
function ffEscape(p) { return p.replaceAll('\\','/').replaceAll(':','\\:').replaceAll("'", "'\\''").replaceAll(',','\\,'); }
function wrapText(text, limit=23) {
  return text.split('\n').flatMap(para=>{
    const words=para.split(/\s+/).filter(Boolean),lines=[];
    let line='';
    for (const word of words) {
      if (line && (line+' '+word).length>limit) {lines.push(line);line=word;}
      else line=line?line+' '+word:word;
    }
    lines.push(line);
    return lines;
  }).join('\n');
}
export function renderReel({offer,images,output,hook=0,customHooks=null,fontFile=null,ffmpeg='ffmpeg',ffprobe='ffprobe'}) {
  if (!Array.isArray(images) || images.length===0) throw Error('At least one image required');
  for (const file of images) if (!existsSync(resolve(file))) throw Error(`Missing image: ${file}`);
  if (!output) throw Error('Output path required');
  if (fontFile && !existsSync(resolve(fontFile))) throw Error(`Missing font: ${fontFile}`);
  const board=createStoryboard(offer,hook,customHooks);
  const temp=mkdtempSync(join(tmpdir(),'simba-reels-'));
  const segments=[];
  try {
    for(let i=0;i<board.scenes.length;i++) {
      const scene=board.scenes[i], image=resolve(images[i%images.length]);
      const textPath=join(temp,`title-${i}.txt`),segment=join(temp,`segment-${i}.mp4`);
      writeFileSync(textPath,wrapText(scene.text),'utf8');
      const font=fontFile?`fontfile='${ffEscape(resolve(fontFile))}':`:'';
      const filter=`scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,drawbox=x=65:y=620:w=950:h=680:color=black@0.65:t=fill,drawtext=${font}textfile='${ffEscape(textPath)}':fontcolor=white:fontsize=56:line_spacing=18:x=(w-text_w)/2:y=(h-text_h)/2:fix_bounds=1,format=yuv420p`;
      run(ffmpeg,['-hide_banner','-loglevel','error','-y','-loop','1','-framerate','30','-i',image,'-t',String(scene.seconds),'-vf',filter,'-an','-c:v','libx264','-preset','ultrafast','-crf','25','-pix_fmt','yuv420p','-r','30',segment]);
      segments.push(segment);
    }
    const concatPath=join(temp,'concat.txt');
    writeFileSync(concatPath,segments.map(p=>`file '${p.replaceAll("'","'\\''")}'`).join('\n')+'\n');
    run(ffmpeg,['-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',concatPath,'-c','copy','-movflags','+faststart',resolve(output)]);
    const probe=JSON.parse(run(ffprobe,['-v','error','-show_entries','format=duration:stream=codec_name,width,height','-of','json',resolve(output)]));
    const video=probe.streams.find(s=>s.codec_name==='h264');
    if (!video || video.width!==1080 || video.height!==1920 || Math.abs(Number(probe.format.duration)-14)>0.2) throw Error('Output QC failed');
    return {output:resolve(output),durationSeconds:Number(probe.format.duration),width:video.width,height:video.height,codec:video.codec_name,storyboard:board};
  } finally {rmSync(temp,{recursive:true,force:true});}
}
