"""Recipe: orient the user's star section marks (`hat` pairs on layer `automatic_sections`, any case; old name `claude_sections`) CLOCKWISE around the plan (user 2026-10-15).
  python star_orient.py FILE [--dry] [--max-y Y]      (--max-y: ignore pairs above Y, e.g. a second plan copy)
A pair that looks E/W (a horizontal beam) is turned so it looks along the clockwise tangent about the centroid of the marked pairs: north side -> E, south side -> W. Pairs looking N/S (vertical beams) ARE turned too since 2026-10-25 (east side -> S, west -> N; was: not touched, user 2026-10-15: the east wall-beam 6-6 with the ledge slab on its right keeps its N view) (slab ends up on the RIGHT of the view for edge beams;
this is also the old convention 'north edges look E, south edges look W'). Flipping = rotation + swapped mirror signs (LAYOUT of cut_marks.py); insert points stay. Snapshot first. UNVERIFIED reading of 'clockwise'."""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from dxflib import backup
from cut_marks import ROT, LAYOUT
LAYERS = ('automatic_sections', 'claude_sections')
VIEW = {v: k for k, v in ROT.items()}

def pairs(doc, max_y=None, min_y=None):
    hats = [e for e in doc.modelspace().query('INSERT') if e.dxf.name == 'hat' and e.dxf.layer.lower() in LAYERS and (max_y is None or e.dxf.insert.y < max_y) and (min_y is None or e.dxf.insert.y >= min_y)]
    out, used = [], set()
    for a in hats:
        if id(a) in used: continue
        rot = round(a.dxf.rotation) % 360; ra = a.dxf.rotation % 180      # the cut line runs along the mark's rotation; a TILTED pair (user 2026-10-16, rot 81 across a slanted beam) is accepted within 6 degrees
        def _ok(h):
            dx, dy = h.dxf.insert.x - a.dxf.insert.x, h.dxf.insert.y - a.dxf.insert.y; d = math.hypot(dx, dy)
            return h is not a and id(h) not in used and abs(h.dxf.rotation - a.dxf.rotation) < 1.0 and 100 < d < 500 and min(abs((math.degrees(math.atan2(dy, dx)) % 180) - ra), 180 - abs((math.degrees(math.atan2(dy, dx)) % 180) - ra)) < 6.0
        cand = [h for h in hats if _ok(h)]
        nxt = hats[hats.index(a) + 1] if hats.index(a) + 1 < len(hats) else None      # user 2026-10-21 (brenda_karka): pairs are drawn/copied as a unit = file-adjacent INSERTs; nearest-neighbour joined marks of NEIGHBOURING pairs (245 apart instead of 288) -> prefer the next INSERT in file order
        b = nxt if (nxt is not None and nxt in cand) else min(cand, key=lambda h: math.dist(a.dxf.insert, h.dxf.insert), default=None)
        if b is None: continue
        used |= {id(a), id(b)}; out.append((a, b))
    return out

def tidy(doc, p, q, label_layer='451TEXT_KORA_100', beam_layer='93_KORA', gap=1.5, clear_label=False):
    """A turned pair is CENTRED on the beam axis (mid of the two outline lines it crosses; both of the user's examples). Moving it along the beam (dx) is OFF unless clear_label=True: the user's
    two examples moved +49 and +11 along the beam with no common anchor (first ended just east of the label, second inside it) - UNVERIFIED rule, ask. Returns (dx, dy) applied to both marks."""
    from ezdxf import bbox
    ms = doc.modelspace(); mx, my = (p.dxf.insert.x + q.dxf.insert.x) / 2, (p.dxf.insert.y + q.dxf.insert.y) / 2; dx = dy = 0.0
    ys = sorted({l.dxf.start.y for l in ms.query('LINE') if l.dxf.layer == beam_layer and abs(l.dxf.start.y - l.dxf.end.y) < 0.5 and min(l.dxf.start.x, l.dxf.end.x) < mx < max(l.dxf.start.x, l.dxf.end.x) and abs(l.dxf.start.y - my) < 60})
    if len(ys) >= 2:
        pair = min(((a, b) for a in ys for b in ys if b > a), key=lambda ab: abs((ab[0] + ab[1]) / 2 - my)); dy = (pair[0] + pair[1]) / 2 - my
    for t in (ms.query('TEXT') if clear_label else []):
        if t.dxf.layer == label_layer and '/' in t.dxf.text:
            b = bbox.extents([t])
            if abs(b.center.x - mx) < 120 and abs(b.center.y - my) < 40 and mx < b.extmax.x + 0.5: dx = b.extmax.x + gap - mx; break
    if abs(dy) < 1: dy = 0.0
    for h in (p, q): h.dxf.insert = (h.dxf.insert.x + dx, h.dxf.insert.y + dy, h.dxf.insert.z)
    return dx, dy

