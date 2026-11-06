#!/usr/bin/env python3
"""Densify only Chapter 2 with approved v7 cutouts and seed33 Kontext v8 assets.

No Swift/API changes. Safe to rerun: removes only additions recorded by the previous
manifest, preserves pre-existing props, real PNG dimensions, and other chapters.
Generation is separate: /workspace/walking-sim/env_ch2/v8_dense/generate.py.
"""
from pathlib import Path
import json, copy, hashlib
from collections import Counter
import numpy as np
from PIL import Image, ImageEnhance, ImageDraw, ImageFilter
ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'Postman/GameAssets'
D=Path('/workspace/walking-sim/env_ch2/v8_dense')
C=A/'Chapter2'
MANIFEST=ROOT/'tools/ch2_dense_manifest.json'

def trimmed(path):
    im=Image.open(path).convert('RGBA')
    b=im.getchannel('A').point(lambda x:255 if x>8 else 0).getbbox()
    if not b: raise ValueError(f'Empty alpha: {path}')
    return im.crop(b)


def export_assets():
    exports=[]
    imported={'hut':'places/el_gar_posthut','hut_b':'places/el_penki_posthut',
              'bicycle':'places/el_bicycle','bicycle_b':'places/el_bicycle_b',
              'buried_horn':'places/el_buried_horn','pole':'places/el_pole',
              'ridge_mid_C':'road/mid_ridge_C'}
    generated={
        'road_main_fir':'road/road_main_fir','road_main_stone':'road/road_main_stone',
        'road_main_alder':'road/road_main_alder','prop_cap_stump':'road/prop_cap_stump',
        'prop_logs_saw':'road/prop_logs_saw','prop_snow_pole':'road/prop_snow_pole',
        'prop_cordon_well':'places/el_gar_well','prop_blank_sign':'road/prop_blank_sign',
        'fg_fir_paw':'foreground/fg_fir_paw','fg_fern_needles':'foreground/fg_fern_needles',
        'fg_boulder':'foreground/fg_boulder','fg_reeds':'foreground/fg_reeds',
        'place_krivulya_main':'places/place_krivulya_main','mid_hill_firs':'road/mid_hill_firs',
        'place_gar_cordon':'places/place_gar_main','place_penki_stumps':'places/place_penki_main',
        'ug_mail_sack':'underground/detail_mail_sack','ug_cable_splice':'underground/detail_cable_splice',
    }
    for group,mapping,source in [('v7',imported,D.parent/'v7/cut'),('v8',generated,D/'cut')]:
        for name,dest in mapping.items():
            im=trimmed(source/(name+'.png'))
            if name.startswith('road_main_'):
                # Remove isolated endcaps, retain the actual low stage silhouette.
                inset=round(im.width*.035)
                im=im.crop((inset,0,im.width-inset,im.height))
                h={'road_main_fir':760,'road_main_stone':650,'road_main_alder':680}[name]
                im=im.resize((2400,h),Image.Resampling.LANCZOS)
                # 60 px overlap at 2000 steps; only 24 px feathered at each seam.
                ar=np.array(im); fade=np.minimum(1,np.minimum(np.arange(2400)/24,(2399-np.arange(2400))/24))
                ar[:,:,3]=np.rint(ar[:,:,3]*fade[None,:]).astype('uint8');im=Image.fromarray(ar)
            if name=='fg_fir_paw':
                # Remove the thin hanging cord the model added above the actual bough.
                a=np.asarray(im.getchannel('A'))
                rows=np.flatnonzero((a>32).sum(axis=1)>im.width*.09)
                if len(rows): im=im.crop((0,max(0,int(rows[0])-3),im.width,im.height))
            path=C/(dest+'.png');path.parent.mkdir(parents=True,exist_ok=True)
            im.save(path,optimize=True)
            (D/'export'/path.parent.name).mkdir(exist_ok=True,parents=True)
            im.save(D/'export'/path.parent.name/path.name,optimize=True)
            exports.append({'image':dest,'source':str(source/(name+'.png')),'pixelSize':list(im.size),'group':group})
    # Three new soil modules use the exact same neutral profile/edges, not stretched terrain.
    neutral=Image.open(C/'underground/ug_neutral_tile.png').convert('RGBA')
    roots=trimmed(D.parent/'v5/cut/roots.png')
    sack=trimmed(C/'underground/detail_mail_sack.png')
    cable=trimmed(C/'underground/detail_cable_splice.png')
    rock=trimmed(C/'foreground/fg_boulder.png')
    def stamp(dst,im,xy,size,opacity=1):
        im=im.resize(size,Image.Resampling.LANCZOS)
        if opacity<1: im.putalpha(im.getchannel('A').point(lambda a:round(a*opacity)))
        dst.alpha_composite(im,xy)
    for name in ['gar','penki','krivulya','repka']:
        im=neutral.copy()
        if name=='gar':
            stamp(im,roots,(285,3),(104,305),.8)
            stamp(im,sack,(505,145),(155,188),.90)
            stamp(im,cable,(385,90),(470,100),.82)
        elif name=='penki':
            stamp(im,roots,(400,0),(108,330),.9)
            stamp(im,roots,(620,8),(86,259),.77)
            stamp(im,cable,(365,183),(470,100),.85)
        elif name=='repka':
            # Existing inherited module contained skulls rejected in the canon.
            # Replace only this Chapter2 module with the relay cable/grounding line.
            stamp(im,roots,(760,0),(83,250),.75)
            stamp(im,cable,(320,115),(620,132),.9)
        else:
            stamp(im,rock,(425,105),(154,178),.65)
            stamp(im,cable,(330,90),(520,111),.85)
        path=C/'underground'/('ug_'+name+'.png');im.convert('RGB').save(path,optimize=True)
        (D/'export/underground').mkdir(parents=True,exist_ok=True)
        im.convert('RGB').save(D/'export/underground'/path.name,optimize=True)
        exports.append({'image':'underground/ug_'+name,'pixelSize':list(im.size),'group':'composite'})
    return exports


