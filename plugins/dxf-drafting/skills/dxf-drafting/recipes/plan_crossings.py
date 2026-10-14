"""Audit of the user's dimension-line rules on one plan box (read-only). Rules (user, 2026-10-13, conventions/plan-dimensions.md):
  1 each line is continuous from the beginning to the end of the plan (no gaps / overlaps between items, spans the plan),
  2 a line states the elements of ONE side only (all measured points on one side of the line, line just outside that row),
  3 every element that intersects the line is dimensioned by it (each crossing coincides with a dim break),
  4 text of a wall item is moved slightly aside (along / perpendicular) so it is readable: narrow items show their text shift.

  python plan_crossings.py FILE --box X0 Y0 X1 Y1 [--min-items 5] [--layers 82_KIR_OLE 93_KORA ...] [-o report.txt]
Works for ANY plan: lines are found from the dimensions themselves (linear dims grouped by orientation + line coordinate), crossings from the structural layers.
Use it (a) on the user's example lines to learn, (b) on every line a recipe generates before reporting. One ezdxf load (~60 s): run once.
"""
import sys, os, math, argparse, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf

STRUCT_LAYERS = ('82_KIR_OLE', '93_KORA', '9_KONTUR', '6_HATCH', '8_KIR', '15_DASHED')   # walls/piers, beams, slab edge, openings, walls, hidden
TOL = 2.0


