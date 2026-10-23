"""Fit the MIDDLE-STEEL note (`2$8@15`, `2$10@15`, ...) of every section so it overlaps NOTHING (user 2026-10-22: 'position the text of the middle element so that it doesn't overlap any other text or cause any interference').
For each note: obstacles = every other text (real SHX extents), dimension lines + texts, beam / slab outline, stirrup and bar lines, leaders of OTHER notes, bar dots; the note's own shelf and forks are exempt (forks may only not cross other TEXT).
Candidates = the note + its shelf + fork joint moved by (dx, dy) on a 3-grid; the nearest candidate (cost |dx| + 1.2|dy|) whose text box (pad 1.5), shelf and forks are clear wins; none clear -> reported, not moved.
  python mid_note_fit.py FILE [--box X Y W H] [--dry]      Snapshot first (.bak-midnote-HHMMSS). Importable: fit(doc, box) -> list of messages."""
import argparse, math, os, re, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from ezdxf import bbox as BB
from shx_width import text_extent
import text_overlap as TO

MID = re.compile(r'^\s*2\$\d+@\d+\s*$')
PAD = 1.5; GRID = 3.0; DX = range(-90, 31, 3); DY = range(-60, 61, 3)

def tbox(e):
    a, b = text_extent(e.dxf.style, e.dxf.text, e.dxf.insert.x, e.dxf.height, e.dxf.get('width', 1.0), bool(e.dxf.get('text_generation_flag', 0) & 2)); y = e.dxf.insert.y
    return (min(a, b), y, max(a, b), y + e.dxf.height)

def segs(e):
    t = e.dxftype()
    if t == 'LINE': return [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))]
    if t == 'LWPOLYLINE':
        p = [(q[0], q[1]) for q in e.get_points()]
        if e.closed and p: p.append(p[0])
        return [(p[i], p[i + 1]) for i in range(len(p) - 1)]
    if t == 'LEADER':
        p = [(q[0], q[1]) for q in e.vertices]; return [(p[i], p[i + 1]) for i in range(len(p) - 1)]
    return []

def seg_hits_box(s, b):
    (x1, y1), (x2, y2) = s; dx, dy = x2 - x1, y2 - y1; t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - b[0]), (dx, b[2] - x1), (-dy, y1 - b[1]), (dy, b[3] - y1)):
        if p == 0:
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

def grow(b, g): return (b[0] - g, b[1] - g, b[2] + g, b[3] + g)
def boxes_hit(a, b): return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

def obstacles(doc, t, own):
    """(text boxes, line segments, extra boxes) around the note, own shelf / forks excluded"""
    msp = doc.modelspace(); tx, ty = t.dxf.insert.x, t.dxf.insert.y; W = (tx - 260, ty - 200, tx + 260, ty + 200)
    tb, ls, xb = [], [], []
    for e in msp.query('TEXT'):
        if e is t or e.dxf.layer in ('claude',): continue
        if not (W[0] < e.dxf.insert.x < W[2] and W[1] < e.dxf.insert.y < W[3]): continue
        try: tb.append(tbox(e))
        except Exception: pass
    for e in msp.query('LINE LWPOLYLINE LEADER'):
        if e in own or e.dxf.layer in ('72_MISGERET_WIN', 'claude', 'claude_Kontur'): continue
        for s in segs(e):
            if W[0] < s[0][0] < W[2] and W[1] < s[0][1] < W[3]: ls.append(s)
    for e in msp.query('DIMENSION'):
        if not (W[0] < e.dxf.defpoint.x < W[2] and W[1] - 80 < e.dxf.defpoint.y < W[3] + 80): continue
        try:
            for v in e.virtual_entities():
                if v.dxftype() in ('TEXT', 'MTEXT'):
                    b = BB.extents([v])
                    if b.has_data: tb.append((b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))
                else: ls += segs(v)
        except Exception: pass
    for e in msp.query('INSERT'):
        if not (W[0] < e.dxf.insert.x < W[2] and W[1] < e.dxf.insert.y < W[3]): continue
        try:
            b = BB.extents([e])
            if b.has_data and (b.extmax.x - b.extmin.x) < 12: xb.append((b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))
        except Exception: pass
    return tb, ls, xb

