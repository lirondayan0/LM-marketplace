"""LEGACY (superseded by ../ledge_beam.py; hard-coded coordinates of the older example set)."""
"""Draw the GEOMETRY of rebar in a section (חתך): help lines, bar dots, stirrup in the cut, stirrup detail.
No text, leaders or dimensions, and no bar sizes (those must come from the engineer).

Usage:  python rebar_section.py FILE N-N [N-N ...] [--dry] [--check76] [--png OUT]
Default: backs up FILE to FILE.bak, adds entities to the ORIGINAL file, re-loads it, audits.

Rules (learned from section 76-76, verified by --check76 which regenerates 76-76's dots and compares):
  HELP_IN   4.5  help lines (2000_DOT_HELP_LINE) = outline inset 4.5 cm; run to the cut end (break line)
  STIR_IN   3.0  stirrup / slab bar lines (57_HATAH_ZIUN) = outline inset 3 cm
  dots      'dot barzel' block on 57_HATAH_ZIUN, at help-line vertices and equally divided along segments:
            horizontal max step 15, vertical max step 25 (UNVERIFIED generalisation of 76-76: 75/15 and 85/25 both exact),
            max step 15 for BOTH directions (finished examples 4-4, 7-7: 20 -> 2x10, 115 -> 8x14.4); 76-76 used 25 (its spec has vstep=25)
            at a cut end the last dot is 4.5 from the cut line
  stirrup   closed rectangle inset 3 from the member faces, + hook (parallelogram) at the top-right corner
  detail    same stirrup redrawn right of the section, same bottom y: 28.5 from a cut line, 58.6 from a wall/edge face
Section outlines are hardcoded below in absolute model coordinates (read from the drawing, 2026-10-03)
and guarded by the position of the section title text.
Existing help lines are never duplicated: only the uncovered parts are added.
"""
import os, sys, math, shutil, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
from dxflib import *

HELP_LAYER, ZIUN_LAYER, DOT_BLOCK = '2000_DOT_HELP_LINE', '57_HATAH_ZIUN', 'dot barzel'
STIR_IN, MAXSTEP_H, MAXSTEP_V = 3.0, 15.0, 15.0   # max dot step 15 everywhere (4-4, 7-7 finished examples; 76-76's stem used 25)
# hook offsets relative to stirrup top-right corner (from 76-76, identical in the cut and in the detail)
HOOK = [(-7.6, -6.0), (-2.2, 0.0), (0.0, 0.0), (0.0, -2.7), (-5.4, -8.6)]

# polyline: dict(pts=[...], cut0=bool, cut1=bool, breaks=[coord,...]) ; cut = that end is a break-line cut end
def P(pts, cut0=False, cut1=False, breaks=()): return dict(pts=pts, cut0=cut0, cut1=cut1, breaks=list(breaks))

SECTIONS = {
 '76-76': dict(title=(40364.8, 48480.6), right=40431.4, dgap=45.8, vstep=25.0,
   help=[P([(40261.4,48415.2),(40431.4,48415.2)], True, True, [40340.9, 40351.9]),
         P([(40431.4,48399.2),(40351.9,48399.2),(40351.9,48314.2),(40340.9,48314.2),(40340.9,48399.2),(40261.4,48399.2)], True, True)],
   stirrup=(40339.4, 48312.7, 40353.4, 48416.7),
   lines=[(40261.4,48416.7,40431.4,48416.7),(40261.4,48397.7,40431.4,48397.7)]),
 '1-1': dict(title=(41169.5, 48011.3), right=41202.2, dgap=28.5,
   help=[P([(41202.2,47950.9),(41127.8,47950.9),(41127.8,47885.9),(41138.8,47885.9),(41138.8,47934.9),(41202.2,47934.9)], True, True, [41138.8, 47934.9])],
   stirrup=(41126.3, 47884.4, 41140.3, 47952.4),
   lines=[(41140.3,47952.4,41202.2,47952.4),(41126.3,47933.4,41202.2,47933.4)]),
 '2-2': dict(title=(40672.2, 48011.3), right=40709.6, dgap=28.5,
   help=[P([(40571.8,47953.0),(40709.6,47953.0)], True, True, [40635.2, 40646.2]),
         P([(40709.6,47937.0),(40646.2,47937.0),(40646.2,47888.0),(40635.2,47888.0),(40635.2,47937.0),(40571.8,47937.0)], True, True)],
   stirrup=(40633.7, 47886.5, 40647.7, 47954.5),
   lines=[(40571.8,47954.5,40709.6,47954.5),(40571.8,47935.5,40709.6,47935.5)]),
 '3-3': dict(title=(40173.5, 48011.3), right=40200.5, dgap=58.6,
   # slab 23 thick + 20x10 upstand; the user's own help-line fragments already outline the 11x24 cage in the upstand
   help=[P([(40095.5,47927.9),(40175.0,47927.9),(40175.0,47937.9),(40186.0,47937.9),(40186.0,47927.9),(40196.0,47927.9),(40196.0,47913.9),(40095.5,47913.9)], True, False, [40175.0, 40186.0]),
         P([(40175.0,47927.9),(40175.0,47913.9)]), P([(40186.0,47927.9),(40186.0,47913.9)])],
   stirrup=(40173.5, 47912.4, 40187.5, 47939.4),
   lines=[(40095.5,47929.4,40197.5,47929.4),(40095.5,47912.4,40197.5,47912.4)],
   extra=[(40197.5,47912.4,40197.5,47929.4)]),   # closes the free slab end (red cloud)
 '4-4': dict(title=(39673.3, 48002.7), right=39658.9, dgap=58.6,
   # slab 23 thick; wall 20 wide above the slab, 7-wide lip below it (single bar line, as in the user's fragments)
   help=[P([(39563.9,47890.2),(39654.4,47890.2)], True, False, [39643.4]),
         P([(39643.4,47890.2),(39643.4,47947.2),(39654.4,47947.2),(39654.4,47846.2)], False, False, [47890.2, 47876.2]),
         P([(39563.9,47876.2),(39654.4,47876.2)], True, False)],
   stirrup=(39641.9, 47874.7, 39655.9, 47948.7),
   lines=[(39563.9,47891.7,39655.9,47891.7),(39563.9,47874.7,39655.9,47874.7)],
   extra=[(39655.9,47874.7,39655.9,47844.7)]),   # slab-bottom bar bends down into the 7-cm lip (red cloud)
 '5-5': dict(title=(39165.6, 48011.3), right=39179.2, dgap=58.6,
   # slab 23 thick + 7-wide lip at the right end: single vertical bar line, no stirrup possible (7 < 2*3 + bar)
   help=[P([(39117.2,47905.6),(39174.7,47905.6),(39174.7,47861.6)], True, False, [47891.6]),
         P([(39117.2,47891.6),(39174.7,47891.6)], True, False)],
   stirrup=None,
   lines=[(39117.2,47907.1,39176.2,47907.1),(39117.2,47890.1,39176.2,47890.1)],
   extra=[(39176.2,47907.1,39176.2,47860.1)]),   # slab-top bar bends down into the 7-cm lip (red cloud)
}

