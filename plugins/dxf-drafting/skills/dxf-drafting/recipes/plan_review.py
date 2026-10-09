"""Recipe: REVIEW a dimension plan like a site inspector and ADD what a worker still lacks, IN PLACE (ramla_base-dimplan.dxf, 2026-10-08). Never deletes, never touches existing dims.
  python plan_review.py FILE [--expect SNAPSHOT] [--dry] [-v]
Coverage test (an element is "dimensioned" when every size of it can be read on the plan): a horizontal / vertical edge needs a chain of linear dims (one collinear dim line) connecting its two faces,
a skewed edge needs an aligned dim on it (opposite edges of a parallelogram count as one). Elements inside a pit block (frame on 93_KORA) are covered by the block face chains; the big building outline, circles
(drains, no diameter dims by the user's red cloud) and annotation frames are not site elements.
Adds, in this order (every new dim readable = text never upside-down, dim lines kept out of other dims/texts by the obstacle map of plan_elements):
 1 single skewed piers outside a row (104E): length + thickness. Rows / columns of skewed piers are done by plan_continuity.py (continuous chain), NOT here.
 2 (removed: pitch dims; superseded by the row chains).
 3 SKEWED ROOMS / TANKS (closed 82_KIR_OLE or 15_DASHED quadrilaterals longer than 1100): clear length + clear width as aligned dims inside the room, wall thickness on every side (measured to the nearest parallel wall line).
 5 OPENINGS between wall pieces inside pit blocks (gap between collinear wall edges, no dim yet): the gap is dimensioned on the EXISTING chain line next to it (touching chain preferred, line must be free over the gap), jog pairs once.
 4 every other small element with an undimensioned edge (pentagons, orphan rectangles, dashed hidden RECTANGLES; other dashed outlines repeat a wall polygon): the missing edges, rectangles as W below / H right, skewed edges aligned. Dashed duplicates of a wall outline are skipped.
`--box X0 Y0 X1 Y1` limits everything to one plan when the file holds several.
Writes into FILE after a timestamped snapshot. --expect = copy of the file as last read: abort when FILE differs."""
import argparse, filecmp, math, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from dxflib import *
import plan_elements as pe, plan_tidy as pt, plan_revise as pr

DASHED = '15_DASHED'; TANK_MIN = 1100.0; BOX = None


def pt_seg(p, a, b):
    L2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / L2))
    return math.hypot(p[0] - (a[0] + t * (b[0] - a[0])), p[1] - (a[1] + t * (b[1] - a[1])))


class Cover:
    """which sizes can the worker read? collinear dim lines -> connected faces"""
    def __init__(self, doc):
        self.g = collections.defaultdict(list); self.al = []; self.items = collections.defaultdict(list)
        for d in doc.modelspace().query('DIMENSION'):
            t = d.dxf.dimtype & 7; p, q, dl = d.dxf.defpoint2, d.dxf.defpoint3, d.dxf.defpoint
            if t == 1: self.al.append((p, q)); continue
            if t != 0: continue
            a = round(dim_angle(d)) % 180
            if a == 0: self.g[('h', round(dl.y / 3))].append((min(p.x, q.x), max(p.x, q.x))); self.items[('h', round(dl.y / 3))].append((min(p.x, q.x), max(p.x, q.x), p.y))
            elif a == 90: self.g[('v', round(dl.x / 3))].append((min(p.y, q.y), max(p.y, q.y))); self.items[('v', round(dl.x / 3))].append((min(p.y, q.y), max(p.y, q.y), p.x))
            else: self.al.append((p, q))

    def lin(self, kind, lo, hi, tol=2.0):
        for (k, _), iv in self.g.items():
            if k != kind: continue
            pts = sorted({v for ab in iv for v in ab}); par = {v: v for v in pts}
            def f(x):
                while par[x] != x: par[x] = par[par[x]]; x = par[x]
                return x
            for a, b in iv: par[f(a)] = f(b)
            A = [v for v in pts if abs(v - lo) <= tol]; B = [v for v in pts if abs(v - hi) <= tol]
            if any(f(a) == f(b) for a in A for b in B): return True
        return False

    def aligned(self, a, b, tol=2.5):
        return any((pe.dist((p.x, p.y), a) < tol and pe.dist((q.x, q.y), b) < tol) or (pe.dist((p.x, p.y), b) < tol and pe.dist((q.x, q.y), a) < tol) for p, q in self.al)

    def axis_dup(self, a, b, poly):
        """a skewed edge a-b whose length a chain item (horizontal / vertical dim between two faces of the same polygon) already gives = covered (no duplicate)"""
        m = pe.dist(a, b)
        for (k, _), iv in self.items.items():
            for lo, hi, ref in iv:
                if abs((hi - lo) - m) > max(1.2, 0.006 * m): continue
                pa, pb = ((lo, ref), (hi, ref)) if k == 'h' else ((ref, lo), (ref, hi))
                if all(min(pe.dist(pp, v) for v in poly) < 1e9 and any(pt_seg(pp, poly[i], poly[(i + 1) % len(poly)]) <= 3.0 for i in range(len(poly))) for pp in (pa, pb)): return True
        return False

    def edge(self, a, b):
        if abs(a[1] - b[1]) < 0.5: return self.lin('h', min(a[0], b[0]), max(a[0], b[0]))
        if abs(a[0] - b[0]) < 0.5: return self.lin('v', min(a[1], b[1]), max(a[1], b[1]))
        return self.aligned(a, b)


