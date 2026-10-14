"""Recipe: DIMENSION PLAN as FULL-WIDTH LINES inside the plan (user corrections 2026-10-11, gallery plan of ramla_base-dimplan.dxf).
  python plan_lines.py FILE --box X0 X1 Y0 Y1 [--replace] [--dry] [-v] [--expect MTIME] [-o OUT]
User rules (all four are hard rules, see conventions/plan-dimensions.md 'FULL-WIDTH LINES'):
 1. Every dimension line is ONE continuous line from one side of the plan (slab contour, 9_KONTUR) to the other, no breaks: items = every face the line crosses.
 2. A line passing through a wall / pier / beam gives that element's dimension as an item; when the item sits on wall material its TEXT moves beside the wall (along the line,
    perpendicular 23), never on the hatch.
 3. All dimensions are INSIDE the plan (lines run through the slab; NO aligned dims (user 2026-10-11: dimensions only along X and Y; skewed elements get X and Y chains); no outer overall / outer chains).
 4. Concise: the FEWEST lines that make every face readable in X and Y (greedy set cover over all faces: walls, piers, beams, openings, void, contour), no duplicated items
    where avoidable (a coordinate read by one line is not chased by another), no dims < 10, jogs <= 12 are one opening.
Engineering reading (knowledge/structural-plan-reading.md): lines are chosen through pier bands / bay beams / core cells so that wall | clear | wall is read as the builder sets it out.
Skewed edges (>= 60): one aligned dim per edge family on the inner side."""
import argparse, math, os, sys, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
import plan_elements as pe
import plan_gallery as pg
import plan_continuity as pcn
from dxflib import backup

MIN_ITEM = 10.0; JOG = 12.0; BEAM_TOL = 1.5; MIN_SEG = 20.0; AVOID_EDGE = 3.0
STEP = 10.0; PERP = 23.0; GAP = 12.0; TEXT_H = 24.0; CHAR_W = 0.6; WALL_TEXT_MAX = 150.0; STAGGER = 45.0; NARROW = 45.0


def contour_of(doc, box):
    x0, x1, y0, y1 = box; best = None
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != '9_KONTUR' or not e.closed: continue
        p = pe.pts(e); b = pe.bb(p)
        if x0 <= b[0] and b[2] <= x1 and y0 <= b[1] and b[3] <= y1:
            if best is None or (b[2] - b[0]) * (b[3] - b[1]) > best[0]: best = ((b[2] - b[0]) * (b[3] - b[1]), p)
    return best[1] if best else None


def inside_any(areas, x, y):
    return any(inside(a, x, y) for a in areas)


def plan_areas(doc, box, cont):
    x0, x1, y0, y1 = box; areas = [cont]
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != '82_KIR_OLE' or not e.closed: continue
        p = pe.pts(e); b = pe.bb(p)
        if 500 < max(b[2] - b[0], b[3] - b[1]) < pg.pc.BIG and x0 <= b[0] and b[2] <= x1 and y0 <= b[1] and b[3] <= y1: areas.append(p)
    return areas


def inside(poly, x, y):
    c = False; n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]: c = not c
    return c


def void_segments(doc, box):
    """closed 4-point 6_HATCH rectangles inside the box = openings (double-height void): their edges are faces"""
    x0, x1, y0, y1 = box; V = []; H = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != '6_HATCH' or not e.closed or len(e) != 4: continue
        p = pe.pts(e); b = pe.bb(p)
        if not pe.is_rect(p) or not (x0 <= b[0] and b[2] <= x1 and y0 <= b[1] and b[3] <= y1): continue
        d = dict(h=e.dxf.handle, layer='6_HATCH', closed=True)
        V += [dict(d, c=b[0], lo=b[1], hi=b[3]), dict(d, c=b[2], lo=b[1], hi=b[3])]
        H += [dict(d, c=b[1], lo=b[0], hi=b[2]), dict(d, c=b[3], lo=b[0], hi=b[2])]
    return V, H


