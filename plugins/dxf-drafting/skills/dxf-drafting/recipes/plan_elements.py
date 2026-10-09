"""Recipe: SITE DIMENSION PLAN - dimensions for the elements that the continuous pier/wall chains (plan_chains.py) do not reach (ramla_base.dxf, 2026-10-08).
  python plan_elements.py FILE -o OUT [--dry] [--png X0 X1 Y0 Y1 OUT.png]
Reads the plan (82_KIR_OLE walls/piers, 93_KORA, circles, 9_KONTUR) and ADDS, on 36_MIDA_CLALI / dim_100 (same as plan_chains):
 1. BLOCKS (shaft / pit groups = rectangles on 93_KORA enclosing 82_KIR_OLE wall polygons): chain of every wall face along the south side (101 out) and west side (101 out),
    overall dimension one step further out (+100). Faces closer than 1.5 are merged. Walls = thickness items, rooms = clear spans.
 2. SKEWED piers / stubs (rotated quadrilaterals): thickness + length as aligned dims, one family = same side and same offset; pitch chain along the row.
 3. Orphan polygons (not in a block, not covered by chains): rectangles -> W x H linear dims, other polygons -> every edge as aligned dim.
 4. Circles (93_KORA, 82_KIR_OLE): diameter dim.
 5. Overall building dimensions (bbox of the biggest 82_KIR_OLE outline) south and east.
Placement: candidates are tried by increasing offset; a candidate is rejected when its stripe hits an existing dimension line / earlier new dim (bbox test), so
dims are shifted a little rather than overlapped. Never edits existing entities; always writes to a NEW file (-o).
UNVERIFIED (one plan): offsets, which polygons count as piers vs walls, no position dims for circles (no reference grid)."""
import argparse, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from dxflib import *

LAYER = '36_MIDA_CLALI'; STYLE = 'dim_100'
WALL = '82_KIR_OLE'; KORA = '93_KORA'; CONT = '9_KONTUR'
CHAIN_OFF = 101.0      # parts chain out of a block (user's pier-row chain: 101)
OVERALL_STEP = 100.0   # overall dim one chain-step further out
NOTE_LAYERS = ('4213_TEXT_ZIUN_T+I', '4', '1932_ZIUN_T+I', '4_TEXT')   # frames of rebar notes (obstacles)
NARROW = 45.0; STAGGER = 45.0   # spans under NARROW get their text staggered above / below the line
MERGE = 1.5            # faces closer than this are one face
QPAD = 20.0; PAD = 34.0             # half-height of a dim stripe (text 24 + gap)
OFFSETS = (45, 70, 100, 140, 180, 220, 260)   # candidate distances for single dims
BIG = 9000.0
MAX_VERT = 8; MAX_SIZE = 1100   # orphan polygons above this are ramps/slabs/outlines: listed, not dimensioned edge by edge


# ---------- geometry helpers
def pts(e): return [(q[0], q[1]) for q in e.get_points()]
def bb(p): xs = [a for a, b in p]; ys = [b for a, b in p]; return min(xs), min(ys), max(xs), max(ys)
def dist(a, b): return math.hypot(b[0] - a[0], b[1] - a[1])


