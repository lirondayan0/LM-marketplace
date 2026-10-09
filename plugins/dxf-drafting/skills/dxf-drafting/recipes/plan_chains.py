"""Recipe: continuous dimension CHAINS (X rows and Y columns) along the piers/walls of a plan (user red-cloud examples in ramla_base.dxf, 2026-10-07).
  python plan_chains.py FILE [--axis x|y|both] [--dry] [-v] [-o OUT] [--force-existing]
Rules (user examples; see conventions/section-drawings.md, Plan dimensions):
 - ROW (X dims): ONE horizontal chain per pier row, dim line 101.09 below the piers bottom edge. COLUMN (Y dims): one vertical chain per pier column, dim line 50 right of the right faces.
   Layer 36_MIDA_CLALI, style dim_100. Chain = every element width + every clear span between neighbours, no overall dim.
 - Elements = axis-aligned small rects of 82_KIR_OLE (pier / wall leg, min side <=45, max <=210; ext lines to their near edge), walls the line crosses (slices of the
   82_KIR_OLE polygons at the line and just inside the piers) and thin STRIPS (15..45) between faces of different polygons (a wall drawn with two lines: user 30 / 35 walls).
   Spans have no ext lines (points on the line).
 - Ends: innermost face of the building outline (polygon spanning >= BIG); the outline strip is dimensioned only when the next outline face is 15..45 further out.
 - Piers are clustered by near edge; the biggest cluster is the anchor; piers within [-100, +260] of it join that chain. A line that already carries >= 3 dims is skipped (user own).
 - Rotated piers (east slanted part) are NOT chained along X/Y: listed in the report.
UNVERIFIED: wall coverage away from the chain lines, offsets (1 example each), end handling."""
import argparse, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from dxflib import *

LAYER = '36_MIDA_CLALI'; STYLE = 'dim_100'; SRC = '82_KIR_OLE'; BIG = 9000.0
OFF = {'x': 101.09, 'y': 50.0}; SLICE2 = {'x': 105.0, 'y': 55.0}; BAND = (-100.0, 260.0)


def load(doc):
    out = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != SRC: continue
        p = [(q[0], q[1]) for q in e.get_points()]
        xs = [a for a, b in p]; ys = [b for a, b in p]
        out.append(dict(h=e.dxf.handle, p=p, closed=e.closed, x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys)))
    return out


def to_uv(P, axis):   # rows: (x,y); columns: (y,-x) -> chain runs along u, piers sit on the +v side of the line
    return [(x, y) if axis == 'x' else (y, -x) for x, y in P]


def cross(p, closed, v):
    n = len(p); us = []
    for i in range(n if closed else n - 1):
        (u1, v1), (u2, v2) = p[i], p[(i + 1) % n]
        if (v1 - v) * (v2 - v) < 0: us.append(u1 + (u2 - u1) * (v - v1) / (v2 - v1))
    us.sort()
    return [(us[i], us[i + 1]) for i in range(0, len(us) - 1, 2)]


def prep(polys, axis):
    out = []
    for q in polys:
        p = to_uv(q['p'], axis); us = [a for a, b in p]; vs = [b for a, b in p]
        d = dict(q, p=p, u0=min(us), u1=max(us), v0=min(vs), v1=max(vs))
        d['rect'] = len(q['p']) == 4 and q['closed'] and all(abs(a - d['u0']) < .6 or abs(a - d['u1']) < .6 for a in us) and all(abs(b - d['v0']) < .6 or abs(b - d['v1']) < .6 for b in vs)
        w, h = d['u1'] - d['u0'], d['v1'] - d['v0']
        d['pier'] = d['rect'] and min(w, h) <= 45 and max(w, h) <= 210
        d['big'] = max(w, h) >= BIG
        d['rot'] = (not d['rect']) and len(q['p']) <= 5 and max(w, h) <= 260 and min(w, h) <= 100
        out.append(d)
    return out


def clusters(vals, tol=5.0):
    cs = []
    for v in sorted(vals):
        if cs and v - cs[-1][-1] <= tol: cs[-1].append(v)
        else: cs.append([v])
    return cs


