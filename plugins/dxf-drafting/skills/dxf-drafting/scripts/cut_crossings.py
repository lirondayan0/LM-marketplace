"""What does each section cut line cross on the plan? (user 2026-10-18: 'review all the sections' - the plan decides the section)
  python cut_crossings.py FILE --box X0 Y0 X1 Y1
For every pair of `hat` marks (same attribute) inside the box prints the distance along the cut (from the first mark) of every crossing line on the plan layers:
  93_KORA = beam face, 0_LUHADIM_SHEN = hollow-core panel edge (15 inside a face = LEDGE on that side), 15_DASHED = wall above.
Reading (conventions/sections-reading.md, sections 1-2): KORA pair = beam width; one LUH = ledge on that side and the other side is the solid casting completion;
view parallel to the panel span (plan_cuts CORES) = cast beam with circles. Compare with the drawn section (dims: B, ledge 15, sides)."""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ezdxf
from ezdxf import bbox

SKIP = ('automatic_sections', 'claude', '72_MISGERET_WIN')

def segs(e):
    if e.dxftype() == 'LINE': yield (e.dxf.start.x, e.dxf.start.y, e.dxf.end.x, e.dxf.end.y)
    elif e.dxftype() == 'LWPOLYLINE':
        p = [(a[0], a[1]) for a in e.get_points('xy')]
        if e.closed: p.append(p[0])
        for a, b in zip(p, p[1:]): yield (a[0], a[1], b[0], b[1])

def pairs(doc, box):
    x0, y0, x1, y1 = box
    hats = [(e.attribs[0].dxf.text, e.dxf.insert.x, e.dxf.insert.y) for e in doc.modelspace().query('INSERT')
            if e.dxf.name.lower() == 'hat' and e.attribs and x0 < e.dxf.insert.x < x1 and y0 < e.dxf.insert.y < y1]
    used, out = set(), []
    for i, h in enumerate(hats):
        if i in used: continue
        c = [(math.hypot(h[1] - g[1], h[2] - g[2]), j) for j, g in enumerate(hats) if j != i and j not in used and g[0] == h[0]]
        if c:
            d, j = min(c); used |= {i, j}; out.append((h[0], (h[1], h[2]), (hats[j][1], hats[j][2]), d))
    return sorted(out, key=lambda p: p[0])

def crossings(doc, box, p, q):
    L = math.hypot(q[0] - p[0], q[1] - p[1]); res = set()
    for e in doc.modelspace():
        if e.dxftype() not in ('LINE', 'LWPOLYLINE') or e.dxf.layer in SKIP: continue
        try:
            b = bbox.extents([e])
            if not b.has_data or b.size.x > 60000 or b.size.y > 60000: continue
            if max(p[0], q[0]) + 1 < b.extmin.x or min(p[0], q[0]) - 1 > b.extmax.x or max(p[1], q[1]) + 1 < b.extmin.y or min(p[1], q[1]) - 1 > b.extmax.y: continue
        except Exception: continue
        for a1, b1, a2, b2 in segs(e):
            r = (q[0] - p[0], q[1] - p[1]); s = (a2 - a1, b2 - b1); den = r[0] * s[1] - r[1] * s[0]
            if abs(den) < 1e-9: continue
            t = ((a1 - p[0]) * s[1] - (b1 - p[1]) * s[0]) / den; u = ((a1 - p[0]) * r[1] - (b1 - p[1]) * r[0]) / den
            if -0.02 <= t <= 1.02 and 0 <= u <= 1: res.add((round(t * L), e.dxf.layer))
    return sorted(res)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0]); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True)
    a = ap.parse_args(); doc = ezdxf.readfile(a.file)
    for name, p, q, L in pairs(doc, a.box):
        print(f'SECTION {name}: {[round(v) for v in p]} -> {[round(v) for v in q]} length {L:.0f}\n   {crossings(doc, a.box, p, q)}')
