"""Is this beam a TRANSFER beam (it carries a new structural element rising from it)?  (user 2026-10-15: two stirrup tables, standard vs transfer)
  python transfer_check.py FILE X0 Y0 X1 Y1 [--layers 82_KIR_OLE,15_DASHED]
  python transfer_check.py FILE --pairs        (every star pair on automatic_sections: finds its beam strip and checks it)
(X0 Y0 X1 Y1) = the beam strip (outer outline of the beam in plan). Lists every closed polyline / hatch on the 'new element' layers whose box lies on the strip: a pier / wall standing on the beam.
Evidence only - the user decides (ask once per plan). On sections_ramla.dxf the 65/65 west beam (x 80972..81037) carries a 40 x 150 pier on 82_KIR_OLE (hatch 63_HATCH_KIR_OLE): transfer."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ezdxf
from ezdxf import bbox

def elements_on(doc, x0, y0, x1, y1, layers=('82_KIR_OLE',), min_overlap=0.5):
    out = []
    for e in doc.modelspace():
        if e.dxf.layer not in layers or e.dxftype() not in ('LWPOLYLINE', 'HATCH', 'INSERT'): continue
        try: b = bbox.extents([e])
        except Exception: continue
        if not b.has_data: continue
        ox, oy = min(b.extmax.x, x1) - max(b.extmin.x, x0), min(b.extmax.y, y1) - max(b.extmin.y, y0)
        if ox > 0 and oy > 0 and ox * oy >= min_overlap * min(b.size.x * b.size.y, (x1 - x0) * (y1 - y0)) and b.size.x < 3000 and b.size.y < 3000:
            out.append((e.dxftype(), e.dxf.layer, tuple(round(v) for v in (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))))
    return out

def _segments(doc, layer='93_KORA'):
    """axis-parallel segments (x0, y0, x1, y1) of LINEs and LWPOLYLINE edges on the beam layer"""
    out = []
    for e in doc.modelspace():
        if e.dxf.layer != layer: continue
        if e.dxftype() == 'LINE': pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif e.dxftype() == 'LWPOLYLINE': pts = [(p[0], p[1]) for p in e.get_points('xy')] + ([(e.get_points('xy')[0][0], e.get_points('xy')[0][1])] if e.closed else [])
        else: continue
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) < 0.5 or abs(a[1] - b[1]) < 0.5: out.append((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
    return out

def beam_strip(doc, mx, my, vertical_cut, segs=None, max_w=150):
    """Beam strip (x0, y0, x1, y1) crossed by a cut centred at (mx, my): the nearest pair of parallel beam edges around the cut centre, over the full length of those edges. vertical_cut=True -> horizontal beam."""
    segs = segs or _segments(doc)
    if vertical_cut:      # horizontal edges crossing x = mx
        es = [s for s in segs if abs(s[1] - s[3]) < .5 and s[0] < mx < s[2] and abs(s[1] - my) < 80]; key = lambda s: s[1]
    else:
        es = [s for s in segs if abs(s[0] - s[2]) < .5 and s[1] < my < s[3] and abs(s[0] - mx) < 80]; key = lambda s: s[0]
    vals = sorted({round(key(s)) for s in es}); c = my if vertical_cut else mx
    pr = min(((a, b) for a in vals for b in vals if 0 < b - a < max_w and a - 1 <= c <= b + 1 or (0 < b - a < max_w and abs((a + b) / 2 - c) < 40)), key=lambda ab: abs((ab[0] + ab[1]) / 2 - c), default=None)
    if not pr: return None
    sel = [s for s in es if round(key(s)) in pr]
    if vertical_cut: return (min(s[0] for s in sel), pr[0], max(s[2] for s in sel), pr[1])
    return (pr[0], min(s[1] for s in sel), pr[1], max(s[3] for s in sel))

if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] != '--pairs' and len(a) > 1 and a[1] == '--pairs':
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'recipes')); from star_orient import pairs
        doc = ezdxf.readfile(a[0]); segs = _segments(doc)
        for p, q in pairs(doc, 40000):
            mx, my = (p.dxf.insert.x + q.dxf.insert.x) / 2, (p.dxf.insert.y + q.dxf.insert.y) / 2; st = beam_strip(doc, mx, my, round(p.dxf.rotation) % 360 in (90, 270), segs)
            r = elements_on(doc, *st) if st else None
            print(f'pair ({mx:.0f},{my:.0f}) looks {round(p.dxf.rotation) % 360}: strip {[round(v) for v in st] if st else None} -> ' + ('no beam found' if st is None else ('TRANSFER ' + str(len(r)) + ' element(s)' if r else 'standard')))
        sys.exit(0)
    layers = tuple(a[a.index('--layers') + 1].split(',')) if '--layers' in a else ('82_KIR_OLE',)
    x0, y0, x1, y1 = map(float, a[1:5]); doc = ezdxf.readfile(a[0]); r = elements_on(doc, x0, y0, x1, y1, layers)
    print('TRANSFER (new element on the beam):' if r else 'standard (nothing rises from it)', *r, sep='\n  ')