def in_block(q, blocks):
    cx, cy = (q['box'][0] + q['box'][2]) / 2, (q['box'][1] + q['box'][3]) / 2
    return any(x0 <= cx <= x1 and y0 <= cy <= y1 for h, x0, y0, x1, y1 in blocks)


def elements(doc, blocks):
    """small closed outlines to check: walls + dashed hidden ones; dashed duplicates of a wall outline dropped, block members dropped"""
    polys, big, circ = pe.inventory(doc); res = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer == DASHED and e.closed:
            p = pe.pts(e); b = pe.bb(p)
            if max(b[2] - b[0], b[3] - b[1]) < pe.BIG and (BOX is None or (b[0] >= BOX[0] and b[2] <= BOX[2] and b[1] >= BOX[1] and b[3] <= BOX[3])): polys.append(dict(h=e.dxf.handle, layer=DASHED, p=p, box=b, w=b[2] - b[0], hgt=b[3] - b[1]))
    walls = [q for q in polys if q['layer'] == pe.WALL]
    for q in polys:
        if q['layer'] not in (pe.WALL, DASHED) or in_block(q, blocks) or len(q['p']) > 12: continue
        if q['layer'] == DASHED and not pe.is_rect(q['p']): continue          # hidden outlines that are not rectangles repeat the wall polygon above them (ghost of a pit / tank): not dimensioned twice
        if q['layer'] == DASHED and any(all(abs(a - b) < 3 for a, b in zip(q['box'], w['box'])) for w in walls): continue
        res.append(q)
    return res


def segments(doc):
    sg = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != pe.WALL: continue
        p = pe.pts(e); n = len(p)
        for i in range(n if e.closed else n - 1):
            a, b = p[i], p[(i + 1) % n]
            if pe.dist(a, b) > 20: sg.append((a, b, e.dxf.handle))
    return sg


def wall_behind(sg, a, b, nx, ny, me):
    """nearest parallel wall segment beyond edge a-b (outward normal n): (distance, foot of the perpendicular from the edge midpoint) or None"""
    L = pe.dist(a, b); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L; mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2; best = None
    for s, t, h in sg:
        if h == me: continue
        ls = pe.dist(s, t); sx, sy = (t[0] - s[0]) / ls, (t[1] - s[1]) / ls
        if abs(sx * uy - sy * ux) > 0.03: continue                       # parallel within ~1.7 deg
        d = (s[0] - mx) * nx + (s[1] - my) * ny
        if not 8 <= d <= 150: continue
        k = ((mx - s[0]) * sx + (my - s[1]) * sy)
        if not -2 <= k <= ls + 2: continue
        if best is None or d < best[0]: best = (d, (mx + nx * d, my + ny * d))
    return best


def free_side(out, a, b, offs, sides):
    for o in offs:
        for sgn in sides:
            nx, ny = -(b[1] - a[1]) / pe.dist(a, b), (b[0] - a[0]) / pe.dist(a, b)
            if out.free((a[0] + nx * sgn * o, a[1] + ny * sgn * o), (b[0] + nx * sgn * o, b[1] + ny * sgn * o)): return o * sgn
    return None


