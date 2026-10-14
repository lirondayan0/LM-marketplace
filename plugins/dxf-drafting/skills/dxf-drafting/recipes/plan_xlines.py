"""XLINE-DRIVEN DIMENSION LINES (user 2026-10-14):  python plan_xlines.py FILE OUT [real]   then   python plan_repair.py OUT OUT2   (real = write over FILE after a snapshot; FILE must be closed in CAD)
XLINEs on layer `claude` mark where dimension lines go - ONLY there, nothing else is added. horizontal Xline -> X chain; tilted Xline -> ALIGNED chain along it (green clouds). horizontal Xline -> X chain; tilted Xline -> ALIGNED chain along it (green clouds).
Chains run outline-to-outline (outline flattened through its arc bulges = blue clouds). Orange clouds: element faces added to the nearest chain by extension lines."""
import sys, os, math
R_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, R_); sys.path.insert(0, os.path.join(R_, '..', 'scripts')); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, ezdxf, ezdxf.path
import plan_rows as pr, plan_elements as pe, plan_continuity as pcn
import plan_xlines_lf as patch_lf
from dxflib import backup
src, dst = sys.argv[1], sys.argv[2]; real = 'real' in sys.argv[3:]; REPLACE = '--replace' in sys.argv[3:]      # default KEEPS every existing dim (earlier approved rounds); --replace deletes this recipe's own earlier output first
_orig_pts = pe.pts
def pts(e):
    if e.dxftype() == 'LWPOLYLINE' and any(abs(q[2]) > 1e-9 for q in e.get_points('xyb')):
        v = list(ezdxf.path.make_path(e).flattening(0.4)); return [(q.x, q.y) for q in v]
    return _orig_pts(e)
pe.pts = pts
doc = ezdxf.readfile(src); ms = doc.modelspace()
TPL = patch_lf.dim_template(ms)
if TPL: pe.LAYER, pe.STYLE = TPL[0], TPL[1]; print('output layer / dim style from the red cloud beside the plan:', TPL)
n = 0
for d in (list(ms.query('DIMENSION')) if REPLACE else []):
    if d.has_xdata(pr.TAG) and any(t.value == 'xline_dims' for t in d.get_xdata(pr.TAG)):      # only this recipe's own output; the user's dims (even if tagged by an older recipe) stay
        g = d.dxf.get('geometry'); ms.delete_entity(d); n += 1
        if g and g in doc.blocks: doc.blocks.delete_block(g, safe=False)
