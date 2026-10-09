"""Recipe: DIMENSION PLAN of a slab / gallery (mezzanine) plan that sits inside a bigger file (ramla_base-dimplan.dxf, 'גלריה 1-', 2026-10-08).
  python plan_gallery.py FILE --box X0 X1 Y0 Y1 [--void X0 X1 Y0 Y1] [--dry] [-v] [--expect MTIME]
Same office rules as plan-dimensions.md (dim_100, layer 36_MIDA_CLALI, face to face, continuous chains, fewest dims), applied to a plan whose
structure is piers/walls (82_KIR_OLE) + beam edges (93_KORA) + slab contour (9_KONTUR):
 1. Pier ROWS (X chains) and COLUMNS (Y chains) from plan_chains.py (monkey-patched load(): only polygons inside --box, the parcel / building outline
    polygons >= 9000 are dropped so chains end at the first/last pier or wall, not at the site boundary). Cores (lift / stair / MAMAD cells) are covered
    because the chains slice their walls (wall | clear | wall).
 2. Chain SIDE: default side of plan_chains (row below, column right of the piers); when that line crosses texts / symbols of the plan (bay notes,
    cut marks) the line is moved to the other face (+101) or further out, whichever hits the fewest obstacles. Extension lines follow the side.
 3. VOID (--void box, the 'חלל כפול' hatch rectangle): its two x faces split the span of the row chain nearest below it, its two y faces split the span
    of the middle column chain, so position AND size of the opening are readable without extra dim lines.
 4. Skewed east piers (4-vertex, not axis aligned): ONE aligned length dim on the west edge, offset 80 (thickness = the horizontal item of the rows).
 5. Overall: slab contour (largest 9_KONTUR polyline in the box) width south (-160) and height west (-160).
Not dimensioned (listed): level tags, beam sizes (already labelled 30/65 ...), polygons outside the box.  UNVERIFIED: chain side choices, void split, overall."""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import plan_chains as pc
import plan_elements as pe
import ezdxf
from dxflib import backup

NARROW = pe.NARROW
MIN_SPAN = 10.0          # no dim shorter than this (rounding artefacts of skewed piers)


def box_load(box):
    orig = pc.load
    def load(doc):
        x0, x1, y0, y1 = box
        return [q for q in orig(doc) if x0 <= q['x0'] and q['x1'] <= x1 and y0 <= q['y0'] and q['y1'] <= y1 and q['x1'] - q['x0'] < pc.BIG and q['y1'] - q['y0'] < pc.BIG]
    return load


def cost(out, a, b, pad=18):
    """obstacle weight of a candidate dim line a-b (text / symbol boxes = 1, parallel dim stripes = 100)"""
    kind = 'h' if abs(a[1] - b[1]) < 1e-6 else 'v'
    x0, y0, x1, y1 = min(a[0], b[0]) - pad, min(a[1], b[1]) - pad, max(a[0], b[0]) + pad, max(a[1], b[1]) + pad
    c = 0
    for bx0, by0, bx1, by1, k in out.stripes.boxes:
        if x0 < bx1 and x1 > bx0 and y0 < by1 and y1 > by0:
            if k == '*': c += 1
            elif k == kind: c += 100
    return c



MERGE_DIST = 450.0       # chains of one axis whose default lines are closer than this are merged into ONE line when their items do not conflict
WALL_MAX = 60.0          # an item without extension line this thin is a wall (solid); wider ones are clear spans
def merge_items(A, B):
    """Combine two chains (lists of (a, b, ext|None)) into one continuous list, or None when they conflict.
    Finest items win (sorted by width); exact duplicates are measured once; a wide clear span that overlaps other items is dropped and the gaps
    are re-filled with spans (only inside a dropped span); a pier/wall overlapped by a different item is trimmed (pier) or the merge is refused (wall)."""
    acc = []; dropped = []
    for it in sorted(A + B, key=lambda t: (t[1] - t[0], t[0])):
        a, b, e = it
        ov = [x for x in acc if x[0] < b - 1 and x[1] > a + 1]
        if not ov: acc.append(it); continue
        if any(abs(x[0] - a) < 1 and abs(x[1] - b) < 1 for x in ov): continue
        if e is None and b - a > WALL_MAX: dropped.append(it); continue
        if e is None: return None
        pieces = [(a, b)]
        for x in ov:
            new = []
            for p, q in pieces:
                if x[1] <= p or x[0] >= q: new.append((p, q))
                else:
                    if x[0] - p >= MIN_SPAN: new.append((p, x[0]))
                    if q - x[1] >= MIN_SPAN: new.append((x[1], q))
            pieces = new
        if not pieces: return None
        acc += [(p, q, e) for p, q in pieces]
    acc.sort(key=lambda t: (t[0], t[1])); out = []
    for i, it in enumerate(acc):
        if out and it[0] - out[-1][1] > 1:
            g0, g1 = out[-1][1], it[0]
            if g1 - g0 < MIN_SPAN: pass
            elif any(d[0] - 1 <= g0 and g1 <= d[1] + 1 for d in dropped): out.append((g0, g1, None))
            else: return None
        out.append(it)
    return out


