"""Recipe: CONTINUITY + DE-DUPLICATION of a dimension plan, IN PLACE (ramla_base-dimplan.dxf, 2026-10-08). Learned from the user's own corrections of my plan:
  python plan_continuity.py FILE [--box X0 Y0 X1 Y1] [--expect SNAPSHOT] [--dry] [-v]
User preference (2026-10-08): "as many CONTINUOUS dimension lines as possible rather than individual dimensions" and "no duplicate dimensions". What the user did and what this recipe generalises:
 1 FILL HOLES: a chain (>= 3 collinear dims) with a short hole (<= 60) between two wall faces gets that item (the user added the 40.2 / 39.8 horizontal items through the skewed piers 1047 / 102D / 1048 on the existing chain lines). Same for 20.0 / 10.4 jogs.
 2 DE-DUPLICATE: an aligned / skewed size dim of a pier that a chain item already measures (same pier faces, same value within 0.6 %) is deleted (red cloud on the 35 of pier 108E: the vertical chain already carries 35.1); the user also removed the aligned 40 / 35 of piers 1047 / 102D / 1048 after filling the chain.
 3 ROW CHAINS: the skewed piers of a row / column (single-link cluster, same family) get ONE continuous linear dim line along the row = pier extent, gap, pier extent, gap ... (offset 80 on the west / south side) instead of separate lengths + pitch + gap dims, which are deleted.
 4 TANKS (skewed rooms > 1100 long): ONE vertical chain wall | clear width | wall through the room at x (the user built it for 108C: 34.8 | 466.9 | 35.1) replaces the aligned clear-width and the aligned north / south wall thickness dims (both tanks).
 5 no dims shorter than 8 (rounding artefacts; user deleted the 4.6).
 6 WALL TEXTS (yellow cloud on the 20 at y=29626): the item of a wall crossed by a continuous line stays in the line, but its text moves along the line beside the wall (not on the hatch).
Deletions are listed (-v). Writes into FILE after a timestamped snapshot; --expect aborts when the user saved meanwhile."""
import argparse, collections, filecmp, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from dxflib import *
import plan_elements as pe, plan_tidy as pt, plan_revise as pr

HOLE_MAX = 60.0; ROW_OFF = 80.0; REL = 0.006


def seg_dist(p, a, b):
    L2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / L2))
    return math.hypot(p[0] - (a[0] + t * (b[0] - a[0])), p[1] - (a[1] + t * (b[1] - a[1])))


def on_boundary(p, poly, tol=3.0):
    n = len(poly); return any(seg_dist(p, poly[i], poly[(i + 1) % n]) <= tol for i in range(n))


def dims_info(doc):
    """[(dim, kind 'h'|'v'|'d', p1, p2, line coordinate, measurement)] for linear / aligned dims"""
    res = []
    for d in doc.modelspace().query('DIMENSION'):
        if d.dxf.dimtype & 7 not in (0, 1): continue
        p, q, dl = d.dxf.defpoint2, d.dxf.defpoint3, d.dxf.defpoint
        k = pt.axis_of(d); line = dl.y if k == 'h' else dl.x if k == 'v' else None
        ang = math.radians(dim_angle(d)); m = abs((q.x - p.x) * math.cos(ang) + (q.y - p.y) * math.sin(ang))   # ezdxf get_measurement() is 0 for some saved dims
        res.append((d, k, (p.x, p.y), (q.x, q.y), line, m))
    return res


def chain_groups(info):
    g = collections.defaultdict(list)
    for d, k, p, q, line, m in info:
        if k == 'h': g[('h', round(line))].append((min(p[0], q[0]), max(p[0], q[0]), p[1], line))
        elif k == 'v': g[('v', round(line))].append((min(p[1], q[1]), max(p[1], q[1]), p[0], line))
    return {k: sorted(v) for k, v in g.items() if len(v) >= 3}


def walls_small(doc):
    return [q for q in pe.inventory(doc)[0] if q['layer'] == pe.WALL and len(q['p']) <= 12]