def seg_dots(a, b, trim_a, trim_b, breaks):
    (x0,y0),(x1,y1) = a, b
    L = math.hypot(x1-x0, y1-y0)
    if L < 1e-6: return [a]
    ux, uy = (x1-x0)/L, (y1-y0)/L
    s, e = (4.5 if trim_a else 0.0), L - (4.5 if trim_b else 0.0)
    vertical = abs(ux) < 1e-9
    cuts = [s, e]
    for c in breaks:                       # break coordinate along the segment's axis
        t = ((c - y0)/uy) if vertical else ((c - x0)/ux)
        if s + 0.05 < t < e - 0.05: cuts.append(t)
    cuts.sort()
    step = MAXSTEP_V if vertical else MAXSTEP_H
    out = []
    for t0, t1 in zip(cuts, cuts[1:]):
        n = max(1, math.ceil((t1 - t0)/step - 1e-6))
        out += [(x0 + ux*(t0+(t1-t0)*i/n), y0 + uy*(t0+(t1-t0)*i/n)) for i in range(n+1)]
    return out

def polyline_dots(p):
    global MAXSTEP_V
    pts, out = p['pts'], []
    for i in range(len(pts)-1):
        out += seg_dots(pts[i], pts[i+1], p['cut0'] and i == 0, p['cut1'] and i == len(pts)-2, p['breaks'])
    return out

def dedupe(pts, tol=0.05):
    out = []
    for q in pts:
        if not any(abs(q[0]-o[0]) < tol and abs(q[1]-o[1]) < tol for o in out): out.append(q)
    return out

def existing_help_segments(msp):
    segs = []
    for e in msp:
        if e.dxf.layer != HELP_LAYER: continue
        if e.dxftype() == 'LINE': pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif e.dxftype() == 'LWPOLYLINE': pts = [(x, y) for x, y, *_ in e.get_points()]
        else: continue
        segs += list(zip(pts, pts[1:]))
    return segs

def uncovered(a, b, ex, tol=0.6):
    """Parts of axis-aligned segment a-b not already covered by existing help segments ex."""
    horiz = abs(a[1]-b[1]) < 1e-6
    k = 0 if horiz else 1                                  # coordinate that runs along the segment
    c = a[1-k]
    lo, hi = sorted((a[k], b[k]))
    cov = []
    for (p, q) in ex:
        same_axis = abs(p[1-k] - q[1-k]) < 1e-6 and abs(p[1-k] - c) < tol   # parallel and on the same line
        if same_axis: cov.append(tuple(sorted((p[k], q[k]))))
    cov.sort(); res, cur = [], lo
    for l2, h2 in cov:
        if h2 <= cur: continue
        if l2 > cur + 0.05: res.append((cur, min(l2, hi)))
        cur = max(cur, h2)
        if cur >= hi: break
    if cur < hi - 0.05: res.append((cur, hi))
    res = [(s, e) for s, e in res if e - s > 0.05]
    return [((s, c), (e, c)) if horiz else ((c, s), (c, e)) for s, e in res]

