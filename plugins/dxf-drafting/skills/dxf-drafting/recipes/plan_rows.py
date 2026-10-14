"""Recipe: ROW-BASED DIMENSION LINES for a slab plan - the user's example rules of 2026-10-13 (conventions/plan-dimensions.md RULES 1-4).
  python plan_rows.py FILE --box X0 Y0 X1 Y1 [--dry] [--expect MTIME] [-v] [-o OUT]
 1. every line is ONE continuous chain from the beginning to the end of the plan (outer face of the perimeter wall to the other): items = every face the line crosses;
 2. a line states the elements of ONE SIDE only: its extension lines reach elements on the chosen side (distance <= EXT_MAX = 100 cm = 1 m, user 2026-10-14; was 250), never both sides; the line runs just outside the row it serves;
 3. EVERY element the line crosses is an item (walls, piers, beams, slab edge, openings, hidden items on 15_DASHED) - nothing is skipped silently;
 4. the text of a wall item is moved slightly aside (along the line ~ item/2 + text half width + 12, perpendicular 26) so it is readable; narrow items stagger.
Coverage is per ELEMENT FACE (segment), not per coordinate: each straight face of walls / piers / beams / slab edge / openings / hidden lines must be crossed by a line or reached by its extension
(<= EXT_MAX, one side). Dimensions only along X and Y. The user's own example lines already in the file are kept untouched and count as coverage. Existing dims are never deleted.
Greedy set cover (fewest lines), candidates on a 10-unit grid inside the perimeter, parallel lines >= MIN_GAP apart, never along an element edge. In place after a timestamped snapshot."""
import argparse, math, os, sys, bisect
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
import plan_elements as pe
import plan_continuity as pcn
from dxflib import backup, step_groups, blue_clouds, flight_chains
try:
    from scipy.optimize import milp, LinearConstraint, Bounds
    from scipy.sparse import lil_matrix
    HAVE_MILP = True
except Exception: HAVE_MILP = False

LAYERS = ('82_KIR_OLE', '93_KORA', '9_KONTUR', '15_DASHED')      # 6_HATCH is NOT dimensioned: user 2026-10-13 - the closed 6_HATCH polygon is only an informational mark of a double-height space around an opening
MIN_SEG = 20.0; MIN_ITEM = 12.5; JOG = 12.0; EXT_MAX = float(os.environ.get("DIM_REACH", "100")); MIN_GAP = 60.0; STEP = 10.0; AVOID = 3.0; BIGMAX = 15000.0
NO_MILP = False
TAG = 'CLAUDE_ROWS'; PERP = 26.0; GAP = 12.0; TEXT_H = 24.0; CHAR_W = 0.6; WALL_TEXT_MAX = 150.0; NARROW = 45.0


def is_tooth(p, closed):
    """bearing tooth of a plank (Luchad) beam: thin 15_DASHED U-strip = 4 vertices, the two end edges <= 20, the long edge >= 100 (user 2026-10-13: the tooth is NOT dimensioned, only the overall beam width = the two 93_KORA faces)"""
    if closed or len(p) != 4: return False
    L = [pe.dist(p[i], p[i + 1]) for i in range(3)]
    return L[0] <= 20 and L[2] <= 20 and L[1] >= 100