class Scan:
    """faces crossing a scan line. axis 'x': horizontal line y = v, faces are x coordinates; axis 'y': vertical line x = v, faces are y coordinates"""
    def __init__(self, uni, cont):
        V, H, S = uni; self.V, self.H, self.S, self.cont = V, H, S, cont
        self.cache = {}

    def crossings_cont(self, axis, v):
        out = []; n = len(self.cont)
        for i in range(n):
            a, b = self.cont[i], self.cont[(i + 1) % n]
            if axis == 'x':
                if (a[1] - v) * (b[1] - v) < 0 or (a[1] == v) != (b[1] == v) and False: out.append(a[0] + (b[0] - a[0]) * (v - a[1]) / (b[1] - a[1]))
            else:
                if (a[0] - v) * (b[0] - v) < 0: out.append(a[1] + (b[1] - a[1]) * (v - a[0]) / (b[0] - a[0]))
        return sorted(out)

    def faces(self, axis, v):
        key = (axis, round(v, 1))
        if key in self.cache: return self.cache[key]
        segs = self.V if axis == 'x' else self.H; fs = []
        for sg in segs:
            if sg['lo'] + 3 <= v <= sg['hi'] - 3 or (sg['layer'] == '9_KONTUR' and sg['lo'] - 1 <= v <= sg['hi'] + 1): fs.append(sg['c'])
        for sg in self.S:
            a, b = sg['a'], sg['b']
            if axis == 'x' and (a[1] - v) * (b[1] - v) < 0: fs.append(a[0] + (b[0] - a[0]) * (v - a[1]) / (b[1] - a[1]))
            if axis == 'y' and (a[0] - v) * (b[0] - v) < 0: fs.append(a[1] + (b[1] - a[1]) * (v - a[0]) / (b[0] - a[0]))
        cc = self.crossings_cont(axis, v)
        fs = sorted(fs + cc)
        out = []
        for f in fs:
            if out and f - out[-1] < MIN_ITEM: continue
            out.append(f)
        if cc:
            for c in (cc[0], cc[-1]):                       # contour faces are exact: they replace a face closer than the jog filter
                j = min(range(len(out)), key=lambda i: abs(out[i] - c))
                if abs(out[j] - c) < MIN_ITEM: out[j] = c
        self.cache[key] = out
        return out


EXT_MAX = 200.0          # a face of an element NOT crossed by the line is read with an extension line when the element is at most this far from the line


def requirements(uni, void):
    """coordinates that must be read: per axis a dict c -> tol (beams exact, everything else jog tolerance) and c -> [(lo, hi, exact c)] of the segments that carry it"""
    V, H, S = uni; V = V + void[0]; H = H + void[1]; req = {'x': {}, 'y': {}}; segs_of = {'x': {}, 'y': {}}
    for axis, segs in (('x', V), ('y', H)):
        raw = {}
        for sg in segs:
            if sg['hi'] - sg['lo'] < MIN_SEG: continue
            tol = BEAM_TOL if sg['layer'] == '93_KORA' else JOG
            raw.setdefault(round(sg['c'], 1), []).append((sg['lo'], sg['hi'], sg['c'], tol))
        keep = {}
        for c in sorted(raw):
            tol = min(t for lo, hi, ce, t in raw[c])
            if keep and c - max(keep) <= min(tol, req[axis][max(keep)]):
                segs_of[axis][max(keep)] += [(lo, hi, ce) for lo, hi, ce, t in raw[c]]; continue
            keep[c] = tol; req[axis][c] = tol; segs_of[axis][c] = [(lo, hi, ce) for lo, hi, ce, t in raw[c]]
    req['segs'] = segs_of
    return req


def covered(faces, c, tol):
    i = bisect.bisect_left(faces, c - tol)
    return i < len(faces) and faces[i] <= c + tol


def candidates(uni, void, axis, cont):
    V, H, S = uni; segs = (V + void[0]) if axis == 'x' else (H + void[1])
    perp = (H + void[1]) if axis == 'x' else (V + void[0])
    avoid = sorted(sg['c'] for sg in perp)
    xs = [p[1] if axis == 'x' else p[0] for p in cont]; lo, hi = min(xs), max(xs)
    cand = set(); v = lo + 20
    while v < hi - 20: cand.add(round(v)); v += STEP
    for sg in segs:
        if sg['hi'] - sg['lo'] >= MIN_SEG: cand.add(round((sg['lo'] + sg['hi']) / 2))
    out = []
    for v in sorted(cand):
        i = bisect.bisect_left(avoid, v - AVOID_EDGE)
        if i < len(avoid) and avoid[i] <= v + AVOID_EDGE: continue         # never run along an element edge
        out.append(float(v))
    return out


