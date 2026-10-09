import {readFileSync,writeFileSync} from 'node:fs';
import {resolve,dirname,isAbsolute,join} from 'node:path';
import {generateHooks,createStoryboard} from './core.js';
import {renderReel} from './renderer.js';
function main() {
  const [command,file,out]=process.argv.slice(2);
  if (!['hooks','storyboard','render'].includes(command)||!file) throw Error('Usage: node src/cli.js hooks|storyboard|render input.json [output.mp4]');
  const absolute=resolve(file),base=dirname(absolute),data=JSON.parse(readFileSync(absolute,'utf8'));
  const hooks=data.hooks ?? generateHooks(data.offer);
  if (command==='hooks') return console.log(JSON.stringify(hooks,null,2));
  if (command==='storyboard') return console.log(JSON.stringify(createStoryboard(data.offer,data.hook??0,hooks),null,2));
  if (!out) throw Error('Provide output.mp4');
  const rel=p=>isAbsolute(p)?p:join(base,p);
  const result=renderReel({offer:data.offer,hook:data.hook??0,customHooks:hooks,images:(data.images??[]).map(rel),output:out,fontFile:data.fontFile?rel(data.fontFile):null});
  writeFileSync(resolve(out+'.json'),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify({output:result.output,durationSeconds:result.durationSeconds,codec:result.codec,width:result.width,height:result.height},null,2));
}
try {main()} catch(e) {console.error(e.message);process.exitCode=1}
