# Align a sheet row (user 2026-10-21: "section 8 too low"): every section hangs from ONE title line (titles at the same y), line chosen so the tallest section hangs inside the frame; tops then share the margin. Run AFTER section_gaps/center (centring in y per section breaks alignment: do NOT centre sections vertically individually). FILE = argv[1] optional; --dry first; snapshot .bak-align-*.
import sys,ezdxf,shutil,datetime
sys.path.insert(0,r"C:\Users\USER082024\.claude\skills\dxf-drafting\scripts")
import dxflib
from ezdxf import bbox
f=r"C:\Users\USER082024\Desktop\AI\חומר לימוד\חתכים\brenda_karka.dxf"; dry='--dry' in sys.argv
doc=ezdxf.readfile(f); msp=doc.modelspace(); Y0=179930.994; H=483.27
seps=sorted([e for e in msp.query('LINE') if e.dxf.layer=='72_MISGERET_WIN' and abs(e.dxf.start.x-e.dxf.end.x)<1e-6 and abs(abs(e.dxf.start.y-e.dxf.end.y)-H)<1],key=lambda e:e.dxf.start.x)
out=[e for e in msp.query('LWPOLYLINE') if e.dxf.layer=='72_MISGERET_WIN'][0]
edges=[-81359.2809]+[e.dxf.start.x for e in seps]+[max(p[0] for p in out.get_points('xy'))]
cells=[[] for _ in range(9)]; titles={}
for e in msp:
    if e.dxf.layer in('72_MISGERET_WIN','claude'): continue
    try: b=bbox.extents([e])
    except Exception: continue
    if not b.has_data: continue
    cx=(b.extmin.x+b.extmax.x)/2; cy=(b.extmin.y+b.extmax.y)/2
    if Y0-60<cy<Y0+H+60:
        for k in range(9):
            if edges[k]<cx<edges[k+1]:
                cells[k].append((e,b))
                if e.dxftype()=='TEXT' and dxflib.decode(e.dxf.text).startswith('חתך'): titles[k]=e.dxf.insert.y
st=[]
for k,c in enumerate(cells):
    y0=min(b.extmin.y for e,b in c); y1=max(b.extmax.y for e,b in c); st.append((titles[k],y0,y1))
dmax=max(t-y0 for t,y0,y1 in st); amax=max(y1-t for t,y0,y1 in st)
T=Y0+(H+dmax-amax)/2
print('envelope below title',round(dmax,1),'above',round(amax,1),'-> title line y',round(T,1),'free total',round(H-dmax-amax,1))
for k,(t,y0,y1) in enumerate(st): print('cell',k+1,'title',round(t,1),'move',round(T-t,1),'bottom margin',round(y0+T-t-Y0,1),'top margin',round(Y0+H-(y1+T-t),1))
if dry: sys.exit()
shutil.copy2(f,f+'.bak-align-'+datetime.datetime.now().strftime('%H%M%S'))
for k,c in enumerate(cells):
    for e,b in c: e.translate(0,T-st[k][0],0)
doc.saveas(f); print('written')
