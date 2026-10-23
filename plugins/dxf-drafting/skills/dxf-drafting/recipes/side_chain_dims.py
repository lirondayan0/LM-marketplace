# Side dimension chains (user 2026-10-21, model = his section 5: 25 / 25 / 70 + overall on each side): every vertical segment beam bottom -> slab soffit -> slab top -> beam top on a side. Identical sides: one side fully detailed; different sides: both. WANT list = missing segments for brenda_karka sections 3,4,6,7 (edit per file); dim_25 on 53_HATAH_MIDA, text -4.5, same line x as the side slab dim.
import ezdxf,sys,shutil,datetime
f=next((a for a in sys.argv[1:] if not a.startswith("--")), r"C:\Users\USER082024\Desktop\AI\חומר לימוד\חתכים\brenda_karka.dxf")
dry='--dry' in sys.argv
doc=ezdxf.readfile(f); msp=doc.modelspace(); x0=-81359.3; YB=180196.8
vs=[e for e in msp.query('LINE') if e.dxf.layer=='9_KONTUR' and abs(e.dxf.start.x-e.dxf.end.x)<1e-6 and abs(e.dxf.start.y-e.dxf.end.y)>8]
dims=[x for x in msp.query('DIMENSION') if x.dxf.hasattr('angle') and abs(x.dxf.angle-90)<1 and x.dxf.layer=='53_HATAH_MIDA']
# (section, side, lo, hi) relative to beam bottom, line x relative to cell, = missing segments of the full chain (non-identical sections 3,4,6,7)
want=[(3,'L',0,90),(4,'L',25,115),(6,'L',0,45),(6,'R',25,95),(7,'L',0,70),(7,'R',25,95)]
todo=[]
for k,side,lo,hi in want:
    a=x0+400*(k-1);b=a+400
    ds=[d for d in dims if a<=d.dxf.defpoint.x<=b and ((d.dxf.defpoint.x-a<200)==(side=='L'))]
    have=[(round(min(d.dxf.defpoint2.y,d.dxf.defpoint3.y)-YB),round(max(d.dxf.defpoint2.y,d.dxf.defpoint3.y)-YB)) for d in ds]
    assert (lo,hi) not in have,(k,side,lo,hi)
    slab=[d for d in ds if max(d.dxf.defpoint2.y,d.dxf.defpoint3.y)-min(d.dxf.defpoint2.y,d.dxf.defpoint3.y)<60 and not(min(d.dxf.defpoint2.y,d.dxf.defpoint3.y)==YB and False)]
    # line x: of the slab-thickness dim on this side (the shortest span, last in list)
    sd=min(ds,key=lambda d:(abs(d.dxf.defpoint2.y-d.dxf.defpoint3.y)))
    lx=sd.dxf.defpoint.x
    xs=sorted({v.dxf.start.x for v in vs if a<=v.dxf.start.x<=b}); face=xs[0] if side=='L' else xs[-1]
    todo.append((k,side,lo,hi,lx,face)); print('section',k,side,lo,'->',hi,'line x rel',round(lx-a,1))
if dry: sys.exit()
shutil.copy2(f,f+'.bak-chain-'+datetime.datetime.now().strftime('%H%M%S'))
for k,side,lo,hi,lx,face in todo:
    yl,yh=YB+lo,YB+hi
    msp.add_linear_dim(base=(lx,(yl+yh)/2),p1=(face,yh),p2=(face,yl),angle=90,location=(lx-4.5,(yl+yh)/2),dimstyle='dim_25',override={'dimexo':1.5,'dimexe':2.0},dxfattribs={'layer':'53_HATAH_MIDA'}).render()
doc.saveas(f); print('written',len(todo))
