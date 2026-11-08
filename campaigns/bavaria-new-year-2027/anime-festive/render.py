from pathlib import Path
import json,math,re,subprocess,functools,unicodedata
from PIL import Image,ImageDraw,ImageFont
import numpy as np

R=Path(__file__).resolve().parent;W,H=720,1280
M=json.loads((R/'motion.json').read_text());CUTS=M['cuts']
GOLD=(239,199,118);WHITE=(250,247,240)
FONT=Path('/usr/share/fonts/truetype/dejavu')
@functools.lru_cache(64)
def font(n,bold=False):return ImageFont.truetype(str(FONT/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),n)
def norm(s):return ''.join(c for c in s.lower().replace('ё','е') if c.isalnum())
def seconds(s):
 a,b,c=s.replace(',','.').split(':');return int(a)*3600+int(b)*60+float(c)
subs=[]
aw=json.loads((R/'alignment.json').read_text())['words']
for p in (R/'current/Bavaria_Reel.srt').read_text().strip().split('\n\n'):
 lines=p.splitlines();a,b=map(seconds,lines[1].split(' --> '));txt=' '.join(lines[2:]);tokens=txt.split();actual=[v for v in aw if v[1]>=a-.1 and v[1]<b-.03]
 total=sum(len(norm(v[0])) for v in actual) or 1;marks=[];c=0
 for word,start,end in actual:marks.append((c/total,max(a,start)));c+=len(norm(word))
 c=0;starts=[];den=sum(len(norm(v)) for v in tokens) or 1
 for tok in tokens:
  f=c/den;eligible=[x for frac,x in marks if frac<=f+1e-6];starts.append(eligible[-1] if eligible else a);c+=len(norm(tok))
 subs.append({'a':a,'b':b,'tokens':tokens,'starts':starts})

FILES={i:sorted((R/'frames'/str(i)).glob('*.jpg')) for i in range(1,7)}
clipmap=[1,2,3,4,5,1,6]
@functools.lru_cache(20)
def imgfile(path):return Image.open(path).convert('RGB')
def background(layer,t):
 i=layer['i'];u=max(0,min(1,(t-CUTS[i])/(CUTS[i+1]-CUTS[i])))
 if i<7:
  fs=FILES[clipmap[i]];im=imgfile(str(fs[min(len(fs)-1,int(u*(len(fs)-1)))]))
 else:im=imgfile(str(R.parent/'fullinput/assets'/('regensburg.jpg' if i==7 else 'alley.jpg')))
 zoom=layer['zoom'];scale=max(W/im.width,H/im.height)*zoom;ww,hh=round(im.width*scale),round(im.height*scale)
 im=im.resize((ww,hh),Image.Resampling.BICUBIC);x=(ww-W)//2+round(layer['x']);y=(hh-H)//2+round(layer['y']);return im.crop((x,y,x+W,y+H))

yy=np.linspace(0,1,H)[:,None];dark=(.08+.45*np.exp(-((yy-.12)/.22)**2)+.52*np.clip((yy-.56)/.44,0,1));shade=np.zeros((H,W,4),np.uint8);shade[:,:,:3]=(9,19,32);shade[:,:,3]=(np.repeat(np.minimum(dark,.74),W,axis=1)*255).astype('uint8');SHADE=Image.fromarray(shade)
y,x=np.mgrid[0:H,0:W];a=np.exp(-(((x-W*.24)/(W*.75))**2+((y-H*.42)/(H*.7))**2));glow=np.zeros((H,W,4),np.uint8);glow[:,:,:3]=(255,206,113);glow[:,:,3]=(a*255).astype(np.uint8);GLOW=Image.fromarray(glow)
def text(canvas,txt,pos,size=40,color=WHITE,bold=False,alpha=1,align='left',stroke=0):
 if alpha<=.001:return
 f=font(size,bold);d=ImageDraw.Draw(canvas);d.text(pos,txt,font=f,fill=(*color,round(255*min(1,alpha))),anchor='ma' if align=='center' else 'la',stroke_width=stroke,stroke_fill=(9,16,25,round(255*min(1,alpha))))
def wrap(txt,size,maxw,bold=True):
 words=txt.split();rows=[''];f=font(size,bold)
 for word in words:
  proposed=(rows[-1]+' '+word).strip()
  if f.getlength(proposed)>maxw and rows[-1]:rows.append(word)
  else:rows[-1]=proposed
 return rows