print('removed my previous dims', n)
def _area(q): return abs(sum(q[i][0] * q[(i + 1) % len(q)][1] - q[(i + 1) % len(q)][0] * q[i][1] for i in range(len(q)))) / 2
_cl = [e for e in ms.query('LWPOLYLINE[layer=="82_KIR_OLE"]') if e.closed]
OUTLINE = max(_cl, key=lambda e: _area(pe.pts(e))) if _cl else None      # plan outline = largest closed wall polyline (4AD on ramla DIM.dxf); arcs flattened
outline = patch_lf.kontur_outline(ms); print('outline = layer claude_kontur (user boundary)' if outline else 'outline = biggest closed wall polyline'); outline = outline or (pts(OUTLINE) if OUTLINE is not None else sys.exit('no plan boundary: neither claude_Kontur nor a closed 82_KIR_OLE polyline')); patch_lf.install(pr, outline)
def pnp(x, y):
    c = False
    for i in range(len(outline)):
        (x1, y1), (x2, y2) = outline[i], outline[(i + 1) % len(outline)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c = not c
    return c
def cross(axis, v):
    r = []
    for i in range(len(outline)):
        (x1, y1), (x2, y2) = outline[i], outline[(i + 1) % len(outline)]
        if axis == 'x' and (y1 - v) * (y2 - v) < 0: r.append(x1 + (v - y1) * (x2 - x1) / (y2 - y1))
        if axis == 'y' and (x1 - v) * (x2 - v) < 0: r.append(y1 + (v - x1) * (y2 - y1) / (x2 - x1))
    return sorted(r)
bx = (min(p[0] for p in outline), min(p[1] for p in outline), max(p[0] for p in outline), max(p[1] for p in outline))
if pr.TAG not in doc.appids: doc.appids.add(pr.TAG)
before = {d.dxf.handle for d in ms.query('DIMENSION')}
V, H, S, per, T = pr.load(doc, bx); out = pe.Out(doc); regions = pcn.wall_regions(doc)
RV = pr.arrays(V); RH = pr.arrays(H); items = []; rep = []
XL_LAYERS = ('claude_DIM', 'claude')      # user 2026-10-14: an XLINE on layer claude_DIM = 'create the dimension plan' (older rounds used layer claude)
xl = []; seen = set()
for e in ms.query('XLINE'):
    if e.dxf.layer not in XL_LAYERS: continue
    s0, u0 = e.dxf.start, e.dxf.unit_vector
    if abs(u0.y) > abs(u0.x):                                  # near-vertical: direction up, so a rotated text reads upright
        if u0.y < 0: u0 = -u0
    elif u0.x < 0: u0 = -u0
    key = (round(u0.x, 3), round(u0.y, 3), round(s0.x * u0.y - s0.y * u0.x))      # duplicate Xlines (same line) once
    if key in seen: continue
    seen.add(key); xl.append((s0, u0))
def has_dim_line(axis, v):
    for d in ms.query('DIMENSION'):
        a = d.dxf.get('angle', 0) % 180
        if axis == 'x' and a < 1 and abs(d.dxf.defpoint.y - v) < 1: return True
        if axis == 'y' and abs(a - 90) < 1 and abs(d.dxf.defpoint.x - v) < 1: return True
    return False
hor = sorted({round(s.y, 1) for s, u in xl if abs(u.y) < 1e-6 and cross('x', s.y) and not has_dim_line('x', s.y)})
ver = sorted({round(s.x, 1) for s, u in xl if abs(u.x) < 1e-6 and cross('y', s.x) and not has_dim_line('y', s.x)})
tilt = [(s, u) for s, u in xl if abs(u.y) >= 1e-6 and abs(u.x) >= 1e-6]
for s, u in xl:
    if abs(u.y) < 1e-6 and not cross('x', s.y): print('Xline y=%d does not meet the plan outline - skipped' % s.y)
    if abs(u.x) < 1e-6 and not cross('y', s.x): print('Xline x=%d does not meet the plan outline - skipped' % s.x)
print('Xlines: horizontal', hor, 'vertical', ver, 'tilted', len(tilt))
# ---- orange clouds -> extra faces on the nearest horizontal chain
extras = {v: [] for v in hor}
for c in (ms.query('LWPOLYLINE[layer=="claude"]') if hor else []):
    if c.dxf.color != 32: continue
    p = [tuple(q) for q in c.get_points('xy')]; cb = (min(a for a, b in p), min(b for a, b in p), max(a for a, b in p), max(b for a, b in p)); found = []
    for e in ms.query('LWPOLYLINE'):
        if e.dxf.layer not in ('82_KIR_OLE', '93_KORA', '15_DASHED'): continue
        q = pe.pts(e); ins = [t for t in q if cb[0] <= t[0] <= cb[2] and cb[1] <= t[1] <= cb[3]]
        if not ins: continue
        if len(ins) == len(q): found += [min(ins, key=lambda t: t[0]), max(ins, key=lambda t: t[0])]
        else: found += ins
    if not found: continue
    yc = sum(t[1] for t in found) / len(found); v = min(hor, key=lambda h: abs(h - yc))
    extras[v] += found; rep.append(('orange', c.dxf.handle, 'faces', len(found), '-> chain y', v))
def chain(axis, v, extra):
    segs, R = (V, RV) if axis == 'x' else (H, RH); xs = cross(axis, v); lo, hi = xs[0], xs[-1]; best = None
    pt = (lambda s, side: (s['c'], s['lo'] if side > 0 else s['hi'])) if axis == 'x' else (lambda s, side: (s['lo'] if side > 0 else s['hi'], s['c']))
    for side in (1, -1):
        m, cr = pr.sat(R, v, side); asg = m & ~cr
        asg &= np.array([lo - 1 <= s['c'] <= hi + 1 and pnp(*pt(s, side)) and s['hi'] - s['lo'] >= pr.MIN_SEG for s in segs]) if axis == 'x' else np.array([pnp(*pt(s, side)) and s['hi'] - s['lo'] >= pr.MIN_SEG and lo - 1 <= s['c'] <= hi + 1 for s in segs])
        if best is None or asg.sum() > best[0]: best = (int(asg.sum()), side, asg)
    k, side, asg = best
    fl = list(pr.line_faces(axis, v, side, R, segs, S, asg)) + [((x, y) if axis == 'x' else (y, x)) for x, y in extra]
    fl.sort(key=lambda t: (t[0], t[1] is not None)); res = []
    for f, r in fl:
        if res and f - res[-1][0] < pr.MIN_ITEM:
            if res[-1][1] is not None and r is None: res[-1] = (f, r)
            continue
        res.append((f, r))
    its = pr.collect_items(axis, v, res); items.extend(its)
    rep.append((axis, v, 'side', side, 'reach', k, 'extras', len(extra), 'items', len(its), 'ends', round(res[0][0]), round(res[-1][0])))
for v in hor: chain('x', v, extras[v])
for v in ver: chain('y', v, [])
bad, moved = pr.place_texts(out, items, regions, pr.existing_obstacles(doc, bx)); pr.draw_items(out, items)
rep.append(('X / Y chains drawn', out.n, 'colliding', bad))
# ---- tilted Xlines -> aligned chains
segs = [((s['c'], s['lo']), (s['c'], s['hi']), s.get('opening', False)) for s in V] + [((s['lo'], s['c']), (s['hi'], s['c']), s.get('opening', False)) for s in H] + [(s['a'], s['b'], False) for s in S]
def aligned(s0, u0):
    p0 = (s0.x, s0.y); ux, uy = u0.x, u0.y; nx, ny = -uy, ux; ang = math.degrees(math.atan2(uy, ux))
    dot = lambda a, b: a[0] * b[0] + a[1] * b[1]; tt = []
    for i in range(len(outline)):
        a, b = outline[i], outline[(i + 1) % len(outline)]; da = dot((a[0] - p0[0], a[1] - p0[1]), (nx, ny)); db = dot((b[0] - p0[0], b[1] - p0[1]), (nx, ny))
        if da * db < 0:
            w = da / (da - db); q = (a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w); tt.append(dot((q[0] - p0[0], q[1] - p0[1]), (ux, uy)))
    tt.sort(); lo, hi = tt[0], tt[-1]; faces = []; reach = {1: [], -1: []}
    for a, b, op in segs:
        da = dot((a[0] - p0[0], a[1] - p0[1]), (nx, ny)); db = dot((b[0] - p0[0], b[1] - p0[1]), (nx, ny)); L = math.hypot(b[0] - a[0], b[1] - a[1])
        if da * db < 0 and L >= 1:
            w = da / (da - db); q = (a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w); t = dot((q[0] - p0[0], q[1] - p0[1]), (ux, uy))
            if lo - 1.5 <= t <= hi + 1.5 and min(w, 1 - w) * L > 3: faces.append((t, q))
        elif da * db > 0 and L >= pr.MIN_SEG and abs(dot((b[0] - a[0], b[1] - a[1]), (ux, uy))) / L < 0.045 and min(abs(da), abs(db)) <= pr.EXT_MAX:      # edge perpendicular to the Xline (tilted pier end) beside it
            q = a if abs(da) < abs(db) else b; t = dot((q[0] - p0[0], q[1] - p0[1]), (ux, uy))
            if lo - 1.5 <= t <= hi + 1.5 and pnp(*q): reach[1 if da > 0 else -1].append((t, q))
    side = 1 if len(reach[1]) >= len(reach[-1]) else -1; fl = faces + reach[side]
    on = lambda q: abs(dot((q[0] - p0[0], q[1] - p0[1]), (nx, ny))) < 0.01
    fl.sort(key=lambda f: (f[0], not on(f[1]))); res = []
    for t, q in fl:
        if res and t - res[-1][0] < pr.MIN_ITEM:
            if not on(res[-1][1]) and on(q): res[-1] = (t, q)
            continue
        res.append((t, q))
    onl = lambda t: (p0[0] + ux * t, p0[1] + uy * t)
    if abs(res[0][0] - lo) > 0.5: res[0:1 if res[0][0] - lo < pr.MIN_ITEM else 0] = [(lo, onl(lo))]
    if abs(res[-1][0] - hi) > 0.5: res[-1:len(res) if hi - res[-1][0] < pr.MIN_ITEM else len(res)] = [(hi, onl(hi))]
    k = 0
    for (t1, q1), (t2, q2) in zip(res, res[1:]):
        m = t2 - t1
        if m < pr.MIN_ITEM: continue
        mid = onl((t1 + t2) / 2); loc = (mid[0] + nx * 18, mid[1] + ny * 18)
        out.ms.add_linear_dim(base=onl(t1), p1=q1, p2=q2, angle=ang, location=loc, dimstyle=pe.STYLE, dxfattribs={'layer': pe.LAYER}).render(); out.n += 1; k += 1
    rep.append(('aligned Xline', (round(s0.x), round(s0.y)), 'angle', round(ang, 2), 'side', side, 'reach', len(reach[side]), 'items', k, 'ends', round(lo), round(hi)))
for s0, u0 in tilt: aligned(s0, u0)
for d in ms.query('DIMENSION'):
    if d.dxf.handle not in before: d.set_xdata(pr.TAG, [(1000, 'xline_dims')])
for r in rep: print(r)
if real: open(src, 'ab').close(); backup(src, 'build')
doc.saveas(dst); print('saved', dst)
