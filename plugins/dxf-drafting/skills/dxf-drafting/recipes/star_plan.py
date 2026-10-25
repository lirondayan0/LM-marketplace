"""Planner for the user's STAR MARKERS (hat `*` pairs on layer automatic_sections): reads every pair like a structural engineer and prints, per pair, the evidence and the section to draw - the whole chain
of conventions/sections-workflow.md + sections-reading.md in one dry listing. It never writes.
  python star_plan.py FILE [--max-y Y]
Per pair: view (as placed / after the clockwise rule for E/W pairs), the BEAM STRIP crossed (93_KORA edges), B from the geometry, the b/h TAG (451TEXT_KORA_100 text on the strip), a LEDGE (a 15_DASHED
line between the two faces = face of the wall above: stem = up to it, the rest = ledge), TRANSFER (new element on the strip), the slab label D=a+b near the cut, panel span vs view (plan_cuts: CORES / LENGTHWISE)
-> recipe + arguments. Pairs that share (recipe, args) are one section (identical beams); numbers are sequential. Every guess is flagged. See conventions 5-5d."""
import argparse, math, os, re, shutil, subprocess, sys, time
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


SLOPE_R_BARE = 150.0                  # ... and a note without a slab word this close
SLOPE_R = 300.0                       # a slope note this close to the cut line (cm on the plan) belongs to the section
SLOPE_OTHER = ('קורה', 'שן', 'אדריכלות')            # slopes of beams / teeth / 'per architecture': reported, never labelled (no taught drawing)
SLOPE_KIND = (('יציקה', 'cast'), ('יצוקה', 'cast'), ('לוחדים', 'hollow'), ('פלדלת', 'hollow'))      # words of the plan note -> slab kind (user's notes on 4_TEXT; 'לוחדים' = precast units: UNVERIFIED reading)


def split_slope(args):
    """('--slope left:cast' is the planner's own marker, not a recipe option) -> (args without it, (side, kind) | None)"""
    m = re.search(r' --slope (left|right):(cast|hollow)', args)
    return (args.replace(m.group(0), ''), (m.group(1), m.group(2))) if m else (args, None)


def split_shutter(args):
    """('--rshutter 10:35' is the planner's own marker: a roller-shutter downstand under a general beam, drawn by beam_shutter) -> (args without it, (b, h) | None)"""
    m = re.search(r' --rshutter ([\d.]+):([\d.]+)', args)
    return (args.replace(m.group(0), ''), (float(m.group(1)), float(m.group(2)))) if m else (args, None)


def clean_args(args): return split_shutter(split_slope(args)[0])[0]


def shutter_under_beam(doc, args, cell, shutter):
    """user 2026-10-24 (his hand version of korchakk 6-6, 1 example): the downstand b x h under the beam, flush with the stem's left face, from the beam bottom; coordinates from the section just drawn by general_beam in `cell`"""
    import general_beam as GB, beam_shutter as BS, ledge_beam as LB
    num = lambda k, d: float(m.group(1)) if (m := re.search(rf'--{k} (-?[\d.]+)', args)) else d
    B = num('B', 20.0); H = num('H', GB.MIN_H); D = num('D-right', num('D', 25.0)); dr = num('drop-right', 0.0)
    cx, cy = float(f'{cell[0]:g}'), float(f'{cell[1]:g}')       # the recipe was handed the cell with :g (6 digits): use the same numbers or the dimension look-up misses by 0.3
    ox = cx + GB.CELL_U0 - (B - 20) / 2; oy = cy + GB.CELL_V0; b, h = shutter; b = min(b, B)
    LB.apply_profile('israeli-structural')
    info = BS.draw(doc, ox, oy, oy + H - dr, oy + H - dr - D, b, h, 'right', ox + B + 76.4); info['width_dim_moved'] = BS.move_width_dim(doc, ox, oy, h, B)
    return info


def slope_notes(doc, p, q, view):
    """user 2026-10-22 ('find the slopes yourself, label only'): a plan note '... בשיפוע' standing ALONG the cut line (vertical cut <-> vertical note: the slope runs in the profile plane) near it
    -> ((side, kind, text) | None, [flags]). Side = the end of the cut line nearest the note, as seen in the view; kind from the note ('יציקה' = cast, 'לוחדים' = precast units). Beam / tooth /
    'per architect' slopes are only REPORTED (no taught drawing)."""
    ax, ay, bx, by = p.dxf.insert.x, p.dxf.insert.y, q.dxf.insert.x, q.dxf.insert.y; L = math.dist((ax, ay), (bx, by)) or 1.0; ux, uy = (bx - ax) / L, (by - ay) / L
    vx, vy = {'E': (1, 0), 'W': (-1, 0), 'N': (0, 1), 'S': (0, -1)}[view]; rx, ry = vy, -vx; mx, my = (ax + bx) / 2, (ay + by) / 2
    best = None; flags = []
    for t in doc.modelspace().query('TEXT'):
        if t.dxf.layer != '4_TEXT': continue
        tx = decode(t.dxf.text)
        if 'בשיפוע' not in tx and 'שיפוע' not in tx: continue
        x, y = t.dxf.insert.x, t.dxf.insert.y; tt = ((x - ax) * ux + (y - ay) * uy) / L; d = math.dist((x, y), (ax + ux * min(max(tt, 0), L), ay + uy * min(max(tt, 0), L)))
        if d > SLOPE_R: continue
        ang = math.radians(t.dxf.rotation)
        if abs(math.cos(ang) * ux + math.sin(ang) * uy) < 0.9: continue             # the note runs across the cut: the slope is not in the section's plane
        kind = next((k for w, k in SLOPE_KIND if w in tx), None)
        if kind is None and any(w in tx for w in SLOPE_OTHER): flags.append(f'slope note {tx!r} near the cut ({d:.0f} away): a beam / tooth / architect slope, not a slab slope - NOT labelled'); continue
        if kind is None and d > SLOPE_R_BARE: continue                              # a bare 'בשיפוע' (101.dxf; shlang 'K.O בשיפוע' = a LEVEL slopes) must stand right at the cut
        kind = kind or '?'                                                         # the slab's own kind decides, see the caller
        if best is None or d < best[0]: best = (d, kind, tx, (x, y))
    if best is None: return None, flags
    x, y = best[3]; end = (ax, ay) if math.dist((ax, ay), (x, y)) <= math.dist((bx, by), (x, y)) else (bx, by)
    return ('right' if (end[0] - mx) * rx + (end[1] - my) * ry > 0 else 'left', best[1], best[2]), flags


