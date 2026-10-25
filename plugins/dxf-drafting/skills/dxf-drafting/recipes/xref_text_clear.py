"""Recipe: clear host notes of XREF sections (user 2026-10-23, 3841-CON_test.dxf: text must not overlap other text or the section XREFs, make it look good).
  python xref_text_clear.py FILE [--dry] [--gap 1.5] [--max-shift 60]
A note = a TEXT on 54_HATAH_TEXT + its shelf (56_HATAH_ZET polyline whose last segment is horizontal, text standing on it) + the leader parts behind the shelf
(single tip: the tip stays, elbow + shelf move; fork: the joint = polyline[0] with the LINEs ending on it moves, the fork tips stay on the bars).
Every note whose box (grown by GAP) hits XREF text / XREF lines / other notes / host bars, or whose moved shelf would hit them, is moved to the nearest free (dx, dy) on a STEP grid
(HORIZONTAL slides (<= 50) with the leader stretched; --vertical = allow a vertical fallback for notes with no free horizontal place); notes that do not conflict are never touched. Sections = INSERT names '... Sec N-N'; a host note belongs to the nearest section.
RULE (user 2026-10-23): a leader is never cut - shelf and fork lines move together, connectivity is asserted before saving.
Snapshot FILE.bak-textclear-HHMMSS before writing (in place). Idempotent. Verify with a render afterwards."""
import argparse, math, os, re, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from ezdxf import bbox as BB
from shx_width import text_extent
from dxflib import xref_section_number

NOTE_LAYER = '54_HATAH_TEXT'; ZET = '56_HATAH_ZET'; BAR_LAYERS = ('51_HATAH_DASHED', '57_HATAH_ZIUN'); STEP = 2.5; H_MAX = 50.0

def lay(e): return e.dxf.layer.split('$0$')[-1]
def tbox(e):
    h = e.dxf.height
    try: x0, x1 = text_extent(e.dxf.style, e.dxf.text, e.dxf.insert.x, h, e.dxf.get('width', 1.0), bool(e.dxf.get('text_generation_flag', 0) & 2))
    except Exception: return None
    x0, x1 = min(x0, x1), max(x0, x1); y = e.dxf.insert.y
    return (x0, y, x1, y + h)
def grow(b, g): return (b[0] - g, b[1] - g, b[2] + g, b[3] + g)
def hit(a, b): return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
def seg_hit(b, s):
    (ax, ay), (bx, by) = s; t0, t1 = 0.0, 1.0; dx, dy = bx - ax, by - ay
    for p, q in ((-dx, ax - b[0]), (dx, b[2] - ax), (-dy, ay - b[1]), (dy, b[3] - ay)):
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
def explode(e, out):
    for v in e.virtual_entities():
        if v.dxftype() == 'INSERT': explode(v, out)
        elif v.dxftype() == 'DIMENSION':
            try: out.extend(v.virtual_entities())
            except Exception: pass
        else: out.append(v)
def pts(e):
    if e.dxftype() == 'LINE': return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
    return [(a[0], a[1]) for a in e.get_points()]
def segs_of(e):
    p = pts(e); return list(zip(p, p[1:]))
def sbox(sg): return (min(sg[0][0], sg[1][0]), min(sg[0][1], sg[1][1]), max(sg[0][0], sg[1][0]), max(sg[0][1], sg[1][1]))

def xref_sections(msp):
    secs = []
    for ins in msp.query('INSERT'):
        sec = xref_section_number(ins.dxf.name)
        if sec is None: continue
        ents = []; explode(ins, ents); segs = []; txt = []
        for s in ents:
            t = s.dxftype()
            if t == 'LINE': segs.append(((s.dxf.start.x, s.dxf.start.y), (s.dxf.end.x, s.dxf.end.y)))
            elif t == 'LWPOLYLINE': segs += segs_of(s)
            elif t in ('TEXT', 'MTEXT'):
                b = BB.extents([s])
                if b.has_data: txt.append((b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))
        if not segs: continue
        xs = [v for a, b in segs for v in (a[0], b[0])]; ys = [v for a, b in segs for v in (a[1], b[1])]
        secs.append(dict(n=sec, segs=segs, txt=txt, bb=(min(xs), min(ys), max(xs), max(ys))))
    return secs

