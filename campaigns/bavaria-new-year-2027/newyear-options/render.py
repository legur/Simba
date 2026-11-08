from pathlib import Path
import sys,math,json,subprocess,functools,random
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import numpy as np

R=Path(__file__).resolve().parent;W,H=720,1280
import importlib.util
BASE=R.parent/'anime-festive'
if not (BASE/'render.py').exists():BASE=R.parent/'anime_edit'
spec=importlib.util.spec_from_file_location('bavaria_existing_render',BASE/'render.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
M=json.loads((R/'motion.json').read_text());FPS=M['fps']
CREAM=(255,242,212);GOLD=(246,197,93);RED=(122,20,37);NAVY=(12,22,37)
def font(n,b=False,serif=False):return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVu'+('Serif' if serif else 'Sans')+('-Bold' if b else '')+'.ttf',n)
@functools.lru_cache(32)
def F(n,b=False,serif=False):return font(n,b,serif)
def txt(im,s,x,y,n=40,c=CREAM,b=False,center=False,serif=False,a=255,stroke=0):
 ImageDraw.Draw(im).text((x,y),s,font=F(n,b,serif),fill=(*c,int(a)),anchor='ma' if center else 'la',stroke_width=stroke,stroke_fill=(*NAVY,int(a)))
@functools.lru_cache(22)
def frame(i,n):return Image.open(base.FILES[i][max(0,min(len(base.FILES[i])-1,n))]).convert('RGB')
def bg(i,t,z=1):
 fs=base.FILES[i];local=t if i==1 else max(0,t-5.625);n=int(local*24)%len(fs);im=frame(i,n);ww,hh=round(W*z),round(H*z);im=im.resize((ww,hh),Image.Resampling.BICUBIC);return im.crop(((ww-W)//2,(hh-H)//2,(ww+W)//2,(hh+H)//2)).convert('RGBA')
def dim(im,alpha=65):im.alpha_composite(Image.new('RGBA',(W,H),(*NAVY,alpha)));return im
def cover(im,w,h):
 k=max(w/im.width,h/im.height);im=im.resize((round(im.width*k),round(im.height*k)),Image.Resampling.BICUBIC);x=(im.width-w)//2;y=(im.height-h)//2;return im.crop((x,y,x+w,y+h))
rand=random.Random(31012027);snow=[(rand.random()*W,rand.random()*H,rand.uniform(1.2,3.5),rand.uniform(17,43),rand.random()*6.28) for _ in range(78)]
def snowfall(im,t,amount=1):
 d=ImageDraw.Draw(im)
 for x,y,r,v,phase in snow[:int(len(snow)*amount)]:
  xx=(x+16*math.sin(t*.6+phase))%W;yy=(y+t*v)%H;d.ellipse((xx-r,yy-r,xx+r,yy+r),fill=(255,250,230,150))
def garland(im,t):
 d=ImageDraw.Draw(im)
 # Decorative evergreen corners and a warm string of lights, separate from photographed landmarks.
 for side in [0,1]:
  for k in range(18):
   x=k*12 if side==0 else W-k*12;y=20+20*math.sin(k/5)
   d.line((x-25,y-25,x+25,y+35),fill=(22,56,37,255),width=5)
   d.line((x-20,y+12,x+25,y-20),fill=(34,76,47,255),width=4)
 for j in range(12):
  x=32+j*59;y=56+33*math.sin(j/11*math.pi);q=int(190+60*math.sin(t*1.6+j*.7)**2)
  d.ellipse((x-5,y-5,x+5,y+5),fill=(*GOLD,q))
 for x,y,r in [(74,146,25),(648,162,32)]:
  d.line((x,24,x,y-r),fill=(*GOLD,240),width=2);d.ellipse((x-r,y-r,x+r,y+r),fill=(*RED,255),outline=(*GOLD,255),width=2);d.ellipse((x-r*.4,y-r*.5,x,y),fill=(201,71,65,240))
def brand(im,c=CREAM):txt(im,'SIMBA BY BON TOURS',W/2,1145,18,c,True,True)
def caption(im,t,y=990):
 L=next((v for v in base.subs if v['a']<=t<v['b']),None)
 if not L:return
 toks=L['tokens'];size=40
 while F(size,True).getlength(' '.join(toks))>636:size-=1
 f=F(size,True);xx=(W-f.getlength(' '.join(toks)))/2;active=max([k for k,a in enumerate(L['starts']) if a<=t] or [0])
 for k,tok in enumerate(toks):txt(im,tok,xx,y,size,GOLD if k==active else CREAM,True,stroke=2);xx+=f.getlength(tok+' ')
def flash(im,a):
 if a>0:im.alpha_composite(Image.new('RGBA',(W,H),(255,229,157,round(a*215))))

def option1(s):
 t=s['t'];im=dim(bg(s['scene'],t,s['drift']['z']),45);garland(im,t)
 if t<1.35:
  n=3-int(t/.45);p=(t%.45)/.45
  txt(im,'31 ДЕКАБРЯ',W/2,284,34,GOLD,True,True)
  txt(im,str(n),W/2,405,220,CREAM,True,True,serif=True,a=255-round(80*p),stroke=2)
  txt(im,'РЕГЕНСБУРГ',W/2,730,32,CREAM,True,True)
 else:
  m=s['hero'];layer=Image.new('RGBA',(W,H));txt(layer,'2027',W/2,350,192,GOLD,True,True,serif=True,stroke=2)
  zz=m['z'];layer=layer.resize((round(W*zz),round(H*zz)),Image.Resampling.BICUBIC);layer.putalpha(layer.getchannel('A').point(lambda x:int(x*m['a'])));im.alpha_composite(layer,(round((W-layer.width)/2),round((H-layer.height)/2+m['y'])))
  if t<5.625:
   txt(im,'НОВЫЙ ГОД',W/2,650,42,CREAM,True,True,stroke=2);txt(im,'В БАВАРИИ',W/2,713,48,CREAM,True,True,stroke=2)
  else:
   txt(im,'НОВЫЙ ГОД',W/2,650,38,CREAM,True,True,stroke=2);txt(im,'В РЕГЕНСБУРГЕ',W/2,713,42,CREAM,True,True,stroke=2)
  burst=max(0,1-(t-1.35)/2)
  d=ImageDraw.Draw(im)
  for k in range(38):
   theta=k*2.399;radius=(t-1.35)*180+20;xx=W/2+radius*math.cos(theta);yy=H*.43+radius*.8*math.sin(theta)
   if burst>0:d.line((xx,yy,xx+10*math.cos(theta),yy+10*math.sin(theta)),fill=(*GOLD,round(230*burst)),width=3)
  flash(im,max(0,1-(t-1.35)/.22))
 if abs(t-5.625)<.35:flash(im,.36*(1-abs(t-5.625)/.35))
 snowfall(im,t,.8);caption(im,t);brand(im);return im

def postcard(i,t,label):
 card=Image.new('RGBA',(552,730),(*CREAM,255));photo=cover(bg(i,t),516,614);card.alpha_composite(photo,(18,18));txt(card,label,276,660,27,RED,True,True,serif=True);return card
def placecard(im,card,x,y,angle,a=1):
 card=card.rotate(angle,Image.Resampling.BICUBIC,expand=True);shadow=Image.new('RGBA',card.size);shadow.putalpha(card.getchannel('A').point(lambda v:round(v*.45*a)));shadow=shadow.filter(ImageFilter.GaussianBlur(13));im.alpha_composite(shadow,(int(x+14),int(y+18)));card.putalpha(card.getchannel('A').point(lambda v:round(v*a)));im.alpha_composite(card,(int(x),int(y)))
def option2(s):
 t=s['t'];im=Image.new('RGBA',(W,H),(*RED,255));d=ImageDraw.Draw(im)
 for k in range(6):d.arc((-120-k*30,280+k*110,840+k*30,880+k*100),0,150,fill=(184,124,68,80),width=2)
 garland(im,t)
 txt(im,'Новогодняя',W/2,115,51,CREAM,True,True,True);txt(im,'Бавария',W/2,179,62,CREAM,True,True,True)
 txt(im,'28.12.2026–03.01.2027',W/2,265,24,GOLD,False,True)
 if t<6.5:
  m=s['cardA'];ex=s['cardExit'];placecard(im,postcard(1,t,'РЕГЕНСБУРГ'),80+m['x']+ex['x'],315+m['y'],ex['r'],m['a'])
 if t>5.45:
  m=s['cardB'];placecard(im,postcard(2,t,'НОВЫЙ ГОД В РЕГЕНСБУРГЕ'),80+m['x'],315+m['y'],-m['r'],m['a'])
 snowfall(im,t,.35);caption(im,t,1080);txt(im,'SIMBA BY BON TOURS',W/2,1210,17,GOLD,True,True);return im

def option3(s):
 t=s['t'];i=s['scene'];cycle=int(t/2.8);im=Image.new('RGBA',(W,H),(*NAVY,255));d=ImageDraw.Draw(im)
 if cycle==0:
  for j in range(3):
   raw=bg(1 if j!=1 else 2,t+j*.6,1.05);p=cover(raw,234,1020);im.alpha_composite(p,(j*243,170))
 elif cycle%2:
  im=dim(bg(i,t,1.04),20);p=s['wipe']['p'];old=bg(1 if i==2 else 2,max(0,t-.7),1.04)
  if p<1:
   for j in range(6):
    edge=int((j+1)*W/6);xx=int(j*W/6);shift=round((1-p)*(H+100)+j*18*(1-p));im.alpha_composite(old.crop((xx,0,edge,H)),(xx,shift))
 else:
  left=cover(bg(1,t,1.06),416,H);right=cover(bg(2,t,1.04),294,H);im.alpha_composite(left,(0,0));im.alpha_composite(right,(426,0));d=ImageDraw.Draw(im);d.line((421,0,421,H),fill=(*GOLD,255),width=8)
 d=ImageDraw.Draw(im);d.rectangle((0,88,620,209),fill=(*RED,255));txt(im,'НОВЫЙ ГОД',36,106,55,CREAM,True)
 # Large typography and changing layouts, rather than one fixed text over a full-screen background.
 if t<5.625:
  d.rectangle((35,650,685,854),fill=(*RED,242));txt(im,'БАВАРИЯ',W/2,669,72,CREAM,True,True);txt(im,'2027',W/2,755,66,GOLD,True,True)
 else:
  d.rectangle((35,682,685,868),fill=(*RED,242));txt(im,'31 ДЕКАБРЯ',W/2,706,48,GOLD,True,True);txt(im,'РЕГЕНСБУРГ',W/2,778,45,CREAM,True,True)
 snowfall(im,t,.5);caption(im,t,1000);brand(im);return im

def render_variant(v):
 path=R/f'Bavaria_NewYear_Option_{v}.mp4';pic=R/f'picture_{v}.mp4';log=open(R/f'encode_{v}.log','w');proc=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r','24','-i','-','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','19','-pix_fmt','yuv420p',str(pic)],stdin=subprocess.PIPE,stderr=log)
 fn=[None,option1,option2,option3][v]
 for n,s in enumerate(M['states']):
  im=fn(s).convert('RGB');proc.stdin.write(im.tobytes())
  if n in [12,40,72,120,132,144,165,225,315]:im.save(R/f'v{v}_{n:03}.jpg')
 proc.stdin.close();assert proc.wait()==0
 subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(pic),'-i',str(BASE/'current/Bavaria_Google_A2E_review.mp4'),'-t','14','-map','0:v','-map','1:a','-c:v','copy','-af','afade=t=out:st=13.7:d=0.3','-c:a','aac','-b:a','192k','-movflags','+faststart',str(path)],check=True)
 print(f'Preview {v} complete',flush=True)
if __name__=='__main__':
 for v in [1,2,3]:render_variant(v)