def slab_step_tag(doc, mx, my, r=450):
    """user 2026-10-24 (his 16-16, korchakk): the S pair at the edge of a THICK 'transformation slab' next to the standard slab: no beam, no free edge, but a wide 'b/h' tag (45_TEXT_KORA, 220/70 =
    the 70 cm slab area) at the cut -> (b, h, (x, y)) of the nearest wide tag (b >= 100) or None; 1 example, UNVERIFIED beyond it"""
    best = None
    for t in doc.modelspace().query('TEXT'):
        if t.dxf.layer not in TAGL: continue
        m = re.match(r'^\s*(\d+)\s*[/.]\s*(\d+)\s*$', t.dxf.text); d_ = math.dist((t.dxf.insert.x, t.dxf.insert.y), (mx, my))
        if m and int(m.group(1)) >= 100 and d_ <= r and (best is None or d_ < best[0]): best = (d_, (int(m.group(1)), int(m.group(2)), (t.dxf.insert.x, t.dxf.insert.y)))
    return best[1] if best else None


def slab_step_args(args):
    """'--thick 70 --thin 25 [--mirror]' -> (thick, thin, mirror)"""
    g = lambda k, d: float(m.group(1)) if (m := re.search(rf'--{k} ([\d.]+)', args)) else d
    return g('thick', 70.0), g('thin', 25.0), '--mirror' in args


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
        if e.dxftype() == 'LWPOLYLINE' and e.closed and pts: pts.append(pts[0])      # the CLOSING segment of a closed beam outline is a face too (korchakk 2026-10-23: the 140/70 cut saw 1 face of 2)
        for a_, b_ in zip(pts, pts[1:]):
            r = (b_[0] - a_[0], b_[1] - a_[1]); s_ = (Q[0] - P[0], Q[1] - P[1]); den = r[0] * s_[1] - r[1] * s_[0]
            if abs(den) < 1e-9: continue
            t = ((P[0] - a_[0]) * s_[1] - (P[1] - a_[1]) * s_[0]) / den; u = ((P[0] - a_[0]) * r[1] - (P[1] - a_[1]) * r[0]) / den
            if 0 <= t <= 1 and 0 <= u <= 1: out.append(u * L)
    return sorted(out)


LEFT_OF = {'N': (-1, 0), 'S': (1, 0), 'E': (0, 1), 'W': (0, -1)}      # unit vector pointing to the LEFT-hand side of the viewer for each view direction
LVL = re.compile(r'^\s*([+-]?\d+\.\d\d)\s*(?:=|$)')      # '-1.20=+50.30' (old) or a bare '+46.20' (brenda_karka S_M, 2026-10-22)
OKT = re.compile(r'^\s*o\.k\.?\s*=?\s*([+-]?\d+\.\d\d)', re.I)      # 'o.k. +45.25' or 'o.k=+45.25'

NUM = re.compile(r'[+-]?\d+\.\d\d')

def levels(text):
    """every level number of a plan level text, in reading order = the datums it is written in (user 2026-10-23, korchakk): '-0.30=+4.95' -> (-0.30, 4.95) [relative to the floor, absolute],
    'o.k.+271.30=+3.80' -> (271.30, 3.80) [architect's datum, absolute], '+4.95' / 'o.k.+4.95' -> (4.95,). The number AFTER '=' is the absolute one"""
    return tuple(float(x) for x in NUM.findall(text))

def level_drop(top, lv):
    """beam top - slab top (m) from two level tuples, compared in the SAME datum: both written 'x=abs' -> the absolute numbers; otherwise the pair (one number of each) that lies closest - the datums differ by metres,
    so the closest pair is the one written in the same datum (a beam 'o.k.+4.95' vs a slab '-0.30=+4.95' -> 0, not 5.25). None when a level is missing"""
    if not top or not lv: return None
    if len(top) > 1 and len(lv) > 1: return top[-1] - lv[-1]
    return min((t - s for t in top for s in lv), key=abs)

def slab_markers(doc):
    """S_M level markers of the plan: (x, y, D, level numbers) - the user's slab labels `D=nn` + `-1.20=+50.30` / `-0.30=+4.95` (attribs of the block S_M; levels(): tuple of datums); D without '+topping' = SOLID slab"""
    out = []
    for e in doc.modelspace().query('INSERT'):
        if e.dxf.name != 'S_M' or not e.attribs: continue
        d_ = lv = None
        for a in e.attribs:
            m_ = SLAB.match(a.dxf.text.strip())
            if m_: d_ = int(m_.group(1)) + int(m_.group(2) or 0); continue
            m_ = LVL.match(a.dxf.text)
            if m_: lv = levels(a.dxf.text)
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
        if best is None or key < best[0]: best = (key, levels(t.dxf.text))
    return best[1] if best else None

SEP_LAYERS = ('93_KORA', '9_KONTUR', '9_1_KONTUR', '82_KIR_OLE')      # beam faces / slab edges / walls: a straight line from the cut to a slab marker that crosses one of them leaves the panel (user 2026-10-22: 'some thicknesses are incorrect')
HARD_SEP = ('93_KORA', '9_KONTUR', '9_1_KONTUR')      # a marker BEHIND a beam face / slab edge is another panel: never used (korchakk 2026-10-23: the balcony beams borrowed D=25 + a level from the main floor across the wall); a wall alone only costs 1500