def reach(segs, v):
    """None = the line crosses one of the carrying segments; else (exact c, ref) of the nearest one within EXT_MAX (ref = nearest point of the segment along the line), or False"""
    best = False; bd = EXT_MAX + 1
    for lo, hi, ce in segs:
        if lo + 3 <= v <= hi - 3: return None
        d = lo - v if v < lo else (v - hi if v > hi else 0)
        if d <= EXT_MAX and d < bd: bd = d; best = (ce, min(max(v, lo), hi))
    return best


def choose_lines(out, scan, req, cands, axis, rep):
    """greedy set cover: the line that reads most still-unread coordinates (crossing them, or reaching them with an extension line <= EXT_MAX); ties -> fewest repeated faces, then fewest obstacles"""
    unread = dict(req[axis]); segs_of = req['segs'][axis]; lines = []; read = []
    xy = (lambda u, v: (u, v)) if axis == 'x' else (lambda u, v: (v, u))

    def line_faces(v):
        fs = [(f, None) for f in scan.faces(axis, v)]; extra = []
        for c, t in unread.items():
            if covered([f for f, r in fs], c, t): continue
            r = reach(segs_of[c], v)
            if r: extra.append(r)
        allf = sorted(fs + extra, key=lambda t: t[0]); out_ = []
        for f, r in allf:
            if out_ and f - out_[-1][0] < MIN_ITEM:
                if out_[-1][1] is not None and r is None: out_[-1] = (f, r)       # a crossed face beats a referenced one
                continue
            out_.append((f, r))
        return out_

    while unread:
        best = []; top = 0
        for v in cands:
            fs = [f for f, r in line_faces(v)]
            if len(fs) < 2: continue
            n = sum(1 for c, t in unread.items() if covered(fs, c, t))
            if n > top: top = n; best = [v]
            elif n == top and n > 0: best.append(v)
        if not best: break
        sc = []
        for v in best:
            fs = [f for f, r in line_faces(v)]
            sc.append((sum(1 for f in fs if covered(read, f, JOG)), len(fs), v))
        sc.sort(); sc = sc[:25]
        sc = [(pg.cost(out, xy(line_faces(v)[0][0], v), xy(line_faces(v)[-1][0], v)), d, v) for d, n_, v in sc]
        c_, d_, v = min(sc, key=lambda t: (t[1], t[0], t[2]))
        fl = line_faces(v); fs = [f for f, r in fl]
        topn = sum(1 for c, t in unread.items() if covered(fs, c, t))
        lines.append((v, fl, c_))
        out.stripes.add(xy(fs[0], v), xy(fs[-1], v))
        read = sorted(read + fs)
        for c in [c for c, t in unread.items() if covered(fs, c, t)]: unread.pop(c)
        rep.append((axis, 'line', round(v), 'newly read=%d' % topn, 'faces=%d' % len(fs), 'with ext lines=%d' % sum(1 for f, r in fl if r is not None), 'repeated=%d' % d_, 'obstacles=%d' % c_))
    # reverse-delete: a line whose faces are all read by the other lines is dropped (fewest lines, rule 4)
    changed = True
    while changed and len(lines) > 1:
        changed = False
        for k in sorted(range(len(lines)), key=lambda i: len(lines[i][1])):
            rest = sorted(f for i, l in enumerate(lines) if i != k for f, r in l[1])
            mine = [f for f, r in lines[k][1]]
            if all(covered(rest, c, t) for c, t in req[axis].items() if c not in unread and covered(mine, c, t)):
                rep.append((axis, 'line dropped (redundant)', round(lines[k][0]))); del lines[k]; changed = True; break
    return lines, unread


