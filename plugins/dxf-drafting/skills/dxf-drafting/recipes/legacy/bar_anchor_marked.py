# Slab bar anchorage from the user clouds (2026-10-21): every claude cloud on a section row -> the long ZIUN bar crossing it ends 60 from the beam face it enters through (W-3 if narrower). Usage: python bar_anchor_marked.py [--dry]; FILE constant below = brenda_karka.dxf (edit); snapshots .bak-barlen2-*; read UTF-8 when patching scripts.
import ezdxf,sys,shutil,datetime
f=next((a for a in sys.argv[1:] if not a.startswith("--")), r"C:\Users\USER082024\Desktop\AI\חומר לימוד\חתכים\brenda_karka.dxf")
dry='--dry' in sys.argv
doc=ezdxf.readfile(f); msp=doc.modelspace()
clouds=[e for e in msp.query('LWPOLYLINE') if e.dxf.layer=='claude']
ls=[e for e in msp.query('LINE') if e.dxf.layer=='57_HATAH_ZIUN' and abs(e.dxf.start.y-e.dxf.end.y)<1e-6]
vs=[e for e in msp.query('LINE') if e.dxf.layer=='9_KONTUR' and abs(e.dxf.start.x-e.dxf.end.x)<1e-6 and abs(e.dxf.start.y-e.dxf.end.y)>8]
for c in clouds:
    p=[(q[0],q[1]) for q in c.get_points()]; cx0,cx1=min(a for a,b in p),max(a for a,b in p); cy0,cy1=min(b for a,b in p),max(b for a,b in p)
    if not(-81360<cx0<-77700 and 180190<cy0<180330) or cx1-cx0>400: continue
    xs=sorted({round(v.dxf.start.x,1) for v in vs if cx0-60<v.dxf.start.x<cx1+60})
    Lf,Rf=xs[0],xs[-1]; W=Rf-Lf; anc=min(60.0,W-3)
    for e in ls:
        s,t=e.dxf.start,e.dxf.end
        if not(cy0<=s.y<=cy1) or max(s.x,t.x)<cx0 or min(s.x,t.x)>cx1: continue
        if abs(s.x-Lf)<6 or abs(s.x-Rf)<6:
            new=(Rf-anc) if abs(s.x-Lf)<6 else (Lf+anc)
            print(c.dxf.handle,e.dxf.handle,'y',round(s.y,1),round(s.x,1),'->',round(new,1))
            if not dry: e.dxf.start=(new,s.y,s.z)
if not dry:
    shutil.copy2(f,f+'.bak-barlen2-'+datetime.datetime.now().strftime('%H%M%S')); doc.saveas(f)
