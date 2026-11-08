from pathlib import Path
import sys,json,subprocess,math,importlib.util,functools
from PIL import Image,ImageDraw,ImageFilter

R=Path(__file__).resolve().parent;W,H=720,1280
OPTIONS=R.parent/'newyear-options'
if not (OPTIONS/'render.py').exists():OPTIONS=R.parent/'newyear_options'
spec=importlib.util.spec_from_file_location('ny_options',OPTIONS/'render.py');opt=importlib.util.module_from_spec(spec);spec.loader.exec_module(opt)
base=opt.base;M=json.loads((R/'motion.json').read_text());CUTS=M['cuts']
CREAM,GOLD,RED,NAVY=opt.CREAM,opt.GOLD,opt.RED,opt.NAVY
CMAP=[1,2,3,4,5,1,6]
TITLES=[['31 декабря.','Вы в Баварии.'],['Новый год','в Регенсбурге'],['Мюнхен · Аугсбург','Нюрнберг'],['Мюнхен · Аугсбург','Нюрнберг'],['Обераммергау','Монастырь Этталь'],['Перелет + 6 ночей','с завтраками'],['Нойшванштайн','и Линдерхоф']]
LABELS=[['РЕГЕНСБУРГ'],['НОВЫЙ ГОД В РЕГЕНСБУРГЕ'],['МЮНХЕН · АУГСБУРГ','НЮРНБЕРГ'],['МЮНХЕН · АУГСБУРГ','НЮРНБЕРГ'],['ОБЕРАММЕРГАУ','МОНАСТЫРЬ ЭТТАЛЬ'],['ПЕРЕЛЕТ + 6 НОЧЕЙ','С ЗАВТРАКАМИ'],['НОЙШВАНШТАЙН · ЛИНДЕРХОФ','ДОПОЛНИТЕЛЬНАЯ ПОЕЗДКА']]
def txt(*a,**k):return opt.txt(*a,**k)
def bg(i,t,z=1.025):
 if i<7:
  fs=base.FILES[CMAP[i]];u=max(0,min(1,(t-CUTS[i])/(CUTS[i+1]-CUTS[i])));im=opt.frame(CMAP[i],round(u*(len(fs)-1)))
 else:
  im=Image.open(R.parent/'fullinput/assets'/('regensburg.jpg' if i==7 else 'alley.jpg')).convert('RGB')
 im=opt.cover(im,W,H);ww,hh=round(W*z),round(H*z);im=im.resize((ww,hh),Image.Resampling.BICUBIC);return im.crop(((ww-W)//2,(hh-H)//2,(ww+W)//2,(hh+H)//2)).convert('RGBA')
def decorated_bg(s):
 t=s['t'];i=s['i'];im=opt.dim(bg(i,t,s['move']['z']),65)
 if i and s['local']<.42:
  old=opt.dim(bg(i-1,CUTS[i]-.02,1.05),65);p=min(1,s['local']/.42);im=Image.blend(old,im,p);opt.flash(im,.38*math.sin(p*math.pi))
 opt.garland(im,t);opt.snowfall(im,t,.8);return im
def reveal_text(im,s,k,text,x,y,size,color=CREAM,bold=False,center=True,serif=False):
 m=s['reveal'][k];layer=Image.new('RGBA',im.size);txt(layer,text,x,y+m['y'],size,color,bold,center,serif,a=round(m['a']*255),stroke=1);im.alpha_composite(layer)

def full1(s):
 t=s['t'];i=s['i']
 if t<CUTS[2]:
  # Preserve the selected opening design, then continue it across the full scene list.
  st=dict(opt.M['states'][min(len(opt.M['states'])-1,round(t*24))]);st['t']=t;return opt.option1(st)
 im=decorated_bg(s)
 if i<7:
  m=s['title'];txt(im,'НОВОГОДНЯЯ БАВАРИЯ',W/2,228,23,GOLD,True,True,stroke=1)
  for k,line in enumerate(TITLES[i]):txt(im,line,W/2,385+k*74+m['y'],45,CREAM,True,True,serif=True,a=round(m['a']*255),stroke=2)
  if i==6:txt(im,'Дополнительная поездка',W/2,580,27,CREAM,False,True,stroke=1)
 elif i==7:
  plate=Image.new('RGBA',(W,H));d=ImageDraw.Draw(plate);d.rounded_rectangle((46,218,674,923),radius=20,fill=(*RED,237),outline=(*GOLD,255),width=2);im.alpha_composite(plate)
  reveal_text(im,s,0,'НОВЫЙ ГОД В БАВАРИИ',W/2,259,28,GOLD,True)
  reveal_text(im,s,0,'28.12.2026–03.01.2027',W/2,314,27)
  reveal_text(im,s,1,'1399 €',W/2,397,104,GOLD,True,serif=True)
  reveal_text(im,s,2,'Вместо 1499 €',W/2,548,31)
  reveal_text(im,s,2,'Скидка 100 € с человека',W/2,603,28,GOLD,True)
  reveal_text(im,s,3,'С человека при',W/2,683,31)
  reveal_text(im,s,3,'двухместном размещении',W/2,728,29)
  reveal_text(im,s,4,'6 ночей с завтраками',W/2,820,28)
 else:
  plate=Image.new('RGBA',(W,H));d=ImageDraw.Draw(plate);d.rounded_rectangle((42,280,678,900),radius=20,fill=(*NAVY,222),outline=(*GOLD,255),width=2);im.alpha_composite(plate)
  reveal_text(im,s,0,'2027',W/2,313,66,GOLD,True,serif=True)
  reveal_text(im,s,1,'Напишите в WhatsApp',W/2,438,35,CREAM,True)
  reveal_text(im,s,1,'«БАВАРИЯ»',W/2,501,61,GOLD,True)
  reveal_text(im,s,2,'058-677-8492',W/2,627,59,CREAM,True)
  reveal_text(im,s,3,'Пришлю полную программу',W/2,738,29)
  reveal_text(im,s,3,'28.12.2026–03.01.2027',W/2,815,25)
 opt.caption(im,t,990);opt.brand(im);return im

def body_card(i,t):
 card=Image.new('RGBA',(552,640),(*CREAM,255));pic=opt.cover(bg(i,t),516,514);card.alpha_composite(pic,(18,18))
 for k,line in enumerate(LABELS[i]):txt(card,line,276,550+k*33,23,RED,True,True,serif=True)
 return card
def offer_card(s):
 card=Image.new('RGBA',(552,640),(*CREAM,255));d=ImageDraw.Draw(card);d.rectangle((14,14,537,625),outline=(*RED,255),width=2)
 def put(k,ss,y,n,c=RED,b=False,ser=False):
  m=s['reveal'][k];layer=Image.new('RGBA',card.size);txt(layer,ss,276,y+m['y'],n,c,b,True,serif=ser,a=round(m['a']*255));card.alpha_composite(layer)
 put(0,'НОВЫЙ ГОД В БАВАРИИ',44,24,RED,True)
 put(1,'1399 €',125,91,RED,True,True)
 put(2,'Вместо 1499 €',264,30)
 put(2,'Скидка 100 € с человека',319,25,RED,True)
 put(3,'С человека при',405,30)
 put(3,'двухместном размещении',451,28)
 put(4,'6 ночей с завтраками',547,27)
 return card
def end_card(s):
 card=Image.new('RGBA',(552,640),(*CREAM,255));d=ImageDraw.Draw(card);d.rectangle((14,14,537,625),outline=(*RED,255),width=2)
 def put(k,ss,y,n,c=RED,b=False,ser=False):
  m=s['reveal'][k];layer=Image.new('RGBA',card.size);txt(layer,ss,276,y+m['y'],n,c,b,True,serif=ser,a=round(m['a']*255));card.alpha_composite(layer)
 put(0,'Напишите в WhatsApp',62,29)
 put(1,'«БАВАРИЯ»',138,53,RED,True,True)
 put(2,'058-677-8492',271,48,RED,True)
 put(3,'Пришлю полную',403,30)
 put(3,'программу',449,30)
 put(4,'Simba by Bon Tours',556,23,RED,True)
 return card
def anycard(i,t,s):return body_card(i,t) if i<7 else offer_card(s) if i==7 else end_card(s)
def full2(s):
 t=s['t'];i=s['i'];im=Image.new('RGBA',(W,H),(*RED,255));d=ImageDraw.Draw(im)
 for k in range(6):d.arc((-120-k*30,280+k*110,840+k*30,880+k*100),0,150,fill=(184,124,68,80),width=2)
 opt.garland(im,t);txt(im,'Новогодняя',W/2,115,51,CREAM,True,True,True);txt(im,'Бавария',W/2,179,62,CREAM,True,True,True);txt(im,'28.12.2026–03.01.2027',W/2,265,24,GOLD,False,True)
 if i and s['local']<1.1:
  m=s['outgoing'];prev={**s,'reveal':[{'a':1,'y':0} for _ in range(6)]};opt.placecard(im,anycard(i-1,CUTS[i]-.02,prev),80+m['x'],310,m['r'],m['a'])
 m=s['incoming'];opt.placecard(im,anycard(i,t,s),80+m['x'],310+m['y'],m['r'] if i%2==0 else -m['r'],m['a'])
 opt.snowfall(im,t,.35);opt.caption(im,t,1030);txt(im,'SIMBA BY BON TOURS',W/2,1195,17,GOLD,True,True);return im

def main(v,start=0):
 name='Countdown' if v==1 else 'Postcards';pic=R/(f'tail_{v}.mp4' if start else f'picture_{v}.mp4');out=R/f'Bavaria_NewYear_{name}.mp4';log=open(R/f'encode_{v}.log','w')
 p=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r','24','-i','-','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','19','-pix_fmt','yuv420p',str(pic)],stdin=subprocess.PIPE,stderr=log)
 for n,s in list(enumerate(M['frames']))[start:]:
  im=(full1(s) if v==1 else full2(s)).convert('RGB');p.stdin.write(im.tobytes())
  if n%192==0:print(f'Variant {v}: {n}/1311',flush=True)
  if n in [64,150,342,475,550,678,866,1010,1025,1050,1090,1140,1180,1198,1220,1250,1305]:im.save(R/f'v{v}_{n:04}.jpg')
 p.stdin.close();assert p.wait()==0,(R/f'encode_{v}.log').read_text()
 if start:return
 subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(pic),'-i',str(opt.BASE/'current/Bavaria_Google_A2E_review.mp4'),'-map','0:v','-map','1:a','-c','copy','-movflags','+faststart',str(out)],check=True)
 print(f'Full variant {v} complete',flush=True)
if __name__=='__main__':main(int(sys.argv[1]))