# ---------- 1 holes
def fill_holes(doc, out, rep):
    info = dims_info(doc); polys = walls_small(doc); n = 0
    for (k, _), iv in chain_groups(info).items():
        cur = iv[0][1]; ref = iv[0][2]; line = iv[0][3]
        for a, b, r, ln in iv[1:]:
            gap = a - cur
            if 3 < gap <= HOLE_MAX:
                pa, pb = ((cur, r), (a, r)) if k == 'h' else ((r, cur), (r, a))
                if any(on_boundary(pa, q['p']) for q in polys) and any(on_boundary(pb, q['p']) for q in polys):
                    nk = 0 if gap < pe.NARROW else None
                    if k == 'h': out.lin((cur, r), (a, r), (cur, ln), 0, nk)
                    else: out.lin((r, cur), (r, a), (ln, cur), 90, nk)
                    rep.append(('fill hole', k, round(ln), round(gap, 1))); n += 1
            cur = max(cur, b)
    return n


# ---------- 2 duplicates
def pier_dups(doc, kill):
    info = dims_info(doc); polys = [q for q in walls_small(doc) if len(q['p']) == 4 and not pe.is_rect(q['p'])]
    axis = [(d, k, p, q, line, m) for d, k, p, q, line, m in info if k in 'hv']
    for d, k, p, q, line, m in info:
        if k != 'd' or m > 100 or d.dxf.handle in kill: continue
        for pl in polys:
            if all(min(pe.dist(p_, v) for v in pl['p']) < 3 for p_ in (p, q)):
                for d2, k2, p2, q2, l2, m2 in axis:
                    if abs(m2 - m) <= max(1.2, REL * m) and on_boundary(p2, pl['p']) and on_boundary(q2, pl['p']):
                        kill.setdefault(d.dxf.handle, 'dup of chain item ' + d2.dxf.handle + ' on pier ' + pl['h']); break
                break


# ---------- 3 rows
def clusters(g, link=1000.0):
    cs = [((q['box'][0] + q['box'][2]) / 2, (q['box'][1] + q['box'][3]) / 2) for q in g]; seen = set(); res = []
    for i in range(len(g)):
        if i in seen: continue
        comp = [i]; seen.add(i); k = 0
        while k < len(comp):
            for j in range(len(g)):
                if j not in seen and pe.dist(cs[comp[k]], cs[j]) < link: seen.add(j); comp.append(j)
            k += 1
        res.append([g[c] for c in comp])
    return res


def row_geometry(row):
    """direction u (upright: angle in (-90,90]), preferred normal n (west for vertical-ish rows, south otherwise), per pier (a, b) = ends of its edge parallel to u on the preferred side, ordered along u"""
    cs = [((q['box'][0] + q['box'][2]) / 2, (q['box'][1] + q['box'][3]) / 2) for q in row]
    dx = max(c[0] for c in cs) - min(c[0] for c in cs); dy = max(c[1] for c in cs) - min(c[1] for c in cs)
    vertical = dy > dx
    # row direction = direction of the longest edge of the first pier that agrees with the row's principal axis
    p0 = row[0]['p']; es = [(p0[i], p0[(i + 1) % 4]) for i in range(4)]
    want = (0.0, 1.0) if vertical else (1.0, 0.0)
    e0 = max(es, key=lambda e: abs((e[1][0] - e[0][0]) * want[0] + (e[1][1] - e[0][1]) * want[1]) / pe.dist(*e))
    ang = math.degrees(math.atan2(e0[1][1] - e0[0][1], e0[1][0] - e0[0][0]))
    while ang > 90.0 + 1e-9: ang -= 180.0
    while ang <= -90.0 + 1e-9: ang += 180.0
    u = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
    npref = (-1.0, 0.0) if vertical else (0.0, -1.0)
    nperp = (-u[1], u[0])
    if nperp[0] * npref[0] + nperp[1] * npref[1] < 0: nperp = (-nperp[0], -nperp[1])
    items = []
    for q in row:
        p = q['p']; es = [(p[i], p[(i + 1) % 4]) for i in range(4)]
        par = [e for e in es if abs(((e[1][0] - e[0][0]) * u[1] - (e[1][1] - e[0][1]) * u[0])) / pe.dist(*e) < 0.35]
        e = max(par, key=lambda e: ((e[0][0] + e[1][0]) / 2) * nperp[0] + ((e[0][1] + e[1][1]) / 2) * nperp[1])
        a, b = sorted(e, key=lambda t: t[0] * u[0] + t[1] * u[1])
        items.append((a, b))
    items.sort(key=lambda ab: ab[0][0] * u[0] + ab[0][1] * u[1])
    return ang, u, nperp, items


