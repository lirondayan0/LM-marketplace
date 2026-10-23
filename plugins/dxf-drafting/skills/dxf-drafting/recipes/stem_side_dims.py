# Right-side stem dim (user 2026-10-21, section 2 example): vertical dim_25 on 53_HATAH_MIDA from beam bottom to the right slab soffit, on the same line x as the right slab-thickness dim (left side already has overall height + slab). Skips sections whose right slab sits at the beam bottom (no stem) and the 20-wide one. FILE constant; --dry first.
import ezdxf,sys,shutil,datetime
f=next((a for a in sys.argv[1:] if not a.startswith("--")), r"C:\Users\USER082024\Desktop\AI\חומר לימוד\חתכים\brenda_karka.dxf")
dry='--dry' in sys.argv
doc=ezdxf.readfile(f); msp=doc.modelspace(); x0=-81359.3; YB=180196.8
vs=[e for e in msp.query('LINE') if e.dxf.layer=='9_KONTUR' and abs(e.dxf.start.x-e.dxf.end.x)<1e-6 and abs(e.dxf.start.y-e.dxf.end.y)>8]
dims=[x for x in msp.query('DIMENSION') if x.dxf.hasattr('angle') and abs(x.dxf.angle-90)<1 and x.dxf.layer=='53_HATAH_MIDA']
todo=[]
for k in range(9):
    a=x0+400*k;b=a+400
    if k==7: print('section 8 skipped'); continue
    if k==1: print('section 2 = user example, kept'); continue
    side=[v for v in vs if a<=v.dxf.start.x<=b]; Rf=max(v.dxf.start.x for v in side)
    stem=[v for v in side if abs(v.dxf.start.x-Rf)<0.1 and abs(min(v.dxf.start.y,v.dxf.end.y)-YB)<0.1]
    if not stem: print('section',k+1,'no stem below right slab'); continue
    yu=max(stem[0].dxf.start.y,stem[0].dxf.end.y)
    rd=[d for d in dims if a<=d.dxf.defpoint.x<=b and d.dxf.defpoint.x-a>250]
    lx=rd[0].dxf.defpoint.x
    print('section',k+1,'stem',round(yu-YB,1),'line x rel',round(lx-a,1)); todo.append((Rf,yu,lx))
if dry: sys.exit()
shutil.copy2(f,f+'.bak-stem-'+datetime.datetime.now().strftime('%H%M%S'))
for Rf,yu,lx in todo:
    msp.add_linear_dim(base=(lx,(yu+YB)/2),p1=(Rf,yu),p2=(Rf,YB),angle=90,location=(lx-4.5,(yu+YB)/2),dimstyle='dim_25',override={'dimexo':1.5,'dimexe':2.0},dxfattribs={'layer':'53_HATAH_MIDA'}).render()
doc.saveas(f); print('written',len(todo))