def own_parts(doc, t):
    lines = [e for e in doc.modelspace() if e.dxf.layer == '56_HATAH_ZET' and e.dxftype() in ('LINE', 'LWPOLYLINE')]; tx, ty = t.dxf.insert.x, t.dxf.insert.y
    shelf = [e for e in lines if len(TO._pts(e)) == 2 and abs(TO._pts(e)[0][1] - TO._pts(e)[1][1]) < .01 and 0 <= ty - TO._pts(e)[0][1] <= 3 and min(abs(p[0] - tx) for p in TO._pts(e)) < 60]
    ends = {(round(x, 1), round(y, 1)) for e in shelf for x, y in TO._pts(e)}
    forks = [e for e in lines if e not in shelf and any((round(x, 1), round(y, 1)) in ends for x, y in TO._pts(e))]
    return shelf, forks

def clear(box, shelf_segs, fork_segs, tb, ls, xb):
    B = grow(box, PAD)
    if any(boxes_hit(B, o) for o in tb) or any(boxes_hit(B, o) for o in xb): return False
    if any(seg_hits_box(s, B) for s in ls): return False
    for s in shelf_segs:
        if any(seg_hits_box(s, grow(o, 0.3)) for o in tb): return False
        if any(_cross(s, q) for q in ls): return False
    for s in fork_segs:
        if any(seg_hits_box(s, grow(o, 0.3)) for o in tb): return False
    return True

def _cross(s, q):
    d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return d(s[0], s[1], q[0]) * d(s[0], s[1], q[1]) < -1e-9 and d(q[0], q[1], s[0]) * d(q[0], q[1], s[1]) < -1e-9

def fit(doc, box=None):
    msg = []
    for t in list(doc.modelspace().query('TEXT')):
        if not MID.match(t.dxf.text) or t.dxf.layer != '54_HATAH_TEXT': continue
        if box and not (box[0] < t.dxf.insert.x < box[0] + box[2] and box[1] < t.dxf.insert.y < box[1] + box[3]): continue
        shelf, forks = own_parts(doc, t)
        if not shelf: msg.append(f'{t.dxf.handle} {t.dxf.text}: no shelf found, skipped'); continue
        own = set(shelf) | set(forks); tb, ls, xb = obstacles(doc, t, own); b0 = tbox(t)
        shelf_s = [s for e in shelf for s in segs(e)]; fork_s = [s for e in forks for s in segs(e)]
        ends = {(round(x, 1), round(y, 1)) for e in shelf for x, y in TO._pts(e)}
        def moved(dx, dy):
            sh = [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)) for a, b in shelf_s]
            fk = []
            for a, b in fork_s:
                fk.append((((a[0] + dx, a[1] + dy) if (round(a[0], 1), round(a[1], 1)) in ends else a), ((b[0] + dx, b[1] + dy) if (round(b[0], 1), round(b[1], 1)) in ends else b)))
            return sh, fk
        best = None
        for dx in DX:
            for dy in DY:
                c = abs(dx) + 1.2 * abs(dy)
                if best and c >= best[0]: continue
                sh, fk = moved(dx, dy)
                if clear((b0[0] + dx, b0[1] + dy, b0[2] + dx, b0[3] + dy), sh, fk, tb, ls, xb): best = (c, dx, dy)
        if best is None: msg.append(f'{t.dxf.handle} {t.dxf.text} at ({t.dxf.insert.x:.0f}, {t.dxf.insert.y:.0f}): NO clear position within the search window - left as is'); continue
        if best[1] or best[2]:
            TO.move_note(doc, t, best[2], best[1]); msg.append(f'{t.dxf.handle} {t.dxf.text}: moved ({best[1]:+d}, {best[2]:+d})')
        else: msg.append(f'{t.dxf.handle} {t.dxf.text}: already clear')
    return msg

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float); ap.add_argument('--dry', action='store_true'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); res = fit(doc, a.box); print('\n'.join(res) or 'no middle-steel notes'); 
    if a.dry or not any('moved' in r for r in res): sys.exit()
    shutil.copy2(a.file, a.file + time.strftime('.bak-midnote-%H%M%S')); doc.saveas(a.file); print('saved', a.file)