def do_piers(doc, out, cov, rep):
    polys, big, circ = pe.inventory(doc)
    quads = [q for q in polys if q['layer'] == pe.WALL and len(q['p']) == 4 and not pe.is_rect(q['p']) and (round(q['w'] / 15), round(q['hgt'] / 15)) in pr.FAMILIES + ((8, 13),)]
    for q in sorted(quads, key=lambda q: (round(q['w']), q['box'][1])):
        if (round(q['w'] / 15), round(q['hgt'] / 15)) != (8, 13): continue      # piers of a row / column are dimensioned by the continuous row chain (plan_continuity.py), their thickness by the chain items
        (la, lb), (ta, tb) = pr.edges_of(q)
        chk = (round(q['w'] / 15), round(q['hgt'] / 15)) == (8, 13)
        if chk:
            p4 = q['p']; es4 = [(p4[i], p4[(i + 1) % 4]) for i in range(4)]; sh = sorted(es4, key=lambda e: pe.dist(*e))[:2]
            ta, tb = max(sh, key=lambda e: (e[0][1] + e[1][1]) / 2)
        for (ea, eb), want, off, nm in (((la, lb), (-1.0, 0.0), pr.LEN_OFF, 'length'), ((ta, tb), (0.0, 1.0) if chk else (0.0, -1.0), pr.THK_OFF, 'thickness')):
            if pr.has_dim_on(doc, ea, eb): continue
            o = pr.place_size(out, ea, eb, want, (off, 110.0, 140.0, 170.0) if chk else (off,), chk); rep.append(('pier size', q['h'], nm, round(pe.dist(ea, eb), 1), round(o)))
    return quads


def rows(g, link=1000.0):
    """piers of one family -> rows: single-link clusters of their lowest corners (< link apart), each ordered along its long direction"""
    cs = [min(q['p'], key=lambda t: (t[1], t[0])) for q in g]; seen = set(); out = []
    for i in range(len(g)):
        if i in seen: continue
        comp = [i]; seen.add(i); k = 0
        while k < len(comp):
            for j in range(len(g)):
                if j not in seen and pe.dist(cs[comp[k]], cs[j]) < link: seen.add(j); comp.append(j)
            k += 1
        xs = [cs[c][0] for c in comp]; ys = [cs[c][1] for c in comp]
        key = (lambda c: cs[c][0]) if max(xs) - min(xs) >= max(ys) - min(ys) else (lambda c: cs[c][1])
        out.append([cs[c] for c in sorted(comp, key=key)])
    return out


def has_gap_dim(doc, a, b, own):
    """a skewed dim longer than the pier sizes that lies between the two corners = the clear gap is already given (pitch = gap + pier length)"""
    x0, x1 = min(a[0], b[0]) - 150, max(a[0], b[0]) + 150; y0, y1 = min(a[1], b[1]) - 150, max(a[1], b[1]) + 150
    for d in doc.modelspace().query('DIMENSION'):
        if d.dxf.dimtype & 7 not in (0, 1) or pt.axis_of(d) != 'd' or d.get_measurement() < 100 or any(abs(d.get_measurement() - pe.dist(q0['p'][i], q0['p'][(i + 1) % 4])) < 2 for q0 in own for i in range(4)): continue
        p, q = d.dxf.defpoint2, d.dxf.defpoint3
        if all(x0 <= u.x <= x1 and y0 <= u.y <= y1 for u in (p, q)): return True
    return False


def do_pitch(doc, out, quads, rep):
    groups = {}
    allq = [q for q in pe.inventory(doc)[0] if q['layer'] == pe.WALL and len(q['p']) == 4 and not pe.is_rect(q['p']) and max(q['w'], q['hgt']) < 400]
    for q in allq: groups.setdefault((round(q['w'] / 15), round(q['hgt'] / 15)), []).append(q)
    for key, g in groups.items():
        pairs = []
        for row in rows(g):
            if len(row) < 3: continue
            pairs += [(a, b) for a, b in zip(row, row[1:]) if pe.dist(a, b) >= 100 and not pr.has_dim_on(doc, a, b) and not has_gap_dim(doc, a, b, g)]
        if not pairs: continue
        best = None
        for sgn in (1, -1):
            for o in (120, 160, 200, 240, 280, 320, 360):
                if all(out.free((a[0] + sgn * -(b[1] - a[1]) / pe.dist(a, b) * o, a[1] + sgn * (b[0] - a[0]) / pe.dist(a, b) * o), (b[0] + sgn * -(b[1] - a[1]) / pe.dist(a, b) * o, b[1] + sgn * (b[0] - a[0]) / pe.dist(a, b) * o)) for a, b in pairs):
                    if best is None or o < best[0]: best = (o, sgn)
                    break
        if best is None: best = (120, 1); out.log.append(('pitch', 'FORCED', key))
        o, sgn = best
        for a, b in pairs: out.aligned(a, b, o * sgn, 'pitch'); rep.append(('pitch', round(pe.dist(a, b), 1)))


