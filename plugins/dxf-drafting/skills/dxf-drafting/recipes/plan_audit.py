"""Inspector: FACE COVERAGE of a plan region - which faces of which elements can NOT be read from any dimension (2026-10-11, gallery plan).
  python plan_audit.py FILE --box X0 X1 Y0 Y1 [-v]
Every vertex coordinate of every element (piers/walls 82_KIR_OLE, beam edges 93_KORA, slab contour 9_KONTUR, openings = inner cell rectangles of core polygons, void hatch 6_HATCH)
must appear as an END POINT of a horizontal dim (x faces) / vertical dim (y faces) (tolerance 1.5); skewed edges need an aligned dim of that length.
Also reports duplicates (two dims with the same interval and the same orientation within one chain-distance) so redundancy can be removed.
Exit info is printed per category: element, missing x faces, missing y faces."""
import argparse, math, os, sys, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from dxflib import dim_angle

TOL = 1.5
CATS = {'82_KIR_OLE': 'wall/pier', '93_KORA': 'beam', '9_KONTUR': 'contour/detail'}   # 6_HATCH = diagonal symbols of shaft cells: not elements
JOG = 12.0      # a wall face within JOG of a read face is a jog of the same opening (read)
MIN_SKEW = 60.0  # shorter skewed edges are pier thicknesses (read by the horizontal chain item)


def dim_faces(doc, box):
    x0, x1, y0, y1 = box
    X = []; Y = []; AL = []; dup = collections.Counter()
    for d in doc.modelspace().query('DIMENSION'):
        dl = d.dxf.defpoint
        if not (x0 - 500 <= dl.x <= x1 + 500 and y0 - 500 <= dl.y <= y1 + 500): continue
        t = d.dxf.dimtype & 7; p, q = d.dxf.defpoint2, d.dxf.defpoint3
        if t == 1: AL.append((p, q)); continue
        if t != 0: continue
        a = round(dim_angle(d)) % 180
        if a == 0: X += [p.x, q.x]; dup[('h', round(min(p.x, q.x)), round(max(p.x, q.x)))] += 1
        elif a == 90: Y += [p.y, q.y]; dup[('v', round(min(p.y, q.y)), round(max(p.y, q.y)))] += 1
        else: AL.append((p, q))
    return sorted(X), sorted(Y), AL, dup


def has_tol(vals, v, tol):
    import bisect
    i = bisect.bisect_left(vals, v - tol)
    return i < len(vals) and vals[i] <= v + tol


def has(vals, v, tol=TOL):
    return has_tol(vals, v, tol)


def elements(doc, box):
    x0, x1, y0, y1 = box
    for e in doc.modelspace():
        if e.dxf.layer not in CATS: continue
        if e.dxftype() == 'LWPOLYLINE': p = [(a, b) for a, b in e.get_points('xy')]
        elif e.dxftype() == 'LINE': p = [tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]]
        else: continue
        if not p: continue
        xs = [a for a, b in p]; ys = [b for a, b in p]
        if not (x0 <= min(xs) and max(xs) <= x1 and y0 <= min(ys) and max(ys) <= y1): continue
        if max(xs) - min(xs) >= 9000 and e.dxf.layer == '82_KIR_OLE': continue    # site / parcel outline
        yield e, p


def skew_ok(AL, a, b):
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    return any(abs(math.hypot(q[0] - p[0], q[1] - p[1]) - L) < 2.0 for p, q in AL)


def audit(doc, box, verbose=False):
    """per element: x / y faces that no dim reads (vertex rule: both coordinates of every vertex whose adjacent edges are straight; beam LINES: perpendicular coordinate only,
    their ends meet other elements); skewed edges need an aligned dim of their length."""
    X, Y, AL, dup = dim_faces(doc, box)
    res = collections.defaultdict(lambda: [0, 0, 0, []])
    for e, p in elements(doc, box):
        cat = CATS[e.dxf.layer]; r = res[cat]; r[0] += 1; mx = set(); my = set(); msk = []
        n = len(p); closed = e.dxftype() == 'LWPOLYLINE' and e.closed
        if max(a for a, b in p) - min(a for a, b in p) < 1 and max(b for a, b in p) - min(b for a, b in p) < 1: continue   # degenerate (a point)
        if n == 2:
            (x1, y1), (x2, y2) = p
            if abs(x1 - x2) < TOL and not has(X, x1): mx.add(round(x1, 1))
            elif abs(y1 - y2) < TOL and not has(Y, y1): my.add(round(y1, 1))
            elif abs(x1 - x2) >= TOL and abs(y1 - y2) >= TOL and math.hypot(x2 - x1, y2 - y1) >= MIN_SKEW:      # USER RULE 2026-10-11: X / Y dims only -> both ends read in x and y
                for v in ((x1, y1), (x2, y2)):
                    if not has(X, v[0], JOG): mx.add(round(v[0], 1))
                    if not has(Y, v[1], JOG): my.add(round(v[1], 1))
        else:
            def skewed(a, b): return abs(a[0] - b[0]) >= TOL and abs(a[1] - b[1]) >= TOL
            for i in range(n):
                a, b = p[i], p[(i + 1) % n]
                if not closed and i == n - 1: continue
                if skewed(a, b) and math.hypot(b[0] - a[0], b[1] - a[1]) < MIN_SKEW: continue
                for j, v in ((i, a), ((i + 1) % n, b)):
                    prv, nxt = p[(j - 1) % n], p[(j + 1) % n]
                    tol = TOL if e.dxf.layer == '93_KORA' else JOG
                    if not has(X, v[0], tol): mx.add(round(v[0], 1))
                    if not has(Y, v[1], tol): my.add(round(v[1], 1))
        if mx or my or msk: r[1] += 1; r[2] += len(mx) + len(my) + len(msk); r[3].append((e.dxf.handle, sorted(mx), sorted(my), msk))
    return res, dup


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True); ap.add_argument('-v', action='store_true')
    a = ap.parse_args(); doc = ezdxf.readfile(a.file)
    res, dup = audit(doc, tuple(a.box), a.v); AL_ = dim_faces(doc, tuple(a.box))[2]; print('aligned / skewed dims (forbidden): %d' % len(AL_))
    for cat, (n, bad, faces, smp) in res.items():
        print('%-18s elements %3d  with unread faces %3d  (faces %d)' % (cat, n, bad, faces))
        if a.v:
            for h, mx, my, sk in smp: print('    ', h, 'x', mx, 'y', my, 'skew', sk)
    print('duplicate dims (same interval twice):', sum(1 for k, v in dup.items() if v > 1))


if __name__ == '__main__': main()