class Stripes:
    """Obstacle map. Dim lines are padded bboxes with an orientation ('h' / 'v' / 'd'); a new line only collides with PARALLEL dim lines (crossing a perpendicular chain is normal).
    Texts, notes, symbols and the text box of every existing dim are '*' obstacles for everything."""
    def __init__(self, doc):
        self.boxes = []
        for d in doc.modelspace().query('DIMENSION'):
            try:
                p1, p2, dl = d.dxf.defpoint2, d.dxf.defpoint3, d.dxf.defpoint
            except Exception: continue
            ang = dim_angle(d)
            a = ang % 180; kind = 'h' if abs(a) < 1 or abs(a - 180) < 1 else 'v' if abs(a - 90) < 1 else 'd'
            ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            t1 = (p1[0] - dl[0]) * ux + (p1[1] - dl[1]) * uy; t2 = (p2[0] - dl[0]) * ux + (p2[1] - dl[1]) * uy
            self.add((dl[0] + ux * t1, dl[1] + uy * t1), (dl[0] + ux * t2, dl[1] + uy * t2), kind)
            tm = d.dxf.get('text_midpoint')
            if tm is not None:
                w, h = (45, 16) if kind != 'v' else (16, 45)
                self.boxes.append((tm.x - w, tm.y - h, tm.x + w, tm.y + h, '*'))
        for e in doc.modelspace():
            t = e.dxftype()
            if t in ('TEXT', 'MTEXT', 'INSERT', 'LEADER') or (t == 'LWPOLYLINE' and e.closed and e.dxf.layer in NOTE_LAYERS):
                try: ext = bbox.extents([e])
                except Exception: continue
                if ext.has_data and ext.size.x < 900 and ext.size.y < 900:   # not whole-plan symbols
                    self.boxes.append((ext.extmin.x - 6, ext.extmin.y - 6, ext.extmax.x + 6, ext.extmax.y + 6, '*'))

    def add(self, a, b, kind=None):
        if kind is None: kind = 'h' if abs(a[1] - b[1]) < 1e-6 else 'v' if abs(a[0] - b[0]) < 1e-6 else 'd'
        self.boxes.append((min(a[0], b[0]) - PAD, min(a[1], b[1]) - PAD, max(a[0], b[0]) + PAD, max(a[1], b[1]) + PAD, kind))

    def hit(self, a, b):
        kind = 'h' if abs(a[1] - b[1]) < 1e-6 else 'v' if abs(a[0] - b[0]) < 1e-6 else 'd'
        q = QPAD   # the candidate line itself needs its own text height of clearance
        x0, y0, x1, y1 = min(a[0], b[0]) - q, min(a[1], b[1]) - q, max(a[0], b[0]) + q, max(a[1], b[1]) + q
        return any(x0 < bx1 and x1 > bx0 and y0 < by1 and y1 > by0 and (k == '*' or k == kind) for bx0, by0, bx1, by1, k in self.boxes)


class Out:
    def __init__(self, doc):
        self.doc = doc; self.ms = doc.modelspace(); self.n = 0; self.stripes = Stripes(doc); self.log = []

    def lin(self, p1, p2, base, angle, narrow_k=None):
        """narrow_k = running index among NARROW items of a chain: texts alternate above / below the line (+-STAGGER) so they do not overprint"""
        kw = {}
        if narrow_k is not None:
            sgn = 1 if narrow_k % 2 else -1
            kw['location'] = ((p1[0] + p2[0]) / 2, base[1] + sgn * STAGGER) if angle == 0 else (base[0] + sgn * STAGGER, (p1[1] + p2[1]) / 2)
        self.ms.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle=STYLE, dxfattribs={'layer': LAYER}, **kw).render(); self.n += 1

    def hchain(self, xs, y_line, y_ref, tag):
        """horizontal chain through consecutive x faces; ext lines start at y_ref"""
        k = 0
        for a, b in zip(xs, xs[1:]):
            nk = None
            if b - a < NARROW: nk = k; k += 1
            self.lin((a, y_ref), (b, y_ref), (a, y_line), 0, nk)
        self.stripes.add((xs[0], y_line), (xs[-1], y_line)); self.log.append((tag, 'x', round(y_line), [round(b - a, 1) for a, b in zip(xs, xs[1:])]))

    def vchain(self, ys, x_line, x_ref, tag):
        k = 0
        for a, b in zip(ys, ys[1:]):
            nk = None
            if b - a < NARROW: nk = k; k += 1
            self.lin((x_ref, a), (x_ref, b), (x_line, a), 90, nk)
        self.stripes.add((x_line, ys[0]), (x_line, ys[-1])); self.log.append((tag, 'y', round(x_line), [round(b - a, 1) for a, b in zip(ys, ys[1:])]))

    def aligned(self, p1, p2, dist_, tag):
        ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
        if ang > 90.5 or ang <= -89.5:     # the text follows the p1->p2 direction: keep it readable (no upside-down text); swapping the points flips the side, so negate the distance
            p1, p2, dist_ = p2, p1, -dist_
        self.ms.add_aligned_dim(p1, p2, dist_, dimstyle=STYLE, dxfattribs={'layer': LAYER}).render(); self.n += 1
        L = dist(p1, p2); nx, ny = -(p2[1] - p1[1]) / L, (p2[0] - p1[0]) / L
        self.stripes.add((p1[0] + nx * dist_, p1[1] + ny * dist_), (p2[0] + nx * dist_, p2[1] + ny * dist_))
        self.log.append((tag, 'aligned', round(L, 1), round(dist_)))

    def free(self, a, b): return not self.stripes.hit(a, b)


