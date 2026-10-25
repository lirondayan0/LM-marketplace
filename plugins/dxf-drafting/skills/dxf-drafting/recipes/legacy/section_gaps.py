# Section spacing (user 2026-10-21): 100 cm clear gap between neighbouring sections measured on ALL their entities (dims, bars, notes); each frame = content width + 100 (50 each side, content centred), frames contiguous, last separator removed and the outer frame shortened. y untouched. Snapshot .bak-gap-*; --dry first. Constants = brenda_karka sheet.
import ezdxf,sys,shutil,datetime
from ezdxf import bbox
f=next((a for a in sys.argv[1:] if not a.startswith("--")), r"C:\Users\USER082024\Desktop\AI\חומר לימוד\חתכים\brenda_karka.dxf")
GAP=100.0; dry='--dry' in sys.argv
doc=ezdxf.readfile(f); msp=doc.modelspace()
X0=-81359.2809; Y0=179930.994; H=483.27
seps=sorted([e for e in msp.query('LINE') if e.dxf.layer=='72_MISGERET_WIN' and abs(e.dxf.start.x-e.dxf.end.x)<1e-6 and abs(abs(e.dxf.start.y-e.dxf.end.y)-H)<1],key=lambda e:e.dxf.start.x)
edges=[X0]+[e.dxf.start.x for e in seps]       # 10 edges incl. right ones; cells 1..9 = edges[k]..edges[k+1]
n=9; cells=[[] for _ in range(n)]
for e in msp:
    if e.dxf.layer in('72_MISGERET_WIN','claude'): continue
    try: b=bbox.extents([e])
    except Exception: continue
    if not b.has_data: continue
    cx=(b.extmin.x+b.extmax.x)/2; cy=(b.extmin.y+b.extmax.y)/2
    if Y0-60<cy<Y0+H+60:
        for k in range(n):
            if edges[k]<cx<edges[k+1]: cells[k].append((e,b))
info=[]; L=X0
for k,c in enumerate(cells):
    x0=min(b.extmin.x for e,b in c); x1=max(b.extmax.x for e,b in c); w=x1-x0
    dx=(L+GAP/2)-x0; info.append((c,dx,L,w)); print('cell',k+1,'content',round(w,1),'frame',round(w+GAP,1),'move',round(dx,1)); L+=w+GAP
print('total width',round(L-X0,1),'(old 4000)')
if dry: sys.exit()
shutil.copy2(f,f+'.bak-gap-'+datetime.datetime.now().strftime('%H%M%S'))
for c,dx,_,_ in info:
    for e,b in c: e.translate(dx,0,0)
newedges=[]; L=X0
for _,_,_,w in info: L+=w+GAP; newedges.append(L)
for e,x in zip(seps[:8],newedges[:8]): e.dxf.start=(x,e.dxf.start.y,0); e.dxf.end=(x,e.dxf.end.y,0)
msp.delete_entity(seps[8])
out=[e for e in msp.query('LWPOLYLINE') if e.dxf.layer=='72_MISGERET_WIN'][0]
pts=[list(p) for p in out.get_points('xyseb')]
mx=max(p[0] for p in pts)
for p in pts:
    if abs(p[0]-mx)<1: p[0]=newedges[-1]
out.set_points(pts,format='xyseb'); doc.saveas(f); print('written; right edge',round(newedges[-1],1))