titles=[('31 декабря.\nВы в Баварии.',''),('Новый год\nв Регенсбурге',''),('Мюнхен · Аугсбург\nНюрнберг',''),('Мюнхен · Аугсбург\nНюрнберг',''),('Обераммергау\nМонастырь Этталь',''),('Перелет + 6 ночей\nс завтраками',''),('Нойшванштайн\nи Линдерхоф','Дополнительная поездка')]
readability=[]
def compose(state):
 t=state['t'];i=state['i'];im=None
 for layer in state['layers']:
  nxt=background(layer,t);im=nxt if im is None else Image.blend(im,nxt,layer['opacity'])
 im=im.convert('RGBA');im.alpha_composite(SHADE)
 if state['glow']>.001:
  g=GLOW.copy();g.putalpha(GLOW.getchannel('A').point(lambda a:round(a*state['glow'])));im.alpha_composite(g)
 ui=Image.new('RGBA',(W,H));d=ImageDraw.Draw(ui)
 text(ui,'SIMBA BY BON TOURS',(48,78),16,GOLD,True)
 d.line((48,114,134,114),fill=(*GOLD,255),width=2)
 if i<7:
  m=state['title'];ys=172+m['y'];title,note=titles[i]
  for line in title.split('\n'):text(ui,line,(48,ys),45,WHITE,True,m['opacity'],stroke=1);ys+=59
  if note:text(ui,note,(48,ys+18),24,WHITE,False,m['opacity'])
 elif i==7:
  ms=state['card']
  def put(k,txt,y,size,color=WHITE,bold=False):text(ui,txt,(48,y+ms[k]['y']),size,color,bold,ms[k]['opacity'],stroke=1)
  put(0,'НОВЫЙ ГОД В БАВАРИИ',164,23,GOLD,True)
  put(0,'28.12.2026–03.01.2027',210,27)
  put(1,'1399 €',290,105,WHITE,True)
  put(2,'С человека при',424,31)
  put(2,'двухместном размещении',467,31)
  put(3,'Вместо 1499 €',541,30)
  put(3,'Скидка 100 € с человека',590,27,GOLD,True)
  put(4,'6 ночей с завтраками',650,28)
  put(5,'WHATSAPP · «БАВАРИЯ»',1008,20,GOLD,True)
  put(5,'058-677-8492',1045,45,WHITE,True)
 else:
  ms=state['card']
  def put(k,txt,y,size,color=WHITE,bold=False):text(ui,txt,(48,y+ms[k]['y']),size,color,bold,ms[k]['opacity'],stroke=1)
  put(0,'ПОЛНАЯ ПРОГРАММА В WHATSAPP',176,22,GOLD,True)
  put(1,'Напишите',254,55,WHITE,True)
  put(1,'«БАВАРИЯ»',328,62,WHITE,True)
  put(2,'058-677-8492',565,53,WHITE,True)
  put(3,'28.12.2026–03.01.2027',649,29)
 # No opaque caption slabs; keep narration in a separate safe region.
 L=next((v for v in subs if v['a']<=t<v['b']),None)
 if L:
  toks=L['tokens'];size=36
  while font(size,True).getlength(' '.join(toks))>624:size-=1
  f=font(size,True);xx=(W-f.getlength(' '.join(toks)))/2;active=max([k for k,a in enumerate(L['starts']) if a<=t] or [0])
  for k,tok in enumerate(toks):
   text(ui,tok,(xx,884),size,GOLD if k==active else WHITE,True,stroke=2);xx+=f.getlength(tok+' ')
 im.alpha_composite(ui)
 # Keep the closing contact visible to the final frame.
 return im.convert('RGB')

def main():
 frames=M['frames'];out=R/'picture.mp4';log=open(R/'encode.log','w')
 p=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r','24','-i','-','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out)],stdin=subprocess.PIPE,stderr=log)
 for n,state in enumerate(frames):
  im=compose(state);p.stdin.write(im.tobytes())
  if n%96==0:print(f'Render {n}/{len(frames)}',flush=True)
  if n in [0,130,137,341,344,537,660,848,1008,1014,1025,1040,1060,1100,1181,1195,1220,1250,1300]:im.save(R/f'check_{n:04}.jpg')
 p.stdin.close();assert p.wait()==0,(R/'encode.log').read_text()
 subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(out),'-i',str(R/'current/Bavaria_Google_A2E_review.mp4'),'-map','0:v','-map','1:a','-c','copy','-movflags','+faststart',str(R/'Bavaria_Google_A2E_review.mp4')],check=True)
 print('Completed Anime.js festive edit',flush=True)
if __name__=='__main__':main()