def load(doc, box):
    """V: vertical faces (c = x, lo..hi = y), H: horizontal faces (c = y, lo..hi = x), S: skewed edges; perimeter bbox of the big 82_KIR_OLE outlines"""
    x0, y0, x1, y1 = box; V = []; H = []; S = []; per = None; T = []
    for e in doc.modelspace().query('LWPOLYLINE LINE'):
        ly = e.dxf.layer
        if ly not in LAYERS: continue
        if e.dxftype() == 'LINE': p = [tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]]; closed = False
        else: p = pe.pts(e); closed = e.closed
        bx0, by0, bx1, by1 = pe.bb(p)
        if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1 or bx1 - bx0 > BIGMAX or by1 - by0 > BIGMAX: continue
        if ly == '15_DASHED' and is_tooth(p, closed):                       # bearing teeth: overall beam width only
            T.append(dict(box=pe.bb(p), vert=abs(p[1][1] - p[2][1]) > abs(p[1][0] - p[2][0])))
            continue
        if ly == '6_HATCH' and not closed: continue          # open 5-point opening symbols repeat edges of walls
        if ly == '82_KIR_OLE' and (bx1 - bx0 > 8000 or by1 - by0 > 8000):
            per = (min(per[0], bx0), min(per[1], by0), max(per[2], bx1), max(per[3], by1)) if per else (bx0, by0, bx1, by1)
        n = len(p)
        for i in range(n if closed else n - 1):
            a, b = p[i], p[(i + 1) % n]; L = pe.dist(a, b)
            if L < 1: continue
            d = dict(h=e.dxf.handle, layer=ly)
            if abs(a[0] - b[0]) < 1.5: V.append(dict(d, c=(a[0] + b[0]) / 2, lo=min(a[1], b[1]), hi=max(a[1], b[1])))
            elif abs(a[1] - b[1]) < 1.5: H.append(dict(d, c=(a[1] + b[1]) / 2, lo=min(a[0], b[0]), hi=max(a[0], b[0])))
            else: S.append(dict(d, a=a, b=b, L=L))
    for ins in doc.modelspace().query('INSERT'):        # X mark in a wall = OPENING (user 2026-10-13): block = 4-vertex bowtie (rectangle with an X); its two end faces bound the opening width
        if ins.dxf.layer != '82_KIR_OLE': continue
        try: blk = [s for s in doc.blocks[ins.dxf.name]]
        except Exception: continue
        if len(blk) != 1 or blk[0].dxftype() != 'LWPOLYLINE' or len(blk[0]) != 4: continue
        q = [(float(a), float(b)) for a, b in blk[0].get_points('xy')]
        if not (pe.dist(q[0], q[3]) < 60 and pe.dist(q[1], q[2]) < 60 and abs(q[0][0] - q[3][0]) < 1 and abs(q[1][0] - q[2][0]) < 1 and pe.dist(q[0], q[1]) > 3 * pe.dist(q[0], q[3])): continue
        ang = math.radians(ins.dxf.rotation); ca, sa = math.cos(ang), math.sin(ang); ox, oy = ins.dxf.insert.x, ins.dxf.insert.y
        w = lambda u, v: (ox + ins.dxf.xscale * u * ca - ins.dxf.yscale * v * sa, oy + ins.dxf.xscale * u * sa + ins.dxf.yscale * v * ca)
        ends = [(w(*q[0]), w(*q[3])), (w(*q[1]), w(*q[2]))]
        if not (x0 <= ox <= x1 and y0 <= oy <= y1): continue
        for a, b in ends:
            if abs(a[0] - b[0]) < 3: V.append(dict(h=ins.dxf.handle, layer='82_KIR_OLE', c=(a[0] + b[0]) / 2, lo=min(a[1], b[1]), hi=max(a[1], b[1]), opening=True))
            elif abs(a[1] - b[1]) < 3: H.append(dict(h=ins.dxf.handle, layer='82_KIR_OLE', c=(a[1] + b[1]) / 2, lo=min(a[0], b[0]), hi=max(a[0], b[0]), opening=True))
    steps = []
    for cb in blue_clouds(doc):     # BLUE cloud = a staircase drawn on 15_DASHED. User's example (3 dims on layer claude): the stair is dimensioned by its OVERALL extents only (east 335 x 233, west 125 x 54)
        inside = lambda q: cb[0] - 5 <= q[0] <= cb[2] + 5 and cb[1] - 5 <= q[1] <= cb[3] + 5
        vs = [sg for sg in V if sg['layer'] == '15_DASHED' and inside((sg['c'], sg['lo'])) and inside((sg['c'], sg['hi']))]
        hs = [sg for sg in H if sg['layer'] == '15_DASHED' and inside((sg['lo'], sg['c'])) and inside((sg['hi'], sg['c']))]
        ss = [sg for sg in S if sg['layer'] == '15_DASHED' and inside(sg['a']) and inside(sg['b'])]
        if not (vs or hs or ss): continue
        xs = [sg['c'] for sg in vs] + [q for sg in hs for q in (sg['lo'], sg['hi'])] + [q[0] for sg in ss for q in (sg['a'], sg['b'])]
        ys = [sg['c'] for sg in hs] + [q for sg in vs for q in (sg['lo'], sg['hi'])] + [q[1] for sg in ss for q in (sg['a'], sg['b'])]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        for sg in vs: V.remove(sg)
        for sg in hs: H.remove(sg)
        for sg in ss: S.remove(sg)
        d = dict(h='stair', layer='15_DASHED')
        V.extend([dict(d, c=x0, lo=y0, hi=y1), dict(d, c=x1, lo=y0, hi=y1)]); H.extend([dict(d, c=y0, lo=x0, hi=x1), dict(d, c=y1, lo=x0, hi=x1)])
        steps.append(('V', [round(x0), round(x1)], y0, y1, x0, x1)); steps.append(('H', [round(y0), round(y1)], x0, x1, y0, y1))
    for name, segs in (('V', V), ('H', H)):
        idx = [i for i, sg in enumerate(segs) if sg['layer'] == '15_DASHED' and sg['hi'] - sg['lo'] >= 30]
        sub = [segs[i] for i in idx]; drop = set()
        for g in step_groups(sub):
            f0, f1 = sub[g[0]], sub[g[-1]]                                          # flight of stairs: keep the first and last step line only (overall run)
            steps.append((name, [round(sub[k]['c']) for k in g], max(f0['lo'], f1['lo']), min(f0['hi'], f1['hi']), sub[g[0]]['c'], sub[g[-1]]['c']))
            drop.update(idx[k] for k in g[1:-1])
        if drop: segs[:] = [sg for i, sg in enumerate(segs) if i not in drop]
    load.steps = steps
    return V, H, S, per, T


