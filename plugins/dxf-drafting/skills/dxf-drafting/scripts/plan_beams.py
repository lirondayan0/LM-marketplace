"""Inventory of the beams / walls of a structural plan floor, with everything a section needs: size, axis (also slanted), both neighbouring slabs (label `D=a+b`, side), panel span relation.
  python plan_beams.py FILE --box X0 Y0 X1 Y1 [--json OUT] [--profile NAME]
For every `b/h` label inside the box: find the strip (two near-parallel edge lines on the beam layer `b` apart) it belongs to, the strip's axis and extent, then on each side of the
strip the nearest slab label `D=a+b` within `reach` along the normal (side L = left of the strip direction, side R = right) and the panel span arrow beside it.
`type_key` = (b, h, slab L, slab R, relation) - one section per distinct key. relation: BEARING (panels span perpendicular to the beam: lengthwise, on ledges) / CORES (span parallel:
circles) / ? . Unmatched labels (no strip found) are listed so a person can look at them. Uses `93_KORA` edges (profile layers.beam_wall) and `0_LUHADIM_HEZ` span arrows."""
import argparse, collections, json, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxflib import *

LBL = re.compile(r'^(\d{2,3})/(\d{2,3})$'); SLB = re.compile(r'^D=(\d+)(?:\+(\d+))?$')

def segments(doc, layer, minlen=80):
    out = []
    for e in doc.modelspace():
        if e.dxf.layer != layer: continue
        if e.dxftype() == 'LINE': pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif e.dxftype() == 'LWPOLYLINE': pts = [(p[0], p[1]) for p in e.get_points()] + ([(e.get_points()[0][0], e.get_points()[0][1])] if e.closed else [])
        else: continue
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b)
            if L >= minlen: out.append((a, b, L, math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi))
    return out

def find_strip(segs, p, w, tol=3.5, reach=None):
    """Strip of width w (two near-parallel segments w+-tol apart) whose footprint contains point p (within `reach` of the centre line). Returns dict or None."""
    reach = reach if reach is not None else w / 2 + 110; best = None
    for i, s in enumerate(segs):
        ux, uy = math.cos(s[3]), math.sin(s[3]); nx, ny = -uy, ux
        for t in segs[i + 1:]:
            d = abs(s[3] - t[3]); d = min(d, math.pi - d)
            if d > math.radians(2.5): continue
            # perpendicular distance between the two lines, measured from s
            dist = (t[0][0] - s[0][0]) * nx + (t[0][1] - s[0][1]) * ny
            if abs(abs(dist) - w) > tol: continue
            # projections along the axis
            sp = sorted([(s[0][0] * ux + s[0][1] * uy), (s[1][0] * ux + s[1][1] * uy)]); tp = sorted([(t[0][0] * ux + t[0][1] * uy), (t[1][0] * ux + t[1][1] * uy)])
            lo, hi = max(sp[0], tp[0]), min(sp[1], tp[1])
            if hi - lo < 80: continue
            c0 = (s[0][0] * nx + s[0][1] * ny) + dist / 2               # centre line offset along the normal
            pn = p[0] * nx + p[1] * ny; pa = p[0] * ux + p[1] * uy
            off = abs(pn - c0)
            if off <= reach and lo - 60 <= pa <= hi + 60 and (best is None or off < best[0]):
                best = (off, dict(angle=s[3], u=(ux, uy), n=(nx, ny), c0=c0, lo=lo, hi=hi, w=w))
    return best[1] if best else None

def to_xy(st, a, nn): return (st['u'][0] * a + st['n'][0] * nn, st['u'][1] * a + st['n'][1] * nn)

def span_axes(doc, slabs, layer='0_LUHADIM_HEZ', r=90):
    out = {}
    leaders = [[(q[0], q[1]) for q in e.vertices] for e in doc.modelspace().query('LEADER') if e.dxf.layer == layer]
    for t, x, y in slabs:
        best = None
        for v in leaders:
            if len(v) < 2: continue
            c = ((v[0][0] + v[-1][0]) / 2, (v[0][1] + v[-1][1]) / 2); d = math.dist(c, (x, y))
            if d < r and (best is None or d < best[0]): best = (d, math.atan2(v[-1][1] - v[0][1], v[-1][0] - v[0][0]) % math.pi)
        if best: out[(x, y)] = best[1]
    return out

def side_slab(st, mid, slabs, side, reach=1100):
    """Nearest slab label on one side of the strip (side=+1 left of the direction, -1 right), looked for around the beam point `mid`."""
    nx = st['n'][0] * side; ny = st['n'][1] * side; best = None
    for t, x, y in slabs:
        dx, dy = x - mid[0], y - mid[1]; across = dx * nx + dy * ny; along = dx * st['u'][0] + dy * st['u'][1]
        if st['w'] / 2 < across <= reach and abs(along) <= max(450, (st['hi'] - st['lo']) / 2 + 100):
            d = math.hypot(across, along * 0.5)
            if best is None or d < best[0]: best = (d, t, (x, y))
    return best

def pseudo_strip(kind, p, w, rot_deg=None, seg=None):
    """Strip-like dict for a label whose outline could not be found: from the single nearest edge line ('line') or from the label's own rotation ('label')."""
    if seg is not None:
        th = seg[3]; u = (math.cos(th), math.sin(th)); n = (-u[1], u[0])
        c_seg = seg[0][0] * n[0] + seg[0][1] * n[1]; c_lab = p[0] * n[0] + p[1] * n[1]
        c0 = c_seg + (w / 2 if c_lab >= c_seg else -w / 2)                       # beam centre line = the edge line shifted by w/2 toward the label
        a0, a1 = sorted([seg[0][0] * u[0] + seg[0][1] * u[1], seg[1][0] * u[0] + seg[1][1] * u[1]])
    else:
        th = math.radians(rot_deg % 180); u = (math.cos(th), math.sin(th)); n = (-u[1], u[0]); c0 = p[0] * n[0] + p[1] * n[1]
        pa = p[0] * u[0] + p[1] * u[1]; a0, a1 = pa - 400, pa + 400
    return dict(angle=th % math.pi, u=u, n=n, c0=c0, lo=a0, hi=a1, w=w, source=kind)

