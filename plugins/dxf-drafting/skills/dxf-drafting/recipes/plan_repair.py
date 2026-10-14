"""  python plan_repair.py FILE OUT  -  text repair pass (run after plan_xlines.py / plan_rows.py): move every generated dimension text that touches another text / another dim's extension or dimension line / a drawing text / wall hatch to the nearest free place. Handles X, Y and rotated (aligned-with-Xline) dims."""
import sys, os, math
R_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, R_); sys.path.insert(0, os.path.join(R_, '..', 'scripts'))
import ezdxf, plan_rows as pr, plan_continuity as pcn
from ezdxf.entities import DimStyleOverride
src, dst = sys.argv[1], sys.argv[2]
doc = ezdxf.readfile(src); ms = doc.modelspace(); regions = pcn.wall_regions(doc); TH = 24.0
def seg_box(b, s):
    (x0, y0), (x1, y1) = s; t0, t1 = 0.0, 1.0; dx, dy = x1 - x0, y1 - y0
    for p, q in ((-dx, x0 - b[0]), (dx, b[2] - x0), (-dy, y0 - b[1]), (dy, b[3] - y0)):
        if abs(p) < 1e-12:
            if q < 0: return False
        else:
            r = q / p
            if p < 0:
                if r > t1: return False
                t0 = max(t0, r)
            else:
                if r < t0: return False
                t1 = min(t1, r)
    return True
def ov(a, b): return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]
def tbox(c, u, n, half, th=TH):
    h = th / 2 + 2; w = half + 2; xs = []; ys = []
    for sa in (-1, 1):
        for sb in (-1, 1): xs.append(c[0] + u[0] * sa * w + n[0] * sb * h); ys.append(c[1] + u[1] * sa * w + n[1] * sb * h)
    return (min(xs), min(ys), max(xs), max(ys))
def PB_BY_TH(th): return 18.0 if th >= 20 else 10.7      # text centre distance from the dim line: 18 for dim_100 (text 24), 7 for dim_50 (text 12; user 2026-10-14: hand-set 10.7)
def info(e):
    dp, a, b, t = e.dxf.defpoint, e.dxf.defpoint2, e.dxf.defpoint3, e.dxf.text_midpoint
    ang = math.radians(e.dxf.get('angle', 0)); u = (math.cos(ang), math.sin(ang)); n = (-u[1], u[0])
    pj = lambda p: (p.x - n[0] * ((p.x - dp.x) * n[0] + (p.y - dp.y) * n[1]), p.y - n[1] * ((p.x - dp.x) * n[0] + (p.y - dp.y) * n[1]))
    qa, qb = pj(a), pj(b); m = abs((b.x - a.x) * u[0] + (b.y - a.y) * u[1]); txt = '%d' % round(m); th = doc.dimstyles.get(e.dxf.dimstyle).dxf.get('dimtxt', TH) if doc.dimstyles.has_entry(e.dxf.dimstyle) else TH; pb = PB_BY_TH(th); half = 0.5 * 0.6 * th * len(txt) + 2
    off = round(dp.x * n[0] + dp.y * n[1]); line = (round(math.degrees(ang) % 180, 1), off)
    return dict(e=e, u=u, n=n, ext=[((a.x, a.y), qa), ((b.x, b.y), qb)], dl=(qa, qb), line=line, half=half, m=m, mid=((qa[0] + qb[0]) / 2, (qa[1] + qb[1]) / 2),
                th=th, pb=pb, box=tbox((t.x, t.y), u, n, half, th), own=e.has_xdata(pr.TAG), tc=(t.x, t.y))
D = [info(e) for e in ms.query('DIMENSION') if e.dimtype & 7 == 0]
texts = []
for e in ms.query('TEXT MTEXT'):
    try:
        ip = e.dxf.insert; h = e.dxf.get('height', 20); s = e.dxf.get('text', '') if e.dxftype() == 'TEXT' else e.text
        w = 0.6 * h * max(1, len(s)); texts.append((ip.x - 2, ip.y - 2, ip.x + w + 2, ip.y + h + 2))
    except Exception: pass
def cols(d, box, c):
    k = 0
    for o in D:
        if o is d: continue
        if ov(box, o['box']): k += 1
        if o['line'] != d['line']:
            if any(seg_box(box, s) for s in o['ext']): k += 1
            if seg_box(box, o['dl']): k += 1
    k += sum(1 for t in texts if ov(box, t)) + (1 if pcn.in_wall(regions, c) else 0)
    return k
def fixone(d):
    pb = d['pb']; perps = [pb, -pb] + [sg * (pb + 26.0 * k) for k in (1, 2, 3) for sg in (1, -1)]; lim = d['m'] / 2 + d['half'] + 150
    alongs = [0.0] + [sg * k * 12.0 for k in range(1, int(lim / 12) + 1) for sg in (1, -1)]; best = None
    for al in alongs:
        for pp in perps:
            cost = abs(al) + abs(pp - pb) + (0 if abs(pp) <= pb else 20)
            if best and best[0] <= cost: continue
            c = (d['mid'][0] + d['u'][0] * al + d['n'][0] * pp, d['mid'][1] + d['u'][1] * al + d['n'][1] * pp); box = tbox(c, d['u'], d['n'], d['half'], d['th']); k = cols(d, box, c)
            if best is None or cost + 1000 * k < best[0]: best = (cost + 1000 * k, c, box, k)
        if best and best[3] == 0 and best[0] < 60: break
    return best
moved = 0
for d in D:       # normalise the generator's default text distance (18) to the style's preferred one (dim_50: 10.7, user 2026-10-14) before the collision pass
    if not d['own'] or d['pb'] == 18.0 or d['e'].dxf.get('angle', 0) % 180 not in (0, 90) and False: continue
    off = (d['tc'][0] - d['e'].dxf.defpoint.x) * d['n'][0] + (d['tc'][1] - d['e'].dxf.defpoint.y) * d['n'][1]
    if 16 <= abs(off) <= 20:
        k = (d['pb'] - abs(off)) * (1 if off > 0 else -1); c = (d['tc'][0] + d['n'][0] * k, d['tc'][1] + d['n'][1] * k)
        o = DimStyleOverride(d['e']); o.set_location(c, leader=False, relative=False); o.render(); d['tc'] = c; d['box'] = tbox(c, d['u'], d['n'], d['half'], d['th'])
for it in range(3):
    n = 0
    for d in D:
        if not d['own'] or cols(d, d['box'], d['tc']) == 0: continue
        best = fixone(d)
        if best[3] >= cols(d, d['box'], d['tc']): continue
        o = DimStyleOverride(d['e']); o.set_location(best[1], leader=False, relative=False); o.render(); d['box'] = best[2]; d['tc'] = best[1]; n += 1
    moved += n
    if n == 0: break
bad = [d for d in D if d['own'] and cols(d, d['box'], d['tc'])]
print('moved', moved, 'still colliding', len(bad), [(d['line'], round(d['m'])) for d in bad][:10]); doc.saveas(dst)