def segments(e):
    if e.dxftype() == 'LINE':
        yield e.dxf.start.x, e.dxf.start.y, e.dxf.end.x, e.dxf.end.y
    elif e.dxftype() == 'LWPOLYLINE':
        p = [(a, b) for a, b in e.get_points('xy')]
        for i in range(len(p) - 1 + (1 if e.closed else 0)):
            a, b = p[i], p[(i + 1) % len(p)]
            yield a[0], a[1], b[0], b[1]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True)
    ap.add_argument('--min-items', type=int, default=5); ap.add_argument('--tol', type=float, default=TOL, help='crossing counts as dimensioned when a break is within this (jog tolerance of the generator = 12.5)'); ap.add_argument('--layers', nargs='*', default=list(STRUCT_LAYERS)); ap.add_argument('-o', default='plan_crossings.txt')
    a = ap.parse_args(); x0, y0, x1, y1 = a.box
    doc = ezdxf.readfile(a.file); msp = doc.modelspace()
    lines = collections.defaultdict(list)       # (axis, line coord) -> items
    for e in msp.query('DIMENSION'):
        if e.dimtype & 7 != 0: continue
        p = e.dxf.defpoint
        if not (x0 <= p.x <= x1 and y0 <= p.y <= y1): continue
        ang = e.dxf.get('angle', 0) % 180
        p1, p3, t = e.dxf.defpoint2, e.dxf.defpoint3, e.dxf.text_midpoint
        if ang < 1:      # X line (measures along x), line at y = p.y
            lines[('X', round(p.y))].append(dict(lo=min(p1.x, p3.x), hi=max(p1.x, p3.x), side=(p1.y + p3.y) / 2 - p.y, tshift=t.x - (p1.x + p3.x) / 2, tperp=t.y - p.y))
        elif abs(ang - 90) < 1:
            lines[('Y', round(p.x))].append(dict(lo=min(p1.y, p3.y), hi=max(p1.y, p3.y), side=(p1.x + p3.x) / 2 - p.x, tshift=t.y - (p1.y + p3.y) / 2, tperp=t.x - p.x))
    lines = {k: sorted(v, key=lambda i: i['lo']) for k, v in lines.items() if len(v) >= a.min_items}
    geo = [e for e in msp if e.dxftype() in ('LINE', 'LWPOLYLINE') and e.dxf.layer in a.layers]
    from dxflib import step_groups, blue_clouds, flight_chains
    clouds = blue_clouds(doc)                                           # blue clouds = stair marks: their 15_DASHED lines are not elements to dimension (only the overall run)
    skip = set()                                                         # interior step lines of stair flights (user 2026-10-13): not dimensioned
    for axis_ in ('V', 'H'):
        cand = []
        for e in geo:
            if e.dxf.layer != '15_DASHED': continue
            for sx0, sy0, sx1, sy1 in segments(e):
                if axis_ == 'V' and abs(sx0 - sx1) < 1.5 and abs(sy1 - sy0) >= 30: cand.append((e, dict(c=(sx0 + sx1) / 2, lo=min(sy0, sy1), hi=max(sy0, sy1))))
                if axis_ == 'H' and abs(sy0 - sy1) < 1.5 and abs(sx1 - sx0) >= 30: cand.append((e, dict(c=(sy0 + sy1) / 2, lo=min(sx0, sx1), hi=max(sx0, sx1))))
        for g in step_groups([d for e, d in cand]):
            for k in g[1:-1]: skip.add((id(cand[k][0]), axis_, round(cand[k][1]['c'], 1)))
    out = open(a.o, 'w', encoding='utf-8')
    for (axis, c), items in sorted(lines.items()):
        lo, hi = items[0]['lo'], max(i['hi'] for i in items)
        gaps = [(round(items[k]['hi'], 1), round(items[k + 1]['lo'], 1)) for k in range(len(items) - 1) if abs(items[k]['hi'] - items[k + 1]['lo']) > 0.5]
        sides = collections.Counter('+' if i['side'] > TOL else '-' if i['side'] < -TOL else '0' for i in items)
        breaks = {round(i['lo']) for i in items} | {round(i['hi']) for i in items}
        miss = []
        for e in geo:
            if e.dxf.layer == '6_HATCH' and not getattr(e, 'closed', False): continue
            if e.dxf.layer == '15_DASHED' and e.dxftype() == 'LWPOLYLINE' and not e.closed and len(e) == 4:      # bearing tooth strip (user 2026-10-13): not an element to dimension
                q = [(u, v) for u, v in e.get_points('xy')]; Ls = [math.hypot(q[i + 1][0] - q[i][0], q[i + 1][1] - q[i][1]) for i in range(3)]
                if Ls[0] <= 20 and Ls[2] <= 20 and Ls[1] >= 100: continue      # open 5-point opening symbols: their diagonal is not an element face
            for sx0, sy0, sx1, sy1 in segments(e):
                if e.dxf.layer == '15_DASHED' and any(cb[0] - 5 <= min(sx0, sx1) and max(sx0, sx1) <= cb[2] + 5 and cb[1] - 5 <= min(sy0, sy1) and max(sy0, sy1) <= cb[3] + 5 for cb in clouds): continue
                if (id(e), 'V', round((sx0 + sx1) / 2, 1)) in skip and abs(sx0 - sx1) < 1.5: continue
                if (id(e), 'H', round((sy0 + sy1) / 2, 1)) in skip and abs(sy0 - sy1) < 1.5: continue
                if axis == 'X' and (sy0 - c) * (sy1 - c) < 0 and abs(sy1 - sy0) > 1e-6:
                    v = sx0 + (sx1 - sx0) * (c - sy0) / (sy1 - sy0)
                elif axis == 'Y' and (sx0 - c) * (sx1 - c) < 0 and abs(sx1 - sx0) > 1e-6:
                    v = sy0 + (sy1 - sy0) * (c - sx0) / (sx1 - sx0)
                else: continue
                if lo - 400 <= v <= hi + 400 and not any(abs(v - b) <= a.tol for b in breaks): miss.append((e.dxf.layer, round(v)))
        narrow = [(round(i['hi'] - i['lo']), round(i['tshift']), round(i['tperp'])) for i in items if i['hi'] - i['lo'] <= 60]
        out.write(f"{axis} line at {c}: {len(items)} items, {lo:.0f} -> {hi:.0f} (length {hi - lo:.0f}); continuity gaps/overlaps: {gaps or 'none'}; "
                  f"measured-point side counts (+/-/on line): {dict(sides)}  [rule 2: one side only]\n")
        out.write(f"   crossings NOT at a dim break (rule 3): {sorted(set(miss), key=lambda z: z[1]) or 'none'}\n")
        out.write(f"   narrow items (len, text shift along, text perp offset) (rule 4): {narrow[:12]}\n")
    out.close()
    print('lines found:', len(lines), '- report', a.o)


if __name__ == '__main__':
    main()