def arrays(segs):
    return dict(c=np.array([s['c'] for s in segs]), lo=np.array([s['lo'] for s in segs]), hi=np.array([s['hi'] for s in segs]),
                keep=np.array([s['hi'] - s['lo'] >= MIN_SEG or s.get('opening', False) for s in segs]))


def sat(R, v, side):
    """requirements a line at v satisfies: crossed, or reached on `side` (+1: element beyond v upward / rightward) within EXT_MAX"""
    cross = (R['lo'] + 3 <= v) & (v <= R['hi'] - 3)
    reach = (R['lo'] > v) & (R['lo'] - v <= EXT_MAX) if side > 0 else (R['hi'] < v) & (v - R['hi'] <= EXT_MAX)
    return cross | reach, cross


def beam_pairs(axis, segs, teeth):
    """beams with bearing teeth (Luchad beams): their OVERALL width (93_KORA face to face) must exist as ONE item on some line.
    axis 'x': vertical faces, vertical tooth strips; axis 'y': horizontal faces, horizontal strips. Returns [(cA, cB, lo, hi)]"""
    kora = [sg for sg in segs if sg['layer'] == '93_KORA']; out = {}
    for t in teeth:
        x0, y0, x1, y1 = t['box']
        if axis == 'x' and not t['vert'] or axis == 'y' and t['vert']: continue
        a0, a1, l0, l1 = (x0, x1, y0, y1) if axis == 'x' else (y0, y1, x0, x1)       # across-the-beam range, along-the-beam range
        A = [sg for sg in kora if (abs(sg['c'] - a0) <= 3 or abs(sg['c'] - a1) <= 3) and min(sg['hi'], l1) - max(sg['lo'], l0) > 50]
        for sa in A:
            Bs = [sg for sg in kora if 30 <= abs(sg['c'] - sa['c']) <= 400 and min(sg['hi'], sa['hi']) - max(sg['lo'], sa['lo']) > 100]
            if not Bs: continue
            sb = min(Bs, key=lambda sg: abs(sg['c'] - sa['c']))
            lo, hi = max(sa['lo'], sb['lo']), min(sa['hi'], sb['hi'])
            out[(round(min(sa['c'], sb['c'])), round(max(sa['c'], sb['c'])))] = (min(sa['c'], sb['c']), max(sa['c'], sb['c']), lo, hi)
    return list(out.values())


def clean_cross(segs, v, cA, cB):
    fs = sorted(sg['c'] for sg in segs if sg['lo'] + 3 <= v <= sg['hi'] - 3)
    return any(abs(f - cA) <= 2 for f in fs) and any(abs(f - cB) <= 2 for f in fs) and not any(cA + JOG < f < cB - JOG for f in fs)


def lines_of_doc(doc, box):
    """the dimension lines already in the file: {(axis,v): dict(breaks, side)} from linear X / Y dims whose line lies in the box (rule 1-2 chains)"""
    x0, y0, x1, y1 = box; res = {}
    for d in doc.modelspace().query('DIMENSION'):
        if d.dimtype & 7 != 0: continue
        p = d.dxf.defpoint
        if not (x0 - 400 <= p.x <= x1 + 400 and y0 - 400 <= p.y <= y1 + 400): continue
        ang = d.dxf.get('angle', 0) % 180; p1, p3 = d.dxf.defpoint2, d.dxf.defpoint3
        if ang < 1: axis, v, a, b, o = 'x', p.y, p1.x, p3.x, (p1.y + p3.y) / 2 - p.y
        elif abs(ang - 90) < 1: axis, v, a, b, o = 'y', p.x, p1.y, p3.y, (p1.x + p3.x) / 2 - p.x
        else: continue
        L = res.setdefault((axis, round(v)), dict(v=v, br=set(), off=[]))
        L['br'].update((a, b)); L['off'].append(o)
    out = {}
    for k, L in res.items():
        if len(L['br']) >= 4:
            off = [o for o in L['off'] if abs(o) > 2]; side = 1 if off and sum(1 for o in off if o > 0) >= len(off) / 2 else -1
            out[k] = dict(v=L['v'], br=np.array(sorted(L['br'])), side=side)
    return out


