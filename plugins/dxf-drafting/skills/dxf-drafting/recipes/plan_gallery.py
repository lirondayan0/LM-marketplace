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
import plan_audit as pa
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


JOG = pa.JOG             # a wall face within JOG of a read face is a jog of the same opening
TOL_BEAM = 1.5
MIN_SKEW = pa.MIN_SKEW
SRC_LAYERS = ('82_KIR_OLE', '93_KORA', '9_KONTUR')


def universe(doc, box):
    """straight segments of every structural element in the box: vertical (x = c, y lo..hi), horizontal (y = c, x lo..hi), skewed (a, b). Beam LINES and polygon edges alike."""
    x0, x1, y0, y1 = box; V = []; H = []; S = []
    for e in doc.modelspace().query('LWPOLYLINE LINE'):
        if e.dxf.layer not in SRC_LAYERS: continue
        if e.dxftype() == 'LINE': p = [tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]]; closed = False
        else: p = pe.pts(e); closed = e.closed
        bx0, by0, bx1, by1 = pe.bb(p)
        if not (x0 <= bx0 and bx1 <= x1 and y0 <= by0 and by1 <= y1): continue
        if e.dxf.layer == '82_KIR_OLE' and (bx1 - bx0 >= pc.BIG or by1 - by0 >= pc.BIG): continue
        n = len(p)
        for i in range(n if closed else n - 1):
            a, b = p[i], p[(i + 1) % n]; L = pe.dist(a, b)
            if L < 1: continue
            d = dict(h=e.dxf.handle, layer=e.dxf.layer, closed=closed)
            if abs(a[0] - b[0]) < 1.5: V.append(dict(d, c=(a[0] + b[0]) / 2, lo=min(a[1], b[1]), hi=max(a[1], b[1])))
            elif abs(a[1] - b[1]) < 1.5: H.append(dict(d, c=(a[1] + b[1]) / 2, lo=min(a[0], b[0]), hi=max(a[0], b[0])))
            else: S.append(dict(d, a=a, b=b, L=L))
    return V, H, S


def read_vals(chains, axis):
    return sorted(u for ch in chains if ch['axis'] == axis for a, b, e in ch['items'] for u in (a, b))


def unread(uni, chains):
    V, H, S = uni; out = {'x': {}, 'y': {}}
    for segs, axis in ((V, 'x'), (H, 'y')):
        vals = read_vals(chains, axis)
        for sg in segs:
            tol = TOL_BEAM if sg['layer'] == '93_KORA' else JOG
            if pa.has_tol(vals, sg['c'], tol): continue
            out[axis].setdefault(round(sg['c'], 1), []).append(sg)
    return out


EXT_MAX = 300.0          # an unread face may be spliced into an existing chain whose line is at most this far from the element (extension line)


def insert_faces(chains, faces, axis):
    """splice an unread face into an EXISTING chain of that axis: the line crosses the element or is <= EXT_MAX away (extension line to the nearest point of the face),
    and runs through a clear span there (a continuous line is kept, no new line)"""
    left = {}
    for c, segs in sorted(faces.items()):
        best = None
        for ch in chains:
            if ch['axis'] != axis: continue
            rv = ch['v'] if axis == 'x' else -ch['v']        # real coordinate of the line (y for rows, x for columns)
            for sg in segs:
                d = max(0.0, sg['lo'] - rv, rv - sg['hi'])
                if d > EXT_MAX: continue
                for k, (a, b, e) in enumerate(ch['items']):
                    if e is None and a + MIN_SPAN < c < b - MIN_SPAN and (best is None or d < best[0]):
                        best = (d, ch, k, min(max(rv, sg['lo']), sg['hi']))
        if best is None: left[c] = segs; continue
        d, ch, k, ref = best; a, b, e = ch['items'][k]
        ch['items'][k:k + 1] = [(a, c, None), (c, b, None)]
        ch.setdefault('refs', {})[round(c, 1)] = ref if axis == 'x' else -ref      # ref in the chain's own v convention (uv)
    return left


def scan_faces(uni, axis, v):
    """every face crossing the scan line (axis x: horizontal line y = v; axis y: vertical line x = v), clustered"""
    V, H, S = uni; segs = V if axis == 'x' else H
    fs = sorted(sg['c'] for sg in segs if sg['lo'] - 1 <= v <= sg['hi'] + 1)
    out = []
    for f in fs:
        if out and f - out[-1] < MIN_SPAN: continue          # jog / duplicate face
        out.append(f)
    return out