def inventory(doc, box, prof, reach=1100):
    """-> (beams, unresolved). Every b/h label in `box` becomes a beam record (strip match, else single edge line, else the label's rotation); labels of one strip collapse into one beam."""
    inbox = lambda x, y: box[0] < x < box[2] and box[1] < y < box[3]
    segs = []
    for lay in prof['layers'].get('beam_edges', [prof['layers'].get('beam_wall', '93_KORA'), '82_KIR_OLE']): segs += segments(doc, lay, minlen=40)
    long_segs = [s for s in segs if s[2] >= 100]
    msp = doc.modelspace()
    texts = [e for e in msp.query('TEXT') if inbox(e.dxf.insert.x, e.dxf.insert.y)]
    labels = [(e.dxf.text.strip(), e.dxf.insert.x, e.dxf.insert.y, e.dxf.rotation) for e in texts if LBL.match(e.dxf.text.strip())]
    slabs = [(e.dxf.text.strip(), e.dxf.insert.x, e.dxf.insert.y) for e in texts if SLB.match(e.dxf.text.strip())]
    spans = span_axes(doc, slabs); beams = {}; unresolved = []
    for t, x, y, rot in labels:
        b, h = map(int, LBL.match(t).groups()); st = find_strip(long_segs, (x, y), b); src = 'strip'
        if st: st['source'] = 'strip'
        if not st:
            near = sorted(((abs((x - s[0][0]) * -math.sin(s[3]) + (y - s[0][1]) * math.cos(s[3])), s) for s in long_segs
                           if (lambda a: -60 <= a <= s[2] + 60)((x - s[0][0]) * math.cos(s[3]) + (y - s[0][1]) * math.sin(s[3]))), key=lambda t: t[0])
            if near and near[0][0] <= max(160, b + 60): st = pseudo_strip('line', (x, y), b, seg=near[0][1]); src = 'line'
        if not st: st = pseudo_strip('label', (x, y), b, rot_deg=rot); src = 'label'
        pa = x * st['u'][0] + y * st['u'][1]; cl = to_xy(st, pa, st['c0']); mid = to_xy(st, (st['lo'] + st['hi']) / 2, st['c0'])
        sides = {}
        for nm, sd in (('L', 1), ('R', -1)):
            r = side_slab(st, cl, slabs, sd, reach); sides[nm] = (r[1][2:] if r else None, r[2] if r else None)
        rel = '?'
        cand = [sides[nm][1] for nm in ('L', 'R') if sides[nm][1]]
        arrows = [spans[c] for c in cand if c in spans] or [v for k, v in sorted(spans.items(), key=lambda kv: math.dist(kv[0], cl))[:1] if math.dist(k, cl) < 1500] if False else [spans[c] for c in cand if c in spans]
        if not arrows and spans:                                         # no arrow beside the side slabs: nearest arrow of the plan within 1500
            k, v = min(spans.items(), key=lambda kv: math.dist(kv[0], cl))
            if math.dist(k, cl) < 1500: arrows = [v]
        if arrows:
            d = abs(arrows[0] - st['angle']); d = min(d, math.pi - d); rel = 'CORES' if d < math.radians(30) else 'BEARING'
        bm = dict(label=t, b=b, h=h, at=(round(x), round(y)), cl=(round(cl[0], 1), round(cl[1], 1)), u=(round(st['u'][0], 4), round(st['u'][1], 4)), n=(round(st['n'][0], 4), round(st['n'][1], 4)),
                  mid=(round(mid[0]), round(mid[1])), axis_deg=round(math.degrees(st['angle'])), length=round(st['hi'] - st['lo']), L=sides['L'][0], R=sides['R'][0], relation=rel, source=src)
        # one entry per physical beam: same strip -> same key; label-only beams keep one entry per label
        key = (b, h, bm['axis_deg'] // 3, bm['mid']) if src != 'label' else (b, h, bm['at'])
        if key in beams: beams[key].setdefault('also_at', []).append(bm['at'])
        else: beams[key] = bm
    return list(beams.values()), unresolved

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True); ap.add_argument('--json'); ap.add_argument('--profile', default='israeli-structural')
    a = ap.parse_args(); prof = load_profile(a.profile); doc = ezdxf.readfile(a.file)
    beams, _ = inventory(doc, a.box, prof)
    print(f"{len(beams)} beams ({collections.Counter(b['source'] for b in beams)}), relation {collections.Counter(b['relation'] for b in beams)}")
    types = collections.defaultdict(list)
    for bm in beams: types[f"{bm['b']}/{bm['h']} L={bm['L']} R={bm['R']} {bm['relation']}"].append(bm)
    for k in sorted(types, key=lambda k: (int(k.split('/')[0]), int(k.split('/')[1].split()[0]))): print(f'  {len(types[k]):2d} x {k}   e.g. at {types[k][0]["at"]} ({types[k][0]["source"]})')
    if a.json: json.dump(dict(beams=beams), open(a.json, 'w'), indent=1); print('wrote', a.json)

if __name__ == '__main__': main()