def build(doc, name, spec):
    msp = doc.modelspace()
    # guard: the title text must be where we expect
    ok = any(e.dxftype() == 'TEXT' and e.dxf.layer == '54_HATAH_TEXT' and e.dxf.text.endswith(' ' + name)
             and abs(e.dxf.insert.x - spec['title'][0]) < 1 and abs(e.dxf.insert.y - spec['title'][1]) < 1 for e in msp)
    if not ok: raise SystemExit(f'{name}: title text not found at expected place; outlines are hardcoded, aborting')
    ex = existing_help_segments(msp)
    global MAXSTEP_V
    MAXSTEP_V = spec.get('vstep', 15.0)
    plan = dict(help=[], dots=[], rects=[], hooks=[], lines=[])
    for p in spec['help']:
        plan['dots'] += polyline_dots(p)
        for a, b in zip(p['pts'], p['pts'][1:]):
            plan['help'] += uncovered(a, b, ex)
    plan['dots'] = dedupe(plan['dots'])
    plan['lines'] = list(spec['lines']) + list(spec.get('extra', []))
    st = spec['stirrup']
    if st:
        x0, y0, x1, y1 = st
        dx = spec['right'] + spec['dgap'] - x0   # detail left edge: 28.5 from a cut line, 58.6 from a wall/edge face (finished examples)
        for ox in (0.0, dx):
            plan['rects'].append((x0+ox, y0, x1+ox, y1))
            plan['hooks'].append([(x1+ox+hx, y1+hy) for hx, hy in HOOK])
    return plan

def apply(doc, plan):
    msp = doc.modelspace()
    for a, b in plan['help']: msp.add_line((*a, 0), (*b, 0), dxfattribs={'layer': HELP_LAYER})
    for (x0, y0, x1, y1) in plan['lines']: msp.add_line((x0, y0, 0), (x1, y1, 0), dxfattribs={'layer': ZIUN_LAYER})
    for (x0, y0, x1, y1) in plan['rects']:
        msp.add_lwpolyline([(x0,y0),(x1,y0),(x1,y1),(x0,y1)], close=True, dxfattribs={'layer': ZIUN_LAYER})
    for h in plan['hooks']: msp.add_lwpolyline(h, dxfattribs={'layer': ZIUN_LAYER})
    for x, y in plan['dots']: msp.add_blockref(DOT_BLOCK, (x, y), dxfattribs={'layer': ZIUN_LAYER})

def check76(doc):
    """Regenerate 76-76's dots and compare with the dots that are really in the drawing."""
    plan = build(doc, '76-76', SECTIONS['76-76'])
    real = []
    for e in doc.modelspace().query('INSERT'):
        if e.dxf.name == DOT_BLOCK and 40250 < e.dxf.insert.x < 40500 and 48290 < e.dxf.insert.y < 48450: real.append((e.dxf.insert.x, e.dxf.insert.y))
        elif e.dxf.name.startswith('*U'):
            for t in doc.blocks[e.dxf.name]:
                if t.dxftype() == 'INSERT' and 40250 < t.dxf.insert.x < 40500 and 48290 < t.dxf.insert.y < 48450: real.append((t.dxf.insert.x, t.dxf.insert.y))
    real = dedupe(real, 0.2)
    miss = [q for q in real if not any(abs(q[0]-o[0]) < .2 and abs(q[1]-o[1]) < .2 for o in plan['dots'])]
    extra = [o for o in plan['dots'] if not any(abs(q[0]-o[0]) < .2 and abs(q[1]-o[1]) < .2 for q in real)]
    print(f'76-76 check: real dots {len(real)}, generated {len(plan["dots"])}, missing {len(miss)}, extra {len(extra)}')
    if miss: print('  missing', [(round(a,1), round(b,1)) for a, b in miss])
    if extra: print('  extra', [(round(a,1), round(b,1)) for a, b in extra])
    st = SECTIONS['76-76']['stirrup']; print('  76 stirrup rect', st, ' detail would be at x', st[0] + (SECTIONS['76-76']['right'] + SECTIONS['76-76']['dgap']) - st[0])

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('file'); ap.add_argument('sections', nargs='*')
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--check76', action='store_true'); ap.add_argument('--png')
    a = ap.parse_args()
    doc = ezdxf.readfile(a.file)
    if a.check76: check76(doc); sys.exit()
    plans = {s: build(doc, s, SECTIONS[s]) for s in a.sections}
    for s, p in plans.items():
        print(f'{s}: help segments {len(p["help"])}, dots {len(p["dots"])}, stirrups {len(p["rects"])}, slab lines {len(p["lines"])}')
    if a.dry: sys.exit()
    shutil.copy2(a.file, a.file + '.bak')
    for p in plans.values(): apply(doc, p)
    doc.saveas(a.file)
    d2 = ezdxf.readfile(a.file); aud = d2.audit(); print('reloaded OK, audit errors:', len(aud.errors))