def separators(doc):
    segs = []
    for e in doc.modelspace().query('LINE LWPOLYLINE'):
        if e.dxf.layer not in SEP_LAYERS: continue
        if e.dxftype() == 'LINE': pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        else:
            pts = [(q[0], q[1]) for q in e.get_points()]
            if e.closed and pts: pts.append(pts[0])
        segs += [(pts[i], pts[i + 1], e.dxf.layer in HARD_SEP) for i in range(len(pts) - 1)]
    return segs

def _crosses(p1, p2, q1, q2):
    d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return d(p1, p2, q1) * d(p1, p2, q2) < 0 and d(q1, q2, p1) * d(q1, q2, p2) < 0

_SEPS = {}

def beam_axis(doc, p, q, B):
    """point of the cut line on the beam AXIS and the positions of its two faces along the cut: the two 93_KORA faces whose distance is B (+-3) (the user's mark pair is only roughly centred: 15 off on a 30 beam put the start of a side INSIDE the beam and made its own face a separator); (None, None) = not found"""
    cf = cut_faces(doc, (p, q)); P = (p.dxf.insert.x, p.dxf.insert.y); Q = (q.dxf.insert.x, q.dxf.insert.y); L = math.dist(P, Q)
    for i, a_ in enumerate(cf):
        for b_ in cf[i + 1:]:
            if abs((b_ - a_) - B) <= 3 and L > 0:
                c_ = (a_ + b_) / 2; return (P[0] + (Q[0] - P[0]) * c_ / L, P[1] + (Q[1] - P[1]) * c_ / L), (a_, b_)
    return None, None

def free_sides(doc, p, q, view, faces):
    """sides of the viewer ('L' / 'R') where the beam face IS the slab edge: a 9_KONTUR line crosses the cut within 3 of the face (an edge beam - no slab there, the beam face is the end of the floor); a 9_KONTUR farther out = a cantilever slab, the side exists.
    faces = the (low, high) positions of the beam faces along the cut P -> Q (beam_axis). Returns (set of free sides, {side: cantilever length})"""
    if not faces: return set(), {}
    P = (p.dxf.insert.x, p.dxf.insert.y); Q = (q.dxf.insert.x, q.dxf.insert.y); L = math.dist(P, Q); ks = []
    for e in doc.modelspace().query('LINE LWPOLYLINE'):
        if e.dxf.layer not in ('9_KONTUR', '9_1_KONTUR'): continue
        pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)] if e.dxftype() == 'LINE' else [(x, y) for x, y in e.get_points('xy')] + ([(e.get_points('xy')[0][0], e.get_points('xy')[0][1])] if e.closed else [])
        for a_, b_ in zip(pts, pts[1:]):
            r = (b_[0] - a_[0], b_[1] - a_[1]); s_ = (Q[0] - P[0], Q[1] - P[1]); den = r[0] * s_[1] - r[1] * s_[0]
            if abs(den) < 1e-9: continue
            t = ((P[0] - a_[0]) * s_[1] - (P[1] - a_[1]) * s_[0]) / den; u = ((P[0] - a_[0]) * r[1] - (P[1] - a_[1]) * r[0]) / den
            if 0 <= t <= 1 and 0 <= u <= 1: ks.append(u * L)
    lx, ly = LEFT_OF[view]; high_is_left = ((Q[0] - P[0]) * lx + (Q[1] - P[1]) * ly) > 0
    sd_hi, sd_lo = ('L', 'R') if high_is_left else ('R', 'L'); free = set(); cant = {}
    for sd, face, sign in ((sd_hi, faces[1], 1), (sd_lo, faces[0], -1)):
        out = [sign * (k - face) for k in ks if sign * (k - face) > -3]
        if out and min(out) <= 3: free.add(sd)
        elif out: cant[sd] = round(min(out))
    free |= outer_sides(doc, p, q, view, faces)
    return free, cant

OUTER_LAYERS = ('93_KORA', '9_KONTUR', '9_1_KONTUR', '8_KIR', '82_KIR_OLE', '83_KIR_OLE_No Constr', '62_HATCH_AMUD_OLE', '63_HATCH_KIR_OLE', '6_HATCH')      # structural geometry: anything of it BEYOND a beam face means the floor continues there
OUTER_WINDOW = 1000.0      # along the beam, each way from the cut (cm)

