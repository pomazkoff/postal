# Cut-out walk rig for the last postman. Parts from cut_parts.py, pivots in rig.json (source-pixel coords of side_seed33).
import numpy as np,cv2,json,random,os
from PIL import Image,ImageDraw,ImageFont
R=json.load(open("rig.json"));OFF=R["offsets"];PV=R["pivots_src"]
W,H=1000,1250;PAD=(60,40)
def layer(name,dark=1.0):
  im=np.array(Image.open(f"parts/{name}.png").convert("RGBA")).astype(np.float32)
  im[:,:,:3]*=dark;L=np.zeros((H,W,4),np.float32);x,y=OFF[name];x+=PAD[0];y+=PAD[1]
  L[y:y+im.shape[0],x:x+im.shape[1]]=im;return L
def p(n): return np.array([PV[n][0]+PAD[0],PV[n][1]+PAD[1]],float)
def T(dx,dy): return np.array([[1,0,dx],[0,1,dy],[0,0,1]],float)
def Rot(deg,c):
  a=np.radians(deg);cs,sn=np.cos(a),np.sin(a);return T(*c)@np.array([[cs,-sn,0],[sn,cs,0],[0,0,1]])@T(*-c)
def ap(M,pt): return (M@[pt[0],pt[1],1])[:2]
def comp(C,L,M):
  w=cv2.warpAffine(L,M[:2],(W,H),flags=cv2.INTER_LINEAR,borderValue=(0,0,0,0))
  a=w[:,:,3:4]/255;C[:,:,:3]=w[:,:,:3]*a+C[:,:,:3]*(1-a);C[:,:,3:4]=np.maximum(C[:,:,3:4],w[:,:,3:4])
PARTS=["head","torso","arm_upper","arm_lower","thigh","shin","foot","staff"]
LY={n:layer(n) for n in PARTS};DK={n:layer(n,0.62) for n in ["arm_upper","arm_lower","thigh","shin","foot"]}
# per-leg keys over 8 frames (+deg = swing forward): own contact,down,passing,up, then the other leg's phases
THIGH=[19,14,2,-12,-19,-22,6,20]; KNEE=[4,40,8,2,10,46,58,26]
SUPPORT=[1,1,1,1,0,0,0,0]
NAMES=["01_contact_R","02_down_R","03_passing_R","04_up_R","05_contact_L","06_down_L","07_passing_L","08_up_L"]
STAFF_TIP_X=[40,25,10,-5,-20,-35,0,30]; STAFF_LIFT=[0,0,0,0,0,0,-30,-12]
def leg(MB,f):
  k=f%8;Mt=MB@Rot(-THIGH[k],p("hip"));Ms=Mt@Rot(KNEE[k],p("knee"))
  sh=-THIGH[k]+KNEE[k];fa=-sh if SUPPORT[k] else -0.4*sh
  if k==0: fa-=8
  if k==3: fa+=10
  Mf=Ms@Rot(fa,p("ankle"))
  return Mt,Ms,Mf,max(ap(Mf,(x+PAD[0],1112+PAD[1]))[1] for x in (340,480))
ground=PV["ground_y"]+PAD[1]
dys=[ground-max(leg(np.eye(3),f)[3],leg(np.eye(3),f+4)[3]) for f in range(8)]
random.seed(4);frames=[];NECK=[]
for f in range(8):
  j=lambda:T(random.choice([-1,0,1]),random.choice([-1,0,1]))
  MB=T(0,dys[f]);C=np.zeros((H,W,4),np.float32);sw=-0.3*THIGH[f]
  Mt,Ms,Mf,_=leg(MB,f+4);comp(C,DK["shin"],Ms);comp(C,DK["foot"],Mf);comp(C,DK["thigh"],Mt)
  Ma=MB@Rot(-sw*0.8,p("shoulder"));comp(C,DK["arm_upper"],Ma);comp(C,DK["arm_lower"],Ma@Rot(-8,p("elbow")))
  Mt,Ms,Mf,_=leg(MB,f);comp(C,LY["shin"],Ms);comp(C,LY["foot"],Mf);comp(C,LY["thigh"],Mt)  # thigh over knee
  J=j()@MB                                   # torso+head share one transform/jitter
  comp(C,LY["torso"],J)                      # torso covers hip cut
  Mh=J@Rot(0.5*np.sin(f*np.pi/4),p("neck"))  # rigid head, max +-0.5 deg, no lag
  comp(C,LY["head"],Mh);NECK.append(ap(Mh,p("neck")))
  Mu=MB@Rot(-sw,p("shoulder"));Ml=Mu@Rot(-sw*0.2,p("elbow"))
  grip=ap(Ml,(500+PAD[0],675+PAD[1]));tip=np.array([p("staff_tip")[0]+STAFF_TIP_X[f]-10,ground+STAFF_LIFT[f]])
  g0,t0=p("staff_grip"),p("staff_tip");v0,v1=t0-g0,tip-grip
  ang=np.degrees(np.arctan2(v1[1],v1[0])-np.arctan2(v0[1],v0[0]))
  comp(C,LY["staff"],T(*(grip-g0))@Rot(ang,g0));comp(C,LY["arm_upper"],Mu);comp(C,LY["arm_lower"],Ml)
  frames.append(Image.fromarray(C.clip(0,255).astype(np.uint8)))
# neck check: background pixels enclosed by silhouette around the neck
for n,im,c in zip(NAMES,frames,NECK):
  a=(np.array(im)[:,:,3]>100).astype(np.uint8);x,y=int(c[0]),int(c[1])
  inv=(1-a[y-90:y+60,x-60:x+70]).copy();h,w=inv.shape;m=np.zeros((h+2,w+2),np.uint8)
  for sx in range(w):
    for sy in (0,h-1):
      if inv[sy,sx]: cv2.floodFill(inv,m,(sx,sy),0)
  for sy in range(h):
    for sx in (0,w-1):
      if inv[sy,sx]: cv2.floodFill(inv,m,(sx,sy),0)
  print(n,"enclosed bg px near neck:",int(inv.sum()))
print("body dy per frame (+ = lower):",[round(x) for x in dys])
bb=[min(i.getbbox()[k] for i in frames) if k<2 else max(i.getbbox()[k] for i in frames) for k in range(4)]
bb=(bb[0]-20,bb[1]-20,bb[2]+20,bb[3]+10)
fr=[i.crop(bb).resize(((bb[2]-bb[0])//2,(bb[3]-bb[1])//2),Image.LANCZOS) for i in frames]
os.makedirs("frames",exist_ok=True)
for n,i in zip(NAMES,fr): i.save(f"frames/{n}.png")
sp=Image.new("RGBA",(fr[0].width*8,fr[0].height))
for k,i in enumerate(fr): sp.alpha_composite(i,(k*i.width,0))
sp.save("spritesheet.png")
BG=(222,205,170);gy=int((ground-bb[1])/2)
def onbg(i):
  b=Image.new("RGB",i.size,BG);ImageDraw.Draw(b).line([(0,gy),(i.width,gy)],fill=(170,150,115),width=2);b.paste(i,(0,0),i);return b
g=[onbg(i) for i in fr];g[0].save("walk.gif",save_all=True,append_images=g[1:],duration=83,loop=0)
F=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
sh=Image.new("RGB",(g[0].width*8,g[0].height+24),"white");d=ImageDraw.Draw(sh)
for k,(n,i) in enumerate(zip(NAMES,g)): sh.paste(i,(k*i.width,0));d.text((k*i.width+4,i.height+4),n,fill="black",font=F)
sh.save("frames_sheet.jpg",quality=90)
