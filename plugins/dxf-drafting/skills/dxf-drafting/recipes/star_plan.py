"""Planner for the user's STAR MARKERS (hat `*` pairs on layer automatic_sections): reads every pair like a structural engineer and prints, per pair, the evidence and the section to draw - the whole chain
of conventions/section-drawings.md 'STAR MARKERS' in one dry listing. It never writes.
  python star_plan.py FILE [--max-y Y]
Per pair: view (as placed / after the clockwise rule for E/W pairs), the BEAM STRIP crossed (93_KORA edges), B from the geometry, the b/h TAG (451TEXT_KORA_100 text on the strip), a LEDGE (a 15_DASHED
line between the two faces = face of the wall above: stem = up to it, the rest = ledge), TRANSFER (new element on the strip), the slab label D=a+b near the cut, panel span vs view (plan_cuts: CORES / LENGTHWISE)
-> recipe + arguments. Pairs that share (recipe, args) are one section (identical beams); numbers are sequential. Every guess is flagged. See conventions 5-5d."""
import argparse, math, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import ezdxf
from ezdxf import bbox
from star_orient import pairs, wanted, VIEW
from transfer_check import _segments, beam_strip, elements_on
from dxflib import decode
import plan_beams as pbm, ledge_beam as lb
from plan_sections import classify, parse_slab

TAGL = ('451TEXT_KORA_100', '45_TEXT_KORA')      # beam b/h tag layers (brenda_karka uses 45_TEXT_KORA)
TAG2 = re.compile(r'^\s*(\d+)\s*/\s*(\d+)')
TAG = re.compile(r'^\s*(\d+)\s*/\s*(\d+)\s*$')
SLAB = re.compile(r'^\s*D\s*=\s*(\d+)(?:\s*\+\s*(\d+))?\s*$')

def text_near(doc, strip, layer, rx, pad=80):
    x0, y0, x1, y1 = strip; out = []
    for t in doc.modelspace().query('TEXT'):
        if t.dxf.layer not in TAGL: continue
        m = rx.match(t.dxf.text)
        if not m: continue
        b = bbox.extents([t])
        if b.extmax.x > x0 - pad and b.extmin.x < x1 + pad and b.extmax.y > y0 - pad and b.extmin.y < y1 + pad: out.append((t, m))
    return out

def slab_labels(doc, mx, my, r=700):
    out = []
    for t in doc.modelspace().query('TEXT'):
        m = SLAB.match(t.dxf.text)
        if m and abs(t.dxf.insert.x - mx) < r and abs(t.dxf.insert.y - my) < r: out.append((abs(t.dxf.insert.x - mx) + abs(t.dxf.insert.y - my), t.dxf.insert.x, t.dxf.insert.y, int(m.group(1)), int(m.group(2) or 0)))
    return sorted(out)

def dashed_inside(doc, strip, horizontal):
    """coordinate (across the beam) of 15_DASHED lines lying between the two beam faces"""
    x0, y0, x1, y1 = strip; vals = set()
    for e in doc.modelspace():
        if e.dxf.layer != '15_DASHED' or e.dxftype() not in ('LINE', 'LWPOLYLINE'): continue
        pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)] if e.dxftype() == 'LINE' else [(p[0], p[1]) for p in e.get_points('xy')]
        for a, b in zip(pts, pts[1:]):
            if horizontal and abs(a[1] - b[1]) < .5 and y0 + 3 < a[1] < y1 - 3 and min(a[0], b[0]) < x1 and max(a[0], b[0]) > x0: vals.add(round(a[1], 1))
            if not horizontal and abs(a[0] - b[0]) < .5 and x0 + 3 < a[0] < x1 - 3 and min(a[1], b[1]) < y1 and max(a[1], b[1]) > y0: vals.add(round(a[0], 1))
    return sorted(vals)

def match_beam(beams, px, py, tol=45):
    """beam record whose axis passes within `tol` of the cut centre and whose length covers it (nearest wins)"""
    best = None
    for bm in beams:
        ux, uy = bm['u']; mx, my = bm['mid']; perp = abs((px - mx) * -uy + (py - my) * ux); along = abs((px - mx) * ux + (py - my) * uy) - bm['length'] / 2
        if perp <= max(tol, bm['b'] / 2 + 10) and along <= 20 and (best is None or perp < best[0]): best = (perp, bm)
    return best[1] if best else None

def in_kontur(doc, ps):
    """keep the pairs whose mid-point lies inside a closed region of claude_Kontur (plan_xlines_lf.kontur_loops: arcs flattened, pieces joined); the rest is reported, never touched"""
    from plan_xlines_lf import kontur_loops
    from ezdxf.math import is_point_in_polygon_2d, Vec2
    loops = kontur_loops(doc.modelspace()); keep = []
    for p, q in ps:
        mid = ((p.dxf.insert.x + q.dxf.insert.x) / 2, (p.dxf.insert.y + q.dxf.insert.y) / 2)
        if any(is_point_in_polygon_2d(Vec2(mid), [Vec2(pt[0], pt[1]) for pt in L]) >= 0 for L in loops): keep.append((p, q))
        else: print(f'outside claude_Kontur - ignored: pair at ({mid[0]:.0f}, {mid[1]:.0f})')
    print(f'claude_Kontur: {len(loops)} closed region(s); {len(keep)} of {len(ps)} pairs inside')
    return keep

def wall_cut(doc, p, q):
    """thickness of an existing WALL (8_KIR, two parallel faces 8..60 apart) the cut line crosses, else None. A wall that ends at the slab with ceilings on both sides = an untagged beam (user 2026-10-22)."""
    P = (p.dxf.insert.x, p.dxf.insert.y); Q = (q.dxf.insert.x, q.dxf.insert.y); L = math.dist(P, Q); ts = []
    for e in doc.modelspace().query('LINE LWPOLYLINE'):
        if e.dxf.layer != '8_KIR': continue
        pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)] if e.dxftype() == 'LINE' else [(x, y) for x, y in e.get_points('xy')] + ([(e.get_points('xy')[0][0], e.get_points('xy')[0][1])] if e.closed else [])
        for a_, b_ in zip(pts, pts[1:]):
            r = (b_[0] - a_[0], b_[1] - a_[1]); s_ = (Q[0] - P[0], Q[1] - P[1]); den = r[0] * s_[1] - r[1] * s_[0]
            if abs(den) < 1e-9: continue
            t = ((P[0] - a_[0]) * s_[1] - (P[1] - a_[1]) * s_[0]) / den; u = ((P[0] - a_[0]) * r[1] - (P[1] - a_[1]) * r[0]) / den
            if 0 <= t <= 1 and 0 <= u <= 1: ts.append(u * L)
    ts = sorted(ts)
    for a_, b_ in zip(ts, ts[1:]):
        if 8 <= b_ - a_ <= 60: return round(b_ - a_)
    return None