def row_chains(doc, rep, kill, verbose=False):
    polys = [q for q in walls_small(doc) if len(q['p']) == 4 and not pe.is_rect(q['p']) and max(q['w'], q['hgt']) < 400]
    fam = collections.defaultdict(list)
    for q in polys: fam[(round(q['w'] / 15), round(q['hgt'] / 15))].append(q)
    plans = []
    for key, g in fam.items():
        for row in clusters(g):
            if len(row) < 3: continue
            ang, u, nperp, items = row_geometry(row)
            pts_ = [t for ab in items for t in ab]
            if all(pr.has_dim_on(doc, a_, b_, 2.0) for a_, b_ in zip(pts_, pts_[1:])): continue      # chain already there (re-run)
            verts = [v for q in row for v in q['p']]
            for d, k, p, q, line, m in dims_info(doc):                     # separate lengths / pitch / gap dims of this row go
                if k != 'd' or d.dxf.handle in kill: continue
                da = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 180
                if min(abs(da - ang % 180), 180 - abs(da - ang % 180)) < 3.0 and all(min(pe.dist(p_, v) for v in verts) < 80 for p_ in (p, q)) and m > 20:
                    kill.setdefault(d.dxf.handle, 'row dim replaced by chain (%s)' % (key,))
            plans.append((key, ang, u, nperp, items))
    return plans


def add_rows(doc, plans, rep):
    out = pe.Out(doc)
    for key, ang, u, nperp, items in plans:
        pts = [t for ab in items for t in ab]
        chosen = None
        for o in (ROW_OFF, 110.0, 140.0, 170.0, 200.0):
            for sgn in (1, -1):
                l0 = (pts[0][0] + nperp[0] * o * sgn, pts[0][1] + nperp[1] * o * sgn); l1 = (pts[-1][0] + nperp[0] * o * sgn, pts[-1][1] + nperp[1] * o * sgn)
                if out.free(l0, l1): chosen = (o, sgn); break
            if chosen: break
        if chosen is None: chosen = (ROW_OFF, 1); rep.append(('row chain line FORCED', key))
        o, sgn = chosen; base = (pts[0][0] + nperp[0] * o * sgn, pts[0][1] + nperp[1] * o * sgn)
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            # all dims share ONE dim line through `base`; text above / below it when narrow
            kw = {}
            L = abs((b[0] - a[0]) * u[0] + (b[1] - a[1]) * u[1])
            out.ms.add_linear_dim(base=base, p1=a, p2=b, angle=ang, dimstyle=pe.STYLE, dxfattribs={'layer': pe.LAYER}, **kw).render(); out.n += 1
            rep.append(('row chain item', key, round(L, 1)))
        out.stripes.add((pts[0][0] + nperp[0] * o * sgn, pts[0][1] + nperp[1] * o * sgn), (pts[-1][0] + nperp[0] * o * sgn, pts[-1][1] + nperp[1] * o * sgn))
    return out


# ---------- 4 tanks
def tank_polys(doc):
    return [q for q in pe.inventory(doc)[0] if q['layer'] == pe.WALL and len(q['p']) == 4 and not pe.is_rect(q['p']) and max(q['w'], q['hgt']) > 1100]


def crossings(poly_pts, closed, x):
    ys = []
    n = len(poly_pts)
    for i in range(n if closed else n - 1):
        a, b = poly_pts[i], poly_pts[(i + 1) % n]
        if abs(a[0] - b[0]) < 1e-6: continue
        if min(a[0], b[0]) - 1e-6 <= x <= max(a[0], b[0]) + 1e-6:
            t = (x - a[0]) / (b[0] - a[0]); ys.append(a[1] + t * (b[1] - a[1]))
    return ys


def tanks(doc, kill, rep):
    info = dims_info(doc); todo = []
    wall_lines = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer == pe.WALL: wall_lines.append((pe.pts(e), e.closed, e.dxf.handle))
    for q in tank_polys(doc):
        P = q['p']; es = [(P[i], P[(i + 1) % 4]) for i in range(4)]
        long_ = max(es, key=lambda e: pe.dist(*e)); short = min(es, key=lambda e: pe.dist(*e))
        lang = math.degrees(math.atan2(long_[1][1] - long_[0][1], long_[1][0] - long_[0][0])) % 180; W = pe.dist(*short)
        x0, y0, x1, y1 = q['box']
        for d, k, p, qq, line, m in info:
            if k != 'd' or d.dxf.handle in kill: continue
            mx, my = (p[0] + qq[0]) / 2, (p[1] + qq[1]) / 2
            if not (x0 - 200 <= mx <= x1 + 200 and y0 - 200 <= my <= y1 + 200): continue
            da = math.degrees(math.atan2(qq[1] - p[1], qq[0] - p[0])) % 180
            perp = abs(((da - lang) % 180) - 90) < 4
            if perp and (abs(m - W) <= 1.2 or m <= 60): kill.setdefault(d.dxf.handle, 'tank clear width / N-S wall replaced by the vertical chain ' + q['h'])
        have = any(k == 'v' and abs(m - W) <= max(1.5, 0.006 * W) and on_boundary(p, P, 3) and on_boundary(qq, P, 3) for d, k, p, qq, line, m in info)
        if not have: todo.append(q)
    return todo


