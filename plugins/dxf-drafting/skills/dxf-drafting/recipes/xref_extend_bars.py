"""Recipe: extend overlay slab bars to the XREF slab end (user 2026-10-23, 3841-CON_test.dxf, red cloud on 7-7 right).
  python xref_extend_bars.py FILE [--dry]
Rule (read from his hand-fixed 7-7 left side): a horizontal slab bar drawn by xref_overlay / ledge_beam (2-point LWPOLYLINE on BAR_LAYERS, > MIN_LEN long)
runs to the END OF THE XREF SLAB (A-FLOR-1 extreme x on that side, no cover gap), not the generator's 60 cm. Only the end far from the beam is moved;
leaders, dots and XREF geometry are untouched. Idempotent. Snapshot FILE.bak-xrefext-HHMMSS before writing (in place, his rule)."""
import argparse, re, shutil, time
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts')); from dxflib import XREF_ROLE_LAYERS as RL, xref_section_number      # Revit layer names by role
import ezdxf

BAR_LAYERS = ('51_HATAH_DASHED', '57_HATAH_ZIUN'); MIN_LEN = 20; REACH = 150; TOL = 0.05
def lay(e): return e.dxf.layer.split('$0$')[-1]

def ends(e):
    if e.dxftype() == 'LINE': return (e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)
    return (e[0][0], e[0][1]), (e[1][0], e[1][1])

def run(F, dry=False):
    doc = ezdxf.readfile(F); msp = doc.modelspace(); n = 0
    bars = [e for e in msp if e.dxf.layer in BAR_LAYERS and ((e.dxftype() == 'LWPOLYLINE' and len(e) == 2) or e.dxftype() == 'LINE')      # ledge_beam draws 2-point polylines, general_beam (cast beams) LINEs
            and abs(ends(e)[0][1] - ends(e)[1][1]) < 0.01 and abs(ends(e)[0][0] - ends(e)[1][0]) > MIN_LEN and not e.has_xdata('DXFSKILL_TEMPLATE')]
    for ins in msp.query('INSERT'):
        sec = xref_section_number(ins.dxf.name)
        if sec is None: continue
        ix, iy = ins.dxf.insert.x, ins.dxf.insert.y; L = [s for s in doc.blocks.get(ins.dxf.name) if s.dxftype() == 'LINE']
        bm = [s for s in L if lay(s) in RL['beam']]; fl = [s for s in L if lay(s) in RL['floor']]
        if not bm or not fl: continue
        xs = [v + ix for s in bm for v in (s.dxf.start.x, s.dxf.end.x)]; ys = [v + iy for s in bm for v in (s.dxf.start.y, s.dxf.end.y)]
        bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys); xc = (bx0 + bx1) / 2
        fx = [v + ix for s in fl for v in (s.dxf.start.x, s.dxf.end.x)]; sx0, sx1 = min(fx), max(fx)
        for e in bars:
            (a, ya), (b, _) = ends(e)
            if not (bx0 - REACH < min(a, b) and max(a, b) < bx1 + REACH and by0 - 20 < ya < by1 + 20): continue
            far = 0 if abs(a - xc) > abs(b - xc) else 1; x = (a, b)[far]; tgt = sx0 if x < xc else sx1
            if abs(x - tgt) < TOL: continue
            print('Sec', sec, e.dxf.layer, e.dxf.handle, round(x, 1), '->', round(tgt, 1)); n += 1
            if e.dxftype() == 'LINE': setattr(e.dxf, 'start' if far == 0 else 'end', (tgt, ya, 0.0))
            else: pts = list(e.get_points('xyseb')); pts[far] = (tgt,) + tuple(pts[far][1:]); e.set_points(pts, format='xyseb')
    print(n, 'bars extended')
    if n and not dry:
        shutil.copy2(F, F + '.bak-xrefext-' + time.strftime('%H%M%S')); doc.saveas(F)
    return n

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--dry', action='store_true'); a = ap.parse_args(); run(a.file, a.dry)
