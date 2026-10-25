#!/usr/bin/env python
"""Make every white template row (72_MISGERET_WIN, 10 cells of 400) hold its sections ENTIRELY (user 2026-10-24 'the grid template must be adjusted so the sections do not extend beyond its boundaries').
The stack = the touching frames of the row nearest to --near, top row first. Per row, top to bottom:
  1. content per cell = every entity whose centre is in the cell column and in the row's band (frame edge .. half way to the next row; 150 beyond the stack) - NOT the +-60 of align_row, which pulled the
     notes of the row above into the row below;
  2. needed height = (title - lowest point) + (highest point - title) + 2 * MARGIN; a row that is lower grows DOWNWARD and everything below it (frames, dividers, sections) is moved down by the growth;
  3. every cell hangs from ONE title line, the tallest envelope centred in the frame (same rule as align_row).
Rows are never shrunk. A cell whose content is wider than its 400 (+ XM each side) is WIDENED (`widen`): the cells to its right, their dividers and the frame edge move right, the content is centred; rows stay independent.
    python fit_rows.py FILE [--near X Y] [--dry]
Snapshot first (.bak-fitrows-HHMMSS)."""
import argparse, os, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from ezdxf import bbox
import dxflib

XM = 10.0                          # clear space between a cell's content and the cell's side dividers (a cell is widened when the content needs more)
MARGIN = 25.0                      # clear space between the section's lowest / highest point and the frame (star_plan.MARGIN)
BEYOND = 150.0                     # content this far outside the stack still belongs to the outer rows (notes hanging below the last frame)
LAYER = '72_MISGERET_WIN'


def frames(doc):
    """[(x0, x1, y0, y1, polyline, [x edges])] of every framed row (closed polyline with vertical dividers)"""
    msp = doc.modelspace(); out = []
    lines = [l for l in msp.query('LINE') if l.dxf.layer == LAYER and abs(l.dxf.start.x - l.dxf.end.x) < 1e-6]
    for e in msp.query('LWPOLYLINE'):
        if e.dxf.layer != LAYER or not e.closed: continue
        p = [(q[0], q[1]) for q in e.get_points('xy')]; x0, x1 = min(q[0] for q in p), max(q[0] for q in p); y0, y1 = min(q[1] for q in p), max(q[1] for q in p)
        seps = sorted(l.dxf.start.x for l in lines if x0 < l.dxf.start.x < x1 and abs(min(l.dxf.start.y, l.dxf.end.y) - y0) < 2 and abs(max(l.dxf.start.y, l.dxf.end.y) - y1) < 2)
        if seps: out.append((x0, x1, y0, y1, e, [x0] + seps + [x1]))
    return out


def stack(doc, near=None):
    """the touching frames (same x extent) of the row nearest to `near` (default: the lowest frame), top row first"""
    fr = frames(doc)
    if not fr: sys.exit('no framed row found')
    if near: seed = min(fr, key=lambda r: (0 if r[0] <= near[0] <= r[1] else 1e9) + max(0, r[2] - near[1], near[1] - r[3]))
    else: seed = min(fr, key=lambda r: r[2])
    same = sorted([r for r in fr if abs(r[0] - seed[0]) < 2], key=lambda r: -r[3])                 # same left edge; a row widened by widen() is wider than its neighbours
    i = same.index(seed); chain = [seed]
    for r in same[i + 1:]:
        if chain[-1][2] - r[3] <= 3: chain.append(r)
        else: break
    for r in reversed(same[:i]):
        if r[2] - chain[0][3] <= 3: chain.insert(0, r)
        else: break
    return chain


def candidates(doc, ch):
    """entities near the stack (bbox once per run: it is the slow part), as the list content() / move_below() scan"""
    x0, x1 = ch[0][0] - 300, ch[0][1] + 300; yt, yb = ch[0][3] + BEYOND, ch[-1][2] - 3000.0; out = []
    for e in doc.modelspace():
        if e.dxf.layer == 'claude' or e.dxftype() in ('XLINE', 'RAY'): continue       # frames stay in: move_below carries the lower rows' frames and dividers
        try: b = bbox.extents([e])
        except Exception: continue
        if b.has_data and b.size.x <= 4500 and b.extmax.x > x0 and b.extmin.x < x1 and b.extmax.y > yb and b.extmin.y < yt: out.append(e)
    return out


