"""plan_reach_audit.py FILE [MAXREACH=100]  -  for every X/Y/rotated linear dim near claude_Kontur: perpendicular distance of its two measured points to its dimension line; reports how many exceed MAXREACH (user rule: 1 m = 100 cm) with handles + whether mine (xdata). Run after every round; ANY far dim of mine = fix by re-running the round (plan_rebuild_xlines.py), never by adding lines."""
import sys, os, math, collections
R_=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,R_); sys.path.insert(0,R_+'/../scripts')
import ezdxf, plan_xlines_lf as lf
doc=ezdxf.readfile(sys.argv[1]); ms=doc.modelspace(); bound,_=lf.plan_outline(ms)
bx=(min(q[0] for q in bound)-3000,min(q[1] for q in bound)-3000,max(q[0] for q in bound)+3000,max(q[1] for q in bound)+3000)
print('box',bx)
tot=0; far=[]; hist=collections.Counter()
for d in ms.query('DIMENSION'):
    if d.dimtype&7!=0: continue
    p2,p3,dp=d.dxf.defpoint2,d.dxf.defpoint3,d.dxf.defpoint
    if not (bx[0]<=p2.x<=bx[2] and bx[1]<=p2.y<=bx[3]): continue
    a=math.radians(d.dxf.get('angle',0) or 0); nx,ny=-math.sin(a),math.cos(a)
    ds=[abs((p.x-dp.x)*nx+(p.y-dp.y)*ny) for p in (p2,p3)]
    tot+=1; m=max(ds); hist[int(m//50)*50]+=1
    if m>float(sys.argv[2] if len(sys.argv)>2 else 100)+0.5: far.append((d.dxf.handle,round(m),d.has_xdata('CLAUDE_ROWS'),d.dxf.dimstyle))
print('dims near plan',tot,'far (>100)',len(far)); print(sorted(hist.items())[:12]); print(far[:10])