def near_break(br, c, tol=JOG):
    i = np.searchsorted(br, c - tol); j = np.searchsorted(br, c + tol, side='right'); return j > i


def run(doc, box, dry=False, verbose=False):
    V, H, S, per, T = load(doc, box)
    if per is None: raise SystemExit('no perimeter outline (big 82_KIR_OLE polyline) in the box')
    existing = lines_of_doc(doc, box); rep = []; out = pe.Out(doc); regions = pcn.wall_regions(doc); texts_used = []
    rep.append(('stair flights (interior step lines not dimensioned)', load.steps))
    rep.append(('segments', dict(V=len(V), H=len(H), S=len(S)), 'perimeter bbox', tuple(round(t) for t in per), 'existing lines kept', sorted(existing)))
    user_texts = existing_obstacles(doc, box)[0]; drawn = {}
    for axis, segs, perp in (('x', V, H), ('y', H, V)):
        R = arrays(segs); n = len(segs)
        satisfied = np.zeros(n, bool)
        for (ax, _), L in existing.items():
            if ax != axis: continue
            mm = sat(R, L['v'], L['side'])[0]
            nb = np.array([near_break(L['br'], c) for c in R['c']]); satisfied |= mm & nb
        unread = R['keep'] & ~satisfied
        rep.append((axis, 'faces to read', int(R['keep'].sum()), 'already read by the user lines', int((R['keep'] & satisfied).sum())))
        lo_v, hi_v = (per[1] + 30, per[3] - 30) if axis == 'x' else (per[0] + 30, per[2] - 30)
        avoid = np.sort(np.array([s['c'] for s in perp])); taken = [L['v'] for (ax, _), L in existing.items() if ax == axis]
        cands = np.arange(lo_v, hi_v, STEP)
        ok = np.array([not np.any(np.abs(avoid - v) <= AVOID) and all(abs(v - t) >= MIN_GAP for t in taken)
                       and not any((bx[1] - 3 <= v <= bx[3] + 3) if axis == 'x' else (bx[0] - 3 <= v <= bx[2] + 3) for bx in user_texts) for v in cands]) if len(cands) else np.array([], bool)     # a new line never runs through the user's own dimension texts
        cands = cands[ok]; chosen = []
        def cst(vs):
            v, side = vs; a, b = ((per[0], v), (per[2], v)) if axis == 'x' else ((v, per[1]), (v, per[3]))
            c = 0
            for bx0, by0, bx1, by1, k in out.stripes.boxes:
                if min(a[0], b[0]) - 18 < bx1 and max(a[0], b[0]) + 18 > bx0 and min(a[1], b[1]) - 18 < by1 and max(a[1], b[1]) + 18 > by0 and k == '*': c += 1
            return c
        used = False
        if HAVE_MILP and not NO_MILP and unread.any():
            flights0 = [(c0, c1, lo, hi) for name, cs, lo, hi, c0, c1 in load.steps if (name == 'V') == (axis == 'x')]
            pairs = []
            for cA, cB, lo, hi in beam_pairs(axis, segs, T) + flights0:
                if any(ax == axis and lo + 20 <= L['v'] <= hi - 20 and near_break(L['br'], cA, 2) and near_break(L['br'], cB, 2) and not np.any((L['br'] > cA + JOG) & (L['br'] < cB - JOG)) for (ax, _), L in existing.items()): continue
                pairs.append((cA, cB, lo, hi))
            ch, left = ilp_cover(R, segs, unread, cands, taken, pairs, cst, n)
            if ch is not None:
                used = True; chosen = ch; unread = left; taken += [c_['v'] for c_ in ch]
                rep.append((axis, 'optimal cover (integer program)', len(ch), 'lines'))
        while unread.any() and not used:
            best = (0, None, None)
            for v in cands:
                if any(abs(v - t) < MIN_GAP for t in taken): continue
                for side in (1, -1):
                    m, cr = sat(R, v, side); k = int((m & unread).sum())
                    if k > best[0]: best = (k, v, side)
            if best[0] == 0: break
            tie = []
            for v in cands:
                if any(abs(v - t) < MIN_GAP for t in taken): continue
                for side in (1, -1):
                    m, cr = sat(R, v, side)
                    if int((m & unread).sum()) == best[0]: tie.append((v, side))
            v, side = min(tie[:400], key=lambda vs: (cst(vs), vs[0])) if len(tie) > 1 else tie[0]
            m, cr = sat(R, v, side); assigned = m & unread; unread &= ~m
            taken.append(v); chosen.append(dict(v=float(v), side=side, assigned=assigned))
        # reverse delete: a line whose assigned faces are all satisfied by other lines is dropped
        changed = True
        while changed and len(chosen) > 1 and not used:
            changed = False
            for k in sorted(range(len(chosen)), key=lambda i: int(chosen[i]['assigned'].sum())):
                rest = np.zeros(n, bool)
                for i, ch in enumerate(chosen):
                    if i != k: rest |= sat(R, ch['v'], ch['side'])[0]
                if not (chosen[k]['assigned'] & ~rest).any():
                    rep.append((axis, 'line dropped (redundant)', round(chosen[k]['v']))); chosen.pop(k); changed = True; break
        flights = [(c0, c1, lo, hi) for name, cs, lo, hi, c0, c1 in load.steps if (name == 'V') == (axis == 'x')]     # a stair flight: its overall run must exist as ONE item too
        for cA, cB, lo, hi in beam_pairs(axis, segs, T) + flights:
            done = False
            for ch in chosen:                                                  # the item may come from a crossing OR from an extension line: look at the line's real faces
                fl = line_faces(axis, ch['v'], ch['side'], R, segs, S, ch['assigned'])
                if any(abs(fl[i][0] - cA) <= 2 and abs(fl[i + 1][0] - cB) <= 2 for i in range(len(fl) - 1)): done = True; break
            for (ax, _), L in existing.items():
                if ax == axis and lo + 20 <= L['v'] <= hi - 20 and near_break(L['br'], cA, 2) and near_break(L['br'], cB, 2) and not np.any((L['br'] > cA + JOG) & (L['br'] < cB - JOG)): done = True
            if done: continue
            ok_v = [v for v in cands if lo + 20 <= v <= hi - 20 and all(abs(v - t) >= MIN_GAP for t in taken) and clean_cross(segs, v, cA, cB)]
            if ok_v:
                v = min(ok_v, key=lambda v: abs(v - (lo + hi) / 2)); taken.append(v); chosen.append(dict(v=float(v), side=1, assigned=np.zeros(n, bool)))
                rep.append((axis, 'extra line for the OVERALL width of tooth beam', round(cA), round(cB), round(v)))
            else: rep.append((axis, 'overall width of tooth beam NOT placeable', round(cA), round(cB)))
        if unread.any(): rep.append((axis, 'UNREAD faces', [(round(segs[i]['c'], 1), round(segs[i]['lo']), round(segs[i]['hi']), segs[i]['layer']) for i in np.nonzero(unread)[0]][:40], int(unread.sum())))
        drawn[axis] = (R, segs, chosen)
    allitems = []; per_line = []
    for axis in ('x', 'y'):
        R, segs, chosen = drawn[axis]
        for ch in sorted(chosen, key=lambda c: c['v']):
            fl = line_faces(axis, ch['v'], ch['side'], R, segs, S, ch['assigned'])
            its = collect_items(axis, ch['v'], fl); allitems += its
            per_line.append((axis, ch, fl, len(its)))
    bad, moved = place_texts(out, allitems, regions, existing_obstacles(doc, box))
    draw_items(out, allitems)
    for axis, ch, fl, k in per_line:
        rep.append((axis, 'line', round(ch['v']), 'side', '+' if ch['side'] > 0 else '-', 'items', k, 'extent', round(fl[0][0]), round(fl[-1][0]), 'faces read', int(ch['assigned'].sum())))
    rep.append(('texts moved off the normal place', moved, 'texts still colliding', bad))
    rep.append(('new dimensions', out.n))
    return out, rep