GROUP_IN = 7.5       # min distance of a tagged detail group (beam_shutter stirrup detail) from the left divider of its cell


def content(doc, row, top_lim, bot_lim, cand):
    """per cell: [(entity, bbox)] of everything whose centre is in the column and between bot_lim and top_lim; titles {cell: y}.
    Pieces tagged as ONE object (XDATA DXFSKILL_GROUP: beam_shutter's stirrup detail = polyline + 2 dims + note) follow the cell of their polyline, wherever their own centres fall (they straddle the divider)."""
    x0, x1, y0, y1, _, edges = row; cells = [[] for _ in edges[:-1]]; titles = {}; groups = {}
    for e in cand:
        if e.dxf.layer == LAYER: continue
        try: b = bbox.extents([e])
        except Exception: continue
        if not b.has_data or b.size.x > 1500: continue
        cx = (b.extmin.x + b.extmax.x) / 2; cy = (b.extmin.y + b.extmax.y) / 2
        if not bot_lim < cy < top_lim: continue
        if e.has_xdata('DXFSKILL_GROUP'): groups.setdefault(e.get_xdata('DXFSKILL_GROUP')[0].value, []).append((e, b, cx)); continue
        for k in range(len(edges) - 1):
            if edges[k] < cx < edges[k + 1]:
                cells[k].append((e, b))
                if e.dxftype() == 'TEXT' and e.dxf.layer == '54_HATAH_TEXT' and dxflib.decode(e.dxf.text).startswith('חתך'): titles[k] = e.dxf.insert.y
    for mem in groups.values():
        home = next((k for e, b, cx in mem if e.dxftype() == 'LWPOLYLINE' for k in range(len(edges) - 1) if edges[k] < cx < edges[k + 1]), None)
        if home is not None: cells[home] += [(e, b) for e, b, cx in mem]
    for k, lst in enumerate(cells):                 # his netivot 9-9: the stirrup detail sits INSIDE its cell (7.5 from the divider) and clear of the section: the WHOLE cell content moves right, the cell is widened below if it no longer fits
        g = [b for e, b in lst if e.has_xdata('DXFSKILL_GROUP')]
        if not g: continue
        dx = edges[k] + GROUP_IN - min(b.extmin.x for b in g)
        if dx > 0.05:
            for e, b in lst: e.translate(dx, 0, 0)
            cells[k] = [(e, bbox.extents([e])) for e, b in lst]
            if k in titles: pass
    return cells, titles


def move_below(cand, x0, x1, y_cut, y_floor, d):
    """translate down by d everything in the column band whose centre is between y_floor and y_cut (the rows below the grown one: frames, dividers, sections; the user's clouds stay)"""
    n = 0
    for e in cand:
        try: b = bbox.extents([e])
        except Exception: continue
        if not b.has_data or b.size.x > 4500: continue
        cx = (b.extmin.x + b.extmax.x) / 2; cy = (b.extmin.y + b.extmax.y) / 2
        if x0 - 100 < cx < x1 + 100 and y_floor < cy < y_cut: e.translate(0, -d, 0); n += 1
    return n


def grow_frame(doc, row, d):
    """pull the bottom edge of one framed row (polyline + its dividers) down by d"""
    x0, x1, y0, y1, e, edges = row
    e.set_points([(q[0], q[1] - d if abs(q[1] - y0) < 1 else q[1]) for q in e.get_points('xy')])
    for l in doc.modelspace().query('LINE'):
        if l.dxf.layer == LAYER and abs(l.dxf.start.x - l.dxf.end.x) < 1e-6 and x0 < l.dxf.start.x < x1 and abs(min(l.dxf.start.y, l.dxf.end.y) - y0) < 2 and abs(max(l.dxf.start.y, l.dxf.end.y) - y1) < 2:
            x = l.dxf.start.x; l.dxf.start = (x, y0 - d, 0); l.dxf.end = (x, y1, 0)