def merge_chains(res):
    """res = [(anchor, lv, items, nm)] -> [dict(lvs, items, nm)] merged greedily (sorted by line)"""
    groups = [dict(lvs=[lv], anchors=[anchor], items=[it for it in items if it[1] - it[0] >= MIN_SPAN], nm=nm) for anchor, lv, items, nm in sorted(res, key=lambda r: r[1])]
    changed = True
    while changed:
        changed = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                gi, gj = groups[i], groups[j]
                if min(abs(x - y) for x in gi['lvs'] for y in gj['lvs']) > MERGE_DIST: continue
                m = merge_items(gi['items'], gj['items'])
                if m is None: continue
                groups[i] = dict(lvs=gi['lvs'] + gj['lvs'], anchors=gi['anchors'] + gj['anchors'], items=m, nm=gi['nm'] + gj['nm']); del groups[j]; changed = True; break
            if changed: break
    return groups


def split_items(items, faces):
    out = []
    for a, b, e in items:
        cut = sorted(f for f in faces if a + 40 < f < b - 40) if e is None else []
        pts = [a] + cut + [b]
        for p, q in zip(pts, pts[1:]): out.append((p, q, e))
    return out


def clear_dims(doc, box):
    """delete the DIMENSION entities (and their anonymous blocks) whose dimension line lies in the box: for re-running over an earlier output"""
    x0, x1, y0, y1 = box; n = 0
    for d in list(doc.modelspace().query('DIMENSION')):
        p = d.dxf.defpoint
        if x0 - 400 <= p.x <= x1 + 400 and y0 - 400 <= p.y <= y1 + 400 and d.dxf.layer == pc.LAYER:
            g = d.dxf.get('geometry')
            doc.modelspace().delete_entity(d)
            if g and g in doc.blocks: doc.blocks.delete_block(g, safe=False)
            n += 1
    return n


