"""Where Section 5 (the general wall + slab section for elevator shafts and stairwells) goes on a plan.
  python shaft_walls.py FILE [--box X0 Y0 X1 Y1] [--profile NAME] [--radius 450]
Finds the elevator / stairwell labels, the 15-30 cm wall strips (pairs of parallel `93_KORA` lines) around each, and which side of each strip a floor slab touches (slab
marker block `S_M` / `D=` labels). For every strip that borders a slab it proposes ONE cut pair across the strip at its mid-length, looking so that the slab is on the RIGHT
(N-S wall, slab east -> look N; slab west -> S; E-W wall, slab north -> look W; slab south -> E), and says whether a cut mark of that section already exists there.
Rule learned from the user's four section-5 pairs on the Level -1 plan of ramla.dxf (2026-10-06): one pair per shaft wall that borders a slab, at the wall's mid-length, cut perpendicular
to the wall; elevator and stairwell of both cores. Apply with recipes/cut_marks.py (beam-width = wall thickness)."""
import argparse, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxflib import *

SHAFT_WORDS = ('מעלית', 'מדרגות')           # elevator, stairs (decoded from the Hebrew-keyboard SHX text)

def strips(doc, layer, wmin=15, wmax=30, minlen=60):
    """Wall strips = two parallel axis-aligned lines `wmin..wmax` apart that overlap by >= minlen. Returns dicts with orientation, centre, width, extent."""
    segs = []
    for e in doc.modelspace():
        if e.dxf.layer != layer: continue
        if e.dxftype() == 'LINE': pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif e.dxftype() == 'LWPOLYLINE': pts = [(p[0], p[1]) for p in e.get_points()]
        else: continue
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) < 0.5 and abs(a[1] - b[1]) > minlen: segs.append(('v', a[0], min(a[1], b[1]), max(a[1], b[1])))
            elif abs(a[1] - b[1]) < 0.5 and abs(a[0] - b[0]) > minlen: segs.append(('h', a[1], min(a[0], b[0]), max(a[0], b[0])))
    out = []
    for i, s in enumerate(segs):
        for t in segs[i + 1:]:
            if s[0] != t[0] or not (wmin <= abs(s[1] - t[1]) <= wmax): continue
            lo, hi = max(s[2], t[2]), min(s[3], t[3])
            if hi - lo >= minlen: out.append(dict(o=s[0], pos=(s[1] + t[1]) / 2, w=abs(s[1] - t[1]), lo=lo, hi=hi, mid=(lo + hi) / 2))
    return out

def label_points(doc, words, box):
    out = []
    for e in doc.modelspace().query('TEXT'):
        if decode(e.dxf.text).strip() in words and (not box or box[0] < e.dxf.insert.x < box[2] and box[1] < e.dxf.insert.y < box[3]): out.append((decode(e.dxf.text).strip(), e.dxf.insert.x, e.dxf.insert.y))
    return out

def slab_points(doc, box):
    pts = []
    for e in doc.modelspace().query('INSERT'):
        if e.dxf.name == 'S_M':
            b = bbox.extents([e])
            if b.has_data and (not box or box[0] < b.center.x < box[2] and box[1] < b.center.y < box[3]): pts.append((b.center.x, b.center.y))
    return pts

def slab_side(s, slabs, reach=400, along=500):
    """Which side of the strip a slab marker is on: 'E'/'W' for vertical strips, 'N'/'S' for horizontal ones (marker within `reach` across and along the strip)."""
    best = {}
    for x, y in slabs:
        if s['o'] == 'v':
            if s['lo'] - along <= y <= s['hi'] + along and abs(x - s['pos']) <= reach: best.setdefault('E' if x > s['pos'] else 'W', abs(x - s['pos']))
        else:
            if s['lo'] - along <= x <= s['hi'] + along and abs(y - s['pos']) <= reach: best.setdefault('N' if y > s['pos'] else 'S', abs(y - s['pos']))
    return min(best, key=best.get) if best else None

VIEW = {('v', 'E'): 'N', ('v', 'W'): 'S', ('h', 'N'): 'W', ('h', 'S'): 'E'}      # slab on the right of the view

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float); ap.add_argument('--profile', default='israeli-structural'); ap.add_argument('--radius', type=float, default=450)
    a = ap.parse_args(); prof = load_profile(a.profile); doc = ezdxf.readfile(a.file)
    kor = prof['layers'].get('beam_wall', '93_KORA')
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import plan_cuts as pc
    marks = [c for c in pc.cuts(doc, prof.get('cut_mark', {}).get('block', 'hat'), a.box)]
    st = strips(doc, kor); labs = label_points(doc, SHAFT_WORDS, a.box); slabs = slab_points(doc, a.box)
    print(f'{len(labs)} shaft labels, {len(st)} wall strips, {len(slabs)} slab markers')
    for name, lx, ly in labs:      # ONE pair per shaft: on its N-S wall nearest the label that borders a slab (user's 4 pairs are all on the shaft's east wall); E-W walls only if no N-S wall qualifies
        cands = []
        for s in st:
            c = (s['pos'], s['mid']) if s['o'] == 'v' else (s['mid'], s['pos'])
            d = math.dist(c, (lx, ly)); side = slab_side(s, slabs)
            if d <= a.radius and side: cands.append((s['o'] != 'v', d, s, side, c))
        if not cands: print(f'{name} at ({lx:.0f},{ly:.0f}): no wall strip bordering a slab found'); continue
        _, d, s, side, mid = min(cands, key=lambda t: t[:2]); view = VIEW[(s['o'], side)]
        done = [m for m in marks if m['num'] == '5' and math.dist(m['mid'], mid) < 150]
        print(f"{name} at ({lx:.0f},{ly:.0f}): {'N-S' if s['o'] == 'v' else 'E-W'} wall {s['w']:.0f} thick, {s['hi'] - s['lo']:.0f} long, mid ({mid[0]:.0f},{mid[1]:.0f}), slab on the {side} -> section 5 looking {view}, "
              f"{'mark exists ' + str([(round(m['mid'][0]), round(m['mid'][1])) for m in done]) if done else 'NO MARK YET'}")

if __name__ == '__main__': main()
