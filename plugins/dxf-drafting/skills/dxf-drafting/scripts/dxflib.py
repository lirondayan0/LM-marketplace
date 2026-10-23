"""Shared helpers for all dxf-drafting scripts and recipes. Import with:
    import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')); from dxflib import *
Add a helper here the 2nd time you write it in a recipe (see SKILL.md, self-improvement)."""
import collections, sys
sys.stdout.reconfigure(encoding='utf-8')
import ezdxf
from ezdxf import bbox

# Hebrew SHX text is stored as English-keyboard characters; decode with the Hebrew keyboard layout.
HEB = dict(zip("qwertyuiopasdfghjkl;zxcvbnm,./", "/'קראטוןםפשדגכעיחלךףזסבהנמצתץ."))
HEB_FONTS = {'sivan_m', 'sivan', 'hebtxt', 'miryl'}      # SHX fonts that hold Hebrew; extend as found
HEB_STYLES = {'hebrew'}
import json, os
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'profiles')
def load_profile(name='israeli-structural'):
    """Office-specific constants (layers, styles, offsets) as a dict; recipes take --profile NAME so nothing office-specific is hard-coded."""
    with open(os.path.join(PROFILE_DIR, name + '.json'), encoding='utf-8') as f: return json.load(f)
r = lambda v: (round(v.x, 1), round(v.y, 1))