ATT_LO, ATT_HI, ATT_LY, K = 16.5, 28.55, 11.9, 1.328    # number position in the hat's LOCAL frame (block units): mirror sign +1 -> 16.5, -1 -> 28.55, ly 11.9 = the block's own default
def place_numbers(p, q):
    """A turned pair keeps its numbers RIGID with the block (user's example 2026-10-15, red cloud 82107..82258: whole pair rotated 180 deg incl. the attribute, text rotation = block rotation, local
    position unchanged). Moving / rotating an INSERT in ezdxf leaves its ATTRIBs behind, so re-place them: world = ins + R(rot) * (lx * k, ly * k) with lx = sign-dependent local x (mirror sign included).
    (My earlier 'ly 29.97, text rotation 270' came from an earlier hand example the user has since replaced.)"""
    import math
    for h in (p, q):
        r = math.radians(h.dxf.rotation); sx = 1 if h.dxf.xscale > 0 else -1; lx = ATT_LO if sx > 0 else ATT_HI; ux, uy = sx * lx * K, ATT_LY * K
        for t in h.attribs:
            t.dxf.insert = (h.dxf.insert.x + ux * math.cos(r) - uy * math.sin(r), h.dxf.insert.y + ux * math.sin(r) + uy * math.cos(r), 0); t.dxf.rotation = round(h.dxf.rotation) % 360

def wanted(view, rx, ry):
    """clockwise tangent of the offset (rx, ry) from the centre, snapped to a compass view; the dominant axis decides which side of the plan the pair is on"""
    tx, ty = ry, -rx
    return ('E' if tx > 0 else 'W') if abs(tx) >= abs(ty) else ('N' if ty > 0 else 'S')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--dry', action='store_true'); ap.add_argument('--max-y', type=float); ap.add_argument('--min-y', type=float, help='only pairs at or above this y (one plan copy of a file that holds several)'); ap.add_argument('--tidy', default='', help='also tidy pairs already looking these views (e.g. W): centre on the beam, clear of its label'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); ps = pairs(doc, a.max_y, a.min_y)
    mids = [((p.dxf.insert.x + q.dxf.insert.x) / 2, (p.dxf.insert.y + q.dxf.insert.y) / 2) for p, q in ps]
    cx, cy = sum(m[0] for m in mids) / len(mids), sum(m[1] for m in mids) / len(mids); changed = 0
    for (p, q), (mx, my) in zip(ps, mids):
        cur = VIEW[(round(p.dxf.rotation / 90.0) * 90) % 360]; new = wanted(cur, mx - cx, my - cy)
        # a pair whose cut line is vertical (E/W view) lies on a horizontal beam: only north/south sides matter; vertical beams (N/S view) only east/west sides
        if cur in 'EW' and abs(my - cy) < 1e-6: new = cur
        if cur in 'NS' and abs(mx - cx) < 1e-6: new = cur
        if cur in 'EW' and new in 'NS': new = 'E' if my >= cy else 'W'
        if cur in 'NS' and new in 'EW': new = 'S' if mx >= cx else 'N'      # user 2026-10-25 (test_sections 1-1 / 3-3: east beams looked N): vertical beams are turned CLOCKWISE too - east side looks S, west side N (slab on the RIGHT of the view for edge beams)
        print(f'pair at ({mx:.0f},{my:.0f}) looks {cur} -> {new}' + ('' if new != cur else ' (kept)'))
        if new == cur:
            if cur in a.tidy and cur in 'EW':
                dx, dy = tidy(doc, p, q); changed += bool(dx or dy); print(f'   tidy: moved ({dx:.1f},{dy:.1f})')
            continue
        axis, neg = LAYOUT[new]; lo, hi = sorted((p, q), key=lambda h: h.dxf.insert.y if axis == 'y' else h.dxf.insert.x)
        for h, s in ((lo, neg), (hi, -neg)): h.dxf.rotation = ROT[new]; h.dxf.xscale = s * abs(h.dxf.xscale)
        changed += 1
        if cur in 'EW': dx, dy = tidy(doc, p, q); print(f'   tidy: moved ({dx:.1f},{dy:.1f})')
    for p, q in ps: place_numbers(p, q)
    print('centre', round(cx), round(cy), '| flipped', changed, 'of', len(ps))
    if a.dry: return
    backup(a.file, 'star-orient'); doc.saveas(a.file); print('saved', a.file, '| audit errors', len(ezdxf.readfile(a.file).audit().errors))
if __name__ == '__main__': main()
