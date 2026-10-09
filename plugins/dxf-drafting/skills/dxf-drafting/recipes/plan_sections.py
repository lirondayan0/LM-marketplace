"""Recipe: create ALL the sections of a plan floor from scratch and place their cut marks on the plan.
  python plan_sections.py FILE --box X0 Y0 X1 Y1 --grid X Y [--shafts] [--dry] [--report OUT.md]
Pipeline (everything the user taught, in order):
 1. scripts/plan_beams.py `inventory`: EVERY `b/h` label of the floor becomes a beam record (outline strip, else the single edge line, else the label's own rotation), with both
    neighbouring slabs (`D=a+b`) and the panel span relation (BEARING / CORES).
 2. One section per distinct type (b, h, slab thickness on each side, topping, relation): BEARING on a beam >= 50 wide -> ledge beam (hollow-core on ledges); CORES, or panels on a wall /
    narrow beam (< 50, approximation) -> cast beam with the hollow-core cores as circles; no slab beside the beam -> free beam. One slab side -> slab on the RIGHT of the view.
    Sections are numbered SEQUENTIALLY 1, 2, 3 ... without gaps (user, 2026-10-06); with --shafts the general section 5 (shaft / stairwell walls) is copied into the next number.
 3. Identical sections: beams whose type is the same share ONE section and number; the cell says `זהה ל-N קורות` (identical for N beams) and the report lists the beams of each group.
 4. A grid of white cells (layer 72_MISGERET_WIN, 4 per row, 400 wide, height from the section) starting at --grid (top-left); each section is drawn into its cell by ledge_beam.run.
 5. One cut-mark pair per beam (cut_marks.py logic: copies of the user's pairs), perpendicular to the beam at the label, looking so that the slab is on the right.
The report (--report) lists every section, every beam with its section, the detection source (strip / line / label) and what is an approximation. Writes a timestamped snapshot first.
Use --dry for the catalogue only."""
import argparse, collections, math, os, sys, types as _types
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'scripts')); sys.path.insert(0, HERE)
from dxflib import *
import plan_beams as pbm, cut_marks as cm, shaft_walls as sw
import ledge_beam as lb

def parse_slab(txt):
    if not txt: return None
    a, b = (txt.split('+') + ['0'])[:2]; return float(a), float(b)

def classify(bm):
    """-> (type tuple, note). type = (kind, W, H, sides, -, -, T); note = approximation text ('' when the taught rules apply directly)."""
    b, h = bm['b'], bm['h']; L, R = parse_slab(bm['L']), parse_slab(bm['R']); have = [x for x in (L, R) if x]
    if not have: return ('cast', b, h, 'none', None, None, 0.0), 'no slab label near this beam: drawn as a free beam (UNVERIFIED)'
    T = max(x[1] for x in have); both = len(have) == 2
    if bm['relation'] == 'BEARING' and b >= 50:
        if h - max(x[0] for x in have) - T >= 25: return ('ledge', b, h, 'both' if both else 'right', None, None, T), ''
        return ('cast', b, h, 'both' if both else 'right', None, None, T), 'ledge below the panels too small: drawn as cast beam (approximation)'
    note = ''
    if bm['relation'] == 'BEARING': note = f'panels bear on a {b}-wide beam / wall: drawn as cast beam with cores (approximation, no ledge detail taught)'
    if h - max(x[0] + x[1] for x in have) < 20: note = (note + '; ' if note else '') + 'little depth below the slab'
    return ('cast', b, h, 'both' if both else 'right', None, None, T), note

def view_for(bm):
    """Direction the cut looks, so the (single) slab is on the right; both sides / free beam: E for E-W beams, N for N-S beams (the user's choices on the mezzanine)."""
    both = bool(bm['L'] and bm['R']) or not (bm['L'] or bm['R'])
    if both: return 'E' if abs(bm['u'][0]) >= abs(bm['u'][1]) else 'N'
    n = bm['n']; ns = n if bm['L'] else (-n[0], -n[1]); v = (-ns[1], ns[0])
    return ('E' if v[0] > 0 else 'W') if abs(v[0]) >= abs(v[1]) else ('N' if v[1] > 0 else 'S')

