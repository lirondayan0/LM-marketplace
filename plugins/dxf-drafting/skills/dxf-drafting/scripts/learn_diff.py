"""Learn from the user's hand edits: compare their DXF with a snapshot of what we last generated, inside a region, and print what they added / removed / changed.
  python learn_diff.py USER.dxf SNAPSHOT.dxf --box X0 Y0 X1 Y1 [--dy DY] [--dx DX] [--auto-shift] [--layers L1,L2] [--ignore-layers SHINUIM-TIKUNIM]
Entities are matched by (type, layer, rounded bounding box, text); unmatched ones are listed with decoded Hebrew text, dimension style/measurement/rendered text
and bbox. --auto-shift finds the most common translation between unmatched entities (the user often moves a whole drawing) and re-matches after it.
Markup layers (clouds/X marks) are reported separately with their bbox so they can be read next. Used 2026-10-06 to read the user's corrections of the gallery sections."""
import argparse, collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxflib import *

MARKUP = ('SHINUIM-TIKUNIM', '60_HATCH_ADAMA')

def sig(doc, e, dx=0.0, dy=0.0, tol=0.5):
    try: b = bbox.extents([e])
    except Exception: return None
    if not b.has_data: return None
    t = e.dxftype(); extra = ''
    if t == 'TEXT': extra = e.dxf.text
    elif t == 'DIMENSION': extra = e.dxf.dimstyle
    q = lambda v: round(v / tol) * tol
    return (t, e.dxf.layer, q(b.extmin.x + dx), q(b.extmin.y + dy), q(b.extmax.x + dx), q(b.extmax.y + dy), extra), b

def collect(doc, box, layers=None, ignore=()):
    x0, y0, x1, y1 = box; out = []
    for e in doc.modelspace():
        if e.dxf.layer in ignore or (layers and e.dxf.layer not in layers): continue
        r = sig(doc, e)
        if r and x0 < r[1].center.x < x1 and y0 < r[1].center.y < y1: out.append((e, r[0], r[1]))
    return out

def describe_full(doc, e, b):
    d = describe(doc, e)
    if e.dxftype() == 'DIMENSION':
        try:
            txt = [v.dxf.text if v.dxftype() == 'TEXT' else getattr(v, 'text', '') for v in e.virtual_entities() if v.dxftype() in ('TEXT', 'MTEXT')]
            d += f' dimtype={e.dxf.dimtype} rendered={txt}'
        except Exception: pass
    return f'{d} bbox=({b.extmin.x:.1f},{b.extmin.y:.1f})-({b.extmax.x:.1f},{b.extmax.y:.1f})'

def best_shift(a_only, b_only, tol=0.5):
    """Most common (dx, dy) between unmatched user entities and unmatched snapshot entities of the same type+layer (+text)."""
    votes = collections.Counter()
    byk = collections.defaultdict(list)
    for e, s, b in a_only: byk[(s[0], s[1], s[6])].append(b)
    for e, s, b in b_only:
        for ub in byk.get((s[0], s[1], s[6]), [])[:50]:
            sw, sh = round(ub.size.x - b.size.x, 0), round(ub.size.y - b.size.y, 0)
            if sw == 0 and sh == 0: votes[(round(ub.extmin.x - b.extmin.x, 1), round(ub.extmin.y - b.extmin.y, 1))] += 1
    return votes.most_common(1)[0] if votes else (None, 0)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('user'); ap.add_argument('snapshot'); ap.add_argument('--box', nargs=4, type=float, required=True)
    ap.add_argument('--dx', type=float, default=0); ap.add_argument('--dy', type=float, default=0); ap.add_argument('--auto-shift', action='store_true')
    ap.add_argument('--layers'); ap.add_argument('--ignore-layers', default='')
    a = ap.parse_args(); layers = set(a.layers.split(',')) if a.layers else None; ign = set(filter(None, a.ignore_layers.split(',')))
    U, S = ezdxf.readfile(a.user), ezdxf.readfile(a.snapshot)
    ub = collect(U, a.box, layers, ign)
    box_s = (a.box[0] - a.dx, a.box[1] - a.dy, a.box[2] - a.dx, a.box[3] - a.dy)
    sb = collect(S, box_s, layers, ign)
    def match(ub, sb, dx, dy):
        cs = collections.Counter(s for _, s, _ in sb if s is not None)
        shifted = collections.Counter()
        for e, s, b in sb: shifted[(s[0], s[1], round((b.extmin.x + dx) / 0.5) * 0.5, round((b.extmin.y + dy) / 0.5) * 0.5, round((b.extmax.x + dx) / 0.5) * 0.5, round((b.extmax.y + dy) / 0.5) * 0.5, s[6])] += 1
        ua, ok = [], collections.Counter(shifted)
        for e, s, b in ub:
            if ok[s] > 0: ok[s] -= 1
            else: ua.append((e, s, b))
        left = []
        for e, s, b in sb:
            k = (s[0], s[1], round((b.extmin.x + dx) / 0.5) * 0.5, round((b.extmin.y + dy) / 0.5) * 0.5, round((b.extmax.x + dx) / 0.5) * 0.5, round((b.extmax.y + dy) / 0.5) * 0.5, s[6])
            if ok[k] > 0: ok[k] -= 1; left.append((e, s, b))
        return ua, left
    dx, dy = a.dx, a.dy
    only_u, only_s = match(ub, sb, dx, dy)
    if a.auto_shift and only_u:
        (sh, n) = best_shift(only_u, only_s)
        if sh: dx, dy = sh; print(f'auto-shift: user entities moved by ({dx}, {dy}) for {n} matches'); only_u, only_s = match(ub, sb, dx, dy)
    mk_u = [x for x in only_u if x[1][1] in MARKUP]; only_u = [x for x in only_u if x[1][1] not in MARKUP]
    mk_s = [x for x in only_s if x[1][1] in MARKUP]; only_s = [x for x in only_s if x[1][1] not in MARKUP]
    print(f'user entities {len(ub)}, snapshot entities {len(sb)}; only in USER {len(only_u)}, only in SNAPSHOT {len(only_s)} (shift {dx}, {dy})')
    grp = lambda L: dict(collections.Counter(f'{s[0]} {s[1]}' for _, s, _ in L))
    print('USER added  :', grp(only_u)); print('USER removed:', grp(only_s))
    print('--- added by the user'); [print('  +', describe_full(U, e, b)[:300]) for e, s, b in only_u]
    print('--- removed by the user'); [print('  -', describe_full(S, e, b)[:300]) for e, s, b in only_s]
    if mk_u or mk_s:
        print('--- markup (read these: clouds/X marks)')
        for e, s, b in mk_u: print(f'  + {s[0]} {s[1]} bbox=({b.extmin.x:.0f},{b.extmin.y:.0f})-({b.extmax.x:.0f},{b.extmax.y:.0f})')
        for e, s, b in mk_s: print(f'  - {s[0]} {s[1]} bbox=({b.extmin.x:.0f},{b.extmin.y:.0f})-({b.extmax.x:.0f},{b.extmax.y:.0f})')

if __name__ == '__main__': main()