def ilp_cover(R, segs, unread, cands, taken, pairs, cst, per_n):
    """FEWEST lines (exact integer set cover, user 2026-10-13: minimal, clean plan): choose (v, side) from the candidate grid so that every unread face is crossed or reached on that side (<= EXT_MAX),
    parallel lines >= MIN_GAP apart, plus one line giving each required overall item (tooth beam / stair flight). Secondary (tiny) costs: short extension lines, few collisions with other drawn items.
    Returns (chosen, still_unread)."""
    cols = [(float(v), s) for v in cands if all(abs(v - tt) >= MIN_GAP for tt in taken) for s in (1, -1)]
    rows = np.nonzero(unread)[0]
    A = np.zeros((len(rows), len(cols)), bool); sec = np.zeros(len(cols))
    for j, (v, s) in enumerate(cols):
        m, cr = sat(R, v, s); A[:, j] = m[rows]
        reach = m & ~cr & unread
        d = (R['lo'][reach] - v) if s > 0 else (v - R['hi'][reach])
        sec[j] = 0.012 * (float(d.sum()) / max(1, A[:, j].sum()) / EXT_MAX) + 0.006 * min(cst((v, s)), 5) / 5
    cov = A.any(axis=1)
    cons = []
    Ac = lil_matrix((int(cov.sum()), len(cols)))
    for r, k in enumerate(np.nonzero(cov)[0]):
        for j in np.nonzero(A[k])[0]: Ac[r, j] = 1
    cons.append(LinearConstraint(Ac.tocsr(), lb=np.ones(int(cov.sum())), ub=np.inf))
    vs = np.array([v for v, s in cols]); uv = sorted(set(vs.tolist()))
    G = lil_matrix((len(uv), len(cols)))
    for i, u in enumerate(uv):
        for j in np.nonzero((vs >= u) & (vs < u + MIN_GAP - 1e-6))[0]: G[i, j] = 1
    cons.append(LinearConstraint(G.tocsr(), lb=-np.inf, ub=np.ones(len(uv))))
    if pairs:
        P = lil_matrix((len(pairs), len(cols))); keep = []
        for r, (cA, cB, lo, hi) in enumerate(pairs):
            def clear(j, cA=cA, cB=cB):          # the line must not also REACH a face between the two faces (it would split the overall item)
                v, s = cols[j]; m, cr = sat(R, v, s); idx = np.nonzero(m & ~cr & unread)[0]
                return not any(cA + JOG < R['c'][k] < cB - JOG for k in idx)
            js = [j for j, (v, s) in enumerate(cols) if lo + 20 <= v <= hi - 20 and clean_cross(segs, v, cA, cB) and clear(j)]
            for j in js: P[r, j] = 1
            if js: keep.append(r)
        if keep: cons.append(LinearConstraint(P.tocsr()[keep], lb=np.ones(len(keep)), ub=np.inf))
    res = milp(1.0 + sec, constraints=cons, integrality=np.ones(len(cols)), bounds=Bounds(0, 1), options=dict(time_limit=90))
    if res.x is None: return None, unread
    pick = [j for j in range(len(cols)) if res.x[j] > 0.5]
    assigned = {j: np.zeros(len(unread), bool) for j in pick}
    for k in np.nonzero(unread & np.isin(np.arange(len(unread)), rows[cov]))[0]:
        crossing = [j for j in pick if sat(R, cols[j][0], cols[j][1])[1][k]]
        if crossing: assigned[crossing[0]][k] = True; continue
        reach = [(abs((R['lo'][k] - cols[j][0]) if cols[j][1] > 0 else (cols[j][0] - R['hi'][k])), j) for j in pick if sat(R, cols[j][0], cols[j][1])[0][k]]
        assigned[min(reach)[1]][k] = True
    chosen = [dict(v=cols[j][0], side=cols[j][1], assigned=assigned[j]) for j in pick]
    left = unread.copy(); left[rows[cov]] = False
    return chosen, left