def sides_thickness(bm, view):
    """(slab on the view's right, on its left) as (panel, topping) tuples; the right-hand vector of a view (vx, vy) is (vy, -vx)."""
    v = {'E': (1, 0), 'W': (-1, 0), 'N': (0, 1), 'S': (0, -1)}[view]; r = (v[1], -v[0]); n = bm['n']
    left_is_right = (n[0] * r[0] + n[1] * r[1]) > 0
    L, R = parse_slab(bm['L']), parse_slab(bm['R'])
    return (L, R) if left_is_right else (R, L)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True); ap.add_argument('--grid', nargs=2, type=float, required=True)
    ap.add_argument('--start', type=int, default=1); ap.add_argument('--profile', default='israeli-structural'); ap.add_argument('--report'); ap.add_argument('--dry', action='store_true')
    ap.add_argument('--cols', type=int, default=4); ap.add_argument('--no-marks', action='store_true'); ap.add_argument('--shafts', action='store_true', help='also copy the general section 5 (shaft walls) into the next number and mark the shaft walls')
    a = ap.parse_args(); lb.apply_profile(a.profile); prof = lb.PROF; bottom0 = prof['outline']['cell_beam_bottom_y']
    doc = ezdxf.readfile(a.file); msp = doc.modelspace(); bx = a.box
    beams, _ = pbm.inventory(doc, bx, prof)
    types = collections.OrderedDict(); notes = {}
    for bm in beams:
        ty, note = classify(bm); view = view_for(bm); sr, sl = sides_thickness(bm, view)
        key = (ty[0], ty[1], ty[2], ty[3], sr[0] if sr else None, sl[0] if sl else None, ty[6])
        types.setdefault(key, []).append((bm, view))
        if note: notes.setdefault(key, set()).add(note)
    order = sorted(types, key=lambda k: (k[1], k[2], k[0], k[3], k[4] or 0, k[5] or 0))
    nums = {k: a.start + i for i, k in enumerate(order)}; nsec = a.start + len(order)
    def desc(k):
        kind, W, H, sd, S_r, S_l, T = k
        what = 'ledge beam (panels on ledges)' if kind == 'ledge' else ('free beam' if sd == 'none' else 'cast beam (panels run past, cores)')
        return f'{what} {W}/{H}, ' + ((f"slab on both sides: panel {S_r:.0f} (right) / {S_l:.0f} (left)" if S_l else 'slab on one side: panel %.0f' % S_r) + f' + topping {T:.0f}' if sd != 'none' else 'no slab')
    lines = [f'# Sections of {os.path.basename(a.file)} - box {bx}', '', f'{len(beams)} beams (every b/h label of the floor), {len(order)} different sections' + (f' + general shaft section {nsec}-{nsec}' if a.shafts else '') + ', numbered 1..N without gaps.', '',
             '| Section | what | applies to | identical for |', '|---|---|---|---|']
    for k in order:
        n = len(types[k]); lines.append(f'| {nums[k]}-{nums[k]} | {desc(k)} | {n} beam(s), e.g. at {types[k][0][0]["at"]} | ' + (f'**{n} beams: same section {nums[k]}-{nums[k]}**' if n > 1 else '-') + ' |')
    lines += ['', '## Beam by beam', '', '| label | position | section | outline found by |', '|---|---|---|---|']
    for k in order:
        for bm, view in types[k]: lines.append(f"| {bm['label']} | {bm['at']} | {nums[k]}-{nums[k]} (looking {view}) | {bm['source']} |")
    lines += ['', '## Approximations / to verify', '']
    lines += [f'- section {nums[k]}-{nums[k]}: ' + '; '.join(sorted(notes[k])) for k in order if k in notes]
    lines += [f"- {bm['label']} at {bm['at']} (section {nums[k]}-{nums[k]}): orientation taken from the label only (no outline found)" for k in order for bm, v in types[k] if bm['source'] == 'label']
    print('\n'.join(lines))
    if a.report: open(a.report, 'w', encoding='utf-8').write('\n'.join(lines))
    if a.dry: return
    backup(a.file, 'plansections')
    # ---- cells
    cw, gx, gy = 400.0, a.grid[0], a.grid[1]; allk = list(order) + (['SHAFT'] if a.shafts else []); rows = [allk[i:i + a.cols] for i in range(0, len(allk), a.cols)]; cell_of, bottom_of = {}, {}
    y_top = gy; cell_layer = prof['layers']['target_cell']
    def margin_b(k):
        if k == 'SHAFT': return bottom0
        return max(bottom0, k[2] + 100.0, ((k[2] - (k[4] or 0) - k[6]) if k[3] != 'none' else 0) + 170.0)
    for row in rows:
        mb = max(margin_b(k) for k in row); hh = max(450.0, mb + max((k[2] if k != 'SHAFT' else 74) for k in row) + 110.0); hh = math.ceil(hh / 10) * 10; y0 = y_top - hh; w = cw * len(row)
        msp.add_lwpolyline([(gx, y0), (gx + w, y0), (gx + w, y_top), (gx, y_top)], close=True, dxfattribs=dict(layer=cell_layer))
        for i in range(1, len(row)): msp.add_line((gx + cw * i, y0), (gx + cw * i, y_top), dxfattribs=dict(layer=cell_layer))
        for i, k in enumerate(row): cell_of[k] = [gx + cw * i, y0, cw, hh]; bottom_of[k] = mb
        y_top = y0 - 100.0
    # ---- sections
    for k in order:
        kind, W, H, sd, S_r, S_l, T = k; num = nums[k]; n = len(types[k])
        D = (S_r + T) if (kind == 'cast' and sd != 'none') else (S_r or 0)
        ns = _types.SimpleNamespace(file=a.file, name=f'{num}-{num}', profile=a.profile, box=cell_of[k], cell=None, beam=[W, H], slab=D, topping=T,
                                    slab_left=(None if not S_l else (S_l if kind == 'ledge' else S_l + T)), slab_right=None, sides=sd, kind=kind, beam_bottom=bottom_of[k], replace=False, dims_only=False,
                                    o=None, dry=False, png=None, nosave=True, note=(f'זהה ל-{n} קורות' if n > 1 else None))
        lb.run(ns, doc)
    print(f'drew {len(order)} sections in {len(rows)} rows')
    # ---- shaft section: copy of the general 5-5 under the next number + marks on the shaft walls (all looking N as on the mezzanine)
    shaft_marks = []
    if a.shafts:
        g = prof['general_sections']['5']; box = g['box']; to = cell_of['SHAFT']; dx, dy = to[0] - box[0], to[1] - box[1]
        for e in list(msp):
            if e.dxf.layer in ('72_MISGERET_WIN', 'SHINUIM-TIKUNIM'): continue
            try: b = bbox.extents([e])
            except Exception: continue
            if b.has_data and box[0] < b.center.x < box[2] and box[1] < b.center.y < box[3]:
                c = e.copy(); msp.add_entity(c); c.translate(dx, dy, 0)
                if c.dxftype() == 'DIMENSION':
                    from ezdxf.entities import DimStyleOverride
                    try: DimStyleOverride(c).render()
                    except Exception: pass
                elif c.dxftype() == 'TEXT' and '5-5' in c.dxf.text: c.dxf.text = c.dxf.text.replace('5-5', f'{nsec}-{nsec}')
        slabs_ = sw.slab_points(doc, bx); st_ = sw.strips(doc, '93_KORA')
        for name, lx, ly in sw.label_points(doc, sw.SHAFT_WORDS, bx):
            cands = []
            for s in st_:
                c = (s['pos'], s['mid']) if s['o'] == 'v' else (s['mid'], s['pos']); d = math.dist(c, (lx, ly)); side = sw.slab_side(s, slabs_)
                if d <= 450 and side: cands.append((s['o'] != 'v', d, s, c, side))
            if cands: _, d, s, c, side = min(cands, key=lambda t: t[:2]); shaft_marks.append((c, s['w'], 'N' if s['o'] == 'v' else sw.VIEW[(s['o'], side)]))
    # ---- marks
    placed = 0
    if not a.no_marks:
        block = prof.get('cut_mark', {}).get('block', 'hat')
        def pair(view, at, width, num):
            src = cm.sources(doc, view, block)
            if len(src) < 2: print('no source marks for view', view); return 0
            axis, neg = cm.LAYOUT[view]; half = max(81.0, width / 2 + 70.0); x, y = at
            pos = {neg: (x - half, y) if axis == 'x' else (x, y - half), -neg: (x + half, y) if axis == 'x' else (x, y + half)}
            for sgn in (-1, 1): cm.clone(doc, src[sgn], pos[sgn][0], pos[sgn][1], num)
            return 1
        for k in order:
            for bm, view in types[k]: placed += pair(view, bm['cl'], bm['b'], nums[k])
        for c, w, view in shaft_marks: placed += pair(view, c, w, nsec)
    doc.saveas(a.file); print(f'placed {placed} mark pairs (incl. {len(shaft_marks)} on shaft walls); saved {a.file}; audit errors', len(ezdxf.readfile(a.file).audit().errors))

if __name__ == '__main__': main()