def main():
    D.mkdir(exist_ok=True); (D/'export').mkdir(exist_ok=True)
    exports=export_assets()
    world_path=A/'Data/world.json';world=json.loads(world_path.read_text())
    untouched=copy.deepcopy(world);chapter=world['chapters'][1]
    before=len(chapter['props']); old=json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    retained=[p for p in chapter['props'] if p not in old.get('addedProps',[])]
    added=[]
    def prop(image,step,height,dx=0,layer='main',sink=40,z=-5):
        size=list(Image.open(C/(image+'.png')).size)
        p=dict(image=image,layer=layer,step=step,dx=round(dx,1),height=height,sink=sink,z=z,pixelSize=size)
        added.append(p)
    # Distinct canonical destinations: guardhouse + well / stump dwellings + timber / rock pinch.
    prop('places/place_gar_main',2800,1150,-880,z=12)
    prop('places/el_gar_well',2800,410,420,z=13)
    prop('places/el_tea_table',2800,150,-350,z=14)
    prop('places/el_gar_posthut',3400,730,180,z=15)
    prop('places/place_penki_main',6500,1200,-1000,z=16)
    prop('road/prop_logs_saw',6500,290,250,z=17)
    prop('places/el_bicycle_b',6500,220,-100,z=18)
    prop('places/el_penki_posthut',7200,790,180,z=19)
    prop('places/place_krivulya_main',16500,1350,-650,z=20)
    prop('road/prop_blank_sign',16500,430,330,z=21)
    prop('places/el_pole',16500,780,550,z=22)
    # Low main layer road scenery: never repeated as far or mid terrain.
    for i,step in enumerate(range(0,25001,2000)):
        kind='fir' if step<3600 or 12500<=step<16500 else 'stone' if step<21000 else 'alder'
        img='road/road_main_'+kind
        h=Image.open(C/(img+'.png')).height
        prop(img,step,h,-1200,z=round(-30+i*.001,3))
    roadside=[
      ('road/prop_blank_sign',850,430,180),
      ('road/prop_cap_stump',1600,550,-310),
      ('places/el_pole',2450,820,190),
      ('road/prop_blank_sign',3700,410,-180),
      ('places/el_pole',4650,830,120),
      ('road/prop_logs_saw',5600,240,-250),
      ('road/prop_logs_saw',7700,270,100),
      ('road/prop_snow_pole',8650,720,-160),
      ('road/prop_blank_sign',9550,460,200),
      ('road/prop_snow_pole',10400,800,160),
      ('road/prop_snow_pole',11900,740,-90),
      ('road/prop_snow_pole',12800,620,160),
      ('places/el_pole',13800,850,-150),
      ('places/el_bicycle',14800,220,180),
      ('places/el_buried_horn',17700,210,-240),
      ('road/prop_snow_pole',18700,680,200),
      ('road/prop_blank_sign',19900,440,-120),
      ('places/el_pole',21300,740,170),
      ('road/prop_blank_sign',22500,420,-160),
      ('places/el_buried_horn',23600,195,160),
      ('road/prop_snow_pole',24750,640,-170),
    ]
    for image,step,h,dx in roadside: prop(image,step,h,dx,z=-4)
    for i,(step,h) in enumerate([(500,270),(3800,260),(7200,290),(10600,320),(14000,280),(17600,270),(21100,235),(24100,210)]):
        img='road/mid_ridge_C' if i%2 else 'road/mid_hill_firs'
        size=Image.open(C/(img+'.png')).size; width=h*size[0]/size[1]
        prop(img,step,h,-width*.5,layer='mid',sink=-300,z=i+1)
    for i,step in enumerate(range(350,25000,900)):
        if step<3600 or 12500<=step<15800:
            kind='fir_paw' if i%2==0 else 'fern_needles'
        elif step<12500 or step<21000:
            kind='boulder' if i%3!=1 else 'fern_needles'
        else:
            kind='reeds' if i%3!=1 else 'fern_needles'
        heights={'fir_paw':1350 if i%4 else 1500,'fern_needles':460+(i%3)*35,
                 'boulder':590+(i%3)*70,'reeds':1120 if i%2 else 980}
        h=heights[kind]
        width=h*Image.open(C/('foreground/fg_'+kind+'.png')).width/Image.open(C/('foreground/fg_'+kind+'.png')).height
        dx=-width-170 if i%2==0 else 340
        if i==0: dx-=700  # opening bough frames the left edge instead of hiding the hero
        prop('foreground/fg_'+kind,step,h,dx,layer='foreground',sink=900 if h>900 else 850,z=1)
    chapter['props']=retained+added
    mods=chapter['underground']['modules']
    for name,step in [('gar',2800),('penki',6500),('krivulya',16500)]:
        image='underground/ug_'+name
        mods[:]=[m for m in mods if m['image']!=image]
        mods.append(dict(image=image,step=step,dx=0.0))
    mods.sort(key=lambda m:m['step'])
    # Verify the contract before replacing any data.
    assert world['chapters'][0]==untouched['chapters'][0]
    assert {k:v for k,v in chapter.items() if k not in ['props','underground']}=={k:v for k,v in untouched['chapters'][1].items() if k not in ['props','underground']}
    for p in chapter['props']:
        assert p['pixelSize']==list(Image.open(C/(p['image']+'.png')).size),(p['image'],p['pixelSize'])
    assert len(chapter['props'])>=55
    temp=world_path.with_suffix('.dense.tmp');temp.write_text(json.dumps(world,ensure_ascii=False,indent=2)+'\n');temp.replace(world_path)
    ambient_path=A/'Data/ambient.json'; ambient=json.loads(ambient_path.read_text())
    for match,amp,period in [('foreground/fg_fir_paw',1.1,[3.8,5.2]),('places/el_pole',.35,[4.2,5.6]),('road/prop_snow_pole',.3,[3.6,4.8]),('road/prop_blank_sign',.35,[4.0,5.4])]:
        if not any(x['match']==match for x in ambient['sway']): ambient['sway'].append(dict(match=match,amp=amp,period=period))
    # The generated chimney top is measured on the alpha-trimmed 745x629 guardhouse.
    if not any(x['prop']=='places/place_gar_main' for x in ambient['smoke']):
        ambient['smoke'].append(dict(prop='places/place_gar_main',at=[515,20],scale=.65,interval=1.3,wind=1))
    ambient_path.write_text(json.dumps(ambient,ensure_ascii=False,indent=2)+'\n')
    summary=dict(before=before,baseProps=len(retained),after=len(chapter['props']),added=len(added),byLayer=dict(Counter(p['layer'] for p in chapter['props'])),exports=exports,addedProps=added,undergroundModules=len(mods),chapter1Unchanged=True)
    MANIFEST.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (D/'report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['exports','addedProps']},ensure_ascii=False,indent=2))
    print('Exported',len(exports),'assets')

if __name__=='__main__': main()
