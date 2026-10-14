def install(pr, outline):
    orig = pr.line_faces
    def cr(axis, v):
        r = []
        for i in range(len(outline)):
            (x1, y1), (x2, y2) = outline[i], outline[(i + 1) % len(outline)]
            if axis == 'x' and (y1 - v) * (y2 - v) < 0: r.append(x1 + (v - y1) * (x2 - x1) / (y2 - y1))
            if axis == 'y' and (x1 - v) * (x2 - v) < 0: r.append(y1 + (v - x1) * (y2 - y1) / (x2 - x1))
        return sorted(r)
    def lf(axis, v, side, R, segs, S, assigned):
        z = cr(axis, v); fl = orig(axis, v, side, R, segs, S, assigned)
        if not z: return fl
        lo, hi = z[0], z[-1]; fl = [f for f in fl if lo - 1.5 <= f[0] <= hi + 1.5]
        if not fl: return [(lo, None), (hi, None)]
        if abs(fl[0][0] - lo) > 0.5: fl[0:1 if fl[0][0] - lo < pr.MIN_ITEM else 0] = [(lo, fl[0][1] if fl[0][0] - lo < pr.MIN_ITEM else None)]
        if abs(fl[-1][0] - hi) > 0.5: fl[-1:len(fl) if hi - fl[-1][0] < pr.MIN_ITEM else len(fl)] = [(hi, fl[-1][1] if hi - fl[-1][0] < pr.MIN_ITEM else None)]
        return fl
    pr.line_faces = lf


KONTUR_TYPES = ('LWPOLYLINE', 'POLYLINE', 'LINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE')


def _kd(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy or 1.0)))
    return _kd(p, (a[0] + t * dx, a[1] + t * dy))


def _area(q):
    return abs(sum(q[i][0] * q[(i + 1) % len(q)][1] - q[(i + 1) % len(q)][0] * q[i][1] for i in range(len(q)))) / 2


def _self_close(v, tol):
    """a loop hidden in a point chain, or None: start = end; the chain RETURNS to its start and overshoots (user file hayahalon5: 18 points, the 17th = the 1st);
    the end lands on an earlier vertex / segment (a tail or a T)."""
    n = len(v)
    if n >= 4 and _kd(v[0], v[-1]) <= tol:
        return v[:-1]
    best = None
    for j in range(3, n):                                     # chain returns to its start at vertex j, then overshoots
        if _kd(v[j], v[0]) <= tol:
            c = v[:j]
            if len(c) >= 3 and (best is None or _area(c) > _area(best)): best = c
    for i in range(0, n - 3):                                 # chain end lands on an earlier vertex / segment -> loop from there
        d = min(_kd(v[i], v[-1]), _seg_dist(v[-1], v[i], v[i + 1]))
        if d <= tol:
            c = v[i:-1]
            if len(c) >= 3 and (best is None or _area(c) > _area(best)): best = c
    return best


def kontur_analyze(ms, flatten=0.4, tol=3.0, bridge=0.3):
    """The user's work-plan boundary = layer `claude_kontur` (any case). Returns (loops, repairs): loops = list of closed point lists (arcs / splines / circles flattened, blocks exploded),
    repairs = what was needed to read it ('overshoot' trimmed, 'gap' closed by a straight chord, 'dropped' piece, 'duplicate' loop removed).
    Handles: self-closed pieces, almost-closed / overshooting / T-closed polylines, pieces joined end to end, gaps up to `bridge` x the boundary's size bridged by straight lines,
    duplicates, several regions. The boundary is NEVER replaced by another outline when this layer holds anything usable."""
    import ezdxf.path
    pieces = []; repairs = []

    def add(e):
        try:
            v = [(q.x, q.y) for q in ezdxf.path.make_path(e).flattening(flatten)]
        except Exception:
            return
        w = [v[0]]
        for q in v[1:]:
            if _kd(q, w[-1]) > 1e-6: w.append(q)
        if len(w) >= 2: pieces.append(w)

    for e in ms:
        if e.dxf.layer.strip().lower() != 'claude_kontur': continue
        t = e.dxftype()
        if t == 'INSERT':
            try:
                for ve in e.virtual_entities():
                    if ve.dxftype() in KONTUR_TYPES: add(ve)
            except Exception:
                pass
        elif t in KONTUR_TYPES:
            add(e)
    if not pieces: return [], repairs
    allp = [q for v in pieces for q in v]; diag = _kd((min(q[0] for q in allp), min(q[1] for q in allp)), (max(q[0] for q in allp), max(q[1] for q in allp)))
    loops = []; rest = []
    for v in pieces:
        c = _self_close(v, tol)
        if c and len(c) >= 3:
            if len(c) < len(v) - 1 and _kd(v[0], v[-1]) > tol: repairs.append(dict(kind='overshoot'))
            loops.append(c)
        else: rest.append(v)
    chains = []
    while rest:                                                # exact joins first
        chain = rest.pop(0); grew = True
        while grew:
            grew = False
            for i, q in enumerate(rest):
                if _kd(chain[-1], q[0]) <= tol: chain = chain + q[1:]
                elif _kd(chain[-1], q[-1]) <= tol: chain = chain + q[::-1][1:]
                elif _kd(chain[0], q[-1]) <= tol: chain = q[:-1] + chain
                elif _kd(chain[0], q[0]) <= tol: chain = q[::-1][:-1] + chain
                else: continue
                rest.pop(i); grew = True; break
        c = _self_close(chain, tol)
        if c: loops.append(c)
        else: chains.append(chain)
    while len(chains) > 1:                                     # bridge the nearest endpoints of different open chains (a gap in the drawing)
        best = None
        for a in range(len(chains)):
            for b in range(a + 1, len(chains)):
                for ea in (0, -1):
                    for eb in (0, -1):
                        d = _kd(chains[a][ea], chains[b][eb])
                        if best is None or d < best[0]: best = (d, a, b, ea, eb)
        if best is None or best[0] > bridge * diag: break
        d, a, b, ea, eb = best; A = chains[a] if ea == -1 else chains[a][::-1]; B = chains[b] if eb == 0 else chains[b][::-1]
        repairs.append(dict(kind='gap', size=round(d))); chains = [c for k, c in enumerate(chains) if k not in (a, b)] + [A + B]
    for chain in chains:                                       # last resort: close an open chain by a straight chord
        g = _kd(chain[0], chain[-1])
        if len(chain) >= 3 and g <= bridge * diag and _area(chain) > 0:
            repairs.append(dict(kind='gap', size=round(g))); loops.append(chain)
        else:
            on = lambda p: any(_seg_dist(p, l[i], l[(i + 1) % len(l)]) <= tol * 2 for l in loops for i in range(len(l)))
            if not all(on(q) for q in chain): repairs.append(dict(kind='dropped', points=len(chain)))      # a duplicate / spur edge lying on a loop is ignored silently
    out = []                                                   # duplicates (the same loop drawn twice / a loop and its copy)
    for l in sorted(loops, key=_area, reverse=True):
        bb = (min(q[0] for q in l), min(q[1] for q in l), max(q[0] for q in l), max(q[1] for q in l))
        if _area(l) < 1.0: continue
        if any(all(abs(x - y) <= max(tol, 0.002 * diag) for x, y in zip(bb, o[1])) for o in out):
            repairs.append(dict(kind='duplicate')); continue
        out.append((l, bb))
    def inside(pt, poly):
        c = False
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            if (y1 > pt[1]) != (y2 > pt[1]) and pt[0] < x1 + (pt[1] - y1) * (x2 - x1) / (y2 - y1): c = not c
        return c
    keep = []
    for l, bb in out:                                          # a loop lying inside another one is part of that region (a courtyard / hole), not a plan of its own
        if any(o is not l and _area(o) > _area(l) and all(inside(q, o) for q in l) for o in [k[0] for k in out]):
            repairs.append(dict(kind='nested')); continue
        keep.append(l)
    return keep, repairs