ROLLER_LAYER = 'automatic_Roller_shutter'


def roller_shutter(doc, mx, my, r=450):
    """user 2026-10-22: a TEXT on layer automatic_Roller_shutter ('10/35' = b/h) near the cut = add a roller-shutter beam of that size -> (b, h) or None; nearest text within r."""
    best = None
    for t in doc.modelspace().query('TEXT'):
        if t.dxf.layer != ROLLER_LAYER: continue
        d_ = math.dist((t.dxf.insert.x, t.dxf.insert.y), (mx, my)); nums = re.findall(r'\d+(?:\.\d+)?', t.dxf.text)
        if d_ <= r and len(nums) >= 2 and (best is None or d_ < best[0]): best = (d_, (float(nums[0]), float(nums[1])))
    return best[1] if best else None


def edge_thickness(doc, mx, my, r=450):
    """slab thickness at a free edge: nearest 'D=nn' / 'nn=D' text (any layer, Hebrew-style texts are stored reversed) within r of the cut; (value, remark). 20 = template default, UNVERIFIED."""
    import dxflib as DL
    best = None
    for t in doc.modelspace().query('TEXT MTEXT'):
        ip = t.dxf.insert; d0 = math.dist((ip.x, ip.y), (mx, my))
        if d0 > r: continue
        tx = DL.text_of(doc, t)
        m = re.search(r'D\s*=\s*(\d{2,3})', tx[1]) if tx else None; v = int(m.group(1)) if m else None
        if v is None and tx:                      # SIVAN text is stored reversed: raw '08=D' reads D=80 (digits reversed too)
            m = re.search(r'(\d{2,3})\s*=\s*D', tx[1]); v = int(m.group(1)[::-1]) if m else None
        if v and (best is None or d0 < best[0]): best = (d0, v)
    if best: return best[1], f'D={best[1]} from the plan label {best[0]:.0f} away'
    return None, 'NO D= label within %d of the cut -> solid slab with the parametric thickness H (user rule 2026-10-18: never guess a thickness; a plan-wide note farther away is only mentioned)' % r

def edge_slab_side(doc, p, q, view):
    """which side of the VIEW the slab is on at a free edge: the cut-line end that lies inside claude_Kontur (else the end nearer the plan centre) is the slab; right-of-view vector = (vy, -vx)."""
    from plan_xlines_lf import kontur_loops
    from ezdxf.math import is_point_in_polygon_2d, Vec2
    loops = kontur_loops(doc.modelspace()); ends = [(h.dxf.insert.x, h.dxf.insert.y) for h in (p, q)]
    ins = [any(is_point_in_polygon_2d(Vec2(e), [Vec2(pt[0], pt[1]) for pt in L]) >= 0 for L in loops) for e in ends]
    vx, vy = {'E': (1, 0), 'W': (-1, 0), 'N': (0, 1), 'S': (0, -1)}[view]; rx, ry = vy, -vx
    if ins[0] != ins[1]: e = ends[0] if ins[0] else ends[1]; why = 'the end inside claude_Kontur'
    else: e = ends[0]; why = 'both ends alike: UNVERIFIED, first end taken'
    mx, my = (ends[0][0] + ends[1][0]) / 2, (ends[0][1] + ends[1][1]) / 2
    side = 'right' if ((e[0] - mx) * rx + (e[1] - my) * ry) > 0 else 'left'
    return side, f'slab on the {side} of the view ({why})'

def cut_faces(doc, pq):
    """positions along the cut line of the 93_KORA beam faces it crosses (only when exactly two)"""
    P = (pq[0].dxf.insert.x, pq[0].dxf.insert.y); Q = (pq[1].dxf.insert.x, pq[1].dxf.insert.y); L = math.dist(P, Q); out = []
    for e in doc.modelspace().query('LINE LWPOLYLINE'):
        if e.dxf.layer != '93_KORA': continue
        pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)] if e.dxftype() == 'LINE' else [(x, y) for x, y in e.get_points('xy')]
        for a_, b_ in zip(pts, pts[1:]):
            r = (b_[0] - a_[0], b_[1] - a_[1]); s_ = (Q[0] - P[0], Q[1] - P[1]); den = r[0] * s_[1] - r[1] * s_[0]
            if abs(den) < 1e-9: continue
            t = ((P[0] - a_[0]) * s_[1] - (P[1] - a_[1]) * s_[0]) / den; u = ((P[0] - a_[0]) * r[1] - (P[1] - a_[1]) * r[0]) / den
            if 0 <= t <= 1 and 0 <= u <= 1: out.append(u * L)
    return sorted(out)


LEFT_OF = {'N': (-1, 0), 'S': (1, 0), 'E': (0, 1), 'W': (0, -1)}      # unit vector pointing to the LEFT-hand side of the viewer for each view direction
LVL = re.compile(r'^\s*([+-]?\d+\.\d\d)\s*(?:=|$)')      # '-1.20=+50.30' (old) or a bare '+46.20' (brenda_karka S_M, 2026-10-22)
OKT = re.compile(r'^\s*o\.k\.?\s*=?\s*([+-]?\d+\.\d\d)', re.I)      # 'o.k. +45.25' or 'o.k=+45.25'

