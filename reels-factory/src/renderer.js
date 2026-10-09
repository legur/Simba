import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createStoryboard } from './core.js';

export function renderReel({ offer, images, output, hook = 0, ffmpeg = 'ffmpeg', fontFile }) {
  if (!Array.isArray(images) || images.length < 1) throw new Error('At least one image required');
  if (!output) throw new Error('Output path required');
  const storyboard = createStoryboard(offer, hook);
  const temp = mkdtempSync(join(tmpdir(), 'simba-reel-'));
  try {
    const args = ['-hide_banner','-loglevel','error','-y'];
    for (let i=0;i<storyboard.scenes.length;i++) {
      const scene = storyboard.scenes[i];
      args.push('-loop','1','-framerate','30','-t',String(scene.seconds),'-i',resolve(images[i % images.length]));
    }
    const filters = [];
    for (let i=0;i<storyboard.scenes.length;i++) {
      const scene = storyboard.scenes[i];
      const textPath = join(temp, `scene-${i}.txt`);
      writeFileSync(textPath,scene.text,'utf8');
      const font = fontFile ? `:fontfile='${resolve(fontFile).replaceAll('\\','/').replaceAll(':','\\:').replaceAll("'","\\'")}'` : '';
      filters.push(`[${i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,drawbox=x=50:y=680:w=980:h=550:color=black@0.55:t=fill,drawtext=textfile='${textPath.replaceAll("'","\\'")}':fontcolor=white:fontsize=58:line_spacing=18:x=(w-text_w)/2:y=(h-text_h)/2${font},format=yuv420p,fps=30,trim=duration=${scene.seconds},setpts=PTS-STARTPTS[v${i}]`);
    }
    filters.push(storyboard.scenes.map((_,i)=>`[v${i}]`).join('')+`concat=n=${storyboard.scenes.length}:v=1:a=0[out]`);
    args.push('-filter_complex',filters.join(';'),'-map','[out]','-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',resolve(output));
    const result = spawnSync(ffmpeg,args,{encoding:'utf8',maxBuffer:1024*1024*4});
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(`FFmpeg failed: ${result.stderr || result.status}`);
    return {output:resolve(output),durationSeconds:storyboard.scenes.reduce((s,x)=>s+x.seconds,0),storyboard};
  } finally { rmSync(temp,{recursive:true,force:true}); }
}
