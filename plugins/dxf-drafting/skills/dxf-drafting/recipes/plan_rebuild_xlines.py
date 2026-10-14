"""plan_rebuild_xlines.py FILE [OUT]  -  Xlines are deleted after a round; to RE-RUN a round with new rules (e.g. reach limit) rebuild them from my own tagged dims near claude_Kontur: one XLINE on claude_DIM per chain (H: y, V: x, rotated: base+angle) and delete those dims (OUT = write; without OUT = report only). Then `plan_round.py OUT --write` on the COPY, verify (far / split / collisions), and copy over the real file after snapshot + mtime check. DIM.dxf 2026-10-14: 602 dims -> 25 lines -> 485 dims under the 1 m reach."""
import sys, os, math, collections
R_=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,R_); sys.path.insert(0,R_+'/../scripts')
import ezdxf, plan_xlines_lf as lf
doc=ezdxf.readfile(sys.argv[1]); ms=doc.modelspace(); bound,_=lf.plan_outline(ms)
bx=(min(q[0] for q in bound)-3000,min(q[1] for q in bound)-3000,max(q[0] for q in bound)+3000,max(q[1] for q in bound)+3000)
lines={}; dele=[]; mix=collections.Counter()
for d in ms.query('DIMENSION'):
    if d.dimtype&7!=0: continue
    p2=d.dxf.defpoint2
    if not (bx[0]<=p2.x<=bx[2] and bx[1]<=p2.y<=bx[3]): continue
    own=d.has_xdata('CLAUDE_ROWS') and any(t.value=='xline_dims' for t in d.get_xdata('CLAUDE_ROWS'))
    mix[(own,d.dxf.dimstyle,d.dxf.layer)]+=1
    if not own: continue
    a=(d.dxf.get('angle',0) or 0)%180; dp=d.dxf.defpoint
    if a<0.01: key=('H',round(dp.y,1))
    elif abs(a-90)<0.01: key=('V',round(dp.x,1))
    else: key=('R',round(a,2),round(dp.x*-math.sin(math.radians(a))+dp.y*math.cos(math.radians(a)),1),dp.x,dp.y)
    lines[key]=1; dele.append(d)
print(mix); print('lines',len(lines),collections.Counter(k[0] for k in lines))
if len(sys.argv)>2:
    for k in lines:
        if k[0]=='H': ms.add_xline((0,k[1],0),(1,0,0),dxfattribs={'layer':'claude_DIM'})
        elif k[0]=='V': ms.add_xline((k[1],0,0),(0,1,0),dxfattribs={'layer':'claude_DIM'})
        else: r=math.radians(k[1]); ms.add_xline((k[3],k[4],0),(math.cos(r),math.sin(r),0),dxfattribs={'layer':'claude_DIM'})
    for d in dele: ms.delete_entity(d)
    doc.saveas(sys.argv[2]); print('xlines added, dims deleted',len(dele))