def slab_markers(doc):
    """S_M level markers of the plan: (x, y, D, top level) - the user's slab labels `D=nn` + `-1.20=+50.30` (attribs of the block S_M); D without '+topping' = SOLID slab"""
    out = []
    for e in doc.modelspace().query('INSERT'):
        if e.dxf.name != 'S_M' or not e.attribs: continue
        d_ = lv = None
        for a in e.attribs:
            m_ = SLAB.match(a.dxf.text.strip())
            if m_: d_ = int(m_.group(1)) + int(m_.group(2) or 0); continue
            m_ = LVL.match(a.dxf.text)
            if m_: lv = float(m_.group(1))
        if d_ is not None: out.append((e.attribs[0].dxf.insert.x, e.attribs[0].dxf.insert.y, d_, lv))
    return out

def beam_top_level(doc, mx, my, b, tagpos=None):
    """top level (m) of the beam: the o.k. text next to its b/h tag (45_TEXT_KORA) - the tag given by the beam inventory (tagpos) or else the nearest tag of the same width; o.k text with the tag's rotation preferred (<= 300 away)"""
    tx = [(t, m_) for t in doc.modelspace().query('TEXT') if t.dxf.layer in TAGL for m_ in [TAG2.match(t.dxf.text)] if m_ and abs(int(m_.group(1)) - b) <= 2]
    ref = tagpos or (mx, my)
    tags = sorted((math.dist((t.dxf.insert.x, t.dxf.insert.y), ref), t) for t, _ in tx if math.dist((t.dxf.insert.x, t.dxf.insert.y), ref) < (60 if tagpos else 700))
    if not tags: return None
    t0 = tags[0][1]; tp = t0.dxf.insert; rot = round(t0.dxf.get('rotation', 0)) % 180; best = None
    for t in doc.modelspace().query('TEXT'):
        m_ = OKT.match(t.dxf.text)
        if not m_: continue
        dd = math.dist((t.dxf.insert.x, t.dxf.insert.y), (tp.x, tp.y))
        if dd > 300: continue
        key = (0 if round(t.dxf.get('rotation', 0)) % 180 == rot else 1, dd)
        if best is None or key < best[0]: best = (key, float(m_.group(1)))
    return best[1] if best else None

SEP_LAYERS = ('93_KORA', '9_KONTUR', '9_1_KONTUR', '82_KIR_OLE')      # beam faces / slab edges / walls: a straight line from the cut to a slab marker that crosses one of them leaves the panel (user 2026-10-22: 'some thicknesses are incorrect')