STIRRUP_EXT = {      # beams wider than the user's tables (200): learned 2026-10-21 from the 2 x 38 table rows
    'standard': dict(n=lambda T: 1 if T <= 45 else 2 if T <= 80 else 3 + (T - 85) // 40, c={2: 5.6, 3: 5.4, 4: 7.8, 5: 9.3}, c_far=9.5),
    'transfer': dict(n=lambda T: 1 if T <= 30 else 2 + (T - 35) // 30, c={2: 4.0, 3: 4.0, 4: 5.3, 5: 7.3, 6: 6.9, 7: 8.1}, c_far=8.0)}

STIRRUP_MAX_W = 40.0      # user 2026-10-21: one hoop = two branches, at most 40 cm apart

def stirrup_extend(key, kind='standard'):
    """(n, w) for a stirrup-bearing width KEY (multiple of 5, cm) beyond the user's tables (conventions 'STIRRUPS beyond 200'): number n starts from the fitted progression (a new stirrup every 40 cm standard /
    30 cm transfer); width w = next multiple of 5 above (key-6)/n + c(n) (c = overlap allowance), bumped until the overlap n*w-(key-6) >= 8 per gap, and - USER RULE 2026-10-21 - w <= STIRRUP_MAX_W (40): the
    two branches of a hoop are at most 40 cm apart, so when w would exceed 40 another stirrup is added. UNVERIFIED by the user above 200."""
    E = STIRRUP_EXT[kind]; n = E['n'](key); span = key - 6
    while True:
        if n == 1: return 1, span
        c = E['c'].get(n, E['c_far']); w = int(-(-(span / n + c) // 5) * 5)
        while (n * w - span) / (n - 1) < 8: w += 5
        if w <= STIRRUP_MAX_W: return n, w
        n += 1

def mid_steel(B, H, hollow=False):
    """'Middle steel' (side-face / skin bars between the top and bottom bars; the note `2$d@s`): (diameter mm, max spacing cm, note) - the user's rule (2026-10-21): beam section area B*H < 2000 cm2 -> 8 @ 20;
    2000..10000 -> 8 @ 15; > 10000 -> 10 @ 15; a beam supporting precast hollow-core units -> 12 @ 20 whatever the size."""
    if hollow: d, sp = 12, 20
    else:
        A = B * H; d, sp = (8, 20) if A < 2000 else (8, 15) if A <= 10000 else (10, 15)
    return d, sp, f'2${d}@{sp}'

def stirrup_layout(width, kind='standard', profile='israeli-structural'):
    """(n, w, note, key): number of stirrups, width of each, note text, table row used, for a stirrup-bearing width (beam thickness / stem) in cm - the user's two tables (profile 'stirrup_tables',
    2026-10-15): kind 'standard' (Φ12@15) or 'transfer' (beams carrying a new element rising from them, Φ12/14/16@15 by shear load). The row is the next multiple of 5 above the width; the tables cover
    15..200, wider beams use `stirrup_extend` (rule fitted to the tables, 2026-10-21)."""
    T = load_profile(profile)['stirrup_tables'][kind]; key = max(15, int(-(-width // 5) * 5))
    if str(key) not in T['rows']:
        top = max(int(k) for k in T['rows'])
        if key < top: raise ValueError(f'no {kind} stirrup row for width {width} (table covers 15..{top})')
        import sys; print(f'NOTE stirrup table: width {width:g} is beyond the user table ({kind}: 15..{top}): extended by the fitted rule (dxflib.stirrup_extend) - UNVERIFIED by the user', file=sys.stderr)
        n, w = stirrup_extend(key, kind); return n, w, T['note'], key
    n, w = T['rows'][str(key)]; return n, w, T['note'], key

def hebrew_style(doc, name):
    s = doc.styles.get(name) if name in doc.styles else None
    font = (s.dxf.font if s else '').lower().rsplit('.', 1)[0]
    return font in HEB_FONTS or name.lower() in HEB_STYLES

def decode(t):
    return ''.join(HEB.get(c, c) for c in t.replace('%%U', '').replace('%%u', ''))

def encode(heb):
    """Hebrew -> English-keyboard characters, for writing new text in a Hebrew SHX style."""
    inv = {v: k for k, v in HEB.items()}
    return ''.join(inv.get(c, c) for c in heb)

def text_of(doc, e):
    """(raw, decoded) for TEXT/MTEXT, else None."""
    if e.dxftype() == 'TEXT': raw, st = e.dxf.text, e.dxf.style
    elif e.dxftype() == 'MTEXT': raw, st = e.text, e.dxf.style
    else: return None
    return raw, (decode(raw) if hebrew_style(doc, st) else raw)

def describe(doc, e):
    t, L = e.dxftype(), e.dxf.layer
    if t == 'LINE': return f'LINE {L} {r(e.dxf.start)} {r(e.dxf.end)}'
    if t == 'LWPOLYLINE': return f'POLY {L} {[(round(float(x),1), round(float(y),1)) for x, y, *_ in e.get_points()]}{" closed" if e.closed else ""}'
    if t in ('TEXT', 'MTEXT'):
        raw, dec = text_of(doc, e)
        return f'{t} {L} {raw!r}' + (f' = {dec!r}' if dec != raw else '') + f' @{r(e.dxf.insert)} h={e.dxf.height if t == "TEXT" else e.dxf.char_height} style={e.dxf.style}'
    if t == 'DIMENSION':
        return f'DIM {L} style={e.dxf.dimstyle} text={e.dxf.text!r} meas={e.get_measurement():.1f} def={r(e.dxf.defpoint)}'
    if t == 'INSERT': return f'INSERT {L} {e.dxf.name} @{r(e.dxf.insert)} {[(a.dxf.tag, a.dxf.text) for a in e.attribs]}'
    if t == 'CIRCLE': return f'CIRCLE {L} c={r(e.dxf.center)} r={e.dxf.radius:.1f}'
    if t == 'ARC': return f'ARC {L} c={r(e.dxf.center)} r={e.dxf.radius:.1f} {e.dxf.start_angle:.0f}-{e.dxf.end_angle:.0f}'
    if t == 'HATCH': return f'HATCH {L} pattern={e.dxf.pattern_name} paths={len(e.paths)}'
    return f'{t} {L}'

def in_box(e, x0, x1, y0, y1):
    b = bbox.extents([e])
    return b.has_data and x0 < b.extmin.x and b.extmax.x < x1 and y0 < b.extmin.y and b.extmax.y < y1

def render_png(doc, box, out, layout=None, size=(12, 8), dpi=100):
    """Render region box=(x0,x1,y0,y1) of modelspace (or given layout) to PNG. Look at it after every write."""
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    fig = plt.figure(figsize=size, dpi=dpi); ax = fig.add_axes([0, 0, 1, 1])
    lay = layout or doc.modelspace()
    ctx = RenderContext(doc); ctx.set_current_layout(lay)
    Frontend(ctx, MatplotlibBackend(ax)).draw_layout(lay)
    ax.set_xlim(box[0], box[1]); ax.set_ylim(box[2], box[3]); fig.savefig(out); plt.close(fig)

def diff(doc_a, doc_b):
    """(added, removed) entity descriptions in B vs A. Learn conventions from before/after pairs."""
    ca = collections.Counter(describe(doc_a, e) for e in doc_a.modelspace())
    cb = collections.Counter(describe(doc_b, e) for e in doc_b.modelspace())
    return list((cb - ca).elements()), list((ca - cb).elements())

def target_cells(doc, layer, min_w=100):
    """Target boxes the user drew (white cells on `layer`): the outer rectangle split by its vertical dividers, left to right.
    Returns [(x0, y0, x1, y1, free)]; free = nothing but the cell lines / markup inside. Used by recipes with --cell N|auto."""
    from ezdxf import bbox as _bb
    msp = doc.modelspace(); rects = []; vlines = []
    for e in msp:
        if e.dxf.layer != layer: continue
        b = _bb.extents([e])
        if e.dxftype() == 'LWPOLYLINE' and e.closed and b.size.x > min_w: rects.append(b)
        elif e.dxftype() == 'LINE' and b.size.x < 2 and b.size.y > min_w: vlines.append(b.center.x)
    cells = []
    for r in rects:
        inside = [x for x in vlines if r.extmin.x < x < r.extmax.x]
        xs = sorted({r.extmin.x, r.extmax.x, *inside})
        for a, b in zip(xs, xs[1:]): cells.append([a, r.extmin.y, b, r.extmax.y])
    out = []
    for c in cells:
        busy = False
        for e in msp:
            if e.dxf.layer in (layer, 'SHINUIM-TIKUNIM', '60_HATCH_ADAMA'): continue
            try: b = _bb.extents([e])
            except Exception: continue
            if b.has_data and c[0] < b.center.x < c[2] and c[1] < b.center.y < c[3]: busy = True; break
        out.append((*c, not busy))
    return out

def backup(path, tag='run', keep=6):
    """Safety copies before a recipe overwrites the user's file: FILE.bak (latest, as always) + a timestamped snapshot FILE.bak-<tag>-HHMMSS so the next review can diff against
    exactly what we generated (FILE.bak alone is overwritten by every run). Old snapshots with the same prefix are pruned to `keep`. Returns the snapshot path."""
    import shutil, time, glob
    shutil.copy2(path, os.path.splitext(path)[0] + '.bak')
    snap = f"{path}.bak-{tag}-{time.strftime('%H%M%S')}"
    shutil.copy2(path, snap)
    old = sorted(glob.glob(f"{path}.bak-{tag.split('-')[0]}-*"), key=os.path.getmtime)
    for f in old[:-keep]:
        try: os.remove(f)
        except OSError: pass
    return snap

def levels(vals, tol=0.3):
    """Cluster values closer than tol into distinct levels (outline x/y stations)."""
    out = []
    for v in sorted(vals):
        if not out or v - out[-1] > tol: out.append(v)
    return out


def block_points(e, name='dot barzel'):
    """World positions of every `name` insert reachable from INSERT e, including anonymous nested blocks (*U..)
    that Divide/Measure create. Uses virtual_entities() so the parent transforms are applied."""
    if e.dxftype() != 'INSERT': return
    if e.dxf.name == name: yield (e.dxf.insert.x, e.dxf.insert.y); return
    if e.dxf.name.startswith('*'):
        for v in e.virtual_entities():
            yield from block_points(v, name)

def entity_key(e, nd=1):
    """Hashable geometric signature (type, layer, rounded coordinates) to compare entities across files / find what a recipe added."""
    t, L, f = e.dxftype(), e.dxf.layer, lambda v: round(float(v), nd)
    if t == 'LINE': return (t, L, tuple(sorted([(f(e.dxf.start.x), f(e.dxf.start.y)), (f(e.dxf.end.x), f(e.dxf.end.y))])))
    if t == 'LWPOLYLINE': return (t, L, tuple((f(a), f(b)) for a, b, *_ in e.get_points()))
    if t == 'INSERT': return (t, L, e.dxf.name, f(e.dxf.insert.x), f(e.dxf.insert.y))
    if t == 'TEXT': return (t, L, e.dxf.text, f(e.dxf.insert.x), f(e.dxf.insert.y))
    return (t, L, e.dxf.handle)


def dim_angle(d):
    """Direction (degrees) a linear/aligned DIMENSION measures along. Aligned dims (dimtype&7 == 1) carry NO angle attribute: it is the direction p1 -> p2 (pitfall: .get('angle', 0) reads 0 and misclassifies them as horizontal)."""
    import math
    if d.dxf.dimtype & 7 == 1:
        p, q = d.dxf.defpoint2, d.dxf.defpoint3
        return math.degrees(math.atan2(q.y - p.y, q.x - p.x))
    return d.dxf.get('angle', 0) or 0


def step_groups(segs, gap_lo=20.0, gap_hi=40.0, tol=1.5, min_lines=3, min_overlap=50.0):
    """Stair treads / risers drawn as equally spaced PARALLEL straight segments (dicts with c = position across, lo..hi = extent along).
    Returns [[indices sorted by c], ...] for every run of >= min_lines segments whose neighbours are gap_lo..gap_hi apart (equal within tol) and overlap >= min_overlap.
    User rule 2026-10-13: a flight of stairs gets ONE overall dimension (first to last step line); the interior step lines are not dimensioned."""
    order = sorted(range(len(segs)), key=lambda i: segs[i]['c']); groups = []; chain = []
    def close():
        if len(chain) >= min_lines: groups.append(list(chain))
    for i in order:
        if not chain: chain = [i]; continue
        g = segs[i]['c'] - segs[chain[-1]]['c']
        if g < 1.0: continue                                           # duplicate line on the same position
        prev = segs[chain[-1]]['c'] - segs[chain[-2]]['c'] if len(chain) > 1 else None
        ov = min(segs[i]['hi'], segs[chain[-1]]['hi']) - max(segs[i]['lo'], segs[chain[-1]]['lo'])
        if gap_lo <= g <= gap_hi and ov >= min_overlap and (prev is None or abs(g - prev) <= tol): chain.append(i)
        else: close(); chain = [i]
    close()
    return groups


def blue_clouds(doc, aci=177, layer='claude'):
    """bbox (x0, y0, x1, y1) of the user's BLUE clouds on layer 'claude' (user 2026-10-13: a blue cloud marks a staircase drawn on 15_DASHED)"""
    out = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer.lower() == layer and e.dxf.color == aci:
            xs = [q[0] for q in e.get_points('xy')]; ys = [q[1] for q in e.get_points('xy')]
            out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def flight_chains(levels, gap_lo=20.0, gap_hi=40.0, tol=0.6, min_levels=3):
    """runs of >= min_levels equally spaced levels (tread / riser spacing gap_lo..gap_hi, equal within tol): the step positions of a flight of stairs"""
    lv = sorted(set(round(v, 1) for v in levels)); out = []; chain = []
    for v in lv:
        if chain and not (gap_lo <= v - chain[-1] <= gap_hi and (len(chain) < 2 or abs((v - chain[-1]) - (chain[-1] - chain[-2])) <= tol)):
            if len(chain) >= min_levels: out.append(chain)
            chain = [chain[-1]] if chain and gap_lo <= v - chain[-1] <= gap_hi else []
        chain.append(v)
    if len(chain) >= min_levels: out.append(chain)
    return out