def draw_line(out, axis, v, fl, regions, texts_used, rep):
    """continuous chain of ALL consecutive faces; wall items (<=150 on hatch) get their text beside the wall, narrow items alternate"""
    k = 0; n = 0
    for (a, ra), (b, rb) in zip(fl, fl[1:]):
        ra = v if ra is None else ra; rb = v if rb is None else rb
        m = b - a
        if m < MIN_ITEM: continue
        mid = ((a + b) / 2, v) if axis == 'x' else (v, (a + b) / 2)
        loc = None
        txt = '%g' % round(m, 1) if abs(m - round(m)) > 0.05 else '%d' % round(m)
        half = 0.5 * CHAR_W * TEXT_H * len(txt)
        on_wall = m <= WALL_TEXT_MAX and pcn.in_wall(regions, mid)
        if on_wall:
            for sgn in (1, -1):
                for side in (1, -1):
                    sh = m / 2 + half + GAP
                    c = (mid[0] + sgn * sh, v + side * PERP) if axis == 'x' else (v + side * PERP, mid[1] + sgn * sh)
                    box = (c[0] - half, c[1] - TEXT_H / 2, c[0] + half, c[1] + TEXT_H / 2)
                    if pcn.in_wall(regions, c): continue
                    if any(box[0] < o[2] and box[2] > o[0] and box[1] < o[3] and box[3] > o[1] for o in texts_used): continue
                    loc = c; texts_used.append(box); break
                if loc: break
        nk = None
        if loc is None and m < NARROW: nk = k; k += 1
        if loc is not None:
            kw = dict(base=((a, v) if axis == 'x' else (v, a)), p1=((a, ra) if axis == 'x' else (ra, a)), p2=((b, rb) if axis == 'x' else (rb, b)), angle=0 if axis == 'x' else 90, dimstyle=pe.STYLE, location=loc, dxfattribs={'layer': pe.LAYER})
            out.ms.add_linear_dim(**kw).render(); out.n += 1
        elif axis == 'x': out.lin((a, ra), (b, rb), (a, v), 0, nk)
        else: out.lin((ra, a), (rb, b), (v, a), 90, nk)
        n += 1
    return n


def skew_inside(out, uni, areas, rep):
    """aligned dim on each skewed edge >= 60 (opposite equal parallel edges once), on the INNER side (inside the slab contour), free of other dims"""
    V, H, S = uni; by = {}
    for sg in S:
        if sg['L'] >= pg.MIN_SKEW: by.setdefault(sg['h'], []).append(sg)
    n = 0; placed = set()
    for h, segs in by.items():
        taken = []; allp = [q for t in segs for q in (t['a'], t['b'])]
        cx = sum(q[0] for q in allp) / len(allp); cy = sum(q[1] for q in allp) / len(allp)
        for sg in sorted(segs, key=lambda t: (t['a'][0] + t['b'][0], t['a'][1] + t['b'][1])):
            ang = math.atan2(sg['b'][1] - sg['a'][1], sg['b'][0] - sg['a'][0]) % math.pi
            if any(abs(t['L'] - sg['L']) < 1 and abs(t['ang'] - ang) < .01 for t in taken): continue
            sg['ang'] = ang; taken.append(sg)
            a, b = sg['a'], sg['b']; L = sg['L']; left = (-(b[1] - a[1]) / L, (b[0] - a[0]) / L); mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            away = 1 if (mid[0] - cx) * left[0] + (mid[1] - cy) * left[1] > 0 else -1
            done = False
            key = (round(L), round(ang, 2))
            if key in placed: continue                  # identical element family already dimensioned once
            for forced, anywhere in ((False, False), (True, False), (False, True), (True, True)):   # elements outside the slab contour (rule 4: every element) are dimensioned last, beside the element
                for o in (80, 120, 170, 230, 300, 400, 500, 650):
                    for side in (away, -away):          # element side first, else the other; the dim must lie INSIDE the plan
                        pa_ = (a[0] + left[0] * o * side, a[1] + left[1] * o * side); pb_ = (b[0] + left[0] * o * side, b[1] + left[1] * o * side)
                        if (anywhere or inside_any(areas, (pa_[0] + pb_[0]) / 2, (pa_[1] + pb_[1]) / 2) and inside_any(areas, pa_[0], pa_[1]) and inside_any(areas, pb_[0], pb_[1])) and (forced or out.free(pa_, pb_)):
                            out.aligned(a, b, o * side, 'skew' + h); n += 1; rep.append(('skew edge', h, round(L, 1), o * side, 'FORCED (text may touch)' if forced else '')); done = True; placed.add(key); break
                    if done: break
                if done: break
            if not done: rep.append(('skew edge NOT placed inside', h, round(L, 1)))
    return n