def run(F, dry=False, gap=1.5, max_shift=60.0, vertical=False):
    doc = ezdxf.readfile(F); msp = doc.modelspace(); secs = xref_sections(msp)
    def owner(x, y):
        best = None
        for s in secs:
            b = s['bb']; d = max(b[0] - x, 0, x - b[2]) ** 2 + max(b[1] - y, 0, y - b[3]) ** 2
            if best is None or d < best[0]: best = (d, s)
        return best[1] if best and best[0] < 250 ** 2 else None
    notes = []; host_lines = []; zet = []
    for e in msp:
        t = e.dxftype(); ly = e.dxf.layer
        if e.has_xdata('DXFSKILL_TEMPLATE'): continue            # a copied hand-drawn reference section is final (scripts/ref_library.py)
        if t == 'TEXT' and ly == NOTE_LAYER and e.dxf.text.strip():
            b = tbox(e)
            if b: notes.append(dict(e=e, box=b, sec=owner((b[0] + b[2]) / 2, b[1])))
        elif ly == ZET and t in ('LINE', 'LWPOLYLINE'): zet.append(e)
        elif ly in BAR_LAYERS and t in ('LINE', 'LWPOLYLINE'): host_lines.append(e)
    def horiz(z):
        """(y, x0, x1, joint) of a shelf: LWPOLYLINE with horizontal last segment, or a horizontal LINE (joint decided later)"""
        p = pts(z)
        if len(p) < 2 or abs(p[-1][1] - p[-2][1]) > 0.01: return None
        return p[-1][1], min(p[-1][0], p[-2][0]), max(p[-1][0], p[-2][0])
    def at(q, j): return math.hypot(q[0] - j[0], q[1] - j[1]) < 0.05
    shelves = [(z, h) for z in zet for h in [horiz(z)] if h is not None]
    xov = lambda h, bx: min(h[2], bx[2]) - max(h[1], bx[0])
    cand = []
    for i, n in enumerate(notes):
        bx = n['box']; w_ = max(bx[2] - bx[0], 1.0)
        for z, h in shelves:                       # the text STANDS ON its shelf: base 0..3.6 above it and most of the text over the shelf (user 2026-10-23); touching the shelf end is accepted (generator notes hang past it)
            dy = bx[1] - h[0]
            if -0.8 <= dy <= 3.6 and (xov(h, bx) >= 0.3 * w_ or xov(h, bx) >= -3.0): cand.append((xov(h, bx), i, id(z), z))
    cand.sort(key=lambda c: -c[0]); taken_t, taken_z, pick_ = set(), set(), {}
    for sc, i, zid, z in cand:                     # one text per shelf (best overlap first): two notes at the same height must not be glued to one shelf
        if i in taken_t or zid in taken_z: continue
        taken_t.add(i); taken_z.add(zid); pick_[i] = z
    for i, n in enumerate(notes):
        bx = n['box']; w_ = max(bx[2] - bx[0], 1.0); best = (0, pick_[i]) if i in pick_ else None; n['stack'] = False
        if best is None:                           # second line of a stacked note: above the shelf of its first line (<= 16 up)
            for z, h in shelves:
                dy = bx[1] - h[0]
                if 3.6 < dy <= 16.0 and xov(h, bx) >= 0.3 * w_ and (best is None or dy < best[0]): best = (dy, z)
            n['stack'] = best is not None
        n['shelf'] = best[1] if best else None; n['forks'] = []; n['fork'] = False; n['joint'] = None
        if n['shelf'] is None: continue
        z = n['shelf']; p = pts(z)
        if z.dxftype() == 'LWPOLYLINE':   # the joint can be either END of the polyline (shelf drawn free-end -> joint, user 2026-10-23: such a leader was CUT by a one-sided move)
            for j in (p[0], p[-1]):
                fk = [l for l in zet if l.dxftype() == 'LINE' and any(at(q, j) for q in pts(l))]
                if fk: n['joint'] = j; n['forks'] = fk; break
            if n['joint'] is None: n['joint'] = p[0]
        else:   # LINE shelf: the end where leader LINEs meet is the joint
            for j in p:
                fk = [l for l in zet if l is not z and l.dxftype() == 'LINE' and any(at(q, j) for q in pts(l))]
                if fk: n['joint'] = j; n['forks'] = fk; break
        n['fork'] = bool(n['forks'])
    grid = [i * STEP for i in range(-int(max_shift / STEP), int(max_shift / STEP) + 1)]
    # USER RULE 2026-10-23: clear text by sliding it LEFT / RIGHT with its leader stretched (tips stay on the bars). Pass 1 = horizontal only (<= H_MAX);
    # pass 2 (fallback, reported) = small vertical lift, because some notes (top-bar note beside the XREF level marker) have no free horizontal place.
    hgrid = [i * STEP for i in range(-int(min(max_shift, H_MAX) / STEP), int(min(max_shift, H_MAX) / STEP) + 1)]
    cands_h = sorted(((dx, 0.0) for dx in hgrid), key=lambda c: abs(c[0]))
    cands_v = sorted(((dx, dy) for dx in grid for dy in grid if dy != 0), key=lambda c: (c[1] ** 2 * 4.0 + c[0] ** 2, abs(c[0])))
    moved = 0
    by_shelf = {}
    for n in notes:
        if n['shelf'] is not None: by_shelf.setdefault(id(n['shelf']), []).append(n)
    for g_ in by_shelf.values():
        g_.sort(key=lambda m: m['stack'])
        # several texts on ONE shelf / leader (e.g. a note with two lines) move together, the first is the leader of the group
        for m_ in g_[1:]: m_['follower'] = True
        g_[0]['members'] = g_
    for n in notes:
        s = n['sec']
        if s is not None and n['shelf'] is None:       # a note whose shelf could not be identified is NOT moved - report it when it conflicts
            g0 = grow(n['box'], gap)
            if any(hit(g0, grow(b, gap)) for b in s['txt']) or any(seg_hit(g0, sg) for sg in s['segs']): print('Sec', s['n'], n['e'].dxf.handle, repr(n['e'].dxf.text), 'UNATTACHED (no shelf) and in conflict - fix by hand')
        if s is None or n['shelf'] is None or n.get('follower'): continue
        mem = n.get('members', [n])
        own = {id(m['e']) for m in n.get('members', [n])} | {id(n['shelf'])} | {id(z) for z in n['forks']}
        obst_box = [grow(b, gap) for b in s['txt']] + [grow(m['box'], gap) for m in notes if m not in mem and m['sec'] is s]
        obst_seg = list(s['segs'])
        for e in host_lines + zet:
            if id(e) in own: continue
            q = pts(e)
            if not any(s['bb'][0] - 200 < v[0] < s['bb'][2] + 200 and s['bb'][1] - 100 < v[1] < s['bb'][3] + 100 for v in q): continue
            if len(q) == 2 and abs(q[0][0] - q[1][0]) < 3 and abs(q[0][1] - q[1][1]) < 3: continue
            obst_seg += segs_of(e)
        sp = pts(n['shelf']); line_shelf = n['shelf'].dxftype() == 'LINE'
        def ok(dx, dy):
            for m in mem:
                b = (m['box'][0] + dx, m['box'][1] + dy, m['box'][2] + dx, m['box'][3] + dy); g = grow(b, gap)
                if any(hit(g, o) for o in obst_box): return False
                if any(seg_hit(g, sg) for sg in obst_seg): return False
            q = [(x + dx, y + dy) if (i > 0 or n['fork'] or line_shelf) else (x, y) for i, (x, y) in enumerate(sp)]
            for sg in zip(q, q[1:]):
                if any(seg_hit(o, sg) for o in obst_box): return False
            return True
        if ok(0, 0): continue
        pick = next((c for c in cands_h if ok(*c)), None); vert = False
        if pick is None and vertical: pick = next((c for c in cands_v if ok(*c)), None); vert = pick is not None
        if pick is None: print('Sec', s['n'], n['e'].dxf.handle, 'NO FREE PLACE (left in place)'); continue
        dx, dy = pick; print('Sec', s['n'], n['e'].dxf.handle, 'shift', pick, '(VERTICAL fallback)' if vert else ''); moved += 1
        # the moved note becomes an obstacle for the others
        for m in mem: m['box'] = (m['box'][0] + dx, m['box'][1] + dy, m['box'][2] + dx, m['box'][3] + dy)
        if dry: continue
        for m in mem:
            e = m['e']; e.dxf.insert = (e.dxf.insert.x + dx, e.dxf.insert.y + dy, e.dxf.insert.z)
            if e.dxf.hasattr('align_point'):
                ap = e.dxf.align_point; e.dxf.align_point = (ap.x + dx, ap.y + dy, ap.z)
        z = n['shelf']
        if line_shelf:
            z.dxf.start = (z.dxf.start.x + dx, z.dxf.start.y + dy, z.dxf.start.z); z.dxf.end = (z.dxf.end.x + dx, z.dxf.end.y + dy, z.dxf.end.z)
        else:
            q = list(z.get_points('xyseb'))
            for i in range(len(q)):
                if i > 0 or n['fork']: q[i] = (q[i][0] + dx, q[i][1] + dy) + tuple(q[i][2:])
            z.set_points(q, format='xyseb')
        for l in n['forks']:
            for attr in ('start', 'end'):
                v = getattr(l.dxf, attr)
                if at((v.x, v.y), n['joint']): setattr(l.dxf, attr, (v.x + dx, v.y + dy, v.z))
    broken = 0
    for n in notes:   # LEADER MUST NEVER BE CUT: every fork line still has an end on the shelf end
        if n['shelf'] is None or not n['forks']: continue
        ends = [pts(n['shelf'])[0], pts(n['shelf'])[-1]]
        for l in n['forks']:
            if not any(math.hypot(q[0] - e[0], q[1] - e[1]) < 0.05 for q in pts(l) for e in ends): broken += 1; print('LEADER CUT', n['e'].dxf.handle, l.dxf.handle)
    if broken: raise SystemExit('refusing to save: %d cut leader(s)' % broken)
    print(moved, 'note(s) moved')
    if moved and not dry:
        shutil.copy2(F, F + '.bak-textclear-' + time.strftime('%H%M%S')); doc.saveas(F)
    return moved

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--dry', action='store_true')
    ap.add_argument('--gap', type=float, default=1.5); ap.add_argument('--max-shift', type=float, default=60.0); ap.add_argument('--vertical', action='store_true'); a = ap.parse_args()
    run(a.file, a.dry, a.gap, a.max_shift, a.vertical)
