from pathlib import Path
import json,importlib.util,subprocess
from PIL import Image,ImageDraw

R=Path(__file__).resolve().parent;W,H=720,1280
FULL=R.parent/'newyear-full'
if not (FULL/'render.py').exists():FULL=R.parent/'newyear_full'
spec=importlib.util.spec_from_file_location('bavaria_full',FULL/'render.py');full=importlib.util.module_from_spec(spec);spec.loader.exec_module(full)
opt=full.opt;M=json.loads((R/'motion.json').read_text());GOLD,CREAM,RED,NAVY=opt.GOLD,opt.CREAM,opt.RED,opt.NAVY

def txt(im,*a,**k):
    layer=Image.new('RGBA',im.size);opt.txt(layer,*a,**k);im.alpha_composite(layer)
def body(s):
    t=s['t'];i=s['i'];cycle=s['cycle'];im=Image.new('RGBA',(W,H),(*NAVY,255))
    if cycle%3==0:
        for j in range(3):
            raw=full.bg(i,max(full.CUTS[i],t-.3*j),1.05+.015*j);panel=opt.cover(raw,234,1090);im.alpha_composite(panel,(j*243,160))
    elif cycle%3==1:
        im=opt.dim(full.bg(i,t,1.04),20);p=s['wipe']['p'];old=full.bg(i,max(full.CUTS[i],t-.45),1.13)
        if p<1:
            for j in range(6):
                x=int(j*W/6);edge=int((j+1)*W/6);shift=round(p*(H+100)+j*18*p);im.alpha_composite(old.crop((x,0,edge,H)),(x,shift))
    else:
        left=opt.cover(full.bg(i,t,1.06),416,H);right=opt.cover(full.bg(i,max(full.CUTS[i],t-.5),1.12),294,H);im.alpha_composite(left,(0,0));im.alpha_composite(right,(426,0));ImageDraw.Draw(im).line((421,0,421,H),fill=(*GOLD,255),width=8)
    d=ImageDraw.Draw(im);d.rectangle((0,88,620,209),fill=(*RED,255));txt(im,'НОВЫЙ ГОД',36,106,55,CREAM,True)
    d.rectangle((35,667,685,884 if i==6 else 858),fill=(*RED,255))
    for k,line in enumerate(full.TITLES[i]):txt(im,line.upper(),W/2,692+k*67,41,CREAM,True,True)
    if i==6:txt(im,'Дополнительная поездка',W/2,830,25,GOLD,False,True)
    opt.snowfall(im,t,.5);opt.caption(im,t,1000);opt.brand(im);return im

def offer(s):
    im=opt.dim(full.bg(7,s['t'],1.04),90);d=ImageDraw.Draw(im)
    d.rectangle((0,88,690,209),fill=(*RED,255));txt(im,'НОВЫЙ ГОД В БАВАРИИ',36,120,34,CREAM,True)
    d.rectangle((35,317,685,920),fill=(*RED,255))
    full.reveal_text(im,s,0,'28.12.2026–03.01.2027',W/2,255,30,GOLD)
    # Anime.js controls the distinct large-price pop; composite on transparency.
    layer=Image.new('RGBA',(W,H));m=s['reveal'][1];opt.txt(layer,'1399 €',W/2,377+m['y'],122,GOLD,True,True,a=round(m['a']*255),stroke=1);z=s['price']['scale'];layer=layer.resize((round(W*z),round(H*z)),Image.Resampling.BICUBIC);im.alpha_composite(layer,(round((W-layer.width)/2),round((H-layer.height)/2)))
    full.reveal_text(im,s,2,'Вместо 1499 €',W/2,563,34)
    full.reveal_text(im,s,2,'Скидка 100 € с человека',W/2,623,30,GOLD,True)
    full.reveal_text(im,s,3,'С человека при',W/2,719,31)
    full.reveal_text(im,s,3,'двухместном размещении',W/2,767,29)
    full.reveal_text(im,s,4,'6 ночей с завтраками',W/2,849,29)
    opt.snowfall(im,s['t'],.3);opt.caption(im,s['t'],1000);opt.brand(im);return im

def end(s):
    im=opt.dim(full.bg(8,s['t'],1.04),60);d=ImageDraw.Draw(im)
    d.rectangle((0,88,620,209),fill=(*RED,255));txt(im,'НОВЫЙ ГОД',36,106,55,CREAM,True)
    plate=Image.new('RGBA',(W,H));ImageDraw.Draw(plate).polygon([(0,331),(720,261),(720,901),(0,971)],fill=(*RED,248));im.alpha_composite(plate)
    full.reveal_text(im,s,0,'Напишите в WhatsApp',W/2,394,35,CREAM,True)
    full.reveal_text(im,s,1,'«БАВАРИЯ»',W/2,474,65,GOLD,True)
    full.reveal_text(im,s,2,'058-677-8492',W/2,626,59,CREAM,True)
    full.reveal_text(im,s,3,'Пришлю полную программу',W/2,751,29)
    full.reveal_text(im,s,3,'28.12.2026–03.01.2027',W/2,845,27,GOLD)
    opt.snowfall(im,s['t'],.4);opt.caption(im,s['t'],1020);opt.brand(im);return im

def compose(s):
    if s['t']<full.CUTS[2]:
        st=dict(opt.M['states'][min(len(opt.M['states'])-1,round(s['t']*24))]);st['t']=s['t'];st['wipe']={'p':max(0,min(.999999,1-st['wipe']['p']))};return opt.option3(st)
    return body(s) if s['i']<7 else offer(s) if s['i']==7 else end(s)

def main():
    pic=R/'picture.mp4';log=open(R/'encode.log','w')
    p=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r','24','-i','-','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','19','-pix_fmt','yuv420p',str(pic)],stdin=subprocess.PIPE,stderr=log)
    samples=[64,150,342,475,550,678,866,1008,1014,1025,1040,1090,1140,1180,1198,1220,1250,1305]
    for n,s in enumerate(M['frames']):
        im=compose(s).convert('RGB');p.stdin.write(im.tobytes())
        if n%192==0:print(f'Trailer: {n}/1311',flush=True)
        if n in samples:im.save(R/f'check_{n:04}.jpg')
    p.stdin.close();assert p.wait()==0,(R/'encode.log').read_text()
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(pic),'-i',str(opt.BASE/'current/Bavaria_Google_A2E_review.mp4'),'-map','0:v','-map','1:a','-c','copy','-movflags','+faststart',str(R/'Bavaria_NewYear_Trailer.mp4')],check=True)
    print('Complete full third variant',flush=True)
if __name__=='__main__':main()