def merge_faces(vals, tol=MERGE):
    cs = []
    for v in sorted(vals):
        if cs and v - cs[-1][-1] <= tol: cs[-1].append(v)
        else: cs.append([v])
    return [sum(c) / len(c) for c in cs]


# ---------- inventory
def inventory(doc):
    ms = doc.modelspace(); polys = []
    for e in ms.query('LWPOLYLINE'):
        if e.dxf.layer not in (WALL, KORA, CONT) or not e.closed: continue
        p = pts(e); x0, y0, x1, y1 = bb(p)
        if max(x1 - x0, y1 - y0) >= BIG: continue
        polys.append(dict(h=e.dxf.handle, layer=e.dxf.layer, p=p, box=(x0, y0, x1, y1), w=x1 - x0, hgt=y1 - y0))
    big = []
    for e in ms.query('LWPOLYLINE'):
        if e.dxf.layer == WALL:
            x0, y0, x1, y1 = bb(pts(e))
            if max(x1 - x0, y1 - y0) >= BIG: big.append((e.dxf.handle, (x0, y0, x1, y1)))
    circles = [dict(h=e.dxf.handle, layer=e.dxf.layer, c=(e.dxf.center[0], e.dxf.center[1]), r=e.dxf.radius) for e in ms.query('CIRCLE') if e.dxf.layer in (KORA, WALL)]
    return polys, big, circles


def is_rect(p, tol=1.0):
    if len(p) != 4: return False
    x0, y0, x1, y1 = bb(p)
    return all((abs(a - x0) < tol or abs(a - x1) < tol) and (abs(b - y0) < tol or abs(b - y1) < tol) for a, b in p)


def covered(doc_dims, poly, tol=1.5):
    """True when the plan already carries linear dims between both x faces AND both y faces of this rectangle"""
    x0, y0, x1, y1 = poly['box']
    hx = any(abs(s - x0) < tol and abs(e - x1) < tol for s, e, o in doc_dims['h']); vy = any(abs(s - y0) < tol and abs(e - y1) < tol for s, e, o in doc_dims['v'])
    return hx and vy


def read_dims(doc):
    h = []; v = []
    for d in doc.modelspace().query('DIMENSION'):
        a = round(dim_angle(d)) % 180; p1, p2 = d.dxf.defpoint2, d.dxf.defpoint3
        if a == 0: h.append((min(p1[0], p2[0]), max(p1[0], p2[0]), d.dxf.defpoint[1]))
        elif a == 90: v.append((min(p1[1], p2[1]), max(p1[1], p2[1]), d.dxf.defpoint[0]))
    return dict(h=h, v=v)


# ---------- placement
def free_offset(out, a, b, nx, ny, offsets=OFFSETS):
    """first candidate distance whose stripe (a,b shifted along the normal) does not collide; None if none"""
    for o in offsets:
        if out.free((a[0] + nx * o, a[1] + ny * o), (b[0] + nx * o, b[1] + ny * o)): return o
    return None


