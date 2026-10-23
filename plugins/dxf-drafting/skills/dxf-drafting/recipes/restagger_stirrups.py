# Re-draw the stirrup group of ONE section with a new count (user 2026-10-21, 9-9 stem 250: 7 -> 9 x 40): keeps the first rectangle + its ticks / dims, deletes the rest, copies it at the new step (B-6-w)/(n-1) in the section and in the detail row (dy -5.9 each), re-adds the dims, edits the note count. Constants (B, old n, cell lookup, rectangle size 40 x 69) are for brenda_karka 9-9: adapt. FILE = argv[1] optional; --dry first.
import sys,ezdxf,shutil,datetime
sys.path.insert(0,r"C:\Users\USER082024\.claude\skills\dxf-drafting\scripts"); import dxflib
from ezdxf import bbox
f=r"C:\Users\USER082024\Desktop\AI\חומר לימוד\חתכים\brenda_karka.dxf"; dry='--dry' in sys.argv
doc=ezdxf.readfile(f); msp=doc.modelspace()
seps=sorted([e.dxf.start.x for e in msp.query('LINE') if e.dxf.layer=='72_MISGERET_WIN' and abs(e.dxf.start.x-e.dxf.end.x)<1e-6])
out=[e for e in msp.query('LWPOLYLINE') if e.dxf.layer=='72_MISGERET_WIN'][0]
xa=seps[-1]; xb=max(p[0] for p in out.get_points('xy')); Y0=179930.994
B=250.0; n_old=7; n_new,w=dxflib.stirrup_layout(B,'transfer')[:2]; print('new',n_new,w)
cell=[]
for e in msp:
    if e.dxf.layer in('72_MISGERET_WIN','claude'): continue
    try: b=bbox.extents([e])
    except Exception: continue
    if b.has_data and xa<(b.extmin.x+b.extmax.x)/2<xb: cell.append((e,b))
rects=sorted([(e,b) for e,b in cell if e.dxftype()=='LWPOLYLINE' and e.dxf.layer=='57_HATAH_ZIUN' and e.closed and abs(b.extmax.x-b.extmin.x-40)<0.1 and abs(b.extmax.y-b.extmin.y-69)<0.1],key=lambda t:(-t[1].extmax.y,t[1].extmin.x))
sec=[t for t in rects if t[1].extmax.y-Y0>300]; det=[t for t in rects if t[1].extmax.y-Y0<300]
assert len(sec)==7 and len(det)==7,(len(sec),len(det))
sec.sort(key=lambda t:t[1].extmin.x); det.sort(key=lambda t:t[1].extmin.x)
def members(r):
    e0,b0=r; res=[]
    for e,b in cell:
        if e is e0: continue
        if b.extmin.x>=b0.extmin.x-.5 and b.extmax.x<=b0.extmax.x+.5 and b.extmin.y>=b0.extmin.y-.5 and b.extmax.y<=b0.extmax.y+.5 and ((e.dxftype()=='LINE' and e.dxf.layer=='57_HATAH_ZIUN' and e.dxf.start.distance(e.dxf.end)<6 and b.extmax.x>b0.extmax.x-6 and b.extmax.y>b0.extmax.y-6) or (e.dxftype()=='DIMENSION' and e.dxf.layer=='54_HATAH_TEXT')): res.append(e)
    return res
x0s=det[0][1].extmin.x; step_new=(B-6-w)/(n_new-1); print('step',step_new)
def build(group,dy_step):
    r0=group[0]; mem0=members(r0); olds=[]
    for r in group[1:]: olds+= [r[0]]+members(r)
    return r0,mem0,olds
plan=[]
for g,dy in ((sec,0.0),(det,-5.9)): plan.append((g,dy)+build(g,dy))
for g,dy,r0,mem0,olds in plan: print('keep',r0[0].dxf.handle,'members',[m.dxf.handle for m in mem0],'delete',len(olds))
if dry: sys.exit()
shutil.copy2(f,f+'.bak-st9-'+datetime.datetime.now().strftime('%H%M%S'))
def delete(e):
    if e.dxftype()=='DIMENSION':
        g=e.dxf.geometry; msp.delete_entity(e)
        if g in doc.blocks: doc.blocks.delete_block(g,safe=False)
    else: msp.delete_entity(e)
for g,dy,r0,mem0,olds in plan:
    for e in olds: delete(e)
    for i in range(1,n_new):
        ox=i*step_new; oy=i*dy
        c=r0[0].copy(); msp.add_entity(c); c.translate(ox,oy,0)
        for m in mem0:
            if m.dxftype()=='LINE':
                c=m.copy(); msp.add_entity(c); c.translate(ox,oy,0)
            else:
                p1=m.dxf.defpoint2; p2=m.dxf.defpoint3; base=m.dxf.defpoint
                d=msp.add_linear_dim(base=(base.x+ox,base.y+oy),p1=(p1.x+ox,p1.y+oy),p2=(p2.x+ox,p2.y+oy),angle=m.dxf.angle,dimstyle=m.dxf.dimstyle,dxfattribs={'layer':m.dxf.layer},location=(m.dxf.text_midpoint.x+ox,m.dxf.text_midpoint.y+oy))
                if m.has_xdata('ACAD'): d.set_xdata('ACAD',list(m.get_xdata('ACAD')))
                d.render()
for e,b in cell:
    if e.dxftype()=='TEXT' and dxflib.decode(e.dxf.text).startswith('7$12'):
        e.dxf.text='9'+e.dxf.text[1:]; ins=e.dxf.insert; e.dxf.insert=(ins.x,ins.y-5.9*(n_new-n_old),ins.z); print('note ->',e.dxf.text)
doc.saveas(f); print('written')