def do_tank(out, q, sg, rep):
    p = q['p']; n = len(p); cx = sum(a for a, b in p) / n; cy = sum(b for a, b in p) / n
    es = [(p[i], p[(i + 1) % n]) for i in range(n)]
    long_ = max(es, key=lambda e: pe.dist(*e)); short = max((e for e in es if abs(pe.dist(*e) - pe.dist(*long_)) > 5 and pe.dist(*e) < pe.dist(*long_) - 5), key=lambda e: pe.dist(*e), default=None)
    for e, nm in ((long_, 'clear length'), (short, 'clear width')):
        if e is None: continue
        a, b = e; L = pe.dist(a, b); nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        inward = 1 if ((cx - (a[0] + b[0]) / 2) * nx + (cy - (a[1] + b[1]) / 2) * ny) > 0 else -1
        o = free_side(out, a, b, (60, 90, 120, 150, 190, 230), (inward, -inward))
        if o is None: o = 60 * inward; out.log.append((q['h'], 'FORCED', nm))
        out.aligned(a, b, o, 'tank ' + nm); rep.append(('tank', q['h'], nm, round(L, 1), round(o)))
    for a, b in es:                                                      # wall thickness behind every side
        L = pe.dist(a, b); nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        if ((a[0] + b[0]) / 2 - cx) * nx + ((a[1] + b[1]) / 2 - cy) * ny < 0: nx, ny = -nx, -ny              # outward
        w = wall_behind(sg, a, b, nx, ny, None)
        if not w: rep.append(('tank wall NOT found', q['h'], round(L))); continue
        d, foot = w; m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        for k in (0, 1, 2, 3, 4, 5):                                       # slide along the wall until the dim is free
            for sgn in (1, -1):
                s = sgn * k * 60.0; a2 = (m[0] + ux * s, m[1] + uy * s); b2 = (foot[0] + ux * s, foot[1] + uy * s)
                if out.free(a2, b2):
                    out.aligned(a2, b2, 45.0, 'tank wall'); rep.append(('tank wall', q['h'], round(d, 1))); break
            else: continue
            break
        else: out.aligned(m, foot, 45.0, 'tank wall'); rep.append(('tank wall (forced)', q['h'], round(d, 1)))