def pick_line(out, span, kind, sides, maxk=8, strict=False):
    """(line coord, ext-line reference coord, side sign) for a chain along span: try each side (sign, edge), ideal CHAIN_OFF then +50 steps (max 8); the least displaced candidate wins"""
    best = None
    for sgn, edge in sides:
        for k in range(maxk + 1):
            c = edge + sgn * (CHAIN_OFF + 50 * k)
            a, b = ((span[0], c), (span[1], c)) if kind == 'h' else ((c, span[0]), (c, span[1]))
            if out.free(a, b):
                if best is None or k < best[0]: best = (k, c, edge, sgn)
                break
    if best is None:
        if strict: return None
        sgn, edge = sides[0]; out.log.append(('FORCED line', kind, round(edge))); return edge + sgn * CHAIN_OFF, edge, sgn
    return best[1], best[2], best[3]


def do_blocks(out, polys, rep):
    done = set()
    frames = [q for q in polys if q['layer'] == KORA and q['w'] > 500 and q['hgt'] > 500 and is_rect(q['p'])]
    # keep the INNER frame of each concentric pair (the 15-offset duplicate is the lining)
    frames.sort(key=lambda q: q['w'])
    taken = []
    for f in frames:
        if any(abs(f['box'][0] - t['box'][0]) < 20 and abs(f['box'][1] - t['box'][1]) < 20 for t in taken): continue
        taken.append(f)
    for f in taken:
        x0, y0, x1, y1 = f['box']
        mem = [q for q in polys if q['layer'] == WALL and x0 <= (q['box'][0] + q['box'][2]) / 2 <= x1 and y0 <= (q['box'][1] + q['box'][3]) / 2 <= y1]   # centre inside the frame (a wall may stick out of it)
        if not mem: continue
        x0 = min([x0] + [q['box'][0] for q in mem]); y0 = min([y0] + [q['box'][1] for q in mem])
        x1 = max([x1] + [q['box'][2] for q in mem]); y1 = max([y1] + [q['box'][3] for q in mem])
        xs = merge_faces([a for q in mem for a, b in q['p']] + [x0, x1])
        ys = merge_faces([b for q in mem for a, b in q['p']] + [y0, y1])
        # drop faces that create tiny slivers (<10) other than wall thickness: merge handles <1.5 only, keep rest (they are real wall steps)
        # x chain: south first (ideal 101 out), else shifted outward, else north side; y chain: west, then east
        sx = pick_line(out, (xs[0], xs[-1]), 'h', [(-1, y0), (1, y1)])
        sy = pick_line(out, (ys[0], ys[-1]), 'v', [(-1, x0), (1, x1)])
        (yl, y_ref, sgx), (xl, x_ref, sgy) = sx, sy
        out.hchain(xs, yl, y_ref, 'block%s-x' % f['h']); out.vchain(ys, xl, x_ref, 'block%s-y' % f['h'])
        # overall: nearest free line on either side (the chain just placed blocks its own side up to ~70 beyond it); skipped when none within MAXK steps
        so = pick_line(out, (x0, x1), 'h', [(-1, y0), (1, y1)], maxk=6, strict=True)
        sv = pick_line(out, (y0, y1), 'v', [(-1, x0), (1, x1)], maxk=6, strict=True)
        if so: out.lin((x0, so[1]), (x1, so[1]), (x0, so[0]), 0); out.stripes.add((x0, so[0]), (x1, so[0]))
        else: rep.append(('overall width skipped (no free line)', f['h']))
        if sv: out.lin((sv[1], y0), (sv[1], y1), (sv[0], y0), 90); out.stripes.add((sv[0], y0), (sv[0], y1))
        else: rep.append(('overall height skipped (no free line)', f['h']))
        out.log.append(('block%s-overall' % f['h'], round(x1 - x0), round(y1 - y0), so and round(so[0]), sv and round(sv[0])))
        for q in mem: done.add(q['h'])
        done.add(f['h'])
        for q in polys:
            if q['layer'] == KORA and q['box'][0] >= x0 - 20 and q['box'][2] <= x1 + 20 and q['box'][1] >= y0 - 20 and q['box'][3] <= y1 + 20: done.add(q['h'])
        rep.append(('block', f['h'], len(mem), round(x1 - x0), round(y1 - y0)))
    return done


