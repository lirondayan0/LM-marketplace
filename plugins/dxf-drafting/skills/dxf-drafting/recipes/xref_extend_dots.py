"""Recipe: extend the slab top-bar DOT ROWS to the XREF slab end (user 2026-10-23, 3841-CON_test Sec 9 + 7 left: he added the end dots by hand).
  python xref_extend_dots.py FILE [apply]      (default = report only)
After xref_extend_bars.py the top bar (57_HATAH_ZIUN horizontal) reaches the slab end; its transverse-bar dots (1-wide polylines at bar y - 1, spacing read from the row, 20 in the file) continue
outwards at the same spacing while the dot stays >= 0.7 from the slab end. Idempotent; snapshot FILE.bak-dots-HHMMSS. Dots are plain polylines, NOT associative arrays (bar_arrays.py can re-array them) - UNVERIFIED if he wants arrays."""
import ezdxf,re,sys,shutil,time
F=sys.argv[1]
apply=len(sys.argv)>2 and sys.argv[2]!="--dry"
doc=ezdxf.readfile(F); msp=doc.modelspace()
def lay(e): return e.dxf.layer.split('$0$')[-1]
bars=[e for e in msp if e.dxftype()=='LWPOLYLINE' and e.dxf.layer=='57_HATAH_ZIUN' and len(e)==2 and abs(e[0][1]-e[1][1])<.01 and abs(e[0][0]-e[1][0])>20]
dots=[e for e in msp if e.dxftype()=='LWPOLYLINE' and e.dxf.layer=='57_HATAH_ZIUN' and len(e)==2 and abs(e[0][1]-e[1][1])<.01 and abs(e[0][0]-e[1][0])<1.5]
tot=0; new=[]
for ins in msp.query('INSERT'):
    m=re.search(r'Sec (\d+)-(\d+)$',ins.dxf.name)
    if not m: continue
    ix,iy=ins.dxf.insert.x,ins.dxf.insert.y; L=[s for s in doc.blocks.get(ins.dxf.name) if s.dxftype()=='LINE']
    fl=[v+ix for s in L if lay(s)=='A-FLOR-1' for v in (s.dxf.start.x,s.dxf.end.x)]
    bm=[s for s in L if lay(s)=='S-BEAM-1']
    if not fl or not bm: continue
    sx0,sx1=min(fl),max(fl); bx=[v+ix for s in bm for v in (s.dxf.start.x,s.dxf.end.x)]; xc=(min(bx)+max(bx))/2
    for b in bars:
        x0,x1=sorted((b[0][0],b[1][0])); y=b[0][1]
        if not(min(bx)-150<x0 and x1<max(bx)+150 and abs(y-(min(s.dxf.start.y for s in bm)+iy))<200): continue
        left=(x0+x1)/2<xc
        row=sorted([d for d in dots if abs(d[0][1]-(y-1))<0.06 and x0-1<=min(d[0][0],d[1][0]) and max(d[0][0],d[1][0])<=x1+1],key=lambda d:min(d[0][0],d[1][0]),reverse=left)  # from the beam outwards
        # bars reach the slab end only after xref_extend_bars; skip rows not at the end
        if len(row)<2: 
            if row: print('Sec',m.group(1),'row with 1 dot only',round(y,1)); 
            continue
        xs=[min(d[0][0],d[1][0]) for d in row]; sp=abs(xs[1]-xs[0]); w=abs(row[0][1][0]-row[0][0][0]) if False else 1.0
        cur=xs[-1]; added=0
        while True:
            nx=cur-sp if left else cur+sp
            ok=(nx>=sx0+0.7-0.05) if left else (nx+1<=sx1-0.7+0.05)
            if not ok: break
            if not any(abs(min(d[0][0],d[1][0])-nx)<1 for d in row): new.append((m.group(1),row[-1],nx-xs[-1])); added+=1
            cur=nx
        print('Sec',m.group(1),'left' if left else 'right','y',round(y-1,1),'dots',len(row),'sp',round(sp,1),'+',added)
        tot+=added
print(tot,'dots to add')
if apply and new:
    for n,tpl,dx in new:
        c=tpl.copy(); c.translate(dx,0,0); msp.add_entity(c)
    shutil.copy2(F,F+'.bak-dots-'+time.strftime('%H%M%S')); doc.saveas(F); print('saved')