def add_tank_chain(doc, out, q, rep, x_pref=81862.0):
    P = q['p']; x0, y0, x1, y1 = q['box']
    lines = [t for t in [(pe.pts(e), e.closed, e.dxf.handle) for e in doc.modelspace().query('LWPOLYLINE') if e.dxf.layer == pe.WALL] if t[2] != q['h']]
    for dx in (0, 60, -60, 120, -120, 180, -180, 240, -240):
        x = x_pref + dx
        if not x0 + 50 < x < x1 - 50: continue
        yt = sorted(crossings(P, True, x))
        if len(yt) != 2: continue
        lo_edge, hi_edge = yt
        outer_lo = outer_hi = None
        for pts_, closed, h in lines:
            for y in crossings(pts_, closed, x):
                if lo_edge - 150 <= y < lo_edge - 8 and (outer_lo is None or y > outer_lo): outer_lo = y
                if hi_edge + 8 < y <= hi_edge + 150 and (outer_hi is None or y < outer_hi): outer_hi = y
        if outer_lo is None or outer_hi is None: continue
        ys = [outer_lo, lo_edge, hi_edge, outer_hi]
        if not all(out.free((x, a), (x, b)) for a, b in zip(ys, ys[1:])) and dx != 240: continue
        for a, b in zip(ys, ys[1:]): out.lin((x, a), (x, b), (x, a), 90, 0 if b - a < pe.NARROW else None)
        rep.append(('tank chain', q['h'], round(x), [round(b - a, 1) for a, b in zip(ys, ys[1:])])); return True
    rep.append(('tank chain NOT placed', q['h'])); return False


# ---------- 6 wall texts beside the wall
def wall_regions(doc):
    """polygons (outer + holes, even-odd) of every wall hatch = the hatched wall material"""
    res = []
    for h in doc.modelspace().query('HATCH'):
        if h.dxf.layer != '63_HATCH_KIR_OLE': continue
        paths = []
        for p in h.paths:
            if p.__class__.__name__ == 'PolylinePath': paths.append([(v[0], v[1]) for v in p.vertices])
            else:
                pts = [(e.start[0], e.start[1]) for e in p.edges if e.__class__.__name__ == 'LineEdge']
                if len(pts) >= 3: paths.append(pts)
        if paths:
            xs = [x for q in paths for x, y in q]; ys = [y for q in paths for x, y in q]; res.append(((min(xs), min(ys), max(xs), max(ys)), paths))
    return res


def in_wall(regions, pt_):
    x, y = pt_
    for (bx0, by0, bx1, by1), paths in regions:
        if not (bx0 <= x <= bx1 and by0 <= y <= by1): continue
        c = 0
        for poly in paths:
            n = len(poly); inside = False
            for i in range(n):
                a, b = poly[i], poly[(i + 1) % n]
                if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]: inside = not inside
            c += inside
        if c % 2 == 1: return True
    return False


TEXT_H = 24.0; CHAR_W = 0.6; TEXT_GAP = 12.0; PERP = 23.0; MAX_WALL = 150.0


