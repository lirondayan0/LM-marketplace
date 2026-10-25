"""Centre the title block (title `חתך n-n`, scale `1:25`, optional note under it) of every section cell on the section's centre line, one y per row.
User example (2026-10-15, sections_ramla.dxf, red cloud on 1-1): the title text runs right-to-left from its insert, so title insert = centre + 26.0; the scale starts at centre - 7.72;
notes (normal-direction text) are centred by their own extents. Centre line = cell x0 + 200.4 (the recipes draw at box centre + 0.4). Cells = the 72_MISGERET_WIN frames (polylines 1600 wide = 4 cells of 400, or 4000 = 10 cells; any height).
  python center_titles.py FILE [--min-y Y] [--max-y Y] [--dry]     (also called at the end of star_plan.py --draw)"""
import argparse, collections, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import ezdxf
from ezdxf import bbox
from dxflib import backup
TITLE_DX, SCALE_DX, CENTRE_OFF = 26.0, -7.72, 200.4

def cells(doc, min_y=None, max_y=None):
    out = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != '72_MISGERET_WIN' or not e.closed: continue
        b = bbox.extents([e])
        if b.size.x < 1597 or abs(b.size.x / 400 - round(b.size.x / 400)) > 0.01 or (min_y is not None and b.extmin.y < min_y) or (max_y is not None and b.extmin.y > max_y): continue
        out += [(b.extmin.x + 400 * k, b.extmin.y, b.extmax.y) for k in range(round(b.size.x / 400))]
    return out

def scale_x(title, scale, cx):
    """insert x of the `1:25` text so that its visible centre = the visible centre of the title (shx_width extents); falls back to the old fixed offset"""
    try:
        from shx_width import text_extent
        tt = title.dxf; raw = tt.text.replace('%%U', '')
        a, b = text_extent(tt.style, raw, tt.insert.x, tt.height, tt.get('width', 1.0), bool(tt.get('text_generation_flag', 0) & 2))
        sd = scale.dxf; sa, sb = text_extent(sd.style, sd.text, 0.0, sd.height, sd.get('width', 1.0))
        return (a + b) / 2 - (sa + sb) / 2
    except Exception as ex:
        print('WARNING scale text not centred under the title:', repr(ex)); return cx + SCALE_DX


def center_titles(doc, min_y=None, max_y=None, verbose=True):
    m = doc.modelspace(); rows = collections.defaultdict(list)
    for x0, y0, y1 in cells(doc, min_y, max_y):
        zone = [e for e in m.query('TEXT') if x0 < e.dxf.insert.x < x0 + 400 and y0 + 250 < e.dxf.insert.y < y1 + 10]
        title = [e for e in zone if '%%U' in e.dxf.text]
        if not title: continue
        t = max(title, key=lambda e: e.dxf.insert.y); ty = t.dxf.insert.y
        rows[y0].append((x0 + CENTRE_OFF, t, [e for e in zone if ty - 32 < e.dxf.insert.y <= ty + 1 and e is not t]))
    n = 0
    for y0, lst in rows.items():
        yt = collections.Counter(round(t.dxf.insert.y, 1) for _, t, _ in lst).most_common(1)[0][0]
        for cx, t, blk in lst:
            dy = yt - t.dxf.insert.y; t.dxf.insert = (cx + TITLE_DX, t.dxf.insert.y + dy, 0); n += 1
            for e in blk:
                if e.dxf.text == '1:25': nx = scale_x(t, e, cx)      # user 2026-10-24 (his hand edit of 17-17): the scale sits CENTRED UNDER THE VISIBLE TITLE (two-digit titles are wider: the fixed cx-7.72 left it 7.5 off)
                else: b = bbox.extents([e]); nx = e.dxf.insert.x + cx - (b.extmin.x + b.extmax.x) / 2
                e.dxf.insert = (nx, e.dxf.insert.y + dy, 0)
    if verbose: print(f'titles centred: {n} cell(s) in {len(rows)} row(s)')
    return n

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--min-y', type=float); ap.add_argument('--max-y', type=float); ap.add_argument('--dry', action='store_true'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); center_titles(doc, a.min_y, a.max_y)
    if not a.dry: backup(a.file, 'before-center-titles'); doc.saveas(a.file); print('saved')
