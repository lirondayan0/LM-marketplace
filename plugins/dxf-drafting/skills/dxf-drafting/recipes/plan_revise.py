"""Recipe: REVISE a dimension plan from the user's two cloud colours, IN PLACE (ramla_base-dimplan.dxf, 2026-10-08).
  python plan_revise.py FILE --chains CHAINS_FILE [--expect SNAPSHOT] [--dry] [-v]
Clouds (layer SHINUIM-TIKUNIM): RED (no colour override) = example of a dim to DELETE; BLUE (ACI 4) = example of a dim to ADD / ADJUST. Rules, from the user's examples + earlier tidy rules:
 R1 red clouds: delete the dims they hold (see plan_tidy.clouds / text_pt); long OLD chain dims only touching a cloud stay.
 R2 no diameter dims on circles; old horizontal 'size' dims measured on a skewed pier (40.2 / 34.8) go (red examples); duplicates (same points) and my dims repeating an interval another dim measures go.
 B1 (blue, block B chains 3810/3811/3854) every pit block gets the SAME three vertical face chains the user adjusted on block B (one per wall line, items between the vertices of that line) + the overall height;
    block B's chains are copied to the other block by translation, each end snapped to the nearest real vertex (<= 25) on its face line. My earlier merged west chain on that block is replaced.
 B2 (blue, east piers) every skewed pier gets BOTH size dims like the examples: length on the west side, thickness below, aligned dims at offset 80 / 77 (rows 203 / 123 long); my older far-off versions (offset 140+) are replaced.
 B3 (blue 3703) a size dim must sit next to its element and not cross another chain: 104E is re-placed on the first free side (offset 80..).
Writes into FILE after a timestamped snapshot (dxflib.backup). --expect = a copy of the file as last read: abort when FILE differs (the user may have saved meanwhile)."""
import argparse, filecmp, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from dxflib import *
import plan_elements as pe, plan_tidy as pt

LAYER, STYLE = pe.LAYER, pe.STYLE
LEN_OFF, THK_OFF = 80.0, 77.0          # user's blue examples (85 / 77 on the 123 row, 80 on pier 1049)
FAMILIES = ((4, 14), (3, 8))           # (w, h)/15 of the skewed east piers: 59x203, 46x123


def cloud_colour(doc):
    red, blue = [], []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != pt.CLOUD_LAYER or not e.closed: continue
        x0, y0, x1, y1 = pe.bb(pe.pts(e)); t = (e.dxf.handle, x0, y0, x1, y1)
        (blue if e.dxf.get('color', 256) == 4 else red).append(t)
    return red, blue


def delete_dims(doc, handles):
    ms = doc.modelspace(); n = 0
    for e in list(ms.query('DIMENSION')):
        if e.dxf.handle in handles:
            name = e.dxf.get('geometry'); ms.delete_entity(e); n += 1
            if name and name in doc.blocks:
                try: doc.blocks.delete_block(name, safe=False)
                except Exception: pass
    return n


def vertices(polys):
    return [(x, y) for q in polys for x, y in q['p']]


def snap(vs, x, y, tol=25.0):
    best = None
    for vx, vy in vs:
        if abs(vx - x) <= 3 and abs(vy - y) <= tol and (best is None or abs(vy - y) < abs(best - y)): best = vy
    return best