def separators(doc):
    segs = []
    for e in doc.modelspace().query('LINE LWPOLYLINE'):
        if e.dxf.layer not in SEP_LAYERS: continue
        if e.dxftype() == 'LINE': pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        else:
            pts = [(q[0], q[1]) for q in e.get_points()]
            if e.closed and pts: pts.append(pts[0])
        segs += [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    return segs

def _crosses(p1, p2, q1, q2):
    d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return d(p1, p2, q1) * d(p1, p2, q2) < 0 and d(q1, q2, p1) * d(q1, q2, p2) < 0

_SEPS = {}

def side_slabs(doc, mx, my, view, b=None, markers=None, tagpos=None):
    """(Dl, Dr, drop_l, drop_r, note): slab thickness and level drop (cm, beam top - slab top) on the LEFT / RIGHT of the viewer.
    Per side: the S_M marker (25-700 along the cut, <= 700 beamwise) whose straight line from the beam face crosses the fewest beam faces / slab edges / walls (SEP_LAYERS, 1500 penalty each), then nearest by hypot(along, 2*beamwise) - the marker of the panel that touches the beam, not just the closest one (8-8: D=25 behind the beam, not the D=65 across a face). A marker beyond a separator or > 350 beamwise = UNVERIFIED note. Missing side = copy of the other (UNVERIFIED), none = 25 / 0"""
    mk = markers if markers is not None else slab_markers(doc); lx, ly = LEFT_OF[view]; found = {}; wide = {}
    seps = _SEPS.setdefault(id(doc), separators(doc)); half = (b or 30) / 2.0 + 10.0
    for x, y, D, lv in mk:
        al = (x - mx) * lx + (y - my) * ly; pp = abs((x - mx) * ly - (y - my) * lx)
        if 25 < abs(al) < 700 and pp < 700:
            sd = 'L' if al > 0 else 'R'; s0 = (mx + math.copysign(half, al) * lx, my + math.copysign(half, al) * ly)
            nx = sum(1 for q1, q2 in seps if _crosses(s0, (x, y), q1, q2)); sc = nx * 1500 + math.hypot(al, 2.0 * pp)
            if sd not in found or sc < found[sd][0]: found[sd] = (sc, D, lv, nx, pp)
    for x, y, D, lv in (mk if len(found) < 2 else ()):      # a side still empty (user 2026-10-22, red clouds on the S_M west of 2-2 and on 2-2's left slab): widen the search to 900 along the cut / beamwise, never beyond
        al = (x - mx) * lx + (y - my) * ly; pp = abs((x - mx) * ly - (y - my) * lx); sd = 'L' if al > 0 else 'R'
        if sd in found or not (25 < abs(al) < 900 and pp < 900): continue
        s0 = (mx + math.copysign(half, al) * lx, my + math.copysign(half, al) * ly); nx = sum(1 for q1, q2 in seps if _crosses(s0, (x, y), q1, q2)); sc = nx * 1500 + math.hypot(al, 2.0 * pp)
        if sd not in wide or sc < wide[sd][0]: wide[sd] = (sc, D, lv, nx, 999)
    for sd, v in wide.items(): found[sd] = v
    top = beam_top_level(doc, mx, my, b, tagpos) if b else None; note = []
    sides = {}
    for sd in 'LR':
        if sd in found:
            sides[sd] = (found[sd][1], found[sd][2])
            if found[sd][3] or found[sd][4] > 350: note.append(f"{'left' if sd == 'L' else 'right'} slab D={found[sd][1]} taken from a marker {'beyond a beam face / wall' if found[sd][3] else str(round(found[sd][4])) + ' away along the beam'} (UNVERIFIED)")
    if not sides: return 25, 25, 0, 0, 'no slab marker near the cut: D=25 template both sides, flush (UNVERIFIED)'
    for sd in 'LR':
        if sd not in sides: sides[sd] = sides['L' if sd == 'R' else 'R']; note.append(f"{'left' if sd == 'L' else 'right'} slab not found: copied from the other side (UNVERIFIED)")
    if top is None and b:                    # beam level not on the plan near its tag: the beam top is the HIGHER slab top of the two sides (UNVERIFIED)
        lvs = [lv for _, lv in sides.values() if lv is not None]
        if lvs: top = max(lvs); note.append('beam top level = the higher slab level (tag has no o.k. text) (UNVERIFIED)')
    drops = {}
    for sd in 'LR':
        D, lv = sides[sd]
        drops[sd] = round((top - lv) * 100) if (top is not None and lv is not None) else 0
        if drops[sd] < 0: drops[sd] = 0; note.append('slab above the beam top: drawn flush (UNVERIFIED)')
    if top is None and not b: note.append('untagged beam: slabs drawn flush with the beam top, levels not evaluated (UNVERIFIED)')
    return sides['L'][0], sides['R'][0], drops['L'], drops['R'], '; '.join(note)

def slab_args(Dl, Dr, dl, dr):
    return f'--D {Dl}' if (Dl == Dr and dl == dr == 0) else f'--D {max(Dl, Dr)} --D-left {Dl} --D-right {Dr} --drop-left {dl} --drop-right {dr}'

def mark_of(p, q):
    """'S' (reinforcement as per plan), 'SS' (engineer chooses diameter), 'ST' (= S with TRANSFER-beam stirrups, user 2026-10-16) or '*' (old notation = S) from the pair's attribute"""
    t = ' '.join(x.dxf.text.strip().upper() for h in (p, q) for x in h.attribs)
    return 'SS' if 'SS' in t else ('ST' if 'ST' in t else 'S')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--max-y', type=float, default=1e9); ap.add_argument('--first', type=int, default=1, help='number of the first section'); ap.add_argument('--draw', action='store_true', help='execute: next free cells of the template row (new row below when full), recipes, marks renumbered'); ap.add_argument('--min-y', type=float, default=None, help='only the plan copy whose pairs are at or above this y'); ap.add_argument('--cells-at', type=float, nargs=2, default=None, metavar=('X', 'Y'), help='draw into NEW rows of 4 cells starting at this top-left row origin (x, y of the row bottom-left), rows stacked downward - the sections go beside THIS plan copy'); ap.add_argument('--kontur', action='store_true', help='work ONLY inside the closed regions of layer claude_Kontur (the user work boundary): pairs whose mid-point is outside every region are ignored and reported'); ap.add_argument('--make-rows', type=int, metavar='N', help='only create N empty template rows of 10 cells at --cells-at X Y (bottom-left of the first row) and stop'); ap.add_argument('--stirrups', choices=['standard', 'transfer'], default=None, help='by MARK (user 2026-10-16): S / SS = standard beams, ST = transfer beam; the transfer-beam detection is only reported; force one table for ALL pairs with this; override the transfer-beam detection (user 2026-10-15: plan C beams are NOT transfer beams -> standard tables)'); a = ap.parse_args()
    if a.make_rows:
        from dxflib import backup
        d0 = ezdxf.readfile(a.file); x0, y0 = a.cells_at; have = rows_free(d0, x0, y0, 0); backup(a.file, 'template-rows'); rows_free(d0, x0, y0, PER_ROW * a.make_rows); d0.saveas(a.file); print('template rows created / present:', a.make_rows); return
    doc = ezdxf.readfile(a.file); ps = pairs(doc, a.max_y, a.min_y); segs = _segments(doc)
    MK = slab_markers(doc)
    ps = [pq for pq in ps if any(x.dxf.text.strip().upper() in ('S', 'SS', 'ST', '*') for h in pq for x in h.attribs)]      # only UNNUMBERED marks (S / SS / old *): numbered pairs are finished sections
    if a.kontur: ps = in_kontur(doc, ps)
    cuts = subprocess.run([sys.executable, '-I', os.path.join(HERE, '..', 'scripts', 'plan_cuts.py'), a.file], capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    if not ps: print('no unnumbered S / SS / ST pairs to do (inside claude_Kontur)'); return
    xs = [h.dxf.insert.x for pq in ps for h in pq]; ys = [h.dxf.insert.y for pq in ps for h in pq]
    beams, _ = pbm.inventory(doc, [min(xs) - 1500, min(ys) - 2500, max(xs) + 1500, max(ys) + 2500], lb.apply_profile('israeli-structural') or lb.PROF) if ps else ([], None)
    mids = [((p.dxf.insert.x + q.dxf.insert.x) / 2, (p.dxf.insert.y + q.dxf.insert.y) / 2) for p, q in ps]
    cx, cy = sum(m[0] for m in mids) / len(mids), sum(m[1] for m in mids) / len(mids); plan = []
    for (p, q), (mx, my) in zip(ps, mids):
        rot = (round(p.dxf.rotation / 90.0) * 90) % 360; view = VIEW[rot]; horiz = view in 'EW'      # E/W view = vertical cut line = horizontal beam; the view is AS PLACED (run star_orient first)
        strip = beam_strip(doc, mx, my, horiz, segs); ev = {'mid': (round(mx), round(my)), 'view': view, 'mark': mark_of(p, q)}
        bm = match_beam(beams, mx, my)
        if bm:                       # a b/h label of the floor whose axis passes through the cut: the user's beam inventory (plan_beams), slabs left / right, panel relation
            ev.update(bm=f"{bm['label']} at {bm['at']}", relation=bm['relation'], L=bm['L'], R=bm['R'])
            vx, vy = {'E': (1, 0), 'W': (-1, 0), 'N': (0, 1), 'S': (0, -1)}[view]; rx, ry = vy, -vx; nx, ny = bm['n']; left_is_right = (nx * rx + ny * ry) > 0
            Lp, Rp = parse_slab(bm['L']), parse_slab(bm['R']); sr, sl = (Lp, Rp) if left_is_right else (Rp, Lp)      # slab on the RIGHT / LEFT of the user's view
            ev['slab_right'], ev['slab_left'] = sr, sl; tr_ = elements_on(doc, *strip) if strip else []; st = 'transfer' if tr_ else 'standard'; ev['transfer'] = bool(tr_)
            ty, note = classify(bm); kind = ty[0]; T = ty[6]
            sides = 'both' if (sr and sl) else ('right' if sr else ('left' if sl else 'none'))
            if sides == 'none':      # user 2026-10-21 (brenda_karka): no hollow label beside the beam -> the neighbour is a SOLID slab (D=nn label, level = beam top): the general 6-6 with the tag's B/H, D from the nearest solid label (25 when none = template, UNVERIFIED)
                Dl_, Dr_, dl_, dr_, sn_ = side_slabs(doc, mx, my, view, int(bm['b']), MK, tuple(bm['at']) if isinstance(bm.get('at'), (tuple, list)) else None)
                ev.update(slabs=dict(L=(Dl_, dl_), R=(Dr_, dr_)), recipe='general_beam', args=f"--B {bm['b']} --H {bm['h']} {slab_args(Dl_, Dr_, dl_, dr_)} --stirrups {st}", note=f"beam {bm['b']}/{bm['h']}: slab left D={Dl_} (drop {dl_}), right D={Dr_} (drop {dr_}) as seen in the view" + (f'; {sn_}' if sn_ else '')); plan.append(ev); continue
            args = f"--beam {bm['b']} {bm['h']} --kind {kind} --sides {sides} --topping {T:g} --stirrups {st}"
            if kind == 'ledge': args += f" --slab {max((x[0] for x in (sr, sl) if x)):g}" + (f" --slab-right {sr[0]:g} --slab-left {sl[0]:g}" if (sr and sl and sr[0] != sl[0]) else '')
            else: args += f" --slab {(max(x[0] for x in (sr, sl) if x) + T) if sides != 'none' else 0:g}" + (f" --slab-left {sl[0] + sl[1]:g}" if (sr and sl and sr[0] != sl[0]) else '')
            ev.update(recipe='ledge_beam', args=args, note=note or ('ledge beam: panels bear on it' if kind == 'ledge' else 'cast L edge beam (panels run past, cores)')); plan.append(ev); continue
        if strip is None and len(cut_faces(doc, (p, q))) != 2:            # slanted beam (edges not axis-parallel) or no beam: look for a b/h label (also 'b/h o.k...') around the cut centre
            tg = [(math.dist((t.dxf.insert.x, t.dxf.insert.y), (mx, my)), m) for t in doc.modelspace().query('TEXT') if t.dxf.layer in TAGL for m in [TAG2.match(t.dxf.text)] if m and abs(t.dxf.insert.x - mx) < 200 and abs(t.dxf.insert.y - my) < 260]
            if tg:
                b_, h_ = sorted(tg, key=lambda x: x[0])[0][1].groups(); sl = slab_labels(doc, mx, my, 900); a_, t_ = (sl[0][3], sl[0][4]) if sl else (25, 7); kind = 'ledge' if int(b_) >= 50 else 'cast'
                ev.update(tag=f'{b_}/{h_}', recipe='ledge_beam', args=f"--beam {b_} {h_} --kind {kind} --sides both --topping {t_} --stirrups standard --slab {a_ if kind == 'ledge' else a_ + t_}", note='SLANTED beam (edges not axis-parallel): size from its label, slabs assumed on BOTH sides from the nearest D= label, stirrup table standard (not evaluated) - UNVERIFIED'); plan.append(ev); continue
        if strip is None:            # user 2026-10-21: the beam inventory splits a beam at walls/piers; the cut itself still crosses its two 93_KORA faces -> B from the crossings, b/h from the nearest tag of the SAME width
            cr = cut_faces(doc, (p, q))
            if len(cr) == 2:
                Bc = round(abs(cr[1] - cr[0])); tg = sorted((math.dist((t.dxf.insert.x, t.dxf.insert.y), (mx, my)), m) for t in doc.modelspace().query('TEXT') if t.dxf.layer in TAGL for m in [TAG2.match(t.dxf.text)] if m and abs(int(m.group(1)) - Bc) <= 2 and math.dist((t.dxf.insert.x, t.dxf.insert.y), (mx, my)) < 900)
                if tg:
                    b_, h_ = tg[0][1].groups(); Dl_, Dr_, dl_, dr_, sn_ = side_slabs(doc, mx, my, view, int(b_), MK)
                    ev.update(B=Bc, tag=f'{b_}/{h_}', slabs=dict(L=(Dl_, dl_), R=(Dr_, dr_)), recipe='general_beam', args=f"--B {b_} --H {h_} {slab_args(Dl_, Dr_, dl_, dr_)} --stirrups standard", note=f'faces from the cut crossings, tag {b_}/{h_}: slab left D={Dl_} (drop {dl_}), right D={Dr_} (drop {dr_})' + (f'; {sn_}' if sn_ else '')); plan.append(ev); continue
        if strip is None:
            wB = wall_cut(doc, p, q)
            if wB:        # user 2026-10-22: 'a wall that terminates, ceilings on both sides' = the general untagged-beam section (5c): B = wall thickness, height symbol h, slabs both sides
                Dl_, Dr_, dl_, dr_, sn_ = side_slabs(doc, mx, my, view, None, MK)
                dl_ = False if False else None
                pl = 'no slab marker' in sn_
                ev.update(recipe='general_beam', args=f"--B {wB} --H 40 --h-label h {slab_args(Dl_, Dr_, 0, 0)}" + (' --d-label H' if pl else '') + f" --stirrups standard", note=f'existing wall 8_KIR B={wB} crossed by the cut, slabs both sides: general beam, height h; ' + ('slab thickness unknown -> symbol H, geometry 25 (user rule)' if pl else sn_)); plan.append(ev); continue
            edge = [e for e in doc.modelspace().query('LWPOLYLINE LINE') if e.dxf.layer == '9_KONTUR' and bbox.extents([e]).has_data and bbox.extents([e]).extmin.x - 60 < mx < bbox.extents([e]).extmax.x + 60 and bbox.extents([e]).extmin.y - 60 < my < bbox.extents([e]).extmax.y + 60]
            if edge:
                D_, dn = edge_thickness(doc, mx, my); sd, sn2 = edge_slab_side(doc, p, q, view)
                if not D_:                                   # the plan's own slab markers (S_M, 'D=23' inside the marker block) are a D label too
                    Dl2, Dr2, _, _, sn3 = side_slabs(doc, mx, my, view, None, MK)
                    if 'no slab marker' not in sn3: D_ = max(Dl2, Dr2); dn = f'D={D_} from the nearest S_M slab markers'
                dargs = f'--slab {D_:g}' if D_ else '--slab 25 --d-label H'
                shu = roller_shutter(doc, mx, my)
                if shu: dargs += f' --shutter {shu[0]:g} {shu[1]:g}'; dn += f'; ROLLER SHUTTER {shu[0]:g}/{shu[1]:g} from the plan text (b/h mapping UNVERIFIED)'
                ev.update(recipe='slab_edge', args=f'{dargs} --cut {mx:.0f} {my:.0f}', note=f'no beam, but the cut crosses a 9_KONTUR slab edge: free slab edge (user detail), drawn slab LEFT / end face right as in his 4-4 even though {sn2}; {dn}'); plan.append(ev); continue
            ev.update(kind='NOTHING', note='no beam edges and no slab edge at the cut: skip + report'); plan.append(ev); continue
        B = round(strip[3] - strip[1] if horiz else strip[2] - strip[0]); ev.update(strip=[round(v) for v in strip], B=B)
        tags = text_near(doc, strip, '451TEXT_KORA_100', TAG); ev['tag'] = f'{tags[0][1].group(1)}/{tags[0][1].group(2)}' if tags else None
        tr = elements_on(doc, *strip); ev['transfer'] = bool(tr)
        da = dashed_inside(doc, strip, horiz); lo = strip[1] if horiz else strip[0]; hi = strip[3] if horiz else strip[2]
        ev['ledge'] = None; snap = lambda v: round(v / 5) * 5 if abs(v - round(v / 5) * 5) <= 1.6 else round(v)
        if da:                       # dashed line(s) between the faces = hidden edge(s) above: a line ~15 from a face = a LEDGE on that side; a single line splits the beam into stem (wider part, under the wall) + ledge (narrower)
            led = []
            for d_ in da:
                t0, t1 = d_ - lo, hi - d_
                if min(t0, t1) <= 20: led.append(('low' if t0 < t1 else 'high', snap(min(t0, t1))))
            if led: ev['ledge'] = dict(sides=sorted({sd for sd, _ in led}), width=led[0][1], stem=snap(B - sum(w for _, w in led)))
        sl = slab_labels(doc, mx, my); ev['D'] = f'{sl[0][3]}+{sl[0][4]}' if sl else None
        line = next((l for l in cuts.splitlines() if l.startswith('section') and f'mid ({round(mx)},{round(my)})' in l), '')
        ev['span'] = 'CORES' if 'CORES' in line else ('LENGTHWISE' if 'LENGTHWISE' in line else '?')
        st = 'transfer' if tr else 'standard'
        if ev['tag'] and ev['span'] == 'CORES':
            b_, h_ = ev['tag'].split('/'); ev.update(recipe='ledge_beam', args=f'--beam {b_} {h_} --slab 25 --topping 5 --kind cast --sides right --stirrups {st}', note='cast L edge beam (slab on the right of the view), D from the plan label')
        elif ev['tag']:
            b_, h_ = ev['tag'].split('/'); ev.update(recipe='ledge_beam', args=f'--beam {b_} {h_} --slab 20 --topping 5 --kind ledge --sides {"both" if (ev["ledge"] and len(ev["ledge"]["sides"]) == 2) else "right"} --stirrups {st}', note='ledge beam (panels bear on it)')
        elif ev['ledge']:
            ev.update(recipe='ledge_beam', args=f'--beam {B} 40 --slab 20 --topping 5 --kind ledge --sides right --stirrups {st} --h-label h', note=f"UNTAGGED beam with a tooth: stem {ev['ledge']['stem']} + ledge {ev['ledge']['width']} (dashed line = wall above); height = symbol h (drawn 40, UNVERIFIED); ledge side must be checked against the view")
        else:
            Dl_, Dr_, dl_, dr_, sn_ = side_slabs(doc, mx, my, view, None, MK)
            ev.update(slabs=dict(L=(Dl_, 0), R=(Dr_, 0)), recipe='general_beam', args=f'--B {B} {slab_args(Dl_, Dr_, 0, 0)} --H 40 --h-label h --stirrups {st}', note=f'UNTAGGED beam without a ledge: the general 6-6, height symbol h (UNVERIFIED H=40); slab left D={Dl_}, right D={Dr_} from the plan markers, drawn flush (levels differ? not evaluated)' + (f'; {sn_}' if sn_ else ''))
        plan.append(ev)
    for ev in plan:                                       # S / SS marks (user 2026-10-16): SS = engineer picks the bars -> X$XX notes
        if 'args' in ev: ev['args'] += ' --detail ' + ('ss' if ev.get('mark') == 'SS' else 'plan')
    for ev in plan:                                          # stirrup table by MARK: ST = transfer beam, S / SS = standard (a.stirrups forces one table)
        if 'args' in ev:
            tbl = a.stirrups or ('transfer' if ev.get('mark') == 'ST' else 'standard'); ev['args'] = re.sub(r'--stirrups \w+', f'--stirrups {tbl}', ev['args']); ev['transfer'] = tbl == 'transfer'
    plan.sort(key=lambda e: math.atan2(e['mid'][0] - cx, e['mid'][1] - cy) % (2 * math.pi))   # user 2026-10-22: numbers run CLOCKWISE round the plan (start = north, UNVERIFIED)
    groups = {}
    for ev in plan:
        if 'recipe' in ev: groups.setdefault((ev['recipe'], ev['args']), []).append(ev)
    print(f'{len(plan)} pairs, {len(groups)} section type(s); centre of the marks ({cx:.0f}, {cy:.0f})')
    for ev in plan: print('pair', ev['mid'], 'view', ev['view'], '|', {k: v for k, v in ev.items() if k not in ('mid', 'view', 'recipe', 'args', 'note')})
    for n, ((rec, args), evs) in enumerate(groups.items(), a.first):
        print(f"\nsection {n}-{n}: {rec}.py <file> {n}-{n} --box X Y 400 450 {args}   [{len(evs)} pair(s): {', '.join(str(e['mid']) for e in evs)}]" + (f"  note: {evs[0]['note']}" if evs[0].get('note') else '') + (f"  identical for {len(evs)} beams" if len(evs) > 1 else ''))
    for ev in plan:
        if 'recipe' not in ev: print('\nNOT DRAWN: pair', ev['mid'], '-', ev['note'])

    if a.draw: execute(a, doc, groups, plan)

def template_cells(doc):
    """[(x0, y0, titled)] of the user's template cells (400 x 450 on 72_MISGERET_WIN, in rows of 1600; rows below y=40000 only), top row first, left to right"""
    out = []
    titles = [t for t in doc.modelspace().query('TEXT') if t.dxf.text.startswith('%%U')]
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != '72_MISGERET_WIN' or not e.closed: continue
        b = bbox.extents([e])
        if abs(b.size.x - 1600) < 2 and abs(b.size.y - 450) < 2 and b.extmin.y < 40000:
            for k in range(4):
                x0 = b.extmin.x + 400 * k; out.append((x0, b.extmin.y, any(x0 < t.dxf.insert.x < x0 + 400 and b.extmin.y < t.dxf.insert.y < b.extmax.y for t in titles)))
    return sorted(out, key=lambda c: (-c[1], c[0]))

PER_ROW = 10                                        # cells per template row (user 2026-10-16)

def add_row(doc, x0, y, per_row=PER_ROW, h=450):
    """one template row: a (400*per_row) x 450 white frame on 72_MISGERET_WIN with dividers every 400 (same format as the user's 1600 x 450 row)"""
    msp = doc.modelspace(); w = 400 * per_row
    msp.add_lwpolyline([(x0, y), (x0 + w, y), (x0 + w, y + h), (x0, y + h)], close=True, dxfattribs=dict(layer='72_MISGERET_WIN'))
    for k in range(1, per_row): msp.add_line((x0 + 400 * k, y), (x0 + 400 * k, y + h), dxfattribs=dict(layer='72_MISGERET_WIN'))

def rows_free(doc, x0, y_top, need, per_row=PER_ROW):
    """free cells (x, y_box, False) of the per_row-wide template rows (400*per_row wide, ANY height - the user's own rows are 781 / 719 high) whose left edge is x0 and whose bottom is at or below y_top,
    top row first, left to right. The 400x450 box of a cell is the TOP 450 of its frame (y_box = top - 450; the extra height below takes tall beams). New rows are added below the last one,
    touching it, with the height of the last row, until `need` cells are free."""
    from ezdxf import bbox
    def rows():
        out = []
        for e in doc.modelspace().query('LWPOLYLINE'):
            if e.dxf.layer != '72_MISGERET_WIN' or not e.closed: continue
            b = bbox.extents([e])
            if abs(b.size.x - 400 * per_row) < 2 and b.size.y >= 449 and abs(b.extmin.x - x0) < 2 and b.extmin.y <= y_top + 1: out.append((round(b.extmin.y, 1), round(b.extmax.y, 1)))
        return sorted(set(out), reverse=True)
    titles = [t for t in doc.modelspace().query('TEXT') if t.dxf.text.startswith('%%U')]
    def free_cells():
        return [(x0 + 400 * k, top - 450, False) for (bot, top) in rows() for k in range(per_row)
                if not any(x0 + 400 * k < t.dxf.insert.x < x0 + 400 * k + 400 and bot < t.dxf.insert.y < top for t in titles)]
    free = free_cells()
    while len(free) < need:
        rs = rows()
        if rs: h = rs[-1][1] - rs[-1][0]; top = rs[-1][0] - 1.0; add_row(doc, x0, top - h, per_row, h)
        else: add_row(doc, x0, y_top, per_row)
        free = free_cells()
    return free

MARGIN = 25.0

def section_extent(a, rec, args, name, identical=0):
    """draw ONE section into a scratch copy (box 0 0 400 450) and measure everything the recipe added (title, bars, notes, dims, stirrup details): returns (xmin, ymin, xmax, ymax) relative to the cell box origin"""
    import tempfile
    from ezdxf import bbox
    tmp = os.path.join(tempfile.gettempdir(), 'sp_extent.dxf'); before = {e.dxf.handle for e in ezdxf.readfile(a.file).modelspace()}
    cmd = [sys.executable, '-I', os.path.join(HERE, rec + '.py'), a.file, name, '--box', '0', '0', '400', '450'] + args.split() + ['-o', tmp]
    if rec == 'ledge_beam' and identical > 1: cmd += ['--identical', str(identical)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode or not os.path.exists(tmp): return None
    new = [e for e in ezdxf.readfile(tmp).modelspace() if e.dxf.handle not in before]
    xs0, ys0, xs1, ys1 = 1e9, 1e9, -1e9, -1e9; ty = 403.0
    for e in new:
        if e.dxftype() == 'TEXT' and e.dxf.text.startswith('%%U'): ty = e.dxf.insert.y
        try: b = bbox.extents([e])
        except Exception: continue
        if b.has_data and b.size.x < 2000: xs0, ys0, xs1, ys1 = min(xs0, b.extmin.x), min(ys0, b.extmin.y), max(xs1, b.extmax.x), max(ys1, b.extmax.y)
    return (xs0, ys0, xs1, ys1, ty)

def need_height(ext):
    """frame height that holds the whole section (user 2026-10-16: every section INCLUDING its reinforcement must fit entirely inside its cell). Titles of a row share ONE line 47 below the frame top (his arrangement:
    a tall beam sits lower, its bottom is not aligned with its neighbours), so the section hangs from the title: height = title y - lowest point + 47 + margin; never below 450."""
    return max(450.0, ext[4] - ext[1] + 47.0 + MARGIN) if ext else 450.0

def layout_cells(doc, x0, y_top, needs, tys, per_row=PER_ROW):
    """one (x, y_box) per section, in reading order, into the 10-wide rows at x0 (free = title-less cells, top row first): a row that is too low for its sections is extended downward (only the LOWEST row can be),
    a new row (height = what its sections need, touching the row above) starts after every 10 sections. Returns (cells, report)"""
    from ezdxf import bbox
    msp = doc.modelspace(); rep = []
    def frames():
        out = []
        for e in msp.query('LWPOLYLINE'):
            if e.dxf.layer != '72_MISGERET_WIN' or not e.closed: continue
            b = bbox.extents([e])
            if abs(b.size.x - 400 * per_row) < 2 and b.size.y >= 449 and abs(b.extmin.x - x0) < 2 and b.extmin.y <= y_top + 1: out.append((round(b.extmin.y, 1), round(b.extmax.y, 1), e))
        return sorted(out, key=lambda r: -r[0])
    titles = [t for t in msp.query('TEXT') if t.dxf.text.startswith('%%U')]
    fr = frames(); cells = []; idx = 0; row_need = []
    for (bot, top, e) in fr:
        fk = [k for k in range(per_row) if not any(x0 + 400 * k < t.dxf.insert.x < x0 + 400 * k + 400 and bot < t.dxf.insert.y < top for t in titles)]
        take = fk[:max(0, len(needs) - idx)]
        if not take: continue
        req = max(needs[idx:idx + len(take)]); cells += [(x0 + 400 * k, top - 47.0 - tys[idx + j]) for j, k in enumerate(take)]; idx += len(take)
        if req > top - bot + 0.5:
            if e is fr[-1][2]:                                   # the lowest row grows downward
                nb = top - req; pts = [(p[0], nb if abs(p[1] - bot) < 1 else p[1]) for p in e.get_points('xy')]; e.set_points(pts)
                for l in msp.query('LINE'):
                    if l.dxf.layer == '72_MISGERET_WIN' and abs(l.dxf.start.x - l.dxf.end.x) < 0.01 and x0 < l.dxf.start.x < x0 + 400 * per_row and abs(min(l.dxf.start.y, l.dxf.end.y) - bot) < 1 and abs(max(l.dxf.start.y, l.dxf.end.y) - top) < 1: l.dxf.start = (l.dxf.start.x, nb, 0); l.dxf.end = (l.dxf.end.x, top, 0)
                rep.append(f'row y {bot:g}..{top:g} extended to {nb:g} (needs {req:g})'); bot = nb
            else: rep.append(f'WARNING row y {bot:g}..{top:g} is too low for its sections (needs {req:g}) and has rows below it')
    while idx < len(needs):
        batch = needs[idx:idx + per_row]; h = max(batch); fr = frames()
        if fr: top = fr[-1][0] - 1.0
        else: top = y_top + h
        add_row(doc, x0, top - h, per_row, h); rep.append(f'new row y {top - h:g}..{top:g} (height {h:g}) for sections {idx + 1}..{idx + len(batch)}')
        cells += [(x0 + 400 * k, top - 47.0 - tys[idx + k]) for k in range(len(batch))]; idx += len(batch)
    return cells, rep

def find_rows(doc, marks_mid, per_row=PER_ROW):
    """the user's 10-cell rows: the x0 / top y of the set of rows nearest to the marks (rows share x0); None when there are none"""
    from ezdxf import bbox
    rows = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != '72_MISGERET_WIN' or not e.closed: continue
        b = bbox.extents([e])
        if abs(b.size.x - 400 * per_row) < 2 and b.size.y >= 449: rows.append((b.extmin.x, b.extmin.y, b.extmax.y))
    if not rows: return None
    x0 = min(rows, key=lambda r: math.hypot(r[0] + 2000 - marks_mid[0], r[2] - marks_mid[1]))[0]
    return x0, max(r[1] for r in rows if abs(r[0] - x0) < 2)

def execute(a, doc, groups, plan):
    import shutil
    from dxflib import backup
    need = len(groups)
    if not a.cells_at:                                        # default = the user's rows of 10 (user 2026-10-16: whenever I ask for sections, use this arrangement)
        mids = [ev['mid'] for ev in plan if 'mid' in ev]; fr = find_rows(doc, (sum(m[0] for m in mids) / len(mids), sum(m[1] for m in mids) / len(mids)))
        if fr is None: sys.exit('no 10-cell template rows in the file: give --cells-at X Y (bottom-left x and top row y of the new rows)')
        a.cells_at = list(fr); print('using the template rows at x', fr[0])
    x0, y = a.cells_at
    needs = []; tys = []
    for n, ((rec, args), evs) in zip(range(a.first, a.first + need), groups.items()):
        ext = section_extent(a, rec, args, f'{n}-{n}', len(evs)); needs.append(need_height(ext)); tys.append(ext[4] if ext else 403.0)
        if ext and ext[2] - ext[0] > 395: print(f'WARNING {n}-{n} is {ext[2] - ext[0]:.0f} wide: wider than its 400 cell')
    free, rep = layout_cells(doc, x0, y, needs, tys)
    for r_ in rep: print(r_)
    backup(a.file, 'starplan-rows'); doc.saveas(a.file)
    used = [(c[0], c[1], False) for c in free]; free = used
    for n, ((rec, args), evs), cell in zip(range(a.first, a.first + need), groups.items(), free):
        cmd = [sys.executable, '-I', os.path.join(HERE, rec + '.py'), a.file, f'{n}-{n}', '--box', f'{cell[0]:g}', f'{cell[1]:g}', '400', '450'] + args.split()
        if rec == 'ledge_beam' and len(evs) > 1: cmd += ['--identical', str(len(evs))]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace'); print(f'{n}-{n} -> cell ({cell[0]:g},{cell[1]:g}):', (r.stdout.strip().splitlines() or [''])[-1], r.stderr.strip()[-200:] if r.returncode else '')
    d2 = ezdxf.readfile(a.file); ps2 = pairs(d2, a.max_y, a.min_y)
    for n, ((rec, args), evs) in zip(range(a.first, a.first + need), groups.items()):
        for ev in evs:
            for p, q in ps2:
                if abs((p.dxf.insert.x + q.dxf.insert.x) / 2 - ev['mid'][0]) < 3 and abs((p.dxf.insert.y + q.dxf.insert.y) / 2 - ev['mid'][1]) < 3:
                    for h in (p, q):
                        for t in h.attribs: t.dxf.text = str(n)
    from center_titles import center_titles
    center_titles(d2, min_y=min(c[1] for c in used) - 1000, max_y=max(c[1] for c in used))   # only the rows just filled: the user's rows keep his own title heights
    d2.saveas(a.file); print('marks renumbered; titles centred; audit errors', len(ezdxf.readfile(a.file).audit().errors))

if __name__ == '__main__': main()