def line_faces(axis, v, side, R, segs, S, assigned):
    fs = []
    for i, s in enumerate(segs):
        if s['lo'] + 3 <= v <= s['hi'] - 3: fs.append((s['c'], None))
    for s in S:
        a, b = s['a'], s['b']
        if axis == 'x' and (a[1] - v) * (b[1] - v) < 0: fs.append((a[0] + (b[0] - a[0]) * (v - a[1]) / (b[1] - a[1]), None))
        if axis == 'y' and (a[0] - v) * (b[0] - v) < 0: fs.append((a[1] + (b[1] - a[1]) * (v - a[0]) / (b[0] - a[0]), None))
    for i in np.nonzero(assigned)[0]:
        s = segs[i]
        if not (s['lo'] + 3 <= v <= s['hi'] - 3): fs.append((s['c'], s['lo'] if side > 0 else s['hi']))
    fs.sort(key=lambda t: (t[0], t[1] is not None)); out_ = []
    for f, r in fs:
        if out_ and f - out_[-1][0] < MIN_ITEM:
            if out_[-1][1] is not None and r is None: out_[-1] = (f, r)       # a crossed face beats a referenced one
            continue
        out_.append((f, r))
    return out_


def collect_items(axis, v, fl):
    """consecutive faces of ONE line -> items (the line stays one continuous chain; texts are placed later, against everything)"""
    items = []
    for (a, ra), (b, rb) in zip(fl, fl[1:]):
        ra = v if ra is None else ra; rb = v if rb is None else rb; m = b - a
        if m < MIN_ITEM: continue
        txt = '%g' % round(m, 1) if abs(m - round(m)) > 0.05 else '%d' % round(m)
        items.append(dict(axis=axis, v=v, a=a, b=b, ra=ra, rb=rb, m=m, txt=txt, half=0.5 * CHAR_W * TEXT_H * len(txt)))
    return items