def plan_deletes(doc, chains_doc, red, polys, rot, boxes):
    old = {e.dxf.handle for e in chains_doc.modelspace()}; dims = list(doc.modelspace().query('DIMENSION')); kill = {}
    def mark(d, r): kill.setdefault(d.dxf.handle, r)
    for d in dims:                                                           # R1
        tx, ty = pt.text_pt(d); la, lb = pt.dim_line(d)
        for h, x0, y0, x1, y1 in red:
            on_line = all(x0 - 5 <= px <= x1 + 5 and y0 - 5 <= py <= y1 + 5 for px, py in (la, lb))
            if (x0 <= tx <= x1 and y0 <= ty <= y1) or on_line:
                if d.dxf.handle in old and d.get_measurement() > pt.SHORT: continue
                mark(d, 'R1 red cloud ' + h)
    for h, x0, y0, x1, y1 in red:                                            # small red cloud hugging an element: nearest short dim text
        if max(x1 - x0, y1 - y0) >= pt.SMALL or any(r.endswith(h) for r in kill.values()): continue
        best = None
        for d in dims:
            if d.get_measurement() > pt.SHORT or d.dxf.dimtype & 7 not in (0, 1): continue
            tx, ty = pt.text_pt(d); dd = math.hypot(max(x0 - tx, 0, tx - x1), max(y0 - ty, 0, ty - y1))
            if dd <= pt.NEAR and (best is None or dd < best[0]): best = (dd, d)
        if best: mark(best[1], 'R1 red cloud ' + h + ' (nearest)')
    for d in dims:                                                           # R2
        if d.dxf.dimtype & 7 in (3, 4): mark(d, 'R2 diameter')
    skew_ids = [q for q in rot if (round(q['w'] / 15), round(q['hgt'] / 15)) in FAMILIES]
    for d in dims:                                                           # old horizontal size dims on skewed piers (not the aligned ones along an edge)
        if d.dxf.handle not in old or d.dxf.dimtype & 7 != 0 or pt.axis_of(d) not in ('h', 'v'): continue
        (ax, ay), (bx, by) = pt.pair(d)
        for q in skew_ids:
            x0, y0, x1, y1 = q['box']
            if all(x0 - 4 <= px <= x1 + 4 and y0 - 4 <= py <= y1 + 4 for px, py in ((ax, ay), (bx, by))): mark(d, 'R2 old horizontal size ' + q['h'])
    seen = {}
    for d in sorted(dims, key=lambda d: (d.dxf.handle not in old, int(d.dxf.handle, 16))):
        if d.dxf.handle in kill or d.dxf.dimtype & 7 != 0: continue
        k = (pt.axis_of(d),) + tuple(sorted(pt.pair(d)))
        if k in seen: mark(d, 'R2 duplicate of ' + seen[k])
        else: seen[k] = d.dxf.handle
    return kill, old


def block_pair(doc, blue):
    """(example block B, target block A, dx, dy, example dim handles): B = the block whose face chains sit inside the blue clouds"""
    polys, big, circles = pe.inventory(doc); frames = []
    for q in sorted([q for q in polys if q['layer'] == pe.KORA and q['w'] > 500 and q['hgt'] > 500 and pe.is_rect(q['p'])], key=lambda q: q['w']):
        if not any(abs(q['box'][0] - t['box'][0]) < 20 and abs(q['box'][1] - t['box'][1]) < 20 for t in frames): frames.append(q)
    ex = []
    for d in doc.modelspace().query('DIMENSION'):
        la, lb = pt.dim_line(d)
        if pt.axis_of(d) == 'v' and any(all(x0 - 5 <= px <= x1 + 5 and y0 - 5 <= py <= y1 + 5 for px, py in (la, lb)) for h, x0, y0, x1, y1 in blue): ex.append(d)
    return frames, ex, polys


def add_block_chains(doc, rep, mine_handles, kill):
    red, blue = cloud_colour(doc)
    frames, ex, polys = block_pair(doc, blue)
    ex = [d for d in ex if d.dxf.handle not in kill]
    if len(frames) < 2 or not ex: rep.append(('B1 skipped: no example chains / blocks',)); return 0, []
    def inside(f, d):
        (ax, ay), (bx, by) = pt.pair(d); x0, y0, x1, y1 = f['box']; return x0 - 200 <= ax <= x1 + 200 and y0 - 200 <= min(ay, by) <= y1 + 200
    B = next(f for f in frames if any(inside(f, d) for d in ex)); A = next(f for f in frames if f is not B)
    dx, dy = A['box'][0] - B['box'][0], A['box'][1] - B['box'][1]
    vs = vertices([q for q in polys if q['layer'] in (pe.WALL, pe.KORA)]); made = []; ms = doc.modelspace(); unsnapped = 0
    for d in sorted(ex, key=lambda d: (round(d.dxf.defpoint.x), d.dxf.defpoint2.y)):
        (ax, ay), (bx, by) = pt.pair(d)
        x_ref = ax + dx; y1 = snap(vs, x_ref, ay + dy); y2 = snap(vs, x_ref, by + dy)
        if y1 is None or y2 is None: unsnapped += 1
        y1 = ay + dy if y1 is None else y1; y2 = by + dy if y2 is None else y2
        line_x = d.dxf.defpoint.x + dx
        made.append((x_ref, y1, y2, line_x))
    # extension points of a chain item must sit at the face: the example dims already carry them
    for x_ref, y1, y2, line_x in made:
        ms.add_linear_dim(base=(line_x, y1), p1=(x_ref, y1), p2=(x_ref, y2), angle=90, dimstyle=STYLE, dxfattribs={'layer': LAYER}).render()
    ref = [d for d in doc.modelspace().query('DIMENSION') if pt.axis_of(d) == 'v' and d.dxf.handle not in kill and abs(pt.pair(d)[0][0] - B['box'][2]) < 3 and abs(abs(pt.pair(d)[1][1] - pt.pair(d)[0][1]) - (B['box'][3] - B['box'][1] + 60)) < 40 and d.dxf.defpoint.x > B['box'][2] + 50]
    ext = [b for b in pt.block_boxes(doc)[0]]
    if ref:
        tb = next((b for b in ext if abs(b[1] - A['box'][0]) < 5), None)
        if tb and not any(pt.axis_of(d) == 'v' and abs(pt.pair(d)[0][0] - tb[3]) < 3 and abs(abs(pt.pair(d)[1][1] - pt.pair(d)[0][1]) - (tb[4] - tb[2])) < 3 for d in doc.modelspace().query('DIMENSION')):
            r0 = ref[0]; x_line = tb[3] + (r0.dxf.defpoint.x - pt.pair(r0)[0][0])
            ms.add_linear_dim(base=(x_line, tb[2]), p1=(tb[3], tb[2]), p2=(tb[3], tb[4]), angle=90, dimstyle=STYLE, dxfattribs={'layer': LAYER}).render()
            rep.append(('B1 overall height added', round(tb[4] - tb[2]), 'line x', round(x_line)))
    rep.append(('B1 chains copied to the second block', len(made), 'unsnapped ends', unsnapped, 'dx,dy', round(dx, 1), round(dy, 1)))
    # overall height like the example block's (kept unless the target already has one)
    return len(made), [(A, B, dx, dy)]