def new_chains(out, uni, chains, faces, axis, rep):
    """remaining unread faces: greedy set cover by scan lines; each line carries EVERY face crossing it between its anchors (one continuous chain)"""
    xy = (lambda u, v: (u, v)) if axis == 'x' else (lambda u, v: (v, u))     # REAL coordinates here (the chain is stored with v = -x for columns)
    faces = dict(faces); guard = 0
    while faces and guard < 60:
        guard += 1
        cand = {}
        for c, segs in faces.items():
            for sg in segs:
                v = sg['lo'] + 10
                while v <= sg['hi'] - 10 + 1e-6:
                    cand.setdefault(round(v / 10) * 10, set()).add(c); v += 20
                cand.setdefault(round((sg['lo'] + sg['hi']) / 20) * 10, set()).add(c)
        if not cand: break
        best = sorted(cand.items(), key=lambda t: -len(t[1]))[:80]
        top = len(best[0][1]); scored = []
        for v, cs in best:
            if len(cs) < top * 0.7: continue
            fs = scan_faces(uni, axis, v)
            lo = min(cs); hi = max(cs)
            le = [f for f in fs if f <= lo + 1.5]; ri = [f for f in fs if f >= hi - 1.5]
            u0 = le[-2] if len(le) >= 2 and abs(le[-1] - lo) < 1.5 else (le[-1] if le else lo)
            u1 = ri[1] if len(ri) >= 2 and abs(ri[0] - hi) < 1.5 else (ri[0] if ri else hi)
            u0 = min(u0, lo); u1 = max(u1, hi)
            sel = [f for f in fs if u0 - 1 <= f <= u1 + 1]
            if len(sel) < 2: continue
            scored.append((-len(cs), cost(out, xy(sel[0], v), xy(sel[-1], v)), v, sel, cs))
        if not scored:
            break
        scored.sort(key=lambda t: (t[0], t[1]))
        _, c_, v, sel, cs = scored[0]
        cs = {c for c in cs if any(abs(c - f) < 1.5 for f in sel)}      # a face swallowed by the jog filter of scan_faces cannot be chained: dropped, never loops
        if not cs:
            for c in list(faces):
                if not any(abs(c - f) < 1.5 for f in scan_faces(uni, axis, v)): faces.pop(c)
            continue
        items = [(a, b, None) for a, b in zip(sel, sel[1:]) if b - a >= MIN_SPAN]
        chains.append(dict(axis=axis, v=v if axis == 'x' else -v, items=items, tag='cover', far={}, obst=c_))
        out.stripes.add(xy(sel[0], v), xy(sel[-1], v))
        rep.append((axis, 'cover chain', round(v), 'faces=%d' % len(cs), 'items=%d' % len(items), 'obstacles=%d' % c_))
        faces = {c: s_ for c, s_ in faces.items() if not any(abs(c - f) < 1.5 for f in sel)}
    return faces


def dedupe(chains, rep):
    """A feature is dimensioned ONCE: an interval (same two faces, same direction) that two chains both carry stays only on the chain with the most items; the other chain keeps the rest
    (it may fall into runs). Faces stay readable because the keeper has the same coordinates."""
    n = 0
    for axis in ('x', 'y'):
        cs = [c for c in chains if c['axis'] == axis]
        owner = {}
        for ch in sorted(cs, key=lambda c: (-len(c['items']), c['v'])):
            for a, b, e in ch['items']:
                owner.setdefault((round(a), round(b)), ch)
        for ch in cs:
            keep = [it for it in ch['items'] if owner[(round(it[0]), round(it[1]))] is ch]
            n += len(ch['items']) - len(keep); ch['items'] = keep
    rep.append(('duplicate items removed', n))
    return n


