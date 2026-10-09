"""Recipe: add dimensions to one section. Usage:
  python dim_section.py FILE.dxf 3-3 [-o OUT.dxf] [--dry] [--png OUT.png]
Updates FILE in place (FILE.bak backup first); -o saves a separate copy instead. Rules: ../SKILL.md. Conventions = constants below."""
import argparse, os, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from dxflib import *

PROF = load_profile()                     # office constants live in ../profiles/*.json (--profile NAME to switch)
def use_profile(name):
    global PROF, OUTLINE, DIMLAYER, DIMSTYLE, OVERRIDE, NEAR, FAR, TOL
    PROF = load_profile(name); d = PROF['dim']
    OUTLINE = tuple(PROF['layers']['outline']); DIMLAYER = PROF['layers']['dim']      # cut outline layers (several occur)
    DIMSTYLE, OVERRIDE, NEAR, FAR, TOL = d['style'], d['override'], d['near'], d['far'], d['tol']   # override: style default hides extension lines
use_profile('israeli-structural')

def title_of(e):  # titles read '%%U' + Hebrew 'חתך' typed as 'j,l' + ' 3-3'
    t = e.dxf.text
    return t.replace('%%U', '').split(' ', 1) if 'j,l' in t else None

def find_title(msp, name, near=None):
    found = [t for t in msp.query('TEXT') if (p := title_of(t)) and p[1].strip() == name
             and (near is None or abs(t.dxf.insert.x - near[0]) < 300 and abs(t.dxf.insert.y - near[1]) < 300)]
    if len(found) != 1:
        names = sorted(p[1] for t in msp.query('TEXT') if (p := title_of(t)))
        sys.exit(f'title {name!r}: {len(found)} matches; available: {names}')
    return found[0]

def is_break_mark(e):  # narrow zig-zag polyline marking where the cut stops
    if e.dxftype() != 'LWPOLYLINE': return False
    b = bbox.extents([e]); w, h = b.size.x, b.size.y
    return min(w, h) > 1 and ((w < 15 and h >= 2 * w) or (h < 15 and w >= 2 * h))

def outline_points(msp, title):
    tx, ty = title.dxf.insert.x, title.dxf.insert.y
    pts = []
    for e in msp:
        if e.dxf.layer not in OUTLINE or e.dxftype() not in ('LINE', 'LWPOLYLINE') or is_break_mark(e):
            continue
        b = bbox.extents([e])
        if tx - 250 < b.extmin.x and b.extmax.x < tx + 250 and ty - 200 < b.extmin.y and b.extmax.y < ty - 10:
            pts += [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)] if e.dxftype() == 'LINE' \
                else [(x, y) for x, y, *_ in e.get_points()]
    if not pts: sys.exit('no outline found under the title')
    return pts

def break_xs(msp, title):
    tx, ty = title.dxf.insert.x, title.dxf.insert.y
    out = []
    for e in msp.query('LWPOLYLINE'):
        if e.dxf.layer in OUTLINE and is_break_mark(e):
            b = bbox.extents([e])
            if tx - 250 < b.extmin.x and b.extmax.x < tx + 250 and ty - 200 < b.extmin.y and b.extmax.y < ty + 10: out.append(b.center.x)
    return out

def plan(pts, breaks=()):
    """Return [(base, p1, p2, angle)] following the office rule."""
    xs, ys = levels(p[0] for p in pts), levels(p[1] for p in pts)
    x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]
    at = lambda v, i: [p for p in pts if abs(p[i] - v) <= TOL]
    d = []
    # user rule 2026-10-06: a slab that continues past a break mark has a variable length -> no dimension for it, and no overall width
    var = lambda v: any(abs(v - b) < 8 for b in breaks)
    for a, b in zip(xs, xs[1:]):                          # bottom: parts
        if not (var(a) or var(b)): d.append(((a, y0 - NEAR), (a, y0), (b, y0), 0))
    if len(xs) > 2 and not breaks: d.append(((x0, y0 - FAR), (x0, y0), (x1, y0), 0))   # bottom: overall
    left = at(x0, 0)                                      # left: end thickness near, overall far
    ly0, ly1 = min(p[1] for p in left), max(p[1] for p in left)
    d.append(((x0 - NEAR, y0), (x0, ly0), (x0, ly1), 90))
    if len(ys) > 2 and abs((ly1 - ly0) - (y1 - y0)) > TOL: d.append(((x0 - FAR, y0), (x0, y0), (x0, y1), 90))   # overall only if different from the end thickness
    for a, b in zip(ys, ys[1:]):                          # right: every level step
        pa = max(at(a, 1), key=lambda p: p[0]); pb = max(at(b, 1), key=lambda p: p[0])
        d.append(((x1 + NEAR, a), pa, pb, 90))
    return [x for x in d if abs((x[2][0]-x[1][0]) if x[3] == 0 else (x[2][1]-x[1][1])) > TOL]

def main():
    a = argparse.ArgumentParser()
    a.add_argument('file'); a.add_argument('name'); a.add_argument('--profile', default='israeli-structural')
    a.add_argument('--full', action='store_true', help='also dimension variable slab lengths / overall width / duplicate left overall'); a.add_argument('-o'); a.add_argument('--near', nargs=2, type=float, help='X Y: pick the title near this point when the same number occurs twice'); a.add_argument('--dry', action='store_true'); a.add_argument('--png')
    a = a.parse_args(); use_profile(a.profile)
    doc = ezdxf.readfile(a.file); msp = doc.modelspace()
    title = find_title(msp, a.name, a.near)
    pts = outline_points(msp, title)
    dims = plan(pts, [] if a.full else break_xs(msp, title))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    print(f'section {a.name}: {max(xs)-min(xs):.1f} x {max(ys)-min(ys):.1f} cm, {len(dims)} dims')
    for base, p1, p2, ang in dims:
        print(f'  {"horiz" if ang == 0 else "vert "} {abs((p2[0]-p1[0]) if ang == 0 else (p2[1]-p1[1])):.1f}')
    if a.dry: return
    for base, p1, p2, ang in dims:
        msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=ang, dimstyle=DIMSTYLE, override=OVERRIDE,
                           dxfattribs={'layer': DIMLAYER}).render()
    out = a.o or a.file                       # default: update the ORIGINAL in place (user's rule)
    if out == a.file:
        backup(a.file, 'dim-' + a.name)   # FILE.bak + timestamped snapshot (learn_diff compares against it)
    doc.saveas(out); print('saved', out)
    if a.png:
        render_png(doc, (min(xs) - 70, max(xs) + 70, min(ys) - 60, max(ys) + 50), a.png); print('png', a.png)

main()