def _struct_points(doc):
    pts = []
    for e in doc.modelspace():
        if e.dxf.layer not in OUTER_LAYERS: continue
        t = e.dxftype()
        try:
            if t == 'LINE': pts += [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
            elif t == 'LWPOLYLINE': pts += [(x, y) for x, y in e.get_points('xy')]
            elif t == 'HATCH': pts += [(v[0], v[1]) for path in e.paths for v in getattr(path, 'vertices', [])]
            elif t == 'INSERT':
                for ve in e.virtual_entities():
                    if ve.dxftype() == 'LINE': pts += [(ve.dxf.start.x, ve.dxf.start.y), (ve.dxf.end.x, ve.dxf.end.y)]
                    elif ve.dxftype() == 'LWPOLYLINE': pts += [(x, y) for x, y in ve.get_points('xy')]
        except Exception: continue
    return pts

_OUT_PTS = {}

def outer_sides(doc, p, q, view, faces):
    """sides of the viewer ('L' / 'R') with NO floor at all beyond the beam face: no structural geometry (OUTER_LAYERS) lies beyond the face within OUTER_WINDOW along the beam - the beam is the edge of the building: no floor plan and no ceiling there (user 2026-10-25, test_sections 1-1 / 2-2 / 3-3: the section must show the slab on ONE side only). UNVERIFIED beyond that file."""
    if not faces: return set()
    P = (p.dxf.insert.x, p.dxf.insert.y); Q = (q.dxf.insert.x, q.dxf.insert.y); L = math.dist(P, Q)
    if L <= 0: return set()
    ux, uy = (Q[0] - P[0]) / L, (Q[1] - P[1]) / L
    if abs(uy) < 0.03: ux, uy = math.copysign(1.0, ux), 0.0      # the user's mark pairs are a fraction of a degree off the axis: over 1000 cm that is 4+ cm, more than the 3 tolerance
    elif abs(ux) < 0.03: ux, uy = 0.0, math.copysign(1.0, uy)
    pts = _OUT_PTS.setdefault(id(doc), _struct_points(doc)); c_ = (faces[0] + faces[1]) / 2
    lx, ly = LEFT_OF[view]; high_is_left = (ux * lx + uy * ly) > 0; sd_hi, sd_lo = ('L', 'R') if high_is_left else ('R', 'L'); out = set()
    for sd, face, sign in ((sd_hi, faces[1], 1), (sd_lo, faces[0], -1)):
        has = any(sign * (((x - P[0]) * ux + (y - P[1]) * uy) - face) > 3 and abs(-(x - P[0]) * uy + (y - P[1]) * ux) <= OUTER_WINDOW for x, y in pts)
        if not has: out.add(sd)
    return out

def side_info(doc, mx, my, view, b=None, markers=None, tagpos=None, free=()):
    """what lies on each side of the beam, seen by the viewer: dict(D={'L': nn | None, 'R': ..} (None = nothing there: a FREE edge), drop={'L': cm, 'R': cm}, unknown={sides with no slab marker of THEIR panel}, note).
    Per side: the S_M marker (25-700 along the cut, <= 700 beamwise) of the panel that touches the beam - a marker whose straight line from the beam face crosses a beam face / slab edge (HARD_SEP) is ANOTHER panel and is never used, a wall only costs
    1500 - then nearest by hypot(along, 2*beamwise); a side still empty widens to 900. A side with no marker of its own = UNKNOWN: solid slab with the parametric thickness H, drawn 25, flush (user rule 2026-10-18: never guess a thickness; was 'copied from the other side').
    Levels are compared in ONE datum (level_drop). A side in `free` has no slab."""
    mk = markers if markers is not None else slab_markers(doc); lx, ly = LEFT_OF[view]; found = {}
    seps = _SEPS.setdefault(id(doc), separators(doc)); half = (b or 30) / 2.0 + 10.0
    def scan(lim, wide):
        for x, y, D, lv in mk:
            al = (x - mx) * lx + (y - my) * ly; pp = abs((x - mx) * ly - (y - my) * lx)
            if not (25 < abs(al) < lim and pp < lim): continue
            sd = 'L' if al > 0 else 'R'
            if sd in free or (wide and sd in found): continue
            s0 = (mx + math.copysign(half, al) * lx, my + math.copysign(half, al) * ly); hard = soft = 0
            for q1, q2, h_ in seps:
                if _crosses(s0, (x, y), q1, q2):
                    if h_: hard += 1
                    else: soft += 1
            if hard or soft >= 3: continue      # behind a beam face / slab edge, or behind 3+ walls: another panel (a wall alone only costs 1500)
            sc = soft * 1500 + math.hypot(al, 2.0 * pp)
            if sd not in found or sc < found[sd][0]: found[sd] = (sc, D, lv, soft, 999 if wide else pp)
    scan(700, False)
    if len(found) + len(free) < 2: scan(900, True)
    top = beam_top_level(doc, mx, my, b, tagpos) if b else None; note = []; D = {}; drop = {}; unknown = set()
    if top is None and b:                    # beam level not on the plan near its tag: the beam top is the HIGHER slab top of the two sides (UNVERIFIED)
        lvs = [v[-1] for _, _, v, _, _ in found.values() if v]
        if lvs: top = (max(lvs),); note.append('beam top level = the higher slab level (tag has no o.k. text) (UNVERIFIED)')
    for sd in 'LR':
        name = 'left' if sd == 'L' else 'right'
        if sd in free: D[sd] = None; drop[sd] = 0; note.append(f'{name}: the beam face is the slab edge (9_KONTUR, or no floor beyond it) - no slab'); continue
        if sd not in found: D[sd] = 25; drop[sd] = 0; unknown.add(sd); note.append(f'{name} slab: no slab marker of its own panel -> solid slab, thickness symbol H, flush (UNVERIFIED)'); continue
        _, d_, lv, soft, pp = found[sd]; D[sd] = d_
        if soft or pp > 350: note.append(f"{name} slab D={d_} taken from a marker {'beyond a wall' if soft else str(round(pp)) + ' away along the beam'} (UNVERIFIED)")
        dd = level_drop(top, lv); dp = round(dd * 100) if dd is not None else 0
        if dp < 0: dp = 0; note.append(f'{name} slab above the beam top: drawn flush (UNVERIFIED)')
        if dp > 150: note.append(f'{name} level drop {dp} is implausible - drawn flush (UNVERIFIED)'); dp = 0      # a datum mix-up must never grow the section
        drop[sd] = dp
    if top is None and not b: note.append('untagged beam: slabs drawn flush with the beam top, levels not evaluated (UNVERIFIED)')
    return dict(D=D, drop=drop, unknown=unknown, note='; '.join(note))

def side_slabs(doc, mx, my, view, b=None, markers=None, tagpos=None, free=()):
    """(Dl, Dr, drop_l, drop_r, note) - side_info in the old tuple form (a side without slab = 0)"""
    i = side_info(doc, mx, my, view, b, markers, tagpos, free)
    return i['D']['L'] or 0, i['D']['R'] or 0, i['drop']['L'], i['drop']['R'], i['note']

def general_args(info, B=None):
    """general_beam.py slab arguments for the sides found by side_info: per-side D / drop, `--sides` when one side is a free edge, the symbol H on the thickness dim of every side that has no marker of its own"""
    D, dp, unk = info['D'], info['drop'], info['unknown']; Dl, Dr = D['L'], D['R']
    sides = 'both' if (Dl is not None and Dr is not None) else ('right' if Dr is not None else ('left' if Dl is not None else 'both'))
    if Dl is not None and Dr is not None and Dl == Dr and dp['L'] == dp['R'] == 0 and not unk: a = f'--D {Dl}'
    else: a = f'--D {max(v for v in (Dl, Dr) if v is not None)} --D-left {Dl or 0} --D-right {Dr or 0} --drop-left {dp["L"]} --drop-right {dp["R"]}'
    if sides != 'both': a += f' --sides {sides}'
    if unk == {'L', 'R'}: a += ' --d-label H'
    elif unk: a += f' --d-label-{"left" if "L" in unk else "right"} H'
    return a

WALL_LAYERS = {'82_KIR_OLE': 'new wall rising from the beam', '83_KIR_OLE_No Constr': 'NON-structural wall (no transfer, no wall reinforcement)'}      # korchakk 2026-10-23: 'No Constr' layers = non-structural elements

def wall_above(doc, p, q, faces):
    """walls rising from the beam: (layer, thickness) of every pair of wall faces (82_KIR_OLE / 83_KIR_OLE_No Constr) the cut crosses BETWEEN the two beam faces. No recipe draws a wall above a beam outside XREF files (conventions 'BEAM WITH A WALL RISING ABOVE'): it is reported, never invented."""
    if not faces: return []
    P = (p.dxf.insert.x, p.dxf.insert.y); Q = (q.dxf.insert.x, q.dxf.insert.y); L = math.dist(P, Q); out = []
    for lay in WALL_LAYERS:
        ts = []
        for e in doc.modelspace().query('LINE LWPOLYLINE'):
            if e.dxf.layer != lay: continue
            pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)] if e.dxftype() == 'LINE' else [(x, y) for x, y in e.get_points('xy')] + ([(e.get_points('xy')[0][0], e.get_points('xy')[0][1])] if e.closed else [])
            for a_, b_ in zip(pts, pts[1:]):
                r = (b_[0] - a_[0], b_[1] - a_[1]); s_ = (Q[0] - P[0], Q[1] - P[1]); den = r[0] * s_[1] - r[1] * s_[0]
                if abs(den) < 1e-9: continue
                t = ((P[0] - a_[0]) * s_[1] - (P[1] - a_[1]) * s_[0]) / den; u = ((P[0] - a_[0]) * r[1] - (P[1] - a_[1]) * r[0]) / den
                if 0 <= t <= 1 and 0 <= u <= 1 and faces[0] - 1 <= u * L <= faces[1] + 1: ts.append(u * L)
        ts = sorted(ts)
        out += [(lay, round(b_ - a_)) for a_, b_ in zip(ts[::2], ts[1::2]) if b_ - a_ > 1]
    return out

