# Проверка порта рига: повторяет RigWalk.swift + раскладку в SKSpriteNode (anchor top-left, zRotation=-angle)
# и сравнивает с кадрами rig_walk.py. Запуск: скопировать parts/ и rig.json в папку, сохранить ref.pkl из
# изменённого rig_walk.py (см. README, раздел «Проверки»), затем python3 rig_port_check.py. Результат 2026-11-04: max diff 1/255 на всех 8 кадрах.
# Mirror of RigWalk.swift + PostmanRigNode decomposition, rendered back to image space.
import json, math, numpy as np, cv2, pickle
from PIL import Image
R=json.load(open("rig.json")); OFF=R["offsets"]; PV=R["pivots_src"]; G=PV["ground_y"]
W,H=1000,1250; PAD=(60,40)
class A:
    def __init__(s,a,b,c,d,e,f): s.a,s.b,s.c,s.d,s.e,s.f=a,b,c,d,e,f
    def __mul__(l,r): return A(l.a*r.a+l.b*r.d, l.a*r.b+l.b*r.e, l.a*r.c+l.b*r.f+l.c, l.d*r.a+l.e*r.d, l.d*r.b+l.e*r.e, l.d*r.c+l.e*r.f+l.f)
    def ap(s,p): return (s.a*p[0]+s.b*p[1]+s.c, s.d*p[0]+s.e*p[1]+s.f)
    def angle(s): return math.atan2(s.d,s.a)
I=A(1,0,0,0,1,0)
def T(x,y): return A(1,0,x,0,1,y)
def Rot(deg,p):
    r=math.radians(deg);cs,sn=math.cos(r),math.sin(r); return T(p[0],p[1])*A(cs,-sn,0,sn,cs,0)*T(-p[0],-p[1])
p=lambda n: PV[n]
THIGH=[19,14,2,-12,-19,-22,6,20]; KNEE=[4,40,8,2,10,46,58,26]; SUP=[1,1,1,1,0,0,0,0]
STX=[40,25,10,-5,-20,-35,0,30]; STL=[0,0,0,0,0,0,-30,-12]
JIT=[(-1,0),(-1,1),(0,0),(-1,-1),(-1,-1),(0,1),(0,-1),(-1,1)]
def leg(mb,f):
    k=f%8; mt=mb*Rot(-THIGH[k],p("hip")); ms=mt*Rot(KNEE[k],p("knee")); sh=-THIGH[k]+KNEE[k]
    fa=-sh if SUP[k] else -0.4*sh
    if k==0: fa-=8
    if k==3: fa+=10
    mf=ms*Rot(fa,p("ankle")); low=max(mf.ap((340,1112))[1],mf.ap((480,1112))[1]); return mt,ms,mf,low
dys=[G-max(leg(I,f)[3],leg(I,f+4)[3]) for f in range(8)]
ORDER=[("shin",1),("foot",1),("thigh",1),("arm_upper",1),("arm_lower",1),("shin",0),("foot",0),("thigh",0),("torso",0),("head",0),("staff",0),("arm_upper",0),("arm_lower",0)]
def pose(f):
    mb=T(0,dys[f]); sw=-0.3*THIGH[f]; out=[]
    mt,ms,mf,_=leg(mb,f+4); out+= [ms,mf,mt]
    ma=mb*Rot(-sw*0.8,p("shoulder")); out+=[ma, ma*Rot(-8,p("elbow"))]
    mt,ms,mf,_=leg(mb,f); out+=[ms,mf,mt]
    j=T(*JIT[f])*mb; out+=[j, j*Rot(0.5*math.sin(f*math.pi/4),p("neck"))]
    mu=mb*Rot(-sw,p("shoulder")); ml=mu*Rot(-sw*0.2,p("elbow"))
    grip=ml.ap((500,675)); tip=(p("staff_tip")[0]+STX[f]-10, G+STL[f]); g0,t0=p("staff_grip"),p("staff_tip")
    v0=(t0[0]-g0[0],t0[1]-g0[1]); v1=(tip[0]-grip[0],tip[1]-grip[1])
    ang=math.degrees(math.atan2(v1[1],v1[0])-math.atan2(v0[1],v0[0]))
    out+=[T(grip[0]-g0[0],grip[1]-g0[1])*Rot(ang,g0), mu, ml]
    return out
def comp(C,L,M):
    w=cv2.warpAffine(L,M,(W,H),flags=cv2.INTER_LINEAR,borderValue=(0,0,0,0))
    a=w[:,:,3:4]/255;C[:,:,:3]=w[:,:,:3]*a+C[:,:,:3]*(1-a);C[:,:,3:4]=np.maximum(C[:,:,3:4],w[:,:,3:4])
ref=pickle.load(open("ref.pkl","rb"))
for f in range(8):
    C=np.zeros((H,W,4),np.float32)
    for (name,dark),m in zip(ORDER,pose(f)):
        im=np.array(Image.open(f"parts/{name}.png").convert("RGBA")).astype(np.float32)
        if dark: im[:,:,:3]*=0.62
        # SpriteKit node: anchor top-left at P (y-up), zRotation = -angle
        tl=m.ap(OFF[name]); P=(tl[0],-tl[1]); z=-m.angle()
        # sprite pixel (u,v) -> local y-up (u,-v) -> rotate z -> + P -> y-down (x,-y) -> + PAD
        cz,sz=math.cos(z),math.sin(z)
        # x = cz*u - sz*(-v) + Px ; y_up = sz*u + cz*(-v) + Py ; y_down = -y_up
        M=np.array([[cz, sz, P[0]+PAD[0]],[-sz, cz, -P[1]+PAD[1]]],np.float32)
        comp(C,im,M)
    out=C.clip(0,255).astype(np.uint8)
    diff=np.abs(out.astype(int)-ref[f].astype(int))
    print(f, "max diff",diff.max(),"mean",round(diff.mean(),4))
    if f==2: Image.fromarray(out).save("port_f2.png"); Image.fromarray(ref[f]).save("ref_f2.png")
