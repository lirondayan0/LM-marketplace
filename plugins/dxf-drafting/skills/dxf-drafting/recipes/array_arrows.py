"""Recipe: a bar array follows its ARROW (user 2026-10-25, section 9-9 of netivot: 'position the rebar array by where I place the array arrow; the last bar aligns with that point and the spacing adjusts').
  python array_arrows.py FILE --box X0 Y0 X1 Y1 [--dry] [-o OUT]
Run BEFORE bar_arrays.py (the dots are still loose polylines). For every run of >= 2 equally spaced dots (the same runs bar_arrays turns into one array each): the arrow tip of the leader fork
that points at the LAST dot (right / top end; the source dot = left / lowest stays) is looked up on layer 56_HATAH_ZET; the last dot moves ONTO the tip (centre = tip along the run; with an arrow at the first dot too the array is as long as the two arrows are apart) and the dots between
are redistributed with equal spacing (count unchanged). A tip is accepted when it lies on the run's line (<= 3.5 across) and no more than REACH beyond / TOL before the last dot, so a tip the user moved
a little still drives the array; no tip = untouched. Dots only (the leaders and everything else stay). Idempotent. Snapshot FILE.bak-arrows-HHMMSS (in place) or -o OUT."""
import argparse, os, sys, shutil, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))      # python -I: the script folder is not on the path
import ezdxf
import bar_arrays as BA

ZET = '56_HATAH_ZET'; ACROSS = 3.5; REACH = 15.0; TOL = 3.0; MIN_STEP = 2.0


def tips(doc, box):
    """end points of the leader lines (LINE / LWPOLYLINE) on the leader layer inside the box; the shelf end is a tip candidate too, but only tips on a run's row are used"""
    out = []
    for e in doc.modelspace():
        if e.dxf.layer != ZET: continue
        if e.dxftype() == 'LINE': p = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif e.dxftype() == 'LWPOLYLINE': p = [(a, b) for a, b, *_ in e.get_points()]
        else: continue
        for q in (p[0], p[-1]):
            if box[0] - 30 <= q[0] <= box[2] + 30 and box[1] - 30 <= q[1] <= box[3] + 30: out.append(q)
    return out


def move(e, dx, dy):
    if e.dxftype() == 'INSERT': e.dxf.insert = (e.dxf.insert.x + dx, e.dxf.insert.y + dy, e.dxf.insert.z)
    else:
        pts = list(e.get_points('xyseb')); e.set_points([(p[0] + dx, p[1] + dy, *p[2:]) for p in pts], format='xyseb')


def fit(doc, box, dry=False):
    """-> list of (direction, n, old last, new last, step)"""
    dots = BA.dots_in(doc, box); T = tips(doc, box); by = {h: doc.entitydb[h] for h, _, _ in dots}; done = []
    H, left = BA.runs(dots, lambda t: t[2], lambda t: t[1], tol=1.2)      # loose tolerance: the arrow may already have pulled the last dot a little
    V, _ = BA.runs(left, lambda t: t[1], lambda t: t[2], tol=1.2)
    runs_ = [('H', r) for r in H] + [('V', r) for r in V]
    for k, r in runs_:
        P = sorted(r, key=lambda t: t[1] if k == 'H' else t[2]); n = len(P)
        ax = 1 if k == 'H' else 2; cx = 2 if k == 'H' else 1           # axis index, cross index in (h, x, y)
        first, last = P[0], P[-1]; cross = last[cx]
        cand = [q for q in T if abs(q[1 - (ax - 1)] - cross) <= ACROSS and last[ax] - TOL <= q[ax - 1] <= last[ax] + REACH]
        if not cand: continue
        tip = min(cand, key=lambda q: abs(q[ax - 1] - last[ax])); target = tip[ax - 1]
        ftip = [q for q in T if abs(q[1 - (ax - 1)] - cross) <= ACROSS and abs(q[ax - 1] - first[ax]) <= TOL]
        if ftip: target = first[ax] + (target - min(ftip, key=lambda q: abs(q[ax - 1] - first[ax]))[ax - 1])      # an arrow at BOTH ends: the array is exactly as long as the arrows are apart (his 9-9: tips 41315.1 / 41436.3 -> bars 41314.4 .. 41435.7)
        d = target - last[ax]
        if abs(d) < 0.05: continue
        step = (target - first[ax]) / (n - 1)
        if step < MIN_STEP: continue
        for i, t in enumerate(P[1:], 1):
            new = first[ax] + i * step; delta = new - t[ax]
            if abs(delta) > 1e-6 and not dry: move(by[t[0]], delta if k == 'H' else 0.0, delta if k == 'V' else 0.0)
        done.append((k, n, round(last[ax], 2), round(target, 2), round(step, 3)))
    return done


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True); ap.add_argument('--dry', action='store_true'); ap.add_argument('-o')
    a = ap.parse_args(); doc = ezdxf.readfile(a.file)
    done = fit(doc, a.box, a.dry)
    for k, n, o, t, s in done: print(f'array {k} x{n}: last bar {o} -> {t} (on the arrow), spacing {s}')
    print(f'{len(done)} array(s) fitted to their arrows')
    if a.dry or not done: return
    if not a.o: print('snapshot:', BA.shutil.copy2(a.file, f'{a.file}.bak-arrows-{time.strftime("%H%M%S")}'))
    doc.saveas(a.o or a.file); print('saved', a.o or a.file)


if __name__ == '__main__': main()
