# Centre every section in its white frame (user 2026-10-21): per cell the bbox of ALL its entities (outline, bars, dims, leaders, notes, detail row; not frames / claude) is translated to the frame centre (x and y); a section wider than the cell widens that cell (here cell 9 +60 by moving its right separator). ezdxf translate moves dimension blocks too; no associative arrays in this file (would need re-association). Snapshot .bak-center-*; --dry first. Constants = brenda_karka sheet.
import ezdxf,sys,shutil,datetime
from ezdxf import bbox
f=next((a for a in sys.argv[1:] if not a.startswith("--")), r"C:\Users\USER082024\Desktop\AI\חומר לימוד\חתכים\brenda_karka.dxf")
dry='--dry' in sys.argv
doc=ezdxf.readfile(f); msp=doc.modelspace()
X0=-81359.2809; Y0=179930.994; W=400; H=483.27; E9=60.0      # cell 9 widened by 60 (its section is 428 wide)
cells=[[] for _ in range(9)]
for e in msp:
    if e.dxf.layer in('72_MISGERET_WIN','claude'): continue
    try: b=bbox.extents([e])
    except Exception: continue
    if not b.has_data: continue
    cx=(b.extmin.x+b.extmax.x)/2; cy=(b.extmin.y+b.extmax.y)/2
    if Y0-60<cy<Y0+H+60 and X0<cx<X0+W*9: cells[int((cx-X0)//W)].append((e,b))
plan=[]
for k,c in enumerate(cells):
    x0=min(b.extmin.x for e,b in c); x1=max(b.extmax.x for e,b in c); y0=min(b.extmin.y for e,b in c); y1=max(b.extmax.y for e,b in c)
    a=X0+W*k; w=W+(E9 if k==8 else 0)
    dx=a+w/2-(x0+x1)/2; dy=Y0+H/2-(y0+y1)/2
    plan.append((c,dx,dy)); print('cell',k+1,'content w',round(x1-x0,1),'h',round(y1-y0,1),'move',round(dx,1),round(dy,1),'margins',round(w/2-(x1-x0)/2,1),round(H/2-(y1-y0)/2,1))
if dry: sys.exit()
shutil.copy2(f,f+'.bak-center-'+datetime.datetime.now().strftime('%H%M%S'))
for c,dx,dy in plan:
    for e,b in c: e.translate(dx,dy,0)
for e in msp.query('LINE'):
    if e.dxf.layer=='72_MISGERET_WIN' and abs(e.dxf.start.x-(X0+W*9))<1:
        e.dxf.start=(e.dxf.start.x+E9,e.dxf.start.y,0); e.dxf.end=(e.dxf.end.x+E9,e.dxf.end.y,0)
doc.saveas(f); print('written')