def run(doc, box, void=None, dry=False, verbose=False, replace=False):
    pc.load = box_load(box)
    if replace and not dry: print('removed old dims:', clear_dims(doc, box))
    out = pe.Out(doc); rep = []
    for axis in ('x', 'y'):
        P = pc.prep(pc.load(doc), axis)
        res, rot = pc.plan(doc, axis)
        # void faces: split the chain closest to the void centre (row below the void / the middle column)
        vfaces = None
        if void:
            vx0, vx1, vy0, vy1 = void
            vfaces = (vx0, vx1) if axis == 'x' else (vy0, vy1)
        groups = merge_chains(res)
        best_for_void = None
        if void:
            cx = (void[0] + void[1]) / 2
            def dist_void(g):
                if axis == 'x': return min((abs(lv - (void[2] - 1)) for lv in g['lvs'] if lv <= void[2]), default=1e9)
                return min(abs(-lv - cx) for lv in g['lvs'])
            cands = [g for g in groups if dist_void(g) < 1e9]
            if cands: best_for_void = min(cands, key=dist_void)
        for g in groups:
            items = g['items']
            if not items: continue
            if void and g is best_for_void: items = split_items(items, vfaces)
            far = {}                                      # far face of every pier item (other side of the line)
            for a, b, e in items:
                if e is None: continue
                for q in P:
                    if q['pier'] and q['u0'] - 1 <= a and b <= q['u1'] + 1 and abs(q['v0'] - e) < 1: far[(a, b)] = q['v1']
            xy = (lambda u, v: (u, v)) if axis == 'x' else (lambda u, v: (-v, u))
            u0, u1 = items[0][0], items[-1][1]
            cands = []
            for lv in g['lvs']:
                tops = [q['v1'] for q in P if q['pier'] and abs(q['v0'] - (lv + pc.OFF[axis])) < 120] or [lv + pc.OFF[axis]]
                cands += [(lv, 'near'), (lv - 60, 'near+60'), (max(tops) + 101, 'far'), (max(tops) + 160, 'far+60')]
            scored = [(cost(out, xy(u0, v), xy(u1, v)) + (0 if tag == 'near' else 0.5), v, tag) for v, tag in cands]
            c, v, tag = min(scored, key=lambda t: (t[0], t[1] != g['lvs'][0]))
            side_far = tag.startswith('far'); k = 0
            for a, b, e in items:
                ref = e
                if e is not None and side_far: ref = far.get((a, b), e)
                if ref is None: ref = v
                nk = None
                if b - a < NARROW: nk = k; k += 1
                if axis == 'x': out.lin((a, ref), (b, ref), (a, v), 0, nk)
                else: out.lin((-ref, a), (-ref, b), (-v, a), 90, nk)
            out.stripes.add(xy(u0, v), xy(u1, v))
            rep.append((axis, 'chain', round(v), tag, 'merged=%d' % len(g['lvs']), 'obstacles=%d' % c, len(items), [round(b - a) for a, b, e in items] if verbose else ''))
    # skewed east piers: one aligned length on the west edge
    x0, x1, y0, y1 = box
    n_sk = 0
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != pc.SRC or not e.closed: continue
        p = pe.pts(e)
        if len(p) != 4: continue
        bx0, by0, bx1, by1 = pe.bb(p)
        if not (x0 <= bx0 and bx1 <= x1 and y0 <= by0 and by1 <= y1) or pe.is_rect(p): continue
        if max(bx1 - bx0, by1 - by0) > 260 or min(bx1 - bx0, by1 - by0) > 100: continue   # piers only, not skewed rooms
        edges = sorted([(pe.dist(p[i], p[(i + 1) % 4]), p[i], p[(i + 1) % 4]) for i in range(4)], reverse=True)[:2]
        L, a, b = min(edges, key=lambda t: (t[1][0] + t[2][0]))     # the longer pair, the western one
        if L < MIN_SPAN: continue
        nx, ny = (b[1] - a[1]) / L, -(b[0] - a[0]) / L            # a normal; make it point west
        if nx > 0: nx, ny = -nx, -ny
        left = (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)
        sgn = 1 if left[0] * nx + left[1] * ny > 0 else -1
        out.aligned(a, b, 80 * sgn, 'skew' + e.dxf.handle); n_sk += 1
        rep.append(('skewed pier length', e.dxf.handle, round(L, 1)))
    # overall of the slab contour
    cont = [e for e in doc.modelspace().query('LWPOLYLINE') if e.dxf.layer == pe.CONT and e.closed and len(e) > 8]
    cont = [e for e in cont if x0 <= pe.bb(pe.pts(e))[0] and pe.bb(pe.pts(e))[2] <= x1 and y0 <= pe.bb(pe.pts(e))[1] and pe.bb(pe.pts(e))[3] <= y1]
    if cont:
        e = max(cont, key=lambda q: (pe.bb(pe.pts(q))[2] - pe.bb(pe.pts(q))[0]) * (pe.bb(pe.pts(q))[3] - pe.bb(pe.pts(q))[1]))
        cx0, cy0, cx1, cy1 = pe.bb(pe.pts(e))
        yl = cy0 - 160
        while not out.free((cx0, yl), (cx1, yl)) and yl > cy0 - 400: yl -= 60
        out.lin((cx0, cy0), (cx1, cy0), (cx0, yl), 0); out.stripes.add((cx0, yl), (cx1, yl))
        xl = cx0 - 160
        while not out.free((xl, cy0), (xl, cy1)) and xl > cx0 - 400: xl -= 60
        out.lin((cx0, cy0), (cx0, cy1), (xl, cy0), 90); out.stripes.add((xl, cy0), (xl, cy1))
        rep.append(('overall', e.dxf.handle, round(cx1 - cx0), round(cy1 - cy0)))
    rep.append(('new dimensions', out.n))
    return out, rep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True)
    ap.add_argument('--void', nargs=4, type=float); ap.add_argument('--dry', action='store_true'); ap.add_argument('--replace', action='store_true', help='first delete the dims already in the box'); ap.add_argument('-v', action='store_true')
    ap.add_argument('--expect', type=float, help='abort when the file mtime differs (user saved meanwhile)'); ap.add_argument('-o')
    a = ap.parse_args()
    if a.expect and abs(os.path.getmtime(a.file) - a.expect) > 1: sys.exit('file changed since it was read: re-run markup / diff first')
    doc = ezdxf.readfile(a.file)
    out, rep = run(doc, tuple(a.box), tuple(a.void) if a.void else None, a.dry, a.v, a.replace)
    for r in rep: print(r)
    if a.dry: return
    if a.o: doc.saveas(a.o); print('saved', a.o); return
    open(a.file, 'ab').close()   # PermissionError when the file is open in CAD
    backup(a.file, 'gallery'); doc.saveas(a.file); print('saved', a.file)


if __name__ == '__main__': main()