def do_missing(doc, out, cov, els, done_h, rep):
    for q in els:
        if q['h'] in done_h: continue
        p = q['p']; n = len(p)
        if pe.is_rect(p):
            x0, y0, x1, y1 = q['box']
            thin = q['layer'] == DASHED and min(x1 - x0, y1 - y0) <= 50      # user deleted the 40 on the thin hidden rect F43: a thin hidden line is not dimensioned across
            if not cov.lin('h', x0, x1) and not (thin and x1 - x0 <= 50):
                yl = y0 - 60
                for k in range(8):
                    if out.free((x0, yl), (x1, yl)): break
                    yl -= 50
                out.lin((x0, y0), (x1, y0), (x0, yl), 0); out.stripes.add((x0, yl), (x1, yl)); rep.append(('rect W', q['h'], round(x1 - x0, 1)))
            if not cov.lin('v', y0, y1) and not (thin and y1 - y0 <= 50):
                xl = x1 + 60
                for k in range(8):
                    if out.free((xl, y0), (xl, y1)): break
                    xl += 50
                out.lin((x1, y0), (x1, y1), (xl, y0), 90); out.stripes.add((xl, y0), (xl, y1)); rep.append(('rect H', q['h'], round(y1 - y0, 1)))
            continue
        for a, b, nx, ny in pe.poly_edges(p):
            if cov.edge(a, b) or cov.axis_dup(a, b, p) or (n == 4 and any(cov.edge(c, d) for c, d in [(p[k], p[(k + 1) % 4]) for k in range(4)] if abs(pe.dist(c, d) - pe.dist(a, b)) < 3)): continue
            L = pe.dist(a, b)
            if abs(a[1] - b[1]) < 0.5 or abs(a[0] - b[0]) < 0.5:       # axis edge: linear dim on the outer side
                hor = abs(a[1] - b[1]) < 0.5
                for o in pe.OFFSETS:
                    la = (a[0] + nx * o, a[1] + ny * o); lb = (b[0] + nx * o, b[1] + ny * o)
                    if out.free(la, lb): break
                else: o = pe.OFFSETS[1]
                if hor: out.lin((min(a[0], b[0]), a[1]), (max(a[0], b[0]), a[1]), (min(a[0], b[0]), a[1] + ny * o), 0)
                else: out.lin((a[0], min(a[1], b[1])), (a[0], max(a[1], b[1])), (a[0] + nx * o, min(a[1], b[1])), 90)
                out.stripes.add((a[0] + nx * o, a[1] + ny * o), (b[0] + nx * o, b[1] + ny * o)); rep.append(('edge', q['h'], round(L, 1), round(o)))
            else:
                left = (-(b[1] - a[1]) / L, (b[0] - a[0]) / L); sgn = 1 if left[0] * nx + left[1] * ny > 0 else -1
                o = pe.free_offset(out, a, b, nx, ny)
                if o is None: o = pe.OFFSETS[1]; out.log.append((q['h'], 'FORCED', round(L)))
                out.aligned(a, b, o * sgn, 'edge'); rep.append(('edge', q['h'], round(L, 1), round(o * sgn)))


def opening_gaps(doc, blocks, polys):
    """gaps between collinear wall edges inside pit blocks (door / pass-through openings between wall pieces): [(kind, edge line, lo, hi)]; the jog pair of one opening (faces < 40 apart, same interval) counts once"""
    res = []
    for h, x0, y0, x1, y1 in blocks:
        mem = [q for q in polys if q['layer'] == pe.WALL and x0 <= (q['box'][0] + q['box'][2]) / 2 <= x1 and y0 <= (q['box'][1] + q['box'][3]) / 2 <= y1]
        E = {'h': collections.defaultdict(list), 'v': collections.defaultdict(list)}
        for q in mem:
            P = q['p']; n = len(P)
            for i in range(n):
                a, b = P[i], P[(i + 1) % n]
                if abs(a[1] - b[1]) < 0.5 and abs(a[0] - b[0]) > 3: E['h'][round(a[1])].append((min(a[0], b[0]), max(a[0], b[0])))
                if abs(a[0] - b[0]) < 0.5 and abs(a[1] - b[1]) > 3: E['v'][round(a[0])].append((min(a[1], b[1]), max(a[1], b[1])))
        for k in 'hv':
            for line, iv in sorted(E[k].items()):
                iv.sort(); cur = iv[0][1]
                for a, b in iv[1:]:
                    if a - cur > 2 and not any(r[0] == k and abs(r[2] - cur) < 2 and abs(r[3] - a) < 2 and abs(r[1] - line) < 40 for r in res): res.append((k, line, cur, a))
                    cur = max(cur, b)
    return res


