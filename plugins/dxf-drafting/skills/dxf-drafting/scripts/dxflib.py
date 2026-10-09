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
