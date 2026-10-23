# Apply the middle-steel rule to an existing section sheet (user 2026-10-21): per section the face-column dots between the second-highest and the lowest dot are replaced by equal steps <= s (dxflib.mid_steel from B x H; Hs list = overall heights, edit per file); arrays holding old dots are exploded, notes 2$8@20 -> 2$d@s, leader fork ends moved to the new dots. THEN run bar_arrays.py (PowerShell) and leader_fit.py. Dry first; snapshot .bak-mid-*. Sections are translated vertically, so only relative y is used.
import ezdxf,sys,shutil,datetime
from collections import defaultdict
sys.path.insert(0,r"C:\Users\USER082024\.claude\skills\dxf-drafting\scripts"); import dxflib
f=r"C:\Users\USER082024\Desktop\AI\חומר לימוד\חתכים\brenda_karka.dxf"; dry='--dry' in sys.argv
doc=ezdxf.readfile(f); msp=doc.modelspace(); YB=180196.8; COL_MIN=8.0
seps=sorted([e.dxf.start.x for e in msp.query('LINE') if e.dxf.layer=='72_MISGERET_WIN' and abs(e.dxf.start.x-e.dxf.end.x)<1e-6])
out=[e for e in msp.query('LWPOLYLINE') if e.dxf.layer=='72_MISGERET_WIN'][0]
edges=[-81359.28]+seps+[max(p[0] for p in out.get_points('xy'))]
def dots(e):
    if e.dxftype()=='LWPOLYLINE' and len(e)==2 and 0.5<=e.dxf.get('const_width',0)<=3:
        p=[(a,b) for a,b,*_ in e.get_points()]; return [((p[0][0]+p[1][0])/2,p[0][1],e.dxf.const_width,e.dxf.layer)]
    if e.dxftype()=='INSERT' and e.dxf.layer=='57_HATAH_ZIUN':
        r=[]
        for v in e.virtual_entities(): r+=dots(v)
        return r
    return []
objs=[(e,dots(e)) for e in msp if e.dxf.layer=='57_HATAH_ZIUN' and e.dxftype() in('LWPOLYLINE','INSERT')]
objs=[(e,d) for e,d in objs if d]
zet=[e for e in msp.query('LINE') if e.dxf.layer=='56_HATAH_ZET']
texts=[e for e in msp.query('TEXT') if e.dxf.layer=='54_HATAH_TEXT' and dxflib.decode(e.dxf.text).strip() in('2$8@20',)]
Hs=[115,115,115,115,120,95,95,40,75]       # overall beam heights from the section dims
plan=[]; moves=[]; textnew={}
import math
for k in range(9):
    a,b=edges[k],edges[k+1]
    vs=[v for v in msp.query('LINE') if v.dxf.layer=='9_KONTUR' and abs(v.dxf.start.x-v.dxf.end.x)<1e-6 and abs(v.dxf.start.y-v.dxf.end.y)>8 and a<v.dxf.start.x<b]
    Lf=min(v.dxf.start.x for v in vs); Rf=max(v.dxf.start.x for v in vs); W=Rf-Lf; H=Hs[k]
    d_,s_,note=dxflib.mid_steel(W,H); textnew[k]=(a,b,note); print('section',k+1,'W',round(W),'H',H,'area',round(W*H),'->',note)
    for side,cx in (('L',Lf+4.4),('R',Rf-4.35)):
        col=[(y,e,w,ly) for e,ds in objs for x,y,w,ly in ds if abs(x-cx)<0.4 and a<x<b and 180150<y<180420]
        col.sort(key=lambda t:t[0]); ys=[c[0] for c in col]
        if len(ys)<3: print('  ',side,'too few dots',len(ys)); continue
        y2,bot=ys[-2],ys[0]; old=[y for y in ys[1:-2]]
        gap=y2-bot; n=max(1,math.ceil(gap/s_-1e-9)); new=[y2-gap*i/n for i in range(1,n)]
        print('  ',side,'old mids',[round(v-YB,1) for v in old],'new',[round(v-YB,1) for v in new],'gap',round(gap,1))
        plan.append((k,side,cx,old,new,col))
        for z in zet:
            for end in ('start','end'):
                p=getattr(z.dxf,end)
                if abs(p.x-cx)<0.6:
                    for i,o in enumerate(old):
                        if abs(p.y-o)<0.6 and new: moves.append((z,end,cx,new[min(i,len(new)-1)]))
print(len(moves),'fork endpoints to move')
if dry: sys.exit()
shutil.copy2(f,f+'.bak-mid-'+datetime.datetime.now().strftime('%H%M%S'))
touched=set()
for k,side,cx,old,new,col in plan:
    for y,e,w,ly in col:
        if any(abs(y-o)<1e-6 for o in old) and e.dxftype()=='INSERT': touched.add(e.dxf.handle)
byh={e.dxf.handle:(e,ds) for e,ds in objs}
for h in touched:                         # explode the arrays that hold old mid dots into loose dots
    e,ds=byh[h]
    for v in e.virtual_entities():
        for x,y,w,ly in dots(v):
            msp.add_lwpolyline([(x-w/2,y,0,0,1),(x+w/2,y,0,0,1)],format='xyseb',close=True,dxfattribs=dict(layer=ly,const_width=w))
    msp.delete_entity(e)
# now delete the loose old mid dots and add the new ones
loose=[(e,ds[0]) for e in msp.query('LWPOLYLINE') if e.dxf.layer=='57_HATAH_ZIUN' and len(e)==2 for ds in [dots(e)] if ds]
for k,side,cx,old,new,col in plan:
    for e,(x,y,w,ly) in loose:
        if abs(x-cx)<0.4 and any(abs(y-o)<1e-6 for o in old) and e.is_alive: msp.delete_entity(e)
    for y in new:
        msp.add_lwpolyline([(cx-0.625,y,0,0,1),(cx+0.625,y,0,0,1)],format='xyseb',close=True,dxfattribs=dict(layer='57_HATAH_ZIUN',const_width=1.25))
for z,end,cx,y in moves:
    p=getattr(z.dxf,end); setattr(z.dxf,end,(p.x,y,p.z))
for t in texts:
    for k,(a,b,note) in textnew.items():
        if a<t.dxf.insert.x<b: t.dxf.text=note; print('note',k+1,'->',note)
doc.saveas(f); print('written')