def geom(it):
    """extension-line segments and the dimension-line segment of an item: ((x0,y0),(x1,y1)) each"""
    a, b, ra, rb, v = it['a'], it['b'], it['ra'], it['rb'], it['v']
    if it['axis'] == 'x': return [((a, ra), (a, v)), ((b, rb), (b, v))], ((a, v), (b, v))
    return [((ra, a), (v, a)), ((rb, b), (v, b))], ((v, a), (v, b))


def tbox(axis, v, s, perp, half):
    """text box (with a small margin) centred at along-coordinate s, perpendicular offset perp from the line"""
    h = TEXT_H / 2 + 2; w = half + 2
    return (s - w, v + perp - h, s + w, v + perp + h) if axis == 'x' else (v + perp - h, s - w, v + perp + h, s + w)


def hit(box, seg, pad=0.5):
    (x0, y0), (x1, y1) = seg
    return min(x0, x1) - pad <= box[2] and max(x0, x1) + pad >= box[0] and min(y0, y1) - pad <= box[3] and max(y0, y1) + pad >= box[1]


def existing_obstacles(doc, box):
    """texts, extension lines and dimension lines of the dims already in the file (the user's own lines): new texts must keep clear of them"""
    tb, ex, dl = [], [], []
    for e in doc.modelspace().query('DIMENSION'):
        if e.dimtype & 7 != 0: continue
        p, a, b, t = e.dxf.defpoint, e.dxf.defpoint2, e.dxf.defpoint3, e.dxf.text_midpoint
        if not (box[0] - 300 <= p.x <= box[2] + 300 and box[1] - 300 <= p.y <= box[3] + 300): continue
        ang = e.dxf.get('angle', 0) % 180
        if ang < 1: m = abs(a.x - b.x); half = 0.5 * CHAR_W * TEXT_H * len('%d' % round(m)); ex += [((a.x, a.y), (a.x, p.y)), ((b.x, b.y), (b.x, p.y))]; dl.append((('X', round(p.y)), ((a.x, p.y), (b.x, p.y)))); tb.append(tbox('x', t.y, t.x, 0, half))
        elif abs(ang - 90) < 1: m = abs(a.y - b.y); half = 0.5 * CHAR_W * TEXT_H * len('%d' % round(m)); ex += [((a.x, a.y), (p.x, a.y)), ((b.x, b.y), (p.x, b.y))]; dl.append((('Y', round(p.x)), ((p.x, a.y), (p.x, b.y)))); tb.append(tbox('y', t.x, t.y, 0, half))
    return tb, ex, dl