def pier_dims(doc, rep, mine_aligned_to_remove):
    polys, big, circles = pe.inventory(doc); n = 0
    quads = [q for q in polys if q['layer'] == pe.WALL and len(q['p']) == 4 and not pe.is_rect(q['p']) and (round(q['w'] / 15), round(q['hgt'] / 15)) in FAMILIES]
    return quads


def edges_of(q):
    """(length edge, thickness edge) of a skewed pier: of the two long sides the WEST one, of the two short sides the SOUTH one (where the user's examples put them)"""
    p = q['p']; es = [(p[i], p[(i + 1) % 4]) for i in range(4)]
    order = sorted(range(4), key=lambda i: pe.dist(*es[i]))
    short, long_ = order[:2], order[2:]
    mid = lambda e: ((e[0][0] + e[1][0]) / 2, (e[0][1] + e[1][1]) / 2)
    return min((es[i] for i in long_), key=lambda e: mid(e)[0]), min((es[i] for i in short), key=lambda e: mid(e)[1])


def left_normal(a, b):
    L = pe.dist(a, b); return (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)


def has_dim_on(doc, a, b, tol=3.0):
    for d in doc.modelspace().query('DIMENSION'):
        p, q = (d.dxf.defpoint2.x, d.dxf.defpoint2.y), (d.dxf.defpoint3.x, d.dxf.defpoint3.y)
        if (pe.dist(p, a) < tol and pe.dist(q, b) < tol) or (pe.dist(p, b) < tol and pe.dist(q, a) < tol): return True
    return False


