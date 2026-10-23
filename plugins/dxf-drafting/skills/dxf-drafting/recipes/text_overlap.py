#!/usr/bin/env python
"""Report overlapping notes on a section sheet (user 2026-10-22: text must not overlap, plan must look good; example = red cloud on 6-6, two bottom-bar notes stacked 6.7 apart).
    python text_overlap.py FILE [--fix] [--gap 2.0]
Texts on 54_HATAH_TEXT (real SHX extents). Pair overlap = boxes intersect after growing by GAP. --fix STAGGERS stacked notes (user's 6-6 fix: upper note left, lower right, shelves 4.8 apart; old behaviour = move the LOWER note (text + its shelf + fork joint, forks keep their tips)
down until clear. Snapshot first (.bak-txtov-HHMMSS). Importable: overlaps(doc) -> list of (a, b, box_a, box_b)."""
import argparse, os, re, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from shx_width import text_extent
STY = ('MIRYL', 'SIVAN', 'HEBREW_NEW')

def boxes(doc):
    out = []
    for e in doc.modelspace().query('TEXT'):
        if e.dxf.layer != '54_HATAH_TEXT' or e.dxf.style not in STY or not e.dxf.text.strip(): continue
        h = e.dxf.height; wf = e.dxf.get('width', 1.0)
        try: x0, x1 = text_extent(e.dxf.style, e.dxf.text, e.dxf.insert.x, h, wf, bool(e.dxf.get('text_generation_flag', 0) & 2))
        except Exception: continue
        y = e.dxf.insert.y; out.append((e, (min(x0, x1), y, max(x0, x1), y + h)))
    return out

def overlaps(doc, gap=2.0):
    bs = boxes(doc); res = []
    for i, (a, A) in enumerate(bs):
        for b, B in bs[i + 1:]:
            if A[0] - gap < B[2] and B[0] - gap < A[2] and A[1] - gap < B[3] and B[1] - gap < A[3]: res.append((a, b, A, B))
    return res

def _pts(e):
    if e.dxftype() == 'LINE': return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
    return [(p[0], p[1]) for p in e.get_points()]

def _set(e, old, new):
    if e.dxftype() == 'LINE':
        for k in ('start', 'end'):
            q = e.dxf.get(k)
            if abs(q.x - old[0]) < .7 and abs(q.y - old[1]) < .7: e.dxf.set(k, (new[0], new[1], 0))
    else:
        pp = list(e.get_points('xyseb'))
        e.set_points([(new[0], new[1], st, en, b) if abs(x - old[0]) < .7 and abs(y - old[1]) < .7 else (x, y, st, en, b) for x, y, st, en, b in pp], format='xyseb')

def move_note(doc, t, dy, dx=0.0, whole=False):
    """move a note down by -dy: text, its shelf (horizontal 56_HATAH_ZET line just under it) and the fork ends that start on the shelf."""
    msp = doc.modelspace(); ty = t.dxf.insert.y; tx = t.dxf.insert.x
    lines = [e for e in msp if e.dxf.layer == '56_HATAH_ZET' and e.dxftype() in ('LINE', 'LWPOLYLINE')]
    shelf = [e for e in lines if len(_pts(e)) == 2 and abs(_pts(e)[0][1] - _pts(e)[1][1]) < .01 and 0 <= ty - _pts(e)[0][1] <= 3 and min(abs(p[0] - tx) for p in _pts(e)) < 60]
    ends = {(round(x, 1), round(y, 1)) for e in shelf for x, y in _pts(e)}
    for e in lines:
        if e in shelf: continue
        for x, y in _pts(e):
            if whole or (round(x, 1), round(y, 1)) in ends: _set(e, (x, y), (x + dx, y + (dy if (round(x, 1), round(y, 1)) in ends else 0)))
    for e in shelf: 
        for x, y in _pts(e): _set(e, (x, y), (x + dx, y + dy))
    t.dxf.insert = (tx + dx, ty + dy, 0)

STAG_GAP, UP_BELOW_TIP, LO_BELOW_TIP = 12.0, 17.2, 22.0   # user's 6-6: texts 31 apart, shelves 17.2 / 22.0 under the bottom-bar dot row
PITCH = 9.0     # min vertical distance between two stacked notes (6 high + 3 clear)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--fix', action='store_true'); ap.add_argument('--gap', type=float, default=2.0); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); ov = overlaps(doc, a.gap)
    for x, y, A, B in ov: print(f'{x.dxf.handle} "{x.dxf.text}" y={A[1]:.1f}  x  {y.dxf.handle} "{y.dxf.text}" y={B[1]:.1f}')
    print(len(ov), 'overlapping pair(s)')
    if a.fix and ov:
        bak = a.file + time.strftime('.bak-txtov-%H%M%S'); shutil.copy2(a.file, bak)
        for x, y, A, B in ov:
            if any(re.match(r'^\s*2\$\d+@\d+\s*$', n.dxf.text) for n in (x, y)): print('skipped (middle-steel note: mid_note_fit.py moves it, slab notes keep their place):', x.dxf.handle, y.dxf.handle); continue      # user 2026-10-22 (his 3-3)
            lo, hi = (x, y) if A[1] < B[1] else (y, x)
            ox = min(A[2], B[2]) - max(A[0], B[0])
            if 0 < ox < 6 and abs(A[1] - B[1]) < 3:            # side-by-side labels touching: push the right one right, text only
                r = x if A[0] > B[0] else y; ins = r.dxf.insert; r.dxf.insert = (ins.x + ox + 2.5, ins.y, 0); print('shifted', r.dxf.handle, 'right', round(ox + 2.5, 1)); continue
            if ox > 0 and abs(A[1] - B[1]) < 9:                # STACKED notes (user fixed 6-6 this way, 2026-10-22): upper note LEFT, lower RIGHT, never stacked
                hb, lb = (A, B) if hi is x else (B, A)
                dx = -(hb[2] - (lb[0] - STAG_GAP))             # shift the UPPER note left; fork tips stay on their bars (only the shelf end moves)
                hy = hi.dxf.insert.y
                tipy = max((yy for e in doc.modelspace() if e.dxf.layer == '56_HATAH_ZET' and e.dxftype() == 'LINE' for _, yy in _pts(e) if hy < yy <= hy + 15), default=None)   # bottom-bar dot row the forks end on
                if tipy is None: print('skipped (no fork lines under the note - not one of the generated sections):', hi.dxf.handle, lo.dxf.handle); continue
                move_note(doc, hi, 0, dx)
                move_note(doc, hi, (tipy - UP_BELOW_TIP) - hi.dxf.insert.y + 1.2); move_note(doc, lo, (tipy - LO_BELOW_TIP) - lo.dxf.insert.y + 1.2)
                print('staggered', hi.dxf.handle, 'left', round(-dx, 1), '/', lo.dxf.handle); continue
            if ox > 0:                                         # real column overlap -> push the lower note down to PITCH
                need = PITCH - (hi.dxf.insert.y - lo.dxf.insert.y)
                if need > 0: move_note(doc, lo, -need); print('moved', lo.dxf.handle, 'down', round(need, 1))
        doc.saveas(a.file); print('saved; snapshot', bak)