def skew_xy(doc, out, box, rep):
    """USER RULE 2026-10-11: dimensions ONLY along X and Y. Skewed / oblique elements (and leftover unread faces, also outside the contour) get X and Y chains over the
    vertex coordinates of the element (items < 10 merged), beside the element on a free line; no aligned dims."""
    import plan_audit as pa
    res, _ = pa.audit(doc, box); n = 0
    for cat, (cnt, bad, faces, smp) in res.items():
        for h, mx, my, sk in smp:
            e = doc.entitydb[h]
            pts = [(p[0], p[1]) for p in e.get_points('xy')] if e.dxftype() == 'LWPOLYLINE' else [tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]]
            for axis, un in (('x', mx), ('y', my)):
                if not un: continue
                i = 0 if axis == 'x' else 1; j = 1 - i
                vs = sorted(set(round(p[i], 1) for p in pts)); ch = []
                for v in vs:
                    if ch and v - ch[-1] < MIN_ITEM: continue
                    ch.append(v)
                if len(ch) < 2: rep.append(('X/Y: single coordinate, no partner', h, un)); continue
                lo = min(p[j] for p in pts); hi = max(p[j] for p in pts); done = False
                for forced in (False, True):
                    for o in (60, 90, 130, 180, 250, 350, 500):
                        for side, ref in ((1, hi), (-1, lo)):
                            line = ref + side * o
                            a_, b_ = ((ch[0], line), (ch[-1], line)) if axis == 'x' else ((line, ch[0]), (line, ch[-1]))
                            if forced or out.free(a_, b_):
                                k = 0
                                for a, b in zip(ch, ch[1:]):
                                    nk = None
                                    if b - a < NARROW: nk = k; k += 1
                                    if axis == 'x': out.lin((a, ref), (b, ref), (a, line), 0, nk)
                                    else: out.lin((ref, a), (ref, b), (line, a), 90, nk)
                                out.stripes.add(a_, b_); n += 1; done = True
                                rep.append(('X/Y chain', h, axis, round(line), [round(b - a, 1) for a, b in zip(ch, ch[1:])], 'FORCED' if forced else '')); break
                        if done: break
                    if done: break
    return n


def run(doc, box, replace=False, dry=False, verbose=False):
    cont = contour_of(doc, box)
    if cont is None: raise SystemExit('no slab contour (9_KONTUR closed polyline) in the box')
    if replace and not dry: print('removed old dims:', pg.clear_dims(doc, box))
    pg.pc.load = pg.box_load(box)
    out = pe.Out(doc); rep = []
    uni = pg.universe(doc, box); void = void_segments(doc, box); scan = Scan(uni, cont); req = requirements(uni, void)
    regions = pcn.wall_regions(doc); texts_used = []; total = 0; lines_all = {}
    for axis in ('x', 'y'):
        cands = candidates(uni, void, axis, cont)
        lines, left = choose_lines(out, scan, req, cands, axis, rep)
        lines_all[axis] = lines
        if left: rep.append((axis, 'UNREAD coordinates', sorted(left)))
    for axis in ('x', 'y'):
        for v, fs, c_ in sorted(lines_all[axis]): total += draw_line(out, axis, v, fs, regions, texts_used, rep)
    skew_xy(doc, out, box, rep)
    rep.append(('lines', {a: len(l) for a, l in lines_all.items()}, 'new dimensions', out.n))
    return out, rep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True)
    ap.add_argument('--replace', action='store_true'); ap.add_argument('--dry', action='store_true'); ap.add_argument('-v', action='store_true')
    ap.add_argument('--expect', type=float); ap.add_argument('-o')
    a = ap.parse_args()
    if a.expect and abs(os.path.getmtime(a.file) - a.expect) > 1: sys.exit('file changed since it was read')
    doc = ezdxf.readfile(a.file)
    out, rep = run(doc, tuple(a.box), a.replace, a.dry, a.v)
    for r in rep: print(r)
    if a.dry: return
    if a.o: doc.saveas(a.o); print('saved', a.o); return
    open(a.file, 'ab').close(); backup(a.file, 'lines'); doc.saveas(a.file); print('saved', a.file)


if __name__ == '__main__': main()
