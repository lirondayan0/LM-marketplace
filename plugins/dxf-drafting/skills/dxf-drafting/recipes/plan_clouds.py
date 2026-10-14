"""CLOUD-DRIVEN ADDITIONS to existing dimension lines (user 2026-10-14, red clouds on layer claude):  python plan_clouds.py FILE OUT [real] [--aci 256 1] [--reach 600]
A cloud around an element = 'its dimensions are missing, add them alongside the existing dimension lines'. For every element (82_KIR_OLE / 93_KORA / 15_DASHED polyline) fully inside a cloud:
  X size missing -> its min-x / max-x faces join the NEAREST existing horizontal chain; Y size missing -> its min-y / max-y faces join the NEAREST existing vertical chain (extension lines of any length, <= --reach).
  'missing' = no existing X / Y dim whose extension points sit on the element's two faces (a same-length dim on another element does NOT count - first attempt gave false 'covered').
DEFAULT = the user's rule (2026-10-14, 'do not add any dimensions beyond the XLINEs I created ... add the missing dimensions along the XLINEs - and nothing else'): the faces are added INTO the existing chain that lies on the user's Xline (the chain is re-split, no new line). `--companion` = the optional alternative below (REJECTED by the user as extra lines, keep it only if asked):
COMPANION LINES (learned 2026-10-14): the existing chain is NEVER modified. The new sizes go on a parallel line right beside it (offset 70, on the element's own side; next free level 140, 210 ... when two elements overlap along the line): one full item per element size, extension lines to its faces. Splitting the continuous chain at the faces of side-by-side piers (two columns interleaved in y) made every size read as two pieces (160.8 + 39.2) - wrong. Faces farther than --reach from any chain are reported, not forced.
Then run plan_repair.py. Also deletes XLINEs that do not meet the plan outline (user: 'delete the XLINEs located outside the plan')."""
import sys, os, math
R_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, R_); sys.path.insert(0, os.path.join(R_, '..', 'scripts'))
import ezdxf, ezdxf.path
import plan_rows as pr, plan_elements as pe, plan_continuity as pcn
from dxflib import backup
args = sys.argv[1:]; src, dst = args[0], args[1]; real = 'real' in args[2:]; COMPANION = '--companion' in args
ACI = [int(x) for x in args[args.index('--aci') + 1:] if x.lstrip('-').isdigit()] if '--aci' in args else [256, 1]
REACH = float(args[args.index('--reach') + 1]) if '--reach' in args else 600.0
_orig = pe.pts
def pts(e):
    if e.dxftype() == 'LWPOLYLINE' and any(abs(q[2]) > 1e-9 for q in e.get_points('xyb')): return [(q.x, q.y) for q in ezdxf.path.make_path(e).flattening(0.4)]
    return _orig(e)
pe.pts = pts
import plan_xlines_lf
doc = ezdxf.readfile(src); ms = doc.modelspace()
TPL = plan_xlines_lf.dim_template(ms)
if TPL: pe.LAYER, pe.STYLE = TPL[0], TPL[1]; print('output layer / dim style from the red cloud beside the plan:', TPL)
out = pe.Out(doc); regions = pcn.wall_regions(doc)
if pr.TAG not in doc.appids: doc.appids.add(pr.TAG)
def area(q): return abs(sum(q[i][0] * q[(i + 1) % len(q)][1] - q[(i + 1) % len(q)][0] * q[i][1] for i in range(len(q)))) / 2
import plan_xlines_lf
outline = plan_xlines_lf.kontur_outline(ms)
if not outline:
    _cl = [e for e in ms.query('LWPOLYLINE[layer=="82_KIR_OLE"]') if e.closed]
    if not _cl: sys.exit('no plan boundary: neither claude_Kontur nor a closed 82_KIR_OLE polyline')
    outline = pts(max(_cl, key=lambda e: area(pts(e))))      # claude_kontur = the user's plan boundary, else the biggest closed wall polyline
def crosses(axis, v):
    for i in range(len(outline)):
        (x1, y1), (x2, y2) = outline[i], outline[(i + 1) % len(outline)]
        if axis == 'x' and (y1 - v) * (y2 - v) < 0: return True
        if axis == 'y' and (x1 - v) * (x2 - v) < 0: return True
    return False
# ---- XLINEs outside the plan
gone = 0
for e in list(ms.query('XLINE')):
    s, u = e.dxf.start, e.dxf.unit_vector
    if abs(u.y) < 1e-6: hit = crosses('x', s.y)
    elif abs(u.x) < 1e-6: hit = crosses('y', s.x)
    else: hit = True
    if not hit: ms.delete_entity(e); gone += 1
print('XLINEs outside the plan deleted:', gone)
# ---- existing chains: {(axis, round(v,1)): [dim, ...]}
chains = {}
def own(d): return d.has_xdata(pr.TAG) and any(t.value == 'xline_dims' for t in d.get_xdata(pr.TAG))
for d in ms.query('DIMENSION'):
    if d.dimtype & 7: continue
    a = d.dxf.get('angle', 0) % 180; p = d.dxf.defpoint
    if a < 1: chains.setdefault(('x', round(p.y, 1)), []).append(d)
    elif abs(a - 90) < 1: chains.setdefault(('y', round(p.x, 1)), []).append(d)
def extent(ch):
    xs = []
    for d in ch: xs += [d.dxf.defpoint2, d.dxf.defpoint3]
    return xs