def skew_dims(out, uni, rep):
    """aligned dim on every skewed edge >= MIN_SKEW: opposite equal parallel edges of one element once (the western / southern one), outside the element on a free side"""
    V, H, S = uni; by = {}
    for sg in S:
        if sg['L'] >= MIN_SKEW: by.setdefault(sg['h'], []).append(sg)
    n = 0
    for h, segs in by.items():
        taken = []
        allp = [q for t in segs for q in (t['a'], t['b'])]
        cx = sum(q[0] for q in allp) / len(allp); cy = sum(q[1] for q in allp) / len(allp)
        for sg in sorted(segs, key=lambda t: (t['a'][0] + t['b'][0], t['a'][1] + t['b'][1])):
            ang = math.atan2(sg['b'][1] - sg['a'][1], sg['b'][0] - sg['a'][0]) % math.pi
            if any(abs(t['L'] - sg['L']) < 1 and abs(t['ang'] - ang) < .01 for t in taken): continue
            sg['ang'] = ang; taken.append(sg)
            a, b = sg['a'], sg['b']; L = sg['L']
            left = (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            side = -1 if (mid[0] - cx) * left[0] + (mid[1] - cy) * left[1] < 0 else 1      # +1 = left of a->b is outward
            o = 80
            for o in (80, 120, 170, 230, 300):
                pa_ = (a[0] + left[0] * o * side, a[1] + left[1] * o * side); pb_ = (b[0] + left[0] * o * side, b[1] + left[1] * o * side)
                if out.free(pa_, pb_): break
            out.aligned(a, b, o * side, 'skew' + h); n += 1
            rep.append(('skew edge', h, round(L, 1), o))
    return n


def run(doc, box, void=None, dry=False, verbose=False, replace=False):
    pc.load = box_load(box)
    if replace and not dry: print('removed old dims:', clear_dims(doc, box))
    out = pe.Out(doc); rep = []; chains = []
    # ---- phase 1: pier / wall chains (merged into continuous lines) with placement
    for axis in ('x', 'y'):
        P = pc.prep(pc.load(doc), axis)
        res, rot = pc.plan(doc, axis)
        vfaces = None
        if void: vfaces = (void[0], void[1]) if axis == 'x' else (void[2], void[3])
        groups = merge_chains(res)
        best_for_void = None
        if void:
            cx = (void[0] + void[1]) / 2
            def dist_void(g):
                if axis == 'x': return min((abs(lv - (void[2] - 1)) for lv in g['lvs'] if lv <= void[2]), default=1e9)
                return min(abs(-lv - cx) for lv in g['lvs'])
            cands = [g for g in groups if dist_void(g) < 1e9]
            if cands: best_for_void = min(cands, key=dist_void)
        xy = (lambda u, v: (u, v)) if axis == 'x' else (lambda u, v: (-v, u))
        for g in groups:
            items = g['items']
            if not items: continue
            if void and g is best_for_void: items = split_items(items, vfaces)
            far = {}
            for a, b, e in items:
                if e is None: continue
                for q in P:
                    if q['pier'] and q['u0'] - 1 <= a and b <= q['u1'] + 1 and abs(q['v0'] - e) < 1: far[(a, b)] = q['v1']
            u0, u1 = items[0][0], items[-1][1]
            cands = []
            for lv in g['lvs']:
                tops = [q['v1'] for q in P if q['pier'] and abs(q['v0'] - (lv + pc.OFF[axis])) < 120] or [lv + pc.OFF[axis]]
                cands += [(lv, 'near'), (lv - 60, 'near+60'), (max(tops) + 101, 'far'), (max(tops) + 160, 'far+60')]
            scored = [(cost(out, xy(u0, v), xy(u1, v)) + (0 if tag == 'near' else 0.5), v, tag) for v, tag in cands]
            c, v, tag = min(scored, key=lambda t: (t[0], t[1] != g['lvs'][0]))
            chains.append(dict(axis=axis, v=v, items=items, tag=tag, far=far, obst=c, merged=len(g['lvs'])))
            out.stripes.add(xy(u0, v), xy(u1, v))
    # ---- phase 2: coverage - every face of every beam / wall / column / contour must be readable in X and Y
    uni = universe(doc, box)
    for it in range(3):
        un = unread(uni, chains); n0 = sum(len(v) for v in un.values())
        for axis in ('x', 'y'): un[axis] = insert_faces(chains, un[axis], axis)
        for axis in ('x', 'y'): new_chains(out, uni, chains, un[axis], axis, rep)
        n1 = sum(len(v) for v in unread(uni, chains).values())
        rep.append(('coverage pass', it, 'unread faces %d -> %d' % (n0, n1)))
        if n1 == 0 or n1 >= n0: break
    dedupe(chains, rep)
    # ---- phase 3: draw
    for ch in chains:
        axis, v, items = ch['axis'], ch['v'], ch['items']; side_far = ch['tag'].startswith('far'); k = 0
        for a, b, e in items:
            ref = e
            if e is not None and side_far: ref = ch['far'].get((a, b), e)
            if ref is None: ref = v
            ra = ch.get('refs', {}).get(round(a, 1), ref); rb = ch.get('refs', {}).get(round(b, 1), ref)
            nk = None
            if b - a < NARROW: nk = k; k += 1
            if axis == 'x': out.lin((a, ra), (b, rb), (a, v), 0, nk)
            else: out.lin((-ra, a), (-rb, b), (-v, a), 90, nk)
        rep.append((axis, 'chain', round(v), ch['tag'], 'merged=%d' % ch.get('merged', 1), 'obstacles=%d' % ch['obst'], len(items), [round(b - a) for a, b, e in items] if verbose else ''))
    # ---- phase 4: skewed edges (piers, beams, contour, sloped walls)
    skew_dims(out, uni, rep)
    x0, x1, y0, y1 = box
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