def shift_wall_texts(doc, rep):
    """user's rule (yellow cloud, 2026-10-08): a continuous dim line crossing a wall carries the wall's item, but its TEXT must not sit on the wall: it moves along the line to the side,
    clear of the wall (text half width + 12), perpendicular position 23 from the line (the user's 20 on y=29626: 37 right of the wall centre)"""
    regions = wall_regions(doc); ms = doc.modelspace(); todo = []
    info = [t for t in dims_info(doc) if t[1] in ('h', 'v') and t[0].dxf.dimtype & 7 == 0]
    texts = collections.defaultdict(list)
    for d, k, p, q, line, m in info: texts[(k, round(line))].append(pt.text_pt(d))
    for d, k, p, q, line, m in info:
        if m > MAX_WALL: continue
        mid = ((p[0] + q[0]) / 2, p[1]) if k == 'h' else (p[0], (p[1] + q[1]) / 2)
        tp = pt.text_pt(d)
        if not in_wall(regions, mid) or not in_wall(regions, tp): continue
        perp = (tp[1] - line) if k == 'h' else (tp[0] - line)
        side = 1 if perp >= 0 else -1                                   # keep the text on the side of the line it is on now (above / left)
        half = 0.5 * CHAR_W * TEXT_H * len('%g' % round(m, 1))
        shift = m / 2 + half + TEXT_GAP; placed = None
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        for sgn in (1, -1):                                             # along the line: up / right first, else the other side
            c = (mx + sgn * shift, line + side * PERP) if k == 'h' else (line + side * PERP, my + sgn * shift)
            if in_wall(regions, c): continue
            if any(abs((o[0] - c[0]) if k == 'h' else (o[1] - c[1])) < 40 and abs((o[1] - c[1]) if k == 'h' else (o[0] - c[0])) < 30 for o in texts[(k, round(line))] if o != tp): continue
            placed = c; break
        if placed is None: rep.append(('wall text NOT shifted', d.dxf.handle, round(m, 1))); continue
        todo.append((d, k, placed, round(m, 1)))
    for d, k, loc, m in todo:
        x = d.dxf
        kw = dict(base=(x.defpoint.x, x.defpoint.y), p1=(x.defpoint2.x, x.defpoint2.y), p2=(x.defpoint3.x, x.defpoint3.y), angle=0 if k == 'h' else 90, dimstyle=x.dimstyle,
                  location=loc, dxfattribs={'layer': x.layer})
        if x.get('text', '<>') not in (None, '<>', ''): kw['text'] = x.text
        ms.delete_entity(d); g = x.get('geometry')
        if g and g in doc.blocks:
            try: doc.blocks.delete_block(g, safe=False)
            except Exception: pass
        ms.add_linear_dim(**kw).render(); rep.append(('wall text shifted', k, m, round(loc[0]), round(loc[1])))
    return len(todo)


# ---------- 5 + driver
def tiny(doc, kill):
    for d, k, p, q, line, m in dims_info(doc):
        if m < 8: kill.setdefault(d.dxf.handle, 'tiny dim %.1f' % m)


def run(doc, verbose=False):
    rep = []; kill = {}
    out = pe.Out(doc); nh = fill_holes(doc, out, rep)
    pier_dups(doc, kill)
    plans = row_chains(doc, rep, kill)
    todo_tanks = tanks(doc, kill, rep)
    tiny(doc, kill)
    pr.delete_dims(doc, set(kill))
    out = add_rows(doc, plans, rep)
    for q in todo_tanks: add_tank_chain(doc, out, q, rep)
    shift_wall_texts(doc, rep)
    return rep, kill


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float); ap.add_argument('--expect'); ap.add_argument('--dry', action='store_true'); ap.add_argument('-v', action='store_true')
    a = ap.parse_args()
    if a.expect and not filecmp.cmp(a.file, a.expect, shallow=False): sys.exit('ABORT: the file changed since it was last read (user saved?) - re-read it first')
    if a.box:
        inv0 = pe.inventory; bx = a.box
        def inv(doc):
            polys, big, circ = inv0(doc); ins = lambda b: b[0] >= bx[0] and b[2] <= bx[2] and b[1] >= bx[1] and b[3] <= bx[3]
            return [q for q in polys if ins(q['box'])], [t for t in big if ins(t[1])], [c for c in circ if bx[0] <= c['c'][0] <= bx[2] and bx[1] <= c['c'][1] <= bx[3]]
        pe.inventory = inv
    doc = ezdxf.readfile(a.file); n0 = len(doc.modelspace().query('DIMENSION'))
    rep, kill = run(doc, a.v)
    for h, r in sorted(kill.items(), key=lambda t: t[1]): print('DELETE', h, r)
    for r in rep: print(r)
    print('dimensions', n0, '->', len(doc.modelspace().query('DIMENSION')))
    if a.dry: print('dry run: nothing written'); return
    backup(a.file, 'continuity'); doc.saveas(a.file); print('saved in place', a.file)


if __name__ == '__main__': main()