def place_size(out, a, b, want, offs, check=False):
    """aligned dim on edge a-b, on the side of unit vector `want` (west for lengths, south for thickness) at offs[0] (the user's example offset).
    check=True (a pier next to a chain): take the first free (side, offset) instead - the dim must neither cross another chain nor sit far from its element"""
    nx, ny = left_normal(a, b)
    pref = 1 if nx * want[0] + ny * want[1] > 0 else -1
    if not check:
        out.aligned(a, b, offs[0] * pref, 'size'); return offs[0] * pref
    for o in offs:
        for sgn in (pref, -pref):
            if out.free((a[0] + nx * sgn * o, a[1] + ny * sgn * o), (b[0] + nx * sgn * o, b[1] + ny * sgn * o)):
                out.aligned(a, b, o * sgn, 'size'); return o * sgn
    out.aligned(a, b, offs[0] * pref, 'size-forced'); return offs[0] * pref


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--chains', required=True); ap.add_argument('--expect'); ap.add_argument('--dry', action='store_true'); ap.add_argument('-v', action='store_true')
    a = ap.parse_args()
    if a.expect and not filecmp.cmp(a.file, a.expect, shallow=False): sys.exit('ABORT: the file changed since it was last read (user saved?) - re-read it first')
    doc = ezdxf.readfile(a.file); cd = ezdxf.readfile(a.chains); rep = []
    red, blue = cloud_colour(doc); boxes, rot, circles = pt.block_boxes(doc); polys, big, circ = pe.inventory(doc)
    kill, old = plan_deletes(doc, cd, red, polys, rot, boxes)
    quads = [q for q in polys if q['layer'] == pe.WALL and len(q['p']) == 4 and not pe.is_rect(q['p']) and (round(q['w'] / 15), round(q['hgt'] / 15)) in FAMILIES + ((8, 13),)]
    # B2/B3: my aligned dims on skewed piers: kept when already like the user's examples (side + offset 70..95), else replaced by the uniform pair
    for d in doc.modelspace().query('DIMENSION'):
        if d.dxf.handle in old or d.dxf.dimtype & 7 not in (0, 1) or pt.axis_of(d) != 'd': continue
        p, q_ = (d.dxf.defpoint2.x, d.dxf.defpoint2.y), (d.dxf.defpoint3.x, d.dxf.defpoint3.y); dl = (d.dxf.defpoint.x, d.dxf.defpoint.y)
        for q in quads:
            vs = q['p']; (la, lb), (ta, tb) = edges_of(q)
            for (ea, eb), want in (((la, lb), (-1.0, 0.0)), ((ta, tb), (0.0, -1.0))):
                if not ((pe.dist(p, ea) < 3 and pe.dist(q_, eb) < 3) or (pe.dist(p, eb) < 3 and pe.dist(q_, ea) < 3)): continue
                L = pe.dist(ea, eb); mx, my = (ea[0] + eb[0]) / 2, (ea[1] + eb[1]) / 2
                nx, ny = left_normal(ea, eb); off = (dl[0] - mx) * nx + (dl[1] - my) * ny
                toward = (nx * (1 if off > 0 else -1)) * want[0] + (ny * (1 if off > 0 else -1)) * want[1] > 0
                if 70 <= abs(off) <= 95 and toward and not (round(q['w'] / 15), round(q['hgt'] / 15)) == (8, 13): continue      # already like the example
                kill.setdefault(d.dxf.handle, 'B2 replaced by uniform size dim ' + q['h'])
    # my merged face chain on the target block goes (replaced by B1)
    frames_all = pt.block_boxes(doc)[0]
    for d in doc.modelspace().query('DIMENSION'):
        if d.dxf.handle in old or d.dxf.dimtype & 7 != 0 or pt.axis_of(d) != 'v' or d.dxf.handle in kill: continue
        (ax, ay), (bx, by) = pt.pair(d)
        for h, x0, y0, x1, y1 in frames_all:
            if abs(ax - bx) < 2 and y0 - 150 <= min(ay, by) and max(ay, by) <= y1 + 150 and (abs(ax - x0) < 2 or abs(ax - x1) < 2) and pt.axis_of(d) == 'v' and not blue_has(blue, d):
                if not (abs(min(ay, by) - y0) < 2 and abs(max(ay, by) - y1) < 2): kill.setdefault(d.dxf.handle, 'B1 my merged face chain replaced ' + h)
    by = collections.Counter(r.split(' ')[0] for r in kill.values()); print('delete', len(kill), dict(by))
    if a.v:
        for h, r in sorted(kill.items(), key=lambda t: t[1]): print('  ', h, r)
    n_before = len(doc.modelspace().query('DIMENSION'))
    delete_dims(doc, set(kill))
    nb, info = add_block_chains(doc, rep, set(), kill)
    out = pe.Out(doc)
    for q in sorted(quads, key=lambda q: (round(q['w']), q['box'][1])):
        (la, lb), (ta, tb) = edges_of(q)
        chk = (round(q['w'] / 15), round(q['hgt'] / 15)) == (8, 13)          # 104E sits next to a chain: collision-checked
        if chk:                                   # next to a chain on its south side: thickness goes on the NORTH end of the pier (B3)
            p4 = q['p']; es4 = [(p4[i], p4[(i + 1) % 4]) for i in range(4)]; sh = sorted(es4, key=lambda e: pe.dist(*e))[:2]
            ta, tb = max(sh, key=lambda e: (e[0][1] + e[1][1]) / 2)
        for (ea, eb), want, off, nm in (((la, lb), (-1.0, 0.0), LEN_OFF, 'length'), ((ta, tb), (0.0, 1.0) if chk else (0.0, -1.0), THK_OFF, 'thickness')):
            if has_dim_on(doc, ea, eb): rep.append(('size dim kept (exists)', q['h'], nm)); continue
            o = place_size(out, ea, eb, want, (off, 110.0, 140.0, 170.0) if chk else (off,), chk); rep.append(('size dim', q['h'], nm, round(o)))
    for r in rep: print(r)
    n_after = len(doc.modelspace().query('DIMENSION')); print('dimensions', n_before, '->', n_after)
    if a.dry: print('dry run: nothing written'); return
    backup(a.file, 'revise'); doc.saveas(a.file); print('saved in place', a.file)


def blue_has(blue, d):
    la, lb = pt.dim_line(d)
    return any(all(x0 - 5 <= px <= x1 + 5 and y0 - 5 <= py <= y1 + 5 for px, py in (la, lb)) for h, x0, y0, x1, y1 in blue)


if __name__ == '__main__': main()
