import {createServer} from 'node:http';
import {readFileSync,writeFileSync,mkdtempSync,rmSync,existsSync} from 'node:fs';
import {join,extname} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {dirname} from 'node:path';
import {generateHooks,createStoryboard} from './core.js';
import {renderReel} from './renderer.js';

const root=dirname(dirname(fileURLToPath(import.meta.url)));
const html=readFileSync(join(root,'web','index.html'));
const host='127.0.0.1',port=Number(process.env.PORT||4173);
const maxBytes=24*1024*1024;
const jobs=new Map();
function respond(res,status,data,type='application/json') {
  res.writeHead(status,{'Content-Type':type,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
  res.end(type==='application/json'?JSON.stringify(data):data);
}
async function body(req) {
  let size=0,chunks=[];
  for await(const chunk of req) {size+=chunk.length;if(size>maxBytes) throw Error('Upload too large (24 MB limit)');chunks.push(chunk);}
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}
function imagesToFiles(images,dir) {
  if (!Array.isArray(images)||images.length<1||images.length>6) throw Error('Upload 1–6 images');
  return images.map((image,i)=>{
    if(!image||!['image/jpeg','image/png','image/webp'].includes(image.mime)||typeof image.data!=='string') throw Error('Unsupported image');
    const bytes=Buffer.from(image.data,'base64');
    if(!bytes.length||bytes.length>8*1024*1024) throw Error('Invalid image size');
    const extension={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}[image.mime];
    const path=join(dir,'photo-'+i+extension);writeFileSync(path,bytes);return path;
  });
}
const server=createServer(async(req,res)=>{
  try {
    const path=new URL(req.url,'http://localhost').pathname;
    if(req.method==='GET'&&path==='/') return respond(res,200,html,'text/html; charset=utf-8');
    if(req.method==='POST'&&path==='/api/plan') {
      const input=await body(req);
      return respond(res,200,{hooks:generateHooks(input.offer),storyboard:createStoryboard(input.offer,input.hook??0,input.hooks??null)});
    }
    if(req.method==='POST'&&path==='/api/render') {
      const input=await body(req),dir=mkdtempSync(join(tmpdir(),'simba-ui-'));
      try {
        const images=imagesToFiles(input.images,dir),output=join(dir,'reel.mp4');
        const result=renderReel({offer:input.offer,images,output,hook:input.hook??0,customHooks:input.hooks??null});
        const id=crypto.randomUUID();
        jobs.set(id,{dir,output});
        return respond(res,200,{id,url:'/video/'+id,seconds:result.durationSeconds});
      } catch(error) {rmSync(dir,{recursive:true,force:true});throw error;}
    }
    if(req.method==='GET'&&path.startsWith('/video/')) {
      const id=path.slice('/video/'.length),job=jobs.get(id);
      if(!job||!existsSync(job.output)) return respond(res,404,{error:'Video not found'});
      return respond(res,200,readFileSync(job.output),'video/mp4');
    }
    return respond(res,404,{error:'Not found'});
  }catch(e){respond(res,400,{error:String(e.message||e)})}
});
server.listen(port,host,()=>console.log('SIMBA REELS FACTORY: http://'+host+':'+port));
process.on('SIGINT',()=>{for(const job of jobs.values())rmSync(job.dir,{recursive:true,force:true});process.exit(0)});