def slab_sides(doc, p, q, view, B, mx, my, MK, tagpos=None):
    """(info, note) for a general beam: the beam AXIS from the two 93_KORA faces the cut crosses (B apart), free edges (9_KONTUR on a face = no slab there; farther out = cantilever) and the slab / level of each remaining side (side_info)"""
    axis, faces = beam_axis(doc, p, q, B); cx, cy = axis if axis else (mx, my)
    free, cant = free_sides(doc, p, q, view, faces)
    info = side_info(doc, cx, cy, view, B, MK, tagpos, free); nt = [info['note']] if info['note'] else []
    for lay, w in wall_above(doc, p, q, faces): nt.append(f'{WALL_LAYERS[lay]} ({lay}, {w} wide) crosses the cut - NOT drawn (no recipe for a wall above a beam; the mark S / SS / ST selects the stirrup table)')
    for sd, v in sorted(cant.items()): nt.append(f"{'left' if sd == 'L' else 'right'} slab is a cantilever {v} long (slab edge 9_KONTUR beyond the face)")
    return info, '; '.join(nt)

def slab_text(info):
    """'left D=25 (drop 0), right free edge' - one short phrase for the planner note"""
    def one(sd):
        D = info['D'][sd]
        return 'no slab (free edge)' if D is None else ('H (no marker)' if sd in info['unknown'] else f"D={D} (drop {info['drop'][sd]})")
    return f"left {one('L')}, right {one('R')}"

def mark_of(p, q):
    """'S' (reinforcement as per plan), 'SS' (engineer chooses diameter), 'ST' (= S with TRANSFER-beam stirrups, user 2026-10-16) or '*' (old notation = S) from the pair's attribute"""
    t = ' '.join(x.dxf.text.strip().upper() for h in (p, q) for x in h.attribs)
    return 'SS' if 'SS' in t else ('ST' if 'ST' in t else 'S')