def place_texts(out, items, regions, obst):
    """rule 'no overlaps, clear plan' (user 2026-10-13): every text gets a position where it touches no other text, no extension line, no other line's dimension line and no wall hatch.
    Candidates (cost = distance from the normal place): along the line 0, +-12 .. ; perpendicular = the style's side (X above, Y left), the other side, then further out. Least-collision fallback is counted."""
    tbs, exs, dls = list(obst[0]), list(obst[1]), list(obst[2])
    for it in items:
        e, d = geom(it); exs += e; dls.append(((it['axis'].upper(), round(it['v'])), d))
    order = sorted(items, key=lambda it: it['m'])                        # narrowest first: they have the fewest places
    bad = 0; moved = 0
    for it in order:
        ax, v, mid = it['axis'], it['v'], (it['a'] + it['b']) / 2
        s0 = -1 if ax == 'y' else 1                                      # the style's own side: X above (+), Y left (-)
        d0 = s0 * 18.0
        perps = [d0, -d0, s0 * 44.0, -s0 * 44.0, s0 * 70.0, -s0 * 70.0]
        lim = it['m'] / 2 + it['half'] + 90
        alongs = [0.0] + [sg * k * 12.0 for k in range(1, int(lim / 12) + 1) for sg in (1, -1)]
        W = lim + it['half'] + 20; win = (mid - W, v - 110, mid + W, v + 110) if ax == 'x' else (v - 110, mid - W, v + 110, mid + W)
        ltb = [o for o in tbs if win[0] < o[2] and win[2] > o[0] and win[1] < o[3] and win[3] > o[1]]
        lex = [sg for sg in exs if hit(win, sg)]; ldl = [(k, sg) for k, sg in dls if k != (ax.upper(), round(v)) and hit(win, sg)]
        best = None
        for al in alongs:
            for pp in perps:
                cost = abs(al) + 1.0 * abs(pp - d0) + (0 if abs(pp) < 30 else 20)
                if best is not None and best[0] <= cost: continue
                pe_ = pp                                                          # measured: a given `location` is exact; only the DEFAULT of a narrow item sits 23 out, so every text is located explicitly
                s = mid + al; box = tbox(ax, v, s, pe_, it['half'])
                pts = [(s, v + pe_), (s - it['half'], v + pe_), (s + it['half'], v + pe_)] if ax == 'x' else [(v + pe_, s), (v + pe_, s - it['half']), (v + pe_, s + it['half'])]
                col = sum(1 for o in ltb if box[0] < o[2] and box[2] > o[0] and box[1] < o[3] and box[3] > o[1])
                col += sum(1 for sg in lex if hit(box, sg)) + sum(1 for k, sg in ldl if hit(box, sg))
                col += sum(1 for q in pts if pcn.in_wall(regions, q))
                c = cost + 1000 * col
                if best is None or c < best[0]: best = (c, al, pp, box, col)
            if best is not None and best[4] == 0 and best[0] < 40: break
        c, al, pp, box, col = best
        if col: bad += 1
        it['loc'] = (mid + al, v + pp) if ax == 'x' else (v + pp, mid + al); moved += (al != 0 or pp != d0)
        tbs.append(box)
    return bad, moved


def draw_items(out, items):
    n = 0
    for it in items:
        ax, v, a, b, ra, rb, loc = it['axis'], it['v'], it['a'], it['b'], it['ra'], it['rb'], it.get('loc')
        kw = dict(base=((a, v) if ax == 'x' else (v, a)), p1=((a, ra) if ax == 'x' else (ra, a)), p2=((b, rb) if ax == 'x' else (rb, b)), angle=0 if ax == 'x' else 90, dimstyle=pe.STYLE, dxfattribs={'layer': pe.LAYER})
        if loc is not None: kw['location'] = loc
        out.ms.add_linear_dim(**kw).render(); out.n += 1; n += 1
    return n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True)
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--replace-since', nargs='+', help='SNAPSHOT.dxf file(s): dimensions on the dim layer whose handle is NOT in all of them (= previous output of this recipe) are deleted first; the dims of the user stay. Give two snapshots taken around different runs (each run creates new handles) when no pre-run snapshot is left (backup() keeps only 6 per tag)'); ap.add_argument('--replace', action='store_true', help='delete the dims this recipe tagged with xdata CLAUDE_ROWS in an earlier run (from now on every generated dim carries the tag)'); ap.add_argument('-v', action='store_true'); ap.add_argument('--expect', type=float); ap.add_argument('-o')
    a = ap.parse_args()
    if a.expect and abs(os.path.getmtime(a.file) - a.expect) > 1: sys.exit('file changed since it was read')
    doc = ezdxf.readfile(a.file)
    if a.replace_since or a.replace:
        n = 0
        if a.replace_since:
            sets = [{e.dxf.handle for e in ezdxf.readfile(f).modelspace().query('DIMENSION')} for f in a.replace_since]; keep = set.intersection(*sets)
        for d in list(doc.modelspace().query('DIMENSION')):
            if d.dxf.layer != pe.LAYER: continue
            tagged = d.has_xdata(TAG)
            if (a.replace and tagged) or (a.replace_since and d.dxf.handle not in keep):
                g = d.dxf.get('geometry'); doc.modelspace().delete_entity(d); n += 1
                if g and g in doc.blocks: doc.blocks.delete_block(g, safe=False)
        print('deleted previous output dims:', n)
    if TAG not in doc.appids: doc.appids.add(TAG)
    before = {d.dxf.handle for d in doc.modelspace().query('DIMENSION')}
    out, rep = run(doc, tuple(a.box), a.dry, a.v)
    for d in doc.modelspace().query('DIMENSION'):
        if d.dxf.handle not in before: d.set_xdata(TAG, [(1000, 'plan_rows')])          # marks this recipe's own output for the next --replace
    for r in rep: print(r)
    if a.dry: return
    if a.o: doc.saveas(a.o); print('saved', a.o); return
    open(a.file, 'ab').close(); backup(a.file, 'rows'); doc.saveas(a.file); print('saved', a.file)


if __name__ == '__main__': main()