def do_openings(doc, out, cov, rep):
    """an opening between wall pieces gets its dimension ON THE EXISTING dimension line of the neighbouring chain (user, 2026-10-08), not on a new line"""
    polys = pe.inventory(doc)[0]; blocks = pt.block_boxes(doc)[0]
    lines = collections.defaultdict(list)
    for d in doc.modelspace().query('DIMENSION'):
        if d.dxf.dimtype & 7 != 0: continue
        a = round(dim_angle(d)) % 180; p, q, dl = d.dxf.defpoint2, d.dxf.defpoint3, d.dxf.defpoint
        if a == 0: lines[('h', round(dl.y, 1))].append((min(p.x, q.x), max(p.x, q.x)))
        elif a == 90: lines[('v', round(dl.x, 1))].append((min(p.y, q.y), max(p.y, q.y)))
    for k, line, lo, hi in opening_gaps(doc, blocks, polys):
        if cov.lin(k, lo, hi): continue
        best = None
        for (kk, ln), iv in lines.items():
            if kk != k or abs(ln - line) > 150: continue
            if any(a < hi - 1 and b > lo + 1 for a, b in iv): continue                      # that line is busy over the opening
            touch = any(abs(b - lo) < 2 or abs(a - hi) < 2 or abs(a - lo) < 2 or abs(b - hi) < 2 for a, b in iv)   # the chain continues right here
            sc = (0 if touch else 1, abs(ln - line))
            if best is None or sc < best[0]: best = (sc, ln)
        if best is None:                                                  # no existing line is free here: a new line right beside the opening, away from the block centre
            cx = sum((b[1] + b[3]) / 2 if k == 'h' else (b[0] + b[2]) / 2 for b in [(x0, y0, x1, y1) for h, x0, y0, x1, y1 in blocks if (x0 - 5 <= lo <= x1 + 5 and y0 - 5 <= line <= y1 + 5) or (y0 - 5 <= lo <= y1 + 5 and x0 - 5 <= line <= x1 + 5)][:1]) or line
            for o in (60, 100, 140, 180):
                for sgn in ((1, -1) if line >= cx else (-1, 1)):
                    ln = line + sgn * o
                    if (out.free((lo, ln), (hi, ln)) if k == 'h' else out.free((ln, lo), (ln, hi))): best = (None, ln); break
                if best: break
        if best is None: rep.append(('opening NOT placed (no free dim line)', k, line, round(lo, 1), round(hi, 1))); continue
        ln = best[1]; nk = 0 if hi - lo < pe.NARROW else None
        if k == 'h': out.lin((lo, line), (hi, line), (lo, ln), 0, nk)
        else: out.lin((line, lo), (line, hi), (ln, lo), 90, nk)
        lines[(k, ln)].append((lo, hi)); out.stripes.add((lo, ln), (hi, ln)) if k == 'h' else out.stripes.add((ln, lo), (ln, hi)); rep.append(('opening', k, round(line), round(hi - lo, 1), 'on line', round(ln)))


def run(doc):
    blocks = pt.block_boxes(doc)[0]; cov = Cover(doc); out = pe.Out(doc); rep = []
    quads = do_piers(doc, out, cov, rep)
    cov = Cover(doc)                                                  # re-read: the piers / pitch are now covered
    els = elements(doc, blocks); pier_h = {q['h'] for q in quads}
    sg = segments(doc); done = set(pier_h)
    for q in els:
        if q['h'] in pier_h: continue
        if len(q['p']) == 4 and not pe.is_rect(q['p']) and max(q['w'], q['hgt']) > TANK_MIN:
            done.add(q['h'])
            if not cov.edge(*max(((q['p'][i], q['p'][(i + 1) % 4]) for i in range(4)), key=lambda e: pe.dist(*e))): do_tank(out, q, sg, rep)       # already dimensioned = skip (the recipe can be re-run)
    do_missing(doc, out, Cover(doc), els, done, rep)
    do_openings(doc, out, Cover(doc), rep)
    return out, rep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, metavar=('X0', 'Y0', 'X1', 'Y1'), help='only elements inside this box (the file may hold other plans, e.g. a pasted copy)'); ap.add_argument('--expect'); ap.add_argument('--dry', action='store_true'); ap.add_argument('-v', action='store_true')
    a = ap.parse_args()
    if a.expect and not filecmp.cmp(a.file, a.expect, shallow=False): sys.exit('ABORT: the file changed since it was last read (user saved?) - re-read it first')
    if a.box:
        inv0 = pe.inventory; bx = a.box
        def inside(b): return b[0] >= bx[0] and b[2] <= bx[2] and b[1] >= bx[1] and b[3] <= bx[3]
        def inv(doc):
            polys, big, circ = inv0(doc)
            return [q for q in polys if inside(q['box'])], [t for t in big if inside(t[1])], [c for c in circ if bx[0] <= c['c'][0] <= bx[2] and bx[1] <= c['c'][1] <= bx[3]]
        pe.inventory = inv; globals()['BOX'] = bx
    doc = ezdxf.readfile(a.file); n0 = len(doc.modelspace().query('DIMENSION'))
    out, rep = run(doc)
    for r in rep: print(r)
    for l in out.log: print('LOG', l)
    print('dimensions', n0, '->', len(doc.modelspace().query('DIMENSION')))
    if a.dry: print('dry run: nothing written'); return
    backup(a.file, 'review'); doc.saveas(a.file); print('saved in place', a.file)


if __name__ == '__main__': main()