def clock_key(mid, c):
    """numbering order: START AT THE RIGHT (east of the centroid c), then CLOCKWISE: east -> south (the bottom runs right to left) -> west -> north (user 2026-10-24)"""
    return (math.atan2(mid[0] - c[0], mid[1] - c[1]) - math.pi / 2 + 1e-6) % (2 * math.pi)


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
                info, sn_ = slab_sides(doc, p, q, view, int(bm['b']), mx, my, MK, tuple(bm['at']) if isinstance(bm.get('at'), (tuple, list)) else None)
                ev.update(slabs=dict(L=(info['D']['L'], info['drop']['L']), R=(info['D']['R'], info['drop']['R'])), recipe='general_beam', args=f"--B {bm['b']} --H {bm['h']} {general_args(info)} --stirrups {st}", note=f"beam {bm['b']}/{bm['h']}: slab {slab_text(info)} as seen in the view" + (f'; {sn_}' if sn_ else '')); plan.append(ev); continue
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
                    b_, h_ = tg[0][1].groups(); info, sn_ = slab_sides(doc, p, q, view, int(b_), mx, my, MK)
                    ev.update(B=Bc, tag=f'{b_}/{h_}', slabs=dict(L=(info['D']['L'], info['drop']['L']), R=(info['D']['R'], info['drop']['R'])), recipe='general_beam', args=f"--B {b_} --H {h_} {general_args(info)} --stirrups standard", note=f'faces from the cut crossings, tag {b_}/{h_}: slab {slab_text(info)}' + (f'; {sn_}' if sn_ else '')); plan.append(ev); continue
        if strip is None:
            wB = wall_cut(doc, p, q)
            if wB:        # user 2026-10-22: 'a wall that terminates, ceilings on both sides' = the general untagged-beam section (5c): B = wall thickness, height symbol h, slabs both sides
                info, sn_ = slab_sides(doc, p, q, view, wB, mx, my, MK)
                ev.update(recipe='general_beam', args=f"--B {wB} --H 40 --h-label h {general_args(info)} --stirrups standard", note=f'existing wall 8_KIR B={wB} crossed by the cut, general beam, height h; slab {slab_text(info)}' + (f'; {sn_}' if sn_ else '')); plan.append(ev); continue
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
            stp = slab_step_tag(doc, mx, my)
            if stp:      # his 16-16 made parametric (2026-10-25: 'learn to create a stepped section for varying slab thicknesses'): thick = the h of the wide tag, thin = the plan's D label else 25; thick slab on the side of the tag
                thin_, tn_ = edge_thickness(doc, mx, my); found_ = bool(thin_); thin_ = thin_ or 25
                vx_, vy_ = {'E': (1, 0), 'W': (-1, 0), 'N': (0, 1), 'S': (0, -1)}[view]; right_ = ((stp[2][0] - mx) * vy_ + (stp[2][1] - my) * (-vx_)) > 0      # the tag lies on the RIGHT of the view
                if stp[1] > thin_: ev.update(recipe='slab_step', args=f'--thick {stp[1]} --thin {thin_:g}' + (' --mirror' if right_ else ''), note=f'SLAB STEP: no beam / free edge, a wide tag {stp[0]}/{stp[1]} (thick slab {stp[1]}) at the cut, thin slab {thin_:g}{"" if found_ else " assumed"}; his 16-16 drawn from rules, thick slab on the {"right" if right_ else "left"} of the view - UNVERIFIED beyond 70 / 25'); plan.append(ev); continue
            ev.update(kind='NOTHING', note='no beam edges and no slab edge at the cut: skip + report' + (f'; a wide tag {stp[0]}/{stp[1]} stands there but no thinner slab: not a step' if stp else '')); plan.append(ev); continue
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
        elif ev['tag'] and not (ev['span'] == 'LENGTHWISE' or (sl and sl[0][4] > 0)):      # user rule 2026-10-21: no hollow label / panel span beside the beam = SOLID slab (korchakk 2026-10-23: a hollow 20+5 ledge beam was assumed for a plan without any hollow-core slab)
            b_, h_ = ev['tag'].split('/'); info, sn_ = slab_sides(doc, p, q, view, int(b_), mx, my, MK)
            ev.update(slabs=dict(L=(info['D']['L'], info['drop']['L']), R=(info['D']['R'], info['drop']['R'])), recipe='general_beam', args=f"--B {b_} --H {h_} {general_args(info)} --stirrups {st}", note=f'tagged beam {b_}/{h_}, no hollow-core evidence at the cut: slab {slab_text(info)}' + (f'; {sn_}' if sn_ else ''))
        elif ev['tag']:
            b_, h_ = ev['tag'].split('/'); ev.update(recipe='ledge_beam', args=f'--beam {b_} {h_} --slab 20 --topping 5 --kind ledge --sides {"both" if (ev["ledge"] and len(ev["ledge"]["sides"]) == 2) else "right"} --stirrups {st}', note='ledge beam (panels bear on it)')
        elif ev['ledge']:
            ev.update(recipe='ledge_beam', args=f'--beam {B} 40 --slab 20 --topping 5 --kind ledge --sides right --stirrups {st} --h-label h', note=f"UNTAGGED beam with a tooth: stem {ev['ledge']['stem']} + ledge {ev['ledge']['width']} (dashed line = wall above); height = symbol h (drawn 40, UNVERIFIED); ledge side must be checked against the view")
        else:
            info, sn_ = slab_sides(doc, p, q, view, B, mx, my, MK); shu = roller_shutter(doc, mx, my)
            ev.update(slabs=dict(L=(info['D']['L'], 0), R=(info['D']['R'], 0)), recipe='general_beam', args=f'--B {B} {general_args(info)} --H 40 --h-label h --stirrups {st}', note=f'UNTAGGED beam without a ledge: the general 6-6, height symbol h (UNVERIFIED H=40); slab {slab_text(info)}, drawn flush (levels not evaluated)' + (f'; {sn_}' if sn_ else '') )
        plan.append(ev)
    pq_of = {(round((p.dxf.insert.x + q.dxf.insert.x) / 2), round((p.dxf.insert.y + q.dxf.insert.y) / 2)): (p, q) for p, q in ps}
    own = {}                                              # roller-shutter text (automatic_Roller_shutter, b/h) -> the NEAREST cut only (korchakk: one text, two cuts within 450 -> the shutter was drawn twice)
    for t in doc.modelspace().query('TEXT'):
        nums = re.findall(r'\d+(?:\.\d+)?', t.dxf.text)
        if t.dxf.layer == ROLLER_LAYER and len(nums) >= 2 and plan:
            d_, ev_ = min((math.dist((t.dxf.insert.x, t.dxf.insert.y), e_['mid']), i) for i, e_ in enumerate(plan))
            if d_ <= 450 and (id(plan[ev_]) not in own or own[id(plan[ev_])][0] > d_): own[id(plan[ev_])] = (d_, (float(nums[0]), float(nums[1])))
    for ev in plan:                                       # ... of a general beam: the downstand is drawn under the beam (beam_shutter); other section types are reported
        if 'args' not in ev or ev['recipe'] == 'slab_edge' or id(ev) not in own: continue
        shu = own[id(ev)][1]
        if ev['recipe'] == 'general_beam': ev['args'] += f' --rshutter {shu[0]:g}:{shu[1]:g}'; ev['note'] = '; '.join(filter(None, [ev.get('note'), f'ROLLER SHUTTER {shu[0]:g}/{shu[1]:g} from the plan text: drawn under the beam (b/h mapping UNVERIFIED)']))
        else: ev['note'] = '; '.join(filter(None, [ev.get('note'), f'ROLLER SHUTTER text {shu[0]:g}/{shu[1]:g} near the cut: NOT DRAWN for a {ev["recipe"]} section (no taught drawing) - add it by hand']))
    for ev in plan:                                       # sloped slab along the cut (user 2026-10-22): label only, drawn by slope_label after the section; sections with different slopes are never merged (the marker is part of args)
        if 'args' not in ev or ev['mid'] not in pq_of: continue
        sl_, fl_ = slope_notes(doc, *pq_of[ev['mid']], ev['view']); ev['note'] = '; '.join(filter(None, [ev.get('note')] + fl_))
        if sl_:
            kd = sl_[1] if sl_[1] != '?' else ('hollow' if ev['recipe'] == 'ledge_beam' else 'cast')       # bare note: precast panels beside a ledge / cast edge beam, else a cast slab (UNVERIFIED)
            ev['args'] += f' --slope {sl_[0]}:{kd}'; ev['note'] = '; '.join(filter(None, [ev.get('note'), f'SLOPED SLAB ({sl_[2]!r} -> {kd}{" by the section type" if sl_[1] == "?" else ""}, side {sl_[0]}): label only, UNVERIFIED']))
    for ev in plan:                                       # S / SS marks (user 2026-10-16): SS = engineer picks the bars -> X$XX notes
        if 'args' in ev: ev['args'] += ' --detail ' + ('ss' if ev.get('mark') == 'SS' else 'plan')
    for ev in plan:                                          # stirrup table by MARK: ST = transfer beam, S / SS = standard (a.stirrups forces one table)
        if 'args' in ev:
            tbl = a.stirrups or ('transfer' if ev.get('mark') == 'ST' else 'standard'); ev['args'] = re.sub(r'--stirrups \w+', f'--stirrups {tbl}', ev['args']); ev['transfer'] = tbl == 'transfer'
    plan.sort(key=lambda e: clock_key(e['mid'], (cx, cy)))   # user 2026-10-24: 'number the sections from right to left, clockwise' = START AT THE RIGHT (east of the centroid), then clockwise: east -> south (bottom runs right to left) -> west -> north (UNVERIFIED reading; was: start at north)
    groups = {}
    for ev in plan:
        if 'recipe' in ev: groups.setdefault((ev['recipe'], ev['args']), []).append(ev)
    print(f'{len(plan)} pairs, {len(groups)} section type(s); centre of the marks ({cx:.0f}, {cy:.0f})')
    for ev in plan: print('pair', ev['mid'], 'view', ev['view'], '|', {k: v for k, v in ev.items() if k not in ('mid', 'view', 'recipe', 'args', 'note')})
    for n, ((rec, args), evs) in enumerate(groups.items(), a.first):
        print(f"\nsection {n}-{n}: {rec}.py <file> {n}-{n} --box X Y 400 450 {args}   [{len(evs)} pair(s): {', '.join(str(e['mid']) for e in evs)}]" + (f"  note: {' || '.join(dict.fromkeys(e['note'] for e in evs if e.get('note')))}" if any(e.get('note') for e in evs) else '') + (f"  identical for {len(evs)} beams" if len(evs) > 1 else ''))
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