def poly_edges(p):
    """(a, b, nx, ny) per edge to dimension, normals pointing OUT of the polygon; a quadrilateral keeps its two distinct sides"""
    n = len(p); cx = sum(a for a, b in p) / n; cy = sum(b for a, b in p) / n
    es = [(p[i], p[(i + 1) % n]) for i in range(n)]
    if n == 4 and abs(dist(*es[0]) - dist(*es[2])) < 3: es = es[:2]
    out = []
    for a, b in es:
        L = dist(a, b)
        if L < 8: continue
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        if ((a[0] + b[0]) / 2 - cx) * nx + ((a[1] + b[1]) / 2 - cy) * ny < 0: nx, ny = -nx, -ny
        out.append((a, b, nx, ny))
    return out


def side_dims(out, members, tag):
    """members = polygons of one FAMILY (same shape): each edge slot gets the same offset for all members (smallest offset free for all), else per member"""
    edges = [poly_edges(q['p']) for q in members]
    for j in range(min(len(e) for e in edges)):
        slot = [e[j] for e in edges]
        common = next((o for o in OFFSETS if all(out.free((a[0] + nx * o, a[1] + ny * o), (b[0] + nx * o, b[1] + ny * o)) for a, b, nx, ny in slot)), None)
        for (a, b, nx, ny), q in zip(slot, members):
            o = common if common is not None else free_offset(out, a, b, nx, ny)
            if o is None: o = OFFSETS[-1]; out.log.append((tag + q['h'], 'FORCED', round(dist(a, b))))
            # aligned dim: positive distance = LEFT of a->b; the outward normal may be either side
            left = (-(b[1] - a[1]) / dist(a, b), (b[0] - a[0]) / dist(a, b))
            sgn = 1 if left[0] * nx + left[1] * ny > 0 else -1
            out.aligned(a, b, o * sgn, tag + q['h'])
    for q in members: pass
    return len(members)


def do_orphans(out, polys, done, dims, rep):
    rest = [q for q in polys if q['h'] not in done and q['layer'] in (WALL, CONT)]
    skew = []; skipped = []
    for q in rest:
        if q['layer'] == WALL and is_rect(q['p']) and covered(dims, q): skipped.append(q['h']); continue
        if len(q['p']) > MAX_VERT or max(q['w'], q['hgt']) > MAX_SIZE and not is_rect(q['p']):   # big / complex outline: not a site element, listed
            rep.append(('NOT DIMENSIONED (complex outline)', q['h'], len(q['p']), round(q['w']), round(q['hgt']))); continue
        if is_rect(q['p']):                                    # axis-aligned rectangle: W below, H right
            x0, y0, x1, y1 = q['box']
            yl = y0 - 60
            for k in range(6):
                if out.free((x0, yl), (x1, yl)): break
                yl -= 50
            xl = x1 + 60
            for k in range(6):
                if out.free((xl, y0), (xl, y1)): break
                xl += 50
            out.lin((x0, y0), (x1, y0), (x0, yl), 0); out.stripes.add((x0, yl), (x1, yl))
            out.lin((x1, y0), (x1, y1), (xl, y0), 90); out.stripes.add((xl, y0), (xl, y1)); out.n += 0
            rep.append(('rect', q['h'], round(q['w']), round(q['hgt'])))
        else: skew.append(q)
    fam = {}
    for q in skew: fam.setdefault((len(q['p']), round(q['w'] / 15), round(q['hgt'] / 15)), []).append(q)
    for key, g in fam.items():
        side_dims(out, g, 'poly')
        for q in g: rep.append(('poly', q['h'], len(q['p']), round(q['w']), round(q['hgt'])))
    return skipped