def kontur_loops(ms, flatten=0.4, tol=3.0):
    """ALL closed regions of the boundary layer (see kontur_analyze)."""
    return kontur_analyze(ms, flatten, tol)[0]


def kontur_outline(ms, flatten=0.4, tol=3.0):
    """the user's boundary of the work plan when it is ONE closed region (else None: use kontur_loops; callers fall back to the biggest closed 82_KIR_OLE polyline)."""
    L = kontur_loops(ms, flatten, tol)
    return L[0] if len(L) == 1 else None


def plan_outline(ms):
    """the boundary of the work plan: the user's `claude_Kontur` loop when present, else the biggest closed `82_KIR_OLE` polyline (arcs flattened). Returns (points, source)."""
    import ezdxf.path
    k = kontur_outline(ms)
    if k: return k, 'claude_Kontur'
    area = lambda q: abs(sum(q[i][0] * q[(i + 1) % len(q)][1] - q[(i + 1) % len(q)][0] * q[i][1] for i in range(len(q)))) / 2
    best = None
    for e in ms.query('LWPOLYLINE[layer=="82_KIR_OLE"]'):
        if not e.closed: continue
        q = [(v.x, v.y) for v in ezdxf.path.make_path(e).flattening(0.4)]
        if best is None or area(q) > area(best): best = q
    return best, '82_KIR_OLE biggest closed polyline'


def dim_template(ms, pad=100.0):
    """the OUTPUT LAYER + DIM STYLE of the work (user 2026-10-14): a cloud OUTSIDE the plan (outside claude_Kontur) encloses a sample dimension drawn on the layer/style to use for every dimension I create.
    Cloud on layer `claude_DIM` (user's latest marking) is preferred, then red/orange clouds on layer `claude`; clouds inside the plan are missing-size / add-face marks and are skipped.
    Returns (layer, dimstyle, handle) of the first dimension found inside such a cloud, else None (callers keep the defaults 36_MIDA_CLALI / dim_100)."""
    kon = kontur_outline(ms)
    def inside(x, y):
        c = False
        for i in range(len(kon)):
            (x1, y1), (x2, y2) = kon[i], kon[(i + 1) % len(kon)]
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c = not c
        return c
    clouds = [c for c in ms.query('LWPOLYLINE') if c.dxf.layer.lower() in ('claude_dim', 'claude')]
    clouds.sort(key=lambda c: c.dxf.layer.lower() != 'claude_dim')
    for c in clouds:
        q = [tuple(p) for p in c.get_points('xy')]; x0, y0, x1, y1 = min(a for a, b in q), min(b for a, b in q), max(a for a, b in q), max(b for a, b in q)
        if kon and inside((x0 + x1) / 2, (y0 + y1) / 2): continue
        for d in ms.query('DIMENSION'):
            if d.dxf.layer.lower() in ('claude', 'claude_dim'): continue
            pts = [d.dxf.defpoint, d.dxf.defpoint2, d.dxf.defpoint3]
            if sum(x0 - pad <= p.x <= x1 + pad and y0 - pad <= p.y <= y1 + pad for p in pts) >= 2: return d.dxf.layer, d.dxf.dimstyle, d.dxf.handle   # 2 of 3 points: hand-drawn clouds are tight
    return None