def covered(axis, lo, hi, face_lo, face_hi):
    """an existing dim reads exactly this element size: item (lo, hi) with extension points on the element's two faces"""
    for (ax, v), ch in chains.items():
        if ax != axis: continue
        for d in ch:
            a, b = d.dxf.defpoint2, d.dxf.defpoint3
            ca, cb = (a.x, b.x) if axis == 'x' else (a.y, b.y); ra, rb = (a.y, b.y) if axis == 'x' else (a.x, b.x)
            ref = [ra, rb]
            if abs(min(ca, cb) - lo) < 1.5 and abs(max(ca, cb) - hi) < 1.5 and all(face_lo - 1.5 <= r <= face_hi + 1.5 for r in ref): return True
    return False
extras = {}; rep = []
for c in ms.query('LWPOLYLINE[layer=="claude"]'):
    if c.dxf.color not in ACI: continue
    q = [tuple(t) for t in c.get_points('xy')]; cb = (min(a for a, b in q), min(b for a, b in q), max(a for a, b in q), max(b for a, b in q))
    for e in ms.query('LWPOLYLINE'):
        if e.dxf.layer not in ('82_KIR_OLE', '93_KORA', '15_DASHED'): continue
        p = pe.pts(e)
        if not all(cb[0] <= a <= cb[2] and cb[1] <= b <= cb[3] for a, b in p): continue
        xa = min(p, key=lambda t: t[0]); xb = max(p, key=lambda t: t[0]); ya = min(p, key=lambda t: t[1]); yb = max(p, key=lambda t: t[1])
        for axis, lo, hi, fa, fb, (flo, fhi) in (('x', xa[0], xb[0], xa, xb, (ya[1], yb[1])), ('y', ya[1], yb[1], ya, yb, (xa[0], xb[0]))):
            if hi - lo < pr.MIN_ITEM: continue
            if covered(axis, lo, hi, flo, fhi): continue
            mid = (flo + fhi) / 2
            cand = [(abs(v - mid), v) for (ax, v), ch in chains.items() if ax == axis and ch and (COMPANION or all(own(d) for d in ch))]      # default: only chains this skill made on the user's Xlines
            cand.sort()
            if not cand or cand[0][0] > REACH: rep.append(('NOT added (no chain within reach)', e.dxf.handle, axis, round(lo), round(hi), 'nearest', round(cand[0][0]) if cand else None)); continue
            v = cand[0][1]; ca, ra_, cb_, rb_ = (fa[0], fa[1], fb[0], fb[1]) if axis == 'x' else (fa[1], fa[0], fb[1], fb[0])
            extras.setdefault((axis, v), []).append(dict(a=ca, ra=ra_, b=cb_, rb=rb_, mid=mid, h=e.dxf.handle))
            rep.append(('add', e.dxf.handle, axis, round(lo, 1), round(hi, 1), '-> companion of chain', v, 'ext', round(cand[0][0])))
before = {d.dxf.handle for d in ms.query('DIMENSION')}; items = []
OFF = 70.0
for (axis, v), ex in extras.items():
    if not COMPANION:                                      # add the faces INTO the chain on the Xline (no new line)
        ch = chains[(axis, v)]; faces = {}
        for d in ch:
            for pt in (d.dxf.defpoint2, d.dxf.defpoint3):
                c, r = (pt.x, pt.y) if axis == 'x' else (pt.y, pt.x); k = round(c, 1); old = faces.get(k)
                if old is None or (abs(old[1] - v) > 0.5 and abs(r - v) <= 0.5): faces[k] = (c, r)
        fl = [(c, None if abs(r - v) < 0.5 else r) for c, r in faces.values()]
        for it in ex:
            for c, r in ((it['a'], it['ra']), (it['b'], it['rb'])):
                if not any(abs(c - f[0]) < 1.5 for f in fl): fl.append((c, r))
        fl.sort(key=lambda t: (t[0], t[1] is not None)); res = []
        for f, r in fl:
            if res and f - res[-1][0] < pr.MIN_ITEM:
                if res[-1][1] is not None and r is None: res[-1] = (f, r)
                continue
            res.append((f, r))
        for d in ch:
            g = d.dxf.get('geometry'); ms.delete_entity(d)
            if g and g in doc.blocks: doc.blocks.delete_block(g, safe=False)
        its = pr.collect_items(axis, v, res); items += its; rep.append(('rebuilt chain on the Xline', axis, v, 'items', len(ch), '->', len(its)))
        continue
    levels = {}                                           # (side, level) -> last end along the line
    for it in sorted(ex, key=lambda t: min(t['a'], t['b'])):
        side = 1 if it['mid'] >= v else -1; lo, hi = min(it['a'], it['b']), max(it['a'], it['b']); k = 1
        while levels.get((side, k), -1e18) > lo - 12: k += 1
        levels[(side, k)] = hi; vv = v + side * OFF * k
        items += pr.collect_items(axis, vv, [(it['a'], it['ra']), (it['b'], it['rb'])]); rep.append(('companion', axis, round(vv, 1), 'size', round(hi - lo, 1), it['h']))
bx = (min(p[0] for p in outline), min(p[1] for p in outline), max(p[0] for p in outline), max(p[1] for p in outline))
bad, moved = pr.place_texts(out, items, regions, pr.existing_obstacles(doc, bx)); pr.draw_items(out, items)
for d in ms.query('DIMENSION'):
    if d.dxf.handle not in before: d.set_xdata(pr.TAG, [(1000, 'xline_dims')])
for r in rep: print(r)
print('dims drawn', out.n, 'colliding', bad)
if real: open(src, 'ab').close(); backup(src, 'clouds')
doc.saveas(dst); print('saved', dst)
