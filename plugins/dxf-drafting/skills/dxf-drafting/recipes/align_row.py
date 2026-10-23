#!/usr/bin/env python
"""Align every section of one white-frame ROW on ONE title line (user 2026-10-21 'section 8 too low', 2026-10-22 'when creating a cross-section file, all cross-sections must be aligned').
Generic version of align_titles.py (which had the brenda_karka constants typed in): the row = a 72_MISGERET_WIN polyline (e.g. 4000 x 450) with vertical dividers; cells = between dividers.
Per cell: title = TEXT starting with the Hebrew word for 'section' (decoded) on 54_HATAH_TEXT; envelope = everything else in the cell column (frame/claude excluded) -> distance below / above the title.
Common title line T = chosen so the TALLEST envelope is centred in the frame (same as align_titles); each cell is translated vertically by T - its title y (dimension blocks move with it).
    python align_row.py FILE [--row N] [--dry]        (N = n-th 72_MISGERET_WIN polyline with dividers, default = the LAST one = newest row)
Snapshot first (.bak-alignrow-HHMMSS). After it: text_overlap.py --fix, bar_arrays NOT needed (arrays are INSERTs and move with the section)."""
import argparse, os, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from ezdxf import bbox
import dxflib


def row_cells(doc, n=None, near=None):
    msp = doc.modelspace(); rows = []
    for e in msp.query('LWPOLYLINE'):
        if e.dxf.layer != '72_MISGERET_WIN': continue
        p = [(q[0], q[1]) for q in e.get_points('xy')]; x0, x1 = min(q[0] for q in p), max(q[0] for q in p); y0, y1 = min(q[1] for q in p), max(q[1] for q in p)
        seps = sorted(l.dxf.start.x for l in msp.query('LINE') if l.dxf.layer == '72_MISGERET_WIN' and abs(l.dxf.start.x - l.dxf.end.x) < 1e-6 and x0 < l.dxf.start.x < x1
                      and abs(min(l.dxf.start.y, l.dxf.end.y) - y0) < 2 and abs(max(l.dxf.start.y, l.dxf.end.y) - y1) < 2)
        if seps: rows.append((x0, x1, y0, y1, [x0] + seps + [x1]))
    if not rows: sys.exit('no framed row found')
    if near: rows = [r for r in rows if r[0] <= near[0] <= r[1] and r[2] - 60 <= near[1] <= r[3] + 60] or rows
    return rows[-1 if n is None else n]


def align(doc, row, dry=False):
    x0, x1, y0, y1, edges = row; msp = doc.modelspace(); H = y1 - y0
    cells = [[] for _ in edges[:-1]]; titles = {}
    for e in msp:
        if e.dxf.layer in ('72_MISGERET_WIN', 'claude') or e.dxftype() in ('XLINE', 'RAY'): continue
        try: b = bbox.extents([e])
        except Exception: continue
        if not b.has_data: continue
        cx = (b.extmin.x + b.extmax.x) / 2; cy = (b.extmin.y + b.extmax.y) / 2
        if y0 - 60 < cy < y1 + 60:
            for k in range(len(edges) - 1):
                if edges[k] < cx < edges[k + 1]:
                    cells[k].append((e, b))
                    if e.dxftype() == 'TEXT' and e.dxf.layer == '54_HATAH_TEXT' and dxflib.decode(e.dxf.text).startswith('חתך'): titles[k] = e.dxf.insert.y
    use = [k for k, c in enumerate(cells) if c and k in titles]
    st = {k: (titles[k], min(b.extmin.y for e, b in cells[k]), max(b.extmax.y for e, b in cells[k])) for k in use}
    dmax = max(t - lo for t, lo, hi in st.values()); amax = max(hi - t for t, lo, hi in st.values())
    T = y0 + (H + dmax - amax) / 2.0
    out = []
    for k, (t, lo, hi) in st.items():
        dy = T - t; out.append((k + 1, round(dy, 1), round(lo + dy - y0, 1), round(y1 - (hi + dy), 1)))
        if dry or abs(dy) < 0.05: continue
        for e, b in cells[k]: e.translate(0, dy, 0)
    return T, out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--row', type=int); ap.add_argument('--near', nargs=2, type=float, help='pick the row that contains this point (default: the newest row)'); ap.add_argument('--dry', action='store_true'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); row = row_cells(doc, a.row, a.near)
    T, rep = align(doc, row, a.dry)
    print('row', [round(v) for v in row[:4]], 'title line y', round(T, 1))
    for r in rep: print('  cell %d: moved %+.1f | bottom margin %.1f | top margin %.1f' % r)
    if not a.dry:
        bak = a.file + time.strftime('.bak-alignrow-%H%M%S'); shutil.copy2(a.file, bak); doc.saveas(a.file); print('saved; snapshot', bak)