def pitch_chains(out, polys, done, rep):
    """rows of skewed piers (same size): aligned chain between their lowest corners along the row; ONE offset + side for the whole row"""
    sk = [q for q in polys if q['layer'] == WALL and len(q['p']) == 4 and not is_rect(q['p'])]
    groups = {}
    for q in sk: groups.setdefault((round(q['w'] / 15), round(q['hgt'] / 15)), []).append(q)
    for key, g in groups.items():
        if len(g) < 3: continue
        g.sort(key=lambda q: (q['box'][1], q['box'][0]))
        cs = [min(q['p'], key=lambda t: (t[1], t[0])) for q in g]
        pairs = [(a, b) for a, b in zip(cs, cs[1:]) if dist(a, b) >= 100]
        best = None
        for sgn in (1, -1):
            for o in (120, 160, 200, 240, 280, 320, 360):
                if all(out.free((a[0] + sgn * -(b[1] - a[1]) / dist(a, b) * o, a[1] + sgn * (b[0] - a[0]) / dist(a, b) * o), (b[0] + sgn * -(b[1] - a[1]) / dist(a, b) * o, b[1] + sgn * (b[0] - a[0]) / dist(a, b) * o)) for a, b in pairs):
                    if best is None or o < best[0]: best = (o, sgn)
                    break
        if best is None: best = (120, 1); out.log.append(('pitch', 'FORCED', key))
        o, sgn = best
        for a, b in pairs: out.aligned(a, b, o * sgn, 'pitch'); rep.append(('pitch', round(dist(a, b), 1)))


def do_circles(out, circles, rep):
    for c in circles:
        cx, cy = c['c']; r = c['r']
        ang = 45.0
        for ang in (45, 135, 315, 225):
            tip = (cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang)))
            far = (cx + (r + 90) * math.cos(math.radians(ang)), cy + (r + 90) * math.sin(math.radians(ang)))
            if out.free(tip, far): break
        d = out.ms.add_diameter_dim(center=(cx, cy), radius=r, angle=ang, dimstyle=STYLE, dxfattribs={'layer': LAYER}); d.render(); out.n += 1
        out.stripes.add(tip, far); rep.append(('circle', c['h'], 2 * r))


def do_overall(out, big, rep):
    if not big: return
    h, (x0, y0, x1, y1) = max(big, key=lambda t: (t[1][2] - t[1][0]) * (t[1][3] - t[1][1]))
    yl = y0 - 160
    for k in range(8):
        if out.free((x0, yl), (x1, yl)): break
        yl -= 60
    out.lin((x0, y0), (x1, y0), (x0, yl), 0); out.stripes.add((x0, yl), (x1, yl))
    xl = x1 + 160
    for k in range(8):
        if out.free((xl, y0), (xl, y1)): break
        xl += 60
    out.lin((x1, y0), (x1, y1), (xl, y0), 90); out.stripes.add((xl, y0), (xl, y1))
    rep.append(('overall', h, round(x1 - x0), round(y1 - y0)))


def run(doc, dry=False):
    polys, big, circles = inventory(doc); dims = read_dims(doc); out = Out(doc); rep = []
    done = do_blocks(out, polys, rep)
    skipped = do_orphans(out, polys, done, dims, rep)
    pitch_chains(out, polys, done, rep)
    do_circles(out, circles, rep)
    do_overall(out, big, rep)
    rep.append(('already covered by chains', len(skipped)))
    return out, rep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('-o', required=True); ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(); doc = ezdxf.readfile(a.file)
    out, rep = run(doc, a.dry)
    for r in rep: print(r)
    print('new dimensions:', out.n)
    if not a.dry: doc.saveas(a.o); print('saved', a.o)


if __name__ == '__main__': main()