def chain_for(P, anchor, axis, assigned=()):
    """P: prepped polys, anchor = near-edge v of the pier cluster -> (line v, [(a, b, ext_v|None)], member piers)"""
    lv = anchor - OFF[axis]
    piers = [q for q in P if q['pier'] and id(q) not in assigned and anchor + BAND[0] <= q['v0'] <= anchor + BAND[1]]
    crossing = [q for q in P if q['pier'] and id(q) not in assigned and q['v0'] < lv < q['v1']]   # a pier the line passes through = an item on the line
    items = [(q['u0'], q['u1'], q['v0'], 'pier') for q in piers]
    mem_ids = {id(q) for q in piers}
    faces = []; outl = []
    for q in P:
        if q['v0'] > lv + SLICE2[axis] or q['v1'] < lv: continue
        for k, vv in enumerate((lv, lv + SLICE2[axis])):
            if vv < q['v0'] or vv > q['v1']: continue
            for a, b in cross(q['p'], q['closed'], vv):
                if q['big']:
                    if k == 0: outl.append((a, b, q['h']))
                elif q['pier'] and id(q) in mem_ids: continue   # member piers come from their bbox
                elif b - a < 400: items.append((a, b, None, 'wall'))
                elif k == 0: faces += [(a, q['h']), (b, q['h'])]
    items.sort(key=lambda t: (t[0], t[1])); merged = []
    for a, b, e, k in items:
        if merged and a <= merged[-1][1] + 1.5:
            m = merged[-1]; m[1] = max(m[1], b); m[2] = m[2] if m[2] is not None else e
        else: merged.append([a, b, e, k])
    if not merged: return lv, [], piers
    lo, hi = merged[0][0], merged[-1][1]
    lows = sorted(a for a, b, h in outl); highs = sorted(b for a, b, h in outl)
    lo_f = [f for f in lows if f < lo - 1]; hi_f = [f for f in highs if f > hi + 1]
    inner_s = max(lo_f) if lo_f else None; start = inner_s
    if start is not None:
        more = sorted([f for f in lo_f if f < start - 1], reverse=True)
        if more and 15 <= start - more[0] <= 45: start = more[0]
    inner_e = min(hi_f) if hi_f else None; end = inner_e
    if end is not None:
        more = sorted([f for f in hi_f if f > end + 1])
        if more and 15 <= more[0] - end <= 45: end = more[0]
    fs = sorted(faces + ([(inner_s, 'o')] if inner_s is not None else []) + ([(inner_e, 'o')] if inner_e is not None else []))
    for (f1, h1), (f2, h2) in zip(fs, fs[1:]):
        if h1 != h2 and 15 <= f2 - f1 <= 45 and (inner_s is None or f1 >= inner_s - 1) and (inner_e is None or f2 <= inner_e + 1):
            if not any(m[0] < f2 - 1 and m[1] > f1 + 1 for m in merged): merged.append([f1, f2, None, 'wall'])
    merged.sort(key=lambda t: (t[0], t[1]))
    seq = [(m[0], m[1], m[2]) for m in merged]; out = []
    if inner_s is not None:
        if start < inner_s - 1: out.append((start, inner_s, None))
        out.append((inner_s, seq[0][0], None))
    for i, s in enumerate(seq):
        out.append(s)
        if i + 1 < len(seq) and seq[i + 1][0] - s[1] > 1: out.append((s[1], seq[i + 1][0], None))
    if inner_e is not None:
        out.append((seq[-1][1], inner_e, None))
        if end > inner_e + 1: out.append((inner_e, end, None))
    return lv, [o for o in out if o[1] - o[0] > 1], piers + crossing


def plan(doc, axis):
    P = prep(load(doc), axis)
    piers = [q for q in P if q['pier']]; assigned = set(); res = []
    for c in sorted(clusters([q['v0'] for q in piers]), key=lambda c: (-len(c), c[0])):
        anchor = sum(c) / len(c)
        if all(id(q) in assigned for q in piers if abs(q['v0'] - anchor) <= 5): continue
        lv, items, mem = chain_for(P, anchor, axis, assigned)
        for q in mem: assigned.add(id(q))
        res.append((anchor, lv, items, len(mem)))
    return res, [q for q in P if q['rot']]


def existing(doc, axis, lv):
    n = 0
    for d in doc.modelspace().query('DIMENSION'):
        a = dim_angle(d) % 180
        if axis == 'x' and abs(a) < 1 and abs(d.dxf.defpoint.y - lv) < 3: n += 1
        if axis == 'y' and abs(a - 90) < 1 and abs(d.dxf.defpoint.x + lv) < 3: n += 1
    return n


def add_dims(doc, axis, lv, items):
    ms = doc.modelspace()
    for a, b, ev in items:
        e = ev if ev is not None else lv
        if axis == 'x':
            ms.add_linear_dim(base=(a, lv), p1=(a, e), p2=(b, e), angle=0, dimstyle=STYLE, dxfattribs={'layer': LAYER}).render()
        else:   # u = y, v = -x
            ms.add_linear_dim(base=(-lv, a), p1=(-e, a), p2=(-e, b), angle=90, dimstyle=STYLE, dxfattribs={'layer': LAYER}).render()
    return len(items)


def run(doc, axes=('x', 'y'), dry=False, force=False, verbose=False):
    rep = []
    for axis in axes:
        res, rot = plan(doc, axis)
        for anchor, lv, items, nm in res:
            ex = existing(doc, axis, lv); skip = ex >= 3 and not force
            rep.append((axis, round(anchor, 1), round(lv, 1), nm, len(items), ex, 'SKIP(existing)' if skip else 'new'))
            if verbose: print(axis, round(lv, 1), [(round(a), round(b - a)) for a, b, e in items])
            if not skip and not dry: add_dims(doc, axis, lv, items)
        rep.append((axis, 'rotated piers not chained', len(rot)))
    return rep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--axis', default='both'); ap.add_argument('--dry', action='store_true'); ap.add_argument('-o')
    ap.add_argument('--force-existing', action='store_true'); ap.add_argument('-v', action='store_true')
    a = ap.parse_args(); doc = ezdxf.readfile(a.file)
    rep = run(doc, ('x', 'y') if a.axis == 'both' else (a.axis,), a.dry, a.force_existing, a.v)
    for r in rep: print(r)
    if a.dry: return
    out = a.o or a.file
    if not a.o: backup(a.file, 'chains')
    doc.saveas(out); print('saved', out)


if __name__ == '__main__': main()