def widen(doc, near, cand, dry=False):
    """user 2026-10-24 ('the sections must not extend beyond the template'): a cell whose content (+ XM each side) is wider than the cell is WIDENED: its right divider and everything right of it in that row
    (dividers, frame edge, the other cells' content) move right by the excess, the content is centred in the wider cell. Rows are independent (a wider row is simply wider than the rows above / below)."""
    rep = []
    for row in stack(doc, near):
        x0, x1, y0, y1, e, edges = row; cells, titles = content(doc, row, y1 + 0.5, y0 - 0.5, cand); n = len(edges) - 1; need = [0.0] * n; span = {}
        for k in range(n):
            if cells[k] and k in titles:
                lo = min(b.extmin.x for _, b in cells[k]); hi = max(b.extmax.x for _, b in cells[k]); span[k] = (lo, hi); need[k] = hi - lo + 2 * XM
        if not any(need[k] > edges[k + 1] - edges[k] + 0.5 for k in range(n)): continue
        new = [edges[0]]
        for k in range(n): new.append(new[-1] + max(edges[k + 1] - edges[k], need[k] if k in span else 0.0))
        rep.append(f'row y {y0:g}..{y1:g}: wider cell(s) {[k + 1 for k in range(n) if new[k + 1] - new[k] > edges[k + 1] - edges[k] + 0.5]}, row now {new[-1] - new[0]:.0f} wide')
        if dry: continue
        for k in range(n):                                          # content first (the dividers are not in `cells`)
            if k in span: dx = (new[k] + new[k + 1]) / 2 - (span[k][0] + span[k][1]) / 2 if new[k + 1] - new[k] > edges[k + 1] - edges[k] + 0.5 else new[k] - edges[k]
            else: dx = new[k] - edges[k]
            if abs(dx) > 0.05:
                for ent, _ in cells[k]: ent.translate(dx, 0, 0)
        for l in doc.modelspace().query('LINE'):
            if l.dxf.layer == LAYER and abs(l.dxf.start.x - l.dxf.end.x) < 1e-6 and x0 < l.dxf.start.x < x1 and abs(min(l.dxf.start.y, l.dxf.end.y) - y0) < 2 and abs(max(l.dxf.start.y, l.dxf.end.y) - y1) < 2:
                j = min(range(1, n), key=lambda j: abs(edges[j] - l.dxf.start.x)); l.dxf.start = (new[j], l.dxf.start.y, 0); l.dxf.end = (new[j], l.dxf.end.y, 0)
        e.set_points([(new[-1] if abs(q[0] - x1) < 1 else q[0], q[1]) for q in e.get_points('xy')])
    return rep


def fit(doc, near=None, dry=False):
    rep = []; n = len(stack(doc, near)); cand = candidates(doc, stack(doc, near))
    for i in range(n):
        ch = stack(doc, near); row = ch[i]; x0, x1, y0, y1, e, edges = row; H = y1 - y0
        top_lim = y1 + (BEYOND if i == 0 else 0.5)
        bot_lim = y0 - (BEYOND if i == n - 1 else 0.5)
        cells, titles = content(doc, row, top_lim, bot_lim, cand)
        use = [k for k, c in enumerate(cells) if c and k in titles]
        if not use: rep.append(f'row y {y0:g}..{y1:g}: no sections'); continue
        st = {k: (titles[k], min(b.extmin.y for _, b in cells[k]), max(b.extmax.y for _, b in cells[k])) for k in use}
        dmax = max(t - lo for t, lo, hi in st.values()); amax = max(hi - t for t, lo, hi in st.values()); need = dmax + amax + 2 * MARGIN
        if need > H + 0.5:
            d = need - H; rep.append(f'row y {y0:g}..{y1:g} grown by {d:.0f} (needs {need:.0f})')
            if dry: continue
            floor = ch[-1][2] - BEYOND; move_below(cand, x0, x1, y0 + 0.5, floor, d)
            grow_frame(doc, row, d)                                  # AFTER the move (the grown frame would be caught by it); `row` still holds the frame entities
            y0 -= d; H += d
        T = y0 + (H + dmax - amax) / 2.0
        for k in use:
            dy = T - st[k][0]
            if dry or abs(dy) < 0.05: continue
            for ent, _ in cells[k]: ent.translate(0, dy, 0)
    return rep + widen(doc, near, cand, dry)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--near', nargs=2, type=float, help='a point in (or beside) the stack of rows; default = the lowest frame'); ap.add_argument('--dry', action='store_true'); ap.add_argument('-o'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); rep = fit(doc, a.near, a.dry)
    print('\n'.join(rep) or 'every row already holds its sections')
    if not a.dry:
        out = a.o or a.file
        if not a.o: bak = a.file + time.strftime('.bak-fitrows-%H%M%S'); shutil.copy2(a.file, bak); print('snapshot', bak)
        doc.saveas(out); print('saved', out)
