#!/usr/bin/env python3
"""Pillow QA only: world.json coordinates/alpha/z/parallax, not a runtime screenshot."""
from pathlib import Path
import json,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageEnhance
ROOT=Path(__file__).resolve().parents[1];A=ROOT/'Postman/GameAssets'
D=Path('/workspace/walking-sim/env_ch2/v8_dense');C=A/'Chapter2'
w=json.loads((A/'Data/world.json').read_text());c=w['chapters'][1];g=w['game'];L=w['layers']
W,H=1170,2532;heroX=W*.55;pps=g['pixelsPerStep'];road=g['roadLineY']
fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
f=ImageFont.truetype(fontpath,32);fs=ImageFont.truetype(fontpath,24)
HAZE=np.array([153,161,173],dtype=np.float32)
def grade(im,haze=0,brightness=1):
 a=np.array(im.convert('RGBA'));rgb=a[:,:,:3].astype(np.float32)*brightness
 rgb=rgb*(1-haze)+HAZE*haze;a[:,:,:3]=np.clip(rgb,0,255).astype('uint8');return Image.fromarray(a)
def paste(canvas,im,x,y,width,height,alpha=1,haze=0,brightness=1):
 width=max(1,round(width));height=max(1,round(height));x=round(x);y=round(y)
 if x>=W or x+width<=0 or y>=H or y+height<=0:return
 im=grade(im,haze,brightness).resize((width,height),Image.Resampling.LANCZOS)
 if alpha<1:im.putalpha(im.getchannel('A').point(lambda v:round(v*alpha)))
 canvas.alpha_composite(im,(x,y))
def load(path):return Image.open(C/(path+'.png')).convert('RGBA')
def prop_layer(b,layer,step):
 k={'far':.1,'mid':.4,'main':1,'foreground':1.3}[layer]
 for p in sorted([x for x in c['props'] if x['layer']==layer],key=lambda p:p.get('z',0)):
  h=p['height'];pw=h*p['pixelSize'][0]/p['pixelSize'][1]
  x=heroX+(p['step']-step)*pps*k+p['dx'];y=road+p.get('sink',0)-h
  haze={'far':.34,'mid':.28}.get(layer,.2 if p['image'].startswith('places/') else 0)
  paste(b,load(p['image']),x,y,pw,h,alpha=.9 if layer=='foreground' else 1,haze=haze)
def render(step,title):
 top=np.array([20,80,95]);bot=np.array([60,120,115]);t=np.linspace(0,1,H)[:,None,None]
 sky=np.repeat(np.rint(top[None,None,:]*(1-t)+bot[None,None,:]*t).astype('uint8'),W,axis=1)
 b=Image.fromarray(sky).convert('RGBA')
 for layer in ['far','mid']:
  spec=L[layer];im=load(spec['image']);hh=spec['height'];ww=hh*im.width/im.height
  if layer=='far':
   a=np.array(im);fade=np.clip(np.arange(im.height)/(im.height*.22),0,1);a[:,:,3]=np.rint(a[:,:,3]*fade[:,None]).astype('uint8');im=Image.fromarray(a)
  shift=-(step*pps*spec['parallax'])%ww
  for i in range(-2,math.ceil(W/ww)+2):
   paste(b,im,shift+i*ww,spec['top'],ww,hh,haze=.34 if layer=='far' else .28,brightness=spec.get('brightness',1))
  prop_layer(b,layer,step)
 prop_layer(b,'main',step)
 ug=c['underground'];tw=ug['tilePixelSize'][0]*ug['scale'];th=ug['tilePixelSize'][1]*ug['scale']
 shift=-(step*pps)%tw
 for i in range(-2,math.ceil(W/tw)+2):paste(b,load(ug['neutralTile']),shift+i*tw,ug['top'],tw,th)
 # Exact packing rule from buildUnderground, relative to chapter start.
 cursor=None
 for m in sorted(ug['modules'],key=lambda m:m['step']*pps+m.get('dx',0)):
  left=m['step']*pps+m.get('dx',0)-tw/2
  if cursor is not None and left-cursor<tw*ug['minGapFraction']:left=cursor
  paste(b,load(m['image']),heroX+left-step*pps,ug['top'],tw,th);cursor=left+tw
 if ug['top']+th<H: ImageDraw.Draw(b).rectangle((0,ug['top']+th,W,H),fill='#2A1D16')
 # Transparent approved seed33 character; approximate idle footprint, no fake UI.
 hero=Image.open('/workspace/walking-sim/postman_fal/cutout/src/s33_cut.png').convert('RGBA')
 hero=hero.crop(hero.getchannel('A').getbbox());hh=430;hw=hh*hero.width/hero.height
 paste(b,hero,heroX-hw*.5,road+30-hh,hw,hh)
 prop_layer(b,'foreground',step)
 dr=ImageDraw.Draw(b);dr.rounded_rectangle((35,42,1135,140),radius=18,fill=(15,33,35,210))
 dr.text((62,64),f'Горы · {title} · {step:,} шагов'.replace(',',' '),font=f,fill='#EEE1BF')
 dr.text((40,2476),'Pillow QA · игровые ассеты и координаты world.json',font=fs,fill='#C6BCAE')
 return b.convert('RGB')

def main():
 out=C/'_preview';out.mkdir(exist_ok=True)
 names=[(0,'Седло'),(2800,'Гарь'),(11000,'Хомут'),(15500,'Репка')]
 thumbs=[]
 for step,title in names:
  im=render(step,title);im.save(D/f'phone_{step:05}.jpg',quality=90)
  thumbs.append(im.resize((390,844),Image.Resampling.LANCZOS))
 board=Image.new('RGB',(390*4+18*5,844+80),(25,35,36));dr=ImageDraw.Draw(board)
 dr.text((18,17),'Глава 2 · плотность ленты · QA, не скриншот приложения',font=ImageFont.truetype(fontpath,22),fill='#E9DEC4')
 for i,im in enumerate(thumbs):board.paste(im,(18+(390+18)*i,60))
 board.save(D/'preview_dense.jpg',quality=93);board.save(out/'preview_dense.jpg',quality=93)
 for step,title in [(6500,'Пеньки'),(16500,'Кривуля'),(24000,'Горловина')]:
  render(step,title).resize((585,1266),Image.Resampling.LANCZOS).save(D/f'phone_{step:05}.jpg',quality=91)
 print('Saved',D/'preview_dense.jpg','and',out/'preview_dense.jpg')
if __name__=='__main__':main()