def extent_base(a):
    """a small stand-in for the plan, built ONCE per run: every TEXT (the recipes copy note styles from texts) and all tables / blocks, but no other entity and no dimension / array blocks. A section is measured
    on it instead of on the 10-30 MB plan (was ~5 s per section, 18 sections = most of a 190 s draw step; same numbers: tests/run_tests.py). Returns the path, or None."""
    if hasattr(a, '_ext_base'): return a._ext_base
    import tempfile
    a._ext_base = None
    try:
        d = ezdxf.readfile(a.file); msp = d.modelspace()
        for e in list(msp):
            if e.dxftype() != 'TEXT': msp.delete_entity(e)
        for b in list(d.blocks):
            if b.name.upper().startswith(('*D', '*U', '*E')): d.blocks.delete_block(b.name, safe=False)
        tdir = tempfile.mkdtemp(prefix='sp_extbase_'); p = os.path.join(tdir, 'base.dxf'); d.saveas(p); a._ext_base = p; a._ext_seed = int(d.header.get('$HANDSEED', '0'), 16)      # every entity a recipe adds gets a handle >= the seed
    except Exception as ex: print('extent base not built (measuring on the full file):', ex)
    return a._ext_base

def section_extent(a, rec, args, name, identical=0, _full=False):
    if rec == 'slab_step':
        import slab_step; sa = slab_step_args(args); return slab_step.layout(0.0, 0.0, thick=sa[0], thin=sa[1])[2]      # built into a scratch document, no recipe process
    """draw ONE section into a scratch copy (box 0 0 400 450) and measure everything the recipe added (title, bars, notes, dims, stirrup details): returns (xmin, ymin, xmax, ymax) relative to the cell box origin"""
    import tempfile
    from ezdxf import bbox
    src = None if _full else extent_base(a); src = src or a.file
    tdir = tempfile.mkdtemp(prefix='sp_extent_'); tmp = os.path.join(tdir, 'extent.dxf')      # UNIQUE per call: a fixed temp name collided with a second run (app + tests at the same time -> 'missing ENDSEC', no sections drawn, 2026-10-24)
    cmd = [sys.executable, '-I', os.path.join(HERE, rec + '.py'), src, name, '--box', '0', '0', '400', '450'] + clean_args(args).split() + ['-o', tmp]
    if rec == 'ledge_beam' and identical > 1: cmd += ['--identical', str(identical)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, DIMPLAN_FAST='1'))
    if r.returncode or not os.path.exists(tmp):
        shutil.rmtree(tdir, ignore_errors=True)
        return section_extent(a, rec, args, name, identical, _full=True) if src != a.file else None
    try:
        if src == a.file: before = {e.dxf.handle for e in ezdxf.readfile(src).modelspace()}; new = [e for e in ezdxf.readfile(tmp).modelspace() if e.dxf.handle not in before]
        else: new = [e for e in ezdxf.readfile(tmp).modelspace() if int(e.dxf.handle, 16) >= a._ext_seed]
    finally: shutil.rmtree(tdir, ignore_errors=True)
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
    if not need: sys.exit('NOTHING TO DRAW: none of the marked cuts could be read as a section (see the NOT DRAWN lines above: no beam edges and no slab edge at the cut)')      # was: ValueError min() of an empty sequence (3600-CON-11 read as a standard file, 2026-10-25)
    if not a.cells_at:                                        # default = the user's rows of 10 (user 2026-10-16: whenever I ask for sections, use this arrangement)
        mids = [ev['mid'] for ev in plan if 'mid' in ev]; fr = find_rows(doc, (sum(m[0] for m in mids) / len(mids), sum(m[1] for m in mids) / len(mids)))
        if fr is None: sys.exit('no 10-cell template rows in the file: give --cells-at X Y (bottom-left x and top row y of the new rows)')
        a.cells_at = list(fr); print('using the template rows at x', fr[0])
    x0, y = a.cells_at
    needs = []; tys = []
    for n, ((rec, args), evs) in zip(range(a.first, a.first + need), groups.items()):
        ext = section_extent(a, rec, args, f'{n}-{n}', len(evs)); needs.append(need_height(ext)); tys.append(ext[4] if ext else 403.0)
        if ext and ext[2] - ext[0] > 395: print(f'{n}-{n} is {ext[2] - ext[0]:.0f} wide: its cell is widened afterwards (fit_rows)')
    free, rep = layout_cells(doc, x0, y, needs, tys)
    for r_ in rep: print(r_)
    backup(a.file, 'starplan-rows'); doc.saveas(a.file)
    used = [(c[0], c[1], False) for c in free]; free = used; failed = []
    # BATCH (2026-10-24, loading time): every section is drawn into ONE open document and the file is saved ONCE (was: one process per section = a full load + save of the 10-30 MB plan each, ~60% of the round).
    # A section that fails is rolled back (its new entities deleted), the document is saved and that section is drawn the old way, one process, 3 attempts; the document is then reloaded and the batch goes on.
    import io, contextlib, importlib
    mods = {m: importlib.import_module(m) for m in ('ledge_beam', 'general_beam', 'slab_edge')}
    bdoc = ezdxf.readfile(a.file); last = {}; slopes = []
    for n, ((rec, args), evs), cell in zip(range(a.first, a.first + need), groups.items(), free):
        args, slope = split_slope(args); args, shutter = split_shutter(args)
        argv = [a.file, f'{n}-{n}', '--box', f'{cell[0]:g}', f'{cell[1]:g}', '400', '450'] + args.split()
        if rec == 'ledge_beam' and len(evs) > 1: argv += ['--identical', str(len(evs))]
        if rec == 'slab_step':                                   # stamped from the user's own example (slab_step.py), not a drawing recipe
            import slab_step
            try: sa = slab_step_args(args); ox_, oy_, _ = slab_step.layout(cell[0], cell[1], thick=sa[0], thin=sa[1]); n_, nd_ = slab_step.build(bdoc, ox_, oy_, f'{n}-{n}', sa[0], sa[1], sa[2]); line, err = f'slab step {sa[0]:g} / {sa[1]:g} drawn: {n_} entities + {nd_} dims', ''
            except Exception as ex: line, err = '', f'{type(ex).__name__}: {ex}'; failed.append(f'{n}-{n}')
            print(f'{n}-{n} -> cell ({cell[0]:g},{cell[1]:g}):', line, err); continue
        msp = bdoc.modelspace(); seen = {e.dxf.handle for e in msp}; buf = io.StringIO(); ok = rec in mods
        if ok:
            try:
                with contextlib.redirect_stdout(buf): mods[rec].main(argv, bdoc)
            except (Exception, SystemExit) as ex:
                ok = False; print(f'{n}-{n}: in-process draw failed ({type(ex).__name__}: {ex}); redrawing it as its own process')
                for e in list(msp):
                    if e.dxf.handle not in seen: msp.delete_entity(e)
        if ok: line, err = (buf.getvalue().strip().splitlines() or [''])[-1], ''
        else:
            bdoc.saveas(a.file)
            cmd = [sys.executable, '-I', os.path.join(HERE, rec + '.py')] + argv
            for attempt in (1, 2, 3):                       # a recipe that cannot read / write the file (antivirus lock, truncated read: app run 2026-10-24 'missing ENDSEC') is retried, never skipped silently
                r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, DIMPLAN_FAST='1'))
                if not r.returncode: break
                time.sleep(3)
            line, err = (r.stdout.strip().splitlines() or [''])[-1], r.stderr.strip()[-200:] if r.returncode else ''
            if r.returncode: failed.append(f'{n}-{n}')
            bdoc = ezdxf.readfile(a.file)
        print(f'{n}-{n} -> cell ({cell[0]:g},{cell[1]:g}):', line, err)
        if shutter and not err:
            try: print(f'{n}-{n}: roller shutter {shutter[0]:g}/{shutter[1]:g} drawn under the beam (UNVERIFIED beyond his korchakk 6-6):', shutter_under_beam(bdoc, args, cell, shutter))
            except (Exception, SystemExit) as ex: print(f'WARNING {n}-{n}: roller shutter NOT drawn ({type(ex).__name__}: {ex}) - add it by hand')
        if slope and not err: slopes.append(dict(n=n, box=[cell[0], cell[0] + 400, cell[1], cell[1] + 450], side=slope[0], kind=slope[1]))
    bdoc.saveas(a.file)
    if slopes:      # the label copies the mirrored SIVAN notes, which exist only after the finishing passes: slope_label.py --json runs then (sections_round does it), the sidecar lists where
        import json; json.dump(slopes, open(a.file + '.slopes.json', 'w')); print(f"SLOPED SLABS: {len(slopes)} section(s) wait for their label - run slope_label.py FILE --json {a.file}.slopes.json after sivan_text (sections_round does)")
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
    if failed: print('SECTIONS NOT DRAWN (recipe failed 3 times): ' + ', '.join(failed)); sys.exit(2)

if __name__ == '__main__': main()
