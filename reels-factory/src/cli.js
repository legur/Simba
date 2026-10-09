import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { generateHooks, createStoryboard } from './core.js';
import { renderReel } from './renderer.js';

function main() {
  const [command, inputPath, outputPath] = process.argv.slice(2);
  if (!command || !inputPath) throw new Error('Usage: node src/cli.js hooks|storyboard|render input.json [output.mp4]');
  const data = JSON.parse(readFileSync(resolve(inputPath),'utf8'));
  if (command === 'hooks') return console.log(JSON.stringify(generateHooks(data.offer),null,2));
  if (command === 'storyboard') return console.log(JSON.stringify(createStoryboard(data.offer,data.hook ?? 0),null,2));
  if (command === 'render') {
    if (!outputPath) throw new Error('Output MP4 path required');
    const result = renderReel({offer:data.offer,images:data.images,hook:data.hook ?? 0,output:outputPath,fontFile:data.fontFile});
    writeFileSync(resolve(outputPath+'.json'),JSON.stringify(result,null,2));
    return console.log(JSON.stringify(result,null,2));
  }
  throw new Error('Unknown command');
}
try { main(); } catch(e) { console.error(e.message); process.exitCode=1; }